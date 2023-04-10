# -*- coding: utf-8 -*-
"""
    MoinMoin - MoinMoin.macro.EmbedObject Tests

    @copyright: 2008 MoinMoin:ReimarBauer,
                2008 MoinMoin:JohannesBerg
    @license: GNU GPL, see COPYING for details.
"""
import pytest

from MoinMoin.action import AttachFile

from tests._tests import become_trusted, create_page, make_macro, nuke_page

class TestEmbedObject(object):
    """ testing macro Action calling action raw """
    pagename = u'AutoCreatedMoinMoinTemporaryTestPageForEmbedObject'

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        request = req
        pagename = self.pagename
        become_trusted(request)
        self.page = create_page(request, pagename, u"Foo")
        AttachFile.getAttachDir(request, pagename)
        test_files = [
            ('test.ogg', b'vorbis'),
            ('test.svg', b'SVG'),
            ('test.mpg', b'MPG'),
            ('test.pdf', b'PDF'),
            ('test.mp3', b'MP3'),
        ]
        for filename, filecontent in test_files:
            AttachFile.add_attachment(request, pagename, filename, filecontent, overwrite=0)

        yield
        nuke_page(req, self.pagename)

    def testEmbedObjectMimetype(self, req):
        """ tests defined mimetyes """
        tests = [
            (u'test.pdf', 'application/pdf'),
            (u'test.svg', 'image/svg+xml'),
            (u'test.mpg', 'video/mpeg'),
            (u'test.mp3', 'audio/mpeg'),
        ]
        for filename, mimetype in tests:
            m = make_macro(req, self.page)
            result = m.execute('EmbedObject', filename)
            assert mimetype in result

    def testEmbedObjectDefaultValues(self, req):
        """ tests default values of macro EmbedObject """
        m = make_macro(req, self.page)
        filename = 'test.mpg'
        result = m.execute('EmbedObject', u'%s' % filename)
        assert '<object data="/AutoCreatedMoinMoinTemporaryTestPageForEmbedObject?action=AttachFile&amp;do=get&amp;target=test.mpg"' in result
        assert 'align="middle"' in result
        assert 'value="transparent"' in result

    def testEmbedObjectPercentHeight(self, req):
        """ tests a unit value for macro EmbedObject """
        m = make_macro(req, self.page)
        filename = 'test.mpg'
        height = '50 %' # also tests that space is allowed in there
        result = m.execute('EmbedObject', u'target=%s, height=%s' % (filename, height))
        assert '<object data="/AutoCreatedMoinMoinTemporaryTestPageForEmbedObject?action=AttachFile&amp;do=get&amp;target=test.mpg"' in result
        assert 'height="50%"' in result
        assert 'align="middle"' in result

    def testEmbedObjectFromUrl(self, req):
        """ tests using a URL for macro EmbedObject """
        m = make_macro(req, self.page)
        target = 'http://localhost/%s?action=AttachFile&do=view&target=test.mpg' % self.pagename
        result = m.execute('EmbedObject', u'target=%s, url_mimetype=video/mpeg' % target)
        assert '<object data="http://localhost/AutoCreatedMoinMoinTemporaryTestPageForEmbedObject?action=AttachFile&amp;do=view&amp;target=test.mpg" type="video/mpeg"' in result

coverage_modules = ['MoinMoin.macro.EmbedObject']
