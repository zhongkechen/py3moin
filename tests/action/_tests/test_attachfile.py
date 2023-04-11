
"""
    MoinMoin - tests of AttachFile action

    @copyright: 2007 by Karol Nowak <grywacz@gmail.com>
                2007-2008 MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""


import os, io
from MoinMoin.action import AttachFile
from tests._tests import become_trusted, create_page, nuke_page

class TestAttachFile(object):
    """ testing action AttachFile"""
    pagename = u"AutoCreatedSillyPageToTestAttachments"

    def test_add_attachment(self, req):
        """Test if add_attachment() works"""

        become_trusted(req)
        filename = "AutoCreatedSillyAttachment"

        create_page(req, self.pagename, u"Foo!")

        AttachFile.add_attachment(req, self.pagename, filename, b"Test content", True)
        exists = AttachFile.exists(req, self.pagename, filename)

        nuke_page(req, self.pagename)

        assert exists

    def test_add_attachment_for_file_object(self, req):
        """Test if add_attachment() works with file like object"""

        become_trusted(req)

        filename = "AutoCreatedSillyAttachment.png"

        create_page(req, self.pagename, u"FooBar!")
        data = b"Test content"

        filecontent = io.BytesIO(data)

        AttachFile.add_attachment(req, self.pagename, filename, filecontent, True)
        exists = AttachFile.exists(req, self.pagename, filename)
        path = AttachFile.getAttachDir(req, self.pagename)
        imagef = os.path.join(path, filename)
        file_size = os.path.getsize(imagef)

        nuke_page(req, self.pagename)

        assert exists and file_size == len(data)

    def test_get_attachment_path_created_on_getFilename(self, req):
        """
        Tests if AttachFile.getFilename creates the attachment dir on reqing
        """
        become_trusted(req)

        filename = ""

        file_exists = os.path.exists(AttachFile.getFilename(req, self.pagename, filename))

        nuke_page(req, self.pagename)

        assert file_exists

coverage_modules = ['MoinMoin.action.AttachFile']
