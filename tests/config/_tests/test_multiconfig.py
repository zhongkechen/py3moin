
"""
    MoinMoin - MoinMoin.config.multiconfig Tests

    @copyright: 2007 by MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""


import os
import sys

import pytest

from MoinMoin.config import multiconfig


def test_plugin_package_is_registered(req):
    module_name = req.cfg._plugin_modules[0]
    module = sys.modules[module_name]

    assert module.__name__ == module_name
    assert module.__path__ == [os.path.abspath(req.cfg.plugin_dir)]


def test_iwid_generation_uses_hex_text(req, monkeypatch):
    class MetaDict(dict):
        def sync(self):
            self.synced = True

    meta = MetaDict()
    monkeypatch.setattr(req.cfg, '_meta_dict', meta)
    monkeypatch.setattr(multiconfig.util, 'random_string',
                        lambda length: ''.join(chr(value) for value in range(length)))
    monkeypatch.setattr(multiconfig.time, 'time', lambda: 1234567890)

    req.cfg.load_IWID()

    assert req.cfg.iwid == '000102030405060708090a0b0c0d0e0f-1234567890'
    assert meta['IWID'] == req.cfg.iwid
    assert meta.synced


class TestPasswordChecker:
    username = u"SomeUser"
    tests_builtin = [
        (u'', False), # empty
        (u'1966', False), # too short
        (u'asdfghjk', False), # keyboard sequence
        (u'QwertZuiop', False), # german keyboard sequence, with uppercase
        (u'mnbvcx', False), # reverse keyboard sequence
        (u'12345678', False), # keyboard sequence, too easy
        (u'aaaaaaaa', False), # not enough different chars
        (u'BBBaaaddd', False), # not enough different chars
        (username, False), # username == password
        (username[1:-1], False), # password in username
        (u"XXX%sXXX" % username, False), # username in password
        (u'Moin-2007', True), # this should be OK
    ]
    def testBuiltinPasswordChecker(self, req):
        pw_checker = req.cfg.password_checker
        if not pw_checker:
            pytest.skip("password_checker is disabled in the configuration, not testing it")
        else:
            for pw, result in self.tests_builtin:
                pw_error = pw_checker(req, self.username, pw)
                print("%r: %s" % (pw, pw_error))
                assert result == (pw_error is None)

coverage_modules = ['MoinMoin.config.multiconfig']
