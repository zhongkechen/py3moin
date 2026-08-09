"""
    MoinMoin - FCKeditor Python connector compatibility tests

    @license: GNU GPL, see COPYING for details.
"""

from io import BytesIO
import importlib
from pathlib import Path
import sys

import pytest
from werkzeug.test import EnvironBuilder


CONNECTOR_DIR = (
    Path(__file__).resolve().parents[2] /
    'MoinMoin' / 'web' / 'static' / 'htdocs' / 'applets' /
    'FCKeditor' / 'editor' / 'filemanager' / 'connectors' / 'py'
)
FCKEDITOR_FILE = CONNECTOR_DIR.parents[3] / 'fckeditor.py'
CONNECTOR_MODULES = [
    'config',
    'connector',
    'fckcommands',
    'fckconnector',
    'fckoutput',
    'fckutil',
    'upload',
    'wsgi',
]
MISSING = object()


@pytest.fixture
def connector_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(CONNECTOR_DIR))
    previous_modules = {
        name: sys.modules.get(name, MISSING)
        for name in CONNECTOR_MODULES
    }
    for name in CONNECTOR_MODULES:
        sys.modules.pop(name, None)
    try:
        request_module = importlib.import_module('fckconnector')
        wsgi_module = importlib.import_module('wsgi')
        output_module = importlib.import_module('fckoutput')
        yield request_module, wsgi_module, output_module
    finally:
        for name in CONNECTOR_MODULES:
            sys.modules.pop(name, None)
        for name, module in previous_modules.items():
            if module is not MISSING:
                sys.modules[name] = module


@pytest.fixture
def fckeditor_module():
    spec = importlib.util.spec_from_file_location(
        '_fckeditor_python3_test',
        FCKEDITOR_FILE,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_request_parses_query_form_and_upload(connector_modules):
    request_module, unused_wsgi_module, unused_output_module = connector_modules
    builder = EnvironBuilder(
        method='POST',
        query_string={'Type': 'File'},
        data={
            'Command': 'QuickUpload',
            'NewFile': (BytesIO(b'content'), 'example.txt'),
        },
    )
    try:
        request = request_module.FCKeditorRequest(builder.get_environ())

        assert request.get('Type') == 'File'
        assert request.get('Command') == 'QuickUpload'
        upload = request.get('NewFile')
        assert upload.filename == 'example.txt'
        assert upload.file.read() == b'content'
    finally:
        builder.close()


def test_wsgi_application_returns_bytes(connector_modules):
    unused_request_module, wsgi_module, unused_output_module = connector_modules
    environ = {
        'SCRIPT_NAME': '/unknown.py',
        'wsgi.input': BytesIO(),
    }
    response = {}

    def start_response(status, headers):
        response['status'] = status
        response['headers'] = headers

    body = b''.join(wsgi_module.App(environ, start_response))

    assert response['status'] == '200 Ok'
    assert body == b'Unknown page requested: /unknown.py'


def test_wsgi_exception_uses_traceback_module(
        connector_modules, monkeypatch):
    unused_request_module, wsgi_module, unused_output_module = connector_modules

    class BrokenConnector:
        def __init__(self, environ):
            self.headers = []

        def doResponse(self):
            raise RuntimeError('connector failed')

    monkeypatch.setattr(wsgi_module, 'FCKeditorConnector', BrokenConnector)
    environ = {
        'SCRIPT_NAME': '/connector.py',
        'wsgi.input': BytesIO(),
    }
    response = {}

    def start_response(status, headers):
        response['status'] = status
        response['headers'] = headers

    body = b''.join(wsgi_module.App(environ, start_response))

    assert response['status'] == '500 Internal Server Error'
    assert b'RuntimeError: connector failed' in body


def test_xml_attribute_escape_uses_string_methods(connector_modules):
    unused_request_module, unused_wsgi_module, output_module = connector_modules

    assert output_module.convertToXmlAttribute('<"a&b">') == (
        '&lt;&quot;a&amp;b&quot;&gt;'
    )


def test_fckeditor_integration_supports_webkit_and_renders_frame(
        fckeditor_module, monkeypatch):
    monkeypatch.setenv(
        'HTTP_USER_AGENT',
        'Mozilla/5.0 AppleWebKit/537.36 Safari/537.36',
    )
    editor = fckeditor_module.FCKeditor('wiki')
    editor.Value = '<content>'

    html = editor.CreateHtml()

    assert 'id="wiki___Frame"' in html
    assert 'id="wiki\\__Frame"' not in html
    assert '&lt;content&gt;' in html
