
"""
    MoinMoin - MoinMoin.backends.config_dicts tests

    @copyright: 2009 by MoinMoin:DmitrijsMilajevs
    @license: GNU GPL, see COPYING for details.
"""

from tests.datastruct.backends._tests import DictsBackendTest
from MoinMoin.datastruct import ConfigDicts
from tests._tests import wikiconfig


class TestConfigDictsBackend(DictsBackendTest):

    class Config(wikiconfig.Config):

        def dicts(self, request):
            dicts = DictsBackendTest.dicts
            return ConfigDicts(request, dicts)


coverage_modules = ['MoinMoin.datastruct.backends.config_dicts']

