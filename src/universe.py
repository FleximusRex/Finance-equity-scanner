"""Ticker universe selection: test50 (config.UNIVERSE) or current S&P 500 (Wikipedia, cached)."""
from __future__ import annotations

import io
import logging
import urllib.request

import pandas as pd

from src import config

log = logging.getLogger(__name__)
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def sp500_tickers() -> list[str]:
    """Current S&P 500 constituents (Yahoo format, e.g. BRK-B); cached to parquet."""
    path = config.CACHE_DIR / "sp500_constituents.parquet"
    if path.exists():
        return pd.read_parquet(path)["ticker"].tolist()
    req = urllib.request.Request(SP500_URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode()
    table = pd.read_html(io.StringIO(html), attrs={"id": "constituents"})[0]
    df = pd.DataFrame({
        "ticker": table["Symbol"].astype(str).str.strip().str.replace(".", "-", regex=False),
        "sector": table["GICS Sector"].astype(str),
    }).drop_duplicates("ticker")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    log.info("cached %d S&P 500 tickers -> %s", len(df), path.name)
    return df["ticker"].tolist()


def get_universe(mode: str = config.UNIVERSE_MODE) -> list[str]:
    """Ticker list for the configured universe mode."""
    if mode == "test50":
        return list(config.UNIVERSE)
    if mode == "sp500":
        return sp500_tickers()
    raise ValueError(f"unknown universe mode {mode!r}")
