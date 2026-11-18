"""Export the saved results to one Excel workbook.

Run: python -m src.excel_export [--universe {test50,sp100,sp500}]
Writes outputs/<universe>/equity_screener_<as-of date>.xlsx from the CSVs in that folder.
"""
from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from src import cli, config
from src.run_info import load_run_info

log = logging.getLogger("excel")

# sheet name -> CSV file, relative to outputs/<universe>/
SHEETS = {
    "Rankings": "rankings/rankings.csv",
    "Backtest Summary": "backtest_summary.csv",
    "Factor Tests": "factor_tests.csv",
    "FF Regression": "ff_regression.csv",
    "Robustness": "robustness.csv",
    "Sector Neutral": "sector_neutral/backtest_summary.csv",
    "Monthly Returns": "backtest_monthly_returns.csv",
}
SCORE_COLUMNS = ["Value", "Quality", "Momentum", "Growth", "LowVol", "Composite"]
PERCENT = "0.0%"
FORMATS = {
    "Price": "#,##0.00", "MarketCap": "#,##0", "Percentile": "0", "Quintile": "0", "Months": "0",
    "Ret1M": PERCENT, "Ret6M": PERCENT, "Ret12M": PERCENT, "FCFYield": PERCENT,
    "Volatility": PERCENT, "CAGR": PERCENT, "AnnVol": PERCENT, "MaxDD": PERCENT,
    "WinRate": PERCENT, "BestMonth": PERCENT, "WorstMonth": PERCENT, "Alpha": PERCENT,
    "TrackingError": PERCENT, "AvgTurnover": PERCENT, "Alpha_ann": PERCENT,
    "Q1_CAGR": PERCENT, "Q5_CAGR": PERCENT, "LS_CAGR": PERCENT, "EW_CAGR": PERCENT,
    "IC_mean": "0.000", "IC_p": "0.000", "IC_p_holm": "0.000", "Alpha_p": "0.000",
}
HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")

NOTES = [
    "What this is",
    "A multi-factor equity screener and backtest built in Python. The Rankings sheet scores each "
    "stock on value, quality, momentum, growth and low volatility. The other sheets test whether "
    "the price factors (momentum and low volatility) predicted next-month returns.",
    "",
    "How to read the sheets",
    "Rankings: cross-sectional z-scores by category. Composite is the weighted score. "
    "Quintile 1 is the best 20% of stocks.",
    "Backtest Summary: monthly rebalanced quintile portfolios, equal weight. Net rows are after "
    "10 bps per side. Sharpe, Sortino, beta and alpha use returns above the 1-month T-bill rate.",
    "Factor Tests: mean rank IC of each signal with a t-test, and a Holm-adjusted p-value that "
    "allows for testing five signals.",
    "FF Regression: monthly excess returns regressed on the Fama-French five factors plus "
    "momentum, with Newey-West t-stats. Alpha_ann is the annualized alpha.",
    "Robustness: the same backtest at four cost levels, in three sub-periods and with trades "
    "delayed by one day.",
    "Sector Neutral: the backtest with z-scores computed within GICS sector.",
    "Monthly Returns: one row per holding month. LS is Q1 minus Q5. RF is the T-bill rate.",
    "",
    "Limitations",
    "The universe is today's index members, so the backtest has survivorship bias. Compare Q1 "
    "with the equal-weight universe (EW), not with SPY.",
    "Fundamentals are current values, not point-in-time, so value, quality and growth are in the "
    "ranking but not in the backtest.",
    "Sector labels are today's, not historical.",
    "This is a research project and not investment advice.",
    "",
    "Sources",
    "Prices and fundamentals: Yahoo Finance via yfinance. Constituents and sectors: Wikipedia. "
    "Factors and T-bill rate: Kenneth French's data library.",
]


def load_tables(folder: Path | None = None) -> dict[str, pd.DataFrame]:
    """Read every results CSV that exists in the outputs folder, keyed by sheet name."""
    folder = folder or config.OUTPUTS_DIR
    tables = {}
    for sheet, filename in SHEETS.items():
        path = folder / filename
        if path.exists():
            tables[sheet] = pd.read_csv(path)
        else:
            log.warning("no %s; the %s sheet is left out", filename, sheet)
    return tables


def _format_sheet(ws: Worksheet, default_format: str = "0.00") -> None:
    """Freeze and style the header row, set number formats by column name and widen columns."""
    ws.freeze_panes = "B2"
    for col_idx, cell in enumerate(ws[1], start=1):
        cell.font, cell.fill = HEADER_FONT, HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        number_format = FORMATS.get(cell.value, default_format)
        widest = len(str(cell.value))
        for (value_cell,) in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
            if isinstance(value_cell.value, datetime):
                value_cell.number_format = "mmm yyyy"
            elif isinstance(value_cell.value, (int, float)):
                value_cell.number_format = number_format
            else:
                widest = max(widest, len(str(value_cell.value or "")))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(widest + 2, 10), 40)


def _add_color_scale(ws: Worksheet, columns: list[str]) -> None:
    """Red-white-blue color scale (blue = high) on the named columns."""
    headers = [c.value for c in ws[1]]
    rule = ColorScaleRule(start_type="num", start_value=-2, start_color="E34948",
                          mid_type="num", mid_value=0, mid_color="FFFFFF",
                          end_type="num", end_value=2, end_color="2A78D6")
    for name in columns:
        if name in headers:
            letter = get_column_letter(headers.index(name) + 1)
            ws.conditional_formatting.add(f"{letter}2:{letter}{ws.max_row}", rule)


def _write_notes(ws: Worksheet, info: dict) -> None:
    """Run details and a short methodology, one line per row."""
    facts = [
        ("Universe", info.get("universe", "n/a")),
        ("Data as of", info.get("as_of", "n/a")),
        ("Stocks with prices", info.get("tickers", "n/a")),
        ("Holding months", f"{info.get('months', 'n/a')} "
                           f"({info.get('first_month', '?')} to {info.get('last_month', '?')})"),
        ("Code version (git commit)", info.get("git_commit", "n/a")),
    ]
    ws.append(["Multi-Factor Equity Screener"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    for label, value in facts:
        ws.append([label, value])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([])
    for line in NOTES:
        ws.append([line])
        cell = ws.cell(row=ws.max_row, column=1)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if line and len(line) < 30:  # short lines are the section headings
            cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 100
    ws.column_dimensions["B"].width = 24


def write_workbook(path: Path, tables: dict[str, pd.DataFrame], info: dict) -> Path:
    """Write one sheet per table plus a Notes sheet, and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet, df in tables.items():
            if "month" in df.columns:  # real dates, so Excel can sort and chart them
                df = df.assign(month=pd.to_datetime(df["month"]))
            df.to_excel(writer, sheet_name=sheet, index=False)
            ws = writer.sheets[sheet]
            # Monthly returns are small decimals, so they read best as percentages.
            _format_sheet(ws, "0.00%" if sheet == "Monthly Returns" else "0.00")
        if "Rankings" in tables:
            _add_color_scale(writer.sheets["Rankings"], SCORE_COLUMNS)
        _write_notes(writer.book.create_sheet("Notes"), info)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    cli.parse_args("Export the saved results to an Excel workbook.", argv)
    cli.setup_logging()
    info = load_run_info()
    tables = load_tables()
    if not tables or "as_of" not in info:
        log.error("no results in %s; run the ranking and the backtest first", config.OUTPUTS_DIR)
        return 1
    path = config.OUTPUTS_DIR / f"equity_screener_{info['as_of']}.xlsx"
    write_workbook(path, tables, info)
    log.info("saved %d sheets -> %s", len(tables) + 1, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
