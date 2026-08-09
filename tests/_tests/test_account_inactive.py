"""
    MoinMoin - inactive account script tests

    @license: GNU GPL, see COPYING for details.
"""

from MoinMoin.script.account.inactive import _load_editlog_uids


def test_load_editlog_uids_executes_utf8_source(tmp_path):
    source = tmp_path / 'keep-users.py'
    source.write_text(
        "editlog_uids.add('123')\neditlog_uids.add('用户')\n",
        encoding='utf-8',
    )

    assert _load_editlog_uids(str(source)) == {'123', '用户'}
