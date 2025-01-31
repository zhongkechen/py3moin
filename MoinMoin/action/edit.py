"""
    MoinMoin - edit a page

    This either calls the text or the GUI page editor.

    @copyright: 2000-2004 Juergen Hermann <jh@web.de>,
                2006 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""
from MoinMoin import wikiutil
from MoinMoin.Page import Page
from MoinMoin.util.abuse import log_attempt
from MoinMoin.web.utils import check_surge_protect


def execute(pagename, context):
    """ edit a page """
    _ = context.getText

    if 'button_preview' in context.request.form and 'button_spellcheck' in context.request.form:
        # multiple buttons pressed at once? must be some spammer/bot
        check_surge_protect(context, kick=True)  # get rid of him
        return

    if not context.user.may.write(pagename):
        log_attempt('edit/no permissions', False, context, pagename=pagename)
        page = wikiutil.getLocalizedPage(context, 'PermissionDeniedPage')
        page.body = _('You are not allowed to edit this page.')
        page.page_name = pagename
        page.send_page(send_special=True)
        return

    valideditors = ['text', 'gui', ]
    editor = ''
    if context.user.valid:
        editor = context.user.editor_default
    if editor not in valideditors:
        editor = context.cfg.editor_default

    editorparam = context.request.values.get('editor', editor)
    if editorparam == "guipossible":
        lasteditor = editor
    elif editorparam == "textonly":
        editor = lasteditor = 'text'
    else:
        editor = lasteditor = editorparam

    if context.cfg.editor_force:
        editor = context.cfg.editor_default

    # if it is still nothing valid, we just use the text editor
    if editor not in valideditors:
        editor = 'text'

    rev = context.rev or 0
    savetext = context.request.form.get('savetext')
    comment = context.request.form.get('comment', u'')
    category = context.request.form.get('category')
    rstrip = int(context.request.form.get('rstrip', '0'))
    trivial = int(context.request.form.get('trivial', '0'))

    if 'button_switch' in context.request.form:
        if editor == 'text':
            editor = 'gui'
        else:  # 'gui'
            editor = 'text'

    # load right editor class
    if editor == 'gui':
        from MoinMoin.PageGraphicalEditor import PageGraphicalEditor
        pg = PageGraphicalEditor(context, pagename)
    else:  # 'text'
        from MoinMoin.PageEditor import PageEditor
        pg = PageEditor(context, pagename)

    # is invoked without savetext start editing
    if savetext is None or 'button_load_draft' in context.request.form:
        pg.sendEditor()
        return

    # did user hit cancel button?
    cancelled = 'button_cancel' in context.request.form

    from MoinMoin.error import ConvertError
    try:
        if lasteditor == 'gui':
            # convert input from Graphical editor
            format = context.request.form.get('format', 'wiki')
            if format == 'wiki':
                converter_name = 'text_html_text_moin_wiki'
            else:
                converter_name = 'undefined'  # XXX we don't have other converters yet
            convert = wikiutil.importPlugin(context.cfg, "converter", converter_name, 'convert')
            savetext = convert(context, pagename, savetext)

        # IMPORTANT: normalize text from the form. This should be done in
        # one place before we manipulate the text.
        savetext = pg.normalizeText(savetext, stripspaces=rstrip)
    except ConvertError:
        # we don't want to throw an exception if user cancelled anyway
        if not cancelled:
            raise

    if cancelled:
        pg.sendCancel(savetext or "", rev)
        pagedir = pg.getPagePath(check_create=0)
        import os
        if not os.listdir(pagedir):
            os.removedirs(pagedir)
        return

    comment = wikiutil.clean_input(comment)

    # Add category

    # TODO: this code does not work with extended links, and is doing
    # things behind your back, and in general not needed. Either we have
    # a full interface for categories (add, delete) or just add them by
    # markup.

    if category and category != _('<No addition>'):  # opera 8.5 needs this
        # strip trailing whitespace
        savetext = savetext.rstrip()

        # Add category separator if last non-empty line contains
        # non-categories.
        lines = [line for line in savetext.splitlines() if line]
        if lines:

            # TODO: this code is broken, will not work for extended links
            # categories, e.g ["category hebrew"]
            categories = lines[-1].split()

            if categories:
                confirmed = wikiutil.filterCategoryPages(context, categories)
                if len(confirmed) < len(categories):
                    # This was not a categories line, add separator
                    savetext += u'\n----\n'

        # Add new category
        if savetext and savetext[-1] != u'\n':
            savetext += ' '
        savetext += category + u'\n'  # Should end with newline!

    if (context.cfg.edit_ticketing and
            not wikiutil.checkTicket(context, context.request.form.get('ticket', ''))):
        context.theme.add_msg(
            _('Please use the interactive user interface to use action %(actionname)s!') % {'actionname': 'edit'},
            "error")
        pg.sendEditor(preview=savetext, comment=comment, staytop=1)

    # Preview, spellcheck or spellcheck add new words
    elif ('button_preview' in context.request.form or
          'button_spellcheck' in context.request.form or
          'button_newwords' in context.request.form):
        pg.sendEditor(preview=savetext, comment=comment)

    # Preview with mode switch
    elif 'button_switch' in context.request.form:
        pg.sendEditor(preview=savetext, comment=comment, staytop=1)

    # Save new text
    else:
        try:
            from MoinMoin.security.textcha import TextCha
            if not TextCha(context).check_answer_from_form():
                raise pg.SaveError(_('TextCha: Wrong answer! Try again below...'))
            if context.cfg.comment_required and not comment:
                raise pg.SaveError(_('Supplying a comment is mandatory. Write a comment below and try again...'))
            savemsg = pg.saveText(savetext, rev, trivial=trivial, comment=comment)
        except pg.EditConflict as e:
            msg = e.message

            # Handle conflict and send editor
            pg.set_raw_body(savetext, modified=1)

            pg.mergeEditConflict(rev)
            # We don't send preview when we do merge conflict
            pg.sendEditor(msg=msg, comment=comment)
            return

        except pg.SaveError as msg:
            # Show the error message
            context.theme.add_msg(str(msg), "error")
            # And show the editor again
            pg.sendEditor(preview=savetext, comment=comment, staytop=1)
            return

        # Send new page after successful save
        context.reset()
        pg = Page(context, pagename)

        # sets revision number to default for further actions
        context.rev = 0
        context.theme.add_msg(savemsg, "info")
        pg.send_page()
