"""Load the saved results into a SQLite database and run the analysis queries in sql/.

Run: python -m src.database [--universe {test50,sp100,sp500}]
Writes outputs/<universe>/equity_screener.db (not committed) and one CSV per query in
outputs/<universe>/sql_results/.
"""
from __future__ import annotations

import logging
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from src import cli, config

log = logging.getLogger("database")
SQL_DIR = config.ROOT / "sql"
# table name -> CSV file, relative to outputs/<universe>/
TABLES = {
    "rankings": "rankings/rankings.csv",
    "monthly_returns": "backtest_monthly_returns.csv",
    "backtest_summary": "backtest_summary.csv",
    "factor_tests": "factor_tests.csv",
}


def build_database(folder: Path, db_path: Path) -> list[str]:
    """Copy each results CSV in `folder` into a table of a new SQLite file; return the tables."""
    db_path.unlink(missing_ok=True)  # start fresh so rows from an older run never linger
    loaded = []
    conn = sqlite3.connect(db_path)
    try:
        for table, filename in TABLES.items():
            path = folder / filename
            if not path.exists():
                log.warning("no %s; the %s table is left out", filename, table)
                continue
            pd.read_csv(path).to_sql(table, conn, index=False)
            loaded.append(table)
    finally:
        conn.close()
    return loaded


def run_queries(db_path: Path, sql_dir: Path = SQL_DIR) -> dict[str, pd.DataFrame]:
    """Run every .sql file in `sql_dir`, in file-name order, and return the results by name."""
    results = {}
    conn = sqlite3.connect(db_path)
    try:
        for path in sorted(sql_dir.glob("*.sql")):
            results[path.stem] = pd.read_sql_query(path.read_text(encoding="utf-8"), conn)
    finally:
        conn.close()
    return results


def main(argv: Sequence[str] | None = None) -> int:
    cli.parse_args("Load the results into SQLite and run the queries in sql/.", argv)
    cli.setup_logging()
    folder = config.OUTPUTS_DIR
    db_path = folder / "equity_screener.db"
    if not build_database(folder, db_path):
        log.error("no results in %s; run the ranking and the backtest first", folder)
        return 1
    out_dir = folder / "sql_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in run_queries(db_path).items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
        print(f"\n{name}\n{df.to_string(index=False)}")
    log.info("saved query results -> %s", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
