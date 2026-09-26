import io
import json
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import pytest

from stonkfly.lab import fetch, read_prices


def fake_api(monkeypatch, missing=False):
    import urllib.request
    from stonkfly import lab

    end = 1800000000 // 3600 * 3600
    monkeypatch.setattr(lab.time, "time", lambda: end + 123)
    calls = []

    def respond(request, timeout):
        params = parse_qs(urlparse(request.full_url).query)
        start = int(datetime.fromisoformat(params["start"][0]).timestamp())
        stop = int(datetime.fromisoformat(params["end"][0]).timestamp())
        interval = int(params["granularity"][0])
        assert (stop - start) // interval <= 300
        calls.append((start, stop))
        # Unsorted responses include earlier/out-of-range and still-open candles.
        candles = [
            [t, 99, 102, 100, 101, 10]
            for t in range(start - interval, stop + interval, interval)
        ]
        if missing:
            candles = [c for c in candles if c[0] != start]
        return io.StringIO(json.dumps(candles[::-1]))

    monkeypatch.setattr(urllib.request, "urlopen", respond)
    return end, calls


def test_paginated_hourly_history_is_complete_and_closed(tmp_path, monkeypatch):
    end, calls = fake_api(monkeypatch)
    path = tmp_path / "hourly.csv"
    fetch(path, granularity=3600, count=437)
    rows = read_prices(path)
    assert len(calls) == 2 and len(rows) == 437
    assert int(rows[0]["timestamp"]) == end - 437 * 3600
    assert int(rows[-1]["timestamp"]) == end - 3600
    # The first fill (after 100 warmup rows plus decision row) is 14 days ago.
    assert int(rows[101]["timestamp"]) == end - 14 * 24 * 3600
    assert all(
        int(b["timestamp"]) - int(a["timestamp"]) == 3600
        for a, b in zip(rows, rows[1:])
    )


def test_missing_hours_fail_without_partial_output(tmp_path, monkeypatch):
    fake_api(monkeypatch, missing=True)
    path = tmp_path / "hourly.csv"
    with pytest.raises(ValueError, match="incomplete"):
        fetch(path, granularity=3600, count=437)
    assert not path.exists()
