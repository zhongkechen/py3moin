"""
MoinMoin server-side session tests.

@license: GNU GPL, see COPYING for details.
"""

import pickle

import pytest

from MoinMoin.web.session import FilesystemSessionStore, MoinSession


def test_session_tracks_direct_changes():
    session = MoinSession({'name': 'Alice'}, 'a' * 40)

    assert not session.should_save

    session['name'] = 'Bob'

    assert session.should_save


def test_filesystem_store_reads_existing_pickle_format(tmp_path):
    sid = 'a' * 40
    session_file = tmp_path / sid
    session_file.write_bytes(
        pickle.dumps({'user.id': '42'}, pickle.HIGHEST_PROTOCOL))
    store = FilesystemSessionStore(
        path=str(tmp_path), filename_template='%s', mode=0o600)

    session = store.get(sid)

    assert session == {'user.id': '42'}
    assert session.sid == sid
    assert not session.new
    assert not session.modified


def test_filesystem_store_roundtrip_and_list(tmp_path):
    store = FilesystemSessionStore(
        path=str(tmp_path), filename_template='%s', mode=0o600)
    session = store.new()
    session['trail'] = ['FrontPage']

    store.save(session)

    restored = store.get(session.sid)
    assert restored == {'trail': ['FrontPage']}
    assert session.sid in store.list()
    assert (tmp_path / session.sid).stat().st_mode & 0o777 == 0o600

    store.delete(restored)
    assert not (tmp_path / session.sid).exists()


def test_invalid_session_id_gets_replaced(tmp_path):
    store = FilesystemSessionStore(
        path=str(tmp_path), filename_template='%s')

    session = store.get('../not-a-session')

    assert session.new
    assert session.sid != '../not-a-session'
    assert store.is_valid_key(session.sid)


def test_invalid_session_id_cannot_be_saved(tmp_path):
    store = FilesystemSessionStore(
        path=str(tmp_path), filename_template='%s')
    session = MoinSession({}, '../not-a-session')

    with pytest.raises(ValueError):
        store.save(session)
