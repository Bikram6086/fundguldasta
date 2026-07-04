import yfinance as yf
import psycopg2
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

from config.db import get_db_config
DB_CONFIG = get_db_config()

# Yahoo Finance tickers for Indian indices
BENCHMARKS = {
    'NIFTY50':      ('^NSEI',              'Nifty 50'),
    'NIFTY500':     ('^CRSLDX',            'Nifty 500'),
    'NIFTYMID150':  ('^NSEMDCP50',         'Nifty Midcap 150'),
    'NIFTYSML250':  ('NIFTYSMLCAP250.NS',  'Nifty Smallcap 250'),
    'NIFTYNXT50':   ('^NSMIDCP',           'Nifty Next 50'),
    'SENSEX':       ('^BSESN',             'BSE Sensex'),
}

def _latest_date_in_db(index_code: str) -> date | None:
    """Return the most recent price_date stored for this index, or None."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT MAX(price_date) FROM benchmark_data WHERE index_code = %s", (index_code,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def fetch_index_data(ticker: str, start_date: str):
    print(f"  Fetching {ticker} from {start_date}...")
    data = yf.download(ticker, start=start_date, progress=False, auto_adjust=True)
    return data

def insert_benchmark_records(index_code, index_name, df):
    if df is None or len(df) == 0:
        return 0

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    inserted = 0

    for price_date, row in df.iterrows():
        try:
            close_col = row['Close']
            close_value = float(close_col.iloc[0] if hasattr(close_col, 'iloc') else close_col)
            if close_value <= 0:
                continue
            cursor.execute("""
                INSERT INTO benchmark_data (index_code, index_name, price_date, closing_value)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (index_code, price_date) DO NOTHING
            """, (index_code, index_name, price_date.date(), round(close_value, 4)))
            if cursor.rowcount == 1:
                inserted += 1
        except psycopg2.Error:
            conn.rollback()
        except Exception:
            continue

    conn.commit()
    cursor.close()
    conn.close()
    return inserted

def log_pipeline(status, records, error=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pipeline_log (pipeline_name, run_date, started_at, completed_at, status, records_processed, error_message)
        VALUES ('benchmark_ingestion', CURRENT_DATE, NOW(), NOW(), %s, %s, %s)
    """, (status, records, error))
    conn.commit()
    cursor.close()
    conn.close()

def main():
    print("=" * 50)
    print("BENCHMARK INDEX INGESTION")
    print(f"Started: {datetime.now()}")
    print("=" * 50)

    total_inserted = 0

    for index_code, (ticker, index_name) in BENCHMARKS.items():
        print(f"\nProcessing {index_name} ({index_code})...")
        try:
            # Fetch only from 30 days before the last stored date — avoids downloading
            # thousands of already-stored rows on every nightly run.
            latest = _latest_date_in_db(index_code)
            if latest:
                start = (latest - timedelta(days=30)).strftime('%Y-%m-%d')
            else:
                start = '2006-01-01'

            df = fetch_index_data(ticker, start_date=start)
            if df is not None and len(df) > 0:
                inserted = insert_benchmark_records(index_code, index_name, df)
                total_inserted += inserted
                print(f"  Inserted {inserted} new records (fetched {len(df)} rows from {start})")
            else:
                print(f"  No data returned for {ticker}")
        except Exception as e:
            print(f"  ERROR for {ticker}: {e}")
            continue

    log_pipeline('success', total_inserted)
    print()
    print("=" * 50)
    print(f"BENCHMARK INGESTION COMPLETE — {total_inserted} new records")
    print("=" * 50)

if __name__ == "__main__":
    main()
