# -*- coding: utf-8 -*-
"""
    MoinMoin - MoinMoin.web.utils Tests

    @copyright: 2008 MoinMoin:FlorianKrupicka
    @license: GNU GPL, see COPYING for details.
"""
import pytest

from MoinMoin.web import utils

class TestUniqueIDGenerator:

    def setup_method(self, method):
        self.uid_gen = utils.UniqueIDGenerator('TestPage')

    def testGeneration(self):
        TESTCASES = [('somebase', 'somebase'), ('other', 'other'),
                     ('somebase', 'somebase-1'), ('another', 'another'),
                     ('other', 'other-1'), ('other', 'other-2'),
                     ('somebase', 'somebase-2')]
        for base, expected in TESTCASES:
            assert self.uid_gen(base) == expected

    def testStack(self):
        pytest.skip("TODO: needs implementation")

    def testDocuments(self):
        pytest.skip("TODO: needs implementation")
