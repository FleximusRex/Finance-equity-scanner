-- How often each quintile portfolio beat SPY and the equal-weight basket (EW) in a month.
-- The monthly table has one column per quintile, so UNION ALL first stacks them into rows.
WITH quintile_months AS (
    SELECT month, 'Q1' AS portfolio, Q1_net AS ret, EW_net AS ew, SPY AS spy FROM monthly_returns
    UNION ALL
    SELECT month, 'Q2', Q2_net, EW_net, SPY FROM monthly_returns
    UNION ALL
    SELECT month, 'Q3', Q3_net, EW_net, SPY FROM monthly_returns
    UNION ALL
    SELECT month, 'Q4', Q4_net, EW_net, SPY FROM monthly_returns
    UNION ALL
    SELECT month, 'Q5', Q5_net, EW_net, SPY FROM monthly_returns
)
SELECT
    portfolio,
    COUNT(*) AS months,
    ROUND(100.0 * AVG(CASE WHEN ret > spy THEN 1.0 ELSE 0.0 END), 1) AS pct_months_beat_spy,
    ROUND(100.0 * AVG(CASE WHEN ret > ew THEN 1.0 ELSE 0.0 END), 1) AS pct_months_beat_ew,
    ROUND(100 * AVG(ret - ew), 2) AS avg_monthly_gap_vs_ew_pct
FROM quintile_months
GROUP BY portfolio
ORDER BY portfolio;
