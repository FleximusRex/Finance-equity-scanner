"""Raw factor metrics from prices and fundamentals."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config

TRADING_DAYS = 252


def safe_div(num: pd.Series, den: pd.Series, positive_den: bool = True) -> pd.Series:
    """num/den with NaN where den is <=0 (or ==0 if positive_den=False), and no infs."""
    num, den = num.astype(float), den.astype(float)
    ok = den > 0 if positive_den else den != 0
    return (num.where(ok) / den.where(ok)).replace([np.inf, -np.inf], np.nan)


def _lag(px: pd.DataFrame, n: int) -> pd.Series:
    """Price n rows before the last row (NaN if history too short)."""
    return px.iloc[-1 - n] if len(px) > n else pd.Series(np.nan, index=px.columns)


def price_factors(prices: pd.DataFrame, benchmark: str = config.BENCHMARK,
                  asof: pd.Timestamp | str | None = None) -> pd.DataFrame:
    """Returns, momentum, volatility and beta using only data up to `asof`."""
    if asof is not None:
        prices = prices.loc[:asof]
    px = prices.drop(columns=benchmark, errors="ignore")
    enough = px.notna().sum() >= config.MIN_PRICE_HISTORY
    px = px.ffill(limit=5)

    out = pd.DataFrame(index=px.columns)
    out["ret_1m"] = safe_div(_lag(px, 0), _lag(px, 21)) - 1
    out["ret_6m"] = safe_div(_lag(px, 0), _lag(px, 126)) - 1
    out["ret_12m"] = safe_div(_lag(px, 0), _lag(px, 252)) - 1
    out["mom_12_1"] = safe_div(_lag(px, 21), _lag(px, 252)) - 1

    rets = px.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    w60 = rets.iloc[-60:]
    out["vol_60d"] = (w60.std() * np.sqrt(TRADING_DAYS)).where(w60.count() >= 40)

    if benchmark in prices.columns:
        r = rets.iloc[-TRADING_DAYS:]
        b = prices[benchmark].ffill(limit=5).pct_change(fill_method=None).iloc[-TRADING_DAYS:]
        mask = r.notna() & b.notna().to_numpy()[:, None]
        rb = pd.DataFrame(np.where(mask, b.to_numpy()[:, None], np.nan), index=r.index, columns=r.columns)
        r = r.where(mask)
        n = mask.sum()
        cov = ((r - r.mean()) * (rb - rb.mean())).sum() / (n - 1)
        var = ((rb - rb.mean()) ** 2).sum() / (n - 1)
        out["beta"] = safe_div(cov, var).where(n >= 120)
    else:
        out["beta"] = np.nan

    out.loc[~enough] = np.nan
    return out


def fundamental_factors(fund: pd.DataFrame) -> pd.DataFrame:
    """Value, quality and growth metrics from current yfinance info."""
    f = fund.reindex(columns=["price", "eps", "fcf", "market_cap", "ev", "ebitda", "roe",
                              "gross_margin", "debt_to_equity", "revenue_growth",
                              "earnings_growth"]).astype(float)
    out = pd.DataFrame(index=fund.index)
    out["earnings_yield"] = safe_div(f["eps"], f["price"])
    out["fcf_yield"] = safe_div(f["fcf"], f["market_cap"])
    # EV/EBITDA is only meaningful with positive EV and EBITDA.
    out["ev_ebitda"] = safe_div(f["ev"].where(f["ev"] > 0), f["ebitda"])
    out["roe"] = f["roe"]
    out["gross_margin"] = f["gross_margin"]
    # yfinance reports D/E in percent; negative means negative equity -> NaN.
    out["debt_to_equity"] = (f["debt_to_equity"] / 100).where(f["debt_to_equity"] >= 0)
    out["revenue_growth"] = f["revenue_growth"]
    out["earnings_growth"] = f["earnings_growth"]
    return out.replace([np.inf, -np.inf], np.nan)


def compute_factors(prices: pd.DataFrame, fund: pd.DataFrame,
                    benchmark: str = config.BENCHMARK) -> pd.DataFrame:
    """All factor metrics, one row per ticker."""
    pf = price_factors(prices, benchmark)
    ff = fundamental_factors(fund)
    return pf.join(ff, how="outer")
