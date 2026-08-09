"""
MoinMoin - web context compatibility tests

@license: GNU GPL, see COPYING for details.
"""


def test_http_context_exposes_request_views(req):
    assert req.form is req.request.form
    assert req.href is req.request.href
