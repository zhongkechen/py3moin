
"""
    MoinMoin - MoinMoin.macro PageHits tested

    @copyright: 2008 MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""
from builtins import range
from builtins import object
import os

import pytest

from MoinMoin import caching, macro
from MoinMoin.logfile import eventlog
from MoinMoin.PageEditor import PageEditor
from MoinMoin.Page import Page

from MoinMoin._tests import become_trusted, create_page, make_macro, nuke_eventlog, nuke_page

class TestHits(object):
    """Hits: testing Hits macro """
    pagename = u'AutoCreatedMoinMoinTemporaryTestPageForPageHits'

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        request = req
        become_trusted(request)
        self.page = create_page(request, self.pagename, u"Foo!")
        # for that test eventlog needs to be empty
        nuke_eventlog(req)
        # hits is based on hitcounts which reads the cache
        caching.CacheEntry(request, 'charts', 'pagehits', scope='wiki').remove()
        caching.CacheEntry(request, 'charts', 'hitcounts', scope='wiki').remove()

        yield
        nuke_page(req, self.pagename)

    def _test_macro(self, req, name, args):
        m = make_macro(req, self.page)
        return m.execute(name, args)

    def testPageHits(self, req):
        """ macro PageHits test: updating of cache from event-log for multiple call of PageHits"""
        count = 20
        for counter in range(count):
            eventlog.EventLog(req).add(req, 'VIEWPAGE', {'pagename': 'PageHits'})
            result = self._test_macro(req, u'PageHits', u'') # XXX SENSE???
        cache = caching.CacheEntry(req, 'charts', 'pagehits', scope='wiki', use_pickle=True)
        date, hits = 0, {}
        if cache.exists():
            try:
                date, hits = cache.content()
            except caching.CacheError:
                cache.remove()
        assert hits['PageHits'] == count

coverage_modules = ['MoinMoin.macro.PageHits']
