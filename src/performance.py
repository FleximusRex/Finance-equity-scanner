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
               turnover: pd.Series | None = None, rf: pd.Series | None = None,
               excess: bool = False) -> dict[str, float]:
    """Annualized return/risk stats for a monthly return series.

    Sharpe, Sortino, beta and alpha use returns in excess of `rf` (0 if not given). Pass
    excess=True for a long-short portfolio, whose return is already an excess return.
    """
    r = r.dropna()
    n = len(r)
    if n < 2:
        return {}
    rf = pd.Series(0.0, index=r.index) if rf is None else rf.reindex(r.index).fillna(0)
    rx = r if excess else r - rf
    cagr = (1 + r).prod() ** (PPY / n) - 1
    vol = r.std() * np.sqrt(PPY)
    downside = np.sqrt((rx.clip(upper=0) ** 2).mean()) * np.sqrt(PPY)
    mdd = max_drawdown(r)
    out = {
        "CAGR": cagr,
        "AnnVol": vol,
        "Sharpe": rx.mean() * PPY / (rx.std() * np.sqrt(PPY)) if rx.std() > 0 else np.nan,
        "Sortino": rx.mean() * PPY / downside if downside > 0 else np.nan,
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
        rrx, bbx = rx[ok], (b - rf)[ok]
        var = bbx.var()
        beta = rrx.cov(bbx) / var if var > 0 else np.nan
        active = rr - bb
        te = active.std() * np.sqrt(PPY)
        out |= {
            "Beta": beta,
            "Alpha": (rrx.mean() - beta * bbx.mean()) * PPY,
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


def holm_adjust(pvalues: pd.Series) -> pd.Series:
    """Holm step-down adjusted p-values for testing several hypotheses at once."""
    p = pvalues.dropna().sort_values()
    m = len(p)
    # The smallest p-value is multiplied by m, the next by m - 1, and so on.
    scaled = p * (m - np.arange(m))
    adjusted = scaled.cummax().clip(upper=1.0)
    return adjusted.reindex(pvalues.index)


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
