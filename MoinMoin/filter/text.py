
"""
    MoinMoin - text/* file Filter

    We try to support more than ASCII here.

    @copyright: 2006 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

import codecs


def execute(indexobj, filename):
    for enc in ('utf-8', 'iso-8859-15', ):
        try:
            with codecs.open(filename, "r", enc) as f:
                data = f.read()
            return data
        except UnicodeError:
            pass
    with open(filename, "r") as f:
        data = f.read()
    # data = data.decode('ascii', 'replace')
    return data

