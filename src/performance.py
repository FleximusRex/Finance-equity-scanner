"""Portfolio performance and factor (IC) statistics on monthly returns."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

PPY = 12  # periods per year


def max_drawdown(r: pd.Series) -> float:
    """Most negative peak-to-trough decline of the compounded series."""
    wealth = (1 + r.fillna(0)).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def perf_stats(r: pd.Series, bench: pd.Series | None = None,
               turnover: pd.Series | None = None) -> dict[str, float]:
    """Annualized return/risk stats for a monthly return series (rf = 0)."""
    r = r.dropna()
    n = len(r)
    if n < 2:
        return {}
    cagr = (1 + r).prod() ** (PPY / n) - 1
    vol = r.std() * np.sqrt(PPY)
    downside = np.sqrt((r.clip(upper=0) ** 2).mean()) * np.sqrt(PPY)
    mdd = max_drawdown(r)
    out = {
        "CAGR": cagr,
        "AnnVol": vol,
        "Sharpe": r.mean() * PPY / vol if vol > 0 else np.nan,
        "Sortino": r.mean() * PPY / downside if downside > 0 else np.nan,
        "MaxDD": mdd,
        "Calmar": cagr / abs(mdd) if mdd < 0 else np.nan,
        "WinRate": (r > 0).mean(),
        "BestMonth": r.max(),
        "WorstMonth": r.min(),
    }
    if bench is not None:
        b = bench.reindex(r.index)
        ok = b.notna()
        rr, bb = r[ok], b[ok]
        var = bb.var()
        beta = rr.cov(bb) / var if var > 0 else np.nan
        active = rr - bb
        te = active.std() * np.sqrt(PPY)
        out |= {
            "Beta": beta,
            "Alpha": (rr.mean() - beta * bb.mean()) * PPY,
            "TrackingError": te,
            "InfoRatio": active.mean() * PPY / te if te > 0 else np.nan,
        }
    out["AvgTurnover"] = turnover.reindex(r.index).mean() if turnover is not None else np.nan
    return out


def ttest(x: pd.Series) -> tuple[float, float]:
    """t-stat and two-sided p-value that the mean of x is zero."""
    x = x.dropna()
    if len(x) < 3:
        return np.nan, np.nan
    res = stats.ttest_1samp(x, 0.0)
    return float(res.statistic), float(res.pvalue)


def rank_ic(scores: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    """Per-date Spearman correlation of scores vs next-period returns."""
    ok = scores.notna() & fwd.notna()
    s = scores.where(ok).rank(axis=1)
    f = fwd.where(ok).rank(axis=1)
    ic = s.corrwith(f, axis=1)
    return ic.where(ok.sum(axis=1) >= 5)


def ic_stats(ic: pd.Series, spread: pd.Series) -> dict[str, float]:
    """IC mean/std/IR with t-tests on mean IC and on the long-short spread."""
    ic = ic.dropna()
    t_ic, p_ic = ttest(ic)
    t_ls, p_ls = ttest(spread)
    return {
        "IC_mean": ic.mean(), "IC_std": ic.std(),
        "IC_IR": ic.mean() / ic.std() if ic.std() > 0 else np.nan,
        "IC_t": t_ic, "IC_p": p_ic, "LS_t": t_ls, "LS_p": p_ls, "Months": len(ic),
    }
