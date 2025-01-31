"""
    MoinMoin - HTTP exceptions

    Customization of werkzeug.exceptions classes for use in MoinMoin.

    @copyright: 2008-2008 MoinMoin:FlorianKrupicka
    @license: GNU GPL, see COPYING for details.
"""

from werkzeug import exceptions

HTTPException = exceptions.HTTPException


class SurgeProtection(exceptions.ServiceUnavailable):
    """ A surge protection error in MoinMoin is based on the HTTP status
    `Service Unavailable`. This HTTP exception gives a short description
    on what triggered the surge protection mechanism to the user.
    """

    name = 'Surge protection'
    description = (
        "Warning:"
        " You triggered the wiki's surge protection by doing too many requests in a short time."
        " Please make a short break reading the stuff you already got."
        " When you restart doing requests AFTER that, slow down or you might get locked out for a longer time!"
    )

    def __init__(self, description=None, retry_after=3600):
        exceptions.ServiceUnavailable.__init__(self, description)
        self.retry_after = retry_after

    def get_headers(self, environ, scope):
        headers = exceptions.ServiceUnavailable.get_headers(self, environ)
        headers.append(('Retry-After', '%d' % self.retry_after))
        return headers


class Forbidden(exceptions.Forbidden):
    """
    Override the default description of werkzeug.exceptions.Forbidden to a
    less technical sounding one.
    """
    description = "You are not allowed to access this!"


# handy exception raising
abort = exceptions.abort
