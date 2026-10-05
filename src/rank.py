"""Build the current multi-factor ranking: python -m src.rank"""
from __future__ import annotations

import logging
import sys

import pandas as pd

from src import config
from src.data_loader import load_fundamentals, load_prices
from src.factors import compute_factors
from src.scoring import score

log = logging.getLogger("rank")

COLUMNS = {
    "company": "Company", "sector": "Sector", "Price": "Price", "market_cap": "MarketCap",
    "value": "Value", "quality": "Quality", "momentum": "Momentum", "growth": "Growth",
    "low_vol": "LowVol", "composite": "Composite", "percentile": "Percentile",
    "quintile": "Quintile", "ret_1m": "Ret1M", "ret_6m": "Ret6M", "ret_12m": "Ret12M",
    "fcf_yield": "FCFYield", "ev_ebitda": "EV_EBITDA", "vol_60d": "Volatility", "beta": "Beta",
}


def build_rankings(tickers: list[str] = config.UNIVERSE) -> pd.DataFrame:
    """Download (or load cached) data, compute factors and return the ranking table."""
    prices = load_prices(tickers + [config.BENCHMARK])
    fund = load_fundamentals(tickers)
    if prices.empty and fund.empty:
        raise RuntimeError("no price or fundamental data available")

    factors = compute_factors(prices, fund).reindex(tickers).dropna(how="all")
    scores = score(factors)
    meta = fund.reindex(factors.index, columns=["company", "sector", "market_cap", "price"])
    last_px = prices.ffill().iloc[-1] if not prices.empty else pd.Series(dtype=float)
    meta["Price"] = meta["price"].fillna(last_px.reindex(meta.index))

    df = meta.join(scores).join(factors)[list(COLUMNS)].rename(columns=COLUMNS)
    df.index.name = "Ticker"
    return df.sort_values("Composite", ascending=False, na_position="last").reset_index()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    try:
        df = build_rankings()
    except RuntimeError as e:
        log.error("%s", e)
        return 1
    config.RANKINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RANKINGS_DIR / "rankings.csv"
    df.round(4).to_csv(path, index=False)
    log.info("saved %d rows -> %s", len(df), path)
    print(df[["Ticker", "Sector", "Composite", "Quintile"]].head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
