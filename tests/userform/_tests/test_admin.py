
"""
    MoinMoin - MoinMoin.userform.admin Tests

    @copyright: 2009 MoinMoin:DmitrijsMilajevs
    @license: GNU GPL, see COPYING for details.
"""


import pytest

from MoinMoin.userform.admin import do_user_browser
from MoinMoin.datastruct import ConfigGroups
from MoinMoin.user import User
from MoinMoin.Page import Page
from tests._tests import nuke_user, become_superuser, wikiconfig

class TestAdmin:

    class Config(wikiconfig.Config):

        def groups(self, request):
            groups = {'OneGroup': ['TestUser, OtherUser'],
                      'OtherGroup': ['TestUser']}
            return ConfigGroups(request, groups)

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        request = req
        user_name = 'TestUser'
        self.user_name = user_name

        become_superuser(request)

        User(request, name=user_name, password=user_name).save()

        yield

        nuke_user(req, self.user_name)

    @pytest.fixture(autouse=True)
    def setup_method(self, req):
        req.page = Page(req, 'SystemAdmin')

    def test_do_user_browser(self, req):
        browser = do_user_browser(req)
        assert browser


coverage_modules = ['MoinMoin.userform.admin']

