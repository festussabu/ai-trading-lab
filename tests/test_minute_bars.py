"""Tests for src/minute_bars.py. Fake data only: no real API calls, no real keys."""

import socket
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from minute_bars import MinuteBarsError, fetch_minute_bars, save_bars  # noqa: E402

DAY = date(2026, 11, 13)
NY = ZoneInfo("America/New_York")
FAKE_KEY = "FAKE-KEY-123"
FAKE_SECRET = "FAKE-SECRET-456"


# --- fakes -------------------------------------------------------------------


class FakeBarSet:
    def __init__(self, df):
        self.df = df


class FakeClient:
    """Stands in for StockHistoricalDataClient and records the request it receives."""

    def __init__(self, df=None, error=None):
        self.df = df
        self.error = error
        self.request = None

    def get_stock_bars(self, request):
        self.request = request
        if self.error:
            raise self.error
        return FakeBarSet(self.df)


def fake_bars_df(rows=3):
    """A DataFrame shaped like alpaca-py's BarSet.df: (symbol, timestamp) index."""
    stamps = pd.date_range("2026-11-13 14:30", periods=rows, freq="min", tz="UTC")
    index = pd.MultiIndex.from_arrays([["SPY"] * rows, stamps], names=["symbol", "timestamp"])
    return pd.DataFrame(
        {
            "open": [600.0 + i for i in range(rows)],
            "high": [601.0 + i for i in range(rows)],
            "low": [599.0 + i for i in range(rows)],
            "close": [600.5 + i for i in range(rows)],
            "volume": [1000.0 + i for i in range(rows)],
            "trade_count": [10.0] * rows,
            "vwap": [600.2] * rows,
        },
        index=index,
    )


# --- fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Fail any test that tries to open a real network connection."""

    def refuse(*args, **kwargs):
        raise RuntimeError("Network access is blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def fake_keys(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", FAKE_KEY)
    monkeypatch.setenv("ALPACA_SECRET_KEY", FAKE_SECRET)


# --- tests -------------------------------------------------------------------


def test_missing_api_key_names_variable(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.setenv("ALPACA_SECRET_KEY", FAKE_SECRET)
    with pytest.raises(MinuteBarsError, match="ALPACA_API_KEY"):
        fetch_minute_bars(DAY, client=FakeClient(fake_bars_df()))


def test_missing_secret_key_names_variable(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", FAKE_KEY)
    monkeypatch.setenv("ALPACA_SECRET_KEY", "")
    with pytest.raises(MinuteBarsError, match="ALPACA_SECRET_KEY"):
        fetch_minute_bars(DAY, client=FakeClient(fake_bars_df()))


def test_error_messages_never_contain_key_values(fake_keys, monkeypatch):
    # API error whose text echoes both keys back.
    client = FakeClient(error=ConnectionError(f"bad auth {FAKE_KEY} {FAKE_SECRET}"))
    with pytest.raises(MinuteBarsError) as api_err:
        fetch_minute_bars(DAY, client=client)
    # Missing-secret error while the API key is set.
    monkeypatch.delenv("ALPACA_SECRET_KEY")
    with pytest.raises(MinuteBarsError) as key_err:
        fetch_minute_bars(DAY, client=FakeClient(fake_bars_df()))

    for err in (api_err, key_err):
        assert FAKE_KEY not in str(err.value)
        assert FAKE_SECRET not in str(err.value)
    assert api_err.value.__cause__ is None
    assert api_err.value.__suppress_context__ is True


def test_request_is_spy_minute_iex_regular_hours(fake_keys):
    client = FakeClient(fake_bars_df())
    fetch_minute_bars(DAY, client=client)
    req = client.request

    assert req.symbol_or_symbols == "SPY"
    assert req.timeframe.amount_value == TimeFrame.Minute.amount_value
    assert req.timeframe.unit_value == TimeFrame.Minute.unit_value
    assert req.feed == DataFeed.IEX
    # alpaca-py stores times as naive UTC, so convert the expected New York times to UTC.
    def as_naive_utc(ny_time):
        return ny_time.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    assert req.start == as_naive_utc(datetime(2026, 11, 13, 9, 30, tzinfo=NY))
    assert req.end == as_naive_utc(datetime(2026, 11, 13, 16, 0, tzinfo=NY))
    assert req.start == datetime(2026, 11, 13, 14, 30)  # 09:30 EST = 14:30 UTC


def test_returns_ohlcv_columns_and_source(fake_keys):
    bars = fetch_minute_bars(DAY, client=FakeClient(fake_bars_df(rows=3)))
    assert list(bars.columns) == ["timestamp", "open", "high", "low", "close", "volume", "source"]
    assert len(bars) == 3
    assert (bars["source"] == "alpaca-iex").all()


def test_api_failure_raises_clear_error(fake_keys):
    client = FakeClient(error=ConnectionError("service unavailable"))
    with pytest.raises(MinuteBarsError, match="failed"):
        fetch_minute_bars(DAY, client=client)


def test_no_bars_raises_error_with_date(fake_keys):
    empty = fake_bars_df(rows=0)
    with pytest.raises(MinuteBarsError, match="2026-11-13"):
        fetch_minute_bars(DAY, client=FakeClient(empty))


def test_save_bars_creates_folder_and_file(fake_keys, tmp_path):
    bars = fetch_minute_bars(DAY, client=FakeClient(fake_bars_df()))
    out_dir = tmp_path / "missing" / "bars"
    path = save_bars(bars, DAY, out_dir=out_dir)
    assert path == out_dir / "SPY_2026-11-13.csv"
    assert path.exists()


def test_saved_csv_reads_back_same(fake_keys, tmp_path):
    bars = fetch_minute_bars(DAY, client=FakeClient(fake_bars_df(rows=5)))
    path = save_bars(bars, DAY, out_dir=tmp_path)
    loaded = pd.read_csv(path, parse_dates=["timestamp"])
    assert list(loaded.columns) == list(bars.columns)
    assert len(loaded) == len(bars)
    pd.testing.assert_frame_equal(loaded, bars, check_dtype=False)


def test_network_guard_blocks_real_connections():
    with pytest.raises(RuntimeError, match="blocked"):
        socket.create_connection(("example.com", 443))
