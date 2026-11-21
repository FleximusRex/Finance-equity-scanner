-- For each calendar year of the backtest: the average monthly return of the top quintile (Q1),
-- the equal-weight basket of all stocks (EW) and SPY, and in how many months Q1 beat the basket.
-- Returns are net of trading costs and shown in percent.
SELECT
    SUBSTR(month, 1, 4) AS year,
    COUNT(*) AS months,
    ROUND(100 * AVG(Q1_net), 2) AS q1_avg_monthly_pct,
    ROUND(100 * AVG(EW_net), 2) AS ew_avg_monthly_pct,
    ROUND(100 * AVG(SPY), 2) AS spy_avg_monthly_pct,
    SUM(CASE WHEN Q1_net > EW_net THEN 1 ELSE 0 END) AS months_q1_beat_ew
FROM monthly_returns
GROUP BY SUBSTR(month, 1, 4)
ORDER BY year;
