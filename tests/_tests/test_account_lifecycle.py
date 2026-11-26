"""Account lifecycle through WSGI, the CLI, and legacy profiles.

@license: GNU GPL, see COPYING for details.
"""

from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

from MoinMoin import user
from MoinMoin.Page import Page
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.http import Client, create_environ
from MoinMoin.web.request import Request
from MoinMoin.wsgiapp import Application
from tests._tests import wikiconfig


ADMIN = 'LifecycleAdmin'
NAME = 'LifecycleEditor'
EMAIL = 'editor@example.test'
PASSWORD = 'Lifecycle-Synthetic-Password9!'
ADMIN_PAGE = '/LifecycleAdminPage'
PRIVATE_PAGE = '/LifecyclePrivate'


@pytest.fixture(scope='module')
def underlay(tmp_path_factory):
    temp = tmp_path_factory.mktemp('wiki-underlay')
    repo = Path(__file__).resolve().parents[2]
    with tarfile.open(repo / 'wiki/underlay.tar') as archive:
        archive.extractall(temp, filter='data')
    return temp / 'underlay'


@pytest.fixture
def wiki(tmp_path, underlay):
    repo = Path(__file__).resolve().parents[2]
    shutil.copytree(repo / 'wiki/data', tmp_path / 'data')
    shutil.copytree(underlay, tmp_path / 'underlay')
    (tmp_path / 'wikiconfig.py').write_text(f'''from tests._tests.wikiconfig import Config as BaseConfig

class Config(BaseConfig):
    data_dir = {str(tmp_path / 'data')!r}
    data_underlay_dir = {str(tmp_path / 'underlay')!r}
''')

    class Config(wikiconfig.Config):
        cfg_mtime = 1
        data_dir = str(tmp_path / 'data')
        data_underlay_dir = str(tmp_path / 'underlay')
        acl_rights_default = 'All:read'
        superuser = [ADMIN]
        actions_superuser = []
        mail_from = 'wiki@example.test'
        mail_smarthost = 'mail.example.test'
        surge_action_limits = {}

    def disk_page(name, content):
        page = tmp_path / 'data/pages' / name.lstrip('/')
        (page / 'revisions').mkdir(parents=True)
        (page / 'current').write_text('00000001\n')
        (page / 'revisions/00000001').write_text(content, encoding='utf-8')

    disk_page(ADMIN_PAGE, '<<SystemAdmin>>\n')
    disk_page(PRIVATE_PAGE, '#acl LifecycleEditor:read All:\nOnly the subscribed editor sees this.\n')
    context = AllContext(Request(create_environ(), given_config=Config))
    return context, Application(Config)


def create_account(context, name, email, subscriptions=()):
    profile = user.User(context, auth_method='new-user')
    profile.name = name
    profile.email = email
    profile.enc_password = user.encodePassword(context.cfg, PASSWORD)
    profile.subscribed_pages = list(subscriptions)
    profile.save()
    return profile


def login(client, name):
    return client.post('/FrontPage', data={
        'action': 'login', 'login': '1', 'name': name, 'password': PASSWORD,
    })


class Forms(HTMLParser):
    def __init__(self, response):
        assert response.status_code == 200
        super().__init__()
        self.forms = []
        self.fields = None
        self.feed(response.get_data(as_text=True))

    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            self.fields = {}
            self.forms.append(self.fields)
        elif tag == 'input' and self.fields is not None:
            field = dict(attrs)
            if field.get('type') == 'submit':
                return
            if 'name' in field and 'value' in field:
                self.fields[field['name']] = field['value']

    def handle_endtag(self, tag):
        if tag == 'form':
            self.fields = None


def control(client, uid, operation):
    page = client.get(ADMIN_PAGE + '?sysadm=users')
    return next(fields for fields in Forms(page).forms
                if fields.get('uid') == uid and fields.get('operation') == operation)


def test_browser_lifecycle_keeps_settings_and_revokes_sessions(wiki, tmp_path):
    context, app = wiki
    create_account(context, ADMIN, 'admin@example.test')
    editor = create_account(context, NAME, EMAIL, [PRIVATE_PAGE.lstrip('/')])
    original_hash = editor.enc_password
    admin_client, editor_client = Client(app), Client(app)
    assert 'Set-Cookie' in login(admin_client, ADMIN).headers
    assert 'Set-Cookie' in login(editor_client, NAME).headers
    assert b'Only the subscribed editor sees this.' in editor_client.get(PRIVATE_PAGE).data
    page = Page(context, PRIVATE_PAGE[1:])
    assert EMAIL in page.getSubscribers(context, include_self=True)['en']
    fields = control(admin_client, editor.id, 'disable')

    editor_client.post(ADMIN_PAGE, data=fields)
    admin_client.get(ADMIN_PAGE, query_string=fields)
    admin_client.post(ADMIN_PAGE, data=dict(fields, ticket='invalid'))
    assert user.User(context, editor.id).valid

    response = admin_client.post(ADMIN_PAGE, data=fields)
    assert b'disabled.' in response.data
    account = user.User(context, editor.id)
    assert account.disabled and not account.valid
    assert not account.disable()
    assert (account.name, account.email, account.enc_password) == (NAME, EMAIL, original_hash)
    assert account.subscribed_pages == [PRIVATE_PAGE[1:]]
    assert not account.mailAccountData()[0]
    assert page.getSubscribers(context, include_self=True) == {}
    assert user.getUserId(context, NAME, include_disabled=True) == editor.id
    assert user.get_by_email_address(context, EMAIL.upper(), include_disabled=True).id == editor.id
    assert b'Only the subscribed editor sees this.' not in editor_client.get(PRIVATE_PAGE).data
    assert b'Invalid username or password.' in login(Client(app), NAME).data

    fields = control(admin_client, editor.id, 'enable')
    assert b'enabled.' in admin_client.post(ADMIN_PAGE, data=fields).data
    assert EMAIL in page.getSubscribers(context, include_self=True)['en']
    assert 'Set-Cookie' in login(editor_client, NAME).headers

    fields = control(admin_client, editor.id, 'delete')
    assert b'Confirm this deletion' in admin_client.post(
        ADMIN_PAGE, data=dict(fields, operation='confirm-delete')).data
    prompt = admin_client.post(ADMIN_PAGE, data=fields)
    assert b'Permanently delete the account' in prompt.data
    assert user.User(context, editor.id).exists()
    confirmation = next(fields for fields in Forms(prompt).forms
                        if fields.get('operation') == 'confirm-delete')
    assert b'deleted.' in admin_client.post(ADMIN_PAGE, data=confirmation).data
    assert not user.User(context, editor.id).exists()
    assert not user.getUserId(context, NAME, include_disabled=True)
    assert user.get_by_email_address(context, EMAIL, include_disabled=True) is None
    assert b'Only the subscribed editor sees this.' not in editor_client.get(PRIVATE_PAGE).data
    assert (tmp_path / 'data/pages/LifecyclePrivate/revisions/00000001').read_bytes().endswith(
        b'Only the subscribed editor sees this.\n')


def test_disabled_identity_blocks_registration_and_preferences(wiki):
    context, app = wiki
    disabled = create_account(context, NAME, EMAIL)
    disabled.disable()
    client = Client(app)
    form = client.get('/FrontPage?action=newaccount')
    fields = next(fields for fields in Forms(form).forms if fields.get('action') == 'newaccount')
    data = dict(fields, create='1', name=NAME, email='another@example.test',
                password1=PASSWORD, password2=PASSWORD)
    assert b'This user name already belongs' in client.post('/FrontPage', data=data).data
    data.update(name='NewLifecycleEditor', email=EMAIL.upper())
    assert b'This email already belongs' in client.post('/FrontPage', data=data).data

    other = create_account(context, 'OtherEditor', 'other@example.test')
    login(client, other.name)
    settings = '/FrontPage?action=userprefs&sub=prefs'
    form = client.get(settings)
    fields = next(fields for fields in Forms(form).forms if fields.get('handler') == 'prefs')
    response = client.post(settings, data=dict(fields, save='1', name=NAME))
    assert b'This user name already belongs' in response.data
    response = client.post(settings, data=dict(fields, save='1', name=other.name, email=EMAIL))
    assert b'This email already belongs' in response.data
    assert user.User(context, other.id).email == 'other@example.test'


def test_legacy_identity_conflict_preserves_both_profiles(wiki):
    context, _ = wiki
    legacy = create_account(context, NAME, EMAIL)
    legacy.disabled = 1
    legacy.name += '-' + legacy.id
    legacy.email += '-' + legacy.id
    legacy.save()
    assert user.getUserId(context, NAME, include_disabled=True) == legacy.id
    other = create_account(context, NAME, 'other@example.test')
    with pytest.raises(user.AccountIdentityConflict, match='username'):
        legacy.enable()
    assert legacy.disabled and legacy.name.endswith('-' + legacy.id)
    assert other.delete()
    assert legacy.enable()
    assert not legacy.enable()
    assert (legacy.name, legacy.email) == (NAME, EMAIL)


def test_cli_round_trip_and_reserved_identity(wiki, tmp_path):
    context, _ = wiki
    profile = create_account(context, NAME, EMAIL)

    def run(operation, *options):
        return subprocess.run(
            [sys.executable, '-m', 'MoinMoin.script.moin', f'--config-dir={tmp_path}',
             'account', operation, *options], capture_output=True, text=True,
        )

    assert 'disabled.' in run('disable', '--name', NAME).stdout
    assert 'already disabled.' in run('disable', '--uid', profile.id).stdout
    assert 'exists already' in run('create', '--name', NAME, '--email', 'new@example.test').stdout
    assert 'belongs to someone else' in run('create', '--name', 'NewEditor', '--email', EMAIL).stdout
    assert 'enabled.' in run('enable', '--name', NAME).stdout
    assert user.User(context, profile.id).valid
    assert 'deleted.' in run('delete', '--uid', profile.id).stdout
    assert not user.User(context, profile.id).exists()
    result = run('delete', '--uid', profile.id)
    assert result.returncode != 0 and 'account not found' in result.stderr


def test_stale_profile_update_cannot_undo_account_lifecycle(wiki):
    context, _ = wiki
    account = create_account(context, NAME, EMAIL)
    stale = user.User(context, account.id)
    assert account.disable()
    stale.aliasname = 'Concurrent change'
    assert stale.save()
    assert user.User(context, account.id).disabled

    assert account.delete()
    assert not stale.save()
    assert not user.User(context, account.id).exists()
