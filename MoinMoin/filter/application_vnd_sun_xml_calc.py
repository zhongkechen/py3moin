
"""
    MoinMoin - OpenOffice.org Calc Filter

    Depends on: nothing (only python with zlib)

    @copyright: 2006 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

from MoinMoin.filter.application_vnd_sun_xml import execute as ooofilter

def execute(indexobj, filename):
    return ooofilter(indexobj, filename)

