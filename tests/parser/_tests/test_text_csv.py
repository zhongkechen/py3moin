
"""
    MoinMoin - MoinMoin.parser.text_csv Tests

    @copyright: 2008 by MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""




from MoinMoin.Page import Page
from MoinMoin.parser.text_csv import Parser as CSV_Parser
from MoinMoin.formatter.text_html import Formatter as HtmlFormatter

PAGENAME = u'ThisPageDoesNotExistsAndWillNeverBeReally'

class ParserTestCase:
    """ Helper class that provide a parsing method """

    def parse(self, req, body):
        """Parse body and return html

        Create a page with body, then parse it and format using html formatter
        """
        request = req
        assert body is not None
        request.reset()
        page = Page(request, PAGENAME)
        page.hilite_re = None
        page.set_raw_body(body)
        formatter = HtmlFormatter(request)
        formatter.setPage(page)
        page.formatter = formatter
        request.page = page
        request.formatter = formatter
        parser = CSV_Parser(body, request, line_anchors=False)
        formatter.startContent('') # needed for _include_stack init
        output = request.redirectedOutput(parser.format, formatter)
        formatter.endContent('')
        return output

class TestDelimiters(ParserTestCase):

    def testdelimiters(self, req):
        """ parser.text_csv: delimiter , """
        result = self.parse(req, 'a,b')
        assert '<td class="hcolumn0"><strong>a</strong></td>' in  result and '<td class="hcolumn1"><strong>b</strong></td>' in  result

    def testemptyline(self, req):
        """ parser.text_csv: empty line """
        result = self.parse(req, '')
        assert '<tbody><tr></tr>\n</tbody>' in  result

    def testnodelimiter(self, req):
        """ parser.text_csv: line without delimiter """
        result = self.parse(req, 'ABCDEFGHIJ')
        assert '<td class="hcolumn0"><strong>ABCDEFGHIJ</strong></td>' in  result

coverage_modules = ['MoinMoin.parser.text_csv']

