"""
    MoinMoin - refresh cache of a page

    @copyright: 2000-2004 Juergen Hermann <jh@web.de>,
                2006 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""
from MoinMoin.Page import Page


def execute(pagename, context):
    """ Handle refresh action """
    # Without arguments, refresh action will refresh the page text_html cache.
    arena = context.request.values.get('arena', 'Page.py')
    if arena == 'Page.py':
        arena = Page(context, pagename)
    key = context.request.values.get('key', 'text_html')

    # Remove cache entry (if exists), and send the page
    from MoinMoin import caching
    caching.CacheEntry(context, arena, key, scope='item').remove()
    caching.CacheEntry(context, arena, "pagelinks", scope='item').remove()
    context.page.send_page()
