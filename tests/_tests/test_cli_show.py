"""
MoinMoin CLI show compatibility tests.

@license: GNU GPL, see COPYING for details.
"""

import importlib
from io import StringIO


def test_cli_show_module_imports():
    module = importlib.import_module('MoinMoin.script.cli.show')

    assert module.PluginScript


def test_cli_show_runs_script_context():
    module = importlib.import_module('MoinMoin.script.cli.show')
    script = module.PluginScript(argv=[], def_values=None)
    calls = []

    class Request:
        def run(self):
            calls.append('run')

    def init_request():
        script.request = Request()

    script.init_request = init_request
    script.mainloop()

    assert calls == ['run']


def test_script_context_write_uses_text_stdout(monkeypatch):
    from MoinMoin import i18n
    from MoinMoin.web.contexts import ScriptContext

    output = StringIO()
    context = object.__new__(ScriptContext)
    context.environ = {}
    context.lang = 'en'
    monkeypatch.setattr('sys.stdout', output)
    monkeypatch.setattr(i18n, 'userLanguage', lambda request: 'en')

    context.write('Jürgen', b' bytes', 42)

    assert output.getvalue() == 'Jürgen bytes42'
