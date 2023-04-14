
"""
    MoinMoin - MoinMoin.Page Tests

    @copyright: 2007 MoinMoin:ThomasWaldmann
    @license: GNU GPL, see COPYING for details.
"""



from MoinMoin.Page import Page


class TestPage:
    def testMeta(self, req):
        page = Page(req, u'FrontPage')
        meta = page.meta
        for k, v in meta:
            if k == u'format':
                assert v == u'wiki'
            elif k == u'language':
                assert v == u'en'

    def testBody(self, req):
        page = Page(req, u'FrontPage')
        body = page.body
        assert type(body) is str
        assert 'MoinMoin' in body
        assert body.endswith('\n')
        assert '\r' not in body

    def testExists(self, req):
        assert Page(req, 'FrontPage').exists()
        assert not Page(req, 'ThisPageDoesNotExist').exists()
        assert not Page(req, '').exists()

    def testEditInfoSystemPage(self, req):
        # system pages have no edit-log (and only 1 revision),
        # thus edit_info will return None
        page = Page(req, u'RecentChanges')
        edit_info = page.edit_info()
        assert edit_info == {}

    def testSplitTitle(self, req):
        page = Page(req, u"FrontPage")
        assert page.split_title(force=True) == u'Front Page'

    def testGetRevList(self, req):
        page = Page(req, u"FrontPage")
        assert 1 in page.getRevList()

    def testGetPageLinks(self, req):
        page = Page(req, u"FrontPage")
        assert u'WikiSandBox' in page.getPageLinks(req)

    def testSendPage(self, req):
        page = Page(req, u"FrontPage")
        import io
        out = io.StringIO()
        req.redirect(out)
        page.send_page(msg=u'Done', emit_headers=False)
        result = out.getvalue()
        req.redirect()
        del out
        assert result.strip().endswith('</html>')
        assert result.strip().startswith('<!DOCTYPE HTML PUBLIC')


class TestRootPage:
    def testPageList(self, req):
        rootpage = req.rootpage
        pagelist = rootpage.getPageList()
        assert len(pagelist) > 100
        assert u'FrontPage' in pagelist
        assert u'' not in pagelist


coverage_modules = ['MoinMoin.Page']

