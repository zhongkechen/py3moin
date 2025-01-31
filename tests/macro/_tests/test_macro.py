
"""
    MoinMoin - MoinMoin.macro Tests

    @copyright: 2003-2004 by Juergen Hermann <jh@web.de>,
                2006 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

import pytest

from tests._tests import become_trusted, create_page, make_macro, nuke_page

class TestMacro:
    pagename = u'AutoCreatedMoinMoinTemporaryTestPageForTestMacro'

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        request = req
        become_trusted(request)
        self.page = create_page(request, self.pagename, u"Foo!")

        yield

        nuke_page(req, self.pagename)

    def testTrivialMacro(self, req):
        """macro: trivial macro works"""
        m = make_macro(req, self.page)
        expected = m.formatter.linebreak(0)
        result = m.execute("BR", "")
        assert result == expected

coverage_modules = ['MoinMoin.macro']

