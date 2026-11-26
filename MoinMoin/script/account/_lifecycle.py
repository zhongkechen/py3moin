"""Common CLI for account lifecycle operations.

Adapted from moinmoin-py3-md 1.12.1 by Gabriele 'asbesto' Zaverio and
Claude (Anthropic AI). GNU GPL, see docs/licenses/COPYING.
"""

from MoinMoin import user
from MoinMoin.script import MoinScript


class AccountLifecycleScript(MoinScript):
    def __init__(self, argv, def_values):
        super().__init__(argv, def_values)
        self.parser.add_option('--uid', metavar='UID', help='Select the account by user ID.')
        self.parser.add_option('--name', metavar='NAME', help='Select the account by username.')

    def mainloop(self):
        if self.args or bool(self.options.uid) == bool(self.options.name):
            self.parser.error('specify exactly one of --uid or --name')
        self.init_request()
        context = self.request
        profiles = user.getUserList(context)
        if self.options.uid:
            matches = [user.User(context, self.options.uid)] if self.options.uid in profiles else []
        else:
            matches = []
            for uid in profiles:
                profile = user.User(context, uid)
                if self.options.name in (profile.name, profile.original_identity()[0]):
                    matches.append(profile)
        if len(matches) > 1:
            self.parser.error('multiple accounts match this name; select one with --uid')
        if not matches or not matches[0].exists():
            self.parser.error('account not found')
        account = matches[0]
        try:
            changed = getattr(account, self.operation)()
        except user.AccountIdentityConflict as error:
            self.parser.error(f'cannot enable account: another profile uses its {error}')
        if changed:
            print(f'{account.name} ({account.id}): {self.result}.')
        else:
            print(f'{account.name} ({account.id}): already {self.result}.')
