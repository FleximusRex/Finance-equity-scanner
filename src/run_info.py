"""Save and load run_info.json: the as-of date and size of the run behind each outputs folder."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from src import config

FILENAME = "run_info.json"


def git_commit() -> str:
    """Short hash of the checked-out commit ('unknown' outside a git checkout)."""
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT,
                             capture_output=True, text=True, check=False)
    except OSError:
        return "unknown"
    return res.stdout.strip() or "unknown"


def load_run_info(folder: Path | None = None) -> dict:
    """Contents of run_info.json in `folder` (default: the current outputs folder), or {}."""
    path = (folder or config.OUTPUTS_DIR) / FILENAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_run_info(prices: pd.DataFrame, **fields: object) -> dict:
    """Merge the as-of date (last date in the price data) and `fields` into run_info.json."""
    info = load_run_info()
    info["universe"] = config.UNIVERSE_MODE
    info["sector_neutral"] = config.SECTOR_NEUTRAL
    info["as_of"] = f"{prices.index[-1]:%Y-%m-%d}"
    info["git_commit"] = git_commit()
    info.update(fields)
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.OUTPUTS_DIR / FILENAME
    path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return info
