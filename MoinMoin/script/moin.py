#!/usr/bin/env python

"""
    MoinMoin - "moin" is the main script command and calls other stuff as
    a sub-command.

    Usage: moin cmdmodule cmdname [options]

    @copyright: 2006 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""


def run():
    from MoinMoin.script import MoinScript
    MoinScript().run(showtime=0)


if __name__ == "__main__":
    run()
