
"""
MoinMoin - dict access via various backends.

@copyright: 2009 DmitrijsMilajevs
@license: GPL, see COPYING for details
"""
from abc import ABC

from MoinMoin.datastruct.backends import BaseDictsBackend, DictDoesNotExistError


class CompositeDicts(BaseDictsBackend, ABC):
    """
    Manage several dicts backends.
    """

    def __init__(self, request, *backends):
        """
        @param backends: list of dict backends which are used to get
                         access to the dict definitions.
        """
        super(CompositeDicts, self).__init__(request)
        self._backends = backends

    def __getitem__(self, dict_name):
        """
        Get a dict by its name. First match counts.
        """
        for backend in self._backends:
            try:
                return backend[dict_name]
            except DictDoesNotExistError:
                pass
        raise DictDoesNotExistError(dict_name)

    def __contains__(self, dict_name):
        """
        Check if a dict called dict_name is available in any of the backends.
        """
        for backend in self._backends:
            if dict_name in backend:
                return True
        return False

    def __repr__(self):
        return "<%s backends=%s>" % (self.__class__, self._backends)

