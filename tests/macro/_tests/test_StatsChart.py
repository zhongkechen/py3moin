
"""
    MoinMoin - MoinMoin.macro StatsChart tested

    @copyright: 2008 MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""
from builtins import object

import pytest

from MoinMoin import caching
from tests._tests import become_trusted, create_page, make_macro, nuke_page

class TestStatsCharts(object):
    """StartsChart: testing StatsChart macro """
    pagename = u'AutoCreatedMoinMoinTemporaryTestPageStatsChart'

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        become_trusted(req)
        self.page = create_page(req, self.pagename, u"Foo!")
        # clean page scope cache entries
        for key in ['text_html', 'pagelinks', ]:
            caching.CacheEntry(req, self.page, key, scope='item').remove()

        yield

        nuke_page(req, self.pagename)

    def _test_macro(self, req, name, args):
        m = make_macro(req, self.page)
        return m.execute(name, args)

    def testStatsChart_useragents(self, req):
        """ macro StatsChart useragents test: 'tests useragents' and clean page scope cache """
        result = self._test_macro(req, u'StatsChart', u'useragents')
        expected = u'<form action="/AutoCreatedMoinMoinTemporaryTestPageStatsChart" method="GET"'
        assert expected in result

    def testStatsChart_hitcounts(self, req):
        """ macro StatsChart hitcounts test: 'tests hitcounts' and clean page scope cache  """
        result = self._test_macro(req, u'StatsChart', u'hitcounts')
        expected = u'<form action="/AutoCreatedMoinMoinTemporaryTestPageStatsChart" method="GET"'
        assert expected in result

    def testStatsChart_languages(self, req):
        """ macro StatsChart languages test: 'tests languages' and clean page scope cache  """
        result = self._test_macro(req, u'StatsChart', u'hitcounts')
        expected = u'<form action="/AutoCreatedMoinMoinTemporaryTestPageStatsChart" method="GET"'
        assert expected in result

coverage_modules = ['MoinMoin.stats']
