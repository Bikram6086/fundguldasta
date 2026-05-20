import requests
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'fundguldasta_dev'),
    'user': os.getenv('DB_USER', 'fundguldasta_user'),
}

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

CATEGORY_MAP = {
    'Large Cap': 'Large Cap',
    'Mid Cap': 'Mid Cap',
    'Small Cap': 'Small Cap',
    'Multi Cap': 'Multi Cap',
    'Flexi Cap': 'Flexi Cap',
    'Large & Mid Cap': 'Large & Mid Cap',
    'ELSS': 'ELSS',
    'Focused': 'Focused',
    'Sectoral': 'Sectoral',
    'Thematic': 'Thematic',
    'Contra': 'Contra',
    'Value': 'Value',
    'Dividend Yield': 'Dividend Yield',
    'Balanced Advantage': 'Balanced Advantage',
    'Aggressive Hybrid': 'Aggressive Hybrid',
    'Conservative Hybrid': 'Conservative Hybrid',
    'Equity Savings': 'Equity Savings',
}

def fetch_amfi_data():
    print(f"Fetching AMFI data from {AMFI_URL}")
    response = requests.get(AMFI_URL, timeout=30)
    response.raise_for_status()
    print(f"Downloaded {len(response.text)} characters")
    return response.text

def parse_amfi_data(raw_text):
    schemes = []
    current_amc = None
    lines = raw_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split(';')
        
        if len(parts) == 1:
            current_amc = line
            continue
        
        if len(parts) >= 5:
            try:
                scheme_code = parts[0].strip()
                scheme_name = parts[3].strip() if len(parts) > 3 else parts[1].strip()
                nav_str = parts[4].strip() if len(parts) > 4 else '0'
                
                if not scheme_code.isdigit():
                    continue
                
                plan_type = 'Direct' if 'Direct' in scheme_name else 'Regular'
                
                category = None
                for cat_key in CATEGORY_MAP:
                    if cat_key.lower() in scheme_name.lower():
                        category = CATEGORY_MAP[cat_key]
                        break
                
                schemes.append({
                    'scheme_code': scheme_code,
                    'scheme_name': scheme_name,
                    'amc_name': current_amc or 'Unknown',
                    'plan_type': plan_type,
                    'sebi_category': category,
                    'is_active': True,
                })
            except Exception as e:
                continue
    
    return schemes

def insert_schemes(schemes):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    inserted = 0
    updated = 0
    
    for scheme in schemes:
        cursor.execute("""
            INSERT INTO fund_metadata 
                (scheme_code, scheme_name, amc_name, plan_type, sebi_category, is_active, updated_at)
            VALUES 
                (%(scheme_code)s, %(scheme_name)s, %(amc_name)s, %(plan_type)s, %(sebi_category)s, %(is_active)s, NOW())
            ON CONFLICT (scheme_code) DO UPDATE SET
                scheme_name = EXCLUDED.scheme_name,
                amc_name = EXCLUDED.amc_name,
                plan_type = EXCLUDED.plan_type,
                sebi_category = EXCLUDED.sebi_category,
                updated_at = NOW()
        """, scheme)
        
        if cursor.rowcount == 1:
            inserted += 1
        else:
            updated += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return inserted, updated

def log_pipeline(status, records, error=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pipeline_log (pipeline_name, run_date, started_at, completed_at, status, records_processed, error_message)
        VALUES ('amfi_scheme_master', CURRENT_DATE, NOW(), NOW(), %s, %s, %s)
    """, (status, records, error))
    conn.commit()
    cursor.close()
    conn.close()

def main():
    print("=" * 50)
    print("AMFI Scheme Master Ingestion")
    print(f"Started: {datetime.now()}")
    print("=" * 50)
    
    try:
        raw_data = fetch_amfi_data()
        schemes = parse_amfi_data(raw_data)
        print(f"Parsed {len(schemes)} schemes")
        
        inserted, updated = insert_schemes(schemes)
        print(f"Inserted: {inserted} new schemes")
        print(f"Updated:  {updated} existing schemes")
        print(f"Total:    {inserted + updated} schemes processed")
        
        log_pipeline('success', inserted + updated)
        print("\nSCHEME MASTER INGESTION COMPLETE")
        
    except Exception as e:
        print(f"ERROR: {e}")
        log_pipeline('failed', 0, str(e))
        raise

if __name__ == "__main__":
    main()
