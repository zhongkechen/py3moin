"""
    MoinMoin -  This Action is used to create a supplementation subpage e.g. a Discussion page below a comon page

    Note:
    derived from the newpage macro by Vito Miliano (vito_moinnewpagewithtemplate@perilith.com) et al

    @copyright: 2006-2007 MoinMoin:ReimarBauer
    @license: GNU GPL, see COPYING for details.
"""
from MoinMoin.Page import Page
from MoinMoin.wikiutil import quoteWikinameURL


def execute(pagename, context):
    _ = context.getText
    sub_page_name = context.cfg.supplementation_page_name
    sub_page_template = context.cfg.supplementation_page_template
    newpagename = "%s/%s" % (pagename, sub_page_name)
    errormsg = _("You are not allowed to create the supplementation page.")

    if pagename.endswith(sub_page_name):  # sub_sub_page redirects to sub_page
        query = {}
        url = Page(context, pagename).url(context, query)
        context.http_redirect(url)
    elif context.user.may.read(newpagename):
        query = {}
        url = Page(context, newpagename).url(context, query)
        test = Page(context, newpagename)
        if test.exists():  # page is defined -> redirect
            context.http_redirect(url)
        elif context.user.may.write(newpagename):  # page will be created from template
            query = {'action': 'edit', 'backto': newpagename, 'template': quoteWikinameURL(sub_page_template)}
            url = Page(context, newpagename).url(context, query)
            context.http_redirect(url)
        else:
            context.theme.add_msg(errormsg, "error")
    else:
        context.theme.add_msg(errormsg, "error")
