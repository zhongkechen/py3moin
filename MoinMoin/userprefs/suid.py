
"""
    MoinMoin - switch user form

    @copyright: 2001-2004 Juergen Hermann <jh@web.de>,
                2003-2007 MoinMoin:ThomasWaldmann
                2007      MoinMoin:JohannesBerg
    @license: GNU GPL, see COPYING for details.
"""

from past.builtins import cmp
from MoinMoin import user, util, wikiutil
from MoinMoin.widget import html
from MoinMoin.userprefs import UserPrefBase


class Settings(UserPrefBase):

    def __init__(self, request):
        """ Initialize setuid settings form. """
        UserPrefBase.__init__(self, request)
        self.request = request
        self._ = request.getText
        self.cfg = request.cfg
        _ = self._
        self.title = _("Switch user")
        self.name = 'suid'

    def allowed(self):
        return (self.request.user.auth_method in self.request.cfg.auth_can_logout and
               UserPrefBase.allowed(self) and self.request.user.isSuperUser())

    def handle_form(self):
        _ = self._
        context = self.request
        form = context.request.form

        if 'cancel' in form:
            return

        if context.request.method != 'POST':
            return

        if not wikiutil.checkTicket(context, form['ticket']):
            return

        user_name = form.get('user_name', '')
        if user_name:
            uid = user.getUserId(context, user_name)
            if uid:
                theuser = user.User(context, uid, auth_method='setuid')
            else:
                # Don't allow creating users with invalid names
                if not user.isValidName(context, user_name):
                    return 'error', _("""Invalid user name {{{'%s'}}}.
Name may contain any Unicode alpha numeric character, with optional one
space between words. Group page name is not allowed.""", wiki=True) % wikiutil.escape(user_name)
                theuser = user.User(context, auth_method='setuid')
                theuser.name = user_name
        else:
            uid = form.get('selected_user', '')
            if not uid:
                return 'error', _("No user selected")
            theuser = user.User(context, uid, auth_method='setuid')
            if not theuser or not theuser.exists():
                return 'error', _("No user selected")
        # set valid to True so superusers can even switch
        # to disable accounts
        theuser.valid = True
        context._setuid_real_user = context.user
        # now continue as the other user
        context.user = theuser
        if not uid:
            # create new user
            theuser.save()
        return _("You can now change the settings of the selected user account; log out to get back to your account.")

    def _user_select(self):
        options = []
        users = user.getUserList(self.request)
        current_uid = self.request.user.id
        for uid in users:
            if uid != current_uid:
                name = user.User(self.request, id=uid).name
                options.append((uid, name))
        options.sort(key=lambda y: y[1].lower())

        if not options:
            _ = self._
            self._only = True
            return _("You are the only user.")

        self._only = False
        size = min(10, len(options))
        return util.web.makeSelection('selected_user', options, current_uid, size=size)

    def create_form(self):
        """ Create the complete HTML form code. """
        _ = self._
        form = self.make_form(html.Text(_('As a superuser, you can temporarily '
                                          'assume the identity of another user.')))

        ticket = wikiutil.createTicket(self.request)
        self.make_row(_('User'), [html.INPUT(type="text", size="32", name="user_name")], valign="top")
        self.make_row(_('Select User'), [self._user_select()], valign="top")
        form.append(html.INPUT(type="hidden", name="ticket", value="%s" % ticket))
        if not self._only:
            buttons = [html.INPUT(type="submit", name="select_user",
                                  value=_('Select User')),
                       ' ', ]
        else:
            buttons = []
        buttons.append(html.INPUT(type="submit", name="cancel",
                                  value=_('Cancel')))
        self.make_row('', buttons)
        return str(form)
