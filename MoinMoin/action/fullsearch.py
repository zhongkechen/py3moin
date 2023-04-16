"""
    MoinMoin - fullsearch action

    This is the backend of the search form. Search pages and print results.

    @copyright: 2001 by Juergen Hermann <jh@web.de>
    @license: GNU GPL, see COPYING for details.
"""

import re
import time

from parsedatetime import Calendar

from MoinMoin import wikiutil
from MoinMoin.Page import Page
from MoinMoin.web.utils import check_surge_protect


def checkTitleSearch(context):
    """ Return 1 for title search, 0 for full text search, -1 for idiot spammer
        who tries to press all buttons at once.

    When used in FullSearch macro, we have 'titlesearch' parameter with
    '0' or '1'. In standard search, we have either 'titlesearch' or
    'fullsearch' with localized string. If both missing, default to
    True (might happen with Safari) if this isn't an advanced search.
"""
    form = context.request.values
    if 'titlesearch' in form and 'fullsearch' in form:
        ret = -1  # spammer / bot
    else:
        try:
            ret = int(form['titlesearch'])
        except ValueError:
            ret = 1
        except KeyError:
            ret = ('fullsearch' not in form and not isAdvancedSearch(context)) and 1 or 0
    return ret


def isAdvancedSearch(context):
    """ Return True if advanced search is requested """
    try:
        return int(context.request.values['advancedsearch'])
    except KeyError:
        return False


def searchHints(f, hints):
    """ Return a paragraph showing hints for a search

    @param f: the formatter to use
    @param hints: list of hints (as strings) to show
    """
    return ''.join([
        f.paragraph(1, attr={'class': 'searchhint'}),
        # this is illegal formatter usage anyway, so we can directly use a literal
        "<br>".join(hints),
        f.paragraph(0),
    ])


def execute(pagename, context, fieldname='value', titlesearch=0, statistic=0):
    _ = context.getText
    titlesearch = checkTitleSearch(context)
    if titlesearch < 0:
        check_surge_protect(context, kick=True)  # get rid of spammer
        return

    advancedsearch = isAdvancedSearch(context)

    form = context.request.values

    # context is relevant only for full search
    if titlesearch:
        context = 0
    elif advancedsearch:
        context = 180  # XXX: hardcoded context count for advancedsearch
    else:
        context = int(form.get('context', 0))

    # Get other form parameters
    needle = form.get(fieldname, '')
    case = int(form.get('case', 0))
    regex = int(form.get('regex', 0))  # no interface currently
    hitsFrom = int(form.get('from', 0))
    highlight_titles = int(form.get('highlight_titles', 1))
    highlight_pages = int(form.get('highlight_pages', 1))
    mtime = None
    msg = ''
    historysearch = 0

    # if advanced search is enabled we construct our own search query
    if advancedsearch:
        and_terms = form.get('and_terms', '').strip()
        or_terms = form.get('or_terms', '').strip()
        not_terms = form.get('not_terms', '').strip()
        # xor_terms = form.get('xor_terms', '').strip()
        categories = form.getlist('categories') or ['']
        timeframe = form.get('time', '').strip()
        language = form.getlist('language') or ['']
        mimetype = form.getlist('mimetype') or [0]
        excludeunderlay = form.get('excludeunderlay', 0)
        nosystemitems = form.get('nosystemitems', 0)
        historysearch = form.get('historysearch', 0)

        mtime = form.get('mtime', '')
        if mtime:
            mtime_parsed = None

            # get mtime from known date/time formats
            for fmt in (context.user.datetime_fmt,
                        context.cfg.datetime_fmt, context.user.date_fmt,
                        context.cfg.date_fmt):
                try:
                    mtime_parsed = time.strptime(mtime, fmt)
                except ValueError:
                    continue
                else:
                    break

            if mtime_parsed:
                mtime = time.mktime(mtime_parsed)
            else:
                # didn't work, let's try parsedatetime
                cal = Calendar()
                mtime_parsed, parsed_what = cal.parse(mtime)
                # XXX it is unclear if usage of localtime here and in parsedatetime module is correct.
                # time.localtime is the SERVER's local time and of no relevance to the user (being
                # somewhere in the world)
                # mktime is reverse function for localtime, so this maybe fixes it again!?
                if parsed_what > 0 and mtime_parsed <= time.localtime():
                    mtime = time.mktime(mtime_parsed)
                else:
                    mtime_parsed = None  # we don't use invalid stuff

            # show info
            if mtime_parsed:
                # XXX mtime_msg is not shown in some cases
                mtime_msg = _("(!) Only pages changed since '''%s''' are being displayed!",
                              wiki=True) % context.user.getFormattedDateTime(mtime)
            else:
                mtime_msg = _('/!\\ The modification date you entered was not '
                              'recognized and is therefore not considered for the '
                              'search results!', wiki=True)
        else:
            mtime_msg = None

        word_re = re.compile(r'(\"[\w\s]+"|\w+)', re.UNICODE)
        needle = ''
        if categories[0]:
            needle += 'category:%s ' % ','.join(categories)
        if language[0]:
            needle += 'language:%s ' % ','.join(language)
        if mimetype[0]:
            needle += 'mimetype:%s ' % ','.join(mimetype)
        if excludeunderlay:
            needle += '-domain:underlay '
        if nosystemitems:
            needle += '-domain:system '
        if and_terms:
            needle += '(%s) ' % and_terms
        if not_terms:
            needle += '(%s) ' % ' '.join(['-%s' % t for t in word_re.findall(not_terms)])
        if or_terms:
            needle += '(%s) ' % ' or '.join(word_re.findall(or_terms))

    # check for sensible search term
    stripped = needle.strip()
    if len(stripped) == 0:
        context.theme.add_msg(_('Please use a more selective search term instead '
                                'of {{{"%s"}}}', wiki=True) % wikiutil.escape(needle), "error")
        Page(context, pagename).send_page()
        return
    needle = stripped

    # Setup for type of search
    if titlesearch:
        title = _('Title Search: "%s"')
        sort = 'page_name'
    else:
        if advancedsearch:
            title = _('Advanced Search: "%s"')
        else:
            title = _('Full Text Search: "%s"')
        sort = 'weight'

    # search the pages
    from MoinMoin.search import searchPages, QueryParser, QueryError
    try:
        query = QueryParser(case=case, regex=regex,
                            titlesearch=titlesearch).parse_query(needle)
    except QueryError:  # catch errors in the search query
        context.theme.add_msg(_('Your search query {{{"%s"}}} is invalid. Please refer to '
                                'HelpOnSearching for more information.', wiki=True, percent=True) % wikiutil.escape(
            needle), "error")
        Page(context, pagename).send_page()
        return

    results = searchPages(context, query, sort, mtime, historysearch)

    # directly show a single hit for title searches
    # this is the "quick jump" functionality if you don't remember
    # the pagename exactly, but just some parts of it
    if titlesearch and len(results.hits) == 1:
        page = results.hits[0]
        if not page.attachment:  # we did not find an attachment
            page = Page(context, page.page_name)
            querydict = {}
            if highlight_pages:
                highlight = query.highlight_re()
                if highlight:
                    querydict.update({'highlight': highlight})
            url = page.url(context, querystr=querydict)
            context.http_redirect(url)
            return
    if not results.hits:  # no hits?
        f = context.formatter
        querydict = wikiutil.parseQueryString(context.query_string).to_dict()
        querydict.update({'titlesearch': 0})

        context.theme.add_msg(_('Your search query {{{"%s"}}} didn\'t return any results. '
                                'Please change some terms and refer to HelpOnSearching for '
                                'more information.%s', wiki=True, percent=True) % (wikiutil.escape(needle),
                                                                                   titlesearch and ''.join([
                                                                                       '<br>',
                                                                                       _('(!) Consider performing a',
                                                                                         wiki=True), ' ',
                                                                                       f.url(1, href=context.page.url(
                                                                                           context, querydict,
                                                                                           escape=0)),
                                                                                       _('full-text search with your search terms'),
                                                                                       f.url(0), '.',
                                                                                   ]) or ''), "error")
        Page(context, pagename).send_page()
        return

    # This action generates data using the user language
    context.setContentLanguage(context.lang)

    context.theme.send_title(title % needle, pagename=pagename)

    # Start content (important for RTL support)
    context.write(context.formatter.startContent("content"))

    # Hints
    f = context.formatter
    hints = []

    if titlesearch:
        querydict = wikiutil.parseQueryString(context.request.query_string).to_dict()
        querydict.update({'titlesearch': 0})

        hints.append(''.join([
            _("(!) You're performing a title search that might not include"
              ' all related results of your search query in this wiki. <<BR>>', wiki=True),
            ' ',
            f.url(1, href=context.page.url(context, querydict, escape=0)),
            f.text(_('Click here to perform a full-text search with your '
                     'search terms!')),
            f.url(0),
        ]))

    if advancedsearch and mtime_msg:
        hints.append(mtime_msg)

    if hints:
        context.write(searchHints(f, hints))

    # Search stats
    context.write(results.stats(context, context.formatter, hitsFrom))

    # Then search results
    info = not titlesearch
    if context:
        output = results.pageListWithContext(context, context.formatter,
                                             info=info, context=context, hitsFrom=hitsFrom, hitsInfo=1,
                                             highlight_titles=highlight_titles,
                                             highlight_pages=highlight_pages)
    else:
        output = results.pageList(context, context.formatter, info=info,
                                  hitsFrom=hitsFrom, hitsInfo=1,
                                  highlight_titles=highlight_titles,
                                  highlight_pages=highlight_pages)

    context.write(output)

    context.write(context.formatter.endContent())
    context.theme.send_footer(pagename)
    context.theme.send_closing_html()
