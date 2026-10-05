"""Download and cache prices and fundamentals from yfinance."""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import pandas as pd
import yfinance as yf

from src import config

log = logging.getLogger(__name__)

# yfinance .info key -> our column name
INFO_FIELDS = {
    "longName": "company",
    "sector": "sector",
    "marketCap": "market_cap",
    "currentPrice": "price",
    "trailingEps": "eps",
    "freeCashflow": "fcf",
    "enterpriseValue": "ev",
    "ebitda": "ebitda",
    "returnOnEquity": "roe",
    "grossMargins": "gross_margin",
    "debtToEquity": "debt_to_equity",
    "revenueGrowth": "revenue_growth",
    "earningsGrowth": "earnings_growth",
}
TEXT_FIELDS = ["company", "sector"]


def _retry(fn: Callable[..., Any], *args: Any, tries: int = 3, delay: float = 1.0) -> Any:
    """Call fn with exponential backoff; re-raise after the last attempt."""
    for i in range(tries):
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            log.debug("retry %d/%d after %s", i + 1, tries, e)
            time.sleep(delay * 2**i)


def _download_prices(tickers: list[str], start: str, end: str | None) -> pd.DataFrame:
    """Adjusted close prices, one column per ticker."""
    df = yf.download(tickers, start=start, end=end, auto_adjust=True,
                     progress=False, threads=True)
    if df is None or df.empty:
        raise RuntimeError("empty price download")
    close = df["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return close.dropna(axis=1, how="all")


def load_prices(tickers: list[str], start: str = config.START_DATE,
                end: str | None = config.END_DATE) -> pd.DataFrame:
    """Return cached adjusted prices; download only tickers missing from cache."""
    path = config.CACHE_DIR / f"prices_{start}_{end or 'latest'}.parquet"
    cached = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    missing = [t for t in tickers if t not in cached.columns]
    if missing:
        log.info("downloading prices for %d tickers", len(missing))
        try:
            new = _retry(_download_prices, missing, start, end)
        except Exception as e:  # noqa: BLE001
            log.error("price download failed: %s", e)
            new = pd.DataFrame()
        failed = sorted(set(missing) - set(new.columns))
        if failed:
            log.warning("skipped %d tickers with no prices: %s", len(failed), failed)
        if not new.empty:
            cached = pd.concat([cached, new], axis=1).sort_index()
            path.parent.mkdir(parents=True, exist_ok=True)
            cached.to_parquet(path)
    return cached.reindex(columns=[t for t in tickers if t in cached.columns])


def _fetch_info(ticker: str) -> dict[str, Any]:
    """Selected .info fields for one ticker; raises if the payload is empty."""
    info = yf.Ticker(ticker).info or {}
    if not info.get("marketCap") and not info.get("longName"):
        raise RuntimeError("empty info")
    return {new: info.get(old) for old, new in INFO_FIELDS.items()}


def _safe_info(ticker: str) -> dict[str, Any] | None:
    try:
        return _retry(_fetch_info, ticker)
    except Exception as e:  # noqa: BLE001
        log.warning("skip %s fundamentals: %s", ticker, e)
        return None


def load_fundamentals(tickers: list[str]) -> pd.DataFrame:
    """Return cached current fundamentals (index=ticker); fetch only missing tickers."""
    path = config.CACHE_DIR / "fundamentals.parquet"
    cached = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    missing = [t for t in tickers if t not in cached.index]
    if missing:
        log.info("downloading fundamentals for %d tickers", len(missing))
        with ThreadPoolExecutor(max_workers=8) as ex:
            rows = dict(zip(missing, ex.map(_safe_info, missing)))
        new = pd.DataFrame.from_dict({t: r for t, r in rows.items() if r}, orient="index")
        if not new.empty:
            num = new.columns.difference(TEXT_FIELDS)
            new[num] = new[num].apply(pd.to_numeric, errors="coerce")
            new[TEXT_FIELDS] = new[TEXT_FIELDS].astype("string")
            cached = pd.concat([cached, new])
            path.parent.mkdir(parents=True, exist_ok=True)
            cached.to_parquet(path)
    return cached.reindex([t for t in tickers if t in cached.index])
