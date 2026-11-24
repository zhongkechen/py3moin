"""Exercise the wiki through its WSGI request and response interfaces.

@copyright: 2008 MoinMoin:FlorianKrupicka
@license: GNU GPL, see COPYING for details.
"""

from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import re
import shutil
import tarfile
import zipfile

import pytest

from MoinMoin.mail import sendmail
from MoinMoin.packages import MOIN_PACKAGE_FILE
from MoinMoin.web.http import Client
from MoinMoin.wsgiapp import Application
from tests._tests import wikiconfig


DOC_TYPE = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">'
WIKI_FILES = Path(__file__).resolve().parents[2] / 'wiki'
USERNAME = 'WorkflowEditor'
PASSWORD = 'First-Workflow-Password1!'
LOGOUT = '/FrontPage?action=logout&logout=logout'


@pytest.fixture(scope='module')
def wiki_files(tmp_path_factory):
    templates = tmp_path_factory.mktemp('wiki-files')
    with tarfile.open(WIKI_FILES / 'underlay.tar') as archive:
        archive.extractall(templates, filter='data')
    return templates


@pytest.fixture
def wiki_config(tmp_path, wiki_files):
    shutil.copytree(WIKI_FILES / 'data', tmp_path / 'data')
    shutil.copytree(wiki_files / 'underlay', tmp_path / 'underlay')

    class Config(wikiconfig.Config):
        data_dir = str(tmp_path / 'data')
        data_underlay_dir = str(tmp_path / 'underlay')
        superuser = [USERNAME]
        actions_superuser = [action for action in wikiconfig.Config.actions_superuser
                             if action != 'newaccount']
        acl_rights_before = f'{USERNAME}:read,write,delete,revert,admin'
        acl_rights_default = 'All:read'
        search_results_per_page = 1
        surge_action_limits = {}
        mail_from = 'wiki@example.test'
        mail_smarthost = 'mail.example.test'

    return Config


@pytest.fixture
def client(wiki_config):
    return Client(Application(wiki_config))


class FormInputs(HTMLParser):
    def __init__(self, response):
        assert response.status_code == 200
        super().__init__()
        self.values = {}
        self.feed(response.get_data(as_text=True))
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            field = dict(attrs)
            if 'name' in field and 'value' in field:
                self.values[field['name']] = field['value']


def ticket(response):
    return FormInputs(response).values['ticket']


def register(client):
    form = client.get('/FrontPage?action=newaccount')
    data = {
        'action': 'newaccount', 'ticket': ticket(form), 'name': USERNAME, 'create': '1',
        'password1': PASSWORD, 'password2': PASSWORD, 'email': 'editor@example.test',
    }
    return client.post('/FrontPage', data=data)


def login(client, password=PASSWORD):
    return client.post('/FrontPage', data={
        'action': 'login', 'login': 'Login', 'name': USERNAME, 'password': password,
    })


@pytest.fixture
def editor(client):
    assert 'User account created!' in register(client).get_data(as_text=True)
    response = login(client)
    assert response.status_code == 200
    assert 'Set-Cookie' in response.headers
    return client


def edit(client, page, body, button='button_save', **changes):
    form = client.get(f'/{page}?action=edit&editor=text')
    fields = FormInputs(form).values
    data = {'action': 'edit', 'editor': 'text', 'ticket': fields['ticket'],
            'savetext': body, button: '1'}
    if 'rev' in fields:
        data['rev'] = fields['rev']
    data.update(changes)
    response = client.post(f'/{page}', data=data)
    assert response.status_code in {200, 302, 303}
    return response


@pytest.mark.parametrize('page', ['FrontPage', 'RecentChanges', 'HelpContents', 'FindPage'])
def test_existing_pages(client, page):
    response = client.get(f'/{page}')
    assert response.status_code == 200
    assert response.content_type == 'text/html; charset=utf-8'
    html = response.get_data(as_text=True)
    assert DOC_TYPE in html
    assert page in html


@pytest.mark.parametrize('page', ['FooBar', 'TheNone/ExistantPage/', '%33Strange%74Codes'])
def test_missing_pages(editor, page):
    response = editor.get(f'/{page}')
    assert response.status_code == 404
    html = response.get_data(as_text=True)
    assert 'new empty page' in html
    assert 'page template' in html


def test_registration_password_change_recovery_and_logout(editor, wiki_config, monkeypatch):
    assert len(list(Path(wiki_config.data_dir, 'user').glob('[0-9]*'))) == 1
    settings = '/FrontPage?action=userprefs&sub=changepass'
    form = editor.get(settings)
    assert 'name="password1"' in form.get_data(as_text=True)
    changed_password = 'Second-Workflow-Password2!'
    response = editor.post(settings, data={
        'handler': 'changepass', 'ticket': ticket(form), 'save': '1',
        'password1': changed_password, 'password2': changed_password,
    })
    assert 'Your password has been changed.' in response.get_data(as_text=True)

    response = editor.get(LOGOUT)
    assert 'You are now logged out.' in response.get_data(as_text=True)
    assert 'You must login' in editor.get(settings).get_data(as_text=True)
    assert 'Invalid username or password.' in login(editor).get_data(as_text=True)
    assert 'Set-Cookie' in login(editor, changed_password).headers
    editor.get(LOGOUT)

    messages = []

    def fake_sendmail(context, to, subject, text, mail_from=None):
        messages.append((to, text))
        return True, 'Mail sent OK'

    monkeypatch.setattr(sendmail, 'sendmail', fake_sendmail)
    recovery = '/FrontPage?action=recoverpass'
    editor.get(recovery + '&account_sendmail=1&email=editor@example.test')
    assert messages == []
    editor.post(recovery, data={'account_sendmail': '1', 'email': 'editor@example.test'})
    [(recipients, message)] = messages
    assert recipients == ['editor@example.test']
    reset_url = re.search(r'http://\S+action=recoverpass&name=WorkflowEditor&token=[0-9a-f-]+', message)
    assert reset_url is not None
    fields = FormInputs(editor.get(reset_url.group())).values
    assert fields['name'] == USERNAME
    assert re.fullmatch(r'[0-9a-f-]+', fields['token'])
    reset_password = 'Third-Workflow-Password3!'
    response = editor.post(recovery, data={
        'name': USERNAME, 'token': fields['token'],
        'password': reset_password, 'password_repeat': reset_password,
    })
    assert response.status_code == 200
    assert 'Invalid username or password.' in login(editor, changed_password).get_data(as_text=True)
    assert 'Set-Cookie' in login(editor, reset_password).headers


def test_edit_preview_revisions_redirect_and_persistence(editor, wiki_config):
    path = '/WorkflowPage'
    page_dir = Path(wiki_config.data_dir, 'pages', 'WorkflowPage')
    first_body = '= Workflow heading =\n<<TableOfContents>>\nFirst workflow revision.\n'
    preview = edit(editor, 'WorkflowPage', first_body, 'button_preview').get_data(as_text=True)
    assert '<h1' in preview and 'Workflow heading' in preview
    assert 'class="table-of-contents"' in preview
    assert not (page_dir / 'current').exists()

    edit(editor, 'WorkflowPage', first_body, ticket='invalid')
    assert not (page_dir / 'current').exists()
    edit(editor, 'WorkflowPage', first_body)
    edit(editor, 'WorkflowPage', 'Second workflow revision.\n')
    assert (page_dir / 'current').read_text().strip() == '00000002'
    assert (page_dir / 'revisions' / '00000001').read_text() == first_body

    edit(editor, 'WorkflowRedirect', '#redirect WorkflowPage\n')
    restarted = Client(Application(wiki_config))
    assert 'Second workflow revision.' in restarted.get(path).get_data(as_text=True)
    assert 'First workflow revision.' in restarted.get(path + '?action=recall&rev=1').get_data(as_text=True)
    response = restarted.get('/WorkflowRedirect')
    assert response.status_code == 302
    assert 'Second workflow revision.' in restarted.get(response.headers['Location']).get_data(as_text=True)


def test_attachments_acl_and_package_export(editor, wiki_config):
    edit(editor, 'WorkflowPublic', 'Public workflow body.\n')
    edit(editor, 'WorkflowPrivate', '#acl WorkflowEditor:read,write All:\nPrivate workflow body.\n')
    path = '/WorkflowPublic'
    attachments = path + '?action=AttachFile'
    upload_ticket = ticket(editor.get(attachments))
    payload = b'Workflow attachment content.\n'
    response = editor.post(attachments, data={
        'do': 'upload', 'ticket': upload_ticket, 'file': (BytesIO(payload), 'workflow.txt'),
    })
    assert 'workflow.txt' in response.get_data(as_text=True)

    anonymous = Client(Application(wiki_config))
    download = anonymous.get(attachments + '&do=get&target=workflow.txt')
    assert download.status_code == 200
    assert download.data == payload
    assert 'filename="workflow.txt"' in download.headers['Content-Disposition']
    preview = anonymous.get(attachments + '&do=view&target=workflow.txt')
    assert preview.status_code == 200
    assert payload.strip() in preview.data

    rejected = anonymous.post(attachments, data={
        'do': 'upload', 'ticket': 'invalid',
        'file': (BytesIO(b'rejected'), 'rejected.txt'),
    })
    assert 'Please use the interactive user interface' in rejected.get_data(as_text=True)
    assert not Path(wiki_config.data_dir, 'pages', 'WorkflowPublic', 'attachments', 'rejected.txt').exists()
    private = anonymous.get('/WorkflowPrivate')
    assert 'Private workflow body.' not in private.get_data(as_text=True)
    assert 'You are not allowed to view this page.' in private.get_data(as_text=True)

    response = anonymous.post(path, data={
        'action': 'PackagePages', 'pagelist': 'WorkflowPublic,WorkflowPrivate',
        'packagename': 'workflow.zip', 'include_attachments': '1', 'submit': '1',
    })
    assert response.status_code == 200
    assert response.mimetype == 'application/zip'
    with zipfile.ZipFile(BytesIO(response.data)) as archive:
        assert set(archive.namelist()) == {MOIN_PACKAGE_FILE, '1', '2_attachment'}
        assert archive.read('1') == b'Public workflow body.\n'
        assert archive.read('2_attachment') == payload
        assert b'WorkflowPrivate' not in archive.read(MOIN_PACKAGE_FILE)


def test_search_pagination(editor, wiki_config):
    edit(editor, 'WorkflowMatchFirst', 'Page one.\n')
    edit(editor, 'WorkflowMatchSecond', 'Page two.\n')
    client = Client(Application(wiki_config))
    response = client.get('/FrontPage?action=fullsearch&titlesearch=1&value=WorkflowMatch')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'href="/WorkflowMatchFirst' in html
    assert 'href="/WorkflowMatchSecond' not in html
    next_page = re.search(r'href="([^"]*(?:\?|&amp;)from=1[^"]*)"', html)
    assert next_page is not None
    response = client.get(unescape(next_page.group(1)))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'href="/WorkflowMatchFirst' not in html
    assert 'href="/WorkflowMatchSecond' in html
