
"""
    MoinMoin - OpenOffice.org 2.0 *.od? Filter (OpenDocument)

    Depends on: nothing (only python with zlib)

    @copyright: 2006-2009 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

import re
import zipfile

from MoinMoin import log

logging = log.getLogger(__name__)

rx_stripxml = re.compile("<[^>]*?>", re.DOTALL|re.MULTILINE)

def execute(indexobj, filename):
    try:
        zf = zipfile.ZipFile(filename, "r")
        data = zf.read("content.xml").decode('utf-8')
        zf.close()
        data = " ".join(rx_stripxml.sub(" ", data).split())
    except (UnicodeDecodeError, zipfile.BadZipfile, RuntimeError) as err:
        logging.error("%s [%s]" % (str(err), filename))
        data = u''
    return data
