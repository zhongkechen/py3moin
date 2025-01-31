

"""
MoinMoin.datastruct.backends.composite_dicts test

@copyright: 2009 MoinMoin:DmitrijsMilajevs
            2008 MoinMoin: MelitaMihaljevic
@license: GPL, see COPYING for details
"""

from tests.datastruct.backends._tests import DictsBackendTest
from MoinMoin.datastruct import ConfigDicts, CompositeDicts
from tests._tests import wikiconfig


class TestCompositeDict(DictsBackendTest):

    class Config(wikiconfig.Config):

        one_dict = {u'SomeTestDict': {u'First': u'first item',
                                      u'text with spaces': u'second item',
                                      u'Empty string': u'',
                                      u'Last': u'last item'}}

        other_dict = {u'SomeOtherTestDict': {u'One': '1',
                                             u'Two': '2'}}

        def dicts(self, request):
            return CompositeDicts(request,
                                  ConfigDicts(request, self.one_dict),
                                  ConfigDicts(request, self.other_dict))


coverage_modules = ['MoinMoin.datastruct.backends.composite_dicts']
