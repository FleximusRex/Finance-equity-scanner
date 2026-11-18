"""Ticker universe selection: test50 (config.UNIVERSE), S&P 100 or S&P 500 (Wikipedia, cached)."""
from __future__ import annotations

import io
import logging
import urllib.request

import pandas as pd

from src import config

log = logging.getLogger(__name__)
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SP100_URL = "https://en.wikipedia.org/wiki/S%26P_100"
# index -> (page, name of the sector column). Both pages give the table id="constituents".
WIKI_TABLES = {
    "sp500": (SP500_URL, "GICS Sector"),
    "sp100": (SP100_URL, "Sector"),
}


def _constituents(index: str) -> pd.DataFrame:
    """Ticker (Yahoo format, e.g. BRK-B) and GICS sector for one index; cached to parquet."""
    path = config.CACHE_DIR / f"{index}_constituents.parquet"
    if path.exists():
        return pd.read_parquet(path)
    url, sector_col = WIKI_TABLES[index]
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode()
    table = pd.read_html(io.StringIO(html), attrs={"id": "constituents"})[0]
    df = pd.DataFrame({
        "ticker": table["Symbol"].astype(str).str.strip().str.replace(".", "-", regex=False),
        "sector": table[sector_col].astype(str),
    }).drop_duplicates("ticker")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    log.info("cached %d %s tickers -> %s", len(df), index, path.name)
    return df


def sp500_tickers() -> list[str]:
    """Current S&P 500 constituents."""
    return _constituents("sp500")["ticker"].tolist()


def sp100_tickers() -> list[str]:
    """Current S&P 100 constituents."""
    return _constituents("sp100")["ticker"].tolist()


def get_universe(mode: str | None = None) -> list[str]:
    """Ticker list for `mode` (default: the configured universe)."""
    mode = mode or config.UNIVERSE_MODE
    if mode == "test50":
        return list(config.UNIVERSE)
    if mode == "sp100":
        return sp100_tickers()
    if mode == "sp500":
        return sp500_tickers()
    raise ValueError(f"unknown universe mode {mode!r}")


def sectors(mode: str | None = None) -> pd.Series:
    """Today's GICS sector for each ticker in the universe (NaN if the ticker is not listed)."""
    mode = mode or config.UNIVERSE_MODE
    # The 50 test tickers have no table of their own, so their sectors come from the S&P 500 page.
    table = _constituents("sp100" if mode == "sp100" else "sp500")
    return table.set_index("ticker")["sector"].reindex(get_universe(mode))
