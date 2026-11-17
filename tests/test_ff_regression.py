"""Fama-French regression on synthetic returns with known alpha and loadings."""
import numpy as np
import pandas as pd
import pytest

from src.ff_regression import ff_regression
from src.french import FACTOR_COLS

BETAS = {"Mkt-RF": 0.9, "SMB": 0.2, "HML": -0.1, "RMW": 0.4, "CMA": 0.05, "UMD": 0.5}
MONTHLY_ALPHA = 0.002


@pytest.fixture
def data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """60 months of factor returns, plus 2 backtest months the factor file does not cover yet."""
    rng = np.random.default_rng(0)
    months = pd.date_range("2020-01-31", periods=62, freq="ME")
    factors = pd.DataFrame(rng.normal(0.0, 0.03, (60, 6)), index=months[:60], columns=FACTOR_COLS)
    factors["RF"] = 0.003
    exposure = sum(b * factors[c] for c, b in BETAS.items())
    q1_excess = MONTHLY_ALPHA + exposure
    monthly = pd.DataFrame({
        "Q1_net": (q1_excess + factors["RF"]).reindex(months, fill_value=0.01),
        "LS_net": exposure.reindex(months, fill_value=0.01),  # zero alpha, already excess
        "EW_net": (factors["Mkt-RF"] + factors["RF"]).reindex(months, fill_value=0.01),
    })
    return monthly, factors


def test_regression_recovers_alpha_and_loadings(data) -> None:
    monthly, factors = data
    res = ff_regression(monthly, factors)
    assert res.loc["Q1", "Alpha_ann"] == pytest.approx(MONTHLY_ALPHA * 12)
    for c, b in BETAS.items():
        assert res.loc["Q1", c] == pytest.approx(b)
    assert res.loc["Q1", "R2"] == pytest.approx(1.0)


def test_long_short_is_not_reduced_by_the_risk_free_rate(data) -> None:
    monthly, factors = data
    res = ff_regression(monthly, factors)
    assert res.loc["LS", "Alpha_ann"] == pytest.approx(0.0, abs=1e-12)
    assert res.loc["EW", "Mkt-RF"] == pytest.approx(1.0)


def test_only_overlapping_months_are_used(data) -> None:
    monthly, factors = data
    res = ff_regression(monthly, factors)
    assert res.loc["Q1", "Months"] == 60
    assert res.loc["Q1", "First"] == "2020-01" and res.loc["Q1", "Last"] == "2024-12"


def test_alpha_t_stat_is_small_for_pure_noise() -> None:
    rng = np.random.default_rng(1)
    months = pd.date_range("2015-01-31", periods=120, freq="ME")
    factors = pd.DataFrame(rng.normal(0.0, 0.03, (120, 6)), index=months, columns=FACTOR_COLS)
    factors["RF"] = 0.0
    noise = pd.Series(rng.normal(0.0, 0.02, 120), index=months)
    monthly = pd.DataFrame({"Q1_net": noise, "LS_net": noise, "EW_net": noise})
    res = ff_regression(monthly, factors)
    assert abs(res.loc["Q1", "Alpha_t"]) < 2.5
    assert res.loc["Q1", "R2"] < 0.2
