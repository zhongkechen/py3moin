"""
    MoinMoin - Remote Script Execution Server part

    @copyright: 2006 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

from MoinMoin import log
from MoinMoin.script import MoinScript

logging = log.getLogger(__name__)


def execute(xmlrpcobj, their_secret, argv):
    request = xmlrpcobj.request
    their_secret = xmlrpcobj._instr(their_secret)

    our_secret = request.cfg.secrets['xmlrpc/RemoteScript']

    if our_secret != their_secret:
        return u"Invalid password"

    try:
        logging.info("RemoteScript argv: %r" % argv)
        MoinScript(argv).run(showtime=0)
    except Exception as err:
        logging.exception('An exception occurred.')
        return xmlrpcobj._outstr(str(err))
    return xmlrpcobj._outstr(u"OK")
