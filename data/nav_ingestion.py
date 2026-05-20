import requests
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

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

def fetch_nav_data():
    print(f"Fetching NAV data from AMFI...")
    response = requests.get(AMFI_URL, timeout=30)
    response.raise_for_status()
    return response.text

def parse_nav_data(raw_text):
    nav_records = []
    lines = raw_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split(';')
        if len(parts) < 6:
            continue
        
        try:
            scheme_code = parts[0].strip()
            if not scheme_code.isdigit():
                continue
            
            nav_str = parts[4].strip()
            date_str = parts[5].strip()
            
            if nav_str in ('N.A.', 'NA', '-', ''):
                continue
            
            nav_value = float(nav_str)
            nav_date = datetime.strptime(date_str, '%d-%b-%Y').date()
            
            nav_records.append({
                'scheme_code': scheme_code,
                'nav_date': nav_date,
                'nav_value': nav_value,
            })
        except Exception:
            continue
    
    return nav_records

def insert_nav_records(records):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    batch_size = 1000
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        
        for record in batch:
            cursor.execute("""
                INSERT INTO nav_data (scheme_code, nav_date, nav_value)
                VALUES (%(scheme_code)s, %(nav_date)s, %(nav_value)s)
                ON CONFLICT (scheme_code, nav_date) DO NOTHING
            """, record)
            
            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
        
        conn.commit()
        if (i // batch_size + 1) % 10 == 0:
            print(f"  Processed {i + len(batch)} records...")
    
    cursor.close()
    conn.close()
    
    return inserted, skipped

def log_pipeline(status, records, error=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pipeline_log (pipeline_name, run_date, started_at, completed_at, status, records_processed, error_message)
        VALUES ('nav_ingestion', CURRENT_DATE, NOW(), NOW(), %s, %s, %s)
    """, (status, records, error))
    conn.commit()
    cursor.close()
    conn.close()

def main():
    print("=" * 50)
    print("AMFI Daily NAV Ingestion")
    print(f"Started: {datetime.now()}")
    print("=" * 50)
    
    try:
        raw_data = fetch_nav_data()
        records = parse_nav_data(raw_data)
        print(f"Parsed {len(records)} NAV records")
        
        inserted, skipped = insert_nav_records(records)
        print(f"Inserted: {inserted} new records")
        print(f"Skipped:  {skipped} existing records")
        
        log_pipeline('success', inserted)
        print(f"\nNAV INGESTION COMPLETE — {datetime.now()}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        log_pipeline('failed', 0, str(e))
        raise

if __name__ == "__main__":
    main()
