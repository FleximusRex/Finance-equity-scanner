"""Retry and caching behaviour of the yfinance loaders, with yfinance mocked."""
from typing import ClassVar

import numpy as np
import pandas as pd
import pytest

from src import config, data_loader


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    delays: list[float] = []
    monkeypatch.setattr(data_loader.time, "sleep", delays.append)
    return delays


def test_retry_returns_after_transient_failures(no_sleep) -> None:
    calls = []

    def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("temporary")
        return "ok"

    assert data_loader._retry(flaky, tries=3, delay=1.0) == "ok"
    assert len(calls) == 3
    assert no_sleep == [1.0, 2.0]  # exponential backoff between attempts


def test_retry_reraises_after_last_attempt(no_sleep) -> None:
    calls = []

    def always_fails() -> None:
        calls.append(1)
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        data_loader._retry(always_fails, tries=3)
    assert len(calls) == 3
    assert len(no_sleep) == 2  # no sleep after the final failure


def _download_frame(tickers: list[str]) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-01", periods=5)
    cols = pd.MultiIndex.from_product([["Close"], tickers])
    data = np.tile(np.arange(5.0).reshape(-1, 1) + 100, (1, len(tickers)))
    df = pd.DataFrame(data, index=idx, columns=cols)
    df[("Close", tickers[-1])] = np.nan  # last ticker has no prices
    return df


def test_load_prices_retries_caches_and_drops_empty_tickers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    attempts = []

    def fake_download(tickers, **kwargs):
        attempts.append(list(tickers))
        if len(attempts) < 3:
            raise ConnectionError("rate limited")
        return _download_frame(tickers)

    monkeypatch.setattr(data_loader.yf, "download", fake_download)
    prices = data_loader.load_prices(["AAA", "BBB", "DEAD"], start="2024-01-01", end=None)
    assert len(attempts) == 3
    assert list(prices.columns) == ["AAA", "BBB"]

    # Second call is served from the parquet cache for tickers it already has.
    attempts.clear()
    again = data_loader.load_prices(["AAA", "BBB"], start="2024-01-01", end=None)
    assert attempts == []
    pd.testing.assert_frame_equal(prices, again, check_freq=False)


def test_load_prices_survives_total_download_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    def broken(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr(data_loader.yf, "download", broken)
    assert data_loader.load_prices(["AAA"], start="2024-01-01", end=None).empty


class FakeTicker:
    payloads: ClassVar[dict[str, dict]] = {}

    def __init__(self, symbol: str) -> None:
        self.info = self.payloads.get(symbol, {})


def test_safe_info_maps_fields_and_skips_empty_payloads(monkeypatch) -> None:
    FakeTicker.payloads = {"GOOD": {"longName": "Good Co", "marketCap": 5e9, "trailingEps": 2.0}}
    monkeypatch.setattr(data_loader.yf, "Ticker", FakeTicker)
    good = data_loader._safe_info("GOOD")
    assert good["company"] == "Good Co" and good["market_cap"] == 5e9 and good["eps"] == 2.0
    assert good["fcf"] is None
    assert data_loader._safe_info("MISSING") is None
