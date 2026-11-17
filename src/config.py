"""Project-wide configuration."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"

# test50 = UNIVERSE below; sp100 and sp500 = Wikipedia lists (cached)
UNIVERSE_MODES = ("test50", "sp100", "sp500")
UNIVERSE_MODE = os.getenv("UNIVERSE_MODE", "sp500")  # fallback when --universe is not given
SECTOR_NEUTRAL = False  # set by --sector-neutral: z-score within GICS sector
OUTPUTS_DIR = CHARTS_DIR = RANKINGS_DIR = ROOT


def set_universe(mode: str, sector_neutral: bool = False) -> None:
    """Select the universe and point the output folders at outputs/<mode>/."""
    global UNIVERSE_MODE, SECTOR_NEUTRAL, OUTPUTS_DIR, CHARTS_DIR, RANKINGS_DIR
    if mode not in UNIVERSE_MODES:
        raise ValueError(f"universe must be one of {UNIVERSE_MODES}, got {mode!r}")
    UNIVERSE_MODE = mode
    SECTOR_NEUTRAL = sector_neutral
    OUTPUTS_DIR = ROOT / "outputs" / mode
    if sector_neutral:  # kept apart so the two runs can be compared
        OUTPUTS_DIR = OUTPUTS_DIR / "sector_neutral"
    CHARTS_DIR = OUTPUTS_DIR / "charts"
    RANKINGS_DIR = OUTPUTS_DIR / "rankings"


set_universe(UNIVERSE_MODE)

START_DATE = "2014-01-01"
END_DATE: str | None = "2026-11-17"  # exclusive; pinned so reruns reproduce outputs/. None = latest
BENCHMARK = "SPY"

# 50 large-cap US tickers across sectors (test universe).
UNIVERSE = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "ORCL", "CRM", "ADBE", "CSCO",
    # Health care
    "JNJ", "UNH", "LLY", "PFE", "MRK", "ABBV", "TMO",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "BRK-B",
    # Consumer discretionary
    "AMZN", "TSLA", "HD", "MCD", "NKE",
    # Consumer staples
    "PG", "KO", "PEP", "WMT", "COST",
    # Energy
    "XOM", "CVX", "COP",
    # Industrials
    "CAT", "HON", "UNP", "GE", "LMT",
    # Communication services
    "DIS", "NFLX", "VZ",
    # Utilities
    "NEE", "DUK",
    # Materials
    "LIN",
    # Real estate
    "PLD",
]

REBALANCE = "M"
TRANSACTION_COST_BPS = 10
MIN_PRICE_HISTORY = 252
WINSOR = (0.01, 0.99)
MIN_SECTOR_NAMES = 5  # sectors with fewer scored names use the universe-wide z-score

# Robustness checks (src/robustness.py)
COST_GRID_BPS = (0, 10, 25, 50)
SUBPERIODS = {"2015-2019": ("2015", "2019"), "2020-2022": ("2020", "2022"),
              "2023-latest": ("2023", None)}
NEWEY_WEST_LAGS = 6  # months of autocorrelation allowed for in the regression standard errors
FACTOR_WEIGHTS = {
    "value": 0.25,
    "quality": 0.25,
    "momentum": 0.25,
    "growth": 0.15,
    "low_vol": 0.10,
}
