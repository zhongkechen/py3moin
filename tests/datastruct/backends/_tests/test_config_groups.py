
"""
    MoinMoin - MoinMoin.backends.config_groups tests

    @copyright: 2009 by MoinMoin:DmitrijsMilajevs
    @license: GNU GPL, see COPYING for details.
"""

from tests.datastruct.backends._tests import GroupsBackendTest
from MoinMoin.datastruct import ConfigGroups
from tests._tests import wikiconfig


class TestConfigGroupsBackend(GroupsBackendTest):

    class Config(wikiconfig.Config):

        def groups(self, request):
            groups = GroupsBackendTest.test_groups
            return ConfigGroups(request, groups)


coverage_modules = ['MoinMoin.datastruct.backends.config_groups']

