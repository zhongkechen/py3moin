"""
    MoinMoin - Context objects which are passed thru instead of the classic
               request objects. Currently contains legacy wrapper code for
               a single request object.

    @copyright: 2008-2008 MoinMoin:FlorianKrupicka
    @license: GNU GPL, see COPYING for details.
"""
import io
import os
import sys
import time
import warnings

from werkzeug.datastructures import Headers, HeaderSet
from werkzeug.exceptions import abort, Unauthorized, NotFound
from werkzeug.test import create_environ
from werkzeug.utils import redirect

from MoinMoin import auth
from MoinMoin import i18n, user, config
from MoinMoin import log
from MoinMoin import wikiutil, xmlrpc, error
from MoinMoin.Page import Page
from MoinMoin.action import get_names, get_available_actions
from MoinMoin.config import multiconfig
from MoinMoin.decorator import EnvironProxy, context_timer
from MoinMoin.formatter import text_html
from MoinMoin.theme import load_theme_fallback
from MoinMoin.util.abuse import log_attempt
from MoinMoin.util.clock import Clock
from MoinMoin.web.exceptions import Forbidden, SurgeProtection
from MoinMoin.web.request import Request, MoinMoinFinish
from MoinMoin.web.request import ResponseBase
from MoinMoin.web.utils import UniqueIDGenerator
from MoinMoin.web.utils import check_forbidden, check_surge_protect, redirect_last_visited

logging = log.getLogger(__name__)


class Context:
    """ Standard implementation for the context interface.

    This one wraps up a Moin-Request object and the associated
    environ and also keeps track of it's changes.
    """

    def __init__(self, request):
        assert isinstance(request, Request)

        self.request = request
        self.response = ResponseBase()
        self.response.headers = Headers([('Content-Type', 'text/html')])
        self.response.response = []
        self.response.status_code = 200
        self.environ = request.environ
        self.personalities = self.environ.setdefault('context.personalities', [])
        self.personalities.append(self.__class__.__name__)

    def become(self, cls):
        """ Become another context, based on given class.

        @param cls: class to change to, must be a sister class
        @rtype: boolean
        @return: wether a class change took place
        """
        if self.__class__ is cls:
            return False
        else:
            self.personalities.append(cls)
            self.__class__ = cls
            return True

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.personalities)


class BaseContext(Context):
    """ Implements a basic context, that provides some common attributes.
    Most attributes are lazily initialized via descriptors. """

    # first the trivial attributes
    action = EnvironProxy('action', lambda o: o.request.values.get('action', 'show'))
    clock = EnvironProxy('clock', lambda o: Clock())
    user = EnvironProxy('user', lambda o: user.User(o, auth_method='request:invalid'))

    lang = EnvironProxy('lang')
    content_lang = EnvironProxy('content_lang', lambda o: o.cfg.language_default)
    current_lang = EnvironProxy('current_lang')

    html_formatter = EnvironProxy('html_formatter', lambda o: text_html.Formatter(o))
    formatter = EnvironProxy('formatter', lambda o: o.html_formatter)

    page = EnvironProxy('page', None)

    # now the more complex factories
    @EnvironProxy
    def cfg(self):
        if self.request.given_config is not None:
            return self.request.given_config('MoinMoin._tests.wikiconfig')
        return self.load_multi_cfg()

    @context_timer("load_multi_cfg")
    def load_multi_cfg(self):
        try:
            return multiconfig.getConfig(self.request.url)
        except error.NoConfigMatchedError:
            raise NotFound('<p>No wiki configuration matching the URL found!</p>')

    def getText(self):
        lang = self.lang

        def _(text, i18n=i18n, request=self, lang=lang, **kw):
            return i18n.getText(text, request, lang, **kw)

        return _

    getText = property(getText)
    _ = getText

    def isSpiderAgent(self):
        """ Simple check if useragent is a spider bot. """
        cfg = self.cfg
        user_agent = self.http_user_agent
        if user_agent and cfg.cache.ua_spiders:
            return cfg.cache.ua_spiders.search(user_agent) is not None
        return False

    isSpiderAgent = EnvironProxy(isSpiderAgent)

    def rootpage(self):
        from MoinMoin.Page import RootPage
        return RootPage(self)

    rootpage = EnvironProxy(rootpage)

    def rev(self):
        try:
            return int(self.request.values['rev'])
        except:
            return None

    rev = EnvironProxy(rev)

    def _theme(self):
        self.initTheme()
        return self.theme

    theme = EnvironProxy('theme', _theme)

    # finally some methods to act on those attributes
    def setContentLanguage(self, lang):
        """ Set the content language, used for the content div

        Actions that generate content in the user language, like search,
        should set the content direction to the user language before they
        call send_title!
        """
        self.response.content_lang = lang
        self.response.current_lang = lang

    def initTheme(self):
        """ Set theme - forced theme, user theme or wiki default """
        if self.cfg.theme_force:
            theme_name = self.cfg.theme_default
        else:
            theme_name = self.user.theme_name
        load_theme_fallback(self, theme_name)


class HTTPContext(BaseContext):
    """ Context that holds attributes and methods for manipulation of
    incoming and outgoing HTTP data. """

    session = EnvironProxy('session')
    _auth_redirected = EnvironProxy('old._auth_redirected', 0)
    cacheable = EnvironProxy('old.cacheable', 0)
    writestack = EnvironProxy('old.writestack', lambda o: list())

    # methods regarding manipulation of HTTP related data
    def read(self, n=None):
        """ Read n bytes (or everything) from input stream. """
        if n is None:
            return self.request.stream.read()
        else:
            return self.request.stream.read(n)

    def makeForbidden(self, resultcode, msg):
        status = {401: Unauthorized,
                  403: Forbidden,
                  404: NotFound,
                  503: SurgeProtection}
        raise status[resultcode](msg)

    def setHttpHeader(self, header):
        logging.warning("Deprecated call to request.setHttpHeader('k:v'), use request.headers.add/set('k', 'v')")
        header, value = header.split(':', 1)
        self.headers.add(header, value)

    def disableHttpCaching(self, level=1):
        """ Prevent caching of pages that should not be cached.

        level == 1 means disabling caching when we have a cookie set
        level == 2 means completely disabling caching (used by Page*Editor)

        This is important to prevent caches break acl by providing one
        user pages meant to be seen only by another user, when both users
        share the same caching proxy.

        AVOID using no-cache and no-store for attachments as it is completely broken on IE!

        Details: http://support.microsoft.com/support/kb/articles/Q234/0/67.ASP
        """
        if level == 1 and self.request.headers.get('Pragma') == 'no-cache':
            return

        if level == 1:
            self.response.headers['Cache-Control'] = 'private, must-revalidate, max-age=10'
        elif level == 2:
            self.response.headers['Cache-Control'] = 'no-cache'
            self.response.headers['Pragma'] = 'no-cache'
        self.response.expires = time.time() - 3600 * 24 * 365

    def http_redirect(self, url, code=302):
        """ Raise a simple redirect exception. """
        # werkzeug >= 0.6 does iri-to-uri transform if it gets unicode, but our
        # url is already url-quoted, so we better give it str to have same behaviour
        # with werkzeug 0.5.x and 0.6.x:
        url = str(url)  # if url is unicode, it should contain ascii chars only
        abort(redirect(url, code=code))

    def http_user_agent(self):
        return self.environ.get('HTTP_USER_AGENT', '')

    http_user_agent = EnvironProxy(http_user_agent)

    def http_referer(self):
        return self.environ.get('HTTP_REFERER', '')

    http_referer = EnvironProxy(http_referer)

    # the output related methods
    def write(self, *data):
        """ Write to output stream. """
        self.response.out_stream.writelines(data)

    def redirectedOutput(self, function, *args, **kw):
        """ Redirect output during function, return redirected output """
        buf = io.StringIO()
        self.redirect(buf)
        try:
            function(*args, **kw)
        finally:
            self.redirect()
        text = buf.getvalue()
        buf.close()
        return text

    def redirect(self, file=None):
        """ Redirect output to file, or restore saved output """
        if file:
            self.writestack.append(self.write)
            self.write = file.write
        else:
            self.write = self.writestack.pop()

    def send_file(self, fileobj, bufsize=8192, do_flush=None):
        """ Send a file to the output stream.

        @param fileobj: a file-like object (supporting read, close)
        @param bufsize: size of chunks to read/write
        @param do_flush: call flush after writing?
        """

        def simple_wrapper(fileobj, bufsize):
            return iter(lambda: fileobj.read(bufsize), '')

        file_wrapper = self.environ.get('wsgi.file_wrapper', simple_wrapper)
        self.response.direct_passthrough = True
        self.response.response = file_wrapper(fileobj, bufsize)
        raise MoinMoinFinish('sent file')

    # fully deprecated functions, with warnings
    def getScriptname(self):
        warnings.warn(
            "request.getScriptname() is deprecated, please use the request's script_root property.",
            DeprecationWarning)
        return self.request.script_root

    def getBaseURL(self):
        warnings.warn(
            "request.getBaseURL() is deprecated, please use the request's "
            "url_root property or the abs_href object if urls should be generated.",
            DeprecationWarning)
        return self.request.url_root

    def getQualifiedURL(self, uri=''):
        """ Return an absolute URL starting with schema and host.

        Already qualified urls are returned unchanged.

        @param uri: server rooted uri e.g /scriptname/pagename.
                    It must start with a slash. Must be ascii and url encoded.
        """
        import urllib.parse
        scheme = urllib.parse.urlparse(uri)[0]
        if scheme:
            return uri

        host_url = self.request.host_url.rstrip('/')
        result = "%s%s" % (host_url, uri)

        # This might break qualified urls in redirects!
        # e.g. mapping 'http://netloc' -> '/'
        result = wikiutil.mapURL(self, result)
        return result


class AuxilaryMixin:
    """
    Mixin for diverse attributes and methods that aren't clearly assignable
    to a particular phase of the request.
    """

    # several attributes used by other code to hold state across calls
    _fmt_hd_counters = EnvironProxy('_fmt_hd_counters')
    parsePageLinks_running = EnvironProxy('parsePageLinks_running', lambda o: {})
    mode_getpagelinks = EnvironProxy('mode_getpagelinks', 0)

    pragma = EnvironProxy('pragma', lambda o: {})
    _login_messages = EnvironProxy('_login_messages', lambda o: [])
    _login_multistage = EnvironProxy('_login_multistage', None)
    _login_multistage_name = EnvironProxy('_login_multistage_name', None)
    _setuid_real_user = EnvironProxy('_setuid_real_user', None)
    pages = EnvironProxy('pages', lambda o: {})

    def uid_generator(self):
        pagename = None
        if hasattr(self, 'page') and hasattr(self.page, 'page_name'):
            pagename = self.page.page_name
        return UniqueIDGenerator(pagename=pagename)

    uid_generator = EnvironProxy(uid_generator)

    def dicts(self):
        """ Lazy initialize the dicts on the first access """
        dicts = self.cfg.dicts(self)
        return dicts

    dicts = EnvironProxy(dicts)

    def groups(self):
        """ Lazy initialize the groups on the first access """
        groups = self.cfg.groups(self)
        return groups

    groups = EnvironProxy(groups)

    def reset(self):
        self.current_lang = self.cfg.language_default
        if hasattr(self, '_fmt_hd_counters'):
            del self._fmt_hd_counters
        if hasattr(self, 'uid_generator'):
            del self.uid_generator

    def getPragma(self, key, defval=None):
        """ Query a pragma value (#pragma processing instruction)

            Keys are not case-sensitive.
        """
        return self.pragma.get(key.lower(), defval)

    def setPragma(self, key, value):
        """ Set a pragma value (#pragma processing instruction)

            Keys are not case-sensitive.
        """
        self.pragma[key.lower()] = value


class XMLRPCContext(HTTPContext, AuxilaryMixin):
    """ Context to act during a XMLRPC request. """


class AllContext(HTTPContext, AuxilaryMixin):
    """ Catchall context to be able to quickly test old Moin code. """

    def __init__(self, request):
        super().__init__(request)
        self.clock.start('total')
        self.init()

    def finish(self):
        pass

    @staticmethod
    def set_umask(new_mask=0o777 ^ config.umask):
        """ Set the OS umask value (and ignore potential failures on OSes where
            this is not supported).
            Default: the bitwise inverted value of config.umask
        """
        try:
            old_mask = os.umask(new_mask)
        except:
            # maybe we are on win32?
            pass

    @context_timer("init")
    def init(self):
        """
        Wraps an incoming WSGI request in a Context object and initializes
        several important attributes.
        """
        self.set_umask()  # do it once per request because maybe some server
        # software sets own umask

        self.lang = self.setup_i18n_preauth()

        self.session = self.cfg.session_service.get_session(self)

        self.user = self.setup_user()

        self.lang = self.setup_i18n_postauth()

        self.reset()

    def setup_i18n_preauth(self):
        """ Determine language for the request in absence of any user info. """
        if i18n.languages is None:
            i18n.i18n_init(self)
        lang = i18n.requestLanguage(self)
        return lang

    def setup_i18n_postauth(self):
        """ Determine language for the request after user-id is established. """
        lang = i18n.userLanguage(self) or self.lang
        return lang

    def setup_user(self):
        """ Try to retrieve a valid user object from the request, be it
        either through the session or through a login. """
        # first try setting up from session
        userobj = auth.setup_from_session(self, self.session)
        userobj, olduser = auth.setup_setuid(self, userobj)
        self._setuid_real_user = olduser

        # then handle login/logout forms
        form = self.request.values

        if 'login' in form:
            params = {
                'username': form.get('name'),
                'password': form.get('password'),
                'attended': True,
                'openid_identifier': form.get('openid_identifier'),
                'stage': form.get('stage')
            }
            userobj = auth.handle_login(self, userobj, **params)
        elif 'logout' in form:
            userobj = auth.handle_logout(self, userobj)
        else:
            userobj = auth.handle_request(self, userobj)

        # if we still have no user obj, create a dummy:
        if not userobj:
            userobj = user.User(self, auth_method='invalid')

        return userobj

    @context_timer("run")
    def run(self):
        """ Run a context through the application. """
        request = self.request

        # preliminary access checks (forbidden, bots, surge protection)
        try:
            try:
                check_forbidden(self)
                check_surge_protect(self)

                action_name = self.action

                # handle XMLRPC calls
                if action_name == 'xmlrpc':
                    response = xmlrpc.xmlrpc(XMLRPCContext(request))
                elif action_name == 'xmlrpc2':
                    response = xmlrpc.xmlrpc2(XMLRPCContext(request))
                else:
                    response = self.dispatch(action_name)
                self.cfg.session_service.finalize(self, self.session)
                return response
            except MoinMoinFinish:
                return self.response
        finally:
            self.finish()

            self.clock.stop('total')
            if self.cfg.log_timing:
                dt = self.clock.timings['total']
                logging.info("timing: %s %s %s %3.3f %s", request.remote_addr, request.url, request.referrer, dt,
                             "!" * int(dt) or ".")

    def dispatch(self, action_name='show'):
        cfg = self.cfg

        # The last component in path_info is the page name, if any
        path = self.remove_prefix(self.request.path, cfg.url_prefix_action)

        if path.startswith('/'):
            pagename = wikiutil.normalize_pagename(path, cfg)
        else:
            pagename = None

        # need to inform caches that content changes based on:
        # * cookie (even if we aren't sending one now)
        # * User-Agent (because a bot might be denied and get no content)
        # * Accept-Language (except if moin is told to ignore browser language)
        hs = HeaderSet(('Cookie', 'User-Agent'))
        if not cfg.language_ignore_browser:
            hs.add('Accept-Language')
        self.response.headers['Vary'] = str(hs)

        # Handle request. We have these options:
        # 1. jump to page where user left off
        if not pagename and self.user.remember_last_visit and action_name == 'show':
            response = redirect_last_visited(self)
        # 2. handle action
        else:
            response = self.handle_action(pagename, action_name)
        if isinstance(response, Context):
            response = response.response
        return response

    def remove_prefix(self, path, prefix=None):
        """ Remove an url prefix from the path info and return shortened path. """
        # we can have all action URLs like this: /action/ActionName/PageName?action=ActionName&...
        # this is just for robots.txt being able to forbid them for crawlers
        if prefix is not None:
            prefix = '/%s/' % prefix  # e.g. '/action/'
            if path.startswith(prefix):
                # remove prefix and action name
                path = path[len(prefix):]
                action, path = (path.split('/', 1) + ['', ''])[:2]
                path = '/' + path
        return path

    def handle_action(self, pagename, action_name='show'):
        """ Actual dispatcher function for non-XMLRPC actions.

        Also sets up the Page object for this request, normalizes and
        redirects to canonical pagenames and checks for non-allowed
        actions.
        """
        _ = self.getText
        cfg = self.cfg

        # pagename could be empty after normalization e.g. '///' -> ''
        # Use localized FrontPage if pagename is empty
        if not pagename:
            self.page = wikiutil.getFrontPage(self)
        else:
            self.page = Page(self, pagename)
            if '_' in pagename and not self.page.exists():
                pagename = pagename.replace('_', ' ')
                page = Page(self, pagename)
                if page.exists():
                    url = page.url(self)
                    return self.http_redirect(url)

        msg = None
        # Complain about unknown actions
        if action_name not in get_names(cfg):
            msg = _("Unknown action %(action_name)s.") % {
                'action_name': wikiutil.escape(action_name), }

        # Disallow non available actions
        elif action_name[0].isupper() and action_name not in get_available_actions(cfg, self.page, self.user):
            msg = _("You are not allowed to do %(action_name)s on this page.") % {
                'action_name': wikiutil.escape(action_name), }
            if self.user.valid:
                log_attempt(action_name + '/action unavailable', False,
                            self.request, self.user.name, pagename=pagename)
            else:
                log_attempt(action_name + '/action unavailable', False, self.request, pagename=pagename)
                # Suggest non valid user to login
                msg += " " + _("Login and try again.")

        if msg:
            self.theme.add_msg(msg, "error")
            self.page.send_page()
        # Try action
        else:
            from MoinMoin import action
            handler = action.getHandler(self, action_name)
            if handler is None:
                msg = _("You are not allowed to do %(action_name)s on this page.") % {
                    'action_name': wikiutil.escape(action_name), }
                if self.user.valid:
                    log_attempt(action_name + '/no handler', False, self.request, self.user.name,
                                pagename=pagename)
                else:
                    log_attempt(action_name + '/no handler', False, self.request, pagename=pagename)
                    # Suggest non valid user to login
                    msg += " " + _("Login and try again.")
                self.theme.add_msg(msg, "error")
                self.page.send_page()
            else:
                handler(self.page.page_name, self)

        return self


class ScriptContext(AllContext):
    """ Context to act in scripting environments (e.g. former request_cli).

    For input, sys.stdin is used as 'wsgi.input', output is written directly
    to sys.stdout though.
    """

    def __init__(self, url=None, pagename=''):
        if url is None:
            url = 'http://localhost:0/'  # just some somehow valid dummy URL
        environ = create_environ(base_url=url)  # XXX not sure about base_url, but makes "make underlay" work
        environ['HTTP_USER_AGENT'] = 'CLI/Script'
        environ['wsgi.input'] = sys.stdin
        request = Request(environ)
        super(ScriptContext, self).__init__(request)

    def write(self, *data):
        for d in data:
            if isinstance(d, str):
                d = d.encode(config.charset)
            else:
                d = str(d)
            sys.stdout.write(d)
