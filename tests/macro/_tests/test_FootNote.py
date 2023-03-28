# -*- coding: utf-8 -*-
"""
    MoinMoin - MoinMoin.macro.FootNote Tests

    @copyright: 2008 MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""
from builtins import object

import pytest

from MoinMoin.macro import FootNote
from tests._tests import become_trusted, create_page, make_macro, nuke_page

class TestFootNote(object):
    """ testing macro Action calling action raw """
    pagename = u'AutoCreatedMoinMoinTemporaryTestPageForFootNote'

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        become_trusted(req)
        self.page = create_page(req, self.pagename, u"Foo!")

        yield

        nuke_page(req, self.pagename)

    def test_enumbering(self, req):
        """ module_tested: enumbering of Footnotes"""
        m = make_macro(req, self.page)
        text = 'a'
        FootNote.execute(m, text)
        text = 'b'
        FootNote.execute(m, text)
        result = FootNote.emit_footnotes(m.request, m.request.formatter)
        assert result.endswith('2</a>)</li></ol></div>')

coverage_modules = ['MoinMoin.macro.FootNote']
