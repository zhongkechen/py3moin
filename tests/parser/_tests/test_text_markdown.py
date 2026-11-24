"""Verify Markdown rendering, editor previews, and compiled wiki pages.

@license: GNU GPL, see COPYING for details.
"""

from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import tarfile

import pytest

from MoinMoin import wikiutil
from MoinMoin.Page import Page
from MoinMoin.formatter.pagelinks import Formatter as PageLinksFormatter
from MoinMoin.parser.text_markdown import Parser
from MoinMoin.web.http import Client
from MoinMoin.wsgiapp import Application
from tests._tests import wikiconfig


@pytest.mark.parametrize(('source', 'expected'), [
    ('#format markdown\n# Title\n## Overview\n', '# Title\n## Overview\n'),
    ('#format markdown\n#acl All:read\n## Overview\n', '## Overview\n'),
    ('## page was renamed from OldPage\n#format markdown\n# Title\n', '# Title\n'),
    ('## Ordinary wiki comment\n= Wiki title =\n', '= Wiki title =\n'),
])
def test_processing_instructions(source, expected):
    assert wikiutil.get_processing_instructions(source)[1] == expected


@pytest.fixture
def client(tmp_path):
    files = Path(__file__).resolve().parents[3] / 'wiki'
    shutil.copytree(files / 'data', tmp_path / 'data')
    with tarfile.open(files / 'underlay.tar') as archive:
        archive.extractall(tmp_path, filter='data')

    class Config(wikiconfig.Config):
        cfg_mtime = 1
        data_dir = str(tmp_path / 'data')
        data_underlay_dir = str(tmp_path / 'underlay')
        acl_rights_default = 'All:read,write'
        surge_action_limits = {}

    return Client(Application(Config))


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'input' and 'name' in fields and 'value' in fields:
            self.values[fields['name']] = fields['value']


SOURCE = '''#format markdown
# Markdown title

<<TableOfContents>>

## A *formatted* heading

<<Verbatim(MacroBefore)>>

```python
print("Code sample")
```

<<Verbatim(MacroAfter)>>

[Home](FrontPage), [[MoinMoin:FrontPage]], [Child](/Child),
[Download](attachment:notes.txt), ![Picture](attachment:picture.png).

| Word | Its value |
| ------ | ------- |
| Alpha | 10 |

Text[^a].

[^a]: A footnote.
'''


def test_markdown_edit_preview_save_and_cache(client, tmp_path):
    url = '/MarkdownArticle'
    edit_url = url + '?action=edit&editor=text'
    form = Inputs(client.get(edit_url).get_data(as_text=True))
    fields = {'action': 'edit', 'editor': 'text', 'rev': '0',
              'ticket': form.values['ticket'], 'savetext': SOURCE}
    preview = client.post(url, data=dict(fields, button_preview='1'))
    assert preview.status_code == 200
    preview_html = preview.get_data(as_text=True).split('id="preview"', 1)[1]
    assert 'class="table-of-contents"' in preview_html
    assert 'A formatted heading</a>' in preview_html
    assert not (tmp_path / 'data/pages/MarkdownArticle/current').exists()

    saved = client.post(url, data=dict(fields, button_save='1'))
    assert saved.status_code in {200, 302, 303}
    page = client.get(url)
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'Markdown title</h1>' in html
    assert 'A <em>formatted</em> heading</h2>' in html
    assert re.search(r'href="#([^"]+)">A formatted heading</a>', html)
    assert html.index('MacroBefore') < html.index('Code sample') < html.index('MacroAfter')
    assert 'class="highlight python"' in html
    assert 'href="/FrontPage"' in html
    assert 'class="interwiki"' in html
    assert 'href="/MarkdownArticle/Child"' in html
    assert 'target=notes.txt' in html and 'target=picture.png' in html
    assert '<td>10</td>' in html and 'A footnote.' in html
    cache = tmp_path / 'data/pages/MarkdownArticle/cache/text_html'
    assert cache.is_file()
    cache_mtime = cache.stat().st_mtime_ns
    cached = client.get(url).get_data(as_text=True)
    assert cache.stat().st_mtime_ns == cache_mtime
    assert 'A formatted heading</a>' in cached and 'MacroAfter' in cached


def render(req, body, formatter_class=None):
    from MoinMoin.formatter.text_html import Formatter

    page = Page(req, 'MarkdownArticle')
    page.set_raw_body('#format markdown\n' + body, modified=True)
    req.page = page
    formatter = (formatter_class or Formatter)(req, store_pagelinks=1)
    formatter.setPage(page)
    page.formatter = req.formatter = formatter
    formatter.startContent('markdown-test')
    return req.redirectedOutput(Parser(page.data, req).format, formatter)


def test_backlinks_include_links_in_headings(req):
    render(req, '# [Read the front](FrontPage)\n\n[Help](HelpContents)\n', PageLinksFormatter)
    assert req.formatter.pagelinks == ['FrontPage', 'HelpContents']


def test_raw_html_and_unapproved_schemes_are_plain_text(req):
    result = render(req, '<b>Literal tags</b>\n\n# [Document](data:text/plain,example)\n\n'
                         '[External](https://example.test) and `<<PageCount>>`.')
    assert '&lt;b&gt;Literal tags&lt;/b&gt;' in result
    assert 'href="data:' not in result
    assert 'href="https://example.test"' in result
    assert '<code>&lt;&lt;PageCount&gt;&gt;</code>' in result


def test_extensions_may_be_disabled(req):
    req.cfg.markdown_extensions = []
    result = render(req, '| A | B |\n| - | - |\n| 1 | 2 |\n')
    assert '<table>' not in result
    assert '| A | B |' in result


def test_large_page_with_incomplete_markup_and_private_characters(req):
    sections = ''.join(f'## Section {number}\n\nContent for section {number}.\n\n' for number in range(350))
    result = render(req, sections + '\n[incomplete link\n\nPrivate characters: \ue0001\ue001\n')
    assert result.count('<h2 ') == 350
    assert '[incomplete link' in result
    assert 'Private characters: �1�' in result
