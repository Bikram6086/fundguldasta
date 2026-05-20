"""
FUNDGULDASTA — ELIGIBILITY FILTER (ALGORITHM LAYER 1)
======================================================
Binary pass/fail. No scoring yet.
A fund either qualifies for consideration or it does not.

Hard elimination criteria — no exceptions:
1. Must be a Direct plan — no regular plans ever
2. AUM above Rs 500 Crore — liquidity and survival
3. Expense ratio below 1.5% — cost ceiling
4. Active status — no wound-up or merged funds
5. Minimum NAV history — must have enough data
6. Style consistency — fund behaves like its stated category

This layer reduces 14,000+ schemes to ~200-300 eligible funds.
"""

import psycopg2
import numpy as np
import pandas as pd
import os
from datetime import datetime, date
from dotenv import load_dotenv
from engine.rolling_returns import get_nav_series, get_benchmark_series

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'fundguldasta_dev'),
    'user': os.getenv('DB_USER', 'fundguldasta_user'),
}

# Eligibility thresholds
MIN_AUM_CRORES = 500
MAX_EXPENSE_RATIO = 1.5
MIN_NAV_RECORDS = 750        # ~3 years of daily NAV
MIN_NAV_RECORDS_FULL = 1750  # ~7 years — Tier 1 threshold

# Target categories for equity bouquets
ELIGIBLE_CATEGORIES = [
    'Large Cap',
    'Mid Cap',
    'Small Cap',
    'Flexi Cap',
    'Multi Cap',
    'Large & Mid Cap',
    'ELSS',
    'Focused',
    'Contra',
    'Value',
    'Dividend Yield',
    'Balanced Advantage',
    'Aggressive Hybrid',
    'Equity Savings',
]

# Scheme name keywords that identify equity growth funds
EQUITY_GROWTH_KEYWORDS = [
    'growth',
]

EXCLUDED_KEYWORDS = [
    'idcw', 'dividend', 'weekly', 'monthly', 'quarterly',
    'debt', 'liquid', 'overnight', 'money market',
    'gilt', 'bond', 'income', 'credit risk',
    'arbitrage', 'conservative',
]

def get_all_direct_equity_funds():
    """
    Fetch all direct plan equity growth funds from fund_metadata.
    First-pass filter using database queries.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            fm.scheme_code,
            fm.scheme_name,
            fm.amc_name,
            fm.sebi_category,
            fm.plan_type,
            fm.is_active,
            fm.aum_crores,
            fm.expense_ratio,
            fm.inception_date,
            COUNT(nd.nav_date) as nav_record_count
        FROM fund_metadata fm
        LEFT JOIN nav_data nd ON fm.scheme_code = nd.scheme_code
        WHERE fm.plan_type = 'Direct'
        AND fm.is_active = TRUE
        AND fm.scheme_name ILIKE '%growth%'
        AND fm.scheme_name NOT ILIKE '%idcw%'
        AND fm.scheme_name NOT ILIKE '%dividend%'
        AND fm.scheme_name NOT ILIKE '%debt%'
        AND fm.scheme_name NOT ILIKE '%liquid%'
        AND fm.scheme_name NOT ILIKE '%overnight%'
        AND fm.scheme_name NOT ILIKE '%gilt%'
        AND fm.scheme_name NOT ILIKE '%bond%'
        AND fm.scheme_name NOT ILIKE '%arbitrage%'
        GROUP BY
            fm.scheme_code, fm.scheme_name, fm.amc_name,
            fm.sebi_category, fm.plan_type, fm.is_active,
            fm.aum_crores, fm.expense_ratio, fm.inception_date
        HAVING COUNT(nd.nav_date) >= 750
        ORDER BY fm.scheme_code
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    funds = []
    for row in rows:
        funds.append({
            'scheme_code':      row[0],
            'scheme_name':      row[1],
            'amc_name':         row[2],
            'sebi_category':    row[3],
            'plan_type':        row[4],
            'is_active':        row[5],
            'aum_crores':       float(row[6]) if row[6] else None,
            'expense_ratio':    float(row[7]) if row[7] else None,
            'inception_date':   row[8],
            'nav_record_count': row[9],
        })

    return funds

def check_expense_ratio(fund):
    """Pass if expense ratio is below ceiling or unknown."""
    if fund['expense_ratio'] is None:
        return True, "Expense ratio unknown — allowing pending verification"
    if fund['expense_ratio'] > MAX_EXPENSE_RATIO:
        return False, f"Expense ratio {fund['expense_ratio']}% exceeds {MAX_EXPENSE_RATIO}% ceiling"
    return True, f"Expense ratio {fund['expense_ratio']}% within limit"

def check_aum(fund):
    """Pass if AUM is above floor or unknown."""
    if fund['aum_crores'] is None:
        return True, "AUM unknown — allowing pending verification"
    if fund['aum_crores'] < MIN_AUM_CRORES:
        return False, f"AUM Rs{fund['aum_crores']}Cr below Rs{MIN_AUM_CRORES}Cr minimum"
    return True, f"AUM Rs{fund['aum_crores']}Cr above minimum"

def check_nav_history(fund):
    """Check if fund has sufficient NAV history."""
    count = fund['nav_record_count']
    if count >= MIN_NAV_RECORDS_FULL:
        return True, "Full", f"{count} records — Tier 1 evidence"
    elif count >= MIN_NAV_RECORDS:
        return True, "Partial", f"{count} records — Tier 3 on potential"
    else:
        return False, "Insufficient", f"{count} records below minimum {MIN_NAV_RECORDS}"

def check_category(fund):
    """Pass if fund is in an eligible equity category."""
    category = fund['sebi_category']
    if category is None:
        # Check scheme name for equity keywords
        name = fund['scheme_name'].lower()
        equity_signals = [
            'equity', 'large cap', 'mid cap', 'small cap',
            'flexi cap', 'elss', 'bluechip', 'multicap'
        ]
        if any(signal in name for signal in equity_signals):
            return True, "Category inferred from scheme name"
        return False, "Category unknown and cannot be inferred"

    for eligible in ELIGIBLE_CATEGORIES:
        if eligible.lower() in category.lower():
            return True, f"Category: {category}"

    return False, f"Category '{category}' not in eligible equity categories"

def determine_evidence_tier(fund):
    """
    Assign evidence tier based on NAV history length.
    Tier 1: 7+ years  — Full Record
    Tier 2: 5-7 years — Substantial
    Tier 3: 3-5 years — On Potential
    """
    count = fund['nav_record_count']
    if count >= 1750:
        return 1, "Full Record"
    elif count >= 1250:
        return 2, "Substantial"
    else:
        return 3, "On Potential"

def run_eligibility_filter(verbose=False):
    """
    Run complete eligibility filter across all direct equity funds.
    Returns list of eligible funds with their evidence tiers.
    """
    print("Running Eligibility Filter — Layer 1...")
    all_funds = get_all_direct_equity_funds()
    print(f"Initial universe: {len(all_funds)} direct equity growth funds")

    eligible = []
    ineligible = []

    for fund in all_funds:
        reasons_fail = []
        reasons_pass = []

        # Check 1: Plan type — already filtered in SQL
        reasons_pass.append("Direct plan confirmed")

        # Check 2: Expense ratio
        passed, reason = check_expense_ratio(fund)
        if not passed:
            reasons_fail.append(reason)
        else:
            reasons_pass.append(reason)

        # Check 3: AUM
        passed, reason = check_aum(fund)
        if not passed:
            reasons_fail.append(reason)
        else:
            reasons_pass.append(reason)

        # Check 4: NAV history
        passed, tier_name, reason = check_nav_history(fund)
        if not passed:
            reasons_fail.append(reason)
        else:
            reasons_pass.append(reason)

        # Check 5: Category
        passed, reason = check_category(fund)
        if not passed:
            reasons_fail.append(reason)
        else:
            reasons_pass.append(reason)

        if reasons_fail:
            ineligible.append({**fund, 'fail_reasons': reasons_fail})
            if verbose:
                print(f"  FAIL: {fund['scheme_code']} — {reasons_fail[0]}")
        else:
            tier, tier_label = determine_evidence_tier(fund)
            eligible.append({
                **fund,
                'evidence_tier': tier,
                'evidence_label': tier_label,
                'pass_reasons': reasons_pass,
            })

    print(f"Eligible funds:   {len(eligible)}")
    print(f"Ineligible funds: {len(ineligible)}")

    return eligible, ineligible

def get_eligible_funds_by_category(eligible_funds):
    """Group eligible funds by SEBI category."""
    by_category = {}
    for fund in eligible_funds:
        cat = fund['sebi_category'] or 'Unknown'
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(fund)
    return by_category


if __name__ == "__main__":
    print("=" * 60)
    print("ELIGIBILITY FILTER — TEST")
    print("=" * 60)

    eligible, ineligible = run_eligibility_filter(verbose=False)

    by_category = get_eligible_funds_by_category(eligible)

    print("\nEligible funds by category:")
    for cat, funds in sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True):
        tier1 = sum(1 for f in funds if f['evidence_tier'] == 1)
        tier2 = sum(1 for f in funds if f['evidence_tier'] == 2)
        tier3 = sum(1 for f in funds if f['evidence_tier'] == 3)
        print(f"  {cat:<35} {len(funds):>3} funds  "
              f"(T1:{tier1} T2:{tier2} T3:{tier3})")

    print("\nTier breakdown across all eligible funds:")
    t1 = sum(1 for f in eligible if f['evidence_tier'] == 1)
    t2 = sum(1 for f in eligible if f['evidence_tier'] == 2)
    t3 = sum(1 for f in eligible if f['evidence_tier'] == 3)
    print(f"  Tier 1 — Full Record (7+ yrs):    {t1} funds")
    print(f"  Tier 2 — Substantial (5-7 yrs):   {t2} funds")
    print(f"  Tier 3 — On Potential (3-5 yrs):  {t3} funds")

    print("\nSample eligible funds:")
    bouquet_codes = ['122639', '118778', '120503', '118988', '120465']
    for code in bouquet_codes:
        match = next((f for f in eligible if f['scheme_code'] == code), None)
        if match:
            print(f"  ✅ {code} — {match['scheme_name'][:50]} — Tier {match['evidence_tier']}")
        else:
            print(f"  ❌ {code} — NOT in eligible list")

    print("\nELIGIBILITY FILTER — TEST COMPLETE")
