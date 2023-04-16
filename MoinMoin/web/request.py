"""
    MoinMoin - New slimmed down WSGI Request.

    @copyright: 2008-2008 MoinMoin:FlorianKrupicka
    @license: GNU GPL, see COPYING for details.
"""
import sys
from io import StringIO

from passlib.utils import to_unicode
from werkzeug import Request as RequestBase
from werkzeug import Response as WerkzeugResponseBase
from werkzeug.datastructures import EnvironHeaders
from werkzeug.test import create_environ
from werkzeug.urls import url_encode, url_join, url_quote
from werkzeug.utils import cached_property
from werkzeug.wrappers import ResponseStream

from MoinMoin import config
from MoinMoin import log

logging = log.getLogger(__name__)


class MoinMoinFinish(Exception):
    """ Raised to jump directly to end of run() function, where finish is called """


class ModifiedResponseStreamMixin:
    """
    to avoid .stream attributes name collision when we mix together Request
    and Response, we use "out_stream" instead of "stream" in the original
    ResponseStreamMixin
    """

    @cached_property
    def out_stream(self):
        """The response iterable as write-only stream."""
        return ResponseStream(self)


# class ResponseBase(BaseResponse, ETagResponseMixin, ModifiedResponseStreamMixin, CommonResponseDescriptorsMixin, WWWAuthenticateMixin):
class ResponseBase(WerkzeugResponseBase, ModifiedResponseStreamMixin):
    """
    similar to werkzeug.Response, but with ModifiedResponseStreamMixin
    """


def to_native(x, charset=sys.getdefaultencoding(), errors="strict"):
    if x is None or isinstance(x, str):
        return x
    return x.decode(charset, errors)


class Href:
    """Implements a callable that constructs URLs with the given base. The
    function can be called with any number of positional and keyword
    arguments which than are used to assemble the URL.  Works with URLs
    and posix paths.
    Positional arguments are appended as individual segments to
    the path of the URL:
    >>> href = Href('/foo')
    >>> href('bar', 23)
    '/foo/bar/23'
    >>> href('foo', bar=23)
    '/foo/foo?bar=23'
    If any of the arguments (positional or keyword) evaluates to `None` it
    will be skipped.  If no keyword arguments are given the last argument
    can be a :class:`dict` or :class:`MultiDict` (or any other dict subclass),
    otherwise the keyword arguments are used for the query parameters, cutting
    off the first trailing underscore of the parameter name:
    >>> href(is_=42)
    '/foo?is=42'
    >>> href({'foo': 'bar'})
    '/foo?foo=bar'
    Combining of both methods is not allowed:
    >>> href({'foo': 'bar'}, bar=42)
    Traceback (most recent call last):
      ...
    TypeError: keyword arguments and query-dicts can't be combined
    Accessing attributes on the href object creates a new href object with
    the attribute name as prefix:
    >>> bar_href = href.bar
    >>> bar_href("blub")
    '/foo/bar/blub'
    If `sort` is set to `True` the items are sorted by `key` or the default
    sorting algorithm:
    >>> href = Href("/", sort=True)
    >>> href(a=1, b=2, c=3)
    '/?a=1&b=2&c=3'
    .. versionadded:: 0.5
        `sort` and `key` were added.
    """

    def __init__(self, base="./", charset="utf-8", sort=False, key=None):
        if not base:
            base = "./"
        self.base = base
        self.charset = charset
        self.sort = sort
        self.key = key

    def __getattr__(self, name):
        if name[:2] == "__":
            raise AttributeError(name)
        base = self.base
        if base[-1:] != "/":
            base += "/"
        return Href(url_join(base, name), self.charset, self.sort, self.key)

    def __call__(self, *path, **query):
        if path and isinstance(path[-1], dict):
            if query:
                raise TypeError("keyword arguments and query-dicts can't be combined")
            query, path = path[-1], path[:-1]
        elif query:
            query = dict(
                [(k.endswith("_") and k[:-1] or k, v) for k, v in query.items()]
            )
        path = "/".join(
            [
                to_unicode(url_quote(x, self.charset), "ascii")
                for x in path
                if x is not None
            ]
        ).lstrip("/")
        rv = self.base
        if path:
            if not rv.endswith("/"):
                rv += "/"
            rv = url_join(rv, "./" + path)
        if query:
            rv += "?" + to_unicode(
                url_encode(query, self.charset, sort=self.sort, key=self.key), "ascii"
            )
        return to_native(rv)


class Request(RequestBase):
    """ A full-featured Request/Response object.

    To better distinguish incoming and outgoing data/headers,
    incoming versions are prefixed with 'in_' in contrast to
    original Werkzeug implementation.
    """
    charset = config.charset
    encoding_errors = 'replace'
    default_mimetype = 'text/html'

    # get rid of some inherited descriptors
    headers = None

    def __init__(self, environ, populate_request=True, shallow=False, given_config=None):
        super().__init__(environ, populate_request, shallow)
        self.href = Href(self.script_root or '/', self.charset)
        self.given_config = given_config
        # self.abs_href = Href(self.url_root, self.charset)
        # self.headers = Headers([('Content-Type', 'text/html')])
        # self.response = []
        # self.status_code = 200

    # Note: we inherit a .stream attribute from RequestBase and this needs
    # to refer to the input stream because inherited functionality of werkzeug
    # base classes will access it as .stream.
    # The output stream is .out_stream (see above).
    # TODO keep request and response separate, don't mix them together

    @cached_property
    def in_headers(self):
        return EnvironHeaders(self.environ)


class TestRequest(Request):
    """ Request with customized `environ` for test purposes. """

    def __init__(self, path="/", query_string=None, method='GET',
                 content_type=None, content_length=0, form_data=None,
                 environ_overrides=None):
        """
        For parameter reference see the documentation of the werkzeug
        package, especially the functions `url_encode` and `create_environ`.
        """
        input_stream = None

        if form_data is not None:
            form_data = url_encode(form_data)
            content_type = 'application/x-www-form-urlencoded'
            content_length = len(form_data)
            input_stream = StringIO(form_data)
        environ = create_environ(path=path, query_string=query_string,
                                 method=method, input_stream=input_stream,
                                 content_type=content_type,
                                 content_length=content_length)

        environ['HTTP_USER_AGENT'] = 'MoinMoin/TestRequest'
        # must have reverse lookup or tests will be extremely slow:
        environ['REMOTE_ADDR'] = '127.0.0.1'

        if environ_overrides:
            environ.update(environ_overrides)

        super(TestRequest, self).__init__(environ)


def evaluate_request(request):
    """ Evaluate a request and returns a tuple of application iterator,
    status code and list of headers. This method is meant for testing
    purposes.
    """
    output = []
    headers_set = []

    def start_response(status, headers, exc_info=None):
        headers_set[:] = [status, headers]
        return output.append

    result = request(request.environ, start_response)

    # any output via (WSGI-deprecated) write-callable?
    if output:
        result = output
    return result, headers_set[0], headers_set[1]
