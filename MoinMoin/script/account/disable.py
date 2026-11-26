"""Disable an account and retain its profile.

@copyright: 2006 MoinMoin:ThomasWaldmann
@license: GNU GPL, see COPYING for details.
"""

from MoinMoin.script.account._lifecycle import AccountLifecycleScript


class PluginScript(AccountLifecycleScript):
    """Disable an account and retain its profile."""

    operation = 'disable'
    result = 'disabled'
