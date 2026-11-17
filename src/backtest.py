"""Monthly-rebalanced quintile backtest on price-based factors.

Run: python -m src.backtest [--universe {test50,sp100,sp500}] [--sector-neutral]

Known limitation: yfinance fundamentals are not point-in-time, so the historical
backtest uses only momentum + low-vol. Universe is today's tickers (survivorship bias).
"""
from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

import numpy as np
import pandas as pd

from src import cli, config, french
from src.data_loader import load_prices
from src.factors import price_factors
from src.ff_regression import ff_regression
from src.performance import holm_adjust, ic_stats, perf_stats, rank_ic
from src.run_info import save_run_info
from src.scoring import score, winsorize, zscore
from src.universe import get_universe, sectors

log = logging.getLogger("backtest")
PRICE_CATEGORIES = ["momentum", "low_vol"]
QUINTILES = [f"Q{i}" for i in range(1, 6)]
# single price factors tested alone: column -> sign (+1 = higher is better)
SINGLE_FACTORS = {"mom_12_1": 1, "ret_6m": 1, "vol_60d": -1, "beta": -1}


def rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last trading day of each complete month in the price index."""
    s = index.to_series()
    dates = pd.DatetimeIndex(s.groupby(index.to_period("M")).max().to_numpy())
    # If the next business day is still in the same month, the data stops mid-month. Dropping
    # that month keeps a few trading days from being counted as a full holding month.
    last = dates[-1]
    if (last + pd.offsets.BDay(1)).to_period("M") == last.to_period("M"):
        dates = dates[:-1]
    return dates


def signals_through_time(prices: pd.DataFrame, dates: pd.DatetimeIndex,
                         sectors: pd.Series | None = None) -> dict[str, pd.DataFrame]:
    """Composite and signed single-factor signals per (date, ticker), from data up to each date.

    If `sectors` is given, every signal is z-scored within sector (sector-neutral).
    """
    signs = pd.Series(SINGLE_FACTORS)
    panels: dict[str, dict] = {k: {} for k in ["composite", *SINGLE_FACTORS]}
    for d in dates:
        try:
            pf = price_factors(prices, config.BENCHMARK, asof=d)
            sc = score(pf, categories=PRICE_CATEGORIES, sectors=sectors)
        except (ValueError, KeyError, IndexError) as e:
            log.warning("skip %s: %s", d.date(), e)
            continue
        panels["composite"][d] = sc["composite"]
        # Without sectors the raw value is enough: ranks are invariant to winsor/z-score.
        single = pf[signs.index] * signs
        if sectors is not None:
            single = zscore(winsorize(pf[signs.index]), sectors) * signs
        for f in SINGLE_FACTORS:
            panels[f][d] = single[f]
    return {k: pd.DataFrame(v).T for k, v in panels.items()}


def quintiles(sig: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional quintile per date (1 = highest signal); NaN on dates with <5 names."""
    order = sig.rank(axis=1, ascending=False, method="first")
    n = order.count(axis=1)
    return np.ceil(order.mul(5).div(n, axis=0)).where(n >= 5, axis=0)


def _turnover(w: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    """One-way turnover vs. previous weights drifted by realized returns."""
    drift = w.shift(1).fillna(0) * (1 + fwd.shift(1).fillna(0))
    drift = drift.div(drift.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    return 0.5 * (w - drift).abs().sum(axis=1)


def backtest_signal(prices: pd.DataFrame, sig: pd.DataFrame, cost_bps: float | None = None,
                    lag_days: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    """Monthly gross/net returns and turnover per quintile portfolio of `sig`, plus rank IC.

    `cost_bps` is the cost per side (default: config.TRANSACTION_COST_BPS). `lag_days` trades
    that many days after each rebalance date instead of at its close.
    """
    dates = rebalance_dates(prices.index)
    px = prices.ffill(limit=5)
    if lag_days:
        px = px.shift(-lag_days)  # each row now holds the close `lag_days` later
    px_m = px.reindex(dates)
    fwd_all = (px_m.shift(-1) / px_m - 1).replace([np.inf, -np.inf], np.nan)

    quint = quintiles(sig)
    keep = quint.notna().any(axis=1)
    comp, quint = sig[keep], quint[keep]
    if comp.empty:
        raise RuntimeError("no rebalance date had enough scored stocks")
    fwd = fwd_all.reindex(index=comp.index, columns=comp.columns)
    held = fwd.notna()  # names without a next-month price are excluded

    cost = (config.TRANSACTION_COST_BPS if cost_bps is None else cost_bps) / 1e4
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
    out["SPY"] = np.nan
    if config.BENCHMARK in fwd_all:
        out["SPY"] = fwd_all[config.BENCHMARK].reindex(comp.index)

    monthly = pd.DataFrame(out)
    # Label each row with the month the return was earned in (the month after the signal date).
    monthly.index = monthly.index + pd.offsets.MonthEnd(0) + pd.offsets.MonthEnd(1)
    monthly.index.name = "month"
    ic = rank_ic(comp, fwd)
    ic.index = monthly.index
    return monthly, ic


def run_backtest(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Backtest of the price-factor composite (momentum + low vol)."""
    sigs = signals_through_time(prices, rebalance_dates(prices.index)[:-1])
    return backtest_signal(prices, sigs["composite"])


def factor_tests(prices: pd.DataFrame, sigs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """IC and quintile CAGR stats for each single price factor and the composite (net of costs)."""
    sigs = sigs or signals_through_time(prices, rebalance_dates(prices.index)[:-1])
    rows = {}
    for name in [*SINGLE_FACTORS, "composite"]:
        try:
            monthly, ic = backtest_signal(prices, sigs[name])
        except RuntimeError as e:
            log.warning("factor %s: %s", name, e)
            continue
        fs = ic_stats(ic, monthly["LS_gross"])
        cagr = {p: perf_stats(monthly[f"{p}_net"]).get("CAGR", np.nan) for p in ("Q1", "Q5", "LS")}
        rows[name] = {"IC_mean": fs["IC_mean"], "IC_t": fs["IC_t"], "IC_p": fs["IC_p"],
                      "Q1_CAGR": cagr["Q1"], "Q5_CAGR": cagr["Q5"], "LS_CAGR": cagr["LS"],
                      "Months": fs["Months"]}
    table = pd.DataFrame.from_dict(rows, orient="index").rename_axis("factor")
    # Testing several signals raises the chance that one looks significant by luck.
    table.insert(3, "IC_p_holm", holm_adjust(table["IC_p"]))
    return table


def summarize(monthly: pd.DataFrame, ic: pd.Series) -> tuple[pd.DataFrame, dict[str, float]]:
    """Performance table (rows = portfolios) and factor IC stats.

    Sharpe, Sortino, beta and alpha use excess returns if `monthly` has an RF column.
    """
    bench = monthly["SPY"]
    rf = monthly["RF"] if "RF" in monthly else None
    rows = {}
    for p in [*QUINTILES, "LS", "EW"]:
        for kind in ("net", "gross"):
            r, to = monthly[f"{p}_{kind}"], monthly[f"{p}_turnover"]
            rows[f"{p}_{kind}"] = perf_stats(r, bench, to, rf=rf, excess=(p == "LS"))
    rows["SPY"] = perf_stats(bench, bench, rf=rf)
    return pd.DataFrame(rows).T, ic_stats(ic, monthly["LS_gross"])


def _robustness_row(monthly: pd.DataFrame, rf: pd.Series | None) -> dict[str, float]:
    """Net CAGR and excess-return Sharpe of Q1, the long-short and the equal-weight universe."""
    out: dict[str, float] = {}
    for p in ("Q1", "LS", "EW"):
        stats = perf_stats(monthly[f"{p}_net"], rf=rf, excess=(p == "LS"))
        out[f"{p}_CAGR"] = stats.get("CAGR", np.nan)
        out[f"{p}_Sharpe"] = stats.get("Sharpe", np.nan)
    out["Months"] = len(monthly)
    return out


def robustness_table(prices: pd.DataFrame, sig: pd.DataFrame,
                     rf: pd.Series | None = None) -> pd.DataFrame:
    """Rerun the backtest of `sig` under each cost level, sub-period and a one-day lag."""
    rows = {}
    for bps in config.COST_GRID_BPS:
        monthly, _ = backtest_signal(prices, sig, cost_bps=bps)
        rows[f"Cost {bps} bps per side"] = _robustness_row(monthly, rf)

    base, _ = backtest_signal(prices, sig)
    for label, (start, end) in config.SUBPERIODS.items():
        rows[f"Sub-period {label}"] = _robustness_row(base.loc[start:end], rf)

    # Signal at the month-end close, trade at the next day's close.
    lagged, _ = backtest_signal(prices, sig, lag_days=1)
    rows["One-day execution lag"] = _robustness_row(lagged, rf)
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("Case")


def main(argv: Sequence[str] | None = None) -> int:
    cli.parse_args("Run the price-factor quintile backtest and single-factor tests.", argv)
    cli.setup_logging()
    prices = load_prices([*get_universe(), config.BENCHMARK])
    if prices.empty:
        log.error("no price data available")
        return 1
    sector = sectors() if config.SECTOR_NEUTRAL else None
    try:
        sigs = signals_through_time(prices, rebalance_dates(prices.index)[:-1], sector)
        monthly, ic = backtest_signal(prices, sigs["composite"])
    except RuntimeError as e:
        log.error("%s", e)
        return 1
    monthly["RF"] = french.risk_free(monthly.index)
    table, fstats = summarize(monthly, ic)

    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    table.round(4).to_csv(config.OUTPUTS_DIR / "backtest_summary.csv", index_label="Portfolio")
    monthly.assign(IC=ic).round(6).to_csv(config.OUTPUTS_DIR / "backtest_monthly_returns.csv")
    save_run_info(prices, tickers=int(prices.drop(columns=config.BENCHMARK).shape[1]),
                  months=len(monthly), first_month=f"{monthly.index[0]:%Y-%m}",
                  last_month=f"{monthly.index[-1]:%Y-%m}")

    show = ["Q1_net", "Q2_net", "Q3_net", "Q4_net", "Q5_net", "LS_net", "LS_gross", "EW_net", "SPY"]
    cols = ["CAGR", "AnnVol", "Sharpe", "MaxDD", "Beta", "Alpha", "InfoRatio", "AvgTurnover"]
    log.info("universe=%s  %d holding months, %s to %s", config.UNIVERSE_MODE, len(monthly),
             f"{monthly.index[0]:%b %Y}", f"{monthly.index[-1]:%b %Y}")
    print(table.loc[show, cols].round(3).to_string())
    print("  ".join(f"{k}={v:.3f}" for k, v in fstats.items() if k != "Months"))

    ft = factor_tests(prices, sigs)
    ft.round(4).to_csv(config.OUTPUTS_DIR / "factor_tests.csv")
    print(ft.drop(columns="Months").round(3).to_string())

    ff = ff_regression(monthly, french.load_factors())
    ff.round(4).to_csv(config.OUTPUTS_DIR / "ff_regression.csv")
    print(ff[["Alpha_ann", "Alpha_t", *french.FACTOR_COLS, "R2", "Months"]].to_string())

    rob = robustness_table(prices, sigs["composite"], monthly["RF"])
    rob.round(4).to_csv(config.OUTPUTS_DIR / "robustness.csv")
    print(rob.round(3).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
