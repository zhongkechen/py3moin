"""
    MoinMoin - WSGI application

    @copyright: 2003-2008 MoinMoin:ThomasWaldmann,
                2008-2008 MoinMoin:FlorianKrupicka
    @license: GNU GPL, see COPYING for details.
"""
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.request import Request
from MoinMoin.web.exceptions import HTTPException
from MoinMoin.web.utils import fatal_response
from MoinMoin import error
from MoinMoin import log

logging = log.getLogger(__name__)


class Application:
    def __init__(self, app_config=None):
        self.app_config = app_config

    def __call__(self, environ, start_response):

        request = None
        try:
            request = Request(environ, given_config=self.app_config)
            context = AllContext(request)
            response = context.run()
        except HTTPException as e:
            response = e
        except error.ConfigurationError as e:
            # this is stuff the user should see on the web interface:
            response = fatal_response(e)
        except Exception as e:
            # we avoid raising more exceptions here to preserve the original exception
            url_info = request and ' [%s]' % request.url or ''
            # have exceptions logged within the moin logging framework:
            logging.exception("An exception has occurred%s." % url_info)
            # re-raise exception, so e.g. the debugger middleware gets it
            raise

        return response(environ, start_response)


# XXX: default application using the default config from disk
application = Application()
