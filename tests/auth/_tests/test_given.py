"""
    Tests for authentication values supplied by the web server.

    @license: GNU GPL, see COPYING for details.
"""

from MoinMoin.auth import GivenAuth


def test_given_auth_decodes_only_bytes():
    auth = GivenAuth(coding='utf-8')

    assert auth.decode_username('Jürgen') == 'Jürgen'
    assert auth.decode_username('Jürgen'.encode('utf-8')) == 'Jürgen'
