"""
    MoinMoin - info action

    Displays page history, some general page infos and statistics.

    @copyright: 2000-2004 Juergen Hermann <jh@web.de>,
                2006-2008 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""

import hashlib

from MoinMoin import config, wikiutil, action
from MoinMoin.Page import Page
from MoinMoin.action import AttachFile
from MoinMoin.logfile import editlog
from MoinMoin.widget import html


def general(page, pagename, context):
    _ = context.getText
    f = context.formatter

    context.write(f.heading(1, 1),
                  f.text(_('General Information')),
                  f.heading(0, 1))

    context.write(f.paragraph(1),
                  f.text(_("Page size: %d") % page.size()),
                  f.paragraph(0))

    digest = hashlib.new('sha1', page.get_raw_body().encode(config.charset)).hexdigest().upper()
    context.write(f.paragraph(1),
                  f.rawHTML('%(label)s <tt>%(value)s</tt>' % {
                      'label': _("SHA digest of this page's content is:"),
                      'value': digest, }),
                  f.paragraph(0))

    # show attachments (if allowed)
    attachment_info = action.getHandler(context, 'AttachFile', 'info')
    if attachment_info:
        context.write(attachment_info(pagename, context))

    # show subscribers
    subscribers = page.getSubscribers(context, include_self=1, return_users=1)
    if subscribers:
        context.write(f.paragraph(1))
        context.write(f.text(_('The following users subscribed to this page:')))
        for lang in subscribers:
            context.write(f.linebreak(), f.text('[%s] ' % lang))
            for user in subscribers[lang]:
                # do NOT disclose email addr, only WikiName
                userhomepage = Page(context, user.name)
                if userhomepage.exists():
                    context.write(f.rawHTML(userhomepage.link_to(context) + ' '))
                else:
                    context.write(f.text(user.name + ' '))
        context.write(f.paragraph(0))

    # show links
    links = page.getPageLinks(context)
    if links:
        context.write(f.paragraph(1))
        context.write(f.text(_('This page links to the following pages:')))
        context.write(f.linebreak())
        for linkedpage in links:
            context.write(
                f.rawHTML("%s%s " % (Page(context, linkedpage).link_to(context), ",."[linkedpage == links[-1]])))
        context.write(f.paragraph(0))


def history(page, pagename, context):
    # show history as default
    _ = context.getText
    default_count, limit_max_count = context.cfg.history_count[0:2]
    paging = context.cfg.history_paging

    try:
        max_count = int(context.request.values.get('max_count', default_count))
    except ValueError:
        max_count = default_count
    max_count = max(1, min(max_count, limit_max_count))

    # read in the complete log of this page
    log = editlog.EditLog(context, rootpagename=pagename)

    offset = 0
    paging_info_html = ""
    paging_nav_html = ""
    count_select_html = ""

    f = context.formatter

    if paging:
        log_size = log.lines()

        try:
            offset = int(context.request.values.get('offset', 0))
        except ValueError:
            offset = 0
        offset = max(min(offset, log_size - 1), 0)

        # The buttons say which way to move; the form carries the current
        # offset. Adjust it before rendering the summary and history rows.
        offsetmove = context.request.values.get('offsetmove', u'')
        if offsetmove == u'newer':
            offset = ((offset - 1) // max_count) * max_count
        elif offsetmove == u'older':
            offset = ((offset + max_count) // max_count) * max_count
        offset = max(min(offset, log_size - 1), 0)

        paging_info_html += f.paragraph(1, css_class="searchstats info-paging-info") + _(
            "Showing page edit history entries from '''%(start_offset)d''' to '''%(end_offset)d''' out of '''%(total_count)d''' entries total.",
            wiki=True) % {
                'start_offset': log_size - min(log_size, offset + max_count) + 1,
                'end_offset': log_size - offset,
                'total_count': log_size,
            } + f.paragraph(0)

        # Use form buttons so crawlers do not discover a URL for every page of
        # the history listing.
        if max_count < log_size or offset != 0:
            def offset_button(direction, caption, enabled):
                return '<button type="submit" name="offsetmove" value="%s"%s>%s</button> ' % (
                    direction,
                    not enabled and ' disabled="disabled"' or '',
                    wikiutil.escape(caption))

            paging_nav_html += (
                offset_button('newer', _("Newer"), offset > 0) +
                offset_button('older', _("Older"), offset < (log_size - max_count)))

        # Use a select in the paging form instead of one link per page size.
        if len(context.cfg.history_count) > 2:
            max_count_possibilities = sorted(set(context.cfg.history_count))
            max_count_html = []
            cur_count_added = False

            for count in max_count_possibilities:
                if max_count <= count and not cur_count_added:
                    max_count_html.append('<option value="%d" selected="selected">%d</option>'
                                          % (max_count, max_count))
                    cur_count_added = True

                if max_count != count and count <= limit_max_count:
                    max_count_html.append('<option value="%d">%d</option>' % (count, count))

            count_select_html += "".join([
                f.span(1, css_class="info-count-selector"),
                f.text(" ("),
                f.text(_("%s items per page")) % (
                    '<select name="max_count" class="info-count-select">%s</select>'
                    % "".join(max_count_html)),
                f.rawHTML(' <button type="submit">%s</button>' % wikiutil.escape(_("Do"))),
                f.text(")"),
                f.span(0),
            ])

    # open log for this page
    from MoinMoin.util.dataset import TupleDataset, Column

    history = TupleDataset()
    history.columns = [
        Column('rev', label='#', align='right'),
        Column('mtime', label=_('Date'), align='right'),
        Column('size', label=_('Size'), align='right'),
        Column('diff', label='<button type="submit" name="action" value="diff">%s</button>' % (_("Diff"))),
        Column('editor', label=_('Editor'), hidden=not context.cfg.show_names),
        Column('comment', label=_('Comment')),
        Column('action', label='<button type="submit" name="action" value="info">%s</button>' % (_("Do"))),
    ]

    # Row actions are radio buttons in the history form, keeping their target
    # URLs out of crawler-visible links.
    def render_action(text, value):
        return '<input type="radio" name="rowaction" value="%s">%s' % (
            wikiutil.escape(value, True), wikiutil.escape(text))

    def render_file_action(text, filename, do):
        if AttachFile.get_action(context, filename, do):
            return render_action(text, u'AttachFile:%s:%s' % (do, filename))

    may_write = context.user.may.write(pagename)
    may_delete = context.user.may.delete(pagename)

    count = 0
    pgactioncount = 0
    for line in log.reverse():
        count += 1

        if paging and count <= offset:
            continue

        rev = int(line.rev)
        actions = []
        if line.action in ('SAVE', 'SAVENEW', 'SAVE/REVERT', 'SAVE/RENAME',):
            size = page.size(rev=rev)
            actions.append(render_action(_('view'), u'recall:%d' % rev))
            if pgactioncount == 0:
                rchecked = ' checked="checked"'
                lchecked = ''
            elif pgactioncount == 1:
                lchecked = ' checked="checked"'
                rchecked = ''
            else:
                lchecked = rchecked = ''
            diff = '<input type="radio" name="rev1" value="%d"%s><input type="radio" name="rev2" value="%d"%s>' % (
                rev, lchecked, rev, rchecked)
            comment = line.comment
            if not comment:
                if '/REVERT' in line.action:
                    comment = _("Revert to revision %(rev)d.") % {'rev': int(line.extra)}
                elif '/RENAME' in line.action:
                    comment = _("Renamed from '%(oldpagename)s'.") % {'oldpagename': line.extra}
            pgactioncount += 1
        else:  # ATT*
            rev = '-'
            diff = '-'

            filename = wikiutil.url_unquote(line.extra)
            comment = "%s: %s %s" % (line.action, filename, line.comment)
            if AttachFile.exists(context, pagename, filename):
                size = AttachFile.size(context, pagename, filename)
                actions.append(render_file_action(_('view'), filename, 'view'))
                actions.append(render_file_action(_('get'), filename, 'get'))
                if may_delete:
                    actions.append(render_file_action(_('del'), filename, 'del'))
                if may_write:
                    actions.append(render_file_action(_('edit'), filename, 'modify'))
            else:
                size = 0

        history.addRow((
            rev,
            context.user.getFormattedDateTime(wikiutil.version2timestamp(line.ed_time_usecs)),
            str(size),
            diff,
            line.getEditor(context) or _("N/A"),
            wikiutil.escape(comment) or '&nbsp;',
            "&nbsp;".join(a for a in actions if a),
        ))
        if (count >= max_count + offset) or (paging and count >= log_size):
            break

    # print version history
    from MoinMoin.widget.browser import DataBrowserWidget

    context.write(str(html.H2().append(_('Revision History'))))

    if not count:  # there was no entry in logfile
        context.write(_('No log entries found.'))
        return

    history_table = DataBrowserWidget(context)
    history_table.setData(history)

    div = html.DIV(id="page-history")
    div.append(history_table.render(method="GET"))

    # Paging controls live in forms beside the table form. Their hidden inputs
    # carry the current position while each button says what to change.
    def paging_form(css_class, content, hidden_max_count=False):
        return "".join([
            '<form method="GET" action="">',
            f.div(1, css_class=css_class),
            '<input type="hidden" name="action" value="info">',
            '<input type="hidden" name="offset" value="%d">' % offset,
            hidden_max_count and '<input type="hidden" name="max_count" value="%d">' % max_count or '',
            content,
            f.div(0),
            '</form>',
        ])

    if paging:
        context.write(paging_form("info-paging-info",
                                  paging_info_html + count_select_html))

    context.write(str(div))

    if paging:
        context.write(paging_form("info-paging-nav info-paging-nav-bottom",
                                  paging_nav_html, hidden_max_count=True))


def execute(pagename, context):
    """ show misc. infos about a page """
    if not context.user.may.read(pagename):
        Page(context, pagename).send_page()
        return

    # main function
    _ = context.getText
    page = Page(context, pagename)

    # Resolve a selected history row action through a fixed set of local
    # actions, then redirect to the generated URL.
    rowaction = context.request.values.get('rowaction', u'')
    if rowaction:
        what = rowaction.split(u':', 2)
        url = None
        if len(what) == 2 and what[0] == u'recall' and what[1].isdigit():
            url = page.url(context, querystr={'action': 'recall', 'rev': str(int(what[1]))})
        elif len(what) == 3 and what[0] == u'AttachFile' and what[1] in ('view', 'get', 'del', 'modify'):
            url = AttachFile.getAttachUrl(pagename, what[2], context, do=what[1])
        if url:
            context.http_redirect(url)
            return

    title = page.split_title()

    context.setContentLanguage(context.lang)
    f = context.formatter

    context.theme.send_title(_('Info for "%s"') % (title,), page=page)
    menu_items = [
        (_('Show "%(title)s"') % {'title': _('Revision History')}, None),
        (_('Show "%(title)s"') % {'title': _('General Page Infos')}, 'general'),
        (_('Show "%(title)s"') % {'title': _('Page hits and edits')}, 'hitcounts'),
    ]
    context.write(f.div(1, id="content"))  # start content div
    context.write(f.rawHTML('<form method="GET" action="%s"><div>'
                            '<input type="hidden" name="action" value="info">'
                            % wikiutil.escape(page.url(context), True)))
    for text, name in menu_items:
        if name:
            button = '<button type="submit" name="%s" value="1">%s</button> ' % (
                name, wikiutil.escape(text))
        else:
            button = '<button type="submit">%s</button> ' % wikiutil.escape(text)
        context.write(f.rawHTML(button))
    context.write(f.rawHTML('</div></form>'))

    show_hitcounts = int(context.request.values.get('hitcounts', 0)) != 0
    show_general = int(context.request.values.get('general', 0)) != 0

    if show_hitcounts:
        from MoinMoin.stats import hitcounts
        context.write(hitcounts.linkto(pagename, context, 'page=' + wikiutil.url_quote(pagename)))
    elif show_general:
        general(page, pagename, context)
    else:
        history(page, pagename, context)

    context.write(f.div(0))  # end content div
    context.theme.send_footer(pagename)
    context.theme.send_closing_html()
