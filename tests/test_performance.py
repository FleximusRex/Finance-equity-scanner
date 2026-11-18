"""Performance and IC statistics on small series with known answers."""
import numpy as np
import pandas as pd
import pytest

from src.performance import holm_adjust, ic_stats, max_drawdown, perf_stats, rank_ic, ttest


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


def test_sharpe_uses_returns_in_excess_of_the_risk_free_rate() -> None:
    r = pd.Series([0.03, 0.01] * 6)
    rf = pd.Series(0.005, index=r.index)
    s = perf_stats(r, rf=rf)
    vol = r.std() * np.sqrt(12)
    assert s["Sharpe"] == pytest.approx((0.02 - 0.005) * 12 / vol)
    assert s["Sharpe"] < perf_stats(r)["Sharpe"]
    assert s["CAGR"] == perf_stats(r)["CAGR"]  # CAGR is a total return and does not change


def test_long_short_returns_are_already_excess() -> None:
    r = pd.Series([0.03, 0.01] * 6)
    rf = pd.Series(0.005, index=r.index)
    assert perf_stats(r, rf=rf, excess=True)["Sharpe"] == pytest.approx(perf_stats(r)["Sharpe"])


def test_alpha_is_measured_on_excess_returns() -> None:
    rng = np.random.default_rng(0)
    rf = pd.Series(0.004, index=range(60))
    bench = pd.Series(rng.normal(0.01, 0.04, 60))
    r = rf + 1.5 * (bench - rf) + 0.002  # beta 1.5 and monthly alpha 20 bps over the T-bill
    s = perf_stats(r, bench, rf=rf)
    assert s["Beta"] == pytest.approx(1.5)
    assert s["Alpha"] == pytest.approx(0.002 * 12)


def test_holm_adjust_known_values() -> None:
    p = pd.Series({"a": 0.01, "b": 0.04, "c": 0.03})
    adj = holm_adjust(p)
    # sorted: 0.01 x 3, 0.03 x 2, 0.04 x 1 = 0.03, 0.06, 0.04; then never allowed to decrease
    assert adj["a"] == pytest.approx(0.03)
    assert adj["c"] == pytest.approx(0.06)
    assert adj["b"] == pytest.approx(0.06)


def test_holm_adjust_caps_at_one_and_matches_statsmodels() -> None:
    from statsmodels.stats.multitest import multipletests

    p = pd.Series([0.565, 0.249, 0.098, 0.103, 0.897])
    adj = holm_adjust(p)
    assert adj.max() <= 1.0
    assert adj.tolist() == pytest.approx(multipletests(p, method="holm")[1].tolist())


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
