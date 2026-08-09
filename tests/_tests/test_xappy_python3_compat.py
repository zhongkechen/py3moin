"""
    MoinMoin - Xappy Python 3 compatibility tests

    @license: GNU GPL, see COPYING for details.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType


XAPPY_DIR = (
    Path(__file__).resolve().parents[2] /
    'MoinMoin' / 'support' / 'xappy'
)


def _load_replaylog(monkeypatch):
    monkeypatch.setitem(sys.modules, 'xapian', ModuleType('xapian'))
    spec = importlib.util.spec_from_file_location(
        '_xappy_replaylog_test',
        XAPPY_DIR / 'replaylog.py',
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_indexerconnection(monkeypatch):
    package_name = '_xappy_indexer_test'
    package = ModuleType(package_name)
    package.__path__ = [str(XAPPY_DIR)]
    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setitem(sys.modules, 'xapian', ModuleType('xapian'))

    modules = {
        '_checkxapian': {'missing_features': {}},
        'datastructures': {'__all__': []},
        'errors': {'IndexerError': RuntimeError},
        'fieldactions': {'__all__': []},
        'fieldmappings': {},
        'memutils': {'get_physical_memory': lambda: None},
        'replaylog': {'log': lambda call, *args: call(*args)},
    }
    for name, attributes in modules.items():
        module = ModuleType('%s.%s' % (package_name, name))
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, module.__name__, module)

    spec = importlib.util.spec_from_file_location(
        '%s.indexerconnection' % package_name,
        XAPPY_DIR / 'indexerconnection.py',
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_replay_log_serializes_python3_values(monkeypatch, tmp_path):
    replaylog = _load_replaylog(monkeypatch)
    path = tmp_path / 'replay.log'
    log = replaylog.ReplayLog(str(path))
    try:
        assert log._repr_arg(42) == 'int(42)'
        assert log._repr_arg('café') == 'str(5,café)'
        assert log._repr_arg(b'value') == 'str(5,value)'
        assert log._get_call_id() == '1'
        log._log('RET1:int(42)\n')
        log._log(log._repr_arg(b'\xff') + '\n')
    finally:
        log._fd.close()

    assert path.read_bytes() == b'RET1:int(42)\nstr(1,\xff)\n'


def test_prefixed_term_iterator_uses_python3_iterator_protocol(monkeypatch):
    indexerconnection = _load_indexerconnection(monkeypatch)

    class Term:
        def __init__(self, value):
            self.term = value

    class TermIterator:
        def __init__(self):
            self.terms = ['Qfirst', 'Qsecond', 'Rstop']
            self.position = 0

        def skip_to(self, prefix):
            self.position = next(
                index for index, value in enumerate(self.terms)
                if value >= prefix
            )
            return Term(self.terms[self.position])

        def __iter__(self):
            return self

        def __next__(self):
            self.position += 1
            if self.position >= len(self.terms):
                raise StopIteration
            return Term(self.terms[self.position])

    iterator = indexerconnection.PrefixedTermIter('Q', TermIterator())

    assert list(iterator) == ['first', 'second']
