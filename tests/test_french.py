"""French data library parsing and the risk-free rate, with downloads mocked; no network access."""
import pandas as pd
import pytest

from src import config, french

# Same layout as the real files: description, header row, monthly block, blank line, annual block.
FF5_CSV = """This file was created using the 202609 CRSP database.
The 1-month TBill rate data until 202405 are from Ibbotson Associates.

,Mkt-RF,SMB,HML,RMW,CMA,RF
202607,   -0.61,   -0.09,    2.11,   11.07,    2.27,    0.33
202608,    2.56,   -0.52,   -3.54,   -4.09,   -2.01,    0.29
202609,   -1.07,   -4.60,   -1.55,   -3.22,    1.08,    0.31

 Annual Factors: January-December
,Mkt-RF,SMB,HML,RMW,CMA,RF
  2024,   19.78,  -13.44,   -8.43,    5.11,  -10.04,    5.26
  2025,   13.30,   -9.31,    8.71,  -10.85,   -5.33,    4.25

Copyright 2026 Eugene F. Fama and Kenneth R. French
"""

MOM_CSV = """This file was created using the 202609 CRSP database.  It
contains a momentum factor, constructed from six value-weight portfolios formed
using independent sorts on size and prior return of NYSE, AMEX, and NASDAQ stocks.

,Mom
202606,   -99.99
202607, -12.21
202608,  -5.60
202609,   6.70

Annual Factors:
January-December
,Mom
  2024,  19.72
  2025,  -2.27
"""


@pytest.fixture
def french_cache(tmp_path, monkeypatch):
    """Empty cache folder and a fake download that returns the fixtures above."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    files = {french.FF5_FILE: FF5_CSV, french.MOM_FILE: MOM_CSV}
    monkeypatch.setattr(french, "_download_csv", lambda name: files[name])
    return tmp_path


def test_parse_keeps_only_the_monthly_block_as_decimals() -> None:
    df = french.parse_french_csv(FF5_CSV)
    assert list(df.index) == list(pd.to_datetime(["2026-07-31", "2026-08-31", "2026-09-30"]))
    assert list(df.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    assert df.loc["2026-08-31", "Mkt-RF"] == pytest.approx(0.0256)
    assert df.loc["2026-09-30", "RF"] == pytest.approx(0.0031)


def test_parse_treats_missing_codes_as_nan() -> None:
    df = french.parse_french_csv(MOM_CSV)
    assert pd.isna(df.loc["2026-06-30", "Mom"])
    assert df.loc["2026-07-31", "Mom"] == pytest.approx(-0.1221)


def test_parse_rejects_text_without_a_monthly_block() -> None:
    with pytest.raises(ValueError):
        french.parse_french_csv("not a French file")


def test_load_factors_joins_momentum_and_caches(french_cache, monkeypatch) -> None:
    df = french.load_factors()
    assert list(df.columns) == [*french.FACTOR_COLS, "RF"]
    assert len(df) == 3  # June has no five-factor row, so the inner join drops it
    assert df.loc["2026-09-30", "UMD"] == pytest.approx(0.067)

    def fail(name):
        raise AssertionError("network was used despite a cache")

    monkeypatch.setattr(french, "_download_csv", fail)
    pd.testing.assert_frame_equal(french.load_factors(), df)


def test_risk_free_falls_back_to_irx_after_the_french_file_ends(french_cache, monkeypatch) -> None:
    days = pd.to_datetime(["2026-09-29", "2026-09-30", "2026-10-29", "2026-10-30", "2026-11-13"])
    irx = pd.DataFrame({french.IRX: [3.50, 3.60, 3.70, 3.72, 3.80]}, index=days)
    monkeypatch.setattr(french, "load_prices", lambda tickers: irx)
    months = pd.to_datetime(["2026-08-31", "2026-09-30", "2026-10-31"])
    rf = french.risk_free(months)
    assert rf["2026-08-31"] == pytest.approx(0.0029)  # French RF
    assert rf["2026-09-30"] == pytest.approx(0.0031)
    # October is not in the French file: the 3.60% yield at the end of September, over 12 months.
    assert rf["2026-10-31"] == pytest.approx(3.60 / 100 / 12)
