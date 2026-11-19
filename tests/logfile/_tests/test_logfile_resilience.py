"""Regression tests for damaged event logs and long reverse-read records."""

import io
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from MoinMoin.logfile import LogFile
from MoinMoin.logfile.eventlog import EventLog
from MoinMoin.macro.PageHits import PageHits


class ReadBudgetIO(io.BytesIO):
    """Fail deterministically if reverse iteration rereads without advancing."""

    def __init__(self, data):
        super().__init__(data)
        self.reads_left = 200

    def read(self, *args):
        self.reads_left -= 1
        assert self.reads_left >= 0, "reverse iteration did not make progress"
        return super().read(*args)


def event_line(timestamp, page, event="VIEWPAGE"):
    query = urlencode({"pagename": page, "HTTP_USER_AGENT": "Test/1.0"})
    return ("%s\t%s\t%s" % (timestamp, event, query)).encode("utf-8")


def memory_log(data, cls=LogFile, buffer_size=65536):
    if cls is EventLog:
        log = cls(None, filename="<memory>", buffer_size=buffer_size)
    else:
        log = cls("<memory>", buffer_size=buffer_size)
    log._input = ReadBudgetIO(data)
    return log


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("separator", [b"\n", b"\r\n"])
def test_event_iteration_skips_damage_and_preserves_unicode(reverse, separator):
    rows = [
        event_line(1000000, "首页"),
        b"\x00" * 1160 + event_line(1500000, "damaged"),
        b"not-a-timestamp\tVIEWPAGE\tpagename=bad",
        b"1700000\tVIEWPAGE",  # missing field
        b"1800000\tVIEWPAGE\tpagename=bad\textra",  # extra field
        b"",
        event_line(2000000, "C++ 小程序", "SAVEPAGE"),
        event_line(2500000, "unrelated", "SEARCH"),
        event_line(3000000, "首页"),
    ]
    log = memory_log(separator.join(rows) + separator, EventLog, buffer_size=64)
    log.set_filter(["VIEWPAGE", "SAVEPAGE"])
    result = list(log.reverse() if reverse else log)
    expected = [(1000000, "VIEWPAGE", "首页"),
                (2000000, "SAVEPAGE", "C++ 小程序"),
                (3000000, "VIEWPAGE", "首页")]
    if reverse:
        expected.reverse()
    assert [(t, action, data["pagename"]) for t, action, data in result] == expected


@pytest.mark.parametrize("data", [b"", b"broken\n", b"broken\n\x00\n"])
def test_empty_or_invalid_logs_reach_both_ends(data):
    log = memory_log(data, EventLog, buffer_size=8)
    assert list(log) == []
    with pytest.raises(StopIteration):
        next(log)
    assert list(log.reverse()) == []
    with pytest.raises(StopIteration):
        log.previous()


@pytest.mark.parametrize("position", ["only", "first", "middle", "last"])
@pytest.mark.parametrize("buffer_size", [16, 65536])
@pytest.mark.parametrize("final_newline", [False, True])
def test_long_unicode_line_preserves_forward_reverse_order(position, buffer_size, final_newline):
    long_line = "长行🙂" * 24000  # More than three default 64 KiB buffers.
    lines = {
        "only": [long_line],
        "first": [long_line, "middle", "尾行"],
        "middle": ["首行", long_line, "尾行"],
        "last": ["首行", "middle", long_line],
    }[position]
    data = ("\n".join(lines) + ("\n" if final_newline else "")).encode("utf-8")
    log = memory_log(data, buffer_size=buffer_size)
    assert list(log) == [[line] for line in lines]
    with pytest.raises(StopIteration):
        next(log)
    # Start reverse traversal without buffers populated by a forward read.
    log = memory_log(data, buffer_size=buffer_size)
    assert list(log.reverse()) == [[line] for line in reversed(lines)]
    with pytest.raises(StopIteration):
        log.previous()
    log.to_begin()
    assert list(log) == [[line] for line in lines]


@pytest.mark.parametrize("final_newline", [False, True])
def test_reverse_skips_nul_record_larger_than_buffer(final_newline):
    rows = [event_line(1000000, "before"),
            b"\x00" * 200000 + event_line(2000000, "damaged"),
            event_line(3000000, "after")]
    data = b"\n".join(rows) + (b"\n" if final_newline else b"")
    log = memory_log(data, EventLog)
    assert [entry[2]["pagename"] for entry in log.reverse()] == ["after", "before"]
    log.to_begin()
    assert [entry[2]["pagename"] for entry in log] == ["before", "after"]


def test_seek_uses_byte_offsets_with_unicode(tmp_path):
    lines = ["首行🙂", "second", "末行"]
    filename = tmp_path / "log"
    filename.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    log = LogFile(str(filename), buffer_size=8)
    try:
        log.seek(len((lines[0] + "\n").encode("utf-8")))
        assert list(log) == [[line] for line in lines[1:]]
        assert list(log.reverse()) == [[line] for line in reversed(lines)]
    finally:
        log._input.close()


def test_pagehits_updates_cache_after_skipping_corrupt_record(tmp_path):
    filename = tmp_path / "event-log"
    filename.write_bytes(b"\n".join([
        event_line(1000000, "首页"),
        b"\x00" * 1160 + event_line(1500000, "damaged"),
        event_line(2000000, "首页"),
        event_line(3000000, "Other"),
    ]) + b"\n")
    pagehits = PageHits.__new__(PageHits)
    pagehits.request = SimpleNamespace(rootpage=SimpleNamespace(
        getPagePath=lambda *args, **kwargs: str(filename)))
    updates = []
    pagehits.updateCache = lambda date, hits: updates.append((date, dict(hits)))
    hits = {}
    pagehits.addHitsFromLog(hits, 0)
    assert hits == {"首页": 2, "Other": 1}
    assert updates == [(3000000, hits)]
    pagehits.addHitsFromLog(hits, updates[0][0])
    assert hits == {"首页": 2, "Other": 1}
    assert len(updates) == 1


class MemoryCache:
    def __init__(self, data=None):
        self.data = data

    def exists(self):
        return self.data is not None

    def content(self):
        return self.data

    def remove(self):
        self.data = None

    def update(self, data):
        self.data = data


@pytest.mark.parametrize("initial_log", [
    b"",
    b"\x00" * 1160 + event_line(1000000, "damaged") + b"\n",
    event_line(1000000, "unrelated", "SEARCH") + b"\n",
])
def test_hitcounts_empty_log_then_new_events_updates_cache(tmp_path, monkeypatch, initial_log):
    from MoinMoin.stats import hitcounts

    filename = tmp_path / "event-log"
    filename.write_bytes(initial_log)
    request = SimpleNamespace(rootpage=SimpleNamespace(
        getPagePath=lambda *args, **kwargs: str(filename)))
    cache = MemoryCache()
    monkeypatch.setattr(hitcounts.caching, "CacheEntry", lambda *args, **kwargs: cache)
    assert hitcounts.get_data("Stats", request) == ([], [], [])
    assert cache.data == (0, [], [], [])

    timestamp = 1700000000000000  # 2023-11-14 UTC
    with filename.open("ab") as output:
        output.write(event_line(timestamp, "首页") + b"\n")
    assert hitcounts.get_data("Stats", request) == (["2023-11-14"], [1], [0])
    assert cache.data[0] == timestamp
    # A subsequent request must use the new watermark and not count twice.
    assert hitcounts.get_data("Stats", request) == (["2023-11-14"], [1], [0])


def test_hitcounts_accepts_legacy_none_cache_timestamp(tmp_path, monkeypatch):
    from MoinMoin.stats import hitcounts

    filename = tmp_path / "event-log"
    timestamp = 1700000000000000
    filename.write_bytes(event_line(timestamp, "首页") + b"\n")
    request = SimpleNamespace(rootpage=SimpleNamespace(
        getPagePath=lambda *args, **kwargs: str(filename)))
    cache = MemoryCache((None, [], [], []))
    monkeypatch.setattr(hitcounts.caching, "CacheEntry", lambda *args, **kwargs: cache)
    assert hitcounts.get_data("Stats", request) == (["2023-11-14"], [1], [0])
    assert cache.data[0] == timestamp


def test_hitcounts_preserves_existing_watermark_after_log_rotation(tmp_path, monkeypatch):
    from MoinMoin.stats import hitcounts

    filename = tmp_path / "event-log"
    filename.write_bytes(b"")
    request = SimpleNamespace(rootpage=SimpleNamespace(
        getPagePath=lambda *args, **kwargs: str(filename)))
    timestamp = 1700000000000000
    cache = MemoryCache((timestamp, ["2023-11-14"], [5], [2]))
    monkeypatch.setattr(hitcounts.caching, "CacheEntry", lambda *args, **kwargs: cache)
    assert hitcounts.get_data("Stats", request) == (["2023-11-14"], [5], [2])
    assert cache.data[0] == timestamp
