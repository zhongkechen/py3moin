# -*- coding: iso-8859-1 -*-
"""
    MoinMoin - MoinMoin.formatter.* Tests

    @copyright: 2005 by MoinMoin:AlexanderSchremmer
    @license: GNU GPL, see COPYING for details.
"""
from __future__ import print_function

from builtins import range
from builtins import object
import pytest

from MoinMoin.Page import Page
from MoinMoin import wikiutil


class TestFormatter(object):
    def testSyntaxReferenceDomXml(self, req):
        pytest.skip("domxml <p> generation is broken")
        f_name = 'dom_xml'
        try:
            formatter = wikiutil.importPlugin(req.cfg, "formatter", f_name, "Formatter")
        except wikiutil.PluginAttributeError:
            pass
        else:
            print("Formatting using %r" % formatter)
            self.formatPage("HelpOnMoinWikiSyntax", formatter)
            print("Done.")

    def testSyntaxReferenceDocBook(self, req):
        pytest.skip("docbook is broken")
        f_name = 'text_docbook'
        try:
            formatter = wikiutil.importPlugin(req.cfg, "formatter", f_name, "Formatter")
        except wikiutil.PluginAttributeError:
            pass
        else:
            print("Formatting using %r" % formatter)
            self.formatPage("HelpOnMoinWikiSyntax", formatter)
            print("Done.")

    def testSyntaxReferenceOthers(self, req):
        formatters = wikiutil.getPlugins("formatter", req.cfg)

        # we have separate tests for those:
        formatters.remove('text_docbook')
        formatters.remove('dom_xml')

        for f_name in formatters:
            try:
                formatter = wikiutil.importPlugin(req.cfg, "formatter", f_name, "Formatter")
            except wikiutil.PluginAttributeError:
                pass
            else:
                print("Formatting using %r" % formatter)
                self.formatPage(req, "HelpOnMoinWikiSyntax", formatter)
                print("Done.")

    def formatPage(self, req, pagename, formatter):
        """Parse a page. Should not raise an exception if the API of the
        formatter is correct.
        """

        req.reset()
        page = Page(req, pagename, formatter=formatter)
        req.formatter = page.formatter = formatter(req)
        req.page = page
        #page.formatter.setPage(page)
        #page.hilite_re = None

        return req.redirectedOutput(page.send_page, content_only=1)


class TestIdIdempotency(object):
    def test_sanitize_to_id_idempotent(self, req):
        def _verify(formatter, id):
            origid = formatter.sanitize_to_id(id)
            id = origid
            for i in range(3):
                id = formatter.sanitize_to_id(id)
                assert id == origid

        formatters = wikiutil.getPlugins("formatter", req.cfg)

        testids = [
            r"tho/zeequeen&angu\za",
            r"quuirahz\iphohsaij,i",
            r"ashuifa+it[ohchieque",
            r"ohyie-lakoo`duaghaib",
            r"eixaepumuqu[ie\ba|eh",
            r"theegieque;zahmeitie",
            r"pahcooje&rahkeiz$oez",
            r"ohjeeng*iequao%fai?p",
            r"ahfoodahmepooquepee;",
            r"ubed_aex;ohwebeixah%",
            r"eitiekicaejuelae=g^u",
            r"",
            r'  ',
            r'--123',
            r'__$$',
            r'@@',
            u'\xf6\xf6llasdf\xe4',
        ]

        for f_name in formatters:
            try:
                formatter = wikiutil.importPlugin(req.cfg, "formatter",
                                                  f_name, "Formatter")
                f = formatter(req)
                for id in testids:
                    yield _verify, f, id
            except wikiutil.PluginAttributeError:
                pass


coverage_modules = ['MoinMoin.formatter',
                    'MoinMoin.formatter.text_html',
                    'MoinMoin.formatter.text_gedit',
                    'MoinMoin.formatter.text_xml',
                    'MoinMoin.formatter.text_docbook',
                    'MoinMoin.formatter.text_plain',
                    'MoinMoin.formatter.dom_xml',
                    'MoinMoin.formatter.text_python',
                    'MoinMoin.formatter.pagelinks',
                    'MoinMoin.formtter.groups',
                   ]

