"""Command-line handling shared by the entry points."""
from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from src import config


def parse_args(description: str, argv: Sequence[str] | None = None,
               ticker: bool = False) -> argparse.Namespace:
    """Parse --universe (default: UNIVERSE_MODE env var, else sp500) and --sector-neutral."""
    parser = argparse.ArgumentParser(description=description)
    if ticker:
        parser.add_argument("ticker", help="ticker symbol, e.g. AAPL")
    parser.add_argument("--universe", choices=config.UNIVERSE_MODES, default=config.UNIVERSE_MODE,
                        help="stock universe to use (default: %(default)s)")
    parser.add_argument("--sector-neutral", action="store_true",
                        help="z-score within GICS sector (outputs/<universe>/sector_neutral/)")
    args = parser.parse_args(argv)
    config.set_universe(args.universe, args.sector_neutral)
    return args


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
