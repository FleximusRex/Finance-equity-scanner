"""Winsorize, z-score and combine factors into category and composite scores."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config

# category -> {factor column: sign}; -1 means lower raw value is better.
FACTORS: dict[str, dict[str, int]] = {
    "value": {"earnings_yield": 1, "fcf_yield": 1, "ev_ebitda": -1},
    "quality": {"roe": 1, "gross_margin": 1, "debt_to_equity": -1},
    "momentum": {"mom_12_1": 1, "ret_6m": 1},
    "low_vol": {"vol_60d": -1, "beta": -1},
    "growth": {"revenue_growth": 1, "earnings_growth": 1},
}


def winsorize(df: pd.DataFrame, limits: tuple[float, float] = config.WINSOR) -> pd.DataFrame:
    """Clip each column to its cross-sectional quantiles."""
    return df.clip(df.quantile(limits[0]), df.quantile(limits[1]), axis=1)


def zscore(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score per column (NaN if std is 0)."""
    return (df - df.mean()) / df.std().replace(0, np.nan)


def score(factors: pd.DataFrame, weights: dict[str, float] = config.FACTOR_WEIGHTS,
          categories: list[str] | None = None) -> pd.DataFrame:
    """Category scores, composite, percentile (100 = best) and quintile (1 = best)."""
    categories = categories or list(weights)
    signs = pd.Series({c: s for cat in categories for c, s in FACTORS[cat].items()})
    z = zscore(winsorize(factors.reindex(columns=signs.index).astype(float))) * signs
    out = pd.DataFrame({cat: z[list(FACTORS[cat])].mean(axis=1) for cat in categories})

    w = pd.Series({c: weights[c] for c in categories})
    wsum = out.notna().mul(w).sum(axis=1).replace(0, np.nan)  # re-normalize missing cats
    out["composite"] = out.fillna(0).mul(w).sum(axis=1) / wsum

    out["percentile"] = out["composite"].rank(pct=True) * 100
    order = out["composite"].rank(ascending=False, method="first")
    out["quintile"] = (pd.qcut(order, 5, labels=False) + 1 if order.notna().sum() >= 5
                       else np.nan)
    out["quintile"] = out["quintile"].astype("Int64")
    return out
