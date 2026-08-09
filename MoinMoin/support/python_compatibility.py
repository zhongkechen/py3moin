"""
    MoinMoin - Support Package

    Was: Stuff for compatibility with Python < 2.7. Just a dummy now.

    @copyright: 2007 Heinrich Wendel <heinrich.wendel@gmail.com>,
                2009 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

rsplit = str.rsplit

sorted = sorted

set = set
frozenset = frozenset

from functools import partial

import hashlib, hmac

hash_new = hashlib.new

def hmac_new(key, msg, digestmod=hashlib.sha1):
    if isinstance(key, str):
        key = key.encode('utf-8')
    if isinstance(msg, str):
        msg = msg.encode('utf-8')
    return hmac.new(key, msg, digestmod)
