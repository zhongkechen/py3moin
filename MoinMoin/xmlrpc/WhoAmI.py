"""
    MoinMoin - Tells who you are and whether the wiki trusts you.

    @copyright: 2005 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

s
def execute(xmlrpcobj, *args):
    request = xmlrpcobj.request
    username = request.user.name
    if not username:
        username = "<unknown user>"
    valid = request.user.valid
    result = "You are %s. valid=%d." % (username.encode("utf-8"), valid)
    return xmlrpcobj._outstr(result)
