"""SQLite load and the queries in sql/, on tiny results tables with known answers."""
import sqlite3

import pandas as pd
import pytest

from src.database import TABLES, build_database, run_queries


@pytest.fixture
def results_folder(tmp_path):
    """A fake outputs/<universe>/ folder with a 4-stock ranking and 3 months of returns."""
    (tmp_path / "rankings").mkdir()
    pd.DataFrame({
        "Ticker": ["AAA", "BBB", "CCC", "DDD"],
        "Company": ["A Co", "B Co", "C Co", "D Co"],
        "Sector": ["Tech", "Tech", "Energy", None],
        "Composite": [1.0, -0.5, 0.4, 0.1],
        "Quintile": [1, 5, 1, 3],
        "Momentum": [1.2, -0.3, 0.6, 0.0],
        "LowVol": [-0.4, 0.1, 0.5, 0.2],
        "Value": [0.3, 0.2, 1.1, None],
        "Quality": [0.8, -0.1, 0.0, None],
    }).to_csv(tmp_path / TABLES["rankings"], index=False)
    monthly = {"month": ["2024-11-30", "2024-12-31", "2025-01-31"], "SPY": [0.01, 0.02, 0.0],
               "EW_net": [0.02, 0.00, 0.01]}
    for i in range(1, 6):
        monthly[f"Q{i}_net"] = [0.03, -0.01, 0.01 * i]
    pd.DataFrame(monthly).to_csv(tmp_path / TABLES["monthly_returns"], index=False)
    return tmp_path


def test_build_database_loads_available_tables(results_folder) -> None:
    db = results_folder / "test.db"
    assert build_database(results_folder, db) == ["rankings", "monthly_returns"]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM rankings").fetchone() == (4,)


def test_rebuilding_replaces_old_rows(results_folder) -> None:
    db = results_folder / "test.db"
    build_database(results_folder, db)
    build_database(results_folder, db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM monthly_returns").fetchone() == (3,)


def test_queries_give_known_answers(results_folder) -> None:
    db = results_folder / "test.db"
    build_database(results_folder, db)
    res = run_queries(db)
    assert list(res) == ["01_sector_summary", "02_top_stock_per_sector",
                         "03_q1_vs_basket_by_year", "04_quintile_hit_rates"]

    sectors = res["01_sector_summary"].set_index("sector")
    assert sectors.loc["Tech", "stocks"] == 2 and sectors.loc["Tech", "stocks_in_q1"] == 1
    assert sectors.loc["Tech", "pct_in_q1"] == 50.0
    assert sectors.loc["Unknown", "stocks"] == 1  # a missing sector is grouped, not dropped

    leaders = res["02_top_stock_per_sector"]
    assert leaders["ticker"].tolist() == ["AAA", "CCC", "DDD"]  # one per sector, best first

    years = res["03_q1_vs_basket_by_year"].set_index("year")
    assert years.loc["2024", "months"] == 2 and years.loc["2024", "months_q1_beat_ew"] == 1
    assert years.loc["2024", "q1_avg_monthly_pct"] == pytest.approx(1.0)

    hits = res["04_quintile_hit_rates"].set_index("portfolio")
    assert hits.loc["Q1", "months"] == 3
    # Q1 earned 3%, -1%, 1% against SPY's 1%, 2%, 0%: it won 2 of 3 months.
    assert hits.loc["Q1", "pct_months_beat_spy"] == pytest.approx(66.7)
    assert hits.loc["Q5", "pct_months_beat_ew"] == pytest.approx(66.7)
