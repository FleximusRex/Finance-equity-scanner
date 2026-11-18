"""Excel export: sheets, frozen header, number formats and the color scale."""
import pandas as pd
import pytest
from openpyxl import load_workbook

from src.excel_export import SHEETS, load_tables, write_workbook

INFO = {"universe": "test50", "as_of": "2026-11-16", "tickers": 2, "months": 142,
        "first_month": "2015-01", "last_month": "2026-10", "git_commit": "abc1234"}


@pytest.fixture
def tables() -> dict[str, pd.DataFrame]:
    rankings = pd.DataFrame({
        "Ticker": ["AAA", "BBB"], "Company": ["Alpha Corp", "Beta Inc"], "Price": [101.5, 20.25],
        "MarketCap": [2.5e12, 3.0e9], "Value": [1.2, -0.8], "Composite": [0.9, -0.4],
        "Quintile": [1, 5], "Ret1M": [0.031, -0.052],
    })
    summary = pd.DataFrame({"Portfolio": ["Q1_net", "SPY"], "CAGR": [0.205, 0.135],
                            "Sharpe": [1.08, 0.79]})
    monthly = pd.DataFrame({"month": ["2026-09-30", "2026-10-31"], "Q1_net": [0.012, -0.004],
                            "IC": [0.05, -0.02]})
    return {"Rankings": rankings, "Backtest Summary": summary, "Monthly Returns": monthly}


def test_workbook_has_a_sheet_per_table_plus_notes(tmp_path, tables) -> None:
    path = write_workbook(tmp_path / "out.xlsx", tables, INFO)
    wb = load_workbook(path)
    assert wb.sheetnames == ["Rankings", "Backtest Summary", "Monthly Returns", "Notes"]
    notes = [row[0].value for row in wb["Notes"].iter_rows() if row[0].value]
    assert "Data as of" in notes
    assert wb["Notes"]["B4"].value == "2026-11-16"


def test_rankings_sheet_is_frozen_formatted_and_colored(tmp_path, tables) -> None:
    ws = load_workbook(write_workbook(tmp_path / "out.xlsx", tables, INFO))["Rankings"]
    assert ws.freeze_panes == "B2"
    assert ws["A1"].font.bold
    headers = [c.value for c in ws[1]]
    by_name = {name: ws.cell(row=2, column=i + 1) for i, name in enumerate(headers)}
    assert by_name["MarketCap"].number_format == "#,##0"
    assert by_name["Ret1M"].number_format == "0.0%"
    assert by_name["Value"].number_format == "0.00"
    assert by_name["Value"].value == pytest.approx(1.2)
    colored = {str(rng.sqref) for rng in ws.conditional_formatting}
    assert colored == {"E2:E3", "F2:F3"}  # Value and Composite, the two score columns here


def test_monthly_returns_are_percentages(tmp_path, tables) -> None:
    ws = load_workbook(write_workbook(tmp_path / "out.xlsx", tables, INFO))["Monthly Returns"]
    assert ws["B2"].number_format == "0.00%"
    assert ws["B2"].value == pytest.approx(0.012)
    assert ws["A2"].is_date and ws["A2"].number_format == "mmm yyyy"


def test_load_tables_skips_missing_files(tmp_path) -> None:
    (tmp_path / "rankings").mkdir()
    pd.DataFrame({"Ticker": ["AAA"]}).to_csv(tmp_path / SHEETS["Rankings"], index=False)
    assert list(load_tables(tmp_path)) == ["Rankings"]
