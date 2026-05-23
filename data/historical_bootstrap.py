import psycopg2
import os
import time
from datetime import datetime
from dotenv import load_dotenv

from config.db import get_db_config
DB_CONFIG = get_db_config()

def get_equity_schemes():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT scheme_code, scheme_name, amc_name
        FROM fund_metadata
        WHERE plan_type = 'Direct'
        AND is_active = TRUE
        AND (
            scheme_name ILIKE '%equity%'
            OR scheme_name ILIKE '%large cap%'
            OR scheme_name ILIKE '%mid cap%'
            OR scheme_name ILIKE '%small cap%'
            OR scheme_name ILIKE '%flexi cap%'
            OR scheme_name ILIKE '%multi cap%'
            OR scheme_name ILIKE '%elss%'
            OR scheme_name ILIKE '%bluechip%'
            OR scheme_name ILIKE '%opportunities%'
            OR scheme_name ILIKE '%focused%'
            OR scheme_name ILIKE '%value%'
            OR scheme_name ILIKE '%contra%'
            OR scheme_name ILIKE '%sectoral%'
            OR scheme_name ILIKE '%thematic%'
            OR scheme_name ILIKE '%balanced advantage%'
            OR scheme_name ILIKE '%aggressive hybrid%'
        )
        AND scheme_name ILIKE '%growth%'
        ORDER BY scheme_code
    """)
    schemes = cursor.fetchall()
    cursor.close()
    conn.close()
    return schemes

def get_already_bootstrapped():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT scheme_code
        FROM nav_data
        GROUP BY scheme_code
        HAVING COUNT(*) > 5
    """)
    codes = {row[0] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return codes

def fetch_historical_nav(scheme_code):
    try:
        from mftool import Mftool
        mf = Mftool()
        df = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
        return df
    except Exception as e:
        return None

def insert_historical_records(scheme_code, df):
    if df is None or len(df) == 0:
        return 0

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    inserted = 0

    for date_str, row in df.iterrows():
        try:
            # Format from mftool: DD-MM-YYYY
            nav_date = datetime.strptime(str(date_str), '%d-%m-%Y').date()
            nav_value = float(str(row['nav']).replace(',', ''))

            cursor.execute("""
                INSERT INTO nav_data (scheme_code, nav_date, nav_value)
                VALUES (%s, %s, %s)
                ON CONFLICT (scheme_code, nav_date) DO NOTHING
            """, (scheme_code, nav_date, nav_value))

            if cursor.rowcount == 1:
                inserted += 1
        except Exception:
            continue

    conn.commit()
    cursor.close()
    conn.close()
    return inserted

def save_progress(scheme_code, success):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pipeline_log (pipeline_name, run_date, started_at, completed_at, status, records_processed, error_message)
        VALUES ('historical_bootstrap', CURRENT_DATE, NOW(), NOW(), %s, %s, %s)
    """, ('success' if success else 'failed', 1, scheme_code))
    conn.commit()
    cursor.close()
    conn.close()

def main():
    print("=" * 60)
    print("HISTORICAL NAV BOOTSTRAP")
    print(f"Started: {datetime.now()}")
    print("This job runs once. Takes several hours to complete.")
    print("Safe to stop with Ctrl+C and restart — skips done funds.")
    print("=" * 60)

    schemes = get_equity_schemes()
    already_done = get_already_bootstrapped()
    pending = [s for s in schemes if s[0] not in already_done]

    print(f"Total equity schemes:  {len(schemes)}")
    print(f"Already bootstrapped:  {len(already_done)}")
    print(f"Pending:               {len(pending)}")
    print()

    total_inserted = 0
    failed = []

    for i, (scheme_code, scheme_name, amc_name) in enumerate(pending):
        try:
            df = fetch_historical_nav(scheme_code)

            if df is not None and len(df) > 0:
                inserted = insert_historical_records(scheme_code, df)
                total_inserted += inserted
                print(f"[{i+1}/{len(pending)}] {scheme_code} — {scheme_name[:45]} — {inserted} records")
                save_progress(scheme_code, True)
            else:
                print(f"[{i+1}/{len(pending)}] {scheme_code} — No data — skipping")
                failed.append(scheme_code)

            time.sleep(0.3)

        except KeyboardInterrupt:
            print(f"\nStopped at scheme {i+1}/{len(pending)}")
            print(f"Total inserted so far: {total_inserted}")
            print("Run again to resume from where you left off.")
            break

        except Exception as e:
            print(f"[{i+1}/{len(pending)}] {scheme_code} — ERROR: {e}")
            failed.append(scheme_code)
            time.sleep(1)
            continue

    print()
    print("=" * 60)
    print(f"BOOTSTRAP COMPLETE")
    print(f"Total records inserted: {total_inserted}")
    print(f"Failed schemes:         {len(failed)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
