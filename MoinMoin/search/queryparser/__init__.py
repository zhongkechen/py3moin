
"""
    MoinMoin - search query parser

    @copyright: 2005 MoinMoin:FlorianFesti,
                2005 MoinMoin:NirSoffer,
                2005 MoinMoin:AlexanderSchremmer,
                2006-2008 MoinMoin:ThomasWaldmann,
                2006 MoinMoin:FranzPletz
    @license: GNU GPL, see COPYING for details
"""

from MoinMoin import log
logging = log.getLogger(__name__)

from MoinMoin import config, wikiutil
from MoinMoin.search.queryparser.expressions import AndExpression, OrExpression, TextSearch, TitleSearch, \
    LinkSearch, CategorySearch, DomainSearch, MimetypeSearch, LanguageSearch


class QueryError(ValueError):
    """ error raised for problems when parsing the query """


class QueryParser:
    """
    Converts a String into a tree of Query objects.
    """

    def __init__(self, **kw):
        """
        @keyword titlesearch: treat all terms as title searches
        @keyword case: do case sensitive search
        @keyword regex: treat all terms as regular expressions
        """
        self.titlesearch = kw.get('titlesearch', 0)
        self.case = kw.get('case', 0)
        self.regex = kw.get('regex', 0)
        self.no_highlight = kw.get('no_highlight', 0)
        self._M = wikiutil.ParserPrefix('-')

    def _analyse_items(self, items):
        terms = AndExpression()
        M = self._M
        while items:
            item = items[0]
            items = items[1:]

            if isinstance(item, str):
                if item.lower() == 'or':
                    sub = terms.subterms()
                    if len(sub) >= 1:
                        last = sub[-1]
                        if last.__class__ == OrExpression:
                            orexpr = last
                        else:
                            # Note: do NOT reduce "terms" when it has a single subterm only!
                            # Doing that would break "-someterm" searches as we rely on AndExpression
                            # doing a "MatchAll AND_NOT someterm" for that case!
                            orexpr = OrExpression(terms)
                        terms = AndExpression(orexpr)
                    else:
                        raise QueryError('Nothing to OR')
                    remaining = self._analyse_items(items)
                    if remaining.__class__ == OrExpression:
                        for sub in remaining.subterms():
                            orexpr.append(sub)
                    else:
                        orexpr.append(remaining)
                    break
                elif item.lower() == 'and':
                    pass
                else:
                    # odd workaround; we should instead ignore this term
                    # and reject expressions that contain nothing after
                    # being parsed rather than rejecting an empty string
                    # before parsing...
                    if not item:
                        raise QueryError("Term too short")
                    regex = self.regex
                    case = self.case
                    if self.titlesearch:
                        terms.append(TitleSearch(item, use_re=regex, case=case))
                    else:
                        terms.append(TextSearch(item, use_re=regex, case=case))
            elif isinstance(item, tuple):
                negate = item[0] == M
                title_search = self.titlesearch
                regex = self.regex
                case = self.case
                no_highlight = self.no_highlight
                linkto = False
                lang = False
                category = False
                mimetype = False
                domain = False
                while len(item) > 1:
                    m = item[0]
                    if m is None:
                        raise QueryError("Invalid search prefix")
                    elif m == M:
                        negate = True
                    elif "title".startswith(m):
                        title_search = True
                    elif "regex".startswith(m):
                        regex = True
                    elif "case".startswith(m):
                        case = True
                    elif "linkto".startswith(m):
                        linkto = True
                    elif "language".startswith(m):
                        lang = True
                    elif "category".startswith(m):
                        category = True
                    elif "mimetype".startswith(m):
                        mimetype = True
                    elif "domain".startswith(m):
                        domain = True
                    elif "no_highlight".startswith(m):
                        no_highlight = True
                    else:
                        raise QueryError("Invalid search prefix")
                    item = item[1:]

                text = item[0]
                if category:
                    obj = CategorySearch(text, use_re=regex, case=case)
                elif mimetype:
                    obj = MimetypeSearch(text, use_re=regex, case=False)
                elif lang:
                    obj = LanguageSearch(text, use_re=regex, case=False)
                elif linkto:
                    obj = LinkSearch(text, use_re=regex, case=case)
                elif domain:
                    obj = DomainSearch(text, use_re=regex, case=False)
                elif title_search:
                    obj = TitleSearch(text, use_re=regex, case=case)
                else:
                    obj = TextSearch(text, use_re=regex, case=case)
                obj.negated = negate
                obj.highlight = not no_highlight
                terms.append(obj)
            elif isinstance(item, list):
                # strip off the opening parenthesis
                terms.append(self._analyse_items(item[1:]))

        # Note: do NOT reduce "terms" when it has a single subterm only!
        # Doing that would break "-someterm" searches as we rely on AndExpression
        # doing a "MatchAll AND_NOT someterm" for that case!
        return terms

    def parse_query(self, query):
        """ transform an string into a tree of Query objects """
        if isinstance(query, bytes):
            query = query.decode(config.charset)
        try:
            items = wikiutil.parse_quoted_separated_ext(query,
                                                        name_value_separator=':',
                                                        prefixes='-',
                                                        multikey=True,
                                                        brackets=('()', ),
                                                        quotes='\'"')
        except wikiutil.BracketError as err:
            raise QueryError(str(err))
        logging.debug("parse_quoted_separated items: %r" % items)
        query = self._analyse_items(items)
        logging.debug("analyse_items query: %r" % query)
        return query
