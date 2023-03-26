
"""
    MoinMoin - MoinMoin.packages tests

    @copyright: 2005 MoinMoin:AlexanderSchremmer,
                2007 Federico Lorenzi,
                2010 MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""

from builtins import object
import os
import pytest
import tempfile
import zipfile

from datetime import datetime
from MoinMoin import user, wikiutil
from MoinMoin.action import AttachFile
from MoinMoin.action.PackagePages import PackagePages
from MoinMoin.packages import Package, ScriptEngine, MOIN_PACKAGE_FILE, ZipPackage, packLine, unpackLine
from MoinMoin._tests import become_trusted, become_superuser, create_page, nuke_page
from MoinMoin.Page import Page
from MoinMoin.PageEditor import PageEditor



class DebugPackage(Package, ScriptEngine):
    """ Used for debugging, does not need a real .zip file. """

    def __init__(self, request, filename, script=None):
        Package.__init__(self, request)
        ScriptEngine.__init__(self)
        self.filename = filename
        self.script = script or u"""moinmoinpackage|1
print|foo
ReplaceUnderlay|testdatei|TestSeite2
IgnoreExceptions|True
IgnoreExceptions|False
AddRevision|foofile|FooPage
AddRevision|foofile|FooPage
#foobar
"""

    def extract_file(self, filename):
        if filename == MOIN_PACKAGE_FILE:
            return self.script
        else:
            return "Hello world, I am the file " + filename

    def filelist(self):
        return [MOIN_PACKAGE_FILE, "foo"]

    def isPackage(self):
        return True


class TestUnsafePackage(object):
    """ Tests various things in the packages package. Note that this package does
        not care to clean up and needs to run in a test wiki because of that. """

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        if not getattr(req.cfg, 'is_test_wiki', False):
            pytest.skip('This test needs to be run using the test wiki.')
        yield

        nuke_page(req, "FooPage")

    def testBasicPackageThings(self, req):
        become_superuser(req)
        myPackage = DebugPackage(req, 'test')
        myPackage.installPackage()
        assert myPackage.msg == u'foo\nFooPage added \n'
        testseite2 = Page(req, 'TestSeite2')
        assert testseite2.getPageText() == "Hello world, I am the file testdatei"
        assert testseite2.isUnderlayPage()


class TestQuoting(object):

    def testQuoting(self):
        for line in ([':foo', 'is\\', 'ja|', u't|�', u'baAz�'], [], ['', '']):
            assert line == unpackLine(packLine(line))


class TestRealCreation(object):

    def testSearch(self, req):
        package = PackagePages(req.rootpage.page_name, req)
        assert package.searchpackage(req, "title:BadCon") == [u'BadContent']

    def testListCreate(self, req):
        package = PackagePages(req.rootpage.page_name, req)
        temp = tempfile.NamedTemporaryFile(suffix='.zip')
        package.collectpackage(['FrontPage'], temp)
        assert zipfile.is_zipfile(temp.name)

    def testAllCreate(self, req):
        package = PackagePages(req.rootpage.page_name, req)
        temp = tempfile.NamedTemporaryFile(suffix='.zip')
        collected = package.collectpackage(req.rootpage.getPageList(
                                include_underlay=False,
                                filter=lambda name: not wikiutil.isSystemPage(req, name)),
                                temp)
        if collected:
            pytest.skip("No user created pages in wiki!")
        assert zipfile.is_zipfile(temp.name)

    def testInvalidCreate(self, req):
        package = PackagePages(req.rootpage.page_name, req)
        temp = tempfile.NamedTemporaryFile(suffix='.zip')
        package.collectpackage(['___//THIS PAGE SHOULD NOT EXIST\\___'], temp)
        assert not zipfile.is_zipfile(temp.name)


class TestRealPackageInstallation(object):


    def create_package(self, req, script, page=None):
        # creates the package example zip file
        userid = user.getUserIdentification(req)
        COMPRESSION_LEVEL = zipfile.ZIP_DEFLATED
        zip_file = tempfile.mkstemp(suffix='.zip')[1]
        zf = zipfile.ZipFile(zip_file, "w", COMPRESSION_LEVEL)
        if page:
            timestamp = wikiutil.version2timestamp(page.mtime_usecs())
            zi = zipfile.ZipInfo(filename="1", date_time=datetime.fromtimestamp(timestamp).timetuple()[:6])
            zi.compress_type = COMPRESSION_LEVEL
            zf.writestr(zi, page.get_raw_body().encode("utf-8"))
        zf.writestr("1_attachment", "sample attachment")
        zf.writestr(MOIN_PACKAGE_FILE, script.encode("utf-8"))
        zf.close()
        return zip_file

    def testAttachments_after_page_creation(self, req):
        become_trusted(req)
        pagename = u'PackageTestPageCreatedFirst'
        page = create_page(req, pagename, u"This page has not yet an attachments dir")
        script = u"""MoinMoinPackage|1
AddRevision|1|%(pagename)s
AddAttachment|1_attachment|my_test.txt|%(pagename)s
Print|Thank you for using PackagePages!
""" % {"pagename": pagename}
        zip_file = self.create_package(req, script, page)
        package = ZipPackage(req, zip_file)
        package.installPackage()
        assert Page(req, pagename).exists()
        assert AttachFile.exists(req, pagename, "my_test.txt")

        nuke_page(req, pagename)
        os.unlink(zip_file)

    def testAttachments_without_page_creation(self, req):
        become_trusted(req)
        pagename = u"PackageAttachmentAttachWithoutPageCreation"
        script = u"""MoinMoinPackage|1
AddAttachment|1_attachment|my_test.txt|%(pagename)s
Print|Thank you for using PackagePages!
""" % {"pagename": pagename}
        zip_file = self.create_package(req, script)
        package = ZipPackage(req, zip_file)
        package.installPackage()
        assert not Page(req, pagename).exists()
        assert AttachFile.exists(req, pagename, "my_test.txt")

        nuke_page(req, pagename)
        os.unlink(zip_file)


coverage_modules = ['MoinMoin.packages']

