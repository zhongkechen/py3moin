"""Exercise page saves, actions, and exports through the WSGI application."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import tarfile
from threading import Barrier, Event
from xml.etree import ElementTree

import pytest

from MoinMoin import PageEditor as page_editor_module, user
from MoinMoin.Page import Page
from MoinMoin.PageEditor import PageEditor
from MoinMoin.action import cache
from MoinMoin.events import PagePreSaveEvent
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.http import Client
from MoinMoin.web.request import TestRequest as WikiTestRequest
from MoinMoin.wsgiapp import Application
from tests._tests import maketestwiki, wikiconfig


CONFIG_NAME = 'MoinMoin._tests.wikiconfig'


def _context(cfg):
    request = WikiTestRequest()
    request.given_config = lambda _: cfg
    return AllContext(request)


def _client(cfg):
    return Client(Application(lambda _: cfg))


@pytest.fixture
def wiki(tmp_path):
    data_path = tmp_path / 'data'
    shutil.copytree(Path(maketestwiki.SHARE) / 'data', data_path)

    class Config(wikiconfig.Config):
        data_dir = str(data_path)
        data_underlay_dir = None
        language_default = 'en'
        acl_rights_default = 'All:read,write,delete,revert,admin'
        surge_action_limits = {}

    cfg = Config(CONFIG_NAME)
    cfg.cfg_mtime = 0
    return _context(cfg), _client(cfg)


def _field(response, name):
    match = re.search(fr'name="{name}" value="([^"]+)"'.encode('ascii'), response.data)
    assert match is not None, f'Missing {name} in the response form'
    return match[1].decode('ascii')


def test_concurrent_saves_from_the_same_revision(wiki, monkeypatch):
    context, first_client = wiki
    PageEditor(context, 'EditPage').saveText('Original page.\n', 0, notify=False)
    second_client = _client(context.cfg)
    ready = Barrier(2)
    send_event = page_editor_module.send_event

    def wait_for_both_saves(event):
        if isinstance(event, PagePreSaveEvent):
            ready.wait(timeout=10)
        return send_event(event)

    monkeypatch.setattr(page_editor_module, 'send_event', wait_for_both_saves)

    def submit(client, ip_address, body):
        environ = {'REMOTE_ADDR': ip_address}
        form = client.get('/EditPage', query_string={'action': 'edit', 'editor': 'text'},
                          environ_overrides=environ)
        return client.post('/EditPage', environ_overrides=environ, buffered=True, data={
            'action': 'edit', 'editor': 'text', 'ticket': _field(form, 'ticket'),
            'rev': _field(form, 'rev'), 'savetext': body, 'button_save': 'Save Changes',
        })

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(submit, first_client, '127.0.0.10', 'First edit.')
        second = executor.submit(submit, second_client, '127.0.0.20', 'Second edit.')
        responses = [first.result(timeout=15), second.result(timeout=15)]

    assert all(response.status_code == 200 for response in responses)
    assert sum(b'Thank you for your changes' in response.data for response in responses) == 1
    assert sum(b'Someone else saved this page while you were editing' in response.data
               for response in responses) == 1
    page = Page(_context(context.cfg), 'EditPage')
    assert page.getRevList() == [2, 1]
    assert page.get_raw_body() in ('First edit.\n', 'Second edit.\n')


def test_uncached_reader_can_read_during_a_save(wiki, monkeypatch):
    context, _ = wiki
    PageEditor(context, 'ReadPage').saveText('Previous revision.\n', 0, notify=False)
    editor = PageEditor(context, 'ReadPage')
    revision = editor.getPagePath('revisions', '00000002', check_create=False)
    staging = Event()
    resume = Event()
    replace = os.replace

    def pause_revision_write(source, destination):
        if destination == revision:
            staging.set()
            assert resume.wait(timeout=10)
        return replace(source, destination)

    cfg = type(context.cfg)(CONFIG_NAME)
    cfg.cfg_mtime = 0
    reader = _client(cfg)
    monkeypatch.setattr(page_editor_module.os, 'replace', pause_revision_write)

    with ThreadPoolExecutor(max_workers=1) as executor:
        save = executor.submit(editor.saveText, 'Updated revision.\n', 1, notify=False)
        try:
            assert staging.wait(timeout=10)
            during_save = reader.get('/ReadPage', buffered=True)
        finally:
            resume.set()
        save.result(timeout=15)

    assert during_save.status_code == 200
    assert b'Previous revision.' in during_save.data
    assert b'Updated revision.' in reader.get('/ReadPage').data


def test_revert_creates_a_revision_from_the_selected_history(wiki):
    context, client = wiki
    PageEditor(context, 'RevisionPage').saveText('Original text.\n', 0, notify=False)
    PageEditor(context, 'RevisionPage').saveText('Updated text.\n', 1, notify=False)

    form = client.get('/RevisionPage', query_string={'action': 'revert', 'rev': 1})
    response = client.post('/RevisionPage', data={
        'action': 'revert', 'rev': 1, 'revert': '1', 'ticket': _field(form, 'ticket'),
    })

    assert response.status_code == 200
    assert b'Original text.' in response.data
    page = Page(_context(context.cfg), 'RevisionPage')
    assert page.getRevList() == [3, 2, 1]
    assert page.get_raw_body() == 'Original text.\n'


def test_edits_and_reverts_keep_deprecated_history(wiki):
    context, client = wiki
    name = 'DeprecatedHistory'
    PageEditor(context, name).saveText('Original page.\n', 0, notify=False)
    PageEditor(context, name).saveText('#deprecated\n\nFirst note.\n', 1, notify=False)
    PageEditor(context, name).saveText('#deprecated\n\nSecond note.\n', 2, notify=False)

    rendered = client.get('/' + name)
    assert b'Second note.' in rendered.data
    assert b'Original page.' in rendered.data
    assert b'First note.' not in rendered.data
    historical = client.get('/' + name, query_string={'rev': 2})
    assert b'First note.' in historical.data
    assert b'Original page.' in historical.data

    form = client.get('/' + name, query_string={'action': 'revert', 'rev': 1})
    reverted = client.post('/' + name, data={
        'action': 'revert', 'rev': 1, 'revert': 1, 'ticket': _field(form, 'ticket'),
    })
    assert reverted.status_code == 200
    assert Page(context, name).getRevList() == [4, 3, 2, 1]
    assert Page(context, name, rev=3).get_raw_body() == '#deprecated\n\nSecond note.\n'
    assert Page(context, name, rev=2).get_raw_body() == '#deprecated\n\nFirst note.\n'
    assert Page(context, name).get_raw_body() == 'Original page.\n'


def test_delete_deprecated_page_keeps_its_history(wiki):
    context, client = wiki
    PageEditor(context, 'DeprecatedPage').saveText('Original content.\n', 0, notify=False)
    PageEditor(context, 'DeprecatedPage').saveText('#deprecated\n\nOld page.\n', 1, notify=False)

    form = client.get('/DeprecatedPage', query_string={'action': 'DeletePage'})
    result = client.post('/DeprecatedPage', data={
        'action': 'DeletePage', 'delete': '1', 'ticket': _field(form, 'ticket'),
    })

    assert b'was successfully deleted' in result.data
    assert client.get('/DeprecatedPage').status_code == 404
    page = Page(_context(context.cfg), 'DeprecatedPage')
    assert page.current_rev() == 3
    assert page.getRevList() == [2, 1]


def test_rename_and_delete_support_subpages(wiki):
    context, client = wiki
    PageEditor(context, 'ParentPage').saveText('Parent text.\n', 0, notify=False)
    PageEditor(context, 'ParentPage/Child').saveText('Child text.\n', 0, notify=False)

    form = client.get('/ParentPage', query_string={'action': 'RenamePage', 'subpages_checked': 1})
    assert b'name="rename_subpages" value="1" checked' in form.data
    renamed = client.post('/ParentPage', data={
        'action': 'RenamePage', 'rename': '1', 'newpagename': 'RenamedPage',
        'rename_subpages': '1', 'ticket': _field(form, 'ticket'),
    })
    assert renamed.status_code == 301
    assert client.get('/ParentPage/Child').status_code == 404
    assert b'Child text.' in client.get('/RenamedPage/Child').data

    form = client.get('/RenamedPage', query_string={'action': 'DeletePage', 'subpages_checked': 1})
    assert b'name="delete_subpages" value="1" checked' in form.data
    deleted = client.post('/RenamedPage', data={
        'action': 'DeletePage', 'delete': '1', 'delete_subpages': '1', 'ticket': _field(form, 'ticket'),
    })
    assert b'was successfully deleted' in deleted.data
    assert client.get('/RenamedPage').status_code == 404
    assert client.get('/RenamedPage/Child').status_code == 404


def test_load_upload_as_page_content(wiki):
    _, client = wiki
    form = client.get('/LoadedPage', query_string={'action': 'Load'})
    ticket = _field(form, 'ticket')

    def upload(body):
        return client.post('/LoadedPage', data={
            'action': 'Load', 'Load': '1', 'ticket': ticket, 'rename': 'LoadedPage',
            'file': (BytesIO(body), 'page.txt'),
        })

    assert b'You cannot save empty pages' in upload(b'').data
    assert upload(b'Uploaded text.\n').status_code == 302
    assert b'Uploaded text.' in client.get('/LoadedPage').data


def test_backup_form_and_archive_require_a_configured_user(wiki, tmp_path):
    context, client = wiki
    backup_dir = tmp_path / 'backup-source'
    backup_dir.mkdir()
    (backup_dir / 'notes.txt').write_bytes(b'Backup contents.\n')
    context.cfg.backup_include = [str(backup_dir)]
    context.cfg.backup_users = ['BackupReader']

    denied = client.post('/BackupPage', data={'action': 'backup', 'do': 'backup'})
    assert b'You are not allowed to do remote backup' in denied.data

    account = user.User(context, auth_method='new-user')
    account.name = 'BackupReader'
    account.email = 'backup@example.invalid'
    account.enc_password = user.encodePassword(context.cfg, 'backup-test-password')
    account.save()
    login = client.post('/BackupPage', data={
        'action': 'login', 'login': '1', 'name': account.name, 'password': 'backup-test-password',
    })
    assert login.headers.get('Set-Cookie')

    form = client.get('/BackupPage', query_string={'action': 'backup'},
                      environ_overrides={'SCRIPT_NAME': '/wiki'})
    assert b'action="/wiki/BackupPage"' in form.data

    response = client.post('/BackupPage', data={'action': 'backup', 'do': 'backup'})
    assert response.status_code == 200
    assert response.mimetype == 'application/octet-stream'
    assert '.tar.gz' in response.headers['Content-Disposition']
    with tarfile.open(fileobj=BytesIO(response.data), mode='r:gz') as archive:
        names = archive.getnames()
        assert [Path(name).name for name in names] == ['notes.txt']
        assert archive.extractfile(names[0]).read() == b'Backup contents.\n'


def test_wiki_indexes_return_the_requested_formats(wiki):
    context, client = wiki
    PageEditor(context, 'IndexPage').saveText('[[SecondPage]]\n', 0, notify=False)
    PageEditor(context, 'SecondPage').saveText('Other page.\n', 0, notify=False)

    sitemap = client.get('/', query_string={'action': 'sitemap', 'underlay': '0'},
                         environ_overrides={'SCRIPT_NAME': '/wiki'})
    assert sitemap.mimetype == 'text/xml'
    root = ElementTree.fromstring(sitemap.data)
    assert 'http://localhost/wiki/IndexPage' in [loc.text for loc in root.findall('.//{*}loc')]

    xml_titles = client.get('/', query_string={'action': 'titleindex', 'mimetype': 'text/xml'})
    assert xml_titles.mimetype == 'text/xml'
    assert 'SecondPage' in [title.text for title in ElementTree.fromstring(xml_titles.data)]
    titles = client.get('/', query_string={'action': 'titleindex'})
    assert titles.mimetype == 'text/plain'
    assert b'IndexPage' in titles.data.splitlines()

    links = client.get('/', query_string={'action': 'links', 'mimetype': 'text/plain'})
    assert links.mimetype == 'text/plain'
    assert b'IndexPage SecondPage' in links.data.splitlines()
    html_links = client.get('/', query_string={'action': 'links'})
    assert html_links.mimetype == 'text/html'
    assert b'href="/SecondPage"' in html_links.data


def test_cache_download_sends_headers_body_and_conditional_status(wiki):
    context, client = wiki
    key = cache.key(context, content='Cache download fixture')
    cache.put(context, key, b'Cache contents.\n', filename='cached.txt', last_modified=1700000000)

    url = cache.url(context, key)
    response = client.get(url, buffered=True)
    assert response.status_code == 200
    assert response.data == b'Cache contents.\n'
    assert response.headers.getlist('Content-Type') == ['text/plain']

    headers = {'If-Modified-Since': response.headers['Last-Modified']}
    unchanged = client.get(url, headers=headers)
    assert unchanged.status_code == 304
    assert unchanged.data == b''

    assert client.get(cache.url(context, key, do='remove')).status_code == 404
    assert cache.exists(context, key, strict=True)
    cache.remove(context, key)
    assert client.get(url, headers=headers).status_code == 404


def test_page_language_controls_the_rendered_content_direction(wiki):
    context, client = wiki
    PageEditor(context, 'EnglishSection').saveText('Included text.\n', 0, notify=False)
    PageEditor(context, 'ArabicPage').saveText(
        '#language ar\n\nنص عربي\n\n<<Include(EnglishSection)>>\n', 0, notify=False,
    )

    response = client.get('/ArabicPage')

    assert response.status_code == 200
    assert b'<div dir="rtl" id="content" lang="ar">' in response.data
    assert b'<div dir="ltr" id="EnglishSection.content" lang="en">' in response.data
    assert b'Included text.' in response.data
