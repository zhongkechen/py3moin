# -*- coding: utf-8 -*-
"""
    MoinMoin - MoinMoin.user Tests

    @copyright: 2003-2004 by Juergen Hermann <jh@web.de>
                2009 by ReimarBauer
                2013 by MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

import os
import pytest

from MoinMoin import user, caching


class TestEncodePassword:
    """user: encode passwords tests"""

    def testAscii(self, req):
        """user: encode ascii password"""
        # u'MoinMoin' and 'MoinMoin' should be encoded to same result
        cfg = req.cfg
        tests = [
            ('{PASSLIB}', b'12345', "{PASSLIB}$6$rounds=1001$12345$jrPUCzPJt1yiixDbzIgSBoKED0/DlNDTHZN3lVarCtN6IM/.LoAw5pgUQH112CErU6wS8HXTZNpqb7wVjHLs/0"),
            ('{SSHA}', b'12345', "{SSHA}xkDIIx1I7A4gC98Vt/+UelIkTDYxMjM0NQ=="),
        ]
        for scheme, salt, expected in tests:
            result = user.encodePassword(cfg, "MoinMoin", salt=salt, scheme=scheme)
            assert result == expected
            result = user.encodePassword(cfg, u"MoinMoin", salt=salt, scheme=scheme)
            assert result == expected

    def testUnicode(self, req):
        """ user: encode unicode password """
        cfg = req.cfg
        tests = [
            ('{PASSLIB}', '12345', "{PASSLIB}$6$rounds=1001$12345$5srFB66ZCu2JgGwPgdfb1lHRmqkjnKC/RxdsFlWn2WzoQh3btIjH6Ai1LJV9iYLDa9kLP/VQYa4DHLkRnaBw8."),
            ('{SSHA}', '12345', "{SSHA}YiwfeVWdVW9luqyVn8t2JivlzmUxMjM0NQ=="),
            ]
        for scheme, salt, expected in tests:
            result = user.encodePassword(cfg, u'סיסמה סודית בהחלט', salt=salt, scheme=scheme) # Hebrew
            assert result == expected


class TestLoginWithPassword:
    """user: login tests"""

    @pytest.fixture(autouse=True)
    def setup_method(self, req):
        # Create anon user for the tests
        req.cookies = {}
        req.user = user.User(req)

        self.user = None
        self.passlib_support = req.cfg.passlib_support
        self.password_scheme = req.cfg.password_scheme

        yield

        # Remove user file and user
        if self.user is not None:
            try:
                path = self.user._User__filename()
                os.remove(path)
            except OSError:
                pass
            del self.user

        # Remove user lookup caches, or next test will fail
        user.clearLookupCaches(req)

    def testAsciiPassword(self, req):
        """ user: login with ascii password """
        # Create test user
        name = u'__Non Existent User Name__'
        password = name
        self.createUser(req, name, password)

        # Try to "login"
        theUser = user.User(req, name=name, password=password)
        assert theUser.valid

    def testUnicodePassword(self, req):
        """ user: login with non-ascii password """
        # Create test user
        name = u'__שם משתמש לא קיים__' # Hebrew
        password = name
        self.createUser(req, name, password)

        # Try to "login"
        theUser = user.User(req, name=name, password=password)
        assert theUser.valid

    def test_auth_with_apr1_stored_password(self, req):
        """
        Create user with {APR1} password and check that user can login.
        Also check if auto-upgrade happens and is saved to disk.
        """
        # Create test user
        name = u'Test User'
        password = '12345'
        # generated with "htpasswd -nbm blaze 12345"
        pw_hash = '{APR1}$apr1$NG3VoiU5$PSpHT6tV0ZMKkSZ71E3qg.'
        self.createUser(req, name, pw_hash, True)

        # Try to "login"
        theuser = user.User(req, name=name, password=password)
        assert theuser.valid
        # Check if the stored password was auto-upgraded on login and saved
        theuser = user.User(req, name=name, password=password)
        assert theuser.enc_password.startswith(self.password_scheme)

    def test_auth_with_md5_stored_password(self, req):
        """
        Create user with {MD5} password and check that user can login.
        Also check if auto-upgrade happens and is saved to disk.
        """
        # Create test user
        name = u'Test User'
        password = '12345'
        pw_hash = '{MD5}$1$salt$etVYf53ma13QCiRbQOuRk/'
        self.createUser(req, name, pw_hash, True)

        # Try to "login"
        theuser = user.User(req, name=name, password=password)
        assert theuser.valid
        # Check if the stored password was auto-upgraded on login and saved
        theuser = user.User(req, name=name, password=password)
        assert theuser.enc_password.startswith(self.password_scheme)

    def test_auth_with_des_stored_password(self, req):
        """
        Create user with {DES} password and check that user can login.
        Also check if auto-upgrade happens and is saved to disk.
        """
        # Create test user
        name = u'Test User'
        password = '12345'
        # generated with "htpasswd -nbd blaze 12345"
        pw_hash = '{DES}gArsfn7O5Yqfo'
        self.createUser(req, name, pw_hash, True)

        try:
            import crypt
            # Try to "login"
            theuser = user.User(req, name=name, password=password)
            assert theuser.valid
            # Check if the stored password was auto-upgraded on login and saved
            theuser = user.User(req, name=name, password=password)
            assert theuser.enc_password.startswith(self.password_scheme)
        except ImportError:
            pytest.skip("Platform does not provide crypt module!")

    def test_auth_with_sha_stored_password(self, req):
        """
        Create user with {SHA} password and check that user can login.
        Also check if auto-upgrade happens and is saved to disk.
        """
        # Create test user
        name = u'Test User'
        password = '12345'
        pw_hash = '{SHA}jLIjfQZ5yojbZGTqxg2pY0VROWQ='
        self.createUser(req, name, pw_hash, True)

        # Try to "login"
        theuser = user.User(req, name=name, password=password)
        assert theuser.valid
        # Check if the stored password was auto-upgraded on login and saved
        theuser = user.User(req, name=name, password=password)
        assert theuser.enc_password.startswith(self.password_scheme)

    def test_auth_with_ssha_stored_password(self, req):
        """
        Create user with {SSHA} password and check that user can login.
        Also check if auto-upgrade happens and is saved to disk.
        """
        # Create test user
        name = u'Test User'
        password = '12345'
        pw_hash = '{SSHA}dbeFtH5EGkOI1jgPADlGZgHWq072TIsKqWfHX7zZbUQa85Ze8774Rg=='
        self.createUser(req, name, pw_hash, True)

        # Try to "login"
        theuser = user.User(req, name=name, password=password)
        assert theuser.valid
        # Check if the stored password was auto-upgraded on login and saved
        theuser = user.User(req, name=name, password=password)
        assert theuser.enc_password.startswith(self.password_scheme)

    def test_auth_with_passlib_stored_password(self, req):
        """
        Create user with {PASSLIB} password and check that user can login.
        """
        if not self.passlib_support:
            pytest.skip("test requires passlib, but passlib_support is False")
        # Create test user
        name = u'Test User'
        password = '12345'
        pw_hash = '{PASSLIB}$6$rounds=1001$/AVWSh/RUWpcppfl$8DCRGLaBD3KoV4Ag67sUv6b2QdrUFXk1yWCxqWnBLJ.iHSe4Piv6nqzSQgELeLPIvwTC9APaWv1XCTOHjkLOj/'
        self.createUser(req, name, pw_hash, True)

        # Try to "login"
        theuser = user.User(req, name=name, password=password)
        assert theuser.valid
        # Check if the stored password was auto-upgraded on login and saved
        theuser = user.User(req, name=name, password=password)
        assert theuser.enc_password.startswith(self.password_scheme)

    def testSubscriptionSubscribedPage(self, req):
        """ user: tests isSubscribedTo  """
        pagename = u'HelpMiscellaneous'
        name = u'__Jürgen Herman__'
        password = name
        self.createUser(req, name, password)
        # Login - this should replace the old password in the user file
        theUser = user.User(req, name=name, password=password)
        theUser.subscribe(pagename)
        assert theUser.isSubscribedTo([pagename]) # list(!) of pages to check

    def testSubscriptionSubPage(self, req):
        """ user: tests isSubscribedTo on a subpage """
        pagename = u'HelpMiscellaneous'
        testPagename = u'HelpMiscellaneous/FrequentlyAskedQuestions'
        name = u'__Jürgen Herman__'
        password = name
        self.createUser(req, name, password)
        # Login - this should replace the old password in the user file
        theUser = user.User(req, name=name, password=password)
        theUser.subscribe(pagename)
        assert not theUser.isSubscribedTo([testPagename]) # list(!) of pages to check

    def testRenameUser(self, req):
        """ create user and then rename user and check whether
        the old username is removed (and the lookup cache behaves well)
        """
        # Create test user
        name = u'__Some Name__'
        password = name
        self.createUser(req, name, password)
        # Login - this should replace the old password in the user file
        theUser = user.User(req, name=name)
        # Rename user
        theUser.name = u'__SomeName__'
        theUser.save()
        theUser = user.User(req, name=name, password=password)

        assert not theUser.exists()

    def test_for_email_attribute_by_name(self, req):
        """
        checks for no access to the email attribute by getting the user object from name
        """
        name = u"__TestUser__"
        password = u"ekfdweurwerh"
        email = "__TestUser__@moinhost"
        self.createUser(req, name, password, email=email)
        theuser = user.User(req, name=name)
        assert theuser.email == ""

    def test_for_email_attribut_by_uid(self, req):
        """
        checks access to the email attribute by getting the user object from the uid
        """
        name = u"__TestUser2__"
        password = u"ekERErwerwerh"
        email = "__TestUser2__@moinhost"
        self.createUser(req, name, password, email=email)
        uid = user.getUserId(req, name)
        theuser = user.User(req, uid)
        assert theuser.email == email

    # Helpers ---------------------------------------------------------

    def createUser(self, req, name, password, pwencoded=False, email=None):
        """ helper to create test user
        """
        # Create user
        self.user = user.User(req)
        self.user.name = name
        self.user.email = email
        if not pwencoded:
            password = user.encodePassword(req.cfg, password)
        self.user.enc_password = password

        # Validate that we are not modifying existing user data file!
        if self.user.exists():
            self.user = None
            pytest.skip("Test user exists, will not override existing user data file!")

        # Save test user
        self.user.save()

        # Validate user creation
        if not self.user.exists():
            self.user = None
            pytest.skip("Can't create test user")


class TestGroupName:

    def testGroupNames(self, req):
        """ user: isValidName: reject group names """
        test = u'AdminGroup'
        assert not user.isValidName(req, test)


class TestIsValidName:

    def testNonAlnumCharacters(self, req):
        """ user: isValidName: reject unicode non alpha numeric characters

        : and , used in acl rules, we might add more characters to the syntax.
        """
        invalid = u'! # $ % ^ & * ( ) = + , : ; " | ~ / \\ \u0000 \u202a'.split()
        base = u'User%sName'
        for c in invalid:
            name = base % c
            assert not user.isValidName(req, name)

    def testWhitespace(self, req):
        """ user: isValidName: reject leading, trailing or multiple whitespace """
        cases = (
            u' User Name',
            u'User Name ',
            u'User   Name',
            )
        for test in cases:
            assert not user.isValidName(req, test)

    def testValid(self, req):
        """ user: isValidName: accept names in any language, with spaces """
        cases = (
            u'Jürgen Hermann', # German
            u'ניר סופר', # Hebrew
            u'CamelCase', # Good old camel case
            u'가각간갇갈 갉갊감 갬갯걀갼' # Hangul (gibberish)
            )
        for test in cases:
            assert user.isValidName(req, test)


coverage_modules = ['MoinMoin.user']

