"""Build the current multi-factor ranking.

Run: python -m src.rank [--universe {test50,sp100,sp500}] [--sector-neutral]
"""
from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

import pandas as pd

from src import cli, config
from src.data_loader import load_fundamentals, load_prices
from src.factors import compute_factors
from src.run_info import save_run_info
from src.scoring import score
from src.universe import get_universe, sectors

log = logging.getLogger("rank")

COLUMNS = {
    "company": "Company", "sector": "Sector", "Price": "Price", "market_cap": "MarketCap",
    "value": "Value", "quality": "Quality", "momentum": "Momentum", "growth": "Growth",
    "low_vol": "LowVol", "composite": "Composite", "percentile": "Percentile",
    "quintile": "Quintile", "ret_1m": "Ret1M", "ret_6m": "Ret6M", "ret_12m": "Ret12M",
    "fcf_yield": "FCFYield", "ev_ebitda": "EV_EBITDA", "vol_60d": "Volatility", "beta": "Beta",
}


def build_rankings(tickers: list[str] | None = None,
                   prices: pd.DataFrame | None = None) -> pd.DataFrame:
    """Download (or load cached) data, compute factors and return the ranking table."""
    tickers = tickers or get_universe()
    if prices is None:
        prices = load_prices([*tickers, config.BENCHMARK])
    fund = load_fundamentals(tickers)
    if prices.empty and fund.empty:
        raise RuntimeError("no price or fundamental data available")

    factors = compute_factors(prices, fund).reindex(tickers).dropna(how="all")
    scores = score(factors, sectors=sectors() if config.SECTOR_NEUTRAL else None)
    meta = fund.reindex(factors.index, columns=["company", "sector", "market_cap", "price"])
    last_px = prices.ffill().iloc[-1] if not prices.empty else pd.Series(dtype=float)
    meta["Price"] = meta["price"].fillna(last_px.reindex(meta.index))

    df = meta.join(scores).join(factors)[list(COLUMNS)].rename(columns=COLUMNS)
    df.index.name = "Ticker"
    return df.sort_values("Composite", ascending=False, na_position="last").reset_index()


def main(argv: Sequence[str] | None = None) -> int:
    cli.parse_args("Build the current multi-factor ranking.", argv)
    cli.setup_logging()
    prices = load_prices([*get_universe(), config.BENCHMARK])
    if prices.empty:
        log.error("no price data available")
        return 1
    try:
        df = build_rankings(prices=prices)
    except RuntimeError as e:
        log.error("%s", e)
        return 1
    config.RANKINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RANKINGS_DIR / "rankings.csv"
    df.round(4).to_csv(path, index=False)
    info = save_run_info(prices, tickers_ranked=len(df))
    log.info("saved %d rows -> %s (data as of %s)", len(df), path, info["as_of"])
    print(df[["Ticker", "Sector", "Composite", "Quintile"]].head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
