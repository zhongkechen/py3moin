"""
MoinMoin - fullsearch action tests

@license: GNU GPL, see COPYING for details.
"""

import pytest

from MoinMoin import search
from MoinMoin.Page import Page
from MoinMoin.action import fullsearch
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.request import TestRequest as MoinTestRequest


@pytest.mark.parametrize('query_string, expected_sort', [
    ('value=Search&titlesearch=Titles&context=180', 'page_name'),
    ('value=Search&fullsearch=Text&context=180', 'weight'),
])
def test_execute_preserves_request_context(
        req, monkeypatch, query_string, expected_sort):
    request = MoinTestRequest(path='/FrontPage', query_string=query_string)
    request.given_config = req.cfg.__class__
    context = AllContext(request)
    search_call = {}

    class SearchCalled(Exception):
        pass

    def record_search(search_context, query, sort, mtime, historysearch):
        search_call['context'] = search_context
        search_call['sort'] = sort
        raise SearchCalled

    monkeypatch.setattr(search, 'searchPages', record_search)

    with pytest.raises(SearchCalled):
        fullsearch.execute('FrontPage', context)

    assert search_call['context'] is context
    assert search_call['sort'] == expected_sort


def test_execute_passes_context_lines_to_result_renderer(req, monkeypatch):
    request = MoinTestRequest(
        path='/FrontPage',
        query_string='value=Search&fullsearch=Text&context=180',
    )
    request.given_config = req.cfg.__class__
    context = AllContext(request)
    context.page = Page(context, 'FrontPage')
    render_call = {}

    class ResultsRendered(Exception):
        pass

    class SearchResults:
        hits = [object()]

        def stats(self, request_context, formatter, hits_from):
            return ''

        def pageListWithContext(
                self, request_context, formatter, **kwargs):
            render_call['context'] = request_context
            render_call['context_lines'] = kwargs['context']
            raise ResultsRendered

    monkeypatch.setattr(search, 'searchPages', lambda *args: SearchResults())
    monkeypatch.setattr(context, 'write', lambda *args: None)
    monkeypatch.setattr(context, 'setContentLanguage', lambda lang: None)
    monkeypatch.setattr(
        context.theme, 'send_title', lambda *args, **kwargs: None)

    with pytest.raises(ResultsRendered):
        fullsearch.execute('FrontPage', context)

    assert render_call['context'] is context
    assert render_call['context_lines'] == 180
