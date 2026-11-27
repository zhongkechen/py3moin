"""
    MoinMoin - language_setup

    The superuser gets a table of language packages listed dependent on the selected language
    for installation.

    @copyright: 2009 MoinMoin:ReimarBauer,
                     MoinMoin:ThomasWaldmnann

    @license: GNU GPL, see COPYING for details.
"""

import os
from zipfile import BadZipFile

from MoinMoin import packages, wikiutil
from MoinMoin.action import AttachFile
from MoinMoin.i18n import strings
from MoinMoin.util.dataset import TupleDataset, Column
from MoinMoin.widget.browser import DataBrowserWidget

def execute(pagename, request):
    _ = request.getText
    if not request.user or not request.user.isSuperUser():
        msg = _('Only superuser is allowed to use this action.')
        request.theme.add_msg(msg, "error")
        request.page.send_page()
        return ''
    language_setup_page = 'LanguageSetup'
    pack_dir = AttachFile.getAttachDir(request, language_setup_page)
    files = {name for name in AttachFile._get_files(request, language_setup_page)
             if name.endswith('.zip') and os.path.isfile(os.path.join(pack_dir, name))}
    available = {}
    for filename in files:
        language, separator, pageset = filename[:-4].partition('--')
        if language and separator and pageset in strings.pagesets:
            available[language, pageset] = filename
    legacy_pack = 'English_not_translated_system_pages.zip'
    if legacy_pack in files:
        available.setdefault(('English', 'not_translated_system_pages'), legacy_pack)

    if not available:
        msg = _('No page packages found.')
        request.theme.add_msg(msg, "error")
        request.page.send_page()
        return ''
    wiki_languages = sorted({language for language, _ in available})

    values = request.request.values
    lang = values.get('language') or 'English'
    target = values.get('target')
    if target:
        if wikiutil.checkTicket(request, values.get('ticket', '')):
            _install_pack(request, pack_dir, set(available.values()), target)
        else:
            msg = _('Please use the interactive user interface to use action %(actionname)s!') % {
                'actionname': 'language_setup'}
            request.theme.add_msg(msg, "error")

    data = TupleDataset()
    data.columns = [
        Column('page package', label=_('page package')),
        Column('action', label=_('install')),
    ]

    label_install = _("install")
    ticket = wikiutil.createTicket(request)
    for pageset_name in strings.pagesets:
        package_language = 'English' if pageset_name == 'not_translated_system_pages' else lang
        attachment = available.get((package_language, pageset_name))
        install_link = ''
        if attachment:
            querystr = {'action': 'language_setup', 'target': attachment, 'language': lang, 'ticket': ticket}
            install_link = request.page.link_to(request, label_install, querystr=querystr)
        data.addRow((pageset_name, install_link))

    table = DataBrowserWidget(request)
    table.setData(data)
    page_table = ''.join(table.format(method='GET'))

    fmt = request.formatter
    lang_links = [request.page.link_to_raw(request, wikiutil.escape(_lang),
                                          querystr={'action': 'language_setup', 'language': _lang})
                  for _lang in wiki_languages]

    lang_selector = u''.join([fmt.paragraph(1), _("Choose:"), ' ', ' '.join(lang_links), fmt.paragraph(0)])

    title = _("Install language packs for '%s'") % wikiutil.escape(lang)
    request.theme.send_title(title, page=request.page, pagename=pagename)
    request.write(request.formatter.startContent("content"))
    request.write(lang_selector)
    request.write(page_table)
    request.write(request.formatter.endContent())
    request.theme.send_footer(pagename)
    request.theme.send_closing_html()


def _install_pack(request, pack_dir, available, target):
    _ = request.getText
    filename = wikiutil.escape(target)
    message_type = 'error'
    try:
        if target not in available:
            raise FileNotFoundError(target)
        package = packages.ZipPackage(request, os.path.join(pack_dir, target))
        if package.isPackage():
            with package.zipfile:
                installed = package.installPackage()
            if installed:
                msg = _("Attachment '%(filename)s' installed.") % {'filename': filename}
                message_type = 'info'
            else:
                msg = _("Installation of '%(filename)s' failed.") % {'filename': filename}
                if package.msg:
                    msg += " " + wikiutil.escape(package.msg)
        else:
            msg = _('The file %s is not a MoinMoin package file.') % filename
    except FileNotFoundError:
        msg = _("Attachment '%(filename)s' does not exist!") % {'filename': filename}
    except (BadZipFile, OSError, packages.PackageException):
        msg = _("Installation of '%(filename)s' failed.") % {'filename': filename}
    request.theme.add_msg(msg, message_type)
