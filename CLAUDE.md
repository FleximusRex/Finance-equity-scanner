# Multi-Factor Equity Screener — project rules
Goal: GitHub portfolio project for quant/asset-management recruiting. Python 3.11, pandas, numpy, scipy, yfinance, matplotlib, plotly, pytest.

Working style (important — I am on a tight credit budget):
- Be terse. No long explanations. End each task with a 5-line summary of what was built and how to run it.
- Never print full DataFrames or long logs; use .head() and short logging.
- Cache all downloads to data/cache/ as parquet; never re-download if cache exists.
- Use the 50-ticker test universe until I say otherwise.
- One stock with bad data must never crash the run: log and skip.
- Type hints + short docstrings. Vectorized pandas, no slow loops.

Design:
- src/config.py: UNIVERSE_MODE ("test50" | "sp500", env-overridable; outputs go to outputs/<mode>/), START_DATE, END_DATE, BENCHMARK="SPY", UNIVERSE (50 large-cap US tickers across sectors), REBALANCE="M", TRANSACTION_COST_BPS=10, MIN_PRICE_HISTORY=252, WINSOR=(0.01,0.99), FACTOR_WEIGHTS={value:.25, quality:.25, momentum:.25, growth:.15, low_vol:.10}.
- Factors (higher score = better; flip sign where lower is better):
  Value: earnings yield, FCF yield, EV/EBITDA (inverted)
  Quality: ROE, gross margin, debt/equity (inverted)
  Momentum: 12-1 month return, 6-month return
  Low vol: 60-day volatility (inverted), beta vs SPY (inverted)
  Growth: revenue growth, earnings growth
- Normalization: winsorize, then cross-sectional z-score; category score = mean of available factor z-scores; composite = weighted sum, re-normalizing weights if a category is missing.
- Known limitation (document, don't fix): yfinance fundamentals are not point-in-time, so the HISTORICAL backtest uses only price-based factors (momentum + low vol), computed with data available at each rebalance date. Current ranking uses all five categories. Universe is today's tickers, so survivorship bias exists.
