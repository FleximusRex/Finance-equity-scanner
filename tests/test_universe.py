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


# The S&P 100 article uses the same table id but calls the sector column "Sector".
SP100_HTML = b"""
<html><body>
<table class="wikitable"><tr><th>Category</th><th>Value</th></tr></table>
<table class="wikitable sortable" id="constituents"><thead>
<tr><th>Symbol</th><th>Name</th><th>Sector</th></tr></thead>
<tbody>
<tr><td>AAPL</td><td>Apple Inc.</td><td>Information Technology</td></tr>
<tr><td>BRK.B</td><td>Berkshire Hathaway (Class B)</td><td>Financials</td></tr>
<tr><td>XOM</td><td>ExxonMobil</td><td>Energy</td></tr>
</tbody></table>
</body></html>
"""


class FakeResponse:
    def __init__(self, body: bytes = HTML) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body


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


def test_sp100_tickers_parses_and_converts_class_shares(cache_dir, monkeypatch) -> None:
    monkeypatch.setattr(universe.urllib.request, "urlopen",
                        lambda *a, **k: FakeResponse(SP100_HTML))
    assert universe.sp100_tickers() == ["AAPL", "BRK-B", "XOM"]
    assert universe.get_universe("sp100") == ["AAPL", "BRK-B", "XOM"]
    assert (cache_dir / "sp100_constituents.parquet").exists()


def test_sectors_are_indexed_by_ticker(cache_dir, monkeypatch) -> None:
    monkeypatch.setattr(universe.urllib.request, "urlopen",
                        lambda *a, **k: FakeResponse(SP100_HTML))
    sec = universe.sectors("sp100")
    assert sec["BRK-B"] == "Financials" and sec["XOM"] == "Energy"


def test_test50_sectors_come_from_the_sp500_table(cache_dir, monkeypatch) -> None:
    monkeypatch.setattr(universe.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    sec = universe.sectors("test50")
    assert list(sec.index) == config.UNIVERSE
    assert sec["AAPL"] == "Information Technology" and sec["BRK-B"] == "Financials"
    assert pd.isna(sec["MSFT"])  # not in the small fixture


def test_get_universe_modes() -> None:
    assert universe.get_universe("test50") == config.UNIVERSE
    assert len(config.UNIVERSE) == 50 and len(set(config.UNIVERSE)) == 50
    assert config.UNIVERSE_MODES == ("test50", "sp100", "sp500")
    with pytest.raises(ValueError):
        universe.get_universe("nasdaq")
