"""Restore a disabled account.

@copyright: 2006 MoinMoin:ThomasWaldmann
@license: GNU GPL, see COPYING for details.
"""

from MoinMoin.script.account._lifecycle import AccountLifecycleScript


class PluginScript(AccountLifecycleScript):
    """Restore a disabled account."""

    operation = 'enable'
    result = 'enabled'
