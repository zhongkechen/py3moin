
"""
    MoinMoin - MoinMoin.security Tests

    TODO: when refactoring this, do not use "iter" (is a builtin)

    @copyright: 2003-2004 by Juergen Hermann <jh@web.de>,
                2007 by MoinMoin:ReimarBauer,
                2007 by MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""
from __future__ import print_function

from builtins import next
from builtins import object
import pytest

from MoinMoin import security
acliter = security.ACLStringIterator
AccessControlList = security.AccessControlList

from MoinMoin.datastruct import ConfigGroups
from MoinMoin.PageEditor import PageEditor
from MoinMoin.user import User

from MoinMoin._tests import wikiconfig, become_trusted, create_page, nuke_page

class TestACLStringIterator(object):

    def testEmpty(self, req):
        """ security: empty acl string raise StopIteration """
        iter = acliter(req.cfg.acl_rights_valid, '')
        pytest.raises(StopIteration, iter.__next__)

    def testWhiteSpace(self, req):
        """ security: white space acl string raise StopIteration """
        iter = acliter(req.cfg.acl_rights_valid, '       ')
        pytest.raises(StopIteration, iter.__next__)

    def testDefault(self, req):
        """ security: default meta acl """
        iter = acliter(req.cfg.acl_rights_valid, 'Default Default')
        for mod, entries, rights in iter:
            assert entries == ['Default']
            assert rights == []

    def testEmptyRights(self, req):
        """ security: empty rights """
        iter = acliter(req.cfg.acl_rights_valid, 'WikiName:')
        mod, entries, rights = next(iter)
        assert entries == ['WikiName']
        assert rights == []

    def testSingleWikiNameSingleWrite(self, req):
        """ security: single wiki name, single right """
        iter = acliter(req.cfg.acl_rights_valid, 'WikiName:read')
        mod, entries, rights = next(iter)
        assert entries == ['WikiName']
        assert rights == ['read']

    def testMultipleWikiNameAndRights(self, req):
        """ security: multiple wiki names and rights """
        iter = acliter(req.cfg.acl_rights_valid, 'UserOne,UserTwo:read,write')
        mod, entries, rights = next(iter)
        assert entries == ['UserOne', 'UserTwo']
        assert rights == ['read', 'write']

    def testMultipleWikiNameAndRightsSpaces(self, req):
        """ security: multiple names with spaces """
        iter = acliter(req.cfg.acl_rights_valid, 'user one,user two:read')
        mod, entries, rights = next(iter)
        assert entries == ['user one', 'user two']
        assert rights == ['read']

    def testMultipleEntries(self, req):
        """ security: multiple entries """
        iter = acliter(req.cfg.acl_rights_valid, 'UserOne:read,write UserTwo:read All:')
        mod, entries, rights = next(iter)
        assert entries == ['UserOne']
        assert rights == ['read', 'write']
        mod, entries, rights = next(iter)
        assert entries == ['UserTwo']
        assert rights == ['read']
        mod, entries, rights = next(iter)
        assert entries == ['All']
        assert rights == []

    def testNameWithSpaces(self, req):
        """ security: single name with spaces """
        iter = acliter(req.cfg.acl_rights_valid, 'user one:read')
        mod, entries, rights = next(iter)
        assert entries == ['user one']
        assert rights == ['read']

    def testMultipleEntriesWithSpaces(self, req):
        """ security: multiple entries with spaces """
        iter = acliter(req.cfg.acl_rights_valid, 'user one:read,write user two:read')
        mod, entries, rights = next(iter)
        assert entries == ['user one']
        assert rights == ['read', 'write']
        mod, entries, rights = next(iter)
        assert entries == ['user two']
        assert rights == ['read']

    def testMixedNames(self, req):
        """ security: mixed wiki names and names with spaces """
        iter = acliter(req.cfg.acl_rights_valid, 'UserOne,user two:read,write user three,UserFour:read')
        mod, entries, rights = next(iter)
        assert entries == ['UserOne', 'user two']
        assert rights == ['read', 'write']
        mod, entries, rights = next(iter)
        assert entries == ['user three', 'UserFour']
        assert rights == ['read']

    def testModifier(self, req):
        """ security: acl modifiers """
        iter = acliter(req.cfg.acl_rights_valid, '+UserOne:read -UserTwo:')
        mod, entries, rights = next(iter)
        assert mod == '+'
        assert entries == ['UserOne']
        assert rights == ['read']
        mod, entries, rights = next(iter)
        assert mod == '-'
        assert entries == ['UserTwo']
        assert rights == []

    def testIgnoreInvalidACL(self, req):
        """ security: ignore invalid acl

        The last part of this acl can not be parsed. If it ends with :
        then it will be parsed as one name with spaces.
        """
        iter = acliter(req.cfg.acl_rights_valid, 'UserOne:read user two is ignored')
        mod, entries, rights = next(iter)
        assert entries == ['UserOne']
        assert rights == ['read']
        pytest.raises(StopIteration, iter.__next__)

    def testEmptyNamesWithRight(self, req):
        """ security: empty names with rights

        The documents does not talk about this case, may() should ignore
        the rights because there is no entry.
        """
        iter = acliter(req.cfg.acl_rights_valid, 'UserOne:read :read All:')
        mod, entries, rights = next(iter)
        assert entries == ['UserOne']
        assert rights == ['read']
        mod, entries, rights = next(iter)
        assert entries == []
        assert rights == ['read']
        mod, entries, rights = next(iter)
        assert entries == ['All']
        assert rights == []

    def testIgnodeInvalidRights(self, req):
        """ security: ignore rights not in acl_rights_valid """
        iter = acliter(req.cfg.acl_rights_valid, 'UserOne:read,sing,write,drink,sleep')
        mod, entries, rights = next(iter)
        assert rights == ['read', 'write']

    def testBadGuy(self, req):
        """ security: bad guy may not allowed anything

        This test was failing on the apply acl rights test.
        """
        iter = acliter(req.cfg.acl_rights_valid, 'UserOne:read,write BadGuy: All:read')
        mod, entries, rights = next(iter)
        mod, entries, rights = next(iter)
        assert entries == ['BadGuy']
        assert rights == []

    def testAllowExtraWhitespace(self, req):
        """ security: allow extra white space between entries """
        iter = acliter(req.cfg.acl_rights_valid, 'UserOne,user two:read,write   user three,UserFour:read  All:')
        mod, entries, rights = next(iter)
        assert  entries == ['UserOne', 'user two']
        assert rights == ['read', 'write']
        mod, entries, rights = next(iter)
        assert entries == ['user three', 'UserFour']
        assert rights == ['read']
        mod, entries, rights = next(iter)
        assert entries == ['All']
        assert rights == []


class TestAcl(object):
    """ security: testing access control list

    TO DO: test unknown user?
    """

    def testApplyACLByUser(self, req):
        """ security: applying acl by user name"""
        # This acl string...
        acl_rights = [
            "-MinusGuy:read "
            "+MinusGuy:read "
            "+PlusGuy:read "
            "-PlusGuy:read "
            "Admin1,Admin2:read,write,delete,revert,admin  "
            "Admin3:read,write,admin  "
            "JoeDoe:read,write  "
            "name with spaces,another one:read,write  "
            "CamelCase,extended name:read,write  "
            "BadGuy:  "
            "All:read  "
            ]
        acl = security.AccessControlList(req.cfg, acl_rights)

        # Should apply these rights:
        users = (
            # user,                 rights
            # CamelCase names
            ('Admin1', ('read', 'write', 'admin', 'revert', 'delete')),
            ('Admin2', ('read', 'write', 'admin', 'revert', 'delete')),
            ('Admin3', ('read', 'write', 'admin')),
            ('JoeDoe', ('read', 'write')),
            ('SomeGuy', ('read', )),
            # Extended names or mix of extended and CamelCase
            ('name with spaces', ('read', 'write', )),
            ('another one', ('read', 'write', )),
            ('CamelCase', ('read', 'write', )),
            ('extended name', ('read', 'write', )),
            # Blocking bad guys
            ('BadGuy', ()),
            # All other users - every one not mentioned in the acl lines
            ('All', ('read', )),
            ('Anonymous', ('read', )),
            # we check whether ACL processing stops for a user/right match
            # with ACL modifiers
            ('MinusGuy', ()),
            ('PlusGuy', ('read', )),
            )

        # Check rights
        for user, may in users:
            mayNot = [right for right in req.cfg.acl_rights_valid
                      if right not in may]
            # User should have these rights...
            for right in may:
                assert acl.may(req, user, right)
            # But NOT these:
            for right in mayNot:
                assert not acl.may(req, user, right)

groups = {
    u'PGroup': frozenset([u'Antony', u'Beatrice', ]),
    u'AGroup': frozenset([u'All', ]),
    # note: the next line is a INTENDED misnomer, there is "All" in
    # the group NAME, but not in the group members. This makes
    # sure that a bug that erroneously checked "in groupname" (instead
    # of "in groupmembers") does not reappear.
    u'AllGroup': frozenset([]), # note: intended misnomer
}

class TestGroupACL(object):

    @pytest.mark.wiki_config(groups=lambda s, r: ConfigGroups(r, groups))
    def testApplyACLByGroup(self, req):
        """ security: applying acl by group name"""
        # This acl string...
        acl_rights = [
            "PGroup,AllGroup:read,write,admin "
            "AGroup:read "
            ]
        acl = security.AccessControlList(req.cfg, acl_rights)

        # Should apply these rights:
        users = (
            # user, rights
            ('Antony', ('read', 'write', 'admin', )),  # in PGroup
            ('Beatrice', ('read', 'write', 'admin', )),  # in PGroup
            ('Charles', ('read', )),  # virtually in AGroup
            )

        # Check rights
        for user, may in users:
            mayNot = [right for right in req.cfg.acl_rights_valid
                      if right not in may]
            # User should have these rights...
            for right in may:
                assert acl.may(req, user, right)
            # But NOT these:
            for right in mayNot:
                assert not acl.may(req, user, right)


class TestPageAcls(object):
    """ security: real-life access control list on pages testing
    """
    mainpage_name = u'AclTestMainPage'
    subpage_name = u'AclTestMainPage/SubPage'
    item_rwforall = u'EveryoneMayReadWriteMe'
    subitem_4boss = u'EveryoneMayReadWriteMe/OnlyTheBossMayWMe'
    pages = [
        # pagename, content
        (mainpage_name, u"#acl JoeDoe:\n#acl JaneDoe:read,write\nFoo!"),
        (subpage_name, u"FooFoo!"),
        (item_rwforall, u"#acl All:read,write\nMay be read from and written to by anyone"),
        (subitem_4boss, u"#acl JoeDoe:read,write\nOnly JoeDoe (the boss) may write"),
    ]

    from MoinMoin._tests import wikiconfig
    class Config(wikiconfig.Config):
        acl_rights_before = u"WikiAdmin:admin,read,write,delete,revert"
        acl_rights_default = u"All:read,write"
        acl_rights_after = u"All:read"
        acl_hierarchic = False

    def setup_class(self, req):
        # Backup user
        self.savedUser = req.user.name
        req.user = User(req, auth_username=u'WikiAdmin')
        req.user.valid = True

        for page_name, page_content in self.pages:
            create_page(req, page_name, page_content)

    def teardown_class(self, req):
        # Restore user
        req.user.name = self.savedUser

        for page_name, dummy in self.pages:
            nuke_page(req, page_name)

    def testPageACLs(self, req):
        """ security: test page acls """
        tests = [
            # hierarchic, pagename, username, expected_rights
            (False, self.mainpage_name, u'WikiAdmin', ['read', 'write', 'admin', 'revert', 'delete']),
            (True,  self.mainpage_name, u'WikiAdmin', ['read', 'write', 'admin', 'revert', 'delete']),
            (False, self.mainpage_name, u'AnyUser', ['read']), # by after acl
            (True,  self.mainpage_name, u'AnyUser', ['read']), # by after acl
            (False, self.mainpage_name, u'JaneDoe', ['read', 'write']), # by page acl
            (True,  self.mainpage_name, u'JaneDoe', ['read', 'write']), # by page acl
            (False, self.mainpage_name, u'JoeDoe', []), # by page acl
            (True,  self.mainpage_name, u'JoeDoe', []), # by page acl
            (False, self.subpage_name, u'WikiAdmin', ['read', 'write', 'admin', 'revert', 'delete']),
            (True,  self.subpage_name, u'WikiAdmin', ['read', 'write', 'admin', 'revert', 'delete']),
            (False, self.subpage_name, u'AnyUser', ['read', 'write']), # by default acl
            (True,  self.subpage_name, u'AnyUser', ['read']), # by after acl
            (False, self.subpage_name, u'JoeDoe', ['read', 'write']), # by default acl
            (True,  self.subpage_name, u'JoeDoe', []), # by inherited acl from main page
            (False, self.subpage_name, u'JaneDoe', ['read', 'write']), # by default acl
            (True,  self.subpage_name, u'JaneDoe', ['read', 'write']), # by inherited acl from main page
            (True,  self.subitem_4boss, u'AnyUser', ['read']), # by after acl
            (True,  self.subitem_4boss, u'JoeDoe', ['read', 'write']), # by item acl
        ]

        for hierarchic, pagename, username, may in tests:
            u = User(req, auth_username=username)
            u.valid = True

            def _have_right(u, right, pagename, hierarchic):
                req.cfg.acl_hierarchic = hierarchic
                can_access = u.may.__getattr__(right)(pagename)
                if can_access:
                    print("page %s: %s test if %s may %s (success)" % (
                        pagename, ['normal', 'hierarchic'][hierarchic], username, right))
                else:
                    print("page %s: %s test if %s may %s (failure)" % (
                        pagename, ['normal', 'hierarchic'][hierarchic], username, right))
                assert can_access

            # User should have these rights...
            for right in may:
                yield _have_right, u, right, pagename, hierarchic

            def _not_have_right(u, right, pagename, hierarchic):
                req.cfg.acl_hierarchic = hierarchic
                can_access = u.may.__getattr__(right)(pagename)
                if can_access:
                    print("page %s: %s test if %s may not %s (failure)" % (
                        pagename, ['normal', 'hierarchic'][hierarchic], username, right))
                else:
                    print("page %s: %s test if %s may not %s (success)" % (
                        pagename, ['normal', 'hierarchic'][hierarchic], username, right))
                assert not can_access

            # User should NOT have these rights:
            mayNot = [right for right in req.cfg.acl_rights_valid
                      if right not in may]
            for right in mayNot:
                yield _not_have_right, u, right, pagename, hierarchic

coverage_modules = ['MoinMoin.security']
