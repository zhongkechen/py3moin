
"""
    MoinMoin - MoinMoin.formatter.groups Tests

    @copyright: 2009 by MoinMoin:DmitrijsMilajevs
    @license: GNU GPL, see COPYING for details.
"""

from  MoinMoin.formatter.groups import Formatter
from MoinMoin.Page import Page
from tests._tests import become_trusted, create_page, nuke_page

class TestGroupFormatterWikiMarkup:

    def get_members(self, req, text):
        request = req
        formatter = Formatter(req)

        become_trusted(request)
        create_page(request, u'TestPageGroup', text)
        page = Page(request, 'TestPageGroup', formatter=formatter)
        page.send_page(content_only=True)
        nuke_page(request, u'TestPageGroup')

        return formatter.members

    def test_CamelCase(self, req):
        text = """
 * CamelCase
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'CamelCase' in members

    def test_extended_name(self, req):
        text = """
 * extended name
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'extended name' in members

    def test_extended_link(self, req):
        text = """
 * [[extended link]]
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'extended link' in members

    def test_extended_link_with_label(self, req):
        text = """
 * [[extended link| label]]
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'extended link' in members

    def test_ignore_not_first_level_list(self, req):
        text = """
 * first level
  * second level
   * [[SomeLink]]
    * forth level
     * and then some...
 * again first level
"""
        members = self.get_members(req, text)
        assert len(members) == 2
        assert 'first level' in members
        assert 'again first level' in members

    def test_indented_list(self, req):
        text = """
    * first level
     * second level
      * [[SomeLink|label]]
       * forth level
        * and then some...
    * again first level
"""
        members = self.get_members(req, text)
        assert len(members) == 2
        assert 'first level' in members
        assert 'again first level' in members

    def test_ignore_other(self, req):
        text = """
= ignore this =
 * take this

Ignore previous line and this text.
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'take this' in members

    def test_strip_whitespace(self, req):
        text = """
 *   take this
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'take this' in members


class TestGroupFormatterCreole:

    def get_members(self, req, text):
        request = req
        formatter = Formatter(req)

        become_trusted(request)
        create_page(request, u'TestPageGroup', "#FORMAT creole \n" + text)
        page = Page(request, 'TestPageGroup', formatter=formatter)
        page.send_page(content_only=True)
        nuke_page(request, u'TestPageGroup')

        return formatter.members

    def test_CamelCase(self, req):
        text = """
 * CamelCase
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'CamelCase' in members

    def test_extended_name(self, req):
        text = """
 * extended name
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'extended name' in members

    def test_extended_link(self, req):
        text = """
 * [[extended link]]
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'extended link' in members

    def test_extended_link_with_label(self, req):
        text = """
 * [[FrontPage|named link]]
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'FrontPage' in members

    def test_ignore_not_first_level_list(self, req):
        text = """
* first level
** second level
*** [[SomeLink]]
**** forth level
***** and then some...
* again first level
"""
        members = self.get_members(req, text)
        assert len(members) == 2
        assert 'first level' in members
        assert 'again first level' in members

    def test_indented_list(self, req):
        text = """
    * first level
    ** second level
    *** [[SomeLink|label]]
    **** forth level
    ***** and then some...
    * again first level
"""
        members = self.get_members(req, text)
        assert len(members) == 2
        assert 'first level' in members
        assert 'again first level' in members

    def test_ignore_other(self, req):
        text = """
= ignore this =
 * take this

Ignore previous line and this text.
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'take this' in members

    def test_strip_whitespace(self, req):
        text = """
 *   take this
"""
        members = self.get_members(req, text)
        assert len(members) == 1
        assert u'take this' in members


coverage_modules = ['MoinMoin.formtter.groups']
