"""Build the Equity Factor Lab dashboard: one self-contained docs/index.html.

Reads existing CSVs in outputs/sp500, outputs/test50 and (optionally) outputs/watchlist;
never re-runs the pipeline. All data is embedded as JSON (NaN -> null).

Run: python -m src.dashboard
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
TEMPLATE = Path(__file__).with_name("dashboard_template.html")
TARGET = ROOT / "docs" / "index.html"
UNIVERSES = ("sp500", "test50")
CATEGORIES = ["Value", "Quality", "Momentum", "Growth", "LowVol"]
METRICS = ["Price", "MarketCap", "Ret1M", "Ret6M", "Ret12M", "FCFYield", "EV_EBITDA", "Volatility", "Beta"]

log = logging.getLogger("dashboard")


def _read(path: Path) -> pd.DataFrame | None:
    """Read a CSV, returning None (and logging) if missing or unreadable."""
    try:
        return pd.read_csv(path)
    except FileNotFoundError:
        log.warning("missing %s", path.relative_to(ROOT))
    except Exception as exc:  # bad file must not crash the build
        log.warning("skip %s: %s", path.relative_to(ROOT), exc)
    return None


def _records(df: pd.DataFrame, digits: int = 6) -> dict:
    """Column-oriented JSON payload: {"cols": [...], "rows": [[...]]}, NaN -> None."""
    num = df.select_dtypes("number").columns
    df = df.replace([np.inf, -np.inf], np.nan)
    df[num] = df[num].round(digits)
    obj = df.astype(object).where(df.notna(), None)
    return {"cols": list(df.columns), "rows": obj.values.tolist()}


def _flags(df: pd.DataFrame) -> pd.Series:
    """Plain-English data-quality warnings per row ('' if clean)."""
    msgs = pd.DataFrame(index=df.index)
    msgs["r"] = np.where(df["Ret1M"].abs() > 0.60, "1-month return of " + (df["Ret1M"] * 100).round(0).astype(str) + "%", "")
    msgs["v"] = np.where(df["Volatility"] > 1.50, "volatility of " + (df["Volatility"] * 100).round(0).astype(str) + "%", "")
    msgs["e"] = np.where(df["EV_EBITDA"] > 500, "EV/EBITDA of " + df["EV_EBITDA"].round(0).astype(str), "")
    return msgs.apply(lambda r: "; ".join(m.replace(".0", "") for m in r if m), axis=1)


def load_rankings(uni: str, watch: set[str], watch_df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Rankings + derived fields: sector fill, category percentiles, sector rank, flags."""
    df = _read(OUT / uni / "rankings" / "rankings.csv")
    if df is None:
        return None
    df["Watch"] = df["Ticker"].isin(watch).astype(int)
    df["InUni"] = 1
    if watch_df is not None:  # watchlist names outside the universe keep their own scores
        extra = watch_df[~watch_df["Ticker"].isin(df["Ticker"])].assign(Watch=1, InUni=0)
        df = pd.concat([df, extra[[c for c in df.columns if c in extra.columns]]], ignore_index=True)
    df["Sector"] = df["Sector"].fillna("Unknown").replace("", "Unknown")
    for c in CATEGORIES:
        df[f"P_{c}"] = df[c].rank(pct=True).mul(100).round(1)
    df = df.sort_values("Composite", ascending=False, na_position="last").reset_index(drop=True)
    df["Rank"] = np.arange(1, len(df) + 1)
    df["SectorRank"] = df.groupby("Sector")["Composite"].rank(ascending=False, method="min")
    df["SectorN"] = df.groupby("Sector")["Ticker"].transform("size")
    df["Flag"] = _flags(df)
    return df


def load_universe(uni: str, watch: set[str], watch_df: pd.DataFrame | None) -> dict | None:
    """Everything the page needs for one universe."""
    rk = load_rankings(uni, watch, watch_df)
    if rk is None:
        return None
    summary = _read(OUT / uni / "backtest_summary.csv")
    tests = _read(OUT / uni / "factor_tests.csv")
    monthly = _read(OUT / uni / "backtest_monthly_returns.csv")
    med = rk.groupby("Sector")[METRICS].median().round(6)
    med.loc["All"] = rk[METRICS].median().round(6)
    return {
        "rankings": _records(rk),
        "summary": _records(summary) if summary is not None else None,
        "tests": _records(tests) if tests is not None else None,
        "monthly": _records(monthly) if monthly is not None else None,
        "sectorMedian": _records(med.reset_index().rename(columns={"index": "Sector"})),
        "asof": _asof(uni, monthly),
    }


def _asof(uni: str, monthly: pd.DataFrame | None) -> str:
    """Date of the last commit touching the outputs; fall back to last rebalance month."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", f"outputs/{uni}"],
                             cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        if out:
            return out
    except Exception:
        pass
    return str(monthly["rebalance_month"].iloc[-1]) if monthly is not None else ""


def load_watchlist() -> tuple[set[str], pd.DataFrame | None]:
    """Tickers (and any scored rows) from outputs/watchlist/*.csv, if present."""
    wdir = OUT / "watchlist"
    files = sorted(wdir.rglob("*.csv")) if wdir.exists() else []
    frames = [f for f in (_read(p) for p in files) if f is not None and "Ticker" in f.columns]
    if not frames:
        return set(), None
    wl = pd.concat(frames, ignore_index=True).drop_duplicates("Ticker")
    scored = wl if {"Composite", "Percentile", "Quintile"} <= set(wl.columns) else None
    return set(wl["Ticker"].astype(str)), scored


def build() -> Path:
    """Write docs/index.html and return its path."""
    watch, watch_df = load_watchlist()
    data = {u: d for u in UNIVERSES if (d := load_universe(u, watch, watch_df)) is not None}
    if not data:
        raise SystemExit("No outputs found; run the pipeline first.")
    payload = json.dumps({"universes": data, "watchlist": sorted(watch)}, separators=(",", ":"), allow_nan=False)
    payload = payload.replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(html, encoding="utf-8")
    log.info("wrote %s (%.0f KB; %s)", TARGET.relative_to(ROOT), TARGET.stat().st_size / 1024, ", ".join(data))
    return TARGET


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build()
