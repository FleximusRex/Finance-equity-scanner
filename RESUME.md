# Resume material: Multi-Factor Equity Screener

## Resume bullets

- Built a Python multi-factor equity screener (pandas, NumPy, SciPy, yfinance) that scores 503 S&P 500 stocks on 13 value, quality, momentum, growth and low-volatility metrics using winsorized cross-sectional z-scores, with cached data ingestion and fault-tolerant per-ticker error handling.
- Designed a point-in-time monthly quintile backtest (142 rebalances, 2014–2026, 10 bps costs) with rank-IC t-tests for each single factor. Found that no price factor was significant at 5% (composite IC −0.003, p = 0.87) and that the top quintile's 17.8% CAGR vs. SPY's 13.6% was mostly survivorship bias (equal-weight universe: 15.7%).

## Project description

A Python research pipeline that ranks US large-cap stocks on five factor categories and tests the price-based factors with a point-in-time monthly backtest, rank-IC statistics and a factor-by-factor significance test across a 50-stock and a 503-stock universe. It documents its own biases (non-point-in-time fundamentals, survivorship) and reports results in terms of statistical evidence rather than headline returns.

## 30-second interview explanation

"I built a multi-factor stock screener that scores the S&P 500 on value, quality, momentum, growth and low volatility, then backtested the price-based factors monthly from 2014 to 2026 with transaction costs. The top quintile beat SPY, 17.8% vs 13.6% a year, but I didn't trust that number. An equal-weighted basket of today's index members made 15.7%, so most of the edge was survivorship bias. So I tested each factor's rank IC on its own. Nothing was significant at 5%. Momentum's IC was essentially zero, and low volatility actually had the wrong sign, because high-beta stocks won over that period. The main lesson was to judge a factor by IC and t-stats against a fair baseline, not by a cumulative-return chart. The next step would be point-in-time fundamentals and survivorship-free constituents."
