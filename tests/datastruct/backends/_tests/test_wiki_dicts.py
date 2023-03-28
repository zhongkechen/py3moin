
"""
    MoinMoin - MoinMoin.datastruct.backends.wiki_dicts tests

    @copyright: 2003-2004 by Juergen Hermann <jh@web.de>,
                2007 by MoinMoin:ThomasWaldmann
                2009 by MoinMoin:DmitrijsMilajevs
    @license: GNU GPL, see COPYING for details.
"""

from tests.datastruct.backends._tests import DictsBackendTest


class TestWikiDictsBackend(DictsBackendTest):

    # Suppose that default configuration for the dicts is used which
    # is WikiDicts backend.
    pass


coverage_modules = ['MoinMoin.datastruct.backends.wiki_dicts']

