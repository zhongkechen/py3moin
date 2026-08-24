"""
MoinMoin - search result formatting tests

@license: GNU GPL, see COPYING for details.
"""

from MoinMoin.Page import Page
from MoinMoin.search.results import SearchResults
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.request import TestRequest as MoinTestRequest


def test_format_page_links_uses_wrapped_request_query_string(req):
    request = MoinTestRequest(
        path='/FrontPage',
        query_string='action=fullsearch&value=Data&titlesearch=Titles',
    )
    request.given_config = req.cfg.__class__
    context = AllContext(request)
    context.page = Page(context, 'FrontPage')
    results = SearchResults(
        query=None,
        hits=[],
        pages=0,
        elapsed=0,
        sort='page_name',
        estimated_hits=('', 2),
    )
    results._reset(context, context.formatter)

    output = results.formatPageLinks(
        hitsFrom=0,
        hitsPerPage=1,
        hitsNum=2,
    )

    assert 'value=Data' in output
    assert 'from=1' in output
