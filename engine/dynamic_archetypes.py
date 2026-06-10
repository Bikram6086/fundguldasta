"""
FUNDGULDASTA — DYNAMIC ARCHETYPE BOUQUET BUILDER
=================================================
Replaces the hardcoded 13-fund archetype compositions with funds
algorithmically selected from the full 271-fund scored universe.

Each archetype defines a category allocation profile and dimension
boosts. The engine queries computed_metrics, applies archetype-
specific scoring, runs correlation-aware selection, and returns the
same dict structure as legacy build_bouquet() — fully precompute-
compatible with no frontend changes required.
"""

import psycopg2
import numpy as np
import pandas as pd
from datetime import date, timedelta
from itertools import combinations

from config.db import get_db_config
from engine.bouquet_builder import compute_bouquet_metrics, compute_holding_overlap

DB_CONFIG = get_db_config()

MAX_CORRELATION = 0.92
TOP_N_PER_CATEGORY = 5

# SEBI categories treated as equity (exclude Equity Savings — too conservative at 10-35% eq)
EQUITY_CATEGORIES = frozenset({
    'Large Cap', 'Mid Cap', 'Small Cap', 'Flexi Cap', 'Multi Cap',
    'Large & Mid Cap', 'ELSS', 'Focused', 'Value', 'Contra',
    'Balanced Advantage', 'Aggressive Hybrid',
})

ARCHETYPE_PROFILES = {
    'steady': {
        # Low-medium risk. Large cap stability + flexi flexibility + hybrid buffer.
        'category_weights': {
            'Large Cap':          30,
            'Flexi Cap':          25,
            'Balanced Advantage': 20,
            'Mid Cap':            15,
            'ELSS':               10,
            'Value':              10,
            'Large & Mid Cap':    10,
        },
        # Downside protection and risk-adjusted quality weighted higher
        'dim_boosts': {
            'dim_downside':    1.8,
            'dim_risk_adj':    1.4,
            'dim_return_cons': 1.0,
            'dim_manager':     1.0,
        },
        'exclude_categories': {'Small Cap', 'Focused'},
        # Combo must contain at least one fund from each required category
        'required_categories': [{'Large Cap'}, {'Flexi Cap', 'Multi Cap', 'Large & Mid Cap'}],
    },
    'balanced': {
        # Medium risk. Diversified across large/mid/small/hybrid.
        'category_weights': {
            'Large Cap':         20,
            'Flexi Cap':         20,
            'Mid Cap':           25,
            'Small Cap':         20,
            'Aggressive Hybrid': 15,
            'Multi Cap':         15,
        },
        'dim_boosts': {
            'dim_return_cons': 1.2,
            'dim_risk_adj':    1.1,
            'dim_downside':    1.0,
        },
        'exclude_categories': set(),
        'required_categories': [{'Mid Cap'}, {'Small Cap'}],
    },
    'aggressive': {
        # Medium-high risk. Mid/small cap dominant, return maximising.
        'category_weights': {
            'Mid Cap':         35,
            'Small Cap':       35,
            'Flexi Cap':       20,
            'Multi Cap':       10,
            'Large & Mid Cap': 10,
        },
        'dim_boosts': {
            'dim_return_cons': 1.8,
            'dim_risk_adj':    1.0,
            'dim_downside':    0.6,
        },
        'exclude_categories': {'Balanced Advantage', 'Equity Savings'},
        'required_categories': [{'Mid Cap'}, {'Small Cap'}],
    },
    'conviction': {
        # High risk. Concentrated small cap + focused. Pure score maximiser.
        'category_weights': {
            'Small Cap': 45,
            'Mid Cap':   25,
            'Focused':   15,
            'Flexi Cap': 15,
        },
        'dim_boosts': {
            'dim_return_cons': 1.5,
            'dim_risk_adj':    1.0,
            'dim_downside':    0.4,
        },
        'exclude_categories': {'Balanced Advantage', 'Equity Savings', 'ELSS'},
        'required_categories': [{'Small Cap'}, {'Mid Cap'}],
    },
}


def _load_scored_universe(horizon_years: int) -> list[dict]:
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
            fm.scheme_name,
            fm.amc_name,
            fm.sebi_category,
            fm.aum_crores,
            fm.expense_ratio
        FROM computed_metrics cm
        JOIN fund_metadata fm ON cm.scheme_code = fm.scheme_code
        WHERE cm.horizon_years = %s
          AND cm.fund_score IS NOT NULL
          AND fm.is_active = true
          AND fm.scheme_name NOT ILIKE '%%US Bluechip%%'
          AND (fm.fund_type IS NULL OR fm.fund_type NOT ILIKE '%%overseas%%')
        ORDER BY cm.scheme_code, cm.computation_date DESC
    """, (horizon_years,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    funds = []
    for r in rows:
        cat = r[10] or 'Unknown'
        if cat not in EQUITY_CATEGORIES:
            continue
        funds.append({
            'scheme_code':     str(r[0]),
            'fund_score':      float(r[1]) if r[1] else 0.0,
            'dim_return_cons': float(r[2]) if r[2] else 0.0,
            'dim_risk_adj':    float(r[3]) if r[3] else 0.0,
            'dim_downside':    float(r[4]) if r[4] else 0.0,
            'dim_manager':     float(r[5]) if r[5] else 0.0,
            'dim_port_qual':   float(r[6]) if r[6] else 0.0,
            'dim_fwd_context': float(r[7]) if r[7] else 0.0,
            'scheme_name':     r[8] or '',
            'amc_name':        r[9] or '',
            'category':        cat,
            'aum_crores':      float(r[11]) if r[11] else 0.0,
            'expense_ratio':   float(r[12]) if r[12] else 0.0,
        })
    return funds


def _boosted_score(fund: dict, dim_boosts: dict) -> float:
    """Re-weight composite score with archetype-specific dimension emphasis."""
    if not dim_boosts:
        return fund['fund_score']
    base_w = {
        'dim_return_cons': 25.0,
        'dim_risk_adj':    20.0,
        'dim_downside':    20.0,
        'dim_manager':     15.0,
        'dim_port_qual':   10.0,
        'dim_fwd_context': 10.0,
    }
    adj_w = {k: v * dim_boosts.get(k, 1.0) for k, v in base_w.items()}
    total = sum(adj_w.values())
    return round(sum(fund[k] * (adj_w[k] / total) for k in adj_w), 2)


def _fetch_nav_batch(codes: list[str], years: int = 5) -> dict:
    if not codes:
        return {}
    cutoff = date.today() - timedelta(days=int(years * 365.25) + 30)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT scheme_code, nav_date, nav_value
            FROM nav_data
            WHERE scheme_code = ANY(%s) AND nav_date >= %s
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

    return {
        code: pd.Series(vals, index=pd.DatetimeIndex(dates))
        for code, (dates, vals) in nav_map.items()
    }


def _corr(s1: pd.Series, s2: pd.Series) -> float:
    try:
        r1 = s1.pct_change().dropna()
        r2 = s2.pct_change().dropna()
        common = r1.index.intersection(r2.index)
        if len(common) < 100:
            return 0.7
        return round(float(r1[common].corr(r2[common])), 4)
    except Exception:
        return 0.7


def _select_candidates(scored_funds: list, profile: dict) -> list:
    """Pick top-scoring candidates per priority category (up to 25 total)."""
    cat_weights = profile['category_weights']
    dim_boosts  = profile.get('dim_boosts', {})
    exclude     = profile.get('exclude_categories', set())

    by_cat: dict = {}
    for f in scored_funds:
        if f['category'] in exclude:
            continue
        by_cat.setdefault(f['category'], []).append(f)

    for cat in by_cat:
        by_cat[cat].sort(key=lambda f: _boosted_score(f, dim_boosts), reverse=True)

    seen = set()
    candidates = []

    # Priority categories first
    for cat in sorted(cat_weights, key=lambda c: cat_weights[c], reverse=True):
        for fund in by_cat.get(cat, [])[:TOP_N_PER_CATEGORY]:
            if fund['scheme_code'] not in seen:
                candidates.append(fund)
                seen.add(fund['scheme_code'])

    # Fill with remaining equity categories as fallback
    fallback = ['Flexi Cap', 'Large Cap', 'Mid Cap', 'Small Cap', 'Multi Cap',
                'Large & Mid Cap', 'ELSS', 'Focused', 'Value', 'Contra',
                'Balanced Advantage', 'Aggressive Hybrid']
    for cat in fallback:
        if len(candidates) >= 25:
            break
        for fund in by_cat.get(cat, [])[:2]:
            if fund['scheme_code'] not in seen:
                candidates.append(fund)
                seen.add(fund['scheme_code'])

    return candidates


def _combo_score(combo: tuple, corr_matrix: dict, profile: dict) -> float:
    dim_boosts = profile.get('dim_boosts', {})
    avg_score  = float(np.mean([_boosted_score(f, dim_boosts) for f in combo]))
    codes = [f['scheme_code'] for f in combo]
    pairs = [(codes[i], codes[j]) for i in range(len(codes)) for j in range(i+1, len(codes))]
    avg_corr = float(np.mean([corr_matrix.get((c1, c2), 0.7) for c1, c2 in pairs]))
    n_cats   = len(set(f['category'] for f in combo))
    n_amcs   = len(set(f['amc_name'] for f in combo))
    return avg_score - (avg_corr * 20) + (n_cats - 1) * 3 + (n_amcs - 1) * 1.5


def _assign_weights(selected: list, profile: dict) -> list[tuple]:
    """Assign category-based weights, normalised to 100%."""
    cat_weights = profile['category_weights']
    raw = [cat_weights.get(f['category'], 10) for f in selected]
    total = sum(raw)
    weights = [round(w / total * 100) for w in raw]
    diff = 100 - sum(weights)
    if diff:
        weights[weights.index(max(weights))] += diff
    return [(f['scheme_code'], w) for f, w in zip(selected, weights)]


def build_dynamic_archetype_bouquet(
    arch_id: str,
    horizon_years: int,
    target_cagr: float,
) -> dict | None:
    """
    Select the best 5-fund bouquet for an archetype from the scored 271-fund universe.
    Returns the same dict as legacy build_bouquet() — precompute.py compatible.
    """
    profile = ARCHETYPE_PROFILES.get(arch_id)
    if not profile:
        return None

    print(f"  [dynamic] Loading {horizon_years}yr scored universe...")
    scored_funds = _load_scored_universe(horizon_years)
    if not scored_funds:
        print(f"  [dynamic] No scored funds for {horizon_years}yr")
        return None
    print(f"  [dynamic] {len(scored_funds)} equity funds available")

    candidates = _select_candidates(scored_funds, profile)
    print(f"  [dynamic] {len(candidates)} candidates, evaluating combinations...")

    if len(candidates) < 5:
        print(f"  [dynamic] Too few candidates ({len(candidates)})")
        return None

    codes = [f['scheme_code'] for f in candidates]
    nav_cache = _fetch_nav_batch(codes)

    # Pairwise correlation matrix
    corr_matrix: dict = {}
    for i, f1 in enumerate(candidates):
        for f2 in candidates[i+1:]:
            c1, c2 = f1['scheme_code'], f2['scheme_code']
            s1, s2 = nav_cache.get(c1), nav_cache.get(c2)
            c = _corr(s1, s2) if s1 is not None and s2 is not None else 0.7
            corr_matrix[(c1, c2)] = c
            corr_matrix[(c2, c1)] = c

    # Select best valid 5-fund combination
    best_combo: list | None = None
    best_score = -9999.0

    required = profile.get('required_categories', [])

    for combo in combinations(candidates, 5):
        codes_c = [f['scheme_code'] for f in combo]
        combo_cats = {f['category'] for f in combo}

        # Each required_categories entry is a set — combo must have at least one fund from each set
        if any(not (req_set & combo_cats) for req_set in required):
            continue
        if any(
            corr_matrix.get((codes_c[i], codes_c[j]), 0) > MAX_CORRELATION
            for i in range(len(codes_c)) for j in range(i+1, len(codes_c))
        ):
            continue
        if len(combo_cats) < 3:
            continue
        if len(set(f['amc_name'] for f in combo)) < 3:
            continue
        sc = _combo_score(combo, corr_matrix, profile)
        if sc > best_score:
            best_score = sc
            best_combo = list(combo)

    if best_combo is None:
        # Relax constraints: take top 5 by boosted score (no correlation filter)
        print(f"  [dynamic] No valid combo — using top-5 by score")
        dim_boosts = profile.get('dim_boosts', {})
        candidates.sort(key=lambda f: _boosted_score(f, dim_boosts), reverse=True)
        best_combo = candidates[:5]

    fund_weights = _assign_weights(best_combo, profile)

    # Build fund_scores list matching legacy build_bouquet() output
    fund_scores = [
        {
            'scheme_code':      f['scheme_code'],
            'weight':           w,
            'name':             f['scheme_name'],
            'category':         f['category'],
            'amc':              f['amc_name'],
            'tier':             1,
            'composite_score':  f['fund_score'],
            'dimension_scores': {
                'return_consistency': f['dim_return_cons'],
                'risk_adjusted':      f['dim_risk_adj'],
                'downside':           f['dim_downside'],
                'manager':            f['dim_manager'],
                'portfolio_quality':  f['dim_port_qual'],
                'forward_context':    f['dim_fwd_context'],
            },
        }
        for f, (_, w) in zip(best_combo, fund_weights)
    ]

    print(f"  [dynamic] Computing bouquet metrics...")
    metrics = compute_bouquet_metrics(fund_weights, horizon_years)

    # Intra-bouquet correlation stats
    codes_final = [f['scheme_code'] for f in best_combo]
    intra_corrs = [
        corr_matrix.get((codes_final[i], codes_final[j]), 0.7)
        for i in range(len(codes_final)) for j in range(i+1, len(codes_final))
    ]
    avg_correlation = round(float(np.mean(intra_corrs)), 4) if intra_corrs else 0.7

    # Holdings overlap
    overlap_scores = []
    pairs_with_data = total_pairs = 0
    for i in range(len(codes_final)):
        for j in range(i+1, len(codes_final)):
            total_pairs += 1
            ov = compute_holding_overlap(codes_final[i], codes_final[j])
            if ov is not None:
                overlap_scores.append(ov)
                pairs_with_data += 1

    avg_overlap = round(float(np.mean(overlap_scores)) * 100, 1) if overlap_scores else None
    holdings_cov = round(pairs_with_data / total_pairs * 100) if total_pairs else 0

    return {
        'archetype_id':          arch_id,
        'horizon_years':         horizon_years,
        'target_cagr':           target_cagr,
        'funds':                 fund_scores,
        'metrics':               metrics,
        'avg_correlation':       avg_correlation,
        'avg_overlap_pct':       avg_overlap,
        'holdings_coverage_pct': holdings_cov,
        'avg_fund_score':        round(float(np.mean([f['fund_score'] for f in best_combo])), 2),
        'high_correlation_pairs': [],
        'universe_size':         len(scored_funds),
    }
