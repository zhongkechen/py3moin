# -*- coding: utf-8 -*-
"""
    MoinMoin - MoinMoin.wsgiapp Tests

    @copyright: 2008 MoinMoin:FlorianKrupicka
    @license: GNU GPL, see COPYING for details.
"""
from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from builtins import object
from io import StringIO

from MoinMoin import wsgiapp

DOC_TYPE = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">'

class TestApplication(object):
    # self.client is made by conftest

    # These should exist
    PAGES = ('FrontPage', 'RecentChanges', 'HelpContents', 'FindPage')
    # ... and these should not
    NO_PAGES = ('FooBar', 'TheNone/ExistantPage/', '%33Strange%74Codes')

    def testWSGIAppExisting(self):
        for page in self.PAGES:
            def _test_(page=page):
                appiter, status, headers = self.client.get('/%s' % page)
                output = ''.join(appiter)
                print(output)
                assert status[:3] == '200'
                assert ('Content-Type', 'text/html; charset=utf-8') in list(headers)
                for needle in (DOC_TYPE, page):
                    assert needle in output
            yield _test_

    def testWSGIAppAbsent(self):
        for page in self.NO_PAGES:
            def _test_(page=page):
                appiter, status, headers = self.client.get('/%s' % page)
                assert status[:3] == '404'
                output = ''.join(appiter)
                for needle in ('new empty page', 'page template'):
                    assert needle in output
            yield _test_