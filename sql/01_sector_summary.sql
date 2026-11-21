-- Stocks per sector, the sector's average composite score, and how many of its stocks
-- make the top quintile (Q1) of today's ranking.
SELECT
    COALESCE(Sector, 'Unknown') AS sector,
    COUNT(*) AS stocks,
    ROUND(AVG(Composite), 2) AS avg_composite,
    SUM(CASE WHEN Quintile = 1 THEN 1 ELSE 0 END) AS stocks_in_q1,
    ROUND(100.0 * SUM(CASE WHEN Quintile = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_in_q1
FROM rankings
GROUP BY COALESCE(Sector, 'Unknown')
ORDER BY avg_composite DESC;
