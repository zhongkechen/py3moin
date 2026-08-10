"""
Tests for the i18n source checker.

@license: GNU GPL, see COPYING for details.
"""

import importlib


def test_text_finder_uses_python_ast(tmp_path, capsys):
    check_i18n = importlib.import_module('MoinMoin.i18n.tools.check_i18n')
    source = tmp_path / 'messages.py'
    source.write_text(
        "_('direct')\n"
        "translator._('attribute')\n"
        "_('dynamic ' + value)\n",
        encoding='utf-8',
    )
    finder = check_i18n.TextFinder()

    check_i18n.visit(source, finder)

    assert finder.dictionary() == {
        'direct': {source: [1]},
        'attribute': {source: [2]},
    }
    assert finder.found() == 2
    assert finder.bad() == 1
    assert 'non-constant _ call' in capsys.readouterr().out
