
"""
    MoinMoin - set or delete bookmarks (in time) for RecentChanges

    @copyright: 2000-2004 by Juergen Hermann <jh@web.de>,
                2006 by MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""
import time

from MoinMoin import wikiutil
from MoinMoin.Page import Page


def execute(pagename, context):
    """ set bookmarks (in time) for RecentChanges or delete them """
    _ = context.getText
    if not context.user.valid:
        actname = __name__.split('.')[-1]
        context.theme.add_msg(_("You must login to use this action: %(action)s.") % {"action": actname}, "error")
        return Page(context, pagename).send_page()

    timestamp = context.request.values.get('time')
    if timestamp is not None:
        if timestamp == 'del':
            tm = None
        else:
            try:
                tm = int(timestamp)
            except Exception:
                tm = wikiutil.timestamp2version(time.time())
    else:
        tm = wikiutil.timestamp2version(time.time())

    if tm is None:
        context.user.delBookmark()
    else:
        context.user.setBookmark(tm)
    context.page.send_page()
