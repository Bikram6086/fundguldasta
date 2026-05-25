"""
FUNDGULDASTA — FUND REPLACEMENT ENGINE
========================================
Handles user-requested fund substitutions in bouquets.
Provides search, comparison, and impact analysis.

Platform principle: user has full agency. This module computes the honest
trade-off of any substitution without blocking the user's preference.
"""

import psycopg2
import os
from config.db import get_db_config

DB_CONFIG = get_db_config()

from config.scheme_codes import ARCHETYPE_FUNDS, VERIFIED_FUNDS
from config.thresholds import TIER_1_MIN_RECORDS, TIER_2_MIN_RECORDS, TIER_3_MIN_RECORDS

TIER_LABELS = {1: 'Tier 1 (7+ years)', 2: 'Tier 2 (5-7 years)', 3: 'Tier 3 (3-5 years)'}


def _get_db():
    return psycopg2.connect(**DB_CONFIG)


def _get_tier(nav_records: int) -> int:
    if nav_records >= TIER_1_MIN_RECORDS:
        return 1
    elif nav_records >= TIER_2_MIN_RECORDS:
        return 2
    elif nav_records >= TIER_3_MIN_RECORDS:
        return 3
    return 3


def search_eligible_funds(query: str, limit: int = 10) -> list:
    """
    Search the eligible fund universe by name or AMC.
    Returns funds that pass basic eligibility (Direct, Growth, 750+ NAV records).
    """
    conn = _get_db()
    cursor = conn.cursor()
    q = f"%{query.strip()}%"
    cursor.execute("""
        SELECT
            fm.scheme_code,
            fm.scheme_name,
            fm.amc_name,
            fm.sebi_category,
            fm.expense_ratio,
            fm.aum_crores,
            COUNT(nd.nav_date) as nav_count
        FROM fund_metadata fm
        LEFT JOIN nav_data nd ON fm.scheme_code = nd.scheme_code
        WHERE fm.plan_type = 'Direct'
        AND fm.is_active = TRUE
        AND fm.scheme_name ILIKE '%%growth%%'
        AND fm.scheme_name NOT ILIKE '%%idcw%%'
        AND fm.scheme_name NOT ILIKE '%%dividend%%'
        AND fm.scheme_name NOT ILIKE '%%debt%%'
        AND fm.scheme_name NOT ILIKE '%%liquid%%'
        AND fm.scheme_name NOT ILIKE '%%overnight%%'
        AND fm.scheme_name NOT ILIKE '%%gilt%%'
        AND fm.scheme_name NOT ILIKE '%%bond%%'
        AND fm.scheme_name NOT ILIKE '%%arbitrage%%'
        AND (fm.scheme_name ILIKE %s OR fm.amc_name ILIKE %s OR fm.scheme_code::text = %s)
        GROUP BY
            fm.scheme_code, fm.scheme_name, fm.amc_name,
            fm.sebi_category, fm.expense_ratio, fm.aum_crores
        HAVING COUNT(nd.nav_date) >= 750
        ORDER BY COUNT(nd.nav_date) DESC
        LIMIT %s
    """, (q, q, query.strip(), limit))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    results = []
    for row in rows:
        nav_count = row[6]
        tier = _get_tier(nav_count)
        results.append({
            'scheme_code': str(row[0]),
            'name': row[1],
            'amc': row[2],
            'category': row[3],
            'expense_ratio': float(row[4]) if row[4] else None,
            'aum_crores': float(row[5]) if row[5] else None,
            'nav_records': nav_count,
            'tier': tier,
            'tier_label': TIER_LABELS[tier],
        })

    return results


def search_funds_broad(query: str, limit: int = 15) -> list:
    """
    Broad search across all active funds — no plan_type, no NAV-count gate.
    Excludes IDCW/dividend variants and pure debt/liquid/overnight/gilt/arbitrage.
    Returns data quality flags so callers can warn users.
    """
    conn = _get_db()
    cursor = conn.cursor()
    q = f"%{query.strip()}%"
    cursor.execute("""
        SELECT
            fm.scheme_code,
            fm.scheme_name,
            fm.amc_name,
            fm.sebi_category,
            fm.expense_ratio,
            fm.aum_crores,
            fm.plan_type,
            COUNT(nd.nav_date) AS nav_count
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
        AND (fm.scheme_name ILIKE %s OR fm.amc_name ILIKE %s OR fm.scheme_code::text = %s)
        GROUP BY
            fm.scheme_code, fm.scheme_name, fm.amc_name,
            fm.sebi_category, fm.expense_ratio, fm.aum_crores, fm.plan_type
        ORDER BY
            CASE WHEN fm.plan_type = 'Direct' THEN 0 ELSE 1 END,
            COUNT(nd.nav_date) DESC
        LIMIT %s
    """, (q, q, query.strip(), limit))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    results = []
    for row in rows:
        nav_count = int(row[7])
        plan_type = row[6] or 'Regular'
        name_lower = (row[1] or '').lower()
        is_direct = plan_type == 'Direct' or 'direct' in name_lower
        is_growth = 'growth' in name_lower

        if nav_count >= 750:
            data_quality = 'full'
        elif nav_count >= 100:
            data_quality = 'partial'
        else:
            data_quality = 'limited'

        results.append({
            'scheme_code': str(row[0]),
            'name': row[1],
            'amc': row[2],
            'category': row[3] or '',
            'expense_ratio': float(row[4]) if row[4] else None,
            'aum_crores': float(row[5]) if row[5] else None,
            'plan_type': plan_type,
            'is_direct': is_direct,
            'is_growth': is_growth,
            'nav_count': nav_count,
            'data_quality': data_quality,
            'tier': _get_tier(nav_count) if nav_count >= 750 else None,
        })

    return results


def find_replacement_slot(archetype_id: str, user_fund_code: str) -> dict:
    """
    Determine which fund in the archetype to replace with the user's choice.
    Strategy: prefer same SEBI category, else replace lowest-weight fund.
    Returns info about the fund being displaced.
    """
    archetype_funds = ARCHETYPE_FUNDS.get(archetype_id, [])
    if not archetype_funds:
        raise ValueError(f"Unknown archetype: {archetype_id}")

    # Look up user's chosen fund category
    user_category = None
    if user_fund_code in VERIFIED_FUNDS:
        user_category = VERIFIED_FUNDS[user_fund_code].get('category')
    else:
        conn = _get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT sebi_category FROM fund_metadata WHERE scheme_code = %s", (user_fund_code,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            user_category = row[0]

    # Prefer same-category match
    for code, weight in archetype_funds:
        fund_info = VERIFIED_FUNDS.get(code, {})
        if fund_info.get('category') == user_category:
            return {
                'replaced_code': code,
                'replaced_name': fund_info.get('name', code),
                'replaced_weight': weight,
                'replaced_category': fund_info.get('category', 'Unknown'),
                'reason': f'Same category ({user_category}) replacement',
            }

    # Fallback: replace lowest-weight fund
    lowest_code, lowest_weight = min(archetype_funds, key=lambda x: x[1])
    fund_info = VERIFIED_FUNDS.get(lowest_code, {})
    return {
        'replaced_code': lowest_code,
        'replaced_name': fund_info.get('name', lowest_code),
        'replaced_weight': lowest_weight,
        'replaced_category': fund_info.get('category', 'Unknown'),
        'reason': 'Lowest-weight slot (no same-category fund in bouquet)',
    }


def score_single_fund(scheme_code: str, horizon_years: int, target_cagr: float) -> dict:
    """
    Score a single fund using the full 6-dimension engine.
    Wraps engine.fund_scorer.compute_composite_score.
    """
    from engine.fund_scorer import compute_composite_score

    conn = _get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT sebi_category FROM fund_metadata WHERE scheme_code = %s", (str(scheme_code),))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    category = row[0] if row else 'Unknown'

    try:
        result = compute_composite_score(str(scheme_code), horizon_years, target_cagr, category)
        return result
    except Exception as e:
        return {
            'scheme_code': scheme_code,
            'composite_score': None,
            'error': str(e),
            'dimension_scores': {},
        }


def get_fund_rolling_cagr(scheme_code: str, horizon_years: int) -> float | None:
    """
    Get the median rolling CAGR for a fund over the given horizon.
    Used for corpus impact estimation.
    """
    from engine.rolling_returns import get_nav_series
    import numpy as np

    nav = get_nav_series(scheme_code)
    if nav is None or len(nav) < horizon_years * 250:
        return None

    step = 21
    cagrList = []
    n = len(nav)
    window = int(horizon_years * 252)
    for i in range(0, n - window, step):
        start_val = nav.iloc[i]
        end_val = nav.iloc[i + window]
        if start_val > 0:
            cagr = (pow(end_val / start_val, 1 / horizon_years) - 1) * 100
            cagrList.append(cagr)

    return round(float(np.median(cagrList)), 2) if cagrList else None


def compute_replacement_impact(
    replaced_code: str,
    replacement_code: str,
    allocation_weight: int,
    horizon_years: int,
    lumpsum: float = 1_000_000,
) -> dict:
    """
    Estimate the corpus impact of swapping one fund for another at a given weight.

    Uses median rolling CAGR for each fund. The impact on total bouquet CAGR
    is scaled by the fund's allocation weight.
    """
    orig_cagr = get_fund_rolling_cagr(replaced_code, horizon_years)
    repl_cagr = get_fund_rolling_cagr(replacement_code, horizon_years)

    if orig_cagr is None or repl_cagr is None:
        return {
            'estimated_cagr_delta': None,
            'estimated_corpus_delta': None,
            'message': 'Insufficient NAV history for one or both funds — impact cannot be estimated.',
            'orig_median_cagr': orig_cagr,
            'repl_median_cagr': repl_cagr,
        }

    # Bouquet CAGR delta = weight% × individual CAGR delta
    individual_delta = repl_cagr - orig_cagr
    bouquet_cagr_delta = round(individual_delta * (allocation_weight / 100), 2)

    # Use a representative bouquet CAGR of 16% as baseline
    baseline_cagr = 16.0
    modified_cagr = baseline_cagr + bouquet_cagr_delta

    corpus_original = lumpsum * pow(1 + baseline_cagr / 100, horizon_years)
    corpus_modified = lumpsum * pow(1 + modified_cagr / 100, horizon_years)
    corpus_delta = corpus_modified - corpus_original

    return {
        'estimated_cagr_delta': bouquet_cagr_delta,
        'estimated_corpus_delta': round(corpus_delta),
        'orig_median_cagr': orig_cagr,
        'repl_median_cagr': repl_cagr,
        'individual_cagr_delta': round(individual_delta, 2),
        'allocation_weight': allocation_weight,
        'horizon_years': horizon_years,
        'lumpsum': lumpsum,
        'message': (
            f"Replacing {replaced_code} ({orig_cagr:.1f}% median rolling CAGR) with "
            f"{replacement_code} ({repl_cagr:.1f}%) at {allocation_weight}% weight "
            f"{'adds' if bouquet_cagr_delta >= 0 else 'reduces'} ~{abs(bouquet_cagr_delta):.2f}% "
            f"to bouquet CAGR. Estimated corpus impact on ₹10L: "
            f"{'+'if corpus_delta >= 0 else ''}₹{abs(corpus_delta)/100000:.1f}L."
        ),
    }
