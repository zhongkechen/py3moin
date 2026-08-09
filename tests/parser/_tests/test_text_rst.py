"""
    MoinMoin - reStructuredText parser tests

    @license: GNU GPL, see COPYING for details.
"""

import pytest

pytest.importorskip('docutils')

from MoinMoin.Page import Page
from MoinMoin.parser.text_rst import Parser


def test_rst_handlers_are_bound_and_rendered(req):
    page = Page(req, 'RstTestPage')
    req.page = page
    req.formatter.page = page
    parser = Parser('This is **strong**.', req)

    result = req.redirectedOutput(parser.format, req.formatter)

    assert '<strong>strong</strong>' in result
