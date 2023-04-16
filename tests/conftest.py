
"""
MoinMoin Testing Framework
--------------------------

All test modules must be named test_modulename to be included in the
test suite. If you are testing a package, name the test module
test_package_module.

Tests that need the current request, for example to create a page
instance, can refer to self.request. It is injected into all test case
classes by the framework.

Tests that require a certain configuration, like section_numbers = 1, must
use a Config class to define the required configuration within the test class.

@copyright: 2005 MoinMoin:NirSoffer,
            2007 MoinMoin:AlexanderSchremmer,
            2008 MoinMoin:ThomasWaldmann
@license: GNU GPL, see COPYING for details.
"""

import atexit
import sys
import os.path

import pytest

from MoinMoin.web.contexts import AllContext

rootdir = os.path.abspath(os.path.dirname(__file__))
moindir = rootdir.join("..")
sys.path.insert(0, str(moindir))

from MoinMoin.web.request import TestRequest, Client
from MoinMoin.wsgiapp import Application
from tests._tests import maketestwiki, wikiconfig

coverage_modules = set()

try:
    """
    This code adds support for coverage.py (see
    http://nedbatchelder.com/code/modules/coverage.html).
    It prints a coverage report for the modules specified in all
    module globals (of the test modules) named "coverage_modules".
    """

    import coverage

    def report_coverage():
        coverage.stop()
        module_list = [sys.modules[mod] for mod in coverage_modules]
        module_list.sort()
        coverage.report(module_list)

    def callback(option, opt_str, value, parser):
        atexit.register(report_coverage)
        coverage.erase()
        coverage.start()

    pytest.config.addoptions('MoinMoin options', pytest.config.Option('-C',
        '--coverage', action='callback', callback=callback,
        help='Output information about code coverage (slow!)'))

except ImportError:
    coverage = None


def init_test_request(given_config=None, static_state=[False]):
    if not static_state[0]:
        maketestwiki.run(True)
        static_state[0] = True
    request = TestRequest()
    request.given_config = given_config
    context = AllContext(request)
    return context


# pytest customization starts here

# pytest-1.0 provides "funcargs" natively
@pytest.hookimpl(optionalhook=True)
def pytest_funcarg__request(request):
    # note the naminng clash: pytest's funcarg-request object
    # and the request we provide are totally separate things
    cls = request._pyfuncitem.getparent(pytest.Module)
    return cls.request


@pytest.fixture
def req(request):
    marker = request.node.get_closest_marker("wiki_config")
    if marker:
        class config(wikiconfig.Config):
            pass

        for k, v in marker.kwargs.items():
            setattr(config, k, v)
    else:
        config = wikiconfig.Config

    return init_test_request(config)


class MoinTestFunction(pytest.Function):
    def execute(self, target, *args):
        request = self.parent.request
        co = target.__code__
        if 'request' in co.co_varnames[:co.co_argcount]:
            target(request, *args)
        else:
            target(*args)


class MoinClassCollector(pytest.Class):
    Function = MoinTestFunction

    def setup(self):
        cls = self.obj
        if hasattr(cls, 'Config'):
            cls.request = init_test_request(given_config=cls.Config)
            cls.client = Client(Application(cls.Config))
        else:
            cls.request = self.parent.request
            #XXX: this is the extremely messy way to configure the wsgi app
            #     with the correct testing config
            cls.client = Client(Application(self.parent.request.cfg.__class__))
        super(MoinClassCollector, self).setup()


class Module(pytest.Module):
    Class = MoinClassCollector
    Function = MoinTestFunction

    def __init__(self, *args, **kwargs):
        self.request = init_test_request(given_config=wikiconfig.Config)
        super(Module, self).__init__(*args, **kwargs)

    def run(self, *args, **kwargs):
        if coverage is not None:
            coverage_modules.update(getattr(self.obj, 'coverage_modules', []))
        return super(Module, self).run(*args, **kwargs)
