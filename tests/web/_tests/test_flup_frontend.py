"""
    MoinMoin - Flup frontend compatibility tests

    @license: GNU GPL, see COPYING for details.
"""

import sys

from MoinMoin.web import flup_frontend


def test_format_web_error_uses_standard_traceback_and_escapes_html():
    try:
        raise RuntimeError('<script>alert("bad")</script>')
    except RuntimeError:
        page = flup_frontend.format_web_error(sys.exc_info())

    assert 'RuntimeError' in page
    assert '&lt;script&gt;' in page
    assert '<script>' not in page
