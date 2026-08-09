"""
    MoinMoin - mk_POTFILES tests

    @license: GNU GPL, see COPYING for details.
"""

from pathlib import Path

from MoinMoin.i18n.tools import mk_POTFILES


def test_find_files_uses_python3_directory_walking(tmp_path):
    paths = [
        'alpha.py',
        'sub/beta.py',
        'filter/keep.py',
        '_tests/ignored.py',
        'support/ignored.py',
        'filter/EXIF.py',
        'web/static/htdocs/ignored.py',
        'notes.txt',
    ]
    for relative_path in paths:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')

    assert mk_POTFILES.find_files(str(tmp_path)) == [
        'alpha.py',
        str(Path('filter') / 'keep.py'),
        str(Path('sub') / 'beta.py'),
    ]


def test_write_potfiles_handles_files_and_empty_lists(tmp_path):
    files = ['alpha.py', str(Path('sub') / 'beta.py')]
    mk_POTFILES.write_potfiles(files, 'MoinMoin', str(tmp_path))

    assert (tmp_path / 'POTFILES.in').read_text(encoding='utf-8') == (
        'alpha.py\nsub/beta.py\n'
    )
    assert (tmp_path / 'POTFILES').read_text(encoding='utf-8') == (
        'POTFILES = \\\n'
        '\tMoinMoin/alpha.py \\\n'
        '\tMoinMoin/sub/beta.py\n'
    )

    mk_POTFILES.write_potfiles([], 'MoinMoin', str(tmp_path))
    assert (tmp_path / 'POTFILES.in').read_text(encoding='utf-8') == ''
    assert (tmp_path / 'POTFILES').read_text(encoding='utf-8') == (
        'POTFILES = \\\n'
    )
