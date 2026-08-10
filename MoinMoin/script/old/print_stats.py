#!/usr/bin/env python

"""
    MoinMoin - Print statistics gathered by cProfile

    Usage:
        print_stats.py statsfile

    Typical usage:
     1. Configure the cProfile middleware and set the profile file name
     2. Run moin.py
     3. Do some request, with a browser, script or ab
     4. Stop moin.py
     5. Run this tool: print_stats.py moin.prof

    @copyright: 2005 by Thomas Waldmann (MoinMoin:ThomasWaldmann)
    @license: GNU GPL, see COPYING for details.
"""

def run():
    import pstats
    import sys

    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit()

    # Load and print stats
    s = pstats.Stats(sys.argv[1])
    s.strip_dirs()
    s.sort_stats('cumulative', 'time', 'calls')
    s.print_stats(40)
    s.print_callers(40)

if __name__ == "__main__":
    run()
