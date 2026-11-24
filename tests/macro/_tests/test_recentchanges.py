"""
MoinMoin - RecentChanges macro end-of-log flush regression tests (Issue #24).

@license: GNU GPL, see COPYING for details.
"""

from datetime import datetime, timezone

from MoinMoin import wikiutil
from MoinMoin.Page import Page
from MoinMoin.logfile import editlog
from MoinMoin.macro import Macro
from MoinMoin.macro import RecentChanges as recentchanges_macro
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.http import create_environ
from MoinMoin.web.request import Request
from tests._tests import become_trusted


def _utc_usecs(year, month, day, hour, minute=0, second=0):
    ts = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp()
    return wikiutil.timestamp2version(ts)


def _write_editlog(path, entries):
    lines = []
    for usecs, rev, action, pagename, comment in entries:
        lines.append(
            "\t".join(
                (
                    str(int(usecs)),
                    "%08d" % rev,
                    action,
                    wikiutil.quoteWikinameFS(pagename),
                    "127.0.0.1",
                    "localhost",
                    "",
                    "",
                    comment,
                )
            )
            + "\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


def _render_recentchanges(req, tmp_path, entries, query_string=None, bookmark_usecs=None, monkeypatch=None):
    editlog_path = tmp_path / "edit-log"
    _write_editlog(editlog_path, entries)

    environ = create_environ(path="/RecentChanges", method="GET", query_string=query_string)
    environ["REMOTE_ADDR"] = "127.0.0.1"
    wsgi_req = Request(environ, given_config=req.request.given_config)
    context = AllContext(wsgi_req)
    become_trusted(context)
    context.user.tz_offset = 0
    if bookmark_usecs is not None:
        context.user.valid = 1
        monkeypatch.setattr(context.user, "getBookmark", lambda: bookmark_usecs)
    else:
        context.user.valid = 0
        monkeypatch.setattr(context.user, "getBookmark", lambda: None)

    page = Page(context, "RecentChanges")
    context.page = page
    context.formatter.setPage(page)

    real_editlog = editlog.EditLog

    def isolated_editlog(ctx, filename=None, **kw):
        return real_editlog(ctx, filename=filename or str(editlog_path), **kw)

    monkeypatch.setattr(recentchanges_macro.editlog, "EditLog", isolated_editlog)

    macro = Macro(context.formatter)
    return recentchanges_macro.macro_RecentChanges(macro)


def test_recentchanges_empty_edit_log(req, tmp_path, monkeypatch):
    html = _render_recentchanges(req, tmp_path, [], monkeypatch=monkeypatch)
    assert '<div class="recentchanges"' in html
    assert "rcdaybreak" not in html
    assert "</div>" in html


def test_recentchanges_single_edit_flushes_at_end_of_log(req, tmp_path, monkeypatch):
    entries = [
        (_utc_usecs(2024, 2, 10, 12, 0), 1, "SAVENEW", "SingleEditPage", "initial commit"),
    ]
    html = _render_recentchanges(req, tmp_path, entries, monkeypatch=monkeypatch)
    assert "SingleEditPage" in html
    assert "initial commit" in html
    assert "rcdaybreak" in html
    assert html.rstrip().endswith("</div>")


def test_recentchanges_multiple_edits_single_day_sorted_newest_first(req, tmp_path, monkeypatch):
    entries = [
        (_utc_usecs(2024, 2, 10, 9, 0), 1, "SAVENEW", "AlphaPage", "first"),
        (_utc_usecs(2024, 2, 10, 10, 0), 1, "SAVENEW", "BetaPage", "second"),
        (_utc_usecs(2024, 2, 10, 11, 0), 2, "SAVE", "AlphaPage", "third"),
        (_utc_usecs(2024, 2, 10, 12, 0), 1, "SAVENEW", "GammaPage", "fourth"),
    ]
    html = _render_recentchanges(req, tmp_path, entries, monkeypatch=monkeypatch)
    pos_gamma = html.index("GammaPage")
    pos_alpha = html.index("AlphaPage")
    pos_beta = html.index("BetaPage")
    assert pos_gamma < pos_alpha < pos_beta
    assert html.rstrip().endswith("</div>")


def test_recentchanges_multiple_days_ending_before_day_limit(req, tmp_path, monkeypatch):
    entries = [
        # Day 1 (older day - flushed by the end-of-log else branch)
        (_utc_usecs(2024, 2, 9, 8, 0), 1, "SAVENEW", "OlderFirstPage", "day1 early"),
        (_utc_usecs(2024, 2, 9, 16, 0), 1, "SAVENEW", "OlderSecondPage", "day1 late"),
        # Day 2 (newer day - flushed on day transition)
        (_utc_usecs(2024, 2, 10, 9, 0), 1, "SAVENEW", "NewerPage", "day2 edit"),
    ]
    html = _render_recentchanges(req, tmp_path, entries, monkeypatch=monkeypatch)
    pos_newer = html.index("NewerPage")
    pos_older_second = html.index("OlderSecondPage")
    pos_older_first = html.index("OlderFirstPage")
    assert pos_newer < pos_older_second < pos_older_first
    assert html.count("rcdaybreak") == 2
    assert html.rstrip().endswith("</div>")


def test_recentchanges_day_limit_early_break(req, tmp_path, monkeypatch):
    entries = [
        (_utc_usecs(2024, 2, 9, 10, 0), 1, "SAVENEW", "OlderExcludedPage", "day1"),
        (_utc_usecs(2024, 2, 10, 10, 0), 1, "SAVENEW", "NewestIncludedPage", "day2"),
    ]
    html = _render_recentchanges(
        req,
        tmp_path,
        entries,
        query_string={"max_days": "1"},
        monkeypatch=monkeypatch,
    )
    assert "NewestIncludedPage" in html
    assert "OlderExcludedPage" not in html
    assert html.rstrip().endswith("</div>")


def test_recentchanges_bookmark_early_break(req, tmp_path, monkeypatch):
    entries = [
        (_utc_usecs(2024, 2, 9, 10, 0), 1, "SAVENEW", "BeforeBookmarkPage", "before"),
        (_utc_usecs(2024, 2, 10, 10, 0), 1, "SAVENEW", "AfterBookmarkPage", "after"),
    ]
    bookmark = _utc_usecs(2024, 2, 9, 12, 0)
    html = _render_recentchanges(
        req,
        tmp_path,
        entries,
        bookmark_usecs=bookmark,
        monkeypatch=monkeypatch,
    )
    assert "AfterBookmarkPage" in html
    assert "BeforeBookmarkPage" not in html
    assert "Bookmark reached" in html
    assert html.rstrip().endswith("</div>")
