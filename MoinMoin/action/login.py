"""
    MoinMoin - login action

    The real login is done in MoinMoin.request.
    Here is only some user notification in case something went wrong.

    @copyright: 2005-2006 Radomirs Cirskis <nad2000@gmail.com>,
                2006 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

from MoinMoin import userform, wikiutil
from MoinMoin.Page import Page
from MoinMoin.widget import html


def execute(pagename, context):
    return LoginHandler(pagename, context).handle()


class LoginHandler:
    def __init__(self, pagename, context):
        self.context = context
        self._ = context.getText
        self.cfg = context.cfg
        self.pagename = pagename
        self.page = Page(context, pagename)

    def handle_multistage(self):
        """Handle a multistage request.

        If the auth handler wants a multistage request, we
        now set up the login form for that.
        """
        _ = self._
        context = self.context
        form = html.FORM(method='POST', name='logincontinue', action=self.pagename)
        form.append(html.INPUT(type='hidden', name='action', value='login'))
        form.append(html.INPUT(type='hidden', name='login', value='1'))
        form.append(html.INPUT(type='hidden', name='stage',
                               value=context._login_multistage_name))

        context.theme.send_title(_("Login"), pagename=self.pagename)
        # Start content (important for RTL support)
        context.response.write(context.formatter.startContent("content"))

        extra = context._login_multistage(context, form)
        context.response.write(str(form))
        if extra:
            context.response.write(extra)

        context.response.write(context.formatter.endContent())
        context.theme.send_footer(self.pagename)
        context.theme.send_closing_html()

    def handle(self):
        _ = self._
        context = self.context
        form = context.request.values

        error = None

        islogin = form.get('login', '')

        if islogin:  # user pressed login button
            if context._login_multistage:
                return self.handle_multistage()
            if hasattr(context, '_login_messages'):
                for msg in context._login_messages:
                    context.theme.add_msg(wikiutil.escape(msg), "error")
            return self.page.send_page()

        else:  # show login form
            context.theme.send_title(_("Login"), pagename=self.pagename)
            # Start content (important for RTL support)
            context.write(context.formatter.startContent("content"))

            context.write(userform.getLogin(context))

            context.write(context.formatter.endContent())
            context.theme.send_footer(self.pagename)
            context.theme.send_closing_html()
