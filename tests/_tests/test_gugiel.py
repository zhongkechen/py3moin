"""
Tests for the legacy Gugiel theme.

@license: GNU GPL, see COPYING for details.
"""

import importlib.util
from pathlib import Path


GUGIEL_PATH = (
    Path(__file__).resolve().parents[2]
    / 'MoinMoin/web/static/htdocs/gugiel/gugiel.py'
)


def load_gugiel():
    spec = importlib.util.spec_from_file_location('moin_test_gugiel', GUGIEL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sidebar_captures_rendered_page(monkeypatch):
    gugiel = load_gugiel()

    class Request:
        def __init__(self):
            self.write = None
            self.getText = lambda text: text

        def getPragma(self, name):
            return None

        def redirect(self, output=None):
            self.write = output.write if output is not None else None

    class SidebarPage:
        def __init__(self, request, name):
            self.request = request

        def exists(self):
            return True

        def send_page(self, **kwargs):
            self.request.write('sidebar content')

    request = Request()
    theme = object.__new__(gugiel.Theme)
    theme.request = request
    monkeypatch.setattr(gugiel, 'Page', SidebarPage)

    assert theme.sidebar({}) == (
        '<div class="sidebar">sidebar content</div>'
    )
    assert request.write is None
