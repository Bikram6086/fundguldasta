"""
Bulk NAV bootstrap — fetches full historical NAV for all equity/hybrid funds
that have fund_metadata but fewer than 750 NAV records.

Covers both Direct and Regular Growth plans across all equity/hybrid/solution
categories. Safe to stop with Ctrl+C and restart — skips already-done funds.

Estimated time: ~10-20 min for 400-600 funds at ~1.5s/fund via mftool.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import time
from datetime import datetime
from config.db import get_db_config

DB_CONFIG = get_db_config()

EQUITY_CATEGORIES = {
    'Large Cap', 'Mid Cap', 'Small Cap', 'Flexi Cap', 'Multi Cap',
    'ELSS', 'Focused', 'Value', 'Contra', 'Dividend Yield',
    'Aggressive Hybrid', 'Conservative Hybrid', 'Balanced Advantage',
    'Equity Savings', 'Other Scheme - FoF Domestic',
}

EQUITY_KEYWORDS = [
    'equity', 'large cap', 'mid cap', 'small cap', 'flexi cap', 'multi cap',
    'elss', 'bluechip', 'blue chip', 'opportunities', 'focused', 'focus',
    'value', 'contra', 'sectoral', 'thematic', 'balanced advantage',
    'aggressive hybrid', 'hybrid', 'diversified', 'dividend yield',
    'nifty', 'sensex', 'nasdaq', 'index fund',
]


def get_target_schemes():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # All active growth variants (direct + regular) in equity/hybrid categories
    # that have < 750 NAV records
    cur.execute("""
        SELECT fm.scheme_code, fm.scheme_name, fm.amc_name, COUNT(nd.nav_date) as nav_count
        FROM fund_metadata fm
        LEFT JOIN nav_data nd ON fm.scheme_code = nd.scheme_code
        WHERE fm.is_active = TRUE
        AND fm.scheme_name NOT ILIKE '%%idcw%%'
        AND fm.scheme_name NOT ILIKE '%%dividend%%'
        AND fm.scheme_name NOT ILIKE '%%liquid%%'
        AND fm.scheme_name NOT ILIKE '%%overnight%%'
        AND fm.scheme_name NOT ILIKE '%%gilt%%'
        AND fm.scheme_name NOT ILIKE '%%arbitrage%%'
        AND fm.scheme_name NOT ILIKE '%%debt%%'
        AND fm.scheme_name NOT ILIKE '%%bond%%'
        AND fm.scheme_name NOT ILIKE '%%banking and psu%%'
        AND fm.scheme_name NOT ILIKE '%%corporate bond%%'
        AND fm.scheme_name NOT ILIKE '%%credit risk%%'
        AND fm.scheme_name NOT ILIKE '%%money market%%'
        AND (
            fm.sebi_category = ANY(%s)
            OR fm.scheme_name ILIKE '%%growth%%'
        )
        GROUP BY fm.scheme_code, fm.scheme_name, fm.amc_name
        HAVING COUNT(nd.nav_date) < 750
        ORDER BY COUNT(nd.nav_date) DESC, fm.scheme_code
    """, (list(EQUITY_CATEGORIES),))

    schemes = cur.fetchall()
    cur.close()
    conn.close()
    return schemes


def fetch_historical_nav(scheme_code):
    try:
        from mftool import Mftool
        mf = Mftool()
        df = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
        return df
    except Exception:
        return None


def insert_records(scheme_code, df):
    if df is None or len(df) == 0:
        return 0
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    inserted = 0
    for date_str, row in df.iterrows():
        try:
            nav_date = datetime.strptime(str(date_str), '%d-%m-%Y').date()
            nav_value = float(str(row['nav']).replace(',', ''))
            cur.execute(
                "INSERT INTO nav_data (scheme_code, nav_date, nav_value) "
                "VALUES (%s, %s, %s) ON CONFLICT (scheme_code, nav_date) DO NOTHING",
                (scheme_code, nav_date, nav_value)
            )
            if cur.rowcount == 1:
                inserted += 1
        except Exception:
            continue
    conn.commit()
    cur.close()
    conn.close()
    return inserted


def main():
    print("=" * 65)
    print("BULK NAV BOOTSTRAP — equity/hybrid growth funds < 750 records")
    print(f"Started: {datetime.now()}")
    print("Safe to Ctrl+C and restart — skips already-done funds.")
    print("=" * 65)

    schemes = get_target_schemes()
    print(f"\nTarget funds to bootstrap: {len(schemes)}")
    print("(Only funds with < 750 records that pass equity/growth filters)\n")

    total_inserted = 0
    done = 0
    failed = []

    for i, (scheme_code, scheme_name, amc_name, existing_count) in enumerate(schemes):
        try:
            df = fetch_historical_nav(scheme_code)
            if df is not None and len(df) > 0:
                inserted = insert_records(scheme_code, df)
                total_inserted += inserted
                done += 1
                print(f"[{i+1}/{len(schemes)}] {scheme_code} — {scheme_name[:50]} — +{inserted} records (had {existing_count})")
            else:
                print(f"[{i+1}/{len(schemes)}] {scheme_code} — {scheme_name[:50]} — no data from mftool")
                failed.append(scheme_code)
            time.sleep(0.3)  # polite rate limit
        except KeyboardInterrupt:
            print(f"\nInterrupted at {i+1}/{len(schemes)}. Progress saved — restart to continue.")
            break
        except Exception as e:
            print(f"[{i+1}/{len(schemes)}] {scheme_code} — ERROR: {e}")
            failed.append(scheme_code)
            continue

    print(f"\n{'='*65}")
    print(f"BULK BOOTSTRAP COMPLETE")
    print(f"  Funds processed:  {done}")
    print(f"  Total records:    {total_inserted}")
    print(f"  Failed/no-data:   {len(failed)}")
    if failed:
        print(f"  Failed codes: {failed[:20]}")
    print(f"Completed: {datetime.now()}")


if __name__ == "__main__":
    main()
