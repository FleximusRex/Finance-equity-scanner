"""Universe parsing with the Wikipedia response mocked; no network access."""
import pandas as pd
import pytest

from src import config, universe

HTML = b"""
<html><body>
<table id="constituents"><thead>
<tr><th>Symbol</th><th>Security</th><th>GICS Sector</th></tr></thead>
<tbody>
<tr><td>AAPL</td><td>Apple</td><td>Information Technology</td></tr>
<tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td></tr>
<tr><td>BF.B</td><td>Brown-Forman</td><td>Consumer Staples</td></tr>
<tr><td>AAPL</td><td>Apple (duplicate row)</td><td>Information Technology</td></tr>
</tbody></table>
</body></html>
"""


class FakeResponse:
    def read(self) -> bytes:
        return HTML


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    return tmp_path


def test_sp500_tickers_parses_and_converts_class_shares(cache_dir, monkeypatch) -> None:
    monkeypatch.setattr(universe.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    assert universe.sp500_tickers() == ["AAPL", "BRK-B", "BF-B"]
    cached = pd.read_parquet(cache_dir / "sp500_constituents.parquet")
    assert cached["sector"].tolist() == ["Information Technology", "Financials", "Consumer Staples"]


def test_sp500_tickers_uses_cache_on_second_call(cache_dir, monkeypatch) -> None:
    monkeypatch.setattr(universe.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    universe.sp500_tickers()

    def fail(*args, **kwargs):
        raise AssertionError("network was used despite a cache")

    monkeypatch.setattr(universe.urllib.request, "urlopen", fail)
    assert universe.sp500_tickers() == ["AAPL", "BRK-B", "BF-B"]


def test_get_universe_modes() -> None:
    assert universe.get_universe("test50") == config.UNIVERSE
    assert len(config.UNIVERSE) == 50 and len(set(config.UNIVERSE)) == 50
    with pytest.raises(ValueError):
        universe.get_universe("nasdaq")
