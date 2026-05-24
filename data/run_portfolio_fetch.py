"""
One-time script: populate portfolio_holdings in Timescale Cloud production DB.
Fetches from PPFAS, HDFC Flexi Cap, HDFC Mid Cap (the 3 confirmed URLs).
Run from WSL: python3 data/run_portfolio_fetch.py
"""
import sys, os, logging
from datetime import date
sys.path.insert(0, '/home/hpbikram6086/fundguldasta')
from dotenv import load_dotenv
load_dotenv('/home/hpbikram6086/fundguldasta/config/.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

import psycopg2

# Production Timescale Cloud (Mumbai) — run mode determined by env var or arg
USE_PROD = "--prod" in sys.argv or os.getenv("USE_PROD") == "1"
if USE_PROD:
    db_config = {
        "host":     "oiwukb56wf.rfzjm4xx0h.tsdb.cloud.timescale.com",
        "port":     31740,
        "database": "tsdb",
        "user":     "tsdbadmin",
        "password": os.getenv("TSDB_PASS", ""),
        "sslmode":  "require",
    }
    if not db_config["password"]:
        print("ERROR: set TSDB_PASS env var")
        sys.exit(1)
else:
    db_config = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "database": os.getenv("DB_NAME", "fundguldasta_dev"),
        "user": os.getenv("DB_USER", "fundguldasta_user"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
print(f"Connecting to {db_config['host']}:{db_config['port']}/{db_config['database']} ...")

# Verify connection
conn = psycopg2.connect(**db_config)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM portfolio_holdings")
before = cur.fetchone()[0]
print(f"portfolio_holdings rows before: {before}")
cur.close()
conn.close()

from data.portfolio_fetcher import fetch_all_configured

# Last month end = April 30 2026 (most recent full month)
as_of = date(2026, 4, 30)
print(f"\nFetching portfolio holdings as of {as_of}...\n")
results = fetch_all_configured(as_of=as_of, db_config=db_config)

print("\n── Results ──")
for r in results:
    print(f"  {r.get('fund_name', r['scheme_code'])}: {r['status']} — {r.get('holdings_count', 0)} holdings")

# Verify after
conn = psycopg2.connect(**db_config)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM portfolio_holdings")
after = cur.fetchone()[0]
cur.execute("SELECT DISTINCT scheme_code, disclosure_date, COUNT(*) FROM portfolio_holdings GROUP BY scheme_code, disclosure_date")
rows = cur.fetchall()
cur.close()
conn.close()

print(f"\nportfolio_holdings rows after: {after}")
print("\nHoldings by fund:")
for sc, dd, cnt in rows:
    print(f"  scheme {sc}, date {dd}: {cnt} stocks")
