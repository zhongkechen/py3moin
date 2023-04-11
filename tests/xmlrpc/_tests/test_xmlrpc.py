
"""
    MoinMoin - tests for the xmlrpc module

    @copyright: 2007 by Karol Nowak <grywacz@gmail.com>
    @license: GNU GPL, see COPYING for details.
"""




from xmlrpc.client import Fault

from MoinMoin.xmlrpc import XmlRpcBase


def test_fault_serialization(req):
    """test MoinMoin.xmlrpc.xmlrpc_system_multicall Fault serialization"""

    def xmlrpc_return_fault():
        return Fault(666, "Fault description")

    xmlrpc = XmlRpcBase(req)
    xmlrpc.xmlrpc_return_fault = xmlrpc_return_fault
    args = [{'methodName': 'return_fault', 'params': []}]

    print("""If a XML RPC method returns a Fault, we should get a failure response
    instead of a serialized Fault, as it happened in the past. See revision
    8b7d6d70fc95 for details""")

    result = xmlrpc.xmlrpc_system_multicall(args)
    assert type(result[0]) is dict
    assert "faultCode" in result[0] and "faultString" in result[0]


def test_getAuthToken(req):
    """ Tests if getAuthToken passes without crashing """
    xmlrpc = XmlRpcBase(req)
    assert xmlrpc.xmlrpc_getAuthToken("Foo", "bar") == ""


coverage_modules = ['MoinMoin.xmlrpc']

