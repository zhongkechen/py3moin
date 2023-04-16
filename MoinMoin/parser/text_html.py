"""
    MoinMoin - HTML Parser

    @copyright: 2006 MoinMoin:AlexanderSchremmer
    @license: GNU GPL, see COPYING for details.
"""

from MoinMoin.support.htmlmarkup import Markup

Dependencies = []


class Parser:
    """
        Sends HTML code after filtering it.
    """

    extensions = ['.htm', '.html']
    Dependencies = Dependencies

    def __init__(self, raw, request, **kw):
        self.raw = raw
        self.request = request

    def format(self, formatter, **kw):
        """ Send the text. """
        try:
            self.request.write(formatter.rawHTML(Markup(self.raw).sanitize()))
        except Exception as e:
            self.request.write(formatter.sysmsg(1) + formatter.text(u'HTML parsing error: %s in "%s"' % (e.msg, self.raw.splitlines()[e.lineno - 1].strip())) + formatter.sysmsg(0))
