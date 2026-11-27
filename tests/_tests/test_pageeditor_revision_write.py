"""
MoinMoin - PageEditor atomic revision write regression tests (Issue #20).

@license: GNU GPL, see COPYING for details.
"""

import codecs
import errno
import os
from pathlib import Path
import shutil

import pytest

from MoinMoin import PageEditor as page_editor_mod
from MoinMoin.Page import Page
from MoinMoin.PageEditor import PageEditor
from MoinMoin.logfile.editlog import EditLog


def _init_page(req, pagename, initial_text="previous valid page\n"):
    pagedir = Page(req, pagename).getPagePath(use_underlay=0, check_create=0)
    if os.path.exists(pagedir):
        shutil.rmtree(pagedir)
    revdir = os.path.join(pagedir, "revisions")
    os.makedirs(revdir)
    with open(os.path.join(pagedir, "current"), "w", encoding="utf-8") as f:
        f.write("00000001\n")
    with open(os.path.join(revdir, "00000001"), "wb") as f:
        f.write(initial_text.encode("utf-8"))
    return pagedir, revdir


class _FailingStream:
    """Wrap a real file stream and fail during write(), optionally after a partial write."""

    def __init__(self, inner, partial_prefix=None):
        self._inner = inner
        self._partial_prefix = partial_prefix

    def write(self, data):
        if self._partial_prefix:
            self._inner.write(self._partial_prefix)
            self._inner.flush()
        raise OSError(errno.ENOSPC, "simulated disk full during revision write")

    def close(self):
        return self._inner.close()

    def __getattr__(self, name):
        return getattr(self._inner, name)


@pytest.fixture
def isolated_page(req):
    pagename = "AutoCreatedMoinMoinTemporaryAtomicWriteTestPage"
    pagedir, revdir = _init_page(req, pagename)
    try:
        yield pagename, pagedir, revdir
    finally:
        if os.path.exists(pagedir):
            shutil.rmtree(pagedir, ignore_errors=True)


def test_failed_revision_write_before_content_preserves_current(req, isolated_page, monkeypatch):
    pagename, pagedir, revdir = isolated_page
    real_codecs_open = codecs.open

    def failing_codecs_open(filename, mode="r", encoding=None, *args, **kwargs):
        stream = real_codecs_open(filename, mode, encoding, *args, **kwargs)
        if filename.startswith(revdir) and "w" in mode:
            return _FailingStream(stream)
        return stream

    monkeypatch.setattr(page_editor_mod.codecs, "open", failing_codecs_open)

    editor = PageEditor(req, pagename, do_revision_backup=True)
    with pytest.raises(OSError) as exc_info:
        editor._write_file("new content that should not publish\n")

    assert exc_info.value.errno == errno.ENOSPC
    with open(os.path.join(pagedir, "current"), encoding="utf-8") as f:
        assert f.read().strip() == "00000001"
    assert not os.path.exists(os.path.join(pagedir, "current-locked"))
    assert os.listdir(revdir) == ["00000001"]

    page = Page(req, pagename)
    assert page.current_rev() == 1
    assert page.get_raw_body() == "previous valid page\n"


def test_failed_revision_write_after_partial_write_preserves_current(req, isolated_page, monkeypatch):
    pagename, pagedir, revdir = isolated_page
    real_codecs_open = codecs.open

    def failing_codecs_open(filename, mode="r", encoding=None, *args, **kwargs):
        stream = real_codecs_open(filename, mode, encoding, *args, **kwargs)
        if filename.startswith(revdir) and "w" in mode:
            return _FailingStream(stream, partial_prefix="truncated")
        return stream

    monkeypatch.setattr(page_editor_mod.codecs, "open", failing_codecs_open)

    editor = PageEditor(req, pagename, do_revision_backup=True)
    with pytest.raises(OSError) as exc_info:
        editor._write_file("new content that fails midway\n")

    assert exc_info.value.errno == errno.ENOSPC
    with open(os.path.join(pagedir, "current"), encoding="utf-8") as f:
        assert f.read().strip() == "00000001"
    assert not os.path.exists(os.path.join(pagedir, "current-locked"))
    assert os.listdir(revdir) == ["00000001"]

    page = Page(req, pagename)
    assert page.current_rev() == 1
    assert page.get_raw_body() == "previous valid page\n"


def test_successful_revision_write_advances_current_once(req, isolated_page):
    pagename, pagedir, revdir = isolated_page

    editor = PageEditor(req, pagename, do_revision_backup=True)
    mtime_usecs, rev = editor._write_file("updated valid page\n")

    assert rev == 2
    assert mtime_usecs > 0
    with open(os.path.join(pagedir, "current"), encoding="utf-8") as f:
        assert f.read().strip() == "00000002"
    assert not os.path.exists(os.path.join(pagedir, "current-locked"))
    assert sorted(os.listdir(revdir)) == ["00000001", "00000002"]

    page = Page(req, pagename)
    assert page.current_rev() == 2
    assert page.get_raw_body() == "updated valid page\n"
    assert Page(req, pagename, rev=1).get_raw_body() == "previous valid page\n"


def test_failed_current_replacement_leaves_previous_revision_published(req, isolated_page, monkeypatch):
    pagename, pagedir, revdir = isolated_page
    current = Path(pagedir) / 'current'
    global_log = Path(req.rootpage.getPagePath('edit-log', isfile=1))
    previous_log = global_log.read_bytes() if global_log.exists() else b''
    replace = os.replace

    def fail_to_publish_pointer(source, destination):
        if Path(destination) == current:
            raise OSError(errno.ENOSPC, 'simulated pointer publication failure')
        return replace(source, destination)

    editor = PageEditor(req, pagename)
    with monkeypatch.context() as patch:
        patch.setattr(page_editor_mod.os, 'replace', fail_to_publish_pointer)
        with pytest.raises(PageEditor.SaveError, match='no storage space left'):
            editor._write_file('Revision which could not be published.\n')

    assert current.read_text() == '00000001\n'
    assert os.listdir(revdir) == ['00000001']
    assert not (Path(pagedir) / 'current.tmp').exists()
    assert (Path(pagedir) / 'edit-log').read_bytes() == b''
    assert global_log.read_bytes() == previous_log
    assert Page(req, pagename).get_raw_body() == 'previous valid page\n'

    _, revision = editor._write_file('Retry after publication failure.\n')
    assert revision == 2
    assert current.read_text() == '00000002\n'


def test_failed_in_place_write_preserves_existing_revision_and_allows_recovery(req, isolated_page, monkeypatch):
    pagename, pagedir, revdir = isolated_page
    real_codecs_open = codecs.open

    def failing_codecs_open(filename, mode="r", encoding=None, *args, **kwargs):
        stream = real_codecs_open(filename, mode, encoding, *args, **kwargs)
        if filename.startswith(revdir) and "w" in mode:
            return _FailingStream(stream, partial_prefix="corrupt")
        return stream

    monkeypatch.setattr(page_editor_mod.codecs, "open", failing_codecs_open)

    editor = PageEditor(req, pagename, do_revision_backup=False)
    with pytest.raises(OSError) as exc_info:
        editor._write_file("replacement that fails\n")
    assert exc_info.value.errno == errno.ENOSPC
    assert Page(req, pagename).get_raw_body() == "previous valid page\n"
    assert os.listdir(revdir) == ["00000001"]

    # After restoring I/O, a subsequent backup save succeeds and advances cleanly to rev 2.
    monkeypatch.undo()
    editor_ok = PageEditor(req, pagename, do_revision_backup=True)
    _, rev = editor_ok._write_file("recovered save\n")
    assert rev == 2
    assert Page(req, pagename).current_rev() == 2
    assert Page(req, pagename).get_raw_body() == "recovered save\n"


@pytest.mark.parametrize('failure', ['local', 'global'])
def test_partial_edit_log_write_rolls_back_the_save(req, isolated_page, monkeypatch, failure):
    pagename, pagedir, revdir = isolated_page
    editor = PageEditor(req, pagename, do_revision_backup=True)
    editor._write_file('Last successful edit.\n')
    current = Path(pagedir) / 'current'
    local_log = Path(pagedir) / 'edit-log'
    global_log = Path(req.rootpage.getPagePath('edit-log', isfile=1))
    log_contents = {path: path.read_bytes() for path in (local_log, global_log)}
    failed_log = local_log if failure == 'local' else global_log
    append = EditLog._add

    def fail_append(log, line):
        if Path(log._path) == failed_log:
            with failed_log.open('ab') as stream:
                stream.write(b'incomplete edit record')
            raise OSError(errno.ENOSPC, 'simulated edit-log write failure')
        append(log, line)

    with monkeypatch.context() as patch:
        patch.setattr(EditLog, '_add', fail_append)
        with pytest.raises(PageEditor.SaveError, match='no storage space left'):
            editor._write_file('This edit could not be logged.\n')

    assert current.read_text() == '00000002\n'
    assert sorted(os.listdir(revdir)) == ['00000001', '00000002']
    assert Page(req, pagename).get_raw_body() == 'Last successful edit.\n'
    assert all(path.read_bytes() == previous for path, previous in log_contents.items())

    _, revision = editor._write_file('Successful retry.\n')
    assert revision == 3
    assert Page(req, pagename).get_raw_body() == 'Successful retry.\n'
    for path, previous in log_contents.items():
        records = path.read_bytes()
        assert records.startswith(previous)
        assert records[len(previous):].count(b'\n') == 1
        assert b'\t00000003\tSAVE\t' in records[len(previous):]

