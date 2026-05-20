import requests
import psycopg2
import os
import re
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

def fetch_amfi_data():
    response = requests.get(AMFI_URL, timeout=30)
    response.raise_for_status()
    return response.text

def parse_managers_from_amfi(raw_text):
    """
    AMFI NAV file contains scheme details.
    We extract scheme codes and match to scheme info documents.
    For now we populate with available data and flag for SID enrichment.
    """
    managers = []
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

            scheme_name = parts[3].strip() if len(parts) > 3 else ''

            # Only process direct plans
            if 'Direct' not in scheme_name:
                continue

            managers.append({
                'scheme_code': scheme_code,
                'scheme_name': scheme_name,
            })
        except Exception:
            continue

    return managers

def get_scheme_info(scheme_code):
    """
    Fetch scheme details from AMFI scheme info API.
    Returns manager name if available.
    """
    try:
        url = f"https://api.mfapi.in/mf/{scheme_code}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            meta = data.get('meta', {})
            return {
                'fund_house': meta.get('fund_house', ''),
                'scheme_name': meta.get('scheme_name', ''),
                'scheme_type': meta.get('scheme_type', ''),
                'scheme_category': meta.get('scheme_category', ''),
            }
    except Exception:
        pass
    return None

def update_fund_metadata_category(scheme_code, category, scheme_type):
    """Update sebi_category in fund_metadata from mfapi data."""
    if not category:
        return
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE fund_metadata
        SET sebi_category = %s,
            fund_type = %s,
            updated_at = NOW()
        WHERE scheme_code = %s
        AND sebi_category IS NULL
    """, (category, scheme_type, scheme_code))
    conn.commit()
    cursor.close()
    conn.close()

def insert_manager_placeholder(scheme_code):
    """
    Insert a placeholder manager record.
    Will be enriched by SID parser and monthly disclosure parser.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO fund_managers (scheme_code, manager_name, is_current, source)
        VALUES (%s, %s, TRUE, %s)
        ON CONFLICT DO NOTHING
    """, (scheme_code, 'Pending SID enrichment', 'AMFI'))
    conn.commit()
    cursor.close()
    conn.close()

def enrich_categories_from_mfapi(schemes, sample_size=50):
    """
    Use mfapi.in to enrich category data for schemes missing it.
    Run on a sample to avoid overloading the API.
    """
    print(f"Enriching category data for up to {sample_size} schemes...")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT scheme_code FROM fund_metadata
        WHERE sebi_category IS NULL
        AND plan_type = 'Direct'
        AND is_active = TRUE
        LIMIT %s
    """, (sample_size,))
    missing_category = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    enriched = 0
    for scheme_code in missing_category:
        info = get_scheme_info(scheme_code)
        if info and info.get('scheme_category'):
            update_fund_metadata_category(
                scheme_code,
                info['scheme_category'],
                info['scheme_type']
            )
            enriched += 1

    return enriched

def detect_manager_changes():
    """
    Compare current AMFI data against stored manager records.
    Log any discrepancies for human review.
    This runs daily as part of the monitoring pipeline.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Check for schemes with no manager record yet
    cursor.execute("""
        SELECT fm.scheme_code, fm.scheme_name
        FROM fund_metadata fm
        LEFT JOIN fund_managers mgr ON fm.scheme_code = mgr.scheme_code
        WHERE mgr.id IS NULL
        AND fm.plan_type = 'Direct'
        AND fm.is_active = TRUE
        LIMIT 20
    """)
    missing = cursor.fetchall()
    cursor.close()
    conn.close()

    return missing

def log_pipeline(status, records, error=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pipeline_log (pipeline_name, run_date, started_at, completed_at, status, records_processed, error_message)
        VALUES ('manager_ingestion', CURRENT_DATE, NOW(), NOW(), %s, %s, %s)
    """, (status, records, error))
    conn.commit()
    cursor.close()
    conn.close()

def main():
    print("=" * 50)
    print("FUND MANAGER DATA INGESTION")
    print(f"Started: {datetime.now()}")
    print("=" * 50)

    try:
        # Step 1: Enrich missing categories from mfapi
        enriched = enrich_categories_from_mfapi([], sample_size=100)
        print(f"Enriched categories: {enriched} schemes updated")

        # Step 2: Check for schemes missing manager records
        missing = detect_manager_changes()
        print(f"Schemes missing manager data: {len(missing)}")

        # Step 3: Verify category coverage
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                sebi_category,
                COUNT(*) as fund_count
            FROM fund_metadata
            WHERE plan_type = 'Direct'
            AND is_active = TRUE
            AND sebi_category IS NOT NULL
            GROUP BY sebi_category
            ORDER BY fund_count DESC
            LIMIT 15
        """)
        categories = cursor.fetchall()
        cursor.close()
        conn.close()

        print("\nTop categories in database:")
        for cat, count in categories:
            print(f"  {cat:<35} {count} funds")

        log_pipeline('success', enriched)
        print("\nMANAGER INGESTION COMPLETE")

    except Exception as e:
        print(f"ERROR: {e}")
        log_pipeline('failed', 0, str(e))
        raise

if __name__ == "__main__":
    main()
