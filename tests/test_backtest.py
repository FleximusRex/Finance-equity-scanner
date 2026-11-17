"""Turnover, transaction costs and quintile assignment on a tiny synthetic portfolio."""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.backtest import _turnover, backtest_signal, quintiles, rebalance_dates


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
