-- The highest-ranked stock in each sector, with its category scores.
-- ROW_NUMBER restarts at 1 for every sector, so rank_in_sector = 1 is the sector leader.
WITH ranked AS (
    SELECT
        COALESCE(Sector, 'Unknown') AS sector,
        Ticker AS ticker,
        Company AS company,
        ROUND(Composite, 2) AS composite,
        ROUND(Momentum, 2) AS momentum,
        ROUND(LowVol, 2) AS low_vol,
        ROUND(Value, 2) AS value,
        ROUND(Quality, 2) AS quality,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(Sector, 'Unknown')
            ORDER BY Composite DESC
        ) AS rank_in_sector
    FROM rankings
    WHERE Composite IS NOT NULL
)
SELECT sector, ticker, company, composite, momentum, low_vol, value, quality
FROM ranked
WHERE rank_in_sector = 1
ORDER BY composite DESC;
