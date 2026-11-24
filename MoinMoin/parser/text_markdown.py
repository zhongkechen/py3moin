# -*- coding: utf-8 -*-
# Written by Claude (Anthropic AI) for Gabriele 'asbesto' Zaverio, 2026,
# as part of MoinMoin 1.11.0+md1 (Markdown support).
# MoinMoin 1.11.0+md3: protection against pages made to crash the parser or
# keep it busy (forged placeholders, unclosed brackets), by Claude.
"""
    MoinMoin - Markdown parser

    Renders pages selected with a #format markdown directive.
    Adapted from asbestomolesto/moinmoin-py3-md at ff33538e5dad917c8cd61ec488be26a59f83bbaf.

    The rendering is done by the Python-Markdown library; the parts that
    need the wiki are given to the MoinMoin formatter, so they work like in
    wiki markup pages (page cache, backlinks, LocalSiteMap, TableOfContents,
    syntax highlighting, ...):

     * [[PageName]], [[PageName|text]], [[PageName#anchor|text]]  wiki links
     * [[WikiName:PageName]], [[attachment:file.pdf|text]]          interwiki / attachment links
     * [text](PageName), [text](../SisterPage), [text](/SubPage)  links to wiki pages
     * [text](attachment:file.pdf), ![alt](attachment:image.png)   attachments
     * [text](https://example.org)                                 external links
     * <<MacroName(arguments)>>                                    MoinMoin macros
     * ```python ... ```                                           highlighted code
     * ```wiki / creole / rst / csv ... ```                        blocks in another markup
     * # / ## / ### headings                                       (also used by <<TableOfContents>>)

    Raw HTML is not rendered (it is shown as text) and only safe URL schemes
    are allowed in links, so Markdown pages cannot inject scripts.

    @license: GNU GPL, see COPYING for details.
"""

import bisect
import copy
import re
import xml.etree.ElementTree as etree

import markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor
from markdown.serializers import to_html_string

from MoinMoin import wikiutil
from MoinMoin import macro as wikimacro

Dependencies = []

# placeholders for the parts rendered by the MoinMoin formatter
# (private use unicode characters: they pass unchanged through markdown)
PH_START, PH_END = '\ue000', '\ue001'
PH_RE = re.compile(PH_START + r'([0-9]{1,10})' + PH_END)
BLOCK_PH_RE = re.compile(r'<p>\s*(' + PH_START + r'\d+' + PH_END + r')\s*</p>')
PH_TAG = 'moinph'
# stand-ins for unclosed "[" and "(" (see UnclosedBracketsPreprocessor)
OPEN_BRACKET, OPEN_PAREN = '\ue002', '\ue003'
RESTORE_BRACKETS = {ord(OPEN_BRACKET): '[', ord(OPEN_PAREN): '('}
# characters of the page text that would be taken for placeholders or
# stand-ins
FORGED_PH = {ord(PH_START): '\ufffd', ord(PH_END): '\ufffd',
             ord(OPEN_BRACKET): '\ufffd', ord(OPEN_PAREN): '\ufffd'}

# more unclosed "[" or "(" than this: they are escaped, because
# Python-Markdown needs a time that grows with the square of their number
# to find out that they do not start a link
UNCLOSED_MAX = 100

# URL schemes allowed in links and images (javascript:, data:, vbscript:, ...
# are not)
SAFE_SCHEMES = {'http', 'https', 'mailto'}
IMAGE_SCHEMES = {'http', 'https'}
UNSAFE_URL_WHITESPACE = re.compile(r'[\x00-\x20\x7f]')
SCHEME_RE = re.compile(r'^([A-Za-z][A-Za-z0-9+.\-]*):(.*)$', re.S)

# fenced blocks with these names are rendered with that MoinMoin parser
# (all the other names are languages for the syntax highlighting)
MARKUP_BLOCKS = {'wiki': 'wiki', 'moin': 'wiki', 'creole': 'creole', 'rst': 'rst', 'csv': 'csv', }

# Python-Markdown extensions used by default (wiki config: markdown_extensions)
DEFAULT_EXTENSIONS = ['tables', 'footnotes', 'def_list', 'abbr', 'sane_lists']


class _Store(object):
    """ the parts that are rendered later by the MoinMoin formatter """
    def __init__(self):
        self.items = []

    def add(self, kind, **data):
        data['kind'] = kind
        self.items.append(data)
        return '%s%d%s' % (PH_START, len(self.items) - 1, PH_END)


class FencedCodePreprocessor(Preprocessor):
    """ ```lang ... ``` and ~~~lang ... ~~~ blocks (before markdown sees them) """
    FENCE_RE = re.compile(r'^(?P<indent>[ ]{0,3})(?P<fence>`{3,}|~{3,})[ \t]*(?P<lang>[\w+#.\-]*)[^`]*$')

    def __init__(self, md, store):
        Preprocessor.__init__(self, md)
        self.store = store

    def run(self, lines):
        out = []
        i = 0
        while i < len(lines):
            m = self.FENCE_RE.match(lines[i])
            if not m:
                out.append(lines[i])
                i += 1
                continue
            fence = m.group('fence')
            lang = m.group('lang')
            code = []
            j = i + 1
            while j < len(lines):
                stripped = lines[j].strip()
                if stripped.startswith(fence[0] * len(fence)) and set(stripped) == set(fence[0]):
                    break
                code.append(lines[j])
                j += 1
            ph = self.store.add('code', lang=lang, lines=code)
            out.extend(['', ph, ''])
            i = j + 1
        return out


class UnclosedBracketsPreprocessor(Preprocessor):
    """ the "[" and "(" that are never closed, when there are a lot of them
        (only pages made on purpose have hundreds of them), are replaced by
        stand-in characters that markdown does not look at, and put back
        after the conversion: they cannot start a link anyway, and markdown
        would need a lot of time for them (also when escaped with "\\")
    """
    def run(self, lines):
        text = '\n'.join(lines)
        escape = {}
        for opening, closing, stand_in in (('[', ']', OPEN_BRACKET), ('(', ')', OPEN_PAREN)):
            if text.count(opening) - text.count(closing) <= UNCLOSED_MAX and \
               text.count(opening) <= 10 * UNCLOSED_MAX:
                continue
            stack = []
            for i, c in enumerate(text):
                if c == opening and (i == 0 or text[i - 1] != '\\'):
                    stack.append(i)
                elif c == closing and stack:
                    stack.pop()
            if len(stack) > UNCLOSED_MAX:
                escape.update(dict.fromkeys(stack, stand_in))
        if not escape:
            return lines
        chars = list(text)
        for i, stand_in in escape.items():
            chars[i] = stand_in
        return ''.join(chars).split('\n')


class ManyCodeSpansPreprocessor(Preprocessor):
    """ `code spans`: Python-Markdown needs a time that grows with the square
        of their number in a paragraph (10000 of them: about a minute). When
        a page has a lot of them (only pages made on purpose), they are taken
        out here, in linear time, and rendered by the MoinMoin formatter.
        The other pages are not changed.
    """
    BACKTICKS_RE = re.compile(r'`+')

    def __init__(self, md, store):
        Preprocessor.__init__(self, md)
        self.store = store

    def run(self, lines):
        if sum(line.count('`') for line in lines) <= 4 * UNCLOSED_MAX:
            return lines
        return [line if line.startswith(('    ', '\t')) else self._spans(line)
                for line in lines]

    def _spans(self, line):
        runs = [(m.start(), m.end()) for m in self.BACKTICKS_RE.finditer(line)]
        by_length = {}
        for i, (start, end) in enumerate(runs):
            by_length.setdefault(end - start, []).append(i)
        out = []
        pos = i = 0
        while i < len(runs):
            start, end = runs[i]
            same = by_length[end - start]
            k = bisect.bisect_right(same, i)
            if k == len(same) or (start and line[start - 1] == '\\'):
                i += 1
                continue
            j = same[k] # the closing run of backticks of the same length
            code = line[end:runs[j][0]]
            if code.strip():
                code = code.strip()
            out.append(line[pos:start])
            out.append(self.store.add('inline_code', text=code))
            pos = runs[j][1]
            i = j + 1
        out.append(line[pos:])
        return ''.join(out)


class ManyHeadingsPreprocessor(Preprocessor):
    """ a blank line after each "# heading" when a page has a lot of them
        right after each other: the tables extension of Python-Markdown looks
        at the whole rest of the block for each of them (time growing with the
        square of their number). The result is the same.
    """
    HEADING_RE = re.compile(r'^ {0,3}#{1,6}(\s|$)')

    def run(self, lines):
        if sum(1 for line in lines if line[:4].lstrip(' ')[:1] == '#') <= UNCLOSED_MAX:
            return lines
        out = []
        for line in lines:
            out.append(line)
            if self.HEADING_RE.match(line):
                out.append('')
        return out


class ManyLinksPreprocessor(Preprocessor):
    """ [text](url) links and ![alt](src) images: like for the code spans,
        Python-Markdown needs a time that grows with the square of their number
        in a paragraph. When a page has a lot of them (only pages made on
        purpose), the simple ones are taken out here, in linear time (their
        text is shown as it is, without markup). The other pages are not
        changed.
    """
    LINK_RE = re.compile(r'(!?)\[([^\[\]\n]{0,500})\]\(([^()\s]{0,1000})(?:[ \t]+"([^"\n]{0,500})")?\)')
    WIKILINK_RE = re.compile(r'\[\[([^\[\]|\n]{1,500}?)(?:\|([^\]\n]{0,500}))?\]\]')

    def __init__(self, md, parser):
        Preprocessor.__init__(self, md)
        self.parser = parser

    def run(self, lines):
        many_links = sum(line.count('](') for line in lines) > 4 * UNCLOSED_MAX
        many_wikilinks = sum(line.count('[[') for line in lines) > 4 * UNCLOSED_MAX
        if not (many_links or many_wikilinks):
            return lines
        out = []
        for line in lines:
            if not line.startswith(('    ', '\t')):
                if many_wikilinks and '[[' in line:
                    line = self.WIKILINK_RE.sub(self._wikilink, line)
                if many_links and '](' in line:
                    line = self.LINK_RE.sub(self._link, line)
            out.append(line)
        return out

    def _wikilink(self, m):
        label = m.group(2)
        return self.parser.link_placeholder(m.group(1).strip(),
                                            wikiutil.escape(label.strip()) if label is not None else None) or m.group(0)

    def _link(self, m):
        image, text, url, title = m.group(1), m.group(2), m.group(3), m.group(4)
        store = self.parser.store
        if image:
            ph = self.parser.image_placeholder(url, text, title)
            if ph is None: # external image
                ph = store.add('ext_image', src=url, alt=text, title=title)
            return ph
        label = wikiutil.escape(text) if text else None
        ph = self.parser.link_placeholder(url, label)
        if ph is None: # external link or anchor
            ph = store.add('ext_link', url=url, label=label, title=title)
        return ph


class WikiLinkProcessor(InlineProcessor):
    """ [[target]], [[target|label]] like in MoinMoin wiki markup """
    def __init__(self, pattern, md, parser):
        InlineProcessor.__init__(self, pattern, md)
        self.parser = parser

    def handleMatch(self, m, data):
        target = m.group(1).strip()
        label = m.group(2)
        label_html = wikiutil.escape(label.strip()) if label is not None else None
        placeholder = self.parser.link_placeholder(target, label_html, label)
        return placeholder, m.start(0), m.end(0)


class MacroProcessor(InlineProcessor):
    """ <<MacroName(args)>> like in MoinMoin wiki markup """
    def __init__(self, pattern, md, store):
        InlineProcessor.__init__(self, pattern, md)
        self.store = store

    def handleMatch(self, m, data):
        return (self.store.add('macro', name=m.group(1), args=m.group(2), markup=m.group(0)),
                m.start(0), m.end(0))


class MoinTreeprocessor(Treeprocessor):
    """ hand links, images, headings over to the MoinMoin formatter """
    def __init__(self, md, parser):
        Treeprocessor.__init__(self, md)
        self.parser = parser

    def _inner_html(self, el):
        """ html of the content of el (el is not modified) """
        div = copy.deepcopy(el)
        div.tag = 'div'
        div.attrib.clear()
        div.tail = None
        html = to_html_string(div)
        return html[len('<div>'):-len('</div>')]

    def _replace(self, el, placeholder):
        tail = el.tail
        el.clear()
        el.tag = PH_TAG
        el.text = placeholder
        el.tail = tail

    def run(self, root):
        for el in reversed(list(root.iter())):
            # Formatter output belongs in element content. Never interpret
            # an inline placeholder in a URL, alt text, or title attribute.
            for key, value in el.attrib.items():
                el.set(key, PH_RE.sub('', value))
            if el.tag == 'a':
                href = el.get('href', '')
                if href.startswith('#') and 'class' not in el.attrib:
                    continue # anchor in this page (also footnotes)
                if el.get('class') in ('footnote-ref', 'footnote-backref'):
                    continue
                label = self.parser.plain_text(''.join(el.itertext()))
                ph = self.parser.link_placeholder(href, self._inner_html(el) or None, label)
                if ph is not None: # wiki page, attachment, interwiki, ...
                    self._replace(el, ph)
            elif el.tag == 'img':
                ph = self.parser.image_placeholder(el.get('src', ''), el.get('alt', ''), el.get('title'))
                if ph is not None:
                    self._replace(el, ph)
            elif el.tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                text = self.parser.plain_text(''.join(el.itertext())).strip()
                ph = self.parser.store.add('heading', level=int(el.tag[1]), text=text,
                                           html=self._inner_html(el))
                self._replace(el, ph)


class MoinExtension(Extension):
    def __init__(self, parser):
        Extension.__init__(self)
        self.parser = parser

    def extendMarkdown(self, md):
        store = self.parser.store
        # no raw HTML: it is escaped and shown as text
        md.preprocessors.deregister('html_block')
        md.inlinePatterns.deregister('html')
        md.preprocessors.register(FencedCodePreprocessor(md, store), 'moin_fenced_code', 28)
        md.preprocessors.register(UnclosedBracketsPreprocessor(md), 'moin_unclosed', 27)
        md.preprocessors.register(ManyCodeSpansPreprocessor(md, store), 'moin_code_spans', 26)
        md.preprocessors.register(ManyLinksPreprocessor(md, self.parser), 'moin_links', 25)
        md.preprocessors.register(ManyHeadingsPreprocessor(md), 'moin_headings', 24)
        # higher priority than links, lower than `code spans` (190)
        md.inlinePatterns.register(
            WikiLinkProcessor(r'\[\[([^\[\]|\n]{1,500}?)(?:\|([^\]\n]{0,500}))?\]\]', md, self.parser),
            'moin_wikilink', 175)
        md.inlinePatterns.register(
            MacroProcessor(r'<<([A-Za-z_][A-Za-z0-9_]{0,100})(?:\(([^\n]{0,1000}?)\))?>>', md, store),
            'moin_macro', 174)
        # runs after all markdown tree processors (also after "unescape")
        md.treeprocessors.register(MoinTreeprocessor(md, self.parser), 'moin_tree', -10)


class Parser:
    """ Markdown parser """

    extensions = ['.md', '.markdown', ]
    caching = 1
    Dependencies = Dependencies

    def __init__(self, raw, request, **kw):
        self.raw = raw
        self.request = request
        self.form = request.request.form
        self._ = request.getText
        self.store = _Store()
        self.macro = None
        self.formatter = None
        self.pagename = ''

    # the placeholder factories -------------------------------------------

    def link_placeholder(self, target, label_html, plain_label=None):
        """ placeholder for a link to target, or None for links that markdown
            renders itself (external URLs, anchors)
        """
        target = target.strip()
        if UNSAFE_URL_WHITESPACE.search(target.split(':', 1)[0]) and ':' in target:
            return self.store.add('text', text=target, label=label_html)
        if not target:
            return None
        if target.startswith('#'):
            return None
        m = SCHEME_RE.match(target)
        if m:
            scheme, rest = m.group(1), m.group(2)
            if scheme.lower() in SAFE_SCHEMES:
                return None
            if scheme == 'attachment':
                return self.store.add('attachment_link', url=rest, label=label_html, plain_label=plain_label)
            if self._is_interwiki(scheme):
                return self.store.add('interwiki', wiki=scheme, page=rest, label=label_html, plain_label=plain_label)
            # unknown or dangerous scheme (javascript:, data:, ...): just text
            return self.store.add('text', text=target, label=label_html)
        pagename, anchor = wikiutil.split_anchor(target)
        return self.store.add('page', page=pagename, anchor=anchor, label=label_html,
                              markup=target, plain_label=plain_label)

    def image_placeholder(self, src, alt, title):
        src = src.strip()
        m = SCHEME_RE.match(src)
        if m:
            scheme, rest = m.group(1), m.group(2)
            if scheme.lower() in IMAGE_SCHEMES:
                return None # external image
            if scheme == 'attachment':
                return self.store.add('attachment_image', url=rest, alt=alt, title=title)
            return self.store.add('text', text=alt or src, label=None)
        # no scheme: an attachment of this (or another) page
        return self.store.add('attachment_image', url=src, alt=alt, title=title)

    def _is_interwiki(self, name):
        try:
            return not wikiutil.resolve_interwiki(self.request, name, '')[3]
        except (OSError, ValueError):
            return False

    # rendering -------------------------------------------------------------

    def _markdown(self):
        cfg = self.request.cfg
        configured = cfg.markdown_extensions
        extensions = list(DEFAULT_EXTENSIONS if configured is None else configured)
        extensions.append(MoinExtension(self))
        return markdown.Markdown(extensions=extensions, output_format='html')

    def format(self, formatter, **kw):
        """ Send the text. """
        self.formatter = formatter
        self.store = _Store()
        self.macro = None
        self.pagename = formatter.page.page_name
        md = self._markdown()
        # the page text cannot contain our placeholder characters
        html = md.convert(self.raw.translate(FORGED_PH))
        html = html.replace('<%s>' % PH_TAG, '').replace('</%s>' % PH_TAG, '')
        html = html.translate(RESTORE_BRACKETS)
        html = BLOCK_PH_RE.sub(r'\1', html)

        def postprocess(s):
            # labels were serialized before the markdown postprocessors ran
            for pp in md.postprocessors:
                s = pp.run(s)
            return s.translate(RESTORE_BRACKETS)

        self.request.write(formatter.div(1, css_class='markdown'))
        for fragment in self._fragments(html, postprocess):
            self.request.write(fragment)
        self.request.write(formatter.div(0))

    def plain_text(self, text):
        def label(match):
            index = int(match.group(1))
            if index >= len(self.store.items):
                return ''
            item = self.store.items[index]
            return (item.get('plain_label') or item.get('text') or item.get('markup')
                    or item.get('name') or item.get('page') or item.get('alt') or '')

        return PH_RE.sub(label, text).translate(RESTORE_BRACKETS)

    def _fragments(self, html, postprocess):
        pos = 0
        for match in PH_RE.finditer(html):
            yield self.formatter.rawHTML(html[pos:match.start()])
            index = int(match.group(1))
            if index < len(self.store.items):
                yield self._render(self.store.items[index], postprocess)
            else:
                yield self.formatter.text(match.group(0))
            pos = match.end()
        yield self.formatter.rawHTML(html[pos:])

    def _label(self, item, default, postprocess):
        if item.get('label'):
            return ''.join(self._fragments(postprocess(item['label']), postprocess))
        return self.formatter.text(default)

    def _render(self, item, postprocess):
        f = self.formatter
        kind = item['kind']
        if kind == 'page':
            page = item['page']
            if not page: # [text](#anchor) is handled by markdown, [[#anchor]] here
                return (f.anchorlink(1, item['anchor']) + self._label(item, item['markup'], postprocess) +
                        f.anchorlink(0))
            pagename = wikiutil.AbsPageName(self.pagename, page)
            return (f.pagelink(1, pagename, anchor=item['anchor']) +
                    self._label(item, item['markup'], postprocess) +
                    f.pagelink(0, pagename))
        elif kind == 'interwiki':
            page, anchor = wikiutil.split_anchor(item['page'])
            return (f.interwikilink(1, item['wiki'], page, anchor=anchor) +
                    self._label(item, '%s:%s' % (item['wiki'], item['page']), postprocess) +
                    f.interwikilink(0, item['wiki'], page))
        elif kind == 'attachment_link':
            return (f.attachment_link(1, item['url']) +
                    self._label(item, item['url'], postprocess) +
                    f.attachment_link(0))
        elif kind == 'attachment_image':
            kw = {'alt': item['alt'] or item['url']}
            if item.get('title'):
                kw['title'] = item['title']
            return f.attachment_image(item['url'], **kw)
        elif kind == 'macro':
            if self.macro is None:
                self.macro = wikimacro.Macro(self)
            return f.macro(self.macro, item['name'], item['args'], markup=item['markup'])
        elif kind == 'heading':
            level = item['level']
            start = f.heading(1, level, id=item['text'])
            if getattr(f, 'collects_headings', False):
                body = f.text(item['text'])
            else:
                body = ''.join(self._fragments(postprocess(item['html']), postprocess))
            return start + body + f.heading(0, level)
        elif kind == 'code':
            # formatter.parser() writes its output, but the caching formatter
            # returns a marker for the code it generated: it must be written
            return self._code(item['lang'], item['lines'])
        elif kind == 'text':
            return self._label(item, item['text'], postprocess)
        elif kind == 'ext_link': # safe scheme (see link_placeholder) or #anchor
            attrs = ' title="%s"' % wikiutil.escape(item['title'], 1) if item.get('title') else ''
            return (f.rawHTML('<a href="%s"%s>' % (wikiutil.escape(item['url'], 1), attrs)) +
                    self._label(item, item['url'], postprocess) + f.rawHTML('</a>'))
        elif kind == 'ext_image': # http, https, ftp (see image_placeholder)
            attrs = ' title="%s"' % wikiutil.escape(item['title'], 1) if item.get('title') else ''
            # like the images of Python-Markdown: alt, src, title
            return f.rawHTML('<img alt="%s" src="%s"%s>' % (wikiutil.escape(item['alt'] or '', 1),
                                                            wikiutil.escape(item['src'], 1), attrs))
        elif kind == 'inline_code':
            # like the code spans of Python-Markdown: <code>, escaped text
            return f.rawHTML('<code>%s</code>' % wikiutil.escape(item['text'].translate(RESTORE_BRACKETS)))
        return ''

    def _code(self, lang, lines):
        """ fenced code: a MoinMoin parser of that name (wiki, creole, rst,
            csv, ...) or syntax highlighting of that language
        """
        f = self.formatter
        lang = (lang or '').strip()
        if not lang:
            return f.parser('text', lines) or ''
        markup = MARKUP_BLOCKS.get(lang.lower())
        if markup:
            return f.parser(markup, ['#!%s' % markup] + list(lines)) or ''
        return f.parser('highlight', ['#!highlight %s' % lang] + list(lines)) or ''
