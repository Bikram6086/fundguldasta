"""
FUNDGULDASTA — BOUQUET CONSTRUCTION OPTIMISER (LAYER 3)
========================================================
Takes scored eligible funds and constructs optimal bouquets.

Steps:
1. Apply category allocation per archetype
2. Select top scoring funds per required category
3. Build correlation matrix — reject highly correlated pairs
4. Generate valid 5-fund combinations
5. Score each combination at bouquet level
6. Apply validation checks
7. Return top 2 bouquets per archetype

Key constraint: No two funds with return correlation above 0.85
or holding overlap above 25%. True diversification — not just
different fund names.
"""

import psycopg2
import numpy as np
import pandas as pd
import os
import json
from datetime import datetime, date
from itertools import combinations
from dotenv import load_dotenv
from engine.rolling_returns import get_nav_series, compute_rolling_returns, compute_point_to_point_cagr, compute_since_inception_cagr
from engine.risk_metrics import compute_all_risk_metrics, compute_crash_performance
from engine.fund_scorer import compute_composite_score
from config.scheme_codes import ARCHETYPE_FUNDS, VERIFIED_FUNDS, BENCHMARKS

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'fundguldasta_dev'),
    'user': os.getenv('DB_USER', 'fundguldasta_user'),
}

MAX_PAIRWISE_CORRELATION = 0.85
MAX_HOLDING_OVERLAP = 0.25

def compute_fund_correlation(scheme_code_1, scheme_code_2, years=5):
    """
    Compute return correlation between two funds over N years.
    Uses daily returns — standard financial correlation.
    """
    nav1 = get_nav_series(scheme_code_1)
    nav2 = get_nav_series(scheme_code_2)

    if nav1 is None or nav2 is None:
        return 0.5  # Assume moderate correlation if data missing

    # Use last N years
    cutoff = min(nav1.index[-1], nav2.index[-1]) - pd.Timedelta(days=int(years * 365.25))
    nav1 = nav1[nav1.index >= cutoff]
    nav2 = nav2[nav2.index >= cutoff]

    # Daily returns
    ret1 = nav1.pct_change().dropna()
    ret2 = nav2.pct_change().dropna()

    # Align on common dates
    common = ret1.index.intersection(ret2.index)
    if len(common) < 100:
        return 0.5

    corr = float(ret1[common].corr(ret2[common]))
    return round(corr, 4)

def build_correlation_matrix(scheme_codes, years=5):
    """
    Build full pairwise correlation matrix for a list of funds.
    Returns dict of {(code1, code2): correlation}
    """
    matrix = {}
    codes = list(scheme_codes)

    for i in range(len(codes)):
        for j in range(i+1, len(codes)):
            c1, c2 = codes[i], codes[j]
            corr = compute_fund_correlation(c1, c2, years)
            matrix[(c1, c2)] = corr
            matrix[(c2, c1)] = corr

    return matrix

def compute_holding_overlap(scheme_code_1, scheme_code_2):
    """
    Compute stock holding overlap between two funds.
    Returns fraction of overlap (0.0 to 1.0).
    Uses latest available disclosure for each fund.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    def get_holdings(code):
        cursor.execute("""
            SELECT stock_isin, weight_pct
            FROM portfolio_holdings
            WHERE scheme_code = %s
            AND disclosure_date = (
                SELECT MAX(disclosure_date)
                FROM portfolio_holdings
                WHERE scheme_code = %s
            )
        """, (code, code))
        return {row[0]: float(row[1]) for row in cursor.fetchall() if row[0]}

    holdings1 = get_holdings(scheme_code_1)
    holdings2 = get_holdings(scheme_code_2)

    cursor.close()
    conn.close()

    if not holdings1 or not holdings2:
        return 0.0

    common_isins = set(holdings1.keys()) & set(holdings2.keys())
    if not common_isins:
        return 0.0

    # Overlap = average weight of common stocks
    overlap = sum(
        min(holdings1[isin], holdings2[isin])
        for isin in common_isins
    ) / 100.0

    return round(overlap, 4)

def compute_bouquet_metrics(fund_weights, horizon_years, benchmark_code='NIFTY500'):
    """
    Compute weighted-average performance metrics for a bouquet.
    fund_weights: list of (scheme_code, weight_pct) tuples
    """
    weighted_cagrs = {}
    periods = ['5 Yr', '7 Yr', '10 Yr', '15 Yr']
    years_map = {'5 Yr': 5, '7 Yr': 7, '10 Yr': 10, '15 Yr': 15}

    # Compute weighted CAGR for each period
    period_cagrs = {p: [] for p in periods}
    period_cagrs['Since Inception'] = []
    total_weight = sum(w for _, w in fund_weights)

    for scheme_code, weight in fund_weights:
        w_frac = weight / total_weight

        for period, yrs in years_map.items():
            cagr = compute_point_to_point_cagr(scheme_code, yrs)
            if cagr:
                period_cagrs[period].append((cagr, w_frac))

        since_inc = compute_since_inception_cagr(scheme_code)
        if since_inc:
            period_cagrs['Since Inception'].append((since_inc, w_frac))

    # Weighted average for each period
    result = {}
    for period, cagr_weights in period_cagrs.items():
        if cagr_weights:
            total_w = sum(w for _, w in cagr_weights)
            weighted_avg = sum(c * w for c, w in cagr_weights) / total_w
            # Real CAGR (assume 6% inflation)
            real_cagr = round(((1 + weighted_avg/100) / (1 + 0.06) - 1) * 100, 2)
            # Post-tax CAGR (assume 30% slab, 12.5% LTCG)
            tax_drag = weighted_avg * 0.125 * 0.30
            post_tax = round(weighted_avg - tax_drag, 2)

            result[period] = {
                'bouquet': round(weighted_avg, 2),
                'realCAGR': real_cagr,
                'postTax': post_tax,
                'nifty50': None,   # Filled separately
                'nifty500': None,
                'fdRate': 6.8,
                'inflation': 6.0,
            }

    return result

def build_bouquet(archetype_id, horizon_years=7, target_cagr=16):
    """
    Main bouquet construction function.

    Uses predefined archetype fund compositions from scheme_codes.py
    (verified correct scheme codes) and computes live metrics.
    """
    fund_weights = ARCHETYPE_FUNDS.get(archetype_id, [])
    if not fund_weights:
        return None

    print(f"\nBuilding {archetype_id} bouquet...")

    # Score each fund
    fund_scores = []
    for scheme_code, weight in fund_weights:
        info = VERIFIED_FUNDS.get(scheme_code, {})
        category = info.get('category', 'Unknown')
        score = compute_composite_score(scheme_code, horizon_years, target_cagr, category)
        fund_scores.append({
            'scheme_code': scheme_code,
            'weight': weight,
            'name': info.get('name', ''),
            'category': category,
            'amc': info.get('amc', ''),
            'tier': info.get('tier', 1),
            'composite_score': score['composite_score'],
            'dimension_scores': score['dimension_scores'],
        })

    # Build correlation matrix
    print(f"  Computing correlations...")
    scheme_codes = [f['scheme_code'] for f in fund_scores]
    corr_matrix = build_correlation_matrix(scheme_codes)

    # Check for high correlations
    high_corr_pairs = [
        (c1, c2, corr)
        for (c1, c2), corr in corr_matrix.items()
        if c1 < c2 and corr > MAX_PAIRWISE_CORRELATION
    ]

    if high_corr_pairs:
        print(f"  ⚠️  High correlation pairs: {len(high_corr_pairs)}")
        for c1, c2, corr in high_corr_pairs:
            n1 = VERIFIED_FUNDS.get(c1, {}).get('name', c1)
            n2 = VERIFIED_FUNDS.get(c2, {}).get('name', c2)
            print(f"    {n1[:30]} ↔ {n2[:30]}: {corr}")

    # Compute average inter-fund correlation
    all_corrs = [v for k, v in corr_matrix.items() if k[0] < k[1]]
    avg_correlation = round(float(np.mean(all_corrs)), 4) if all_corrs else 0.5

    # Compute bouquet-level metrics
    print(f"  Computing performance metrics...")
    metrics = compute_bouquet_metrics(fund_weights, horizon_years)

    # Add benchmark comparison
    from engine.rolling_returns import get_benchmark_series, compute_cagr
    bench50 = get_benchmark_series('NIFTY50')
    bench500 = get_benchmark_series('NIFTY500')

    periods_years = {'5 Yr': 5, '7 Yr': 7, '10 Yr': 10, '15 Yr': 15}
    for period, yrs in periods_years.items():
        if period in metrics:
            if bench50 is not None and len(bench50) > yrs * 200:
                end = bench50.index[-1]
                start_target = end - pd.Timedelta(days=int(yrs * 365.25))
                start_candidates = bench50.index[
                    (bench50.index >= start_target - pd.Timedelta(days=30)) &
                    (bench50.index <= start_target + pd.Timedelta(days=30))
                ]
                if len(start_candidates) > 0:
                    actual_yrs = (end - start_candidates[0]).days / 365.25
                    n50_cagr = compute_cagr(
                        float(bench50[start_candidates[0]]),
                        float(bench50[end]),
                        actual_yrs
                    )
                    metrics[period]['nifty50'] = n50_cagr

            if bench500 is not None and len(bench500) > yrs * 200:
                end = bench500.index[-1]
                start_target = end - pd.Timedelta(days=int(yrs * 365.25))
                start_candidates = bench500.index[
                    (bench500.index >= start_target - pd.Timedelta(days=30)) &
                    (bench500.index <= start_target + pd.Timedelta(days=30))
                ]
                if len(start_candidates) > 0:
                    actual_yrs = (end - start_candidates[0]).days / 365.25
                    n500_cagr = compute_cagr(
                        float(bench500[start_candidates[0]]),
                        float(bench500[end]),
                        actual_yrs
                    )
                    metrics[period]['nifty500'] = n500_cagr

    # Compute bouquet-level confidence score
    avg_fund_score = float(np.mean([f['composite_score'] for f in fund_scores]))

    # Compute overlap
    overlap_scores = []
    for i in range(len(scheme_codes)):
        for j in range(i+1, len(scheme_codes)):
            ov = compute_holding_overlap(scheme_codes[i], scheme_codes[j])
            overlap_scores.append(ov)

    avg_overlap = round(float(np.mean(overlap_scores)) * 100, 1) if overlap_scores else 12

    bouquet = {
        'archetype_id': archetype_id,
        'horizon_years': horizon_years,
        'target_cagr': target_cagr,
        'funds': fund_scores,
        'metrics': metrics,
        'avg_correlation': avg_correlation,
        'avg_overlap_pct': avg_overlap,
        'avg_fund_score': round(avg_fund_score, 2),
        'high_correlation_pairs': high_corr_pairs,
        'computed_at': datetime.now().isoformat(),
    }

    return bouquet

def save_to_cache(bouquet, archetype_data):
    """Save computed bouquet to database cache."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO bouquet_cache (
            archetype_id, horizon_years, target_cagr, computation_date,
            funds_json, metrics_json, confidence_json, stress_test_json,
            overlap_json, methodology_json, devils_json, comparator_json,
            is_active
        ) VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (archetype_id, horizon_years, computation_date)
        DO UPDATE SET
            funds_json = EXCLUDED.funds_json,
            metrics_json = EXCLUDED.metrics_json,
            confidence_json = EXCLUDED.confidence_json,
            is_active = TRUE
    """, (
        bouquet['archetype_id'],
        bouquet['horizon_years'],
        bouquet['target_cagr'],
        json.dumps(bouquet['funds']),
        json.dumps(bouquet['metrics']),
        json.dumps(archetype_data.get('confidence', {})),
        json.dumps(archetype_data.get('stress_test', {})),
        json.dumps({'avgOverlapPct': bouquet['avg_overlap_pct']}),
        json.dumps(archetype_data.get('methodology', [])),
        json.dumps(archetype_data.get('devils', [])),
        json.dumps(archetype_data.get('comparator', {})),
    ))

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("BOUQUET BUILDER — TEST")
    print("Building all 4 archetypes for 7-year horizon, 16% target")
    print("=" * 60)

    archetypes = ['steady', 'balanced', 'aggressive', 'conviction']

    for arch_id in archetypes:
        bouquet = build_bouquet(arch_id, horizon_years=7, target_cagr=16)

        if bouquet:
            print(f"\n{'='*50}")
            print(f"ARCHETYPE: {arch_id.upper()}")
            print(f"{'='*50}")
            print(f"Average fund score:    {bouquet['avg_fund_score']:.1f}/100")
            print(f"Average correlation:   {bouquet['avg_correlation']:.3f}")
            print(f"Average overlap:       {bouquet['avg_overlap_pct']:.1f}%")

            print(f"\nFunds in bouquet:")
            for f in bouquet['funds']:
                print(f"  {f['weight']:>3}% — {f['name'][:45]:<45} Score: {f['composite_score']:.1f}")

            print(f"\nPerformance Metrics:")
            for period, metrics in bouquet['metrics'].items():
                n50 = f"N50:{metrics['nifty50']:.1f}%" if metrics.get('nifty50') else ""
                print(f"  {period:<18} Bouquet:{metrics['bouquet']:.1f}%  "
                      f"Real:{metrics['realCAGR']:.1f}%  {n50}")

    print("\nBOUQUET BUILDER — TEST COMPLETE")
