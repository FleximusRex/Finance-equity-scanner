"""Small unit tests for scoring and point-in-time factor computation."""
import numpy as np
import pandas as pd
import pytest

from src.factors import price_factors
from src.scoring import FACTORS, score, winsorize, zscore


def test_zscore_standardizes() -> None:
    z = zscore(pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0]}))
    assert abs(z["a"].mean()) < 1e-12 and abs(z["a"].std() - 1) < 1e-12


def test_inverted_factor_rewards_low_values() -> None:
    f = pd.DataFrame({"vol_60d": [0.1, 0.2, 0.3, 0.4, 0.5], "beta": [0.5, 0.8, 1.0, 1.2, 1.5]},
                     index=list("ABCDE"))
    s = score(f, categories=["low_vol"])
    assert s["low_vol"].idxmax() == "A" and s["low_vol"].idxmin() == "E"


def test_winsorize_clips_outliers() -> None:
    df = pd.DataFrame({"x": [*range(99), 1e6]}, dtype=float)
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


def test_metric_count_matches_documentation() -> None:
    """The README and dashboard say 12 metrics in 5 categories; keep them in sync."""
    counts = {cat: len(metrics) for cat, metrics in FACTORS.items()}
    assert counts == {"value": 3, "quality": 3, "momentum": 2, "low_vol": 2, "growth": 2}
    assert sum(counts.values()) == 12


def test_sector_neutral_zscore_is_centred_within_each_sector() -> None:
    # Tech values are ten times larger; within-sector z-scores should ignore that.
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    df = pd.DataFrame({"x": values}, index=[f"T{i}" for i in range(10)])
    sectors = pd.Series(["Tech"] * 5 + ["Energy"] * 5, index=df.index)
    z = zscore(df, sectors)["x"]
    assert abs(z.iloc[:5].mean()) < 1e-12 and abs(z.iloc[5:].mean()) < 1e-12
    assert z.iloc[:5].tolist() == pytest.approx(z.iloc[5:].tolist())


def test_small_sectors_fall_back_to_the_universe_zscore() -> None:
    df = pd.DataFrame({"x": np.arange(8.0)}, index=[f"T{i}" for i in range(8)])
    sectors = pd.Series(["Big"] * 5 + ["Tiny"] * 2 + [None], index=df.index)
    z, plain = zscore(df, sectors)["x"], zscore(df)["x"]
    assert z.iloc[5:].tolist() == pytest.approx(plain.iloc[5:].tolist())  # 2 names, and no sector
    assert z.iloc[:5].tolist() != pytest.approx(plain.iloc[:5].tolist())


def test_score_accepts_sectors() -> None:
    f = pd.DataFrame({"mom_12_1": np.arange(10.0), "ret_6m": np.arange(10.0)},
                     index=[f"T{i}" for i in range(10)])
    sectors = pd.Series(["A"] * 5 + ["B"] * 5, index=f.index)
    s = score(f, categories=["momentum"], sectors=sectors)
    plain = score(f, categories=["momentum"])
    # T4 is below T5 across the universe, but it is the best of sector A and T5 the worst of B.
    assert plain.loc["T4", "momentum"] < plain.loc["T5", "momentum"]
    assert s.loc["T4", "momentum"] > s.loc["T5", "momentum"]
