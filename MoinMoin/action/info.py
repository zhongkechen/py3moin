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

        paging_info_html += f.paragraph(1, css_class="searchstats info-paging-info") + _(
            "Showing page edit history entries from '''%(start_offset)d''' to '''%(end_offset)d''' out of '''%(total_count)d''' entries total.",
            wiki=True) % {
                                'start_offset': log_size - min(log_size, offset + max_count) + 1,
                                'end_offset': log_size - offset,
                                'total_count': log_size,
                            } + f.paragraph(0)

        # generating offset navigating links
        if max_count < log_size or offset != 0:
            offset_links = []
            cur_offset = max_count
            near_count = 5  # request.cfg.pagination_size

            min_offset = max(0, ((offset + max_count - 1) // max_count) - near_count)
            max_offset = min(((log_size - 1) // max_count), (offset // max_count) + near_count)
            offset_added = False

            def add_offset_link(offset, caption=None):
                offset_links.append(f.table_cell(1, css_class="info-offset-item") +
                                    page.link_to(context, on=1, querystr={
                                        'action': 'info',
                                        'offset': str(offset),
                                        'max_count': str(max_count),
                                    }, css_class="info-offset-nav-link", rel="nofollow") + f.text(
                    caption or str(log_size - offset)) + page.link_to(context, on=0) +
                                    f.table_cell(0)
                                    )

            # link to previous page - only if not at start
            if offset > 0:
                add_offset_link((((offset - 1) // max_count)) * max_count, _("Newer"))

            # link to beggining of event log - if min_offset is not minimal
            if min_offset > 0:
                add_offset_link(0)
                # adding gap only if min_offset not explicitly following beginning
                if min_offset > 1:
                    offset_links.append(
                        f.table_cell(1, css_class="info-offset-gap") + f.text(u'\u2026') + f.table_cell(0))

            # generating near pages links
            for cur_offset in range(min_offset, max_offset + 1):
                # note that current offset may be not multiple of max_count,
                # so we check whether we should add current offset marker like this
                if not offset_added and offset <= cur_offset * max_count:
                    # current info history view offset
                    offset_links.append(f.table_cell(1, css_class="info-offset-item info-cur-offset") + f.text(
                        str(log_size - offset)) + f.table_cell(0))
                    offset_added = True

                # add link, if not at this offset
                if offset != cur_offset * max_count:
                    add_offset_link(cur_offset * max_count)

            # link to the last page of event log
            if max_offset < ((log_size - 1) // max_count):
                if max_offset < ((log_size - 1) // max_count) - 1:
                    offset_links.append(
                        f.table_cell(1, css_class="info-offset-gap") + f.text(u'\u2026') + f.table_cell(0))
                add_offset_link((((log_size - 1) // max_count)) * max_count)

            # special case - if offset is greater than max_offset * max_count
            if offset > max_offset * max_count:
                offset_links.append(f.table_cell(1, css_class="info-offset-item info-cur-offset") + f.text(
                    str(log_size - offset)) + f.table_cell(0))

            # link to next page
            if offset < (log_size - max_count):
                add_offset_link((((offset + max_count) // max_count)) * max_count, _("Older"))

            # generating html
            paging_nav_html += "".join([
                f.table(1, css_class="searchpages"),
                f.table_row(1),
                "".join(offset_links),
                f.table_row(0),
                f.table(0),
            ])

    # generating max_count switcher
    # we do it only in case history_count has additional values
    if len(context.cfg.history_count) > 2:
        max_count_possibilities = list(set(context.cfg.history_count))
        max_count_possibilities.sort()
        max_count_html = []
        cur_count_added = False

        for count in max_count_possibilities:
            # max count value can be not in list of predefined values
            if max_count <= count and not cur_count_added:
                max_count_html.append("".join([
                    f.span(1, css_class="info-count-item info-cur-count"),
                    f.text(str(max_count)),
                    f.span(0),
                ]))
                cur_count_added = True

            # checking for limit_max_count to prevent showing unavailable options
            if max_count != count and count <= limit_max_count:
                max_count_html.append("".join([
                    f.span(1, css_class="info-count-item"),
                    page.link_to(context, on=1, querystr={
                        'action': 'info',
                        'offset': str(offset),
                        'max_count': str(count),
                    }, css_class="info-count-link", rel="nofollow"),
                    f.text(str(count)),
                    page.link_to(context, on=0),
                    f.span(0),
                ]))

        count_select_html += "".join([
            f.span(1, css_class="info-count-selector"),
            f.text(" ("),
            f.text(_("%s items per page")) % (
                    f.span(1, css_class="info-count-selector info-count-selector-divider") + f.text(
                " | ") + f.span(0)).join(max_count_html),
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
        Column('diff', label='<input type="submit" value="%s">' % (_("Diff"))),
        Column('editor', label=_('Editor'), hidden=not context.cfg.show_names),
        Column('comment', label=_('Comment')),
        Column('action', label=_('Action')),
    ]

    # generate history list

    def render_action(text, query, **kw):
        kw.update(dict(rel='nofollow'))
        return page.link_to(context, text, querystr=query, **kw)

    def render_file_action(text, pagename, filename, context, do):
        url = AttachFile.getAttachUrl(pagename, filename, context, do=do)
        if url:
            f = context.formatter
            link = f.url(1, url) + f.text(text) + f.url(0)
            return link

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
            actions.append(render_action(_('view'), {'action': 'recall', 'rev': '%d' % rev}))
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
            if rev > 1:
                diff += render_action(' ' + _('to previous'), {'action': 'diff', 'rev1': rev - 1, 'rev2': rev})
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
                actions.append(render_file_action(_('view'), pagename, filename, context, do='view'))
                actions.append(render_file_action(_('get'), pagename, filename, context, do='get'))
                if may_delete:
                    actions.append(render_file_action(_('del'), pagename, filename, context, do='del'))
                if may_write:
                    actions.append(render_file_action(_('edit'), pagename, filename, context, do='modify'))
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
    div.append(html.INPUT(type="hidden", name="action", value="diff"))
    div.append(history_table.render(method="GET"))

    form = html.FORM(method="GET", action="")
    if paging:
        form.append(f.div(1, css_class="info-paging-info") + paging_info_html + count_select_html + f.div(0))
        form.append("".join([
            f.div(1, css_class="info-paging-nav info-paging-nav-top"),
            paging_nav_html,
            f.div(0),
        ]))
    form.append(div)
    if paging:
        form.append("".join([
            f.div(1, css_class="info-paging-nav info-paging-nav-bottom"),
            paging_nav_html,
            f.div(0)
        ]))
    context.write(str(form))


def execute(pagename, context):
    """ show misc. infos about a page """
    if not context.user.may.read(pagename):
        Page(context, pagename).send_page()
        return

    # main function
    _ = context.getText
    page = Page(context, pagename)
    title = page.split_title()

    context.setContentLanguage(context.lang)
    f = context.formatter

    context.theme.send_title(_('Info for "%s"') % (title,), page=page)
    menu_items = [
        (_('Show "%(title)s"') % {'title': _('Revision History')},
         {'action': 'info'}),
        (_('Show "%(title)s"') % {'title': _('General Page Infos')},
         {'action': 'info', 'general': '1'}),
        (_('Show "%(title)s"') % {'title': _('Page hits and edits')},
         {'action': 'info', 'hitcounts': '1'}),
    ]
    context.write(f.div(1, id="content"))  # start content div
    context.write(f.paragraph(1))
    for text, querystr in menu_items:
        context.write("[%s] " % page.link_to(context, text=text, querystr=querystr, rel='nofollow'))
    context.write(f.paragraph(0))

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
