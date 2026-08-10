"""
Tests for the legacy profile statistics tool.

@license: GNU GPL, see COPYING for details.
"""

import cProfile
import sys


def test_print_stats_reads_cprofile_output(tmp_path, monkeypatch, capsys):
    from MoinMoin.script.old import print_stats

    stats_path = tmp_path / 'profile.stats'
    profiler = cProfile.Profile()
    profiler.runcall(sum, range(5))
    profiler.dump_stats(str(stats_path))

    monkeypatch.setattr(sys, 'argv', ['print_stats.py', str(stats_path)])

    print_stats.run()

    assert 'function calls' in capsys.readouterr().out
