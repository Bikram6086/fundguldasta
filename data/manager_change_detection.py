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

# Key funds we monitor closely — bouquet funds
MONITORED_FUNDS = {
    '118834': 'Mirae Asset Large Cap Fund',
    '122639': 'Parag Parikh Flexi Cap Fund',
    '120505': 'Kotak Equity Opportunities Fund',
    '119553': 'HDFC Flexi Cap Fund',
    '120503': 'Axis Midcap Fund',
    '118778': 'Nippon India Small Cap Fund',
    '120465': 'DSP Midcap Fund',
    '118988': 'HDFC Mid-Cap Opportunities Fund',
    '118825': 'Mirae Asset Emerging Bluechip Fund',
    '148683': 'Quant Small Cap Fund',
    '135783': 'Tata Digital India Fund',
    '135300': 'Motilal Oswal Nasdaq 100 FOF',
}

def fetch_scheme_info(scheme_code):
    """Fetch current scheme details from mfapi."""
    try:
        url = f"https://api.mfapi.in/mf/{scheme_code}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('meta', {})
    except Exception:
        pass
    return None

def get_stored_manager(scheme_code):
    """Get the currently stored manager for a scheme."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT manager_name, appointment_date
        FROM fund_managers
        WHERE scheme_code = %s
        AND is_current = TRUE
        ORDER BY id DESC LIMIT 1
    """, (scheme_code,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def store_manager(scheme_code, manager_name, source='mfapi'):
    """Store or update manager record."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Mark existing records as not current
    cursor.execute("""
        UPDATE fund_managers
        SET is_current = FALSE, departure_date = CURRENT_DATE
        WHERE scheme_code = %s AND is_current = TRUE
        AND manager_name != %s
    """, (scheme_code, manager_name))

    # Insert new current manager
    cursor.execute("""
        INSERT INTO fund_managers (scheme_code, manager_name, is_current, appointment_date, source)
        VALUES (%s, %s, TRUE, CURRENT_DATE, %s)
        ON CONFLICT DO NOTHING
    """, (scheme_code, manager_name, source))

    conn.commit()
    cursor.close()
    conn.close()

def log_change(scheme_code, old_manager, new_manager):
    """Log detected manager change for review."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO manager_change_log
        (scheme_code, old_manager_name, new_manager_name, detected_date, detection_source)
        VALUES (%s, %s, %s, CURRENT_DATE, 'daily_detection')
    """, (scheme_code, old_manager, new_manager))
    conn.commit()
    cursor.close()
    conn.close()

def check_monitored_funds():
    """
    Check all monitored bouquet funds for manager changes.
    Returns list of detected changes.
    """
    changes_detected = []

    for scheme_code, fund_name in MONITORED_FUNDS.items():
        info = fetch_scheme_info(scheme_code)
        if not info:
            continue

        # mfapi returns fund_manager field in some responses
        current_manager = info.get('fund_manager', '')

        if not current_manager:
            continue

        stored = get_stored_manager(scheme_code)

        if stored is None:
            # First time seeing this fund — store it
            store_manager(scheme_code, current_manager)
            print(f"  NEW: {fund_name} — Manager: {current_manager}")

        elif stored[0] != current_manager and stored[0] != 'Pending SID enrichment':
            # Manager change detected
            print(f"  ⚠️  CHANGE DETECTED: {fund_name}")
            print(f"      Previous: {stored[0]}")
            print(f"      Current:  {current_manager}")
            log_change(scheme_code, stored[0], current_manager)
            store_manager(scheme_code, current_manager)
            changes_detected.append({
                'scheme_code': scheme_code,
                'fund_name': fund_name,
                'old_manager': stored[0],
                'new_manager': current_manager,
            })
        else:
            print(f"  ✓ {fund_name[:45]} — No change")

    return changes_detected

def log_pipeline(status, records, error=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pipeline_log
        (pipeline_name, run_date, started_at, completed_at, status, records_processed, error_message)
        VALUES ('manager_change_detection', CURRENT_DATE, NOW(), NOW(), %s, %s, %s)
    """, (status, records, error))
    conn.commit()
    cursor.close()
    conn.close()

def main():
    print("=" * 50)
    print("MANAGER CHANGE DETECTION")
    print(f"Run date: {date.today()}")
    print("=" * 50)

    try:
        print(f"\nChecking {len(MONITORED_FUNDS)} monitored bouquet funds...\n")
        changes = check_monitored_funds()

        print()
        if changes:
            print(f"⚠️  {len(changes)} MANAGER CHANGE(S) DETECTED — REVIEW REQUIRED")
            for c in changes:
                print(f"   {c['fund_name']}: {c['old_manager']} → {c['new_manager']}")
        else:
            print("✓ No manager changes detected in monitored funds")

        log_pipeline('success', len(changes))
        print(f"\nDETECTION COMPLETE — {datetime.now()}")

    except Exception as e:
        print(f"ERROR: {e}")
        log_pipeline('failed', 0, str(e))
        raise

if __name__ == "__main__":
    main()
