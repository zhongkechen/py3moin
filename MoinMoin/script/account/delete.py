"""Permanently delete an account profile.

@copyright: 2006 MoinMoin:ThomasWaldmann
@license: GNU GPL, see COPYING for details.
"""

from MoinMoin.script.account._lifecycle import AccountLifecycleScript


class PluginScript(AccountLifecycleScript):
    """Permanently delete an account profile."""

    operation = 'delete'
    result = 'deleted'
