
"""
    MoinMoin - tests for MoinMoin.filter module

    @copyright: 2007 by MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

import io
import zipfile


class TestFilters:

    def make_file(self, data):
        import tempfile
        fname = tempfile.mktemp()
        f = open(fname, 'wb')
        f.write(data)
        f.close()
        return fname

    def testBinaryGeneric(self):
        from MoinMoin.filter.application_octet_stream import execute as _filter
        tests = [(b'', b''),
                 (b'this\x00is\x00a\x00test\x00', b'this test'),  # throws away short stuff
                ]
        for data, expected in tests:
            fname = self.make_file(data)
            assert _filter(None, fname) == expected

    def testTextGeneric(self):
        from MoinMoin.filter.text import execute as _filter
        tests = [(b'', ''),
                 (b'asdf\r\nghjk', 'asdf\r\nghjk'),
                 # add some tests with umlauts in diff. encodings
                ]
        for data, expected in tests:
            fname = self.make_file(data)
            assert _filter(None, fname) == expected

    def testTextHtml(self):
        from MoinMoin.filter.text_html import execute as _filter
        tests = [(b'', ''),
                 (b'<html><body>Hello<br>World!</body></html>', u'Hello World!'),
                ]
        for data, expected in tests:
            fname = self.make_file(data)
            assert _filter(None, fname) == expected

    def testTextXml(self):
        from MoinMoin.filter.text_xml import execute as _filter
        tests = [(b'', ''),
                 (b'<xml><para>Hello</para><para>World!</para></xml>', u'Hello World!'),
                ]
        for data, expected in tests:
            fname = self.make_file(data)
            assert _filter(None, fname) == expected

    def testOpenDocument(self):
        from MoinMoin.filter.application_vnd_oasis_opendocument import execute as _filter

        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('content.xml', '<doc>Hello <b>Wörld</b></doc>'.encode('utf-8'))

        fname = self.make_file(output.getvalue())
        assert _filter(None, fname) == 'Hello Wörld'

coverage_modules = ['MoinMoin.filter.text',
                    'MoinMoin.filter.text_html',
                    'MoinMoin.filter.text_xml',
                    'MoinMoin.filter.application_octet_stream',
                    'MoinMoin.filter.application_vnd_oasis_opendocument',
                   ]
