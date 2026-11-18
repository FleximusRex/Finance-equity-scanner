"""run_info.json records the as-of date from the price data itself."""
import json

import pandas as pd

from src import config
from src.run_info import load_run_info, save_run_info


def test_as_of_is_the_last_date_in_the_prices(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path)
    prices = pd.DataFrame({"A": [1.0, 2.0]}, index=pd.to_datetime(["2026-11-13", "2026-11-16"]))
    save_run_info(prices, tickers=1)
    info = json.loads((tmp_path / "run_info.json").read_text())
    assert info["as_of"] == "2026-11-16"
    assert info["tickers"] == 1 and info["universe"] == config.UNIVERSE_MODE


def test_later_saves_keep_earlier_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path)
    prices = pd.DataFrame({"A": [1.0]}, index=pd.to_datetime(["2026-11-16"]))
    save_run_info(prices, tickers_ranked=50)
    save_run_info(prices, months=142)
    info = load_run_info()
    assert info["tickers_ranked"] == 50 and info["months"] == 142


def test_load_run_info_is_empty_without_a_file(tmp_path) -> None:
    assert load_run_info(tmp_path) == {}
