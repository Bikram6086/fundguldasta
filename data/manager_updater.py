"""
P22: Fund manager data maintenance tool.

Indian MF ecosystem has no consolidated API for fund manager data.
This tool provides structured workflows to:
  - List current manager records with freshness info
  - Add or update a manager record
  - Record a manager departure
  - Log changes to manager_change_log for P15 alert pipeline

Usage:
    python3 data/manager_updater.py list
    python3 data/manager_updater.py add <scheme_code> <manager_name> <appointment_date> [experience_years]
    python3 data/manager_updater.py depart <scheme_code> <manager_name> <departure_date>
    python3 data/manager_updater.py verify <scheme_code>

Data sources to cross-reference manually:
  - AMC fund page (look for "Fund Manager" section)
  - SEBI SID filings at sebi.gov.in (scheme information document)
  - AMFI scheme listing at amfiindia.com
"""

import sys
import psycopg2
from datetime import date, datetime

sys.path.insert(0, '/home/hpbikram6086/fundguldasta')
from config.db import get_db_config
from config.scheme_codes import VERIFIED_FUNDS

DB_CONFIG = get_db_config()

VERIFIED_CODES = set(VERIFIED_FUNDS.keys())


def _conn():
    return psycopg2.connect(**DB_CONFIG)


def cmd_list():
    """List all manager records with tenure and freshness."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT fm.scheme_code, fm.manager_name, fm.appointment_date,
               fm.departure_date, fm.is_current, fm.total_experience_years,
               fm.source, fm.updated_at
        FROM fund_managers fm
        ORDER BY fm.scheme_code, fm.appointment_date
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("fund_managers is empty.")
        return

    today = date.today()
    current_code = None
    for r in rows:
        code, name, appt, depart, is_curr, exp_yrs, source, updated = r
        if code != current_code:
            fund_name = VERIFIED_FUNDS.get(code, {}).get('name', code)
            print(f"\n{code} — {fund_name}")
            current_code = code
        tenure_yrs = round((today - appt).days / 365.25, 1) if appt else "?"
        status = "current" if is_curr else f"departed {depart}"
        stale_flag = " ⚠ (data >180 days old)" if updated and (datetime.now() - updated).days > 180 else ""
        print(f"  {name:<35} appt={appt}  tenure={tenure_yrs}yr  exp={exp_yrs}yr  {status}  [{source}]{stale_flag}")


def cmd_add(scheme_code, manager_name, appointment_date_str, experience_years=None):
    """Add or update a manager record."""
    if scheme_code not in VERIFIED_CODES:
        print(f"Warning: {scheme_code} is not a verified scheme code.")

    try:
        appt_date = datetime.strptime(appointment_date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: appointment_date must be YYYY-MM-DD, got: {appointment_date_str}")
        sys.exit(1)

    exp_yrs = int(experience_years) if experience_years else None

    conn = _conn()
    cur = conn.cursor()

    # Check if record exists
    cur.execute("""
        SELECT id FROM fund_managers
        WHERE scheme_code = %s AND manager_name = %s AND is_current = TRUE
    """, (scheme_code, manager_name))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE fund_managers
            SET appointment_date = %s, total_experience_years = %s,
                source = 'MANUAL-VERIFIED', updated_at = NOW()
            WHERE id = %s
        """, (appt_date, exp_yrs, existing[0]))
        print(f"Updated: {manager_name} for scheme {scheme_code}")
    else:
        cur.execute("""
            INSERT INTO fund_managers
                (scheme_code, manager_name, appointment_date, is_current,
                 total_experience_years, source)
            VALUES (%s, %s, %s, TRUE, %s, 'MANUAL-VERIFIED')
        """, (scheme_code, manager_name, appt_date, exp_yrs))
        print(f"Added: {manager_name} for scheme {scheme_code} from {appt_date}")

    conn.commit()
    cur.close()
    conn.close()


def cmd_depart(scheme_code, manager_name, departure_date_str):
    """Record a manager departure and log to manager_change_log."""
    try:
        depart_date = datetime.strptime(departure_date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: departure_date must be YYYY-MM-DD, got: {departure_date_str}")
        sys.exit(1)

    conn = _conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, appointment_date FROM fund_managers
        WHERE scheme_code = %s AND manager_name ILIKE %s AND is_current = TRUE
    """, (scheme_code, f"%{manager_name}%"))
    row = cur.fetchone()

    if not row:
        print(f"No current manager matching '{manager_name}' for scheme {scheme_code}")
        cur.close()
        conn.close()
        return

    mgr_id, appt_date = row
    cur.execute("""
        UPDATE fund_managers
        SET departure_date = %s, is_current = FALSE, updated_at = NOW()
        WHERE id = %s
    """, (depart_date, mgr_id))

    # Log to manager_change_log for P15 alert pipeline
    cur.execute("""
        INSERT INTO manager_change_log
            (scheme_code, change_type, old_manager, new_manager, change_date, detected_at, notified)
        VALUES (%s, 'departure', %s, NULL, %s, NOW(), FALSE)
    """, (scheme_code, manager_name, depart_date))

    conn.commit()
    cur.close()
    conn.close()
    print(f"Recorded departure: {manager_name} left scheme {scheme_code} on {departure_date_str}")
    print("  → Logged to manager_change_log for P15 alert pipeline")


def cmd_verify(scheme_code):
    """Show current manager data for manual verification against AMC website."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT manager_name, appointment_date, is_current, total_experience_years, source, updated_at
        FROM fund_managers
        WHERE scheme_code = %s
        ORDER BY appointment_date
    """, (scheme_code,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    fund_name = VERIFIED_FUNDS.get(scheme_code, {}).get('name', scheme_code)
    amc = VERIFIED_FUNDS.get(scheme_code, {}).get('amc', '').lower().replace(' ', '')

    print(f"\n{scheme_code} — {fund_name}")
    print(f"  AMC website: https://www.{amc}mf.com (check 'Fund Manager' page)")
    print(f"  AMFI page:   https://www.amfiindia.com/nav-history-download (search scheme code)")

    if not rows:
        print("  No manager records found.")
        return

    today = date.today()
    for r in rows:
        name, appt, is_curr, exp_yrs, source, updated = r
        tenure = round((today - appt).days / 365.25, 1) if appt else "?"
        stale = " ← STALE (verify!)" if updated and (datetime.now() - updated).days > 180 else ""
        print(f"  {'[CURRENT]' if is_curr else '[DEPARTED]'} {name}  appt={appt}  tenure={tenure}yr  source={source}{stale}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == 'list':
        cmd_list()
    elif args[0] == 'add' and len(args) >= 4:
        cmd_add(*args[1:])
    elif args[0] == 'depart' and len(args) >= 4:
        cmd_depart(*args[1:4])
    elif args[0] == 'verify' and len(args) >= 2:
        cmd_verify(args[1])
    else:
        print(__doc__)
