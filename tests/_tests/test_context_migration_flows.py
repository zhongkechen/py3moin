"""
MoinMoin - Request/Context migration regression tests across account,
rendering, macro, and export flows (Issue #21).

@license: GNU GPL, see COPYING for details.
"""

import io
import re
import zipfile
from urllib.parse import parse_qs, urlsplit

import pytest

from MoinMoin import user, wikiutil
from MoinMoin.Page import Page
from MoinMoin.PageEditor import PageEditor
from MoinMoin.action import PackagePages, newaccount, recoverpass
from MoinMoin.auth import MoinAuth
from MoinMoin.macro import Macro
from MoinMoin.macro import FullSearch as fullsearch_macro
from MoinMoin.macro import RecentChanges as recentchanges_macro
from MoinMoin.mail import sendmail
from MoinMoin.userprefs import changepass
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.http import create_environ, exceptions
from MoinMoin.web.request import Request
from tests._tests import become_trusted, create_page, nuke_page


def _clear_user_lookup_caches(cfg):
    for key in user.CACHED_USER_ATTRS:
        for suffix in ("2id", "2id_lower"):
            attr = key + suffix
            if hasattr(cfg.cache, attr):
                delattr(cfg.cache, attr)


def _make_context(req, path="/FrontPage", method="GET", query_string=None, data=None, cfg=None):
    environ = create_environ(
        path=path,
        method=method,
        query_string=query_string,
        data=data,
    )
    environ["REMOTE_ADDR"] = "127.0.0.1"
    given_config = (lambda _name: cfg) if cfg is not None else req.request.given_config
    wsgi_req = Request(environ, given_config=given_config)
    context = AllContext(wsgi_req)
    context.page = Page(context, path.lstrip("/") or "FrontPage")
    return context


@pytest.fixture
def isolated_user_cfg(req, tmp_path):
    user_dir = tmp_path / "users"
    user_dir.mkdir()
    cfg = req.request.given_config("MoinMoin._tests.wikiconfig")
    cfg.user_dir = str(user_dir)
    _clear_user_lookup_caches(cfg)
    return cfg


def _response_bytes(response):
    return b"".join(
        chunk.encode("utf-8") if isinstance(chunk, str) else chunk
        for chunk in response.response
    )


def _response_text(response):
    return _response_bytes(response).decode("utf-8", "replace")


def test_recoverpass_get_email_and_reset_flow(req, isolated_user_cfg, monkeypatch):
    sent_mails = []

    def fake_sendmail(context, to, subject, text, mail_from=None):
        sent_mails.append({"to": to, "subject": subject, "text": text, "mail_from": mail_from})
        return True, "Mail sent OK"

    monkeypatch.setattr(sendmail, "sendmail", fake_sendmail)
    cfg = isolated_user_cfg
    cfg.auth = [MoinAuth()]
    cfg.mail_enabled = True
    cfg.mail_from = "wiki@example.com"

    # Seed a persisted user in isolated temporary storage.
    seed_ctx = _make_context(req, cfg=cfg)
    account = user.User(seed_ctx, auth_method="new-user")
    account.name = "RecoverAlice"
    account.email = "alice@example.com"
    account.enc_password = user.encodePassword(cfg, "OldPass123!")
    account.save()

    # 1. Recovery GET displays both recovery and token forms.
    get_ctx = _make_context(
        req,
        path="/ExamplePage",
        method="GET",
        query_string={"action": "recoverpass"},
        cfg=cfg,
    )
    recoverpass.execute("ExamplePage", get_ctx)
    html_get = _response_text(get_ctx.response)
    assert 'name="account_sendmail"' in html_get
    assert 'name="token"' in html_get

    # 2. GET with account_sendmail must not send mail (POST required).
    get_submit_ctx = _make_context(
        req,
        path="/ExamplePage",
        method="GET",
        query_string={"action": "recoverpass", "account_sendmail": "1", "email": "alice@example.com"},
        cfg=cfg,
    )
    recoverpass.execute("ExamplePage", get_submit_ctx)
    assert sent_mails == []

    # 3. POST recovery-email submission sends reset URL built from context.request.url.
    post_ctx = _make_context(
        req,
        path="/ExamplePage",
        method="POST",
        data={"action": "recoverpass", "account_sendmail": "1", "email": "alice@example.com"},
        cfg=cfg,
    )
    recoverpass.execute("ExamplePage", post_ctx)

    assert len(sent_mails) == 1
    assert sent_mails[0]["to"] == ["alice@example.com"]
    mail_body = sent_mails[0]["text"]
    match = re.search(r"http://[^\s]+action=recoverpass&name=RecoverAlice&token=([0-9a-f-]+)", mail_body)
    assert match is not None, f"Reset URL missing from email body: {mail_body!r}"
    token = match.group(1)

    # 4. Opening the reset link via GET renders the token form with prefilled values.
    link_ctx = _make_context(
        req,
        path="/ExamplePage",
        method="GET",
        query_string={"action": "recoverpass", "name": "RecoverAlice", "token": token},
        cfg=cfg,
    )
    recoverpass.execute("ExamplePage", link_ctx)
    link_html = _response_text(link_ctx.response)
    assert token in link_html
    assert 'value="RecoverAlice"' in link_html

    # 5. Submitting mismatched passwords is rejected without changing password.
    bad_reset_ctx = _make_context(
        req,
        path="/ExamplePage",
        method="POST",
        data={
            "action": "recoverpass",
            "name": "RecoverAlice",
            "token": token,
            "password": "NewPass456!",
            "password_repeat": "Different789!",
        },
        cfg=cfg,
    )
    recoverpass.execute("ExamplePage", bad_reset_ctx)
    assert "don't match" in _response_text(bad_reset_ctx.response)

    # 6. Submitting matching new password updates stored account and clears token.
    reset_ctx = _make_context(
        req,
        path="/ExamplePage",
        method="POST",
        data={
            "action": "recoverpass",
            "name": "RecoverAlice",
            "token": token,
            "password": "NewPass456!",
            "password_repeat": "NewPass456!",
        },
        cfg=cfg,
    )
    recoverpass.execute("ExamplePage", reset_ctx)

    reloaded = user.User(reset_ctx, auth_username="RecoverAlice", password="NewPass456!", auth_method="moin:login")
    assert reloaded.valid
    assert reloaded.recoverpass_key == ""


def test_newaccount_rejects_invalid_and_creates_user(req, isolated_user_cfg):
    cfg = isolated_user_cfg
    cfg.auth = [MoinAuth()]

    # Non-POST request is rejected immediately.
    get_ctx = _make_context(
        req,
        method="GET",
        query_string={"name": "NewBob", "password1": "Secret123!", "password2": "Secret123!", "email": "bob@example.com"},
        cfg=cfg,
    )
    assert newaccount._create_user(get_ctx) is None
    assert not user.getUserId(get_ctx, "NewBob")

    # POST with mismatched passwords is rejected (anonymous user also exercises TextCha).
    ticket_ctx = _make_context(req, method="GET", cfg=cfg)
    ticket = wikiutil.createTicket(ticket_ctx)

    bad_ctx = _make_context(
        req,
        method="POST",
        data={
            "ticket": ticket,
            "name": "NewBob",
            "password1": "Secret123!",
            "password2": "Other456!",
            "email": "bob@example.com",
        },
        cfg=cfg,
    )
    msg = newaccount._create_user(bad_ctx)
    assert "don't match" in msg
    assert not user.getUserId(bad_ctx, "NewBob")

    # Valid POST creates and persists the user profile in temporary user_dir.
    ok_ctx = _make_context(
        req,
        method="POST",
        data={
            "ticket": ticket,
            "name": "NewBob",
            "password1": "Secret123!",
            "password2": "Secret123!",
            "email": "bob@example.com",
        },
        cfg=cfg,
    )
    ok_msg = newaccount._create_user(ok_ctx)
    assert "created" in ok_msg.lower()

    uid = user.getUserId(ok_ctx, "NewBob")
    assert uid
    created = user.User(ok_ctx, auth_username="NewBob", password="Secret123!", auth_method="moin:login")
    assert created.valid
    assert created.email == "bob@example.com"


def test_changepass_rejects_invalid_and_updates_password(req, isolated_user_cfg):
    cfg = isolated_user_cfg
    seed_ctx = _make_context(req, cfg=cfg)
    account = user.User(seed_ctx, auth_method="new-user")
    account.name = "ChangeCarol"
    account.email = "carol@example.com"
    account.enc_password = user.encodePassword(cfg, "InitialPass1!")
    account.save()
    uid = account.id

    # GET request returns None and leaves password unchanged.
    get_ctx = _make_context(req, method="GET", cfg=cfg)
    get_ctx.user = user.User(get_ctx, uid)
    assert changepass.Settings(get_ctx).handle_form() is None

    ticket = wikiutil.createTicket(get_ctx)

    # POST with mismatched password returns error and does not save.
    bad_ctx = _make_context(
        req,
        method="POST",
        data={"ticket": ticket, "password1": "NewPass2!", "password2": "Mismatch2!", "save": "1"},
        cfg=cfg,
    )
    bad_ctx.user = user.User(bad_ctx, uid)
    kind, msg = changepass.Settings(bad_ctx).handle_form()
    assert kind == "error"
    assert "don't match" in msg

    # Valid POST updates and persists the password hash.
    ok_ctx = _make_context(
        req,
        method="POST",
        data={"ticket": ticket, "password1": "UpdatedPass9!", "password2": "UpdatedPass9!", "save": "1"},
        cfg=cfg,
    )
    ok_ctx.user = user.User(ok_ctx, uid)
    kind, msg = changepass.Settings(ok_ctx).handle_form()
    assert kind == "info"
    assert "changed" in msg.lower()

    assert not user.User(ok_ctx, auth_username="ChangeCarol", password="InitialPass1!", auth_method="moin:login").valid
    assert user.User(ok_ctx, auth_username="ChangeCarol", password="UpdatedPass9!", auth_method="moin:login").valid


def test_page_redirect_directive_and_highlight_message(req, monkeypatch):
    src_page = "AutoCreatedRedirectSourceTestPage"
    dst_page = "AutoCreatedRedirectTargetTestPage"
    hilite_page = "AutoCreatedHighlightMsgTestPage"

    become_trusted(req)
    create_page(req, src_page, f"#redirect {dst_page}\nRedirect body.\n")
    create_page(req, dst_page, "Target page body.\n")
    create_page(req, hilite_page, "Find this needleword in the page.\n")
    try:
        # 1. Plain GET on redirect page triggers HTTP 302 redirect.
        redir_ctx = _make_context(req, path="/" + src_page, method="GET")
        become_trusted(redir_ctx)
        with pytest.raises(exceptions.HTTPException) as exc_info:
            Page(redir_ctx, src_page).send_page()
        response = exc_info.value.get_response(redir_ctx.environ)
        assert response.status_code == 302
        location = response.headers["Location"]
        assert dst_page in location
        parsed = parse_qs(urlsplit(location).query)
        assert parsed["action"] == ["show"]
        assert parsed["redirect"] == [src_page]

        # 2. With action=show or redirect=... query params, page renders without redirecting.
        for qs in ({"action": "show"}, {"redirect": "SomeOrigin"}):
            no_redir_ctx = _make_context(req, path="/" + src_page, method="GET", query_string=qs)
            become_trusted(no_redir_ctx)
            Page(no_redir_ctx, src_page).send_page()
            assert no_redir_ctx.response.status_code == 200
            assert "Redirect body." in _response_text(no_redir_ctx.response)

        # 3. Optional highlighted-page message reads context.request.values.items().
        hilite_ctx = _make_context(
            req,
            path="/" + hilite_page,
            method="GET",
            query_string={"highlight": "needleword", "extra": "keep"},
        )
        become_trusted(hilite_ctx)
        monkeypatch.setattr(hilite_ctx.cfg, "show_highlight_msg", True, raising=False)
        Page(hilite_ctx, hilite_page).send_page()
        html = _response_text(hilite_ctx.response)
        assert "needleword" in html
        assert "Switch to non-highlighted view" in html
        assert "extra=keep" in html
    finally:
        nuke_page(req, src_page)
        nuke_page(req, dst_page)
        nuke_page(req, hilite_page)


def test_argument_free_fullsearch_and_abandoned_pages_macros(req):
    pagename = "AutoCreatedMacroContextFlowTestPage"
    become_trusted(req)
    create_page(req, pagename, "Macro context test page content.\n")
    try:
        # Argument-free FullSearch macro without and with ?value=...
        ctx_empty = _make_context(req, path="/" + pagename, method="GET")
        become_trusted(ctx_empty)
        ctx_empty.formatter.setPage(Page(ctx_empty, pagename))
        macro_empty = Macro(ctx_empty.formatter)
        box_empty = fullsearch_macro.execute(macro_empty, None)
        assert '<input type="hidden" name="action" value="fullsearch">' in box_empty

        ctx_val = _make_context(
            req,
            path="/" + pagename,
            method="GET",
            query_string={"value": 'alpha "beta"'},
        )
        become_trusted(ctx_val)
        ctx_val.formatter.setPage(Page(ctx_val, pagename))
        macro_val = Macro(ctx_val.formatter)
        box_val = fullsearch_macro.execute(macro_val, None)
        assert 'value="alpha &quot;beta&quot;"' in box_val

        # AbandonedPages via RecentChanges(abandoned=True) with max_days query parameter.
        ctx_abandoned = _make_context(
            req,
            path="/" + pagename,
            method="GET",
            query_string={"max_days": "2"},
        )
        become_trusted(ctx_abandoned)
        ctx_abandoned.formatter.setPage(Page(ctx_abandoned, pagename))
        macro_abandoned = Macro(ctx_abandoned.formatter)
        abandoned_html = recentchanges_macro.macro_RecentChanges(macro_abandoned, abandoned=True)
        assert "recentchanges" in abandoned_html.lower()
        assert pagename in abandoned_html
    finally:
        nuke_page(req, pagename)


def test_packagepages_zip_export_headers_and_body(req):
    pagename = "AutoCreatedPackageExportTestPage"
    become_trusted(req)
    create_page(req, pagename, "Packaged page content for export.\n")
    try:
        ctx = _make_context(
            req,
            path="/" + pagename,
            method="POST",
            data={
                "action": "PackagePages",
                "submit": "Package pages",
                "packagename": "export.zip",
                "pagelist": pagename,
            },
        )
        become_trusted(ctx)
        PackagePages.execute(pagename, ctx)

        headers = ctx.response.headers
        assert headers["Content-Type"] == "application/zip"
        assert headers["Content-Disposition"] == 'inline; filename="export.zip"'

        zip_bytes = _response_bytes(ctx.response)
        assert headers["Content-Length"] == str(len(zip_bytes))

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
            assert "MOIN_PACKAGE" in names
            assert "1" in names
            assert zf.read("1").decode("utf-8") == "Packaged page content for export.\n"
            assert pagename in zf.read("MOIN_PACKAGE").decode("utf-8")
    finally:
        nuke_page(req, pagename)
