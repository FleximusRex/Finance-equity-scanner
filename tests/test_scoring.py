"""Small unit tests for scoring and point-in-time factor computation."""
import numpy as np
import pandas as pd

from src.factors import price_factors
from src.scoring import score, winsorize, zscore


def test_zscore_standardizes() -> None:
    z = zscore(pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0]}))
    assert abs(z["a"].mean()) < 1e-12 and abs(z["a"].std() - 1) < 1e-12


def test_inverted_factor_rewards_low_values() -> None:
    f = pd.DataFrame({"vol_60d": [0.1, 0.2, 0.3, 0.4, 0.5], "beta": [0.5, 0.8, 1.0, 1.2, 1.5]},
                     index=list("ABCDE"))
    s = score(f, categories=["low_vol"])
    assert s["low_vol"].idxmax() == "A" and s["low_vol"].idxmin() == "E"


def test_winsorize_clips_outliers() -> None:
    df = pd.DataFrame({"x": list(range(99)) + [1e6]}, dtype=float)
    w = winsorize(df, (0.01, 0.99))
    assert w["x"].max() < 1e6 and w["x"].max() == df["x"].quantile(0.99)


def test_quintiles_one_is_best() -> None:
    f = pd.DataFrame({"mom_12_1": np.arange(10.0), "ret_6m": np.arange(10.0)},
                     index=[f"T{i}" for i in range(10)])
    s = score(f, categories=["momentum"])
    assert s["quintile"].value_counts().eq(2).all()
    assert s.loc["T9", "quintile"] == 1 and s.loc["T0", "quintile"] == 5
    assert s.loc["T9", "percentile"] == 100


def test_price_factors_no_lookahead() -> None:
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2020-01-01", periods=400)
    px = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (400, 4)), 0)),
                      idx, ["A", "B", "C", "SPY"])
    t = idx[300]
    base = price_factors(px, "SPY", asof=t)
    shocked = px.copy()
    shocked.loc[idx > t] *= rng.uniform(0.1, 10, (99, 4))
    pd.testing.assert_frame_equal(base, price_factors(shocked, "SPY", asof=t))
