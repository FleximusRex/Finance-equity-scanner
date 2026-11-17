"""Turnover, transaction costs and quintile assignment on a tiny synthetic portfolio."""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.backtest import (
    _turnover,
    backtest_signal,
    factor_tests,
    quintiles,
    rebalance_dates,
    robustness_table,
    summarize,
)


def test_turnover_measures_trades_against_drifted_weights() -> None:
    idx = pd.date_range("2024-01-31", periods=2, freq="ME")
    w = pd.DataFrame([[0.5, 0.5, 0.0, 0.0], [0.0, 0.5, 0.5, 0.0]], index=idx, columns=list("ABCD"))
    fwd = pd.DataFrame([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]], index=idx, columns=w.columns)
    to = _turnover(w, fwd)
    # Opening the book trades half of the 100% notional one way.
    assert to.iloc[0] == pytest.approx(0.5)
    # A doubled to 2/3 of the book before the rebalance: 0.5 * (2/3 + 1/6 + 1/2).
    assert to.iloc[1] == pytest.approx(2 / 3)


def test_quintile_one_is_highest_signal() -> None:
    sig = pd.DataFrame([np.arange(10.0)], columns=[f"T{i}" for i in range(10)])
    q = quintiles(sig).iloc[0]
    assert q["T9"] == 1 and q["T8"] == 1 and q["T0"] == 5


def test_quintiles_need_five_names() -> None:
    sig = pd.DataFrame([[1.0, 2.0, 3.0, 4.0]], columns=list("ABCD"))
    assert quintiles(sig).isna().all().all()


def test_rebalance_dates_are_month_ends() -> None:
    idx = pd.bdate_range("2024-01-01", "2024-03-31")
    assert list(rebalance_dates(idx)) == [
        pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29"), pd.Timestamp("2024-03-29")]


def test_rebalance_dates_drop_a_partial_final_month() -> None:
    idx = pd.bdate_range("2024-01-01", "2024-03-05")  # stops three trading days into March
    assert list(rebalance_dates(idx)) == [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29")]


def test_backtest_ignores_a_partial_final_month() -> None:
    """Prices ending mid-month give the same months as prices cut at the last month-end."""
    idx = pd.bdate_range("2024-01-01", "2024-07-05")
    growth = {f"S{i}": 1 + 0.002 * i for i in range(10)}
    prices = pd.DataFrame({t: 100 * g ** np.arange(len(idx)) for t, g in growth.items()}, index=idx)
    prices["SPY"] = 100 * 1.001 ** np.arange(len(idx))
    dates = rebalance_dates(idx)[:-1]
    sig = pd.DataFrame([np.arange(10.0)] * len(dates), index=dates, columns=list(growth))

    monthly, _ = backtest_signal(prices, sig)
    full_months, _ = backtest_signal(prices.loc[:"2024-06-30"], sig)
    # Signals from the end of January to the end of May are held February to June.
    assert list(monthly.index) == list(pd.date_range("2024-02-29", "2024-06-30", freq="ME"))
    pd.testing.assert_frame_equal(monthly, full_months)


@pytest.fixture
def synthetic() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ten stocks growing at constant, increasing rates, and a signal that ranks them correctly."""
    idx = pd.bdate_range("2024-01-01", "2024-07-31")
    growth = {f"S{i}": 1 + 0.002 * i for i in range(10)}
    prices = pd.DataFrame({t: 100 * g ** np.arange(len(idx)) for t, g in growth.items()}, index=idx)
    prices["SPY"] = 100 * 1.001 ** np.arange(len(idx))
    dates = rebalance_dates(idx)[:-1]
    sig = pd.DataFrame([np.arange(10.0)] * len(dates), index=dates, columns=list(growth))
    return prices, sig


def test_backtest_net_returns_subtract_two_way_costs(synthetic) -> None:
    prices, sig = synthetic
    monthly, _ = backtest_signal(prices, sig)
    cost = config.TRANSACTION_COST_BPS / 1e4
    for p in ("Q1", "Q5", "EW"):
        expected = monthly[f"{p}_gross"] - 2 * monthly[f"{p}_turnover"] * cost
        pd.testing.assert_series_equal(monthly[f"{p}_net"], expected, check_names=False)
    # The long-short book pays on both legs.
    assert monthly["LS_turnover"].tolist() == pytest.approx(
        (monthly["Q1_turnover"] + monthly["Q5_turnover"]).tolist())


def test_backtest_ranks_winners_in_q1(synthetic) -> None:
    prices, sig = synthetic
    monthly, ic = backtest_signal(prices, sig)
    assert (monthly["Q1_gross"] > monthly["Q5_gross"]).all()
    assert (monthly["LS_gross"] > 0).all()
    assert ic.dropna().tolist() == pytest.approx([1.0] * len(ic.dropna()))


def test_static_signal_has_low_turnover_after_the_first_month(synthetic) -> None:
    prices, sig = synthetic
    monthly, _ = backtest_signal(prices, sig)
    assert monthly["Q1_turnover"].iloc[0] == pytest.approx(0.5)
    assert (monthly["Q1_turnover"].iloc[1:] < 0.02).all()


def test_rows_are_labelled_with_the_holding_month(synthetic) -> None:
    prices, sig = synthetic
    monthly, _ = backtest_signal(prices, sig)
    assert monthly.index.name == "month"
    assert monthly.index[0] == pd.Timestamp("2024-02-29")  # the January signal is held in February
    assert monthly.index[-1] == pd.Timestamp("2024-07-31")
    feb = prices["SPY"].loc["2024-02-29"] / prices["SPY"].loc["2024-01-31"] - 1
    assert monthly["SPY"].iloc[0] == pytest.approx(feb)


def test_cost_per_side_can_be_overridden(synthetic) -> None:
    prices, sig = synthetic
    free, _ = backtest_signal(prices, sig, cost_bps=0)
    costly, _ = backtest_signal(prices, sig, cost_bps=50)
    pd.testing.assert_series_equal(free["Q1_net"], free["Q1_gross"], check_names=False)
    expected = costly["Q1_gross"] - 2 * costly["Q1_turnover"] * 0.005
    pd.testing.assert_series_equal(costly["Q1_net"], expected, check_names=False)


def test_one_day_lag_trades_at_the_next_close(synthetic) -> None:
    prices, sig = synthetic
    lagged, _ = backtest_signal(prices, sig, lag_days=1)
    # The first trade is at the 1 Feb close and the position is held to the 1 Mar close.
    expected = prices["SPY"].loc["2024-03-01"] / prices["SPY"].loc["2024-02-01"] - 1
    assert lagged["SPY"].iloc[0] == pytest.approx(expected)


@pytest.mark.filterwarnings("ignore:Precision loss")  # constant synthetic returns
def test_summarize_uses_the_rf_column_for_sharpe(synthetic) -> None:
    prices, sig = synthetic
    monthly, ic = backtest_signal(prices, sig)
    no_rf, _ = summarize(monthly, ic)
    with_rf, _ = summarize(monthly.assign(RF=0.004), ic)
    assert with_rf.loc["Q1_net", "CAGR"] == pytest.approx(no_rf.loc["Q1_net", "CAGR"])
    # Q1 earns 0.4% a month less in excess terms; the long-short is self-financing and unchanged.
    assert with_rf.loc["Q1_net", "Sharpe"] < no_rf.loc["Q1_net", "Sharpe"]
    assert with_rf.loc["LS_net", "Sharpe"] == pytest.approx(no_rf.loc["LS_net", "Sharpe"])


def test_robustness_table_has_every_case(synthetic) -> None:
    prices, sig = synthetic
    rob = robustness_table(prices, sig)
    assert list(rob.index) == [
        "Cost 0 bps per side", "Cost 10 bps per side", "Cost 25 bps per side",
        "Cost 50 bps per side", "Sub-period 2015-2019", "Sub-period 2020-2022",
        "Sub-period 2023-latest", "One-day execution lag"]
    # Higher costs can only lower the net return.
    costs = rob["Q1_CAGR"].iloc[:4]
    assert costs.is_monotonic_decreasing
    # The synthetic prices are all in 2024, so only the last sub-period has data.
    assert rob.loc["Sub-period 2015-2019", "Months"] == 0
    assert rob.loc["Sub-period 2023-latest", "Months"] == len(sig)


@pytest.mark.filterwarnings("ignore:Precision loss")  # constant synthetic returns
def test_factor_tests_report_holm_adjusted_p_values(synthetic) -> None:
    prices, sig = synthetic
    noise = pd.DataFrame(np.random.default_rng(0).normal(size=sig.shape),
                         index=sig.index, columns=sig.columns)
    sigs = {"mom_12_1": sig, "ret_6m": noise, "vol_60d": -noise, "beta": sig, "composite": noise}
    ft = factor_tests(prices, sigs)
    assert list(ft.columns[:4]) == ["IC_mean", "IC_t", "IC_p", "IC_p_holm"]
    ok = ft["IC_p"].notna()
    assert (ft.loc[ok, "IC_p_holm"] >= ft.loc[ok, "IC_p"]).all()
