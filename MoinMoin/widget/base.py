# -*- coding: iso-8859-1 -*-
"""
    MoinMoin - Widget base class

    @copyright: 2002 Juergen Hermann <jh@web.de>
    @license: GNU GPL, see COPYING for details.
"""

from builtins import object
class Widget(object):

    def __init__(self, request, **kw):
        self.request = request

    def render(self):
        raise NotImplementedError

