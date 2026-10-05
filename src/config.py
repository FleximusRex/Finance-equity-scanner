"""Project-wide configuration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"
CHARTS_DIR = ROOT / "outputs" / "charts"
RANKINGS_DIR = ROOT / "outputs" / "rankings"
OUTPUTS_DIR = ROOT / "outputs"

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
