# -*- coding: iso-8859-1 -*-
"""
    MoinMoin - C/C++ Source Parser

    DEPRECATED compatibility wrapper calling the highlight parser.

    This is to support (deprecated) existing syntax like:
    {{{#!cplusplus ...
    ...
    }}}

    It is equivalent to the new way to highlight code:
    {{{#!highlight cpp ...
    ...
    }}}

    @copyright: 2008 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

from MoinMoin.parser.highlight import Parser as HighlightParser
from MoinMoin.parser.highlight import Dependencies

class Parser(HighlightParser):
    parsername = 'cpp'  # Lexer name pygments recognizes

