#!/usr/bin/env python

"""
    MoinMoin - Version Information

    @copyright: 2000-2006 Juergen Hermann <jh@web.de>,
                2003-2020 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""
from importlib.metadata import version

project = "Py3Moin"
release = version("py3moin")
release_short = release.replace(".", "")  # used for url_prefix_static
revision = "release"
