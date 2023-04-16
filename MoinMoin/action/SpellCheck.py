"""
    MoinMoin - Spelling Action

    Word adding based on code by Christian Bird <chris.bird@lineo.com>

    This action checks for spelling errors in a page using one or several
    word lists.

    MoinMoin looks for dictionary files in the directory "dict" within the
    MoinMoin package directory. To load the default UNIX word files, you
    have to manually create symbolic links to those files (usually
    '/usr/dict/words' or '/usr/share/dict/words').

    Additionally, all words on the page "LocalSpellingWords" are added to
    the list of valid words, if that page exists.

    @copyright: 2001 Richard Jones <richard@bizarsoftware.com.au>,
                2001-2004 Juergen Hermann <jh@web.de>
    @license: GNU GPL, see COPYING for details.
"""

import codecs
import os
import re

from MoinMoin import config, wikiutil
from MoinMoin.Page import Page
from MoinMoin.decorator import context_timer


def _getWordsFiles(request):
    """Check a list of possible word files"""
    candidates = []

    # load a list of possible word files
    for basedir in (request.cfg.moinmoin_dir, request.cfg.data_dir):
        localdict = os.path.join(basedir, 'dict')
        if os.path.isdir(localdict):
            candidates.extend(
                [os.path.join(localdict, fn) for fn in os.listdir(localdict)])

    # validate candidate list (leave out directories!)
    wordsfiles = []
    for f in candidates:
        if os.path.isfile(f) and os.access(f, os.F_OK | os.R_OK):
            wordsfiles.append(f)

    # return validated file list
    return wordsfiles


def _loadWords(lines, dict):
    for line in lines:
        words = line.split()
        for word in words:
            dict[word.encode(config.charset)] = ''


@context_timer("spellread")
def _loadWordsFile(request, dict, filename):
    try:
        try:
            f = codecs.open(filename, 'r', config.charset)
            lines = f.readlines()
        except UnicodeError:
            f = codecs.open(filename, 'r', 'iso-8859-1')
            lines = f.readlines()
    finally:
        f.close()
    _loadWords(lines, dict)


def _loadWordsPage(request, dict, page):
    lines = page.getlines()
    _loadWords(lines, dict)


def _loadDict(request):
    """ Load words from words files or cached dict """
    # check for "dbhash" module
    try:
        import dbm.bsd
    except ImportError:
        dbhash = None

    # load the words
    cachename = os.path.join(request.cfg.data_dir, 'cache', 'spellchecker.dict')
    if dbhash and os.path.exists(cachename):
        wordsdict = dbm.bsd.open(cachename, "r")
    else:
        wordsfiles = _getWordsFiles(request)
        if dbhash:
            wordsdict = dbm.bsd.open(cachename, 'n')
        else:
            wordsdict = {}

        for wordsfile in wordsfiles:
            _loadWordsFile(request, wordsdict, wordsfile)

        if dbhash:
            wordsdict.sync()

    return wordsdict


def _addLocalWords(context):
    from MoinMoin.PageEditor import PageEditor
    # get the new words as a string (if any are marked at all)
    try:
        newwords = context.request.form.getlist('newwords')
    except KeyError:
        # no new words checked
        return
    newwords = u' '.join(newwords)

    # get the page contents
    lsw_page = PageEditor(context, context.cfg.page_local_spelling_words)
    words = lsw_page.get_raw_body()

    # add the words to the page and save it
    if words and words[-1] != '\n':
        words = words + '\n'
    lsw_page.saveText(words + '\n' + newwords, 0)


@context_timer("spellcheck")
def checkSpelling(page, context, own_form=1):
    """ Do spell checking, return a tuple with the result.
    """
    _ = context.getText

    # first check to see if we we're called with a "newwords" parameter
    if 'button_newwords' in context.request.form:
        _addLocalWords(context)

    # load words
    wordsdict = _loadDict(context)

    localwords = {}
    lsw_page = Page(context, context.cfg.page_local_spelling_words)
    if lsw_page.exists():
        _loadWordsPage(context, localwords, lsw_page)

    # init status vars & load page
    badwords = {}
    text = page.get_raw_body()

    # checker regex and matching substitute function
    word_re = re.compile(r'([%s]?[%s]+)' % (
        config.chars_upper, config.chars_lower), re.UNICODE)

    def checkword(match, wordsdict=wordsdict, badwords=badwords,
                  localwords=localwords, num_re=re.compile(r'^\d+$', re.UNICODE)):
        word = match.group(1)
        if len(word) == 1:
            return ""
        w_enc = word.encode(config.charset)
        wl_enc = word.lower().encode(config.charset)
        if not (w_enc in wordsdict or wl_enc in wordsdict or
                w_enc in localwords or wl_enc in localwords):
            if not num_re.match(word):
                badwords[word] = 1
        return ""

    # do the checking
    for line in text.split('\n'):
        if line == '' or line[0] == '#':
            continue
        word_re.sub(checkword, line)

    if badwords:
        badwords = list(badwords.keys())
        badwords.sort(key=lambda y: y.lower())

        # build regex recognizing the bad words
        badwords_re = r'(^|(?<!\w))(%s)(?!\w)'
        badwords_re = badwords_re % ("|".join([re.escape(bw) for bw in badwords]),)
        badwords_re = re.compile(badwords_re, re.UNICODE)

        lsw_msg = ''
        if localwords:
            lsw_msg = ' ' + _('(including %(localwords)d %(pagelink)s)') % {
                'localwords': len(localwords), 'pagelink': lsw_page.link_to(context)}
        msg = _('The following %(badwords)d words could not be found in the dictionary of '
                '%(totalwords)d words%(localwords)s and are highlighted below:') % {
                  'badwords': len(badwords),
                  'totalwords': len(wordsdict) + len(localwords),
                  'localwords': lsw_msg} + "<br>"

        # figure out what this action is called
        action_name = os.path.splitext(os.path.basename(__file__))[0]

        # add a form containing the bad words
        if own_form:
            msg = msg + ('<form method="post" action="%s">\n'
                         '<input type="hidden" name="action" value="%s">\n') % (
                context.request.href(page.page_name),
                action_name)

        checkbox = '<input type="checkbox" name="newwords" value="%(word)s">%(word)s&nbsp;&nbsp;'
        msg = msg + (
                " ".join([checkbox % {'word': wikiutil.escape(w, True), } for w in badwords]) +
                '<p><input type="submit" name="button_newwords" value="%s"></p>' %
                _('Add checked words to dictionary')
        )
        if own_form:
            msg = msg + '</form>'
    else:
        badwords_re = None
        msg = _("No spelling errors found!")

    return badwords, badwords_re, msg


def execute(pagename, context):
    _ = context.getText

    page = Page(context, pagename)
    if not context.user.may.write(context.cfg.page_local_spelling_words):
        context.theme.add_msg(_("You can't save spelling words."), "error")
        page.send_page()
        return

    if context.user.may.read(pagename):
        badwords, badwords_re, msg = checkSpelling(page, context)
    else:
        badwords = []
        context.theme.add_msg(_("You can't check spelling on a page you can't read."), "error")

    context.theme.add_msg(msg, "dialog")
    if badwords:
        page.send_page(hilite_re=badwords_re)
    else:
        page.send_page()
