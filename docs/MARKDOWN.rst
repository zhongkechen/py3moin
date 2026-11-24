Markdown pages
==============

Use the text editor and start the page with ``#format markdown``. A fresh
instance includes ``MarkdownTemplate`` among its page templates. Existing
instances can copy the `template source`_ into a page of that name.
Pages without a format directive continue to use the wiki's configured
``default_markup``.

.. _template source: ../wiki/data/pages/MarkdownTemplate/revisions/00000001

Headings, lists, emphasis, block quotes, inline code and fenced code use
Python-Markdown syntax. Use ``<<TableOfContents>>`` to link to headings.
Fence languages such as ``python`` use the wiki's syntax highlighter.

- ``[[FrontPage|Home]]`` and ``[Home](FrontPage)`` are page links.
- ``[Child](/SubPage)`` and ``[Sibling](../SiblingPage)`` follow wiki-relative paths.
- ``[[MoinMoin:FrontPage]]`` resolves through the site's interwiki map.
- ``[Download](attachment:notes.txt)`` links to an attachment.
- ``![Diagram](attachment:diagram.png)`` displays an image attachment.
- ``<<MacroName(arguments)>>`` calls a wiki macro outside code spans and blocks.

External links use ``http``, ``https``, or ``mailto``. External images use
``http`` or ``https``. Raw HTML is displayed as text. Unknown URL schemes
render as text. The graphical editor handles the native wiki format, so
use the text editor to make changes to Markdown pages.

Tables, footnotes, definition lists, abbreviations and sane lists are
enabled by default. Override the extension list in ``wikiconfig.py``.
For example, set ``markdown_extensions = ['tables', 'footnotes']`` to
keep only those extensions, or ``markdown_extensions = []`` for base
Markdown. Restart the wiki and run ``moin maint cleancache`` after changing
extensions so saved pages are recompiled.
