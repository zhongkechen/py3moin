
"""
    MoinMoin - MoinMoin.macro GetVal tested

    @copyright: 2007 MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""
from builtins import object
import os, py

import pytest

from MoinMoin import macro
from MoinMoin.Page import Page
from MoinMoin.PageEditor import PageEditor
from MoinMoin._tests import become_trusted, create_page, make_macro, nuke_page

class TestGetVal(object):
    """GetVal: testing getVal macro """
    pagename = u'MyDict'

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        become_trusted(req)
        self.cfg = req.cfg
        
        yield

        nuke_page(req, self.pagename)

    def _test_macro(self, req, name, args, page):
        m = make_macro(req, page)
        return m.execute(name, args)

    def testGetValNoACLs(self, req):
        """ macro GetVal test: 'reads VAR' """
        page = create_page(req, self.pagename, u' VAR:: This is an example')
        result = self._test_macro(req, u'GetVal', "%s,%s" % (self.pagename, u'VAR'), page)
        assert result == "This is an example"

    def testGetValAfterADictPageIsDeleted(self, req):
        """ macro GetVal test: 'reads Dict var after another Dict is removed' """
        request = req
        become_trusted(request)
        page = create_page(request, u'SomeDict', u" EXAMPLE:: This is an example text")
        page.deletePage()
        page = create_page(request, self.pagename, u' VAR:: This is a brand new example')
        result = self._test_macro(req, u'GetVal', "%s,%s" % (self.pagename, u'VAR'), page)
        nuke_page(request, u'SomeDict')
        assert result == "This is a brand new example"

    def testGetValACLs(self, req):
        """ macro GetVal test: 'cant read VAR on an ACL protected page' """
        pytest.skip("user has no rights to create acl pages")
        page = create_page(req, self.pagename,
                           '#acl SomeUser:read,write All:delete\n VAR:: This is an example')
        result = self._test_macro(req, u'GetVal', "%s,%s" % (self.pagename, u'VAR'), page)
        assert result == "&lt;&lt;GetVal: You don't have enough rights on this page&gt;&gt;"


coverage_modules = ['MoinMoin.macro.GetVal']

