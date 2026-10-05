"""Project-wide configuration."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"

# "test50" = UNIVERSE below; "sp500" = current S&P 500 list from Wikipedia (cached).
# Override per run with env var, e.g. UNIVERSE_MODE=test50 python -m src.backtest
UNIVERSE_MODE = os.getenv("UNIVERSE_MODE", "sp500")
if UNIVERSE_MODE not in ("test50", "sp500"):
    raise ValueError(f"UNIVERSE_MODE must be 'test50' or 'sp500', got {UNIVERSE_MODE!r}")

OUTPUTS_DIR = ROOT / "outputs" / UNIVERSE_MODE
CHARTS_DIR = OUTPUTS_DIR / "charts"
RANKINGS_DIR = OUTPUTS_DIR / "rankings"

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
