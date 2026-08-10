"""
Tests for example configuration source encodings.

@license: GNU GPL, see COPYING for details.
"""

import ast
from pathlib import Path
import tokenize

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('relative_path', [
    'wiki/config/wikiconfig.py',
    'wiki/config/wikifarm/farmconfig.py',
])
def test_example_config_has_a_valid_source_encoding(relative_path):
    path = REPOSITORY_ROOT / relative_path

    with tokenize.open(path) as source_file:
        source = source_file.read()

    ast.parse(source, filename=str(path))
