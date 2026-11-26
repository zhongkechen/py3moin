"""
MoinMoin - Attachment download Content-Disposition and WSGI serialization tests (Issue #22).

@license: GNU GPL, see COPYING for details.
"""

import os
import re
from urllib.parse import unquote

import pytest

from MoinMoin.action import AttachFile
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.http import Client, content_disposition_header, create_environ
from MoinMoin.web.request import MoinMoinFinish, Request
from MoinMoin.wsgiapp import Application
from tests._tests import become_trusted, create_page, nuke_page


def _serialize_wsgi_response(response, environ):
    """Run a Werkzeug Response through strict PEP 3333 / uWSGI Latin-1 header serialization."""
    captured = {}

    def start_response(status, headers, exc_info=None):
        status.encode("latin-1")
        encoded_headers = []
        for name, value in headers:
            if not isinstance(name, str) or not isinstance(value, str):
                raise TypeError("WSGI header name and value must be str")
            try:
                name.encode("latin-1")
                value.encode("latin-1")
            except UnicodeEncodeError as exc:
                raise TypeError("http header must be encodable in latin1") from exc
            encoded_headers.append((name, value))
        captured["status"] = status
        captured["headers"] = encoded_headers

    chunks = []
    app_iter = response(environ, start_response)
    try:
        for chunk in app_iter:
            chunks.append(chunk)
    finally:
        close = getattr(app_iter, "close", None)
        if callable(close):
            close()

    return captured["status"], dict(captured["headers"]), b"".join(chunks)


def _extract_filename_star(header_value):
    match = re.search(r"filename\*=UTF-8''([^;]+)", header_value)
    assert match is not None, f"Missing RFC 5987 filename* parameter in {header_value!r}"
    return unquote(match.group(1), encoding="utf-8", errors="strict")


def test_content_disposition_header_builder():
    header = content_disposition_header("inline", 'my "quoted" file.txt')
    header.encode("ascii")
    assert header.startswith('inline; filename="my \\"quoted\\" file.txt"; ')
    assert _extract_filename_star(header) == 'my "quoted" file.txt'

    zh_header = content_disposition_header("inline", "中文课件.doc")
    zh_header.encode("ascii")
    assert 'filename="attachment.doc"' in zh_header
    assert _extract_filename_star(zh_header) == "中文课件.doc"

    emoji_header = content_disposition_header("attachment", 'notes 🚀 "final".html')
    emoji_header.encode("ascii")
    assert emoji_header.startswith("attachment; ")
    assert '\\"' in emoji_header.split("; filename*=")[0]
    assert _extract_filename_star(emoji_header) == 'notes 🚀 "final".html'

    emoji_only = content_disposition_header("inline", "🚀")
    emoji_only.encode("ascii")
    assert 'filename="attachment"' in emoji_only
    assert _extract_filename_star(emoji_only) == "🚀"

    injected = content_disposition_header("inline", "bad\r\nX-Injected: 1.txt")
    assert "\r" not in injected and "\n" not in injected


@pytest.mark.parametrize(
    ("filename", "expected_dispo"),
    [
        ("sample.doc", "inline"),
        ("report 2026 draft.txt", "inline"),
        ("中文课件.doc", "inline"),
        ("notes 🚀 final.txt", "inline"),
        ("中文页面.html", "attachment"),
        ("drawing.svg", "attachment"),
    ],
)
def test_attachfile_do_get_wsgi_unicode_downloads(req, filename, expected_dispo):
    pagename = "AutoCreatedAttachmentDownloadUnicodeTestPage"
    payload = b"0123456789abcdef!\n"  # 18 bytes

    become_trusted(req)
    create_page(req, pagename, "Attachment test page\n")
    try:
        AttachFile.add_attachment(req, pagename, filename, payload, overwrite=True)

        environ = create_environ(
            path="/" + pagename,
            query_string={"action": "AttachFile", "do": "get", "target": filename},
            method="GET",
        )
        wsgi_req = Request(environ, given_config=req.request.given_config)
        context = AllContext(wsgi_req)
        become_trusted(context)

        with pytest.raises(MoinMoinFinish):
            AttachFile._do_get(pagename, context)

        status, headers, body = _serialize_wsgi_response(context.response, environ)

        assert status.startswith("200 ")
        assert body == payload
        assert headers["Content-Length"] == str(len(payload))

        dispo = headers["Content-Disposition"]
        dispo.encode("latin-1")
        assert dispo.startswith(f"{expected_dispo}; ")
        assert 'filename="' in dispo
        assert _extract_filename_star(dispo) == filename
    finally:
        nuke_page(req, pagename)


def test_attachfile_do_get_quotes_and_spaces_with_file_wrapper(req, tmp_path, monkeypatch):
    pagename = "AutoCreatedAttachmentDownloadQuotedTestPage"
    filename = 'notes 🚀 "final".txt'
    payload = b"quoted unicode payload\n"
    fixture = tmp_path / "fixture.txt"
    fixture.write_bytes(payload)

    def fake_file_wrapper(fileobj, bufsize=8192):
        try:
            while True:
                chunk = fileobj.read(bufsize)
                if not chunk:
                    break
                yield chunk
        finally:
            fileobj.close()

    environ = create_environ(path="/" + pagename, method="GET")
    environ["wsgi.file_wrapper"] = fake_file_wrapper
    wsgi_req = Request(environ, given_config=req.request.given_config)
    context = AllContext(wsgi_req)
    become_trusted(context)

    monkeypatch.setattr(AttachFile, "_access_file", lambda p, c: (pagename, filename, str(fixture)))

    with pytest.raises(MoinMoinFinish):
        AttachFile._do_get(pagename, context)

    status, headers, body = _serialize_wsgi_response(context.response, environ)

    assert status.startswith("200 ")
    assert body == payload
    dispo = headers["Content-Disposition"]
    dispo.encode("latin-1")
    assert dispo.startswith("inline; ")
    assert '\\"' in dispo.split("; filename*=")[0]
    assert _extract_filename_star(dispo) == filename


@pytest.mark.parametrize('container', [False, True])
def test_attachment_conditional_get_compares_whole_seconds(req, container):
    pagename = 'AutoCreatedAttachmentConditionalTestPage'
    target = 'files.tar' if container else 'fixture.txt'
    payload = b'Attachment contents.\n'
    query = {'action': 'AttachFile', 'target': target}
    become_trusted(req)
    create_page(req, pagename, 'Page with an attachment.\n')
    try:
        if container:
            AttachFile.getAttachDir(req, pagename, create=1)
            AttachFile.ContainerItem(req, pagename, target).put('fixture.txt', payload)
            query.update(do='box', member='fixture.txt')
        else:
            AttachFile.add_attachment(req, pagename, target, payload)
            query['do'] = 'get'

        path = AttachFile.getFilename(req, pagename, target)
        mtime = 1_700_000_000_125_000_000
        os.utime(path, ns=(mtime, mtime))
        client = Client(Application(lambda _: req.cfg))
        url = '/' + pagename
        first = client.get(url, query_string=query, buffered=True)
        assert first.status_code == 200
        assert first.data == payload

        headers = {'If-Modified-Since': first.headers['Last-Modified']}
        unchanged = client.get(url, query_string=query, headers=headers, buffered=True)
        assert unchanged.status_code == 304
        assert unchanged.data == b''

        updated = mtime + 10**9
        os.utime(path, ns=(updated, updated))
        modified = client.get(url, query_string=query, headers=headers, buffered=True)
        assert modified.status_code == 200
        assert modified.data == payload
        assert modified.headers['Last-Modified'] != headers['If-Modified-Since']
    finally:
        nuke_page(req, pagename)
