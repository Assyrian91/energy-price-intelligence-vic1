"""
Fetch hourly Melbourne temperature from Open-Meteo's free historical archive
(no API key needed) and load it into Supabase.

IMPORTANT: AEMO settlement_date is fixed NEM time (UTC+10, no daylight saving).
Melbourne clock time DOES shift for DST. To avoid misaligning summer rows by an
hour, we fetch in UTC and manually shift +10h — we do NOT use a Melbourne/local
timezone parameter from the weather API.

Setup: python -m pip install requests psycopg2-binary python-dotenv --break-system-packages
"""
import os
import requests
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

LAT, LON = -37.8136, 144.9631  # Melbourne CBD
START_DATE = "2025-05-31"
END_DATE = "2026-06-30"

def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
    )

def fetch_weather():
    print("Fetching hourly temperature from Open-Meteo (UTC, no DST)...")
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": "temperature_2m",
        "timezone": "UTC",  # deliberate: we shift to NEM time ourselves below
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()["hourly"]

    df = pd.DataFrame({
        "time_utc": pd.to_datetime(data["time"]),
        "temperature_2m": data["temperature_2m"],
    })
    # Shift UTC -> fixed NEM time (UTC+10), matching AEMO's settlement_date convention
    df["nem_hour"] = df["time_utc"] + pd.Timedelta(hours=10)
    df = df[["nem_hour", "temperature_2m"]].dropna()
    print(f"Fetched {len(df):,} hourly temperature rows ({df['nem_hour'].min()} to {df['nem_hour'].max()})")
    return df

def load_to_supabase(df):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS melbourne_weather (
            nem_hour TIMESTAMP PRIMARY KEY,
            temperature_2m NUMERIC(5,2)
        );
    """)
    cur.execute("CREATE TEMP TABLE staging_weather (nem_hour TIMESTAMP, temperature_2m NUMERIC(5,2));")

    from io import StringIO
    buf = StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    cur.copy_expert("COPY staging_weather (nem_hour, temperature_2m) FROM STDIN WITH CSV", buf)

    cur.execute("""
        INSERT INTO melbourne_weather (nem_hour, temperature_2m)
        SELECT nem_hour, temperature_2m FROM staging_weather
        ON CONFLICT (nem_hour) DO UPDATE SET temperature_2m = EXCLUDED.temperature_2m;
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM melbourne_weather;")
    total = cur.fetchone()[0]
    print(f"melbourne_weather now has {total:,} rows.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    weather_df = fetch_weather()
    load_to_supabase(weather_df)