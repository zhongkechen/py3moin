"""
    Regression tests for Python 3 text and byte boundaries.

    @license: GNU GPL, see COPYING for details.
"""

import io
import http.client

import pytest

from MoinMoin.script.migration import _conv160, _conv160a, wikiutil160a
from MoinMoin.support.BasicAuthTransport import BasicAuthTransport
from MoinMoin.support.python_compatibility import hmac_new


def test_compatibility_hmac_accepts_text():
    assert hmac_new('key', 'message').hexdigest() == (
        '2088df74d5f2146b48146caf4965377e9d0be3a4'
    )


def test_basic_auth_header_is_ascii_base64(monkeypatch):
    class HTTP:
        def __init__(self):
            self.headers = {}

        def putrequest(self, method, handler):
            pass

        def putheader(self, name, value):
            self.headers[name] = value

        def endheaders(self):
            pass

        def getreply(self):
            return 200, 'OK', {}

        def getfile(self):
            return io.BytesIO()

    connection = HTTP()
    monkeypatch.setattr(http.client, 'HTTP', lambda host: connection, raising=False)
    transport = BasicAuthTransport('Jürgen', 'secret')
    monkeypatch.setattr(transport, 'parse_response', lambda stream: 'response')

    assert transport.request('example.test', '/RPC2', b'') == 'response'
    assert connection.headers['Authorization'] == 'Basic SsO8cmdlbjpzZWNyZXQ='


def test_migration_query_string_decodes_bytes():
    assert wikiutil160a.parseQueryString(b'name=J%C3%BCrgen') == {
        'name': 'Jürgen',
    }


@pytest.mark.parametrize('module', [_conv160, _conv160a])
def test_migration_event_log_writes_encoded_bytes(module, tmp_path):
    target = tmp_path / 'event-log'
    event_log = module.EventLog(None, str(target))
    event_log.data = [(1234567890, 'SAVE', {'pagename': 'Jürgen'})]

    event_log.write(str(target))

    assert target.read_bytes().startswith(b'1234567890\tSAVE\t')
