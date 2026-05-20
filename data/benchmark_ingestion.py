import yfinance as yf
import psycopg2
import os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'fundguldasta_dev'),
    'user': os.getenv('DB_USER', 'fundguldasta_user'),
}

# Yahoo Finance tickers for Indian indices
BENCHMARKS = {
    'NIFTY50':      ('^NSEI',   'Nifty 50'),
    'NIFTY500':     ('^CRSLDX', 'Nifty 500'),
    'NIFTYMID150':  ('^NSEMDCP50', 'Nifty Midcap 150'),
    'NIFTYSML250':  ('^NSESMCP', 'Nifty Smallcap 250'),
}

def fetch_index_data(ticker, start_date='2006-01-01'):
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
            close_value = float(row['Close'].iloc[0] if hasattr(row['Close'], 'iloc') else row['Close'])
            if close_value <= 0:
                continue

            cursor.execute("""
                INSERT INTO benchmark_data (index_code, index_name, price_date, closing_value)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (index_code, price_date) DO NOTHING
            """, (index_code, index_name, price_date.date(), round(close_value, 4)))

            if cursor.rowcount == 1:
                inserted += 1
        except Exception as e:
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
            df = fetch_index_data(ticker)
            if df is not None and len(df) > 0:
                inserted = insert_benchmark_records(index_code, index_name, df)
                total_inserted += inserted
                print(f"  Inserted {inserted} records for {index_name}")
                print(f"  Date range: {df.index[0].date()} to {df.index[-1].date()}")
            else:
                print(f"  No data returned for {ticker}")
        except Exception as e:
            print(f"  ERROR for {ticker}: {e}")
            continue

    log_pipeline('success', total_inserted)
    print()
    print("=" * 50)
    print(f"BENCHMARK INGESTION COMPLETE")
    print(f"Total records inserted: {total_inserted}")
    print("=" * 50)

if __name__ == "__main__":
    main()
