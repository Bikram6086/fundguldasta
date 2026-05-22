#!/usr/bin/env python3
"""
FundGuldasta — Data Integrity Validator
=======================================
Run daily after the refresh pipeline. Exits with code 1 if any assertion fails,
so it can be used in cron and CI to catch regressions before users see them.

Usage:
    python3 scripts/validate_integrity.py
    python3 scripts/validate_integrity.py --strict   # fail on warnings too
"""
import sys, os, json, argparse
sys.path.insert(0, '/home/hpbikram6086/fundguldasta')

import psycopg2
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    dbname=os.getenv("DB_NAME", "fundguldasta_dev"),
    user=os.getenv("DB_USER", "fundguldasta_user"),
)

VERIFIED_CODES = [
    "118825","120152","118834","122639","118955",
    "120505","119071","118989","118778","120828",
    "149134","145552","135800",
]
ARCHETYPES = ["steady", "balanced", "aggressive", "conviction"]
MANAGER_SENTINEL_RANGE = range(38, 46)   # 38-45 = "no real data" band

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"

errors   = []
warnings = []

def check(name, condition, message, is_warning=False):
    if condition:
        print(f"  {PASS}  {name}")
    else:
        symbol = WARN if is_warning else FAIL
        print(f"  {symbol}  {name}")
        print(f"       → {message}")
        if is_warning:
            warnings.append(f"{name}: {message}")
        else:
            errors.append(f"{name}: {message}")


def run_checks():
    conn = psycopg2.connect(**DB)
    cur  = conn.cursor()

    print("\n══════════════════════════════════════════")
    print("  FundGuldasta Integrity Check")
    print(f"  {date.today()}")
    print("══════════════════════════════════════════\n")

    # ── 1. NAV Data Freshness ────────────────────────────────────────────────
    print("[ NAV Data ]")
    cur.execute("SELECT MAX(nav_date) FROM nav_data")
    max_nav = cur.fetchone()[0]
    staleness = (date.today() - max_nav).days if max_nav else 9999
    check("NAV data exists", max_nav is not None, "nav_data table is empty")
    check("NAV data fresh (≤10 days)", staleness <= 10,
          f"Last NAV: {max_nav} ({staleness} days ago) — run nav_ingestion.py")
    check("NAV data not stale (≤5 days)", staleness <= 5,
          f"NAV is {staleness} days old — borderline stale", is_warning=True)

    # ── 2. All 13 Funds Have NAV History ────────────────────────────────────
    print("\n[ Fund NAV Coverage ]")
    for code in VERIFIED_CODES:
        cur.execute(
            "SELECT COUNT(*) FROM nav_data WHERE scheme_code=%s", (code,)
        )
        count = cur.fetchone()[0]
        check(
            f"Fund {code} NAV records ≥750",
            count >= 750,
            f"Only {count} records — minimum 3yr of trading days required"
        )

    # ── 3. Manager Data Integrity ────────────────────────────────────────────
    print("\n[ Manager Data ]")
    for code in VERIFIED_CODES:
        cur.execute(
            """SELECT manager_name, appointment_date
               FROM fund_managers
               WHERE scheme_code=%s AND is_current=TRUE
               ORDER BY appointment_date ASC LIMIT 1""",
            (code,)
        )
        row = cur.fetchone()
        check(f"Fund {code} has manager record",
              row is not None,
              "No entry in fund_managers — data missing")
        if row:
            check(f"Fund {code} manager not placeholder",
                  row[0] != "Pending SID enrichment",
                  f"Manager is still '{row[0]}' — SID data not loaded")
            check(f"Fund {code} has appointment_date",
                  row[1] is not None,
                  "appointment_date is NULL — tenure cannot be scored")

    # ── 4. Bouquet Cache Integrity ───────────────────────────────────────────
    print("\n[ Bouquet Cache (7yr) ]")
    cache_cutoff = date.today() - timedelta(days=35)

    for arch in ARCHETYPES:
        cur.execute(
            """SELECT confidence_json, computation_date
               FROM bouquet_cache
               WHERE archetype_id=%s AND horizon_years=7
               ORDER BY computation_date DESC LIMIT 1""",
            (arch,)
        )
        row = cur.fetchone()

        check(f"Cache exists: {arch}", row is not None,
              f"No cache for archetype='{arch}' horizon=7 — run recompute_7yr.py")

        if not row:
            continue

        conf = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        computed = row[1]

        # Age
        check(f"Cache fresh: {arch} (≤35 days)", computed >= cache_cutoff,
              f"Cache computed {computed} — older than 35 days")

        # Overall confidence score
        score = conf.get("score") or conf.get("overall_score")
        check(f"Confidence ≥60: {arch}", score is not None and score >= 60,
              f"Confidence score {score} is below 60 — data regression")

        # Manager stability factor
        ms_score = conf.get("factors", {}).get("manager_stability", {}).get("score")
        if ms_score is not None:
            check(f"Manager factor >50: {arch}", ms_score > 50,
                  f"manager_stability={ms_score} looks like sentinel — "
                  f"cache pre-dates the ORDER BY fix. Recompute required.")

    # ── 5. Benchmark Data ────────────────────────────────────────────────────
    print("\n[ Benchmark Data ]")
    cur.execute("SELECT COUNT(*) FROM benchmark_data")
    bcount = cur.fetchone()[0]
    check("Benchmark data exists", bcount > 0, "benchmark_data table is empty")
    cur.execute("SELECT MAX(price_date) FROM benchmark_data")
    max_bench = cur.fetchone()[0]
    if max_bench:
        bench_staleness = (date.today() - max_bench).days
        check("Benchmark fresh (≤10 days)", bench_staleness <= 10,
              f"Benchmark last updated {max_bench} ({bench_staleness} days ago)")

    cur.close()
    conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="Fail on warnings too")
    args = parser.parse_args()

    run_checks()

    print("\n══════════════════════════════════════════")
    if errors:
        print(f"  FAILED — {len(errors)} error(s), {len(warnings)} warning(s)")
        for e in errors:
            print(f"    ✗ {e}")
        sys.exit(1)
    elif warnings and args.strict:
        print(f"  FAILED (strict) — {len(warnings)} warning(s)")
        for w in warnings:
            print(f"    ⚠ {w}")
        sys.exit(1)
    else:
        print(f"  ALL CHECKS PASSED  ({len(warnings)} warning(s))")
        if warnings:
            for w in warnings:
                print(f"    ⚠ {w}")
        sys.exit(0)


if __name__ == "__main__":
    main()
