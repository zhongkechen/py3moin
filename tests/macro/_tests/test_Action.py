# -*- coding: utf-8 -*-
"""
    MoinMoin - MoinMoin.macro.Action Tests

    @copyright: 2007 MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""
from builtins import object

from MoinMoin.macro import Action

from tests._tests import become_trusted, create_page, make_macro, nuke_page


class TestAction(object):
    """ testing macro Action calling action raw """
    pagename = u'AutoCreatedMoinMoinTemporaryTestPageForAction'

    def testActionCallingRaw(self, req):
        """ module_tested: executes raw by macro Action on existing page"""
        request = req
        become_trusted(request)
        self.page = create_page(request, self.pagename, u'= title1 =\n||A||B||\n')
        m = make_macro(req, self.page)
        result = Action.macro_Action(m, 'raw')
        nuke_page(request, self.pagename)
        expected = '<a class="action" href="/AutoCreatedMoinMoinTemporaryTestPageForAction?action=raw">raw</a>'
        assert result == expected


coverage_modules = ['MoinMoin.macro.Action']
