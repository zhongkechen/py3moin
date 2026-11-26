"""
    MoinMoin - "links" action

    Generate a link database like MeatBall:LinkDatabase.

    @copyright: 2001 Juergen Hermann <jh@web.de>
    @license: GNU GPL, see COPYING for details.
"""
from MoinMoin import wikiutil


def execute(pagename, request):
    _ = request.getText
    # get the MIME type
    html_output = request.request.values.get('mimetype', 'text/html') == 'text/html'
    request.response.mimetype = 'text/html' if html_output else 'text/plain'

    if html_output:
        request.theme.send_title(_('Full Link List for "%s"') % request.cfg.sitename)
        request.write('<pre>')

    # Get page dict readable by current user
    pages = request.rootpage.getPageDict()
    pagelist = list(pages.keys())
    pagelist.sort()

    for name in pagelist:
        if html_output:
            request.write(pages[name].link_to(request))
        else:
            _emit(request, name)
        for link in pages[name].getPageLinks(request):
            request.write(" ")
            if html_output:
                if link in pages:
                    request.write(pages[link].link_to(request))
                else:
                    _emit(request, link)
            else:
                _emit(request, link)
        request.write('\n')

    if html_output:
        request.write('</pre>')
        request.theme.send_footer(pagename)
        request.theme.send_closing_html()


def _emit(request, pagename):
    """ Send pagename, encode it if it contains spaces
    """
    request.write(wikiutil.quoteWikinameURL(pagename))
