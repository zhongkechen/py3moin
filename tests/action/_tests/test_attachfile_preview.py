"""
MoinMoin - Source attachment preview regression tests (Issue #25).

@license: GNU GPL, see COPYING for details.
"""

import pytest

from MoinMoin import config, wikiutil
from MoinMoin.Page import Page
from MoinMoin.action import AttachFile
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.http import create_environ
from MoinMoin.web.request import Request
from tests._tests import become_trusted, create_page, nuke_page


def _make_view_context(req, pagename, filename):
    environ = create_environ(
        path="/" + pagename,
        query_string={"action": "AttachFile", "do": "view", "target": filename},
        method="GET",
    )
    environ["REMOTE_ADDR"] = "127.0.0.1"
    wsgi_req = Request(environ, given_config=req.request.given_config)
    context = AllContext(wsgi_req)
    become_trusted(context)
    context.page = Page(context, pagename)
    context.formatter.setPage(context.page)
    return context


def _response_text(response):
    return b"".join(
        chunk.encode("utf-8") if isinstance(chunk, str) else chunk
        for chunk in response.response
    ).decode("utf-8", "replace")


@pytest.mark.parametrize(
    ("case_id", "raw_bytes", "expected_tokens"),
    [
        ("utf8-lf", "# 中文注释\nprint(1)\nreturn 42\n".encode("utf-8"), ["中文注释", "print", "42"]),
        ("utf8-crlf", "# line1\r\nprint(2)\r\nreturn 99\r\n".encode("utf-8"), ["line1", "print", "99"]),
        ("utf8-cr", "# mac_line1\rprint(3)\rreturn 77\r".encode("utf-8"), ["mac_line1", "print", "77"]),
        ("iso-8859-1", b"# caf\xe9\r\nprint(4)\r\n", ["café", "print", "4"]),
    ],
)
def test_attachfile_source_preview_with_real_python_parser(req, case_id, raw_bytes, expected_tokens):
    pagename = "AutoCreatedAttachPreviewPyTestPage"
    filename = f"demo_{case_id.replace('-', '_')}.py"

    assert wikiutil.getParserForExtension(req.cfg, ".py") is not None

    become_trusted(req)
    create_page(req, pagename, "Preview test page\n")
    try:
        AttachFile.add_attachment(req, pagename, filename, raw_bytes, overwrite=True)

        context = _make_view_context(req, pagename, filename)
        AttachFile._do_view(pagename, context)

        assert context.response.status_code == 200
        html = _response_text(context.response)
        for token in expected_tokens:
            assert token in html
        # Universal newline normalization must prevent raw CR characters from leaking.
        assert "\r" not in html
    finally:
        nuke_page(req, pagename)


def test_attachfile_source_preview_uses_configured_charset_fallback(req, monkeypatch):
    pagename = "AutoCreatedAttachPreviewCharsetTestPage"
    filename = "gbk_sample.py"
    raw_bytes = "# 汉字测试\r\nprint(5)\r\n".encode("gbk")

    become_trusted(req)
    create_page(req, pagename, "Charset fallback test page\n")
    try:
        AttachFile.add_attachment(req, pagename, filename, raw_bytes, overwrite=True)
        monkeypatch.setattr(config, "charset", "gbk")

        context = _make_view_context(req, pagename, filename)
        AttachFile.send_viewfile(pagename, context)

        html = _response_text(context.response)
        assert "汉字测试" in html
        assert "print" in html
        assert "\r" not in html
    finally:
        nuke_page(req, pagename)


def test_attachfile_csv_preview_normalizes_cr_line_endings(req):
    pagename = "AutoCreatedAttachPreviewCsvTestPage"
    filename = "mac_export.csv"
    raw_bytes = b"col1;col2\ralpha;beta\rgamma;delta\r"

    assert wikiutil.getParserForExtension(req.cfg, ".csv") is not None

    become_trusted(req)
    create_page(req, pagename, "CSV preview test page\n")
    try:
        AttachFile.add_attachment(req, pagename, filename, raw_bytes, overwrite=True)

        context = _make_view_context(req, pagename, filename)
        AttachFile.send_viewfile(pagename, context)

        html = _response_text(context.response)
        assert "col1" in html
        assert "alpha" in html
        assert "delta" in html
        assert "\r" not in html
    finally:
        nuke_page(req, pagename)


def test_attachfile_plain_text_fallback_decodes_latin1_and_normalizes_newlines(req):
    pagename = "AutoCreatedAttachPreviewPlainTestPage"
    filename = "notes.txt"
    raw_bytes = b"Gr\xfc\xdfe\rsecond line\r\nthird line\n"

    become_trusted(req)
    create_page(req, pagename, "Plain text preview test page\n")
    try:
        AttachFile.add_attachment(req, pagename, filename, raw_bytes, overwrite=True)

        context = _make_view_context(req, pagename, filename)
        AttachFile.send_viewfile(pagename, context)

        html = _response_text(context.response)
        assert "Grüße" in html
        assert "second line" in html
        assert "third line" in html
        assert "\r" not in html
    finally:
        nuke_page(req, pagename)


def test_formatter_attachment_inlined_reads_source_without_rU(req):
    pagename = "AutoCreatedInlineAttachmentPyTestPage"
    filename = "inline_demo.py"
    raw_bytes = b"# caf\xe9\rprint(123)\r"

    become_trusted(req)
    create_page(req, pagename, "Inline attachment test page\n")
    try:
        AttachFile.add_attachment(req, pagename, filename, raw_bytes, overwrite=True)

        context = _make_view_context(req, pagename, filename)
        link_html = context.formatter.attachment_inlined(filename, filename)
        rendered = _response_text(context.response)

        assert "café" in rendered
        assert "print" in rendered
        assert "123" in rendered
        assert filename in link_html
        assert "\r" not in rendered
    finally:
        nuke_page(req, pagename)
