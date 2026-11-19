"""
MoinMoin HTTP facade compatibility tests.

@license: GNU GPL, see COPYING for details.
"""

import ast
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from MoinMoin.config.multiconfig import DefaultConfig
from MoinMoin.web.exceptions import SurgeProtection
from MoinMoin.web.http import (
    Client,
    MultiDict,
    PathInfoFromRequestUriFix,
    Response,
    create_environ,
    exceptions,
    url_decode,
    url_encode,
    url_quote,
    url_unquote,
)
from MoinMoin.web.request import Href, Request, TestRequest as MoinTestRequest
from MoinMoin.web.static import make_static_serving_app
from MoinMoin.wsgiapp import Application


def test_url_helpers_preserve_legacy_query_semantics():
    values = MultiDict([
        ('name', 'Jürgen'),
        ('tag', 'one'),
        ('tag', 'two'),
        ('ignored', None),
    ])

    encoded = url_encode(values)

    assert encoded == 'name=J%C3%BCrgen&tag=one&tag=two'
    assert url_decode(encoded).getlist('tag') == ['one', 'two']
    assert url_decode('flag&empty=', include_empty=False) == MultiDict([
        ('empty', ''),
    ])
    assert url_unquote(url_quote('Ärger')) == 'Ärger'
    assert url_quote('http://example.org/a?b=1') == (
        'http://example.org/a%3Fb%3D1')


def test_href_uses_internal_url_helpers():
    href = Href('/wiki', sort=True)

    assert href('Ärger', tag=['one', 'two']) == (
        '/wiki/%C3%84rger?tag=one&tag=two')
    assert href('OtherWiki:Page') == '/wiki/OtherWiki:Page'


def test_test_request_builds_binary_form_body():
    request = MoinTestRequest(
        method='POST',
        form_data=MultiDict([('name', 'Jürgen'), ('tag', 'one')]),
    )

    assert request.form['name'] == 'Jürgen'
    assert request.form.getlist('tag') == ['one']


def test_request_defaults_to_ten_megabyte_form_memory_limit():
    request = MoinTestRequest()

    assert DefaultConfig.form_max_memory_size == 10 * 1024 * 1024
    assert request.max_form_memory_size == 10 * 1024 * 1024


def test_request_accepts_forms_larger_than_werkzeug_legacy_default():
    value = 'x' * 501_000
    request = MoinTestRequest(method='POST', form_data={'text': value})

    assert request.form['text'] == value


def test_request_uses_loaded_wiki_form_memory_limit():
    request = MoinTestRequest(method='POST', form_data={'text': 'x' * 2_000})
    request.environ['moin.cfg'] = SimpleNamespace(form_max_memory_size=1_000)

    with pytest.raises(exceptions.RequestEntityTooLarge):
        request.form


@pytest.mark.parametrize('value_size', [995, 996])
def test_request_limits_streamed_urlencoded_form(value_size):
    value = b'x' * value_size
    environ = create_environ(method='POST', data=b'text=' + value,
                             content_type='application/x-www-form-urlencoded')
    del environ['CONTENT_LENGTH']
    environ['wsgi.input_terminated'] = True
    environ['moin.cfg'] = SimpleNamespace(form_max_memory_size=1_000)
    request = Request(environ)

    if value_size == 995:
        assert request.form['text'] == value.decode('ascii')
    else:
        with pytest.raises(exceptions.RequestEntityTooLarge):
            request.form


def test_application_rejects_urlencoded_form_above_wiki_limit(req, monkeypatch):
    monkeypatch.setattr(req.cfg, 'form_max_memory_size', 1_000)
    client = Client(Application(lambda name: req.cfg), Response)

    response = client.post('/', data={'text': 'x' * 2_000})

    assert response.status_code == 413


def test_request_allows_multipart_file_above_form_memory_limit():
    data = b'x' * 110_000
    environ = create_environ(method='POST', data={'file': (BytesIO(data), 'test.txt')})
    environ['moin.cfg'] = SimpleNamespace(form_max_memory_size=100_000)

    with Request(environ) as request:
        assert request.files['file'].read() == data


def test_request_parses_basic_authorization():
    credentials = b64encode('Jürgen:päss'.encode('utf-8')).decode('ascii')
    request = MoinTestRequest(environ_overrides={
        'HTTP_AUTHORIZATION': 'Basic ' + credentials,
    })

    assert request.authorization.username == 'Jürgen'
    assert request.authorization.password == 'päss'


def test_surge_protection_sets_retry_after():
    exception = SurgeProtection(retry_after=17)
    client = Client(exception, Response)

    response = client.get('/')

    assert response.status_code == 503
    assert response.headers['Retry-After'] == '17'


def test_static_middleware_serves_configured_file(tmp_path):
    static_file = tmp_path / 'hello.txt'
    static_file.write_text('Hello', encoding='utf-8')

    def fallback(environ, start_response):
        return Response('fallback', status=404)(environ, start_response)

    application = make_static_serving_app(
        fallback, {'/assets': str(tmp_path)})
    client = Client(application, Response)

    response = client.get('/assets/hello.txt')

    assert response.status_code == 200
    assert response.get_data(as_text=True) == 'Hello'


def test_path_info_fixer_recovers_raw_utf8_path():
    captured = {}

    def application(environ, start_response):
        captured.update(environ)
        start_response('204 No Content', [])
        return []

    middleware = PathInfoFromRequestUriFix(application)
    environ = MoinTestRequest().environ
    environ['SCRIPT_NAME'] = '/moin'
    environ['REQUEST_URI'] = '/moin/wiki/%C3%84rger?do=show'

    list(middleware(environ, lambda status, headers: None))

    assert captured['PATH_INFO'].encode('latin-1').decode('utf-8') == (
        '/wiki/Ärger')


def test_werkzeug_imports_are_isolated_to_http_facade():
    package_root = Path(__file__).resolve().parents[3] / 'MoinMoin'
    facade = package_root / 'web' / 'http.py'
    offenders = []

    for source_path in package_root.rglob('*.py'):
        if source_path == facade:
            continue
        tree = ast.parse(source_path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or '']
            else:
                continue
            if any(name == 'werkzeug' or name.startswith('werkzeug.')
                   for name in names):
                offenders.append(str(source_path.relative_to(package_root)))

    assert offenders == []
