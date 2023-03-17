# -*- coding: iso-8859-1 -*-
"""
MoinMoin - MailImport script

@copyright: 2006 MoinMoin:AlexanderSchremmer
@license: GNU GPL, see COPYING for details.
"""
from __future__ import print_function

from future import standard_library
standard_library.install_aliases()
import sys
import xmlrpc.client

from MoinMoin.script import MoinScript, fatal

input = sys.stdin

class PluginScript(MoinScript):
    """\
Purpose:
========
This tool allows you to import mail into the wiki.

Detailed Instructions:
======================
General syntax: moin [options] maint mailimport [mailimport-options]

[options] usually should be:
    --config-dir=/path/to/my/cfg/ --wiki-url=http://wiki.example.org/

[mailimport-options] see below:
    0. Verify that you have a mailimportconf.py configuration file.

    1. To import mail from the file '/mymail'
       moin ... xmlrpc mailimport << /mymail
       OR
       cat /mymail | moin ... xmlrpc mailimport
"""

    def __init__(self, argv, def_values):
        MoinScript.__init__(self, argv, def_values)

    def mainloop(self):
        try:
            import mailimportconf
        except ImportError:
            fatal("Could not find the file mailimportconf.py. Maybe you want to use the --config-dir=... option?")

        secret = mailimportconf.mail_import_secret
        url = mailimportconf.mail_import_url

        s = xmlrpc.client.ServerProxy(url)

        result = s.ProcessMail(secret, xmlrpc.client.Binary(input.read()))

        if result != "OK":
            print(result, file=sys.stderr)

