"""
FUNDGULDASTA — INDIVIDUAL FUND SCORING ENGINE (LAYER 2)
========================================================
Scores every eligible fund across 6 dimensions.
All scores are category-relative — large cap vs large cap only.
Output: composite score 0-100 per fund.

6 Dimensions:
1. Return Consistency    25% — rolling CAGR vs target, consistency
2. Risk-Adjusted Quality 20% — Sortino, Sharpe, Calmar
3. Downside Behaviour    20% — crash performance vs category peers
4. Manager Stability     15% — tenure, track record
5. Portfolio Quality     10% — concentration, turnover
6. Forward Context       10% — valuation, macro (explicitly uncertain)
"""

import psycopg2
import numpy as np
import os
from datetime import datetime
from dotenv import load_dotenv
from engine.rolling_returns import (
    compute_rolling_returns,
    compute_point_to_point_cagr,
    get_nav_series
)
from engine.risk_metrics import (
    compute_sortino_ratio,
    compute_sharpe_ratio,
    compute_calmar_ratio,
    compute_crash_performance,
    compute_capture_ratios
)

from config.db import get_db_config
DB_CONFIG = get_db_config()

# Scoring weights — must sum to 100
WEIGHTS = {
    'return_consistency':   25,
    'risk_adjusted':        20,
    'downside_behaviour':   20,
    'manager_stability':    15,
    'portfolio_quality':    10,
    'forward_context':      10,
}

def score_return_consistency(scheme_code, horizon_years, target_cagr, proxy_code=None):
    """
    Score based on rolling return consistency.
    How reliably has this fund delivered returns near target?

    Inputs:
    - % of rolling periods beating target CAGR (40%)
    - % of rolling periods beating benchmark (40%)
    - Standard deviation of rolling returns (20% — lower is better)

    proxy_code: regular plan scheme_code used when direct plan lacks history
    """
    result = compute_rolling_returns(scheme_code, horizon_years, proxy_code=proxy_code)
    if result is None:
        return 30, {}  # Default score if insufficient data

    pct_beat_target = result.get(f'pct_beat_{int(target_cagr)}', 0)
    pct_beat_benchmark = result.get('pct_beat_benchmark') or 50
    std_dev = result.get('cagr_std', 5)

    # Normalise std dev — lower is better
    # Typical range 1-8%, score 100 for <2%, 0 for >8%
    std_score = max(0, min(100, (8 - std_dev) / 6 * 100))

    raw_score = (
        pct_beat_target * 0.40 +
        pct_beat_benchmark * 0.40 +
        std_score * 0.20
    )

    return round(raw_score, 2), {
        'pct_beat_target': pct_beat_target,
        'pct_beat_benchmark': pct_beat_benchmark,
        'std_dev': std_dev,
        'rolling_periods': result.get('rolling_period_count', 0),
        'mean_cagr': result.get('cagr_mean', 0),
    }

def score_risk_adjusted(scheme_code):
    """
    Score based on risk-adjusted return metrics.
    Sortino most important — measures downside risk only.
    """
    nav_series = get_nav_series(scheme_code)
    if nav_series is None:
        return 30, {}

    sortino = compute_sortino_ratio(nav_series, years=5) or 0
    sharpe = compute_sharpe_ratio(nav_series, years=5) or 0
    calmar = compute_calmar_ratio(nav_series, years=3) or 0

    # Normalise each metric to 0-100
    # Sortino: 0=poor, 1=good, 2=excellent
    sortino_score = min(100, max(0, sortino * 50))

    # Sharpe: 0=poor, 0.5=good, 1.5=excellent
    sharpe_score = min(100, max(0, sharpe * 67))

    # Calmar: 0=poor, 0.5=good, 2=excellent
    calmar_score = min(100, max(0, calmar * 50))

    raw_score = (sortino_score * 0.50 + sharpe_score * 0.30 + calmar_score * 0.20)

    return round(raw_score, 2), {
        'sortino': sortino,
        'sharpe': sharpe,
        'calmar': calmar,
    }

def score_downside_behaviour(scheme_code):
    """
    Score based on crash period performance.
    How much did fund fall vs how quickly did it recover?
    """
    nav_series = get_nav_series(scheme_code)
    if nav_series is None:
        return 30, {}

    crashes = compute_crash_performance(nav_series)
    if not crashes:
        return 40, {'note': 'Fund did not exist during major crash periods'}

    scores = []
    for crash in crashes:
        fall = abs(crash['peak_fall_pct'])
        recovery = crash['recovery_months'] or 36

        # Score fall: 0% fall = 100, 60%+ fall = 0
        fall_score = max(0, min(100, (60 - fall) / 60 * 100))

        # Score recovery: 0 months = 100, 36+ months = 0
        recovery_score = max(0, min(100, (36 - recovery) / 36 * 100))

        crash_score = fall_score * 0.6 + recovery_score * 0.4
        scores.append(crash_score)

    raw_score = float(np.mean(scores)) if scores else 40

    return round(raw_score, 2), {
        'crash_periods_analysed': len(crashes),
        'crashes': crashes,
    }

def score_manager_stability(scheme_code):
    """
    Score based on manager tenure and track record.
    Uses fund_managers table — updated by automated pipeline.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT manager_name, appointment_date, total_experience_years
        FROM fund_managers
        WHERE scheme_code = %s AND is_current = TRUE
        ORDER BY appointment_date ASC LIMIT 1
    """, (scheme_code,))
    manager = cursor.fetchone()
    cursor.close()
    conn.close()

    if manager is None:
        return 40, {'note': 'Manager data pending verification'}

    manager_name, appointment_date, experience_years = manager

    if manager_name == 'Pending SID enrichment':
        return 40, {'note': 'Manager data pending SID enrichment'}

    # Score tenure at current fund
    tenure_years = 0
    if appointment_date:
        tenure_years = (datetime.now().date() - appointment_date).days / 365.25

    # Tenure score: 0 years = 20, 5 years = 70, 10+ years = 100
    tenure_score = min(100, max(20, tenure_years * 8 + 20))

    # Experience score: 5 years = 40, 10 years = 70, 15+ years = 100
    exp = experience_years or 5
    exp_score = min(100, max(40, exp * 4 + 20))

    raw_score = tenure_score * 0.60 + exp_score * 0.40

    return round(raw_score, 2), {
        'manager_name': manager_name,
        'tenure_years': round(tenure_years, 1),
        'experience_years': experience_years,
    }

def score_portfolio_quality(scheme_code):
    """
    Score based on portfolio construction quality.
    Uses latest holdings data from portfolio_holdings table.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Get latest disclosure date for this fund
    cursor.execute("""
        SELECT MAX(disclosure_date) FROM portfolio_holdings
        WHERE scheme_code = %s
    """, (scheme_code,))
    latest = cursor.fetchone()[0]

    if latest is None:
        cursor.close()
        conn.close()
        return 50, {'note': 'Holdings data not yet available'}

    # Get holdings for latest disclosure
    cursor.execute("""
        SELECT stock_name, weight_pct
        FROM portfolio_holdings
        WHERE scheme_code = %s AND disclosure_date = %s
        ORDER BY weight_pct DESC
    """, (scheme_code, latest))
    holdings = cursor.fetchall()
    cursor.close()
    conn.close()

    if not holdings:
        return 50, {'note': 'No holdings data found'}

    weights = [float(h[1]) for h in holdings]
    total_holdings = len(holdings)

    # Top 10 concentration
    top10_weight = sum(sorted(weights, reverse=True)[:10])

    # Concentration score: 100% in top 10 = 0, 30% = 100
    concentration_score = max(0, min(100, (100 - top10_weight) * 1.43))

    # Diversification score: 10 holdings = 20, 50+ holdings = 100
    diversification_score = min(100, max(20, total_holdings * 1.6 + 20))

    raw_score = concentration_score * 0.60 + diversification_score * 0.40

    return round(raw_score, 2), {
        'total_holdings': total_holdings,
        'top10_concentration': round(top10_weight, 2),
        'disclosure_date': str(latest),
    }

def score_forward_context(scheme_code, category):
    """
    Score based on category-level macro context.
    EXPLICITLY UNCERTAIN — labelled as such in UI.
    Uses simple heuristics — not predictions.

    Current assessment (May 2026):
    - Large Cap: Moderate — fairly valued, stable
    - Mid Cap: Cautious — extended valuation cycle
    - Small Cap: Cautious — elevated valuations
    - Flexi Cap: Positive — manager flexibility
    - Balanced Advantage: Positive — defensive in expensive market
    - International: Positive — diversification benefit
    """
    CONTEXT_SCORES = {
        'Large Cap':        65,
        'Flexi Cap':        70,
        'Large & Mid Cap':  62,
        'Multi Cap':        60,
        'Mid Cap':          55,
        'Small Cap':        50,
        'Balanced Advantage': 72,
        'Aggressive Hybrid':  65,
        'ELSS':             62,
        'Focused':          60,
        'Value':            65,
        'Contra':           63,
        'International':    70,
        'Sectoral-Technology': 62,
    }

    score = CONTEXT_SCORES.get(category, 58)

    return score, {
        'category': category,
        'note': 'Category-level assessment only. Explicitly uncertain. Low weight in composite score.',
    }

def compute_composite_score(scheme_code, horizon_years, target_cagr, category, proxy_code=None):
    """
    Master scoring function.
    Computes all 6 dimension scores and combines with weights.
    Returns composite score 0-100 with full breakdown.

    proxy_code: regular plan scheme_code; used only for return_consistency
                (rolling returns) when direct plan lacks long-horizon history.
                Other 5 dimensions use direct plan data only.
    """
    scores = {}
    details = {}

    s, d = score_return_consistency(scheme_code, horizon_years, target_cagr, proxy_code=proxy_code)
    scores['return_consistency'] = s
    details['return_consistency'] = d

    s, d = score_risk_adjusted(scheme_code)
    scores['risk_adjusted'] = s
    details['risk_adjusted'] = d

    s, d = score_downside_behaviour(scheme_code)
    scores['downside_behaviour'] = s
    details['downside_behaviour'] = d

    s, d = score_manager_stability(scheme_code)
    scores['manager_stability'] = s
    details['manager_stability'] = d

    s, d = score_portfolio_quality(scheme_code)
    scores['portfolio_quality'] = s
    details['portfolio_quality'] = d

    s, d = score_forward_context(scheme_code, category)
    scores['forward_context'] = s
    details['forward_context'] = d

    # Weighted composite
    composite = sum(
        scores[dim] * WEIGHTS[dim] / 100
        for dim in WEIGHTS
    )

    return {
        'scheme_code':      scheme_code,
        'composite_score':  round(composite, 2),
        'dimension_scores': scores,
        'details':          details,
        'weights':          WEIGHTS,
    }


if __name__ == "__main__":
    from config.scheme_codes import VERIFIED_FUNDS, ARCHETYPE_FUNDS

    print("=" * 60)
    print("FUND SCORING ENGINE — TEST")
    print("Scoring all bouquet funds for 7-year horizon, 16% target")
    print("=" * 60)

    TEST_HORIZON = 7
    TEST_TARGET = 16

    results = []
    for scheme_code, info in VERIFIED_FUNDS.items():
        print(f"\nScoring {info['name'][:45]}...")
        score = compute_composite_score(
            scheme_code,
            TEST_HORIZON,
            TEST_TARGET,
            info['category']
        )
        results.append((scheme_code, info['name'], info['category'], score))

    print("\n" + "=" * 60)
    print("SCORING RESULTS — Sorted by composite score")
    print("=" * 60)
    results.sort(key=lambda x: x[3]['composite_score'], reverse=True)

    for code, name, category, score in results:
        comp = score['composite_score']
        dims = score['dimension_scores']
        print(f"\n{name[:48]}")
        print(f"  Composite Score: {comp:.1f}/100")
        print(f"  Return Consistency: {dims['return_consistency']:.1f}  "
              f"Risk-Adjusted: {dims['risk_adjusted']:.1f}  "
              f"Downside: {dims['downside_behaviour']:.1f}")
        print(f"  Manager Stability: {dims['manager_stability']:.1f}  "
              f"Portfolio: {dims['portfolio_quality']:.1f}  "
              f"Forward: {dims['forward_context']:.1f}")

    print("\nFUND SCORING ENGINE — TEST COMPLETE")
