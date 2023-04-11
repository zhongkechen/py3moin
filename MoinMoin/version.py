#!/usr/bin/env python

"""
    MoinMoin - Version Information

    @copyright: 2000-2006 Juergen Hermann <jh@web.de>,
                2003-2020 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""
import sys

try:
    from MoinMoin.patchlevel import patchlevel
except:
    patchlevel = 'release'

project = "Py3Moin"
release = '3.0.0a1'
release_short = '300'  # used for url_prefix_static
revision = patchlevel


def update():
    """ update the version information in package init """
    fname = 'MoinMoin/__init__.py'
    f = open(fname)
    lines = f.readlines()
    f.close()
    f = open(fname, "w")
    version_pattern = "%s Version " % project
    version_string = version_pattern + "%s %s" % (release, revision)
    for line in lines:
        if version_pattern in line:
            f.write("%s\n" % version_string)
        else:
            f.write(line)
    f.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        update()
    else:
        print(project, release, revision)
