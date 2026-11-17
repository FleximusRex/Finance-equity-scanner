"""Fama-French factors and the risk-free rate from Kenneth French's data library."""
from __future__ import annotations

import io
import logging
import urllib.request
import zipfile

import pandas as pd

from src import config
from src.data_loader import load_prices

log = logging.getLogger(__name__)
FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FF5_FILE = "F-F_Research_Data_5_Factors_2x3_CSV.zip"
MOM_FILE = "F-F_Momentum_Factor_CSV.zip"
FACTOR_COLS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]
IRX = "^IRX"  # Yahoo's 13-week T-bill yield, in annualized percent


def parse_french_csv(text: str) -> pd.DataFrame:
    """Monthly block of a French CSV, converted from percent to decimals (index = month end)."""
    header: list[str] | None = None
    rows: dict[pd.Timestamp, list[float]] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.split(",")]
        if header is None:
            # The description lines come first; the header row is the one starting with a comma.
            if cells[0] == "" and len(cells) > 1:
                header = cells[1:]
            continue
        if not (len(cells[0]) == 6 and cells[0].isdigit()):
            break  # the monthly block (YYYYMM rows) is over; the annual block follows
        month = pd.Timestamp(year=int(cells[0][:4]), month=int(cells[0][4:]), day=1)
        rows[month + pd.offsets.MonthEnd(0)] = [float(c) for c in cells[1:]]
    if header is None or not rows:
        raise ValueError("no monthly data found in the French CSV")
    df = pd.DataFrame.from_dict(rows, orient="index", columns=header)
    return df.where(df > -99) / 100  # French marks missing values as -99.99 or -999


def _download_csv(filename: str) -> str:
    """Download one zip from the French library and return the CSV inside it as text."""
    req = urllib.request.Request(FRENCH_URL + filename, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        return z.read(z.namelist()[0]).decode("latin-1")


def load_factors() -> pd.DataFrame:
    """Monthly Mkt-RF, SMB, HML, RMW, CMA, UMD and RF as decimals; cached to parquet."""
    path = config.CACHE_DIR / "french_factors.parquet"
    if path.exists():
        return pd.read_parquet(path)
    ff5 = parse_french_csv(_download_csv(FF5_FILE))
    mom = parse_french_csv(_download_csv(MOM_FILE)).rename(columns={"Mom": "UMD"})
    df = ff5.join(mom, how="inner")[[*FACTOR_COLS, "RF"]]
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    log.info("cached French factors through %s -> %s", f"{df.index[-1]:%b %Y}", path.name)
    return df


def irx_monthly_rate() -> pd.Series:
    """Monthly T-bill rate implied by ^IRX: last month's closing yield divided by 12."""
    level = load_prices([IRX])[IRX].dropna()
    month_end = level.groupby(level.index.to_period("M")).last()
    # A bill bought at one month-end earns that yield over the following month.
    rate = month_end.shift(1) / 100 / 12
    rate.index = rate.index.to_timestamp(how="end").normalize()
    return rate


def risk_free(months: pd.DatetimeIndex) -> pd.Series:
    """Monthly risk-free rate: French RF, with ^IRX for months after the French file ends."""
    rf = load_factors()["RF"].reindex(months)
    if rf.isna().any():
        log.info("French RF missing for %d months; using ^IRX for those", rf.isna().sum())
        rf = rf.fillna(irx_monthly_rate().reindex(months))
    return rf.rename("RF")
