"""
FUNDGULDASTA — DYNAMIC ARCHETYPE BOUQUET BUILDER
=================================================
Selects the best bouquet for each archetype from the full 271-fund
scored universe (computed_metrics). No hardcoded fund compositions.

Steady and Balanced archetypes include a correlation-optimised
international diversifier from a curated pool of overseas equity FOFs.
International funds are outside the India equity scoring universe but
provide genuine low-correlation diversification when Indian markets
are tepid — the fund chosen is whichever minimises average correlation
with the 4 selected India equity funds.

Aggressive and Conviction archetypes are pure India equity conviction
plays — no international slot.

Returns the same dict structure as legacy build_bouquet() — fully
precompute.py-compatible, no frontend or API changes required.
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

# ── International Diversifier Pool ───────────────────────────────────────────
# Three funds curated for genuine geographic diversification.
# All are direct-plan growth, established AMCs, sufficient NAV history.
# Tax note: Indian FOFs investing in overseas ETFs/funds are taxed as
# debt instruments — income slab rate applies regardless of holding period.
# The platform shows intlTaxWarning on archetypes that include these.
INTL_DIVERSIFIER_POOL = [
    {
        'scheme_code': '145552',
        'name':        'Motilal Oswal Nasdaq 100 Fund of Fund',
        'amc_name':    'Motilal Oswal',
        'category':    'International',
        'sub_type':    'US Tech Index',
        'nav_since':   '2018-12',
        'aum_crores':  6200.0,
        'expense_ratio': 0.35,
        # Tracks Nasdaq 100 — Apple, Microsoft, Nvidia, Alphabet, Meta.
        # Correlation with Indian equity ~0.33 — primary diversifier.
    },
    {
        'scheme_code': '118551',
        'name':        'Franklin U.S. Opportunities Equity Active Fund of Funds',
        'amc_name':    'Franklin Templeton',
        'category':    'International',
        'sub_type':    'US Equity Active',
        'nav_since':   '2013-01',
        'aum_crores':  None,
        'expense_ratio': None,
        # Actively managed US growth equity. Longest US fund track record
        # in India (since Jan 2013). Broader than Nasdaq — less tech concentrated.
    },
    {
        'scheme_code': '138528',
        'name':        'PGIM India Global Equity Opportunities Fund of Fund',
        'amc_name':    'PGIM India',
        'category':    'International',
        'sub_type':    'Global Equity',
        'nav_since':   '2016-03',
        'aum_crores':  None,
        'expense_ratio': None,
        # Invests globally (US + non-US developed: Europe, Japan, etc.).
        # True geographic diversification beyond US-only funds.
        # PGIM/Prudential: institutional global equity mandate.
    },
]

INTL_CODES = [f['scheme_code'] for f in INTL_DIVERSIFIER_POOL]
INTL_BY_CODE = {f['scheme_code']: f for f in INTL_DIVERSIFIER_POOL}

# ── SEBI equity categories included in the scored universe ───────────────────
# Equity Savings excluded (10-35% equity — too conservative for bouquets).
EQUITY_CATEGORIES = frozenset({
    'Large Cap', 'Mid Cap', 'Small Cap', 'Flexi Cap', 'Multi Cap',
    'Large & Mid Cap', 'ELSS', 'Focused', 'Value', 'Contra',
    'Balanced Advantage', 'Aggressive Hybrid',
})

# ── Per-archetype selection profiles ─────────────────────────────────────────
ARCHETYPE_PROFILES = {
    'steady': {
        # Low-medium risk. Large cap stability + flexi + hybrid buffer.
        # Includes 1 international diversifier slot (18% weight).
        'equity_fund_count': 4,          # 4 equity + 1 international = 5 total
        'intl_slot_weight':  18,         # % allocated to international diversifier
        'category_weights': {
            'Large Cap':          30,
            'Flexi Cap':          25,
            'Balanced Advantage': 20,
            'Mid Cap':            15,
            'ELSS':               10,
            'Value':              10,
            'Large & Mid Cap':    10,
        },
        'dim_boosts': {
            'dim_downside':    1.8,
            'dim_risk_adj':    1.4,
            'dim_return_cons': 1.0,
            'dim_manager':     1.0,
        },
        'exclude_categories': {'Small Cap', 'Focused'},
        'required_categories': [{'Large Cap'}, {'Flexi Cap', 'Multi Cap', 'Large & Mid Cap'}],
    },
    'balanced': {
        # Medium risk. Diversified across large/mid/small/hybrid.
        # Includes 1 international diversifier slot (13% weight).
        'equity_fund_count': 4,          # 4 equity + 1 international = 5 total
        'intl_slot_weight':  13,
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
        # Pure India equity — no international.
        'equity_fund_count': 5,
        'intl_slot_weight':  0,
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
        # Pure India equity — no international.
        'equity_fund_count': 5,
        'intl_slot_weight':  0,
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


# ── Internal helpers ──────────────────────────────────────────────────────────

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
          AND fm.scheme_name NOT ILIKE '%%FOF%%'
          AND fm.scheme_name NOT ILIKE '%%Fund of Fund%%'
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

    for cat in sorted(cat_weights, key=lambda c: cat_weights[c], reverse=True):
        for fund in by_cat.get(cat, [])[:TOP_N_PER_CATEGORY]:
            if fund['scheme_code'] not in seen:
                candidates.append(fund)
                seen.add(fund['scheme_code'])

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


def _assign_equity_weights(equity_funds: list, profile: dict, equity_total_pct: int) -> list[tuple]:
    """
    Assign weights to the equity portion, scaled to sum to equity_total_pct.
    Returns list of (scheme_code, weight_pct) tuples.
    """
    cat_weights = profile['category_weights']
    raw = [cat_weights.get(f['category'], 10) for f in equity_funds]
    raw_total = sum(raw)
    weights = [round(w / raw_total * equity_total_pct) for w in raw]
    diff = equity_total_pct - sum(weights)
    if diff:
        weights[weights.index(max(weights))] += diff
    return [(f['scheme_code'], w) for f, w in zip(equity_funds, weights)]


def _pick_best_international(equity_funds: list, nav_cache: dict) -> dict | None:
    """
    From the curated INTL_DIVERSIFIER_POOL, pick the fund that minimises
    average correlation with the selected equity funds.
    Falls back to Motilal Nasdaq if NAV data is unavailable for all pool funds.
    """
    equity_codes = [f['scheme_code'] for f in equity_funds]
    best_fund    = None
    best_avg_corr = 999.0

    for intl in INTL_DIVERSIFIER_POOL:
        code  = intl['scheme_code']
        s_intl = nav_cache.get(code)
        if s_intl is None or len(s_intl) < 100:
            continue  # No NAV data — skip this candidate

        corrs = []
        for eq_code in equity_codes:
            s_eq = nav_cache.get(eq_code)
            if s_eq is not None:
                corrs.append(_corr(s_intl, s_eq))

        avg_corr = float(np.mean(corrs)) if corrs else 0.7

        if avg_corr < best_avg_corr:
            best_avg_corr = avg_corr
            best_fund = intl

    # Hard fallback: if no NAV data at all, use Motilal Nasdaq (best-known)
    if best_fund is None:
        best_fund = INTL_DIVERSIFIER_POOL[0]
        best_avg_corr = 0.35  # known approximate value

    print(f"  [intl] Selected {best_fund['name'][:45]} (avg corr with equity: {best_avg_corr:.3f})")
    return best_fund, best_avg_corr


# ── Public API ────────────────────────────────────────────────────────────────

def build_dynamic_archetype_bouquet(
    arch_id: str,
    horizon_years: int,
    target_cagr: float,
) -> dict | None:
    """
    Select the optimal bouquet for an archetype from the scored 271-fund
    universe. Steady and Balanced include 1 international diversifier
    chosen to minimise correlation with the selected equity funds.
    Returns same dict as legacy build_bouquet() — precompute.py compatible.
    """
    profile = ARCHETYPE_PROFILES.get(arch_id)
    if not profile:
        return None

    n_equity       = profile['equity_fund_count']
    intl_weight    = profile.get('intl_slot_weight', 0)
    equity_total   = 100 - intl_weight          # equity funds share this %

    print(f"  [dynamic] Loading {horizon_years}yr scored universe...")
    scored_funds = _load_scored_universe(horizon_years)
    if not scored_funds:
        print(f"  [dynamic] No scored funds for {horizon_years}yr")
        return None
    print(f"  [dynamic] {len(scored_funds)} equity funds available")

    candidates = _select_candidates(scored_funds, profile)
    print(f"  [dynamic] {len(candidates)} candidates — evaluating {n_equity}-fund combinations...")

    if len(candidates) < n_equity:
        print(f"  [dynamic] Too few candidates ({len(candidates)})")
        return None

    # Fetch NAV for equity candidates + international pool (single batch)
    all_codes = [f['scheme_code'] for f in candidates] + INTL_CODES
    nav_cache = _fetch_nav_batch(all_codes)

    # Build pairwise correlation matrix for equity candidates
    corr_matrix: dict = {}
    for i, f1 in enumerate(candidates):
        for f2 in candidates[i+1:]:
            c1, c2 = f1['scheme_code'], f2['scheme_code']
            s1, s2 = nav_cache.get(c1), nav_cache.get(c2)
            c = _corr(s1, s2) if s1 is not None and s2 is not None else 0.7
            corr_matrix[(c1, c2)] = c
            corr_matrix[(c2, c1)] = c

    # Select best valid n_equity-fund equity combination
    required = profile.get('required_categories', [])
    best_combo: list | None = None
    best_score = -9999.0

    for combo in combinations(candidates, n_equity):
        combo_cats = {f['category'] for f in combo}
        codes_c    = [f['scheme_code'] for f in combo]

        if any(not (req & combo_cats) for req in required):
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
        print(f"  [dynamic] No valid equity combo — using top-{n_equity} by score")
        dim_boosts = profile.get('dim_boosts', {})
        candidates.sort(key=lambda f: _boosted_score(f, dim_boosts), reverse=True)
        best_combo = candidates[:n_equity]

    # Assign equity weights scaled to equity_total%
    fund_weights_equity = _assign_equity_weights(best_combo, profile, equity_total)

    # Select & append international diversifier (steady/balanced only)
    all_fund_weights: list[tuple] = list(fund_weights_equity)
    selected_intl: dict | None = None
    intl_avg_corr: float = 0.0

    if intl_weight > 0:
        selected_intl, intl_avg_corr = _pick_best_international(best_combo, nav_cache)
        all_fund_weights.append((selected_intl['scheme_code'], intl_weight))

    # Build fund_scores list (structure matches legacy build_bouquet output)
    fund_scores = []

    for f, (code, weight) in zip(best_combo, fund_weights_equity):
        fund_scores.append({
            'scheme_code':      code,
            'weight':           weight,
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
        })

    if selected_intl:
        fund_scores.append({
            'scheme_code':      selected_intl['scheme_code'],
            'weight':           intl_weight,
            'name':             selected_intl['name'],
            'category':         selected_intl['category'],
            'amc':              selected_intl['amc_name'],
            'tier':             2,
            'composite_score':  None,   # not scored via compute_metrics
            'sub_type':         selected_intl['sub_type'],
            'tax_note':         'Taxed as debt fund — income slab rate applies',
            'dimension_scores': None,
        })

    print(f"  [dynamic] Computing bouquet metrics...")
    metrics = compute_bouquet_metrics(all_fund_weights, horizon_years)

    # Intra-bouquet correlation stats (equity-only pairs for avg correlation display)
    equity_codes_final = [f['scheme_code'] for f in best_combo]
    intra_corrs = [
        corr_matrix.get((equity_codes_final[i], equity_codes_final[j]), 0.7)
        for i in range(len(equity_codes_final))
        for j in range(i+1, len(equity_codes_final))
    ]
    avg_equity_corr = round(float(np.mean(intra_corrs)), 4) if intra_corrs else 0.7

    # Holdings overlap (portfolio_holdings table)
    all_codes_final = [f['scheme_code'] for f in best_combo]
    overlap_scores = []
    pairs_data = total_pairs = 0
    for i in range(len(all_codes_final)):
        for j in range(i+1, len(all_codes_final)):
            total_pairs += 1
            ov = compute_holding_overlap(all_codes_final[i], all_codes_final[j])
            if ov is not None:
                overlap_scores.append(ov)
                pairs_data += 1

    avg_overlap  = round(float(np.mean(overlap_scores)) * 100, 1) if overlap_scores else None
    holdings_cov = round(pairs_data / total_pairs * 100) if total_pairs else 0

    return {
        'archetype_id':          arch_id,
        'horizon_years':         horizon_years,
        'target_cagr':           target_cagr,
        'funds':                 fund_scores,
        'metrics':               metrics,
        'avg_correlation':       avg_equity_corr,
        'intl_avg_corr':         round(intl_avg_corr, 3) if intl_weight else None,
        'avg_overlap_pct':       avg_overlap,
        'holdings_coverage_pct': holdings_cov,
        'avg_fund_score':        round(float(np.mean([f['fund_score'] for f in best_combo])), 2),
        'high_correlation_pairs': [],
        'universe_size':         len(scored_funds),
        'has_international':     intl_weight > 0,
    }
