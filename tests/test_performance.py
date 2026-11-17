"""Performance and IC statistics on small series with known answers."""
import numpy as np
import pandas as pd
import pytest

from src.performance import ic_stats, max_drawdown, perf_stats, rank_ic, ttest


def test_max_drawdown_known_path() -> None:
    # wealth: 1.10 -> 0.55 -> 0.66, so the worst drop is 0.55 / 1.10 - 1 = -50%
    assert max_drawdown(pd.Series([0.10, -0.50, 0.20])) == pytest.approx(-0.5)


def test_max_drawdown_is_zero_when_always_rising() -> None:
    assert max_drawdown(pd.Series([0.01, 0.02, 0.03])) == 0.0


def test_cagr_sharpe_and_drawdown_on_alternating_returns() -> None:
    r = pd.Series([0.02, 0.0] * 6)  # 12 months
    s = perf_stats(r)
    assert s["CAGR"] == pytest.approx(1.02**6 - 1)
    vol = r.std() * np.sqrt(12)
    assert s["AnnVol"] == pytest.approx(vol)
    assert s["Sharpe"] == pytest.approx(0.01 * 12 / vol)
    assert s["MaxDD"] == 0.0
    assert s["WinRate"] == 0.5


def test_cagr_uses_partial_years() -> None:
    r = pd.Series([0.10] * 6)  # half a year of 10% months
    assert perf_stats(r)["CAGR"] == pytest.approx(1.1**12 - 1)


def test_beta_and_alpha_against_benchmark() -> None:
    rng = np.random.default_rng(0)
    bench = pd.Series(rng.normal(0.01, 0.04, 60))
    r = 2 * bench + 0.001  # beta 2, monthly alpha 10 bps
    s = perf_stats(r, bench)
    assert s["Beta"] == pytest.approx(2.0)
    assert s["Alpha"] == pytest.approx(0.001 * 12)
    assert s["InfoRatio"] > 0


def test_perf_stats_needs_two_observations() -> None:
    assert perf_stats(pd.Series([0.01])) == {}


def test_ttest_matches_manual_formula() -> None:
    x = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
    t, p = ttest(x)
    assert t == pytest.approx(x.mean() / (x.std() / np.sqrt(len(x))))
    assert 0 < p < 0.05


def test_ttest_too_short_is_nan() -> None:
    t, p = ttest(pd.Series([0.1, 0.2]))
    assert np.isnan(t) and np.isnan(p)


def test_rank_ic_perfect_and_inverted() -> None:
    idx = pd.date_range("2024-01-31", periods=3, freq="ME")
    cols = list("ABCDEF")
    scores = pd.DataFrame([np.arange(6.0)] * 3, index=idx, columns=cols)
    assert rank_ic(scores, scores * 0.01).tolist() == pytest.approx([1.0] * 3)
    assert rank_ic(scores, -scores).tolist() == pytest.approx([-1.0] * 3)


def test_rank_ic_is_nan_with_fewer_than_five_names() -> None:
    scores = pd.DataFrame([[1.0, 2.0, 3.0, 4.0]], columns=list("ABCD"))
    assert rank_ic(scores, scores).isna().all()


def test_ic_stats_reports_t_test_on_mean_ic() -> None:
    ic = pd.Series([0.05, 0.03, 0.08, -0.01, 0.04, 0.06])
    spread = pd.Series([0.01, -0.02, 0.03, 0.00, 0.02, -0.01])
    s = ic_stats(ic, spread)
    assert s["IC_mean"] == pytest.approx(ic.mean())
    assert s["IC_t"] == pytest.approx(ic.mean() / (ic.std() / np.sqrt(6)))
    assert s["Months"] == 6
