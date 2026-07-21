"""
Load merged AEMO VIC1 price/demand data into Supabase.
Uses psycopg2 COPY for fast bulk insert (113k+ rows).

Setup:
  python -m pip install psycopg2-binary python-dotenv --break-system-packages

Create a file named .env in the SAME folder as this script (never commit this file):
  DB_HOST=aws-1-ap-southeast-1.pooler.supabase.com
  DB_PORT=6543
  DB_NAME=postgres
  DB_USER=postgres.zkukixbaxoyqpbljqlnp
  DB_PASSWORD=your_actual_password_here

Then add .env to your .gitignore BEFORE your first commit.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

CSV_PATH = "../data/energy_price_demand_merged.csv"

def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )

def load():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TEMP TABLE staging_energy (
            region TEXT,
            settlement_date TIMESTAMP,
            total_demand NUMERIC(10,2),
            rrp NUMERIC(10,2),
            period_type TEXT
        );
    """)

    with open(CSV_PATH, "r") as f:
        next(f)  # skip header
        cur.copy_expert(
            "COPY staging_energy (region, settlement_date, total_demand, rrp, period_type) FROM STDIN WITH CSV",
            f
        )

    cur.execute("""
        INSERT INTO energy_price_demand (region, settlement_date, total_demand, rrp, period_type)
        SELECT region, settlement_date, total_demand, rrp, period_type
        FROM staging_energy
        ON CONFLICT (region, settlement_date) DO NOTHING;
    """)

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM energy_price_demand;")
    total = cur.fetchone()[0]
    print(f"Load complete. Table now has {total:,} rows.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    load()