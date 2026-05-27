"""
FUNDGULDASTA — GOAL BOUQUET ENGINE (SCREEN 2)
=============================================
Builds a single bespoke bouquet for a user's specific CAGR + horizon goal.
Selects from the full 271-fund eligible universe (vs Screen 1's 13 fixed funds).

Algorithm:
1. Load pre-scored funds from computed_metrics for the given horizon
2. Map CAGR target to a category allocation profile (conservative → aggressive)
3. Pre-select top candidates per category
4. Compute correlation matrix for candidates only (~30 funds, not 271)
5. Select best 5-fund combination: max score, min correlation, category diversity
6. Assign weights from the allocation profile
7. Compute bouquet-level metrics

Why 5 funds: matches the existing archetype structure and is the minimum
for meaningful diversification across 3+ SEBI categories.
"""

import psycopg2
import numpy as np
import pandas as pd
from datetime import date
from itertools import combinations

from config.db import get_db_config
from engine.rolling_returns import get_nav_series, compute_rolling_returns, compute_point_to_point_cagr
from engine.bouquet_builder import compute_bouquet_metrics

DB_CONFIG = get_db_config()

# Maximum pairwise correlation allowed in a bouquet
MAX_CORRELATION = 0.85

# Category allocation profiles keyed by risk level
# Each profile defines category → target weight (%)
# Profile is used to: (a) weight categories during selection, (b) assign fund weights
ALLOCATION_PROFILES = {
    'conservative': {   # CAGR target ≤ 13%
        'Large Cap':          30,
        'Flexi Cap':          25,
        'Balanced Advantage': 20,
        'Mid Cap':            15,
        'Multi Cap':          10,
    },
    'moderate': {       # CAGR target 14–16%
        'Large Cap':          25,
        'Flexi Cap':          20,
        'Mid Cap':            25,
        'Large & Mid Cap':    15,
        'Small Cap':          15,
    },
    'growth': {         # CAGR target 17–19%
        'Flexi Cap':          20,
        'Mid Cap':            30,
        'Large Cap':          15,
        'Small Cap':          25,
        'Multi Cap':          10,
    },
    'aggressive': {     # CAGR target 20%+
        'Mid Cap':            25,
        'Small Cap':          35,
        'Flexi Cap':          20,
        'Multi Cap':          10,
        'Large Cap':          10,
    },
}

# Fallback category order when a profile category has no qualifying fund
FALLBACK_CATEGORIES = [
    'Flexi Cap', 'Large Cap', 'Mid Cap', 'Small Cap', 'Multi Cap',
    'Large & Mid Cap', 'ELSS', 'Focused', 'Value', 'Contra',
    'Balanced Advantage', 'Aggressive Hybrid',
]


def _get_risk_profile(target_cagr: float) -> str:
    if target_cagr <= 13:
        return 'conservative'
    elif target_cagr <= 16:
        return 'moderate'
    elif target_cagr <= 19:
        return 'growth'
    else:
        return 'aggressive'


def _load_scored_funds(horizon_years: int) -> list[dict]:
    """
    Load all funds scored for this horizon from computed_metrics.
    Returns list sorted by fund_score DESC.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (cm.scheme_code)
            cm.scheme_code,
            cm.fund_score,
            cm.return_consistency_score,
            cm.risk_adjusted_score,
            cm.downside_score,
            cm.manager_score,
            cm.portfolio_quality_score,
            cm.forward_context_score,
            cm.rolling_cagr_mean,
            cm.rolling_cagr_std,
            cm.max_drawdown_pct,
            cm.rolling_period_count,
            fm.scheme_name,
            fm.amc_name,
            fm.sebi_category,
            fm.aum_crores,
            fm.expense_ratio
        FROM computed_metrics cm
        JOIN fund_metadata fm ON cm.scheme_code = fm.scheme_code
        WHERE cm.horizon_years = %s
          AND cm.fund_score IS NOT NULL
        ORDER BY cm.scheme_code, cm.computation_date DESC
    """, (horizon_years,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    funds = []
    for r in rows:
        funds.append({
            'scheme_code':     r[0],
            'fund_score':      float(r[1]) if r[1] else 0,
            'dim_return_cons': float(r[2]) if r[2] else 0,
            'dim_risk_adj':    float(r[3]) if r[3] else 0,
            'dim_downside':    float(r[4]) if r[4] else 0,
            'dim_manager':     float(r[5]) if r[5] else 0,
            'dim_port_qual':   float(r[6]) if r[6] else 0,
            'dim_fwd_context': float(r[7]) if r[7] else 0,
            'rolling_mean':    float(r[8]) if r[8] else None,
            'rolling_std':     float(r[9]) if r[9] else None,
            'max_drawdown':    float(r[10]) if r[10] else None,
            'rolling_periods': r[11],
            'scheme_name':     r[12],
            'amc_name':        r[13],
            'category':        r[14],
            'aum_crores':      float(r[15]) if r[15] else None,
            'expense_ratio':   float(r[16]) if r[16] else None,
        })

    funds.sort(key=lambda x: x['fund_score'], reverse=True)
    return funds


def _select_candidates(scored_funds: list, profile: dict, top_n: int = 5) -> list:
    """
    Select top-N candidates per category from the allocation profile.
    Returns a flat list of candidate funds.
    """
    by_category = {}
    for f in scored_funds:
        cat = f['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(f)

    candidates = []
    seen_codes = set()

    # First pass: pick top-N from each profile category
    for cat in profile:
        for fund in by_category.get(cat, [])[:top_n]:
            if fund['scheme_code'] not in seen_codes:
                candidates.append(fund)
                seen_codes.add(fund['scheme_code'])

    # Second pass: if we have < 15 candidates, fill from fallback categories
    if len(candidates) < 15:
        for cat in FALLBACK_CATEGORIES:
            if cat in profile:
                continue
            for fund in by_category.get(cat, [])[:3]:
                if fund['scheme_code'] not in seen_codes:
                    candidates.append(fund)
                    seen_codes.add(fund['scheme_code'])
            if len(candidates) >= 20:
                break

    return candidates


def _compute_correlation(code1: str, code2: str, years: int = 5) -> float:
    """Return pairwise return correlation (last N years). Defaults to 0.7 on error."""
    try:
        nav1 = get_nav_series(code1)
        nav2 = get_nav_series(code2)
        if nav1 is None or nav2 is None:
            return 0.7
        cutoff = min(nav1.index[-1], nav2.index[-1]) - pd.Timedelta(days=int(years * 365.25))
        nav1 = nav1[nav1.index >= cutoff]
        nav2 = nav2[nav2.index >= cutoff]
        ret1 = nav1.pct_change().dropna()
        ret2 = nav2.pct_change().dropna()
        common = ret1.index.intersection(ret2.index)
        if len(common) < 100:
            return 0.7
        return round(float(ret1[common].corr(ret2[common])), 4)
    except Exception:
        return 0.7


def _build_correlation_matrix(candidates: list) -> dict:
    """Build pairwise correlation matrix for candidate funds."""
    codes = [f['scheme_code'] for f in candidates]
    matrix = {}
    for i, c1 in enumerate(codes):
        for c2 in codes[i + 1:]:
            corr = _compute_correlation(c1, c2)
            matrix[(c1, c2)] = corr
            matrix[(c2, c1)] = corr
    return matrix


def _combination_score(funds: list, corr_matrix: dict, profile: dict) -> float:
    """
    Score a fund combination.
    Penalises high correlation and rewards category diversity.
    """
    # Average fund score
    avg_score = np.mean([f['fund_score'] for f in funds])

    # Correlation penalty: average pairwise correlation
    codes = [f['scheme_code'] for f in funds]
    pairs = [(c1, c2) for i, c1 in enumerate(codes) for c2 in codes[i + 1:]]
    avg_corr = np.mean([corr_matrix.get((c1, c2), 0.7) for c1, c2 in pairs]) if pairs else 0

    # Category diversity bonus: more unique categories = better
    unique_cats = len(set(f['category'] for f in funds))
    diversity_bonus = (unique_cats - 1) * 2

    # Profile alignment: how many funds match the target allocation profile
    profile_cats = set(profile.keys())
    aligned = sum(1 for f in funds if f['category'] in profile_cats)
    alignment_bonus = aligned * 1.5

    return avg_score - (avg_corr * 15) + diversity_bonus + alignment_bonus


def _has_high_correlation(funds: list, corr_matrix: dict) -> bool:
    codes = [f['scheme_code'] for f in funds]
    for i, c1 in enumerate(codes):
        for c2 in codes[i + 1:]:
            if corr_matrix.get((c1, c2), 0) > MAX_CORRELATION:
                return True
    return False


def _assign_weights(funds: list, profile: dict) -> list:
    """
    Assign weights to selected funds based on allocation profile.
    Funds in profile categories get their target weights; others share residual.
    """
    weights = {}
    assigned_weight = 0
    unassigned = []

    for f in funds:
        cat = f['category']
        if cat in profile:
            weights[f['scheme_code']] = profile[cat]
            assigned_weight += profile[cat]
        else:
            unassigned.append(f['scheme_code'])

    # If total assigned > 100 (multiple funds in same category), normalise
    if assigned_weight > 0:
        scale = 100 / (assigned_weight + len(unassigned) * 10) if unassigned else 100 / assigned_weight
        weights = {k: round(v * scale) for k, v in weights.items()}

    # Give residual to unassigned funds
    residual = 100 - sum(weights.values())
    for code in unassigned:
        weights[code] = residual // len(unassigned) if unassigned else 0

    # Final normalise to exactly 100
    total = sum(weights.values())
    if total != 100 and funds:
        # Add/subtract from highest-weighted fund
        max_code = max(weights, key=weights.get)
        weights[max_code] += (100 - total)

    return [{'scheme_code': f['scheme_code'], 'weight': weights[f['scheme_code']]} for f in funds]


def build_goal_bouquet(horizon_years: int, target_cagr: float) -> dict | None:
    """
    Build a bespoke bouquet for the user's specific goal.

    Returns a dict compatible with the existing bouquet format, or None if
    insufficient scored data exists (bulk_scorer not yet run).
    """
    # Map CAGR to risk profile
    risk_profile = _get_risk_profile(target_cagr)
    profile = ALLOCATION_PROFILES[risk_profile]

    # Load all scored funds for this horizon
    scored = _load_scored_funds(horizon_years)
    if len(scored) < 10:
        return None  # Not enough scored data — bulk_scorer hasn't run yet

    # Pre-select candidates (~25-30 funds) — limits correlation matrix size
    candidates = _select_candidates(scored, profile, top_n=5)
    if len(candidates) < 5:
        return None

    # Build correlation matrix for candidates only
    corr_matrix = _build_correlation_matrix(candidates)

    # Find best 5-fund combination
    best_combo = None
    best_score = -999

    for combo in combinations(candidates, 5):
        combo = list(combo)
        # Must have at least 3 distinct categories
        if len(set(f['category'] for f in combo)) < 3:
            continue
        # No highly correlated pairs
        if _has_high_correlation(combo, corr_matrix):
            continue
        sc = _combination_score(combo, corr_matrix, profile)
        if sc > best_score:
            best_score = sc
            best_combo = combo

    # Fallback: if no valid 5-fund combo, relax category constraint
    if not best_combo:
        for combo in combinations(candidates, 5):
            combo = list(combo)
            if _has_high_correlation(combo, corr_matrix):
                continue
            sc = _combination_score(combo, corr_matrix, profile)
            if sc > best_score:
                best_score = sc
                best_combo = combo

    if not best_combo:
        return None

    # Assign weights
    fund_weights_list = _assign_weights(best_combo, profile)

    # Compute bouquet metrics
    fund_weight_tuples = [(fw['scheme_code'], fw['weight']) for fw in fund_weights_list]
    metrics = compute_bouquet_metrics(fund_weight_tuples, horizon_years)

    # Enrich fund data
    funds_out = []
    for fw in fund_weights_list:
        code = fw['scheme_code']
        fund = next(f for f in best_combo if f['scheme_code'] == code)
        funds_out.append({
            'scheme_code':   code,
            'name':          fund['scheme_name'],
            'amc':           fund['amc_name'],
            'category':      fund['category'],
            'weight':        fw['weight'],
            'fund_score':    round(fund['fund_score'], 1),
            'aum_crores':    fund['aum_crores'],
            'expense_ratio': fund['expense_ratio'],
            'rolling_mean_cagr': round(fund['rolling_mean'], 1) if fund['rolling_mean'] else None,
        })

    avg_score = round(np.mean([f['fund_score'] for f in best_combo]), 1)
    unique_cats = len(set(f['category'] for f in best_combo))

    return {
        'type':            'goal_bouquet',
        'risk_profile':    risk_profile,
        'target_cagr':     target_cagr,
        'horizon_years':   horizon_years,
        'fund_count':      len(funds_out),
        'funds':           funds_out,
        'metrics':         {'periods': metrics},
        'avg_fund_score':  avg_score,
        'category_count':  unique_cats,
        'universe_size':   len(scored),
        'generated_at':    date.today().isoformat(),
    }


if __name__ == "__main__":
    print("Testing Goal Bouquet Engine...")
    result = build_goal_bouquet(horizon_years=7, target_cagr=14)
    if result:
        print(f"\nGoal Bouquet — 14% CAGR / 7yr:")
        print(f"  Risk profile: {result['risk_profile']}")
        print(f"  Universe: {result['universe_size']} scored funds")
        print(f"  Avg fund score: {result['avg_fund_score']}/100")
        for f in result['funds']:
            print(f"  {f['weight']:>3}% | {f['fund_score']:>4.0f} | {f['category']:<25} | {f['name'][:45]}")
    else:
        print("No result — bulk_scorer may not have completed yet.")
