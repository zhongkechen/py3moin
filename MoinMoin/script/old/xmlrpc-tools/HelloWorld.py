#!/usr/bin/env python
"""
This script is a sample for xmlrpc calls.

It calls the HelloWorld.py xmlrpc plugin.

GPL software, 2003-08-10 Thomas Waldmann
"""
from __future__ import print_function

from future import standard_library
standard_library.install_aliases()
def run():
    import xmlrpc.client
    srcwiki = xmlrpc.client.ServerProxy("http://master.moinmo.in/?action=xmlrpc2")
    print(srcwiki.HelloWorld("Hello Wiki User!\n"))

if __name__ == "__main__":
    run()

