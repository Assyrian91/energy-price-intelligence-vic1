-- Feature engineering view: joins weather, derives time/season/peak features,
-- adds lag/rolling price features, flags the known June 2025 outage period.
CREATE OR REPLACE VIEW energy_features AS
SELECT
    e.settlement_date,
    e.region,
    e.total_demand,
    e.rrp,
    EXTRACT(HOUR FROM e.settlement_date) AS hour_of_day,
    EXTRACT(MONTH FROM e.settlement_date) AS month_num,
    CASE WHEN EXTRACT(DOW FROM e.settlement_date) IN (0,6) THEN 'weekend' ELSE 'weekday' END AS day_type,
    CASE
        WHEN EXTRACT(MONTH FROM e.settlement_date) IN (12,1,2) THEN 'summer'
        WHEN EXTRACT(MONTH FROM e.settlement_date) IN (3,4,5) THEN 'autumn'
        WHEN EXTRACT(MONTH FROM e.settlement_date) IN (6,7,8) THEN 'winter'
        ELSE 'spring'
    END AS season,
    CASE WHEN EXTRACT(HOUR FROM e.settlement_date) BETWEEN 17 AND 20 THEN 1 ELSE 0 END AS is_peak_hour,
    LAG(e.rrp, 1) OVER (ORDER BY e.settlement_date) AS rrp_prev_interval,
    AVG(e.rrp) OVER (ORDER BY e.settlement_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS rrp_rolling_1hr,
    CASE WHEN e.settlement_date >= '2025-06-01' AND e.settlement_date < '2025-07-01' THEN 1 ELSE 0 END AS is_known_outage_period,
    CASE WHEN e.rrp > 300 THEN 1 ELSE 0 END AS is_spike,
    w.temperature_2m,
    CASE WHEN w.temperature_2m >= 30 OR w.temperature_2m <= 5 THEN 1 ELSE 0 END AS is_temp_extreme
FROM energy_price_demand e
LEFT JOIN melbourne_weather w ON date_trunc('hour', e.settlement_date) = w.nem_hour
ORDER BY e.settlement_date;
