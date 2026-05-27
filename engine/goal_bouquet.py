"""
FUNDGULDASTA — GOAL BOUQUET ENGINE (SCREEN 2)
=============================================
Builds a single bespoke bouquet for a user's specific CAGR + horizon goal.
Selects from the full 271-fund eligible universe (vs Screen 1's 13 fixed funds).

Algorithm:
1. Load pre-scored funds from computed_metrics for the given horizon
2. Map CAGR target to a category allocation profile (conservative → aggressive)
3. Pre-select top candidates per category
4. Batch-fetch all candidate NAV series in one query (avoids N×300 round-trips)
5. Compute correlation matrix using pre-fetched series
6. Select best 5-fund combination: max score, min correlation, category diversity
7. Assign weights from the allocation profile
8. Compute bouquet-level metrics
9. Cache result in bouquet_cache keyed by (horizon, cagr_bucket)

Why 5 funds: matches the existing archetype structure and is the minimum
for meaningful diversification across 3+ SEBI categories.
"""

import json
import psycopg2
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from itertools import combinations

from config.db import get_db_config
from engine.rolling_returns import compute_rolling_returns, compute_point_to_point_cagr
from engine.bouquet_builder import compute_bouquet_metrics

DB_CONFIG = get_db_config()

# Indian equity funds correlate at 0.85–0.98 (structural, not a bug — see CLAUDE.md)
# Using CORRELATION_HARD_REJECT: only reject funds that are essentially identical
MAX_CORRELATION = 0.93
CACHE_TTL_HOURS = 24

ALLOCATION_PROFILES = {
    'conservative': {
        'Large Cap':          30,
        'Flexi Cap':          25,
        'Balanced Advantage': 20,
        'Mid Cap':            15,
        'Multi Cap':          10,
    },
    'moderate': {
        'Large Cap':          25,
        'Flexi Cap':          20,
        'Mid Cap':            25,
        'Large & Mid Cap':    15,
        'Small Cap':          15,
    },
    'growth': {
        'Flexi Cap':          20,
        'Mid Cap':            30,
        'Large Cap':          15,
        'Small Cap':          25,
        'Multi Cap':          10,
    },
    'aggressive': {
        'Mid Cap':            25,
        'Small Cap':          35,
        'Flexi Cap':          20,
        'Multi Cap':          10,
        'Large Cap':          10,
    },
}

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


def _cache_key(horizon_years: int, target_cagr: float) -> str:
    return f"goal_h{horizon_years}_c{int(round(target_cagr))}"


def _get_from_cache(horizon_years: int, target_cagr: float) -> dict | None:
    """Return cached goal bouquet if fresh (< CACHE_TTL_HOURS old), else None."""
    arch_id = _cache_key(horizon_years, target_cagr)
    cutoff = datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT funds_json, created_at
            FROM bouquet_cache
            WHERE archetype_id = %s
              AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, (arch_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[1] and row[1] > cutoff:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def _store_in_cache(result: dict, horizon_years: int, target_cagr: float) -> None:
    """Store goal bouquet result in bouquet_cache."""
    arch_id = _cache_key(horizon_years, target_cagr)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO bouquet_cache (
                archetype_id, horizon_years, target_cagr, computation_date,
                funds_json, metrics_json, confidence_json, stress_test_json,
                overlap_json, methodology_json, devils_json, comparator_json,
                is_active
            ) VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (archetype_id, horizon_years, computation_date)
            DO UPDATE SET
                funds_json  = EXCLUDED.funds_json,
                metrics_json = EXCLUDED.metrics_json,
                is_active   = TRUE
        """, (
            arch_id, horizon_years, float(round(target_cagr)),
            json.dumps(result),
            json.dumps({}),
            json.dumps({}), json.dumps({}), json.dumps({}),
            json.dumps([]), json.dumps([]), json.dumps({}),
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[goal_bouquet] cache store failed ({arch_id}): {e}")


def _load_scored_funds(horizon_years: int) -> list[dict]:
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
    by_category = {}
    for f in scored_funds:
        cat = f['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(f)

    candidates = []
    seen_codes = set()

    for cat in profile:
        for fund in by_category.get(cat, [])[:top_n]:
            if fund['scheme_code'] not in seen_codes:
                candidates.append(fund)
                seen_codes.add(fund['scheme_code'])

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


def _fetch_nav_batch(codes: list, years: int = 5) -> dict:
    """
    Batch-fetch recent NAV series for all candidate funds in ONE query.
    Returns {scheme_code: pd.Series}. Dramatically faster than per-fund queries.
    """
    if not codes:
        return {}
    cutoff = date.today() - timedelta(days=int(years * 365.25) + 30)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT scheme_code, nav_date, nav_value
            FROM nav_data
            WHERE scheme_code = ANY(%s)
              AND nav_date >= %s
            ORDER BY scheme_code, nav_date ASC
        """, (codes, cutoff))
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        return {}

    nav_map: dict = {}
    for code, nav_date, nav_value in rows:
        code = str(code)
        if code not in nav_map:
            nav_map[code] = ([], [])
        nav_map[code][0].append(nav_date)
        nav_map[code][1].append(float(nav_value))

    result = {}
    for code, (dates, values) in nav_map.items():
        result[code] = pd.Series(values, index=pd.DatetimeIndex(dates))

    return result


def _compute_correlation_from_series(s1: pd.Series, s2: pd.Series) -> float:
    """Compute correlation from pre-fetched NAV series."""
    try:
        r1 = s1.pct_change().dropna()
        r2 = s2.pct_change().dropna()
        common = r1.index.intersection(r2.index)
        if len(common) < 100:
            return 0.7
        return round(float(r1[common].corr(r2[common])), 4)
    except Exception:
        return 0.7


def _build_correlation_matrix(candidates: list, nav_cache: dict) -> dict:
    """Build pairwise correlation matrix using pre-fetched NAV series."""
    codes = [f['scheme_code'] for f in candidates]
    matrix = {}
    for i, c1 in enumerate(codes):
        for c2 in codes[i + 1:]:
            s1 = nav_cache.get(str(c1))
            s2 = nav_cache.get(str(c2))
            if s1 is None or s2 is None:
                corr = 0.7
            else:
                corr = _compute_correlation_from_series(s1, s2)
            matrix[(c1, c2)] = corr
            matrix[(c2, c1)] = corr
    return matrix


def _combination_score(funds: list, corr_matrix: dict, profile: dict) -> float:
    avg_score = np.mean([f['fund_score'] for f in funds])
    codes = [f['scheme_code'] for f in funds]
    pairs = [(c1, c2) for i, c1 in enumerate(codes) for c2 in codes[i + 1:]]
    avg_corr = np.mean([corr_matrix.get((c1, c2), 0.7) for c1, c2 in pairs]) if pairs else 0
    unique_cats = len(set(f['category'] for f in funds))
    diversity_bonus = (unique_cats - 1) * 2
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

    if assigned_weight > 0:
        scale = 100 / (assigned_weight + len(unassigned) * 10) if unassigned else 100 / assigned_weight
        weights = {k: round(v * scale) for k, v in weights.items()}

    residual = 100 - sum(weights.values())
    for code in unassigned:
        weights[code] = residual // len(unassigned) if unassigned else 0

    total = sum(weights.values())
    if total != 100 and funds:
        max_code = max(weights, key=weights.get)
        weights[max_code] += (100 - total)

    return [{'scheme_code': f['scheme_code'], 'weight': weights[f['scheme_code']]} for f in funds]


def build_goal_bouquet(
    horizon_years: int,
    target_cagr: float,
    use_cache: bool = True,
    store_cache: bool = True,
) -> dict | None:
    """
    Build a bespoke bouquet for the user's specific goal.

    use_cache=True  → return cached result if fresh (default for API)
    store_cache=True → persist result to bouquet_cache after computation
    use_cache=False  → force recompute (used by precompute job)

    Returns a dict compatible with the existing bouquet format, or None if
    insufficient scored data exists (bulk_scorer not yet run).
    """
    if use_cache:
        cached = _get_from_cache(horizon_years, target_cagr)
        if cached is not None:
            return cached

    risk_profile = _get_risk_profile(target_cagr)
    profile = ALLOCATION_PROFILES[risk_profile]

    scored = _load_scored_funds(horizon_years)
    if len(scored) < 10:
        return None

    candidates = _select_candidates(scored, profile, top_n=5)
    if len(candidates) < 5:
        return None

    # Batch-fetch all candidate NAV series in ONE query
    codes = [str(f['scheme_code']) for f in candidates]
    nav_cache = _fetch_nav_batch(codes, years=5)

    corr_matrix = _build_correlation_matrix(candidates, nav_cache)

    best_combo = None
    best_score = -999

    for combo in combinations(candidates, 5):
        combo = list(combo)
        if len(set(f['category'] for f in combo)) < 3:
            continue
        if _has_high_correlation(combo, corr_matrix):
            continue
        sc = _combination_score(combo, corr_matrix, profile)
        if sc > best_score:
            best_score = sc
            best_combo = combo

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

    fund_weights_list = _assign_weights(best_combo, profile)
    fund_weight_tuples = [(fw['scheme_code'], fw['weight']) for fw in fund_weights_list]
    metrics = compute_bouquet_metrics(fund_weight_tuples, horizon_years)

    funds_out = []
    for fw in fund_weights_list:
        code = fw['scheme_code']
        fund = next(f for f in best_combo if f['scheme_code'] == code)
        funds_out.append({
            'scheme_code':       code,
            'name':              fund['scheme_name'],
            'amc':               fund['amc_name'],
            'category':          fund['category'],
            'weight':            fw['weight'],
            'fund_score':        round(fund['fund_score'], 1),
            'aum_crores':        fund['aum_crores'],
            'expense_ratio':     fund['expense_ratio'],
            'rolling_mean_cagr': round(fund['rolling_mean'], 1) if fund['rolling_mean'] else None,
        })

    avg_score = round(np.mean([f['fund_score'] for f in best_combo]), 1)
    unique_cats = len(set(f['category'] for f in best_combo))

    result = {
        'type':           'goal_bouquet',
        'risk_profile':   risk_profile,
        'target_cagr':    target_cagr,
        'horizon_years':  horizon_years,
        'fund_count':     len(funds_out),
        'funds':          funds_out,
        'metrics':        {'periods': metrics},
        'avg_fund_score': avg_score,
        'category_count': unique_cats,
        'universe_size':  len(scored),
        'generated_at':   date.today().isoformat(),
    }

    if store_cache:
        _store_in_cache(result, horizon_years, target_cagr)

    return result


if __name__ == "__main__":
    print("Testing Goal Bouquet Engine...")
    result = build_goal_bouquet(horizon_years=7, target_cagr=14, use_cache=False)
    if result:
        print(f"\nGoal Bouquet — 14% CAGR / 7yr:")
        print(f"  Risk profile: {result['risk_profile']}")
        print(f"  Universe: {result['universe_size']} scored funds")
        print(f"  Avg fund score: {result['avg_fund_score']}/100")
        for f in result['funds']:
            print(f"  {f['weight']:>3}% | {f['fund_score']:>4.0f} | {f['category']:<25} | {f['name'][:45]}")
    else:
        print("No result — bulk_scorer may not have completed yet.")
