"""
Tests for WSGI profiling middleware.

@license: GNU GPL, see COPYING for details.
"""

import pstats

import pytest

from MoinMoin.web.http import Client, Response
from MoinMoin.web.profile import CProfileMiddleware, HotshotMiddleware


@pytest.mark.parametrize('middleware_class', [
    CProfileMiddleware,
    HotshotMiddleware,
])
def test_profiler_runs_wsgi_app_and_writes_stats(tmp_path, middleware_class):
    def application(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'profiled']

    stats_path = tmp_path / (middleware_class.__name__ + '.stats')
    middleware = middleware_class(application, str(stats_path))
    response = Client(middleware, Response).get('/')
    middleware.shutdown()

    assert response.get_data() == b'profiled'
    assert pstats.Stats(str(stats_path)).total_calls > 0
