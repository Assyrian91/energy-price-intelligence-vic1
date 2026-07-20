-- Analysis queries used to validate features before modeling

-- Average price by hour of day (the "duck curve")
SELECT EXTRACT(HOUR FROM settlement_date) AS hour_of_day,
       ROUND(AVG(rrp)::numeric, 2) AS avg_price,
       COUNT(*) FILTER (WHERE rrp > 300) AS spike_count
FROM energy_price_demand
GROUP BY hour_of_day
ORDER BY avg_price DESC;

-- Monthly seasonal pattern
SELECT TO_CHAR(settlement_date, 'YYYY-MM') AS month,
       ROUND(AVG(rrp)::numeric, 2) AS avg_price,
       ROUND(AVG(total_demand)::numeric, 0) AS avg_demand,
       COUNT(*) FILTER (WHERE rrp > 300) AS spike_count,
       COUNT(*) FILTER (WHERE rrp < 0) AS negative_count
FROM energy_price_demand
GROUP BY month
ORDER BY month;

-- Demand bucket vs price (proves the demand->price relationship)
SELECT
    CASE WHEN total_demand < 4500 THEN 'Low demand'
         WHEN total_demand < 6000 THEN 'Medium demand'
         ELSE 'High demand' END AS demand_bucket,
    ROUND(AVG(rrp)::numeric, 2) AS avg_price,
    COUNT(*) AS interval_count
FROM energy_price_demand
GROUP BY demand_bucket
ORDER BY avg_price DESC;

-- Day-of-week check that exposed the June 12/26 outlier contamination
SELECT DATE(settlement_date) AS day,
       ROUND(AVG(rrp)::numeric,2) AS avg_price,
       COUNT(*) FILTER (WHERE rrp>1000) AS extreme_spikes
FROM energy_price_demand
WHERE TO_CHAR(settlement_date,'Day') LIKE 'Thursday%'
GROUP BY day
ORDER BY avg_price DESC
LIMIT 10;
