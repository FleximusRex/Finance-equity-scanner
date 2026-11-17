"""Project-wide configuration."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"

UNIVERSE_MODES = ("sp500", "test50")  # test50 = UNIVERSE below; sp500 = Wikipedia list (cached)
UNIVERSE_MODE = os.getenv("UNIVERSE_MODE", "sp500")  # fallback when --universe is not given
OUTPUTS_DIR = CHARTS_DIR = RANKINGS_DIR = ROOT


def set_universe(mode: str) -> None:
    """Select the universe and point the output folders at outputs/<mode>/."""
    global UNIVERSE_MODE, OUTPUTS_DIR, CHARTS_DIR, RANKINGS_DIR
    if mode not in UNIVERSE_MODES:
        raise ValueError(f"universe must be one of {UNIVERSE_MODES}, got {mode!r}")
    UNIVERSE_MODE = mode
    OUTPUTS_DIR = ROOT / "outputs" / mode
    CHARTS_DIR = OUTPUTS_DIR / "charts"
    RANKINGS_DIR = OUTPUTS_DIR / "rankings"


set_universe(UNIVERSE_MODE)

START_DATE = "2014-01-01"
END_DATE: str | None = None  # None = latest available
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
FACTOR_WEIGHTS = {
    "value": 0.25,
    "quality": 0.25,
    "momentum": 0.25,
    "growth": 0.15,
    "low_vol": 0.10,
}
