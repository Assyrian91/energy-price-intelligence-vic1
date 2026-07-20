-- Raw AEMO price/demand table
CREATE TABLE energy_price_demand (
    id BIGSERIAL PRIMARY KEY,
    region TEXT NOT NULL,
    settlement_date TIMESTAMP NOT NULL,
    total_demand NUMERIC(10,2),
    rrp NUMERIC(10,2),
    period_type TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (region, settlement_date)
);

CREATE INDEX idx_energy_settlement_date ON energy_price_demand (settlement_date);
CREATE INDEX idx_energy_rrp ON energy_price_demand (rrp);

-- Melbourne hourly temperature (Open-Meteo), fixed NEM time (UTC+10, no DST)
CREATE TABLE melbourne_weather (
    nem_hour TIMESTAMP PRIMARY KEY,
    temperature_2m NUMERIC(5,2)
);
