"""Fetch 1-minute SPY bars for one trading day from Alpaca (IEX feed) and save them to CSV.

Market data only. This module never creates a trading client and cannot place orders.
"""

import os
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

SYMBOL = "SPY"
SOURCE = "alpaca-iex"
NEW_YORK = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
KEY_VARS = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")


class MinuteBarsError(RuntimeError):
    """Raised when bars cannot be fetched or keys are missing."""


def _read_keys() -> tuple[str, str]:
    """Return (api_key, secret_key) from the environment, or raise naming the missing variable."""
    values = []
    for name in KEY_VARS:
        value = os.environ.get(name, "").strip()
        if not value:
            raise MinuteBarsError(f"Environment variable {name} is missing or empty. Add it to your .env file.")
        values.append(value)
    return values[0], values[1]


def _redact(text: str, secrets: tuple[str, ...]) -> str:
    """Replace any secret value in text with ***, so it never ends up in an error message."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def fetch_minute_bars(day: date, client=None) -> pd.DataFrame:
    """Download SPY 1-minute bars (IEX feed) from 09:30 to 16:00 New York time on `day`.

    `client` is optional so tests can pass a fake; by default a StockHistoricalDataClient is built.
    """
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    api_key, secret_key = _read_keys()

    if client is None:
        from alpaca.data.historical import StockHistoricalDataClient

        client = StockHistoricalDataClient(api_key, secret_key)

    request = StockBarsRequest(
        symbol_or_symbols=SYMBOL,
        timeframe=TimeFrame.Minute,
        start=datetime.combine(day, MARKET_OPEN, tzinfo=NEW_YORK),
        end=datetime.combine(day, MARKET_CLOSE, tzinfo=NEW_YORK),
        feed=DataFeed.IEX,
    )

    try:
        barset = client.get_stock_bars(request)
    except Exception as exc:
        reason = _redact(f"{type(exc).__name__}: {exc}", (api_key, secret_key))
        raise MinuteBarsError(f"Alpaca request for {SYMBOL} bars on {day.isoformat()} failed ({reason}).") from None

    raw = barset.df
    if raw is None or raw.empty:
        raise MinuteBarsError(f"Alpaca returned no {SYMBOL} bars for {day.isoformat()}. Was it a trading day?")

    bars = raw.reset_index()[COLUMNS].copy()
    bars["source"] = SOURCE
    return bars


def save_bars(bars: pd.DataFrame, day: date, out_dir: Path = Path("data/bars")) -> Path:
    """Write bars to out_dir/SPY_<YYYY-MM-DD>.csv (creating out_dir if needed) and return the path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{SYMBOL}_{day.isoformat()}.csv"
    bars.to_csv(path, index=False)
    return path
