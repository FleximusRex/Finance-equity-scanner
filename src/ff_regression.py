"""Fama-French five-factor plus momentum regression of the backtest portfolios."""
from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from src import config
from src.french import FACTOR_COLS
from src.performance import PPY

# portfolio -> column of monthly net returns in the backtest table
PORTFOLIOS = {"Q1": "Q1_net", "LS": "LS_net", "EW": "EW_net"}


def ff_regression(monthly: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Alpha, factor loadings and R2 for each portfolio, with Newey-West (HAC) t-stats."""
    # The French files are published a month or two late, so only overlapping months are used.
    f = factors.reindex(monthly.index).dropna(subset=[*FACTOR_COLS, "RF"])
    m = monthly.loc[f.index]
    x = sm.add_constant(f[FACTOR_COLS])
    rows = {}
    for name, col in PORTFOLIOS.items():
        # The long-short portfolio is self-financing, so its return is already an excess return.
        y = m[col] if name == "LS" else m[col] - f["RF"]
        fit = sm.OLS(y, x, missing="drop").fit(
            cov_type="HAC", cov_kwds={"maxlags": config.NEWEY_WEST_LAGS})
        row = {"Alpha_ann": fit.params["const"] * PPY, "Alpha_t": fit.tvalues["const"],
               "Alpha_p": fit.pvalues["const"]}
        for c in FACTOR_COLS:
            row[c] = fit.params[c]
            row[f"{c}_t"] = fit.tvalues[c]
        row["R2"] = fit.rsquared
        row["Months"] = int(fit.nobs)
        row["First"] = f"{f.index[0]:%Y-%m}"
        row["Last"] = f"{f.index[-1]:%Y-%m}"
        rows[name] = row
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("Portfolio")
