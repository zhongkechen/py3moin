"""Render MonthCalendar against the current HTTP context request boundary."""

import calendar
import html
import re
from html.parser import HTMLParser
from types import SimpleNamespace
from urllib.parse import parse_qs, quote, urlencode, urlsplit

import pytest

from MoinMoin.macro import MonthCalendar
from MoinMoin.web.contexts import AllContext
from MoinMoin.web.request import TestRequest as WikiTestRequest


class CalendarContext(AllContext):
    def init(self):
        # Keep the real request/context API without opening a wiki or session.
        pass

    def getText(self, text, **kwargs):
        return text


class CalendarPage:
    def __init__(self, context, page_name):
        self.context = context
        self.page_name = page_name

    def exists(self):
        return self.page_name in self.context.page_bodies

    def get_raw_body(self):
        return self.context.page_bodies[self.page_name]

    def url(self, context, query=None):
        result = '/' + quote(self.page_name)
        if query:
            result += '?' + (urlencode(query) if isinstance(query, dict) else query)
        return result

    def link_to(self, context, text, **attrs):
        return '<a href="%s">%s</a>' % (self.url(context), html.escape(text))


class CalendarFormatter:
    def __init__(self, context, page_name):
        self.page = CalendarPage(context, page_name)

    def url(self, on, url=None, css=None, **attrs):
        if not on:
            return '</a>'
        attrs.update(href=url, **{'class': css})
        return '<a %s>' % ' '.join(
            '%s="%s"' % (name, html.escape(value, quote=True))
            for name, value in attrs.items() if value is not None
        )

    def make_id_unique(self, value):
        return value

    def rawHTML(self, value):
        return value


class Links(HTMLParser):
    def __init__(self, output):
        super().__init__()
        self.links = []
        self.feed(output)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs))


@pytest.fixture
def render(monkeypatch):
    monkeypatch.setattr(MonthCalendar, 'Page', CalendarPage)
    first_weekday = calendar.firstweekday()
    calendar.setfirstweekday(calendar.MONDAY)

    def render_calendar(text=None, *, query=None, spider=False, writable=False,
                        page_name='Calendar', page_bodies=None):
        context = CalendarContext(WikiTestRequest(
            path='/' + page_name, query_string=urlencode(query or {})))
        context.cfg = SimpleNamespace(url_prefix_static='/moin_static',
                                      monthcalendar_max_nav_offset=18)
        context.user = SimpleNamespace(
            getTime=lambda timestamp: (2024, 2, 15, 12, 0, 0, 3, 46, 0),
            may=SimpleNamespace(read=lambda page: True, write=lambda page: writable),
        )
        context.mode_getpagelinks = False
        context.isSpiderAgent = spider
        context.page_bodies = page_bodies or {}
        macro = SimpleNamespace(request=context,
                                formatter=CalendarFormatter(context, page_name))
        return MonthCalendar.execute(macro, text)

    yield render_calendar
    calendar.setfirstweekday(first_weekday)


def navigation(output):
    return [link for link in Links(output).links if 'calparms=' in link['href']]


def displayed_days(output):
    return [int(day) for day in re.findall(r'<span class="cal-[^"]+">(\d+)</span>', output)]


def test_default_calendar_renders_leap_month_and_navigation(render):
    output = render()
    assert '<table' in output
    assert '2024&nbsp;/&nbsp;2' in output
    assert displayed_days(output) == list(range(1, 30))
    assert len(navigation(output)) == 4
    assert all(link.get('rel') == 'nofollow' for link in navigation(output))


@pytest.mark.parametrize(('text', 'year', 'month', 'days'), [
    (',2023,2', 2023, 2, 28),
    (',2024,4', 2024, 4, 30),
    (',2024,12', 2024, 12, 31),
])
def test_explicit_months_render_all_valid_days(render, text, year, month, days):
    output = render(text)
    assert f'{year}&nbsp;/&nbsp;{month}' in output
    assert displayed_days(output) == list(range(1, days + 1))


@pytest.mark.parametrize(('offset', 'expected_year', 'expected_month'), [
    (-1, 2023, 12), (1, 2024, 2), (12, 2025, 1),
])
def test_generated_navigation_can_be_followed(render, offset, expected_year, expected_month):
    output = render(',2024,1')
    query = next(
        parse_qs(urlsplit(link['href']).query)
        for link in navigation(output)
        if parse_qs(urlsplit(link['href']).query)['calparms'][0].split(',')[4] == str(offset)
    )
    followed = render(',2024,1', query={key: values[0] for key, values in query.items()})
    assert f'{expected_year}&nbsp;/&nbsp;{expected_month}' in followed
    assert len(displayed_days(followed)) == calendar.monthrange(expected_year, expected_month)[1]


def test_spider_ignores_navigation_query_and_gets_no_navigation_links(render):
    output = render(',2024,1', spider=True,
                    query={'calparms': 'Calendar,2024,1,0,12,,,'})
    assert '2024&nbsp;/&nbsp;1' in output
    assert not navigation(output)
    assert not Links(output).links


def test_navigation_is_clamped_at_configured_limit(render):
    output = render(',2024,1', query={'calparms': 'Calendar,2024,1,0,999,,,'})
    assert '2025&nbsp;/&nbsp;7' in output
    offsets = [int(parse_qs(urlsplit(link['href']).query)['calparms'][0].split(',')[4])
               for link in navigation(output)]
    assert sorted(offsets) == [6, 17]


def test_unicode_calendar_and_existing_day_render_with_tooltip(render):
    output = render(page_name='日历', page_bodies={'日历/2024-02-29': '= 闰日 =\n'})
    links = Links(output).links
    assert any('%E6%97%A5%E5%8E%86/2024-02-29' in link['href'] for link in links)
    assert "maketip('日历/2024-02-29','日历/2024-02-29','闰日')" in output
    assert len(navigation(output)) == 4


def test_anniversary_template_and_fixed_height_render(render):
    output = render('Calendar,2024,2,,,true,true,DayTemplate', writable=True)
    days = [link for link in Links(output).links if 'action=edit' in link['href']]
    assert len(days) == 29
    assert any('/Calendar/02-29?' in link['href'] for link in days)
    assert all(parse_qs(urlsplit(link['href']).query)['template'] == ['DayTemplate'] for link in days)
    assert output.count(' <tr>') == 8  # Header, weekday names, six calendar weeks.
