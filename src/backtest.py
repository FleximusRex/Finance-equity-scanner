"""Monthly-rebalanced quintile backtest on price-based factors: python -m src.backtest

Known limitation: yfinance fundamentals are not point-in-time, so the historical
backtest uses only momentum + low-vol. Universe is today's tickers (survivorship bias).
"""
from __future__ import annotations

import logging
import sys

import numpy as np
import pandas as pd

from src import config
from src.data_loader import load_prices
from src.factors import price_factors
from src.performance import ic_stats, perf_stats, rank_ic
from src.scoring import score

log = logging.getLogger("backtest")
PRICE_CATEGORIES = ["momentum", "low_vol"]
QUINTILES = [f"Q{i}" for i in range(1, 6)]


def rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last trading day of each month in the price index."""
    s = index.to_series()
    return pd.DatetimeIndex(s.groupby(index.to_period("M")).max().to_numpy())


def scores_through_time(prices: pd.DataFrame, dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Composite score and quintile per (date, ticker), using only data up to each date."""
    comp, quint = {}, {}
    for d in dates:
        try:
            sc = score(price_factors(prices, config.BENCHMARK, asof=d), categories=PRICE_CATEGORIES)
        except Exception as e:  # noqa: BLE001
            log.warning("skip %s: %s", d.date(), e)
            continue
        if sc["quintile"].notna().sum() >= 5:
            comp[d], quint[d] = sc["composite"], sc["quintile"]
    return pd.DataFrame(comp).T, pd.DataFrame(quint).T


def _turnover(w: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    """One-way turnover vs. previous weights drifted by realized returns."""
    drift = w.shift(1).fillna(0) * (1 + fwd.shift(1).fillna(0))
    drift = drift.div(drift.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    return 0.5 * (w - drift).abs().sum(axis=1)


def run_backtest(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Monthly gross/net returns + turnover per portfolio, and the rank-IC series."""
    dates = rebalance_dates(prices.index)
    stocks = prices.drop(columns=config.BENCHMARK, errors="ignore")
    px_m = prices.ffill(limit=5).reindex(dates)
    fwd_all = (px_m.shift(-1) / px_m - 1).replace([np.inf, -np.inf], np.nan)
    fwd = fwd_all[stocks.columns]

    comp, quint = scores_through_time(prices, dates[:-1])
    if comp.empty:
        raise RuntimeError("no rebalance date had enough scored stocks")
    fwd = fwd.reindex(index=comp.index, columns=comp.columns)
    held = fwd.notna()  # names without a next-month price are excluded

    cost = config.TRANSACTION_COST_BPS / 1e4
    out: dict[str, pd.Series] = {}
    masks = {q: (quint == i + 1) & held for i, q in enumerate(QUINTILES)}
    masks["EW"] = comp.notna() & held
    for name, m in masks.items():
        w = m.astype(float).div(m.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        gross = (w * fwd.fillna(0)).sum(axis=1).where(m.any(axis=1))
        to = _turnover(w, fwd)
        out[f"{name}_gross"], out[f"{name}_turnover"] = gross, to
        out[f"{name}_net"] = gross - 2 * to * cost  # one-way turnover x 2 = traded notional
    out["LS_gross"] = out["Q1_gross"] - out["Q5_gross"]
    out["LS_turnover"] = out["Q1_turnover"] + out["Q5_turnover"]
    out["LS_net"] = out["LS_gross"] - 2 * out["LS_turnover"] * cost  # both legs pay costs
    out["SPY"] = fwd_all[config.BENCHMARK].reindex(comp.index) if config.BENCHMARK in fwd_all else np.nan

    monthly = pd.DataFrame(out)
    monthly.index = monthly.index + pd.offsets.MonthEnd(0)  # label = start of holding month
    monthly.index.name = "rebalance_month"
    ic = rank_ic(comp, fwd)
    ic.index = monthly.index
    return monthly, ic


def summarize(monthly: pd.DataFrame, ic: pd.Series) -> tuple[pd.DataFrame, dict[str, float]]:
    """Performance table (rows = portfolios) and factor IC stats."""
    bench = monthly["SPY"]
    rows = {}
    for p in QUINTILES + ["LS", "EW"]:
        for kind in ("net", "gross"):
            rows[f"{p}_{kind}"] = perf_stats(monthly[f"{p}_{kind}"], bench, monthly[f"{p}_turnover"])
    rows["SPY"] = perf_stats(bench, bench)
    return pd.DataFrame(rows).T, ic_stats(ic, monthly["LS_gross"])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    prices = load_prices(config.UNIVERSE + [config.BENCHMARK])
    if prices.empty:
        log.error("no price data available")
        return 1
    try:
        monthly, ic = run_backtest(prices)
    except RuntimeError as e:
        log.error("%s", e)
        return 1
    table, fstats = summarize(monthly, ic)

    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    table.round(4).to_csv(config.OUTPUTS_DIR / "backtest_summary.csv", index_label="Portfolio")
    monthly.assign(IC=ic).round(6).to_csv(config.OUTPUTS_DIR / "backtest_monthly_returns.csv")

    show = ["Q1_net", "Q2_net", "Q3_net", "Q4_net", "Q5_net", "LS_net", "LS_gross", "EW_net", "SPY"]
    cols = ["CAGR", "AnnVol", "Sharpe", "MaxDD", "Beta", "Alpha", "InfoRatio", "AvgTurnover"]
    log.info("%d months %s..%s", len(monthly), monthly.index[0].date(), monthly.index[-1].date())
    print(table.loc[show, cols].round(3).to_string())
    print("  ".join(f"{k}={v:.3f}" for k, v in fstats.items() if k != "Months"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
