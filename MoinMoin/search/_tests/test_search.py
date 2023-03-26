
"""
    MoinMoin - MoinMoin.search Tests

    We exclude underlay/system pages for some search tests to save time.

    @copyright: 2005 by Nir Soffer <nirs@freeshell.org>,
                2007-2010 by MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""
from __future__ import print_function


from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import object
import os, io, time

import pytest

from MoinMoin.search import QueryError, _get_searcher
from MoinMoin.search.queryparser import QueryParser
from MoinMoin.search.builtin import MoinSearch
from MoinMoin._tests import nuke_xapian_index, wikiconfig, become_trusted, create_page, nuke_page, append_page
from MoinMoin.wikiutil import Version
from MoinMoin.action import AttachFile


class TestQueryParsing(object):
    """ search: query parser tests """

    def testQueryParser(self, req):
        """ search: test the query parser """
        parser = QueryParser()
        for query, wanted in [
            # Even a single term is a and expression (this is needed for xapian because it
            # only has AND_NOT, but not a simple NOT).  This is why we have many many brackets here.
            ("a", '["a"]'),
            ("-a", '[-"a"]'),
            ("a b", '["a" "b"]'),
            ("a -b c", '["a" -"b" "c"]'),
            ("aaa bbb -ccc", '["aaa" "bbb" -"ccc"]'),
            ("title:aaa title:bbb -title:ccc", '[title:"aaa" title:"bbb" -title:"ccc"]'),
            ("title:case:aaa title:re:bbb -title:re:case:ccc", '[title:case:"aaa" title:re:"bbb" -title:re:case:"ccc"]'),
            ("linkto:aaa", '[linkto:"aaa"]'),
            ("category:aaa", '[category:"aaa"]'),
            ("domain:aaa", '[domain:"aaa"]'),
            ("re:case:title:aaa", '[title:re:case:"aaa"]'),
            ("(aaa or bbb) and (ccc or ddd)", '[[[["aaa"] or ["bbb"]]] [[["ccc"] or ["ddd"]]]]'),
            ("(aaa or bbb) (ccc or ddd)", '[[[["aaa"] or ["bbb"]]] [[["ccc"] or ["ddd"]]]]'),
            ("aaa or bbb", '[[["aaa"] or ["bbb"]]]'),
            ("aaa or bbb or ccc", '[[["aaa"] or [[["bbb"] or ["ccc"]]]]]'),
            ("aaa or bbb and ccc", '[[["aaa"] or ["bbb" "ccc"]]]'),
            ("aaa and bbb or ccc", '[[["aaa" "bbb"] or ["ccc"]]]'),
            ("aaa and bbb and ccc", '["aaa" "bbb" "ccc"]'),
            ("aaa or bbb and ccc or ddd", '[[["aaa"] or [[["bbb" "ccc"] or ["ddd"]]]]]'),
            ("aaa or bbb ccc or ddd", '[[["aaa"] or [[["bbb" "ccc"] or ["ddd"]]]]]'),
            ("(HelpOn) (Administration)", '[["HelpOn"] ["Administration"]]'),
            ("(HelpOn) (-Administration)", '[["HelpOn"] [-"Administration"]]'),
            ("(HelpOn) and (-Administration)", '[["HelpOn"] [-"Administration"]]'),
            ("(HelpOn) and (Administration) or (Configuration)", '[[[["HelpOn"] ["Administration"]] or [["Configuration"]]]]'),
            ("(a) and (b) or (c) or -d", '[[[["a"] ["b"]] or [[[["c"]] or [-"d"]]]]]'),
            ("a b c d e or f g h", '[[["a" "b" "c" "d" "e"] or ["f" "g" "h"]]]'),
            ('"no', '[""no"]'),
            ('no"', '["no""]'),
            ("'no", "[\"'no\"]"),
            ("no'", "[\"no'\"]"),
            ('"no\'', '[""no\'"]')]:
            result = parser.parse_query(query)
            assert str(result) == wanted

    def testQueryParserExceptions(self, req):
        """ search: test the query parser """
        parser = QueryParser()

        def _test(q):
            pytest.raises(QueryError, parser.parse_query, q)

        for query in ['""', '(', ')', '(a or b']:
            yield _test, query


class BaseSearchTest(object):
    """ search: test search """
    doesnotexist = u'jfhsdaASDLASKDJ'

    # key - page name, value - page content. If value is None page
    # will not be created but will be used for a search. None should
    # be used for pages which already exist.
    pages = {u'SearchTestPage': u'this is a test page',
             u'SearchTestLinks': u'SearchTestPage',
             u'SearchTestLinksLowerCase': u'searchtestpage',
             u'SearchTestOtherLinks': u'SearchTestLinks',
             u'TestEdit': u'TestEdit',
             u'TestOnEditing': u'another test page',
             u'ContentSearchUpper': u'Find the NEEDLE in the haystack.',
             u'ContentSearchLower': u'Find the needle in the haystack.',
             u'LanguageSetup': None,
             u'CategoryHomepage': None,
             u'HomePageWiki': None,
             u'FrontPage': None,
             u'RecentChanges': None,
             u'HelpOnCreoleSyntax': None,
             u'HelpIndex': None,
            }

    searcher_class = None

    def _index_update(self):
        pass

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        become_trusted(req)

        for page, text in list(self.pages.items()):
            if text:
                create_page(req, page, text)

        yield

        for page, text in list(self.pages.items()):
            if text:
                nuke_page(req, page)

    def get_searcher(self, req, query):
        raise NotImplementedError

    def search(self, req, query):
        if isinstance(query, str) or isinstance(query, str):
            query = QueryParser().parse_query(query)

        return self.get_searcher(req, query).run()

    def test_title_search_simple(self, req):
        searches = {u'title:SearchTestPage': 1,
                    u'title:LanguageSetup': 1,
                    u'title:HelpIndex': 1,
                    u'title:Help': 2,
                    u'title:TestOn': 1,
                    u'title:SearchTestNotExisting': 0,
                    u'title:FrontPage': 1,
                    u'title:TestOnEditing': 1,
                   }

        def test(req, query, res_count):
            result = self.search(req, query)
            test_result = len(result.hits)
            assert test_result == res_count

        for query, res_count in list(searches.items()):
            yield query, test, query, res_count

    def test_title_search_re(self, req):
        expected_pages = {u'SearchTestPage', u'SearchTestLinks', u'SearchTestLinksLowerCase', u'SearchTestOtherLinks'}
        result = self.search(req, r'-domain:underlay -domain:system title:re:\bSearchTest')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, r'-domain:underlay -domain:system title:re:\bSearchTest\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_title_search_case(self, req):
        expected_pages = {u'SearchTestPage'}
        result = self.search(req, u'-domain:underlay -domain:system title:case:SearchTestPage')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, u'-domain:underlay -domain:system title:case:searchtestpage')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_title_search_case_re(self, req):
        expected_pages = {u'SearchTestPage'}
        result = self.search(req, r'-domain:underlay -domain:system title:case:re:\bSearchTestPage\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, r'-domain:underlay -domain:system title:case:re:\bsearchtestpage\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_linkto_search_simple(self, req):
        expected_pages = {u'SearchTestLinks'}
        result = self.search(req, u'-domain:underlay -domain:system linkto:SearchTestPage')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, u'-domain:underlay -domain:system linkto:SearchTestNotExisting')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_linkto_search_re(self, req):
        expected_pages = {u'SearchTestLinks', u'SearchTestOtherLinks'}
        result = self.search(req, r'-domain:underlay -domain:system linkto:re:\bSearchTest')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, r'-domain:underlay -domain:system linkto:re:\bSearchTest\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_linkto_search_case(self, req):
        expected_pages = {u'SearchTestLinks'}
        result = self.search(req, u'-domain:underlay -domain:system linkto:case:SearchTestPage')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, u'-domain:underlay -domain:system linkto:case:searchtestpage')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_linkto_search_case_re(self, req):
        expected_pages = {u'SearchTestLinks'}
        result = self.search(req, r'-domain:underlay -domain:system linkto:case:re:\bSearchTestPage\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, r'-domain:underlay -domain:system linkto:case:re:\bsearchtestpage\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_category_search_simple(self, req):
        expected_pages = {u'HomePageWiki'}
        result = self.search(req, u'category:CategoryHomepage')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, u'category:CategorySearchTestNotExisting')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_category_search_re(self, req):
        expected_pages = set([u'HomePageWiki', ])
        result = self.search(req, r'category:re:\bCategoryHomepage\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, r'category:re:\bCategoryHomepa\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_category_search_case(self, req):
        expected_pages = set([u'HomePageWiki', ])
        result = self.search(req, u'category:case:CategoryHomepage')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, u'category:case:categoryhomepage')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_category_search_case_re(self, req):
        expected_pages = {u'HomePageWiki'}
        result = self.search(req, r'category:case:re:\bCategoryHomepage\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, r'category:case:re:\bcategoryhomepage\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_mimetype_search_simple(self, req):
        result = self.search(req, u'mimetype:text/wiki')
        test_result = len(result.hits)
        assert test_result == 14

    def test_mimetype_search_re(self, req):
        result = self.search(req, r'mimetype:re:\btext/wiki\b')
        test_result = len(result.hits)
        assert test_result == 14

        result = self.search(req, r'category:re:\bCategoryHomepa\b')
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def test_language_search_simple(self, req):
        result = self.search(req, u'language:en')
        test_result = len(result.hits)
        assert test_result == 14

    def test_domain_search_simple(self, req):
        result = self.search(req, u'domain:system')
        assert result.hits

    def test_search_and(self, req):
        """ search: title search with AND expression """
        expected_pages = set([u'HelpOnCreoleSyntax', ])
        result = self.search(req, u"title:HelpOnCreoleSyntax lang:en")
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        result = self.search(req, u"title:HelpOnCreoleSyntax lang:de")
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

        result = self.search(req, u"title:Help title:%s" % self.doesnotexist)
        found_pages = set([hit.page_name for hit in result.hits])
        assert not found_pages

    def testTitleSearchOR(self, req):
        """ search: title search with OR expression """
        expected_pages = set([u'FrontPage', u'RecentChanges', ])
        result = self.search(req, u"title:FrontPage or title:RecentChanges")
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

    def testTitleSearchNegatedFindAll(self, req):
        """ search: negated title search for some pagename that does not exist results in all pagenames """
        result = self.search(req, u"-title:%s" % self.doesnotexist)
        n_pages = len(self.pages)
        test_result = len(result.hits)
        assert test_result == n_pages

    def testTitleSearchNegativeTerm(self, req):
        """ search: title search for a AND expression with a negative term """
        result = self.search(req, u"-title:FrontPage")
        found_pages = set([hit.page_name for hit in result.hits])
        assert u'FrontPage' not in found_pages
        test_result = len(result.hits)
        n_pages = len(self.pages) - 1
        assert test_result == n_pages

        result = self.search(req, u"-title:HelpOn")
        test_result = len(result.hits)
        n_pages = len(self.pages) - 1
        assert test_result == n_pages

    def testFullSearchNegatedFindAll(self, req):
        """ search: negated full search for some string that does not exist results in all pages """
        result = self.search(req, u"-%s" % self.doesnotexist)
        test_result = len(result.hits)
        n_pages = len(self.pages)
        assert test_result == n_pages

    def testFullSearchRegexCaseInsensitive(self, req):
        """ search: full search for regular expression (case insensitive) """
        search_re = 'ne{2}dle' # matches 'NEEDLE' or 'needle' or ...
        expected_pages = set(['ContentSearchUpper', 'ContentSearchLower', ])
        result = self.search(req, u'-domain:underlay -domain:system re:%s' % search_re)
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

    def testFullSearchRegexCaseSensitive(self, req):
        """ search: full search for regular expression (case sensitive) """
        search_re = 'ne{2}dle' # matches 'needle'
        expected_pages = set(['ContentSearchLower', ])
        result = self.search(req, u'-domain:underlay -domain:system re:case:%s' % search_re)
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

    def test_title_search(self, req):
        expected_pages = {'FrontPage'}
        query = QueryParser(titlesearch=True).parse_query('FrontPage')
        result = self.search(req, query)
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

    def test_create_page(self, req):
        expected_pages = {u'TestCreatePage'}
        self.pages['TestCreatePage'] = 'some text' # Moin search must search this page
        try:
            create_page(req, 'TestCreatePage', self.pages['TestCreatePage'])
            self._index_update()
            result = self.search(req, u'-domain:underlay -domain:system TestCreatePage')
            found_pages = set([hit.page_name for hit in result.hits])
            assert found_pages == expected_pages
        finally:
            nuke_page(req, 'TestCreatePage')
            self._index_update()
            del self.pages['TestCreatePage']
            result = self.search(req, u'-domain:underlay -domain:system TestCreatePage')
            found_pages = set([hit.page_name for hit in result.hits])
            assert not found_pages

    def test_attachment(self, req):
        page_name = u'TestAttachment'
        self.pages[page_name] = 'some text' # Moin search must search this page

        filename = "AutoCreatedSillyAttachmentForSearching.png"
        data = b"Test content"
        filecontent = io.BytesIO(data)

        result = self.search(req, filename)
        found_attachments = set([(hit.page_name, hit.attachment) for hit in result.hits])
        assert not found_attachments

        try:
            create_page(req, page_name, self.pages[page_name])
            AttachFile.add_attachment(req, page_name, filename, filecontent, True)
            append_page(req, page_name, '[[attachment:%s]]' % filename)
            self._index_update()
            result = self.search(req, filename)
            found_attachments = set([(hit.page_name, hit.attachment) for hit in result.hits])
            assert (page_name, '') in found_attachments
            assert 1 <= len(found_attachments) <= 2
            # Note: moin search returns (page_name, '') as only result
            #       xapian search returns 2 results: (page_name, '') and (page_name, filename)
            # TODO: make behaviour the same, if possible
        finally:
            nuke_page(req, page_name)
            del self.pages[page_name]
            self._index_update()
            result = self.search(req, filename)
            found_attachments = set([(hit.page_name, hit.attachment) for hit in result.hits])
            assert not found_attachments

    def test_get_searcher(self, req):
        assert isinstance(_get_searcher(req, ''), self.searcher_class)


class TestMoinSearch(BaseSearchTest):
    """ search: test Moin search """
    searcher_class = MoinSearch

    def get_searcher(self, req, query):
        pages = [{'pagename': page, 'attachment': '', 'wikiname': 'Self', } for page in self.pages]
        return MoinSearch(req, query, pages=pages)

    def test_stemming(self, req):
        expected_pages = set([u'TestEdit', u'TestOnEditing', ])
        result = self.search(req, u"title:edit")
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        expected_pages = set([u'TestOnEditing', ])
        result = self.search(req, u"title:editing")
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages


class TestXapianSearch(BaseSearchTest):
    """ search: test Xapian indexing / search """

    class Config(wikiconfig.Config):
        xapian_search = True

    def _index_update(self, req):
        # for xapian, we queue index updates so they can get indexed later.
        # here we make sure the queue will be processed completely,
        # before we continue:
        from MoinMoin.search.Xapian import XapianIndex
        XapianIndex(req).do_queued_updates()

    def get_searcher(self, req, query):
        from MoinMoin.search.Xapian.search import XapianSearch
        return XapianSearch(req, query)

    def get_moin_search_connection(self, req):
        from MoinMoin.search.Xapian import XapianIndex
        return XapianIndex(req).get_search_connection()

    @pytest.fixture(autouse=True)
    def setup_class(self, req):
        try:
            from MoinMoin.search.Xapian import XapianIndex
            from MoinMoin.search.Xapian.search import XapianSearch
            self.searcher_class = XapianSearch

        except ImportError as error:
            if not str(error).startswith('Xapian '):
                raise
            pytest.skip('xapian is not installed')

        nuke_xapian_index(req)
        index = XapianIndex(req)
        # Additionally, pages which were not created but supposed to be searched
        # are indexed.
        pages_to_index = [page for page in self.pages if not self.pages[page]]
        index.indexPages(mode='add', pages=pages_to_index)

        super(TestXapianSearch, self).setup_class()

        yield

        nuke_xapian_index(req)

    def test_get_all_documents(self, req):
        connection = self.get_moin_search_connection(req)
        documents = connection.get_all_documents()
        n_pages = len(self.pages)
        test_result = len(documents)
        assert test_result == n_pages
        for document in documents:
            assert document.data['pagename'][0] in list(self.pages.keys())

    def test_xapian_term(self, req):
        parser = QueryParser()
        connection = self.get_moin_search_connection(req)

        prefixes = {u'': ([u'', u're:', u'case:', u'case:re:'], u'SearchTestPage'),
                    u'title:': ([u'', u're:', u'case:', u'case:re:'], u'SearchTestPage'),
                    u'linkto:': ([u'', u're:', u'case:', u'case:re:'], u'FrontPage'),
                    u'category:': ([u'', u're:', u'case:', u'case:re:'], u'CategoryHomepage'),
                    u'mimetype:': ([u'', u're:'], u'text/wiki'),
                    u'language:': ([u''], u'en'),
                    u'domain:': ([u''], u'system'),
                   }

        def test_query(query, req):
            query_ = parser.parse_query(query).xapian_term(req, connection)
            print(str(query_))
            assert not query_.empty()

        for prefix, data in list(prefixes.items()):
            modifiers, term = data
            for modifier in modifiers:
                query = ''.join([prefix, modifier, term])
                yield query, test_query, query

    def test_stemming(self, req):
        expected_pages = {u'TestEdit'}
        result = self.search(req, u"title:edit")
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        expected_pages = {u'TestOnEditing'}
        result = self.search(req, u"title:editing")
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages


class TestXapianSearchStemmed(TestXapianSearch):
    """ search: test Xapian indexing / search - with stemming enabled """

    class Config(wikiconfig.Config):
        xapian_search = True
        xapian_stemming = True

    def test_stemming(self, req):
        pytest.skip("TODO fix TestXapianSearchStemmed - strange effects with stemming")

        expected_pages = {u'TestEdit', u'TestOnEditing'}
        result = self.search(req, u"title:edit")
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages

        expected_pages = {u'TestEdit', u'TestOnEditing'}
        result = self.search(req, u"title:editing")
        found_pages = set([hit.page_name for hit in result.hits])
        assert found_pages == expected_pages


class TestGetSearcher(object):

    class Config(wikiconfig.Config):
        xapian_search = True

    def test_get_searcher(self, req):
        assert isinstance(_get_searcher(req, ''), MoinSearch), 'Xapian index is not created, despite the configuration, MoinSearch must be used!'

coverage_modules = ['MoinMoin.search']

