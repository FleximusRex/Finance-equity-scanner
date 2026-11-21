# Changelog

## v0.3.0 (Nov 2026)

### Added

- SQL analysis: `make sql` loads the results into a SQLite database and runs four queries in `sql/` (sector summary, top stock per sector, Q1 against the equal-weight basket by year, quintile hit rates). Results are saved in `outputs/<universe>/sql_results/`.
- Author name in the notebook and `pyproject.toml`.

### Changed

- Dashboard redesign: the headline answer sits beside a growth-of-$10,000 chart, a new About section lists the method, tools and author, the footer credits the author, and the README has a preview image.
- GitHub's language statistics count the notebook as documentation, since most of its size is saved chart images.

## v0.2.0 (Nov 2026)

Data as of 16 Nov 2026. The backtest covers 142 holding months, Jan 2015 to Oct 2026.

### Fixed

- The backtest counted a partial final month as a full one. With prices ending on 5 Oct 2026, the last holding period was three trading days, but CAGR, the Sharpe ratio and the t-tests treated it as a month. The backtest now holds only through the last complete month-end.
- Each row of `backtest_monthly_returns.csv` is now labelled with the month the return was earned in (column `month`) instead of the signal month.

### Added

- `sp100` universe, the S&P 100 from Wikipedia. It is the notebook default.
- Excess returns: Sharpe, Sortino, beta and alpha use the 1-month T-bill rate from Kenneth French's data library, with Yahoo's `^IRX` for months after the French file ends.
- Fama-French five-factor plus momentum regression with Newey-West t-stats (`ff_regression.csv`).
- Robustness table (`robustness.csv`): costs of 0, 10, 25 and 50 bps per side, three sub-periods and a one-day execution lag.
- Holm-adjusted p-values in `factor_tests.csv`.
- `--sector-neutral` flag and `make sector-neutral`, which z-score within GICS sector and write to `outputs/<universe>/sector_neutral/`.
- Excel export (`make excel`) with Rankings, Backtest Summary, Factor Tests, FF Regression, Robustness, Sector Neutral, Monthly Returns and Notes sheets.
- `run_info.json` in each outputs folder with the as-of date, ticker count, holding months and git commit. The charts, dashboard and Excel file read the date from it instead of a hard-coded value.
- `make all UNIVERSE=...` runs the full pipeline for one universe.
- S&P 100 in the dashboard's universe switcher.
- Notebook sections for excess returns, the Fama-French regression, the robustness table and an Excel download.
- Python 3.13 in CI. 67 offline tests, up from 32.

### Changed

- The Colab setup cell installs the yfinance version pinned in `requirements.txt` instead of the latest one.
- New dependencies: statsmodels and openpyxl.
- All outputs regenerated. On the S&P 500 the top quintile returned 17.9% a year with an excess-return Sharpe ratio of 1.03, against 16.2% and 0.90 for the equal-weight universe. The long-short portfolio lost 3.7% a year and its Fama-French alpha is -2.1% (t = -1.10).

## v0.1.0

First version: multi-factor ranking of the S&P 500 and a 50-stock test set, monthly quintile backtest of the price factors, charts, dashboard and Colab notebook.
