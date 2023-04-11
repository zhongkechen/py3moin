# -*- coding: utf-8 -*-
"""
    MoinMoin - MoinMoin.theme Tests

    @copyright: 2008 MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""

import pytest

from MoinMoin.theme import ThemeBase
from MoinMoin.Page import Page

class TestEditBarActions(object):

    @pytest.fixture(autouse=True)
    def setup_method(self, req):
        req.cfg.mail_enabled = True
        self.page = Page(req, u'FrontPage')
        self.ThemeBase = ThemeBase(req)


    def test_editbar_for_anonymous_user(self, req):
        assert not req.user.valid
        assert not self.ThemeBase.subscribeLink(self.page)
        assert not self.ThemeBase.quicklinkLink(self.page)

    def test_editbar_for_valid_user(self, req):
        req.user.valid = True
        assert req.user.valid
        assert 'subscribe' in self.ThemeBase.subscribeLink(self.page)
        assert 'quicklink' in self.ThemeBase.quicklinkLink(self.page)

coverage_modules = ['MoinMoin.theme']
