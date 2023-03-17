# -*- coding: iso-8859-1 -*-
"""
    MoinMoin - MoinMoin.PageEditor Tests

    @copyright: 2003-2004 by Juergen Hermann <jh@web.de>,
                2007 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

import pytest
import os
import shutil

from MoinMoin.Page import Page
from MoinMoin.PageEditor import PageEditor
from MoinMoin.security import parseACL

# TODO: check if and where we can use the helpers:
from MoinMoin._tests import become_trusted, create_page, nuke_page

class TestExpandVars(object):
    """PageEditor: testing page editor"""
    pagename = u'AutoCreatedMoinMoinTemporaryTestPage'

    _tests = (
        # Variable,             Expanded
        ("@PAGE@", pagename),
        ("em@PAGE@bedded", "em%sbedded" % pagename),
        ("@NOVAR@", "@NOVAR@"),
        ("case@Page@sensitive", "case@Page@sensitive"),
        )

    def testExpandVariables(self, req):
        """ PageEditor: expand general variables """
        page = PageEditor(req, self.pagename)
        for var, expected in self._tests:
            result = page._expand_variables(var)
            assert result == expected


class TestExpandUserName(object):
    """ Base class for user name tests

    Set user name during tests.
    """
    pagename = u'AutoCreatedMoinMoinTemporaryTestPage'
    variable = u'@USERNAME@'

    @pytest.fixture
    def page(self, req):
        return PageEditor(req, self.pagename)

    @pytest.fixture(autouse=True)
    def set_username(self, req):
        req.user.name = self.name

    # def setup_method(self, method):
    #     self.page = PageEditor(self.request, self.pagename)
    #     self.savedName = self.request.user.name
    #     self.request.user.name = self.name
    #
    # def teardown_method(self, method):
    #     self.request.user.name = self.savedName
    #
    def expand(self, page):
        return page._expand_variables(self.variable)


class TestExpandCamelCaseName(TestExpandUserName):

    name = u'UserName'

    def testExpandCamelCaseUserName(self, req, page):
        """ PageEditor: expand @USERNAME@ CamelCase """
        assert self.expand(page) == self.name


class TestExpandExtendedName(TestExpandUserName):

    name = u'user name'

    def testExtendedNamesEnabled(self, req, page):
        """ PageEditor: expand @USERNAME@ extended name - enabled """
        assert self.expand(page) == u'[[%s]]' % self.name


class TestExpandMailto(TestExpandUserName):

    variable = u'@MAILTO@'
    name = u'user name'
    email = 'user@example.com'

    @pytest.fixture(autouse=True)
    def set_email_valid(self, req):
        req.user.valid = 1
        req.user.email = self.email

    def testMailto(self, req, page):
        """ PageEditor: expand @MAILTO@ """
        assert self.expand(page) == u'<<MailTo(%s)>>' % self.email


class TestExpandPrivateVariables(TestExpandUserName):

    variable = u'@ME@'
    name = u'AutoCreatedMoinMoinTemporaryTestUser'
    dictPage = name + '/MyDict'
    shouldDeleteTestPage = True

    @pytest.fixture(autouse=True)
    def set_valid(self, req):
        req.user.valid = 1

    @pytest.fixture(autouse=True)
    def create_page(self, req):
        self.createTestPage(req)
        yield
        self.deleteTestPage(req)

    def testPrivateVariables(self, page):
        """ PageEditor: expand user variables """
        assert self.expand(page) == self.name

    def createTestPage(self, req):
        """ Create temporary page, bypass logs, notification and backups

        TODO: this code is very fragile, any change in the
        implementation will break this test. Need to factor PageEditor
        to make it possible to create page without loging and notifying.
        """
        import os
        path = self.dictPagePath(req)
        if os.path.exists(path):
            self.shouldDeleteTestPage = False
            pytest.skip("%s exists. Won't overwrite exiting page" % self.dictPage)
        try:
            os.mkdir(path)
            revisionsDir = os.path.join(path, 'revisions')
            os.mkdir(revisionsDir)
            current = '00000001'
            open(os.path.join(path, 'current'), 'w').write('%s\n' % current)
            text = u' ME:: %s\n' % self.name
            open(os.path.join(revisionsDir, current), 'w').write(text)
        except Exception as err:
            pytest.skip("Can not be create test page: %s" % err)


    def deleteTestPage(self, req):
        """ Delete temporary page, bypass logs and notifications """
        if self.shouldDeleteTestPage:
            shutil.rmtree(self.dictPagePath(req), True)

    def dictPagePath(self, req):
        page = Page(req, self.dictPage)
        return page.getPagePath(use_underlay=0, check_create=0)


class TestSave(object):

    @pytest.fixture(autouse=True)
    def setup_method(self, req):
        become_trusted(req)
        yield
        nuke_page(req, u'AutoCreatedMoinMoinTemporaryTestPageFortestSave')

    def testSaveAbort(self, req):
        """Test if saveText() is interrupted if PagePreSave event handler returns Abort"""

        def handler(event):
            from MoinMoin.events import Abort
            return Abort("This is just a test")

        pagename = u'AutoCreatedMoinMoinTemporaryTestPageFortestSave'
        testtext = u'ThisIsSomeStupidTestPageText!'

        req.cfg.event_handlers = [handler]

        page = Page(req, pagename)
        if page.exists():
            deleter = PageEditor(req, pagename)
            deleter.deletePage()

        editor = PageEditor(req, pagename)
        editor.saveText(testtext, 0)

        print("PageEditor can't save a page if Abort is returned from PreSave event handlers")
        page = Page(req, pagename)
        assert page.body != testtext


class TestSaveACLChange(object):

    pagename = u'PageACLTest'
    oldtext = u'''\
## foo
#lang en

foo
'''
    newtext = u'''\
## foo
#acl -All:write Default
#lang en

foo
'''

    @pytest.mark.wiki_config(acl_rights_before='Trusted:read,write,delete,revert', acl_rights_default='All:read,write')
    def test_acls(self, req):
        p = PageEditor(req, self.pagename)
        p.saveText(self.oldtext, 0)
        p = PageEditor(req, self.pagename)
        oldacl = p.getACL(req).acl
        assert not req.user.may.admin(p.page_name)
        newacl = parseACL(req, self.newtext).acl
        assert newacl != oldacl
        pytest.raises(PageEditor.NoAdmin, p.saveText, self.newtext, 0)
        become_trusted(req)
        nuke_page(req, self.pagename)


class TestDictPageDeletion(object):

    def testCreateDictAndDeleteDictPage(self, req):
        """
        simple test if it is possible to delete a Dict page after creation
        """
        become_trusted(req)
        pagename = u'SomeDict'
        page = PageEditor(req, pagename, do_editor_backup=0)
        body = u"This is an example text"
        page.saveText(body, 0)

        success_i, result = page.deletePage()

        expected = u'Page "SomeDict" was successfully deleted!'

        assert result == expected


class TestCopyPage(object):

    pagename = u'AutoCreatedMoinMoinTemporaryTestPage'
    copy_pagename = u'AutoCreatedMoinMoinTemporaryCopyTestPage'

    @pytest.fixture
    def test_page(self, req):
        """ Create temporary page, bypass logs, notification and backups

        TODO: this code is very fragile, any change in the
        implementation will break this test. Need to factor PageEditor
        to make it possible to create page without loging and notifying.
        """
        become_trusted(req)
        should_delete_test_page = True

        def createTestPage(text):
            nonlocal should_delete_test_page
            path = Page(req, self.pagename).getPagePath(check_create=0)
            copy_path = Page(req, self.copy_pagename).getPagePath(check_create=0)

            if os.path.exists(path) or os.path.exists(copy_path):
                should_delete_test_page = False
                pytest.skip("%s or %s exists. Won't overwrite exiting page" % (self.pagename, self.copy_pagename))
            try:
                os.mkdir(path)
                revisionsDir = os.path.join(path, 'revisions')
                os.mkdir(revisionsDir)
                current = '00000001'
                with open(os.path.join(path, 'current'), 'w') as f:
                    f.write('%s\n' % current)

                with open(os.path.join(revisionsDir, current), 'w') as g:
                    g.write(text)
            except Exception as err:
                pytest.skip("Can not be create test page: %s" % err)

        yield createTestPage

        if should_delete_test_page:
            shutil.rmtree(Page(req, self.pagename).getPagePath(), True)
            shutil.rmtree(Page(req, self.copy_pagename).getPagePath(), True)

    def test_copy_page(self, req, test_page):
        """
        Tests copying a page without restricted acls
        """
        text = u'Example'
        test_page(text)
        result, msg = PageEditor(req, self.pagename).copyPage(self.copy_pagename)
        revision = Page(req, self.copy_pagename).current_rev()
        assert result and revision is 2

    def test_copy_page_acl_read(self, req, test_page):
        """
        Tests copying a page without write rights
        """
        text = u'#acl SomeUser:read,write,delete All:read\n'
        test_page(text)
        result, msg = PageEditor(req, self.pagename).copyPage(self.copy_pagename)
        revision = Page(req, self.copy_pagename).current_rev()
        assert result and revision is 2

    def test_copy_page_acl_no_read(self, req, test_page):
        """
        Tests copying a page without read rights
        """
        text = u'#acl SomeUser:read,write,delete All:\n'
        test_page(text)
        result, msg = PageEditor(req, self.pagename).copyPage(self.copy_pagename)
        revision = Page(req, self.copy_pagename).current_rev()
        assert result and revision is 2


coverage_modules = ['MoinMoin.PageEditor']
