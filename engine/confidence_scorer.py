"""
FUNDGULDASTA — CONFIDENCE SCORING ENGINE (LAYER 4)
====================================================
Computes the bouquet-level confidence score shown to users.
All five factor inputs are visible — never editorially assigned.

Confidence Score Components:
1. Rolling Return Consistency  30% — % of rolling periods beat target
2. Downside Protection         20% — Sortino ratio vs category average
3. Manager Stability           20% — tenure, change frequency, tier
4. Category Tailwind           15% — macro context (explicitly uncertain)
5. Cost Efficiency             15% — weighted expense ratio

Score bands:
80-100: High Confidence
60-79:  Medium-High
40-59:  Medium
20-39:  Low-Medium
Below 20: Low
"""

import psycopg2
import numpy as np
import os
from dotenv import load_dotenv
from engine.rolling_returns import compute_rolling_returns, get_nav_series
from engine.risk_metrics import compute_sortino_ratio
from config.thresholds import (
    CONFIDENCE_HIGH, CONFIDENCE_MEDIUM_HIGH,
    CONFIDENCE_MEDIUM, CONFIDENCE_LOW_MEDIUM,
    RISK_FREE_RATE
)

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'fundguldasta_dev'),
    'user': os.getenv('DB_USER', 'fundguldasta_user'),
}

CATEGORY_SORTINO_BENCHMARKS = {
    'Large Cap':         1.0,
    'Flexi Cap':         0.95,
    'Large & Mid Cap':   0.90,
    'Mid Cap':           0.85,
    'Small Cap':         0.80,
    'Balanced Advantage':1.10,
    'International':     0.90,
    'Sectoral-Technology':0.75,
    'ELSS':              0.90,
    'Default':           0.85,
}

def score_rolling_consistency(fund_weights, horizon_years, target_cagr):
    """
    Factor 1: Rolling Return Consistency (30%)
    What % of all rolling periods did bouquet beat target CAGR?
    """
    all_pcts = []
    period_counts = []

    for scheme_code, weight in fund_weights:
        result = compute_rolling_returns(scheme_code, horizon_years)
        if result is None:
            continue

        pct_key = f'pct_beat_{int(target_cagr)}'
        pct = result.get(pct_key, 0)
        all_pcts.append((pct, weight))
        period_counts.append(result.get('rolling_period_count', 0))

    if not all_pcts:
        return 40, "Insufficient rolling return data", 0, 0

    total_weight = sum(w for _, w in all_pcts)
    weighted_pct = sum(p * w for p, w in all_pcts) / total_weight
    avg_periods = int(np.mean(period_counts)) if period_counts else 0

    score = min(100, max(0, weighted_pct))

    description = (
        f"{weighted_pct:.1f}% of {avg_periods} rolling "
        f"{horizon_years}-yr periods beat {target_cagr}% target"
    )

    return round(score, 2), description, round(weighted_pct, 2), avg_periods

def score_downside_protection(fund_weights):
    """
    Factor 2: Downside Protection (20%)
    Weighted average Sortino ratio vs category benchmarks.
    """
    sortino_scores = []

    for scheme_code, weight in fund_weights:
        nav_series = get_nav_series(scheme_code)
        if nav_series is None:
            continue

        sortino = compute_sortino_ratio(nav_series, years=5)
        if sortino is None:
            continue

        sortino_scores.append((sortino, weight))

    if not sortino_scores:
        return 45, "Sortino data unavailable", None

    total_weight = sum(w for _, w in sortino_scores)
    weighted_sortino = sum(s * w for s, w in sortino_scores) / total_weight

    # Normalise: 0.5=score 30, 1.0=score 60, 1.5=score 85, 2.0=score 100
    score = min(100, max(0, weighted_sortino * 55))

    description = f"Weighted Sortino: {weighted_sortino:.2f}"

    return round(score, 2), description, round(weighted_sortino, 3)

def score_manager_stability(fund_weights, fund_details):
    """
    Factor 3: Manager Stability (20%)
    Average manager tenure, recent change frequency, evidence tiers.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    tenure_scores = []
    tier_penalties = []

    for scheme_code, weight in fund_weights:
        cursor.execute("""
            SELECT manager_name, appointment_date
            FROM fund_managers
            WHERE scheme_code = %s AND is_current = TRUE
            LIMIT 1
        """, (scheme_code,))
        mgr = cursor.fetchone()

        if mgr and mgr[1] and mgr[0] != 'Pending SID enrichment':
            from datetime import datetime
            tenure_years = (datetime.now().date() - mgr[1]).days / 365.25
            tenure_score = min(100, max(20, tenure_years * 8 + 20))
            tenure_scores.append((tenure_score, weight))

        # Check for recent changes
        cursor.execute("""
            SELECT COUNT(*) FROM manager_change_log
            WHERE scheme_code = %s
            AND detected_date >= CURRENT_DATE - INTERVAL '2 years'
        """, (scheme_code,))
        changes = cursor.fetchone()[0]
        if changes > 0:
            tier_penalties.append(10 * changes)

    cursor.close()
    conn.close()

    # Evidence tier adjustment
    tier_penalty = 0
    for fund in fund_details:
        tier = fund.get('tier', 1)
        if tier == 3:
            tier_penalty += 12
        elif tier == 2:
            tier_penalty += 4

    if tenure_scores:
        total_weight = sum(w for _, w in tenure_scores)
        base_score = sum(s * w for s, w in tenure_scores) / total_weight
    else:
        base_score = 45

    change_penalty = sum(tier_penalties)
    final_score = max(10, base_score - tier_penalty - change_penalty)

    description = (
        f"{len(tenure_scores)} of {len(fund_weights)} managers with "
        f"verified tenure data"
    )

    return round(final_score, 2), description

def score_category_tailwind(fund_weights, fund_details):
    """
    Factor 4: Category Structural Tailwind (15%)
    EXPLICITLY UNCERTAIN — macro-based assessment.
    Current assessment May 2026.
    """
    TAILWIND_SCORES = {
        'Large Cap':           62,
        'Flexi Cap':           68,
        'Large & Mid Cap':     60,
        'Multi Cap':           58,
        'Mid Cap':             52,
        'Small Cap':           48,
        'Balanced Advantage':  72,
        'Aggressive Hybrid':   63,
        'ELSS':                60,
        'Focused':             58,
        'Value':               64,
        'Contra':              62,
        'International':       72,
        'Sectoral-Technology': 60,
        'Unknown':             55,
    }

    weighted_scores = []
    for fund in fund_details:
        category = fund.get('category', 'Unknown')
        weight = fund.get('weight', 20)
        cat_score = TAILWIND_SCORES.get(category, 55)
        weighted_scores.append((cat_score, weight))

    if not weighted_scores:
        return 55, "Category data unavailable"

    total_weight = sum(w for _, w in weighted_scores)
    weighted_avg = sum(s * w for s, w in weighted_scores) / total_weight

    description = "Macro category assessment — explicitly uncertain, low weight"

    return round(weighted_avg, 2), description

def score_cost_efficiency(fund_weights, fund_details):
    """
    Factor 5: Cost Efficiency (15%)
    Weighted average expense ratio — lower is better.
    All bouquet funds are direct plans — no trail commission.
    """
    er_scores = []

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    for scheme_code, weight in fund_weights:
        cursor.execute("""
            SELECT expense_ratio FROM fund_metadata
            WHERE scheme_code = %s
        """, (scheme_code,))
        row = cursor.fetchone()
        er = float(row[0]) if row and row[0] else None

        if er is not None:
            # Score: 0.3% = 100, 1.0% = 60, 1.5% = 0
            er_score = max(0, min(100, (1.5 - er) / 1.2 * 100))
            er_scores.append((er, er_score, weight))

    cursor.close()
    conn.close()

    if not er_scores:
        # Use fund_details if DB data unavailable
        er_scores = []
        for fund in fund_details:
            er_str = fund.get('expenseRatio', '0.70%')
            try:
                er = float(er_str.replace('%', ''))
                er_score = max(0, min(100, (1.5 - er) / 1.2 * 100))
                er_scores.append((er, er_score, fund.get('weight', 20)))
            except Exception:
                continue

    if not er_scores:
        return 65, "Expense ratio data unavailable", None

    total_weight = sum(w for _, _, w in er_scores)
    weighted_er = sum(er * w for er, _, w in er_scores) / total_weight
    weighted_score = sum(s * w for _, s, w in er_scores) / total_weight

    description = f"Weighted avg expense ratio: {weighted_er:.2f}% (direct plans only)"

    return round(weighted_score, 2), description, round(weighted_er, 3)

def get_confidence_level(score):
    """Convert numeric score to confidence level label."""
    if score >= CONFIDENCE_HIGH:
        return "High"
    elif score >= CONFIDENCE_MEDIUM_HIGH:
        return "Medium-High"
    elif score >= CONFIDENCE_MEDIUM:
        return "Medium"
    elif score >= CONFIDENCE_LOW_MEDIUM:
        return "Low-Medium"
    else:
        return "Low"

def compute_bouquet_confidence(fund_weights, fund_details, horizon_years, target_cagr):
    """
    Master confidence scoring function.
    Computes all 5 factors and combines with weights.
    Returns complete confidence profile for display in UI.
    """
    FACTOR_WEIGHTS = {
        'rolling_consistency': 30,
        'downside_protection': 20,
        'manager_stability':   20,
        'category_tailwind':   15,
        'cost_efficiency':     15,
    }

    factors = {}

    # Factor 1
    score, desc, pct_beat, periods = score_rolling_consistency(
        fund_weights, horizon_years, target_cagr
    )
    factors['rolling_consistency'] = {
        'score': score,
        'value': desc,
        'weight': FACTOR_WEIGHTS['rolling_consistency'],
    }

    # Factor 2
    score, desc, sortino = score_downside_protection(fund_weights)
    factors['downside_protection'] = {
        'score': score,
        'value': desc,
        'weight': FACTOR_WEIGHTS['downside_protection'],
    }

    # Factor 3
    score, desc = score_manager_stability(fund_weights, fund_details)
    factors['manager_stability'] = {
        'score': score,
        'value': desc,
        'weight': FACTOR_WEIGHTS['manager_stability'],
    }

    # Factor 4
    score, desc = score_category_tailwind(fund_weights, fund_details)
    factors['category_tailwind'] = {
        'score': score,
        'value': desc,
        'weight': FACTOR_WEIGHTS['category_tailwind'],
    }

    # Factor 5
    score, desc, avg_er = score_cost_efficiency(fund_weights, fund_details)
    factors['cost_efficiency'] = {
        'score': score,
        'value': desc,
        'weight': FACTOR_WEIGHTS['cost_efficiency'],
    }

    # Composite score
    composite = sum(
        factors[k]['score'] * FACTOR_WEIGHTS[k] / 100
        for k in FACTOR_WEIGHTS
    )

    level = get_confidence_level(composite)

    return {
        'score': round(composite, 1),
        'level': level,
        'factors': factors,
        'rolling_period_count': periods,
        'target_beaten_pct': pct_beat,
    }


if __name__ == "__main__":
    from config.scheme_codes import ARCHETYPE_FUNDS, VERIFIED_FUNDS

    print("=" * 60)
    print("CONFIDENCE SCORING ENGINE — TEST")
    print("=" * 60)

    for arch_id, fund_weights in ARCHETYPE_FUNDS.items():
        fund_details = [
            {
                'scheme_code': code,
                'weight': weight,
                'category': VERIFIED_FUNDS.get(code, {}).get('category', 'Unknown'),
                'tier': VERIFIED_FUNDS.get(code, {}).get('tier', 1),
            }
            for code, weight in fund_weights
        ]

        print(f"\nArchetype: {arch_id.upper()}")
        result = compute_bouquet_confidence(
            fund_weights, fund_details,
            horizon_years=7, target_cagr=16
        )

        print(f"  Confidence Score: {result['score']}/100 — {result['level']}")
        print(f"  Rolling periods beat target: {result['target_beaten_pct']}%")
        print(f"  Factors:")
        for name, factor in result['factors'].items():
            print(f"    {name:<25} {factor['score']:>6.1f}  {factor['value'][:50]}")
