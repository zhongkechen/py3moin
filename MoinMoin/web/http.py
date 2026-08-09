"""
MoinMoin HTTP compatibility facade.

Application code imports HTTP primitives from this module so Werkzeug API
changes stay isolated at the WSGI boundary.
"""

from collections.abc import Mapping
from urllib.parse import (
    quote,
    quote_from_bytes,
    quote_plus,
    unquote_to_bytes,
    urlencode,
    urljoin,
    urlsplit,
)
from wsgiref.util import request_uri

from werkzeug import Request, Response, exceptions
from werkzeug.datastructures import (
    EnvironHeaders,
    Headers,
    HeaderSet,
    MultiDict,
)
from werkzeug.exceptions import (
    NotFound,
    Unauthorized,
    abort,
)
from werkzeug.formparser import parse_form_data
from werkzeug.http import http_date
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.serving import WSGIRequestHandler, run_simple
from werkzeug.test import Client, EnvironBuilder, create_environ
from werkzeug.utils import cached_property, redirect
from werkzeug.wrappers import ResponseStream


def url_quote(value, charset="utf-8", errors="strict", safe="/:"):
    """Quote text or bytes using the legacy Werkzeug URL helper contract."""
    if not isinstance(value, (str, bytes, bytearray)):
        value = str(value)
    if isinstance(value, str):
        return quote(value, safe=safe, encoding=charset, errors=errors)
    return quote_from_bytes(bytes(value), safe=safe)


def url_quote_plus(value, charset="utf-8", errors="strict", safe=""):
    """Quote a query-string component using spaces as plus signs."""
    if not isinstance(value, (str, bytes, bytearray)):
        value = str(value)
    if isinstance(value, str):
        return quote_plus(value, safe=safe, encoding=charset, errors=errors)
    return quote_plus(bytes(value), safe=safe)


def url_unquote(value, charset="utf-8", errors="replace"):
    """Unquote a URL component and decode it with the requested charset."""
    return unquote_to_bytes(value).decode(charset, errors)


def _iter_multi_items(values):
    if isinstance(values, MultiDict):
        yield from values.items(multi=True)
        return
    if isinstance(values, Mapping):
        values = values.items()
    for key, value in values:
        if isinstance(value, (list, tuple)):
            for item in value:
                yield key, item
        else:
            yield key, value


def url_encode(values, charset="utf-8", sort=False, key=None, separator="&"):
    """Encode a mapping or multi-value mapping as a query string."""
    items = [
        (item_key, value)
        for item_key, value in _iter_multi_items(values)
        if value is not None
    ]
    if sort:
        items.sort(key=key)
    return urlencode(
        items,
        doseq=False,
        encoding=charset,
        errors="strict",
    ).replace("&", separator)


def _decode_query_component(value, charset, errors):
    if isinstance(value, str):
        value = value.replace("+", " ")
    else:
        value = value.replace(b"+", b" ")
    return unquote_to_bytes(value).decode(charset, errors)


def url_decode(value, charset="utf-8", include_empty=True,
               errors="replace", separator="&", cls=MultiDict):
    """Decode a query string while preserving repeated parameter names."""
    if isinstance(value, bytes):
        separator = separator.encode("ascii")
    result = cls()
    for pair in value.split(separator):
        if not pair:
            continue
        equals = b"=" if isinstance(pair, bytes) else "="
        if equals in pair:
            item_key, item_value = pair.split(equals, 1)
        else:
            if not include_empty:
                continue
            item_key, item_value = pair, pair[:0]
        result.add(
            _decode_query_component(item_key, charset, errors),
            _decode_query_component(item_value, charset, errors),
        )
    return result


def get_current_url(environ):
    """Return the full request URL for a WSGI environment."""
    return request_uri(environ, include_query=True)


class PathInfoFromRequestUriFix:
    """Recover UTF-8 path bytes from a server's raw request URI."""

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        for key in ("REQUEST_URL", "REQUEST_URI", "UNENCODED_URL", "RAW_URI"):
            request_url = environ.get(key)
            if not request_url:
                continue
            path = unquote_to_bytes(urlsplit(request_url).path).decode("latin-1")
            script_name = environ.get("SCRIPT_NAME", "")
            if path.startswith(script_name):
                environ["PATH_INFO"] = path[len(script_name):]
                break
        return self.application(environ, start_response)


url_join = urljoin
