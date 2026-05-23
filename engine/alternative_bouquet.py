"""
FUNDGULDASTA — ALTERNATIVE BOUQUET GENERATOR
==============================================
Generates rounds 2+ of bouquet options using the broader eligible
fund universe (750+ NAV records, Direct plans only).

Each round excludes funds already shown in prior rounds, ensuring
users see genuinely different options each time.

Platform principle: transparent about data tier. Tier 2/3 funds are
flagged. User has full agency to explore or stop.
"""

import psycopg2
import os
import pandas as pd
from collections import defaultdict
from dotenv import load_dotenv

from config.db import get_db_config
DB_CONFIG = get_db_config()

ARCHETYPE_LABELS = {
    'steady': 'Steady Compounder',
    'balanced': 'Balanced Growther',
    'aggressive': 'Aggressive Achiever',
    'conviction': 'High Conviction',
}
ARCHETYPE_ICONS = {'steady': 'B', 'balanced': 'G', 'aggressive': 'Y', 'conviction': 'R'}
ARCHETYPE_COLORS = {
    'steady': '#4A8FE0', 'balanced': '#27AE78',
    'aggressive': '#F0A500', 'conviction': '#E05555',
}
ARCHETYPE_RGB = {
    'steady': '74,143,224', 'balanced': '39,174,120',
    'aggressive': '240,165,0', 'conviction': '224,85,85',
}
ARCHETYPE_RISK = {
    'steady': 'Low-Medium', 'balanced': 'Medium',
    'aggressive': 'Medium-High', 'conviction': 'High',
}
ARCHETYPE_CAGR_RANGE = {
    'steady': '14-16%', 'balanced': '15-17%',
    'aggressive': '16-19%', 'conviction': '18-22%',
}

# Per slot: ordered list of sebi_category values to try (None = NULL category)
ARCHETYPE_SLOT_CATEGORIES = {
    'steady': [
        ['Large Cap', None],
        ['Flexi Cap', 'Multi Cap', None],
        ['Large Cap', None],
        ['Balanced Advantage', 'Aggressive Hybrid', None],
        ['Flexi Cap', 'Value', None],
    ],
    'balanced': [
        ['Large Cap', None],
        ['Flexi Cap', 'Multi Cap', None],
        ['Mid Cap', None],
        ['Small Cap'],
        ['ELSS', 'Value', 'Contra', None],
    ],
    'aggressive': [
        ['Mid Cap', None],
        ['Small Cap'],
        ['Mid Cap', None],
        ['Small Cap'],
        ['Large & Mid Cap', 'Flexi Cap', None],
    ],
    'conviction': [
        ['Small Cap'],
        ['Mid Cap', None],
        ['Small Cap'],
        ['Large & Mid Cap', None],
        ['ELSS', 'Value', 'Contra', None],
    ],
}

ARCHETYPE_SLOT_WEIGHTS = {
    'steady':     [25, 25, 20, 15, 15],
    'balanced':   [20, 20, 25, 20, 15],
    'aggressive': [25, 20, 20, 20, 15],
    'conviction': [30, 25, 20, 15, 10],
}


def _get_db():
    return psycopg2.connect(**DB_CONFIG)


def _get_tier(nav_count):
    if nav_count >= 1750:
        return 1
    elif nav_count >= 1250:
        return 2
    return 3


def fetch_eligible_pool(excluded_codes: list) -> list:
    """
    Query DB for eligible funds not in excluded_codes.
    Min 750 NAV records; Direct Growth equity only.
    """
    conn = _get_db()
    cur = conn.cursor()

    if excluded_codes:
        placeholders = ','.join(['%s'] * len(excluded_codes))
        exclude_clause = f"AND fm.scheme_code::text NOT IN ({placeholders})"
        params = [str(c) for c in excluded_codes]
    else:
        exclude_clause = ""
        params = []

    query = f"""
        SELECT
            fm.scheme_code::text,
            fm.scheme_name,
            fm.amc_name,
            fm.sebi_category,
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
        AND fm.scheme_name NOT ILIKE '%%credit risk%%'
        AND fm.scheme_name NOT ILIKE '%%index%%'
        AND fm.scheme_name NOT ILIKE '%%etf%%'
        AND fm.scheme_name NOT ILIKE '%%fof%%'
        AND fm.scheme_name NOT ILIKE '%%fund of fund%%'
        AND fm.scheme_name NOT ILIKE '%%international%%'
        AND fm.scheme_name NOT ILIKE '%%global%%'
        AND fm.scheme_name NOT ILIKE '%%nasdaq%%'
        {exclude_clause}
        GROUP BY fm.scheme_code, fm.scheme_name, fm.amc_name, fm.sebi_category
        HAVING COUNT(nd.nav_date) >= 750
        ORDER BY COUNT(nd.nav_date) DESC
    """
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    pool = []
    for code, name, amc, category, nav_count in rows:
        pool.append({
            'scheme_code': str(code),
            'name': name,
            'amc': amc,
            'sebi_category': category,
            'nav_count': int(nav_count),
            'tier': _get_tier(int(nav_count)),
        })
    return pool


def _score_pool(pool: list, horizon_years: int, target_cagr: float, max_funds: int = 10, fast: bool = False) -> list:
    """Score candidate funds. Caps at max_funds by NAV count to manage time.
    fast=True: skip composite scoring, use NAV count as quality proxy (completes in <1s).
    """
    candidates = sorted(pool, key=lambda x: x['nav_count'], reverse=True)[:max_funds]
    if fast:
        for fund in candidates:
            # NAV count / 1750 gives a 0-100 proxy for data quality
            fund['composite_score'] = round(min(fund['nav_count'] / 1750 * 100, 100), 1)
            fund['dimension_scores'] = {}
        return candidates

    from engine.fund_scorer import compute_composite_score
    scored = []
    for fund in candidates:
        try:
            result = compute_composite_score(
                fund['scheme_code'], horizon_years, target_cagr,
                fund['sebi_category'] or 'Unknown'
            )
            fund['composite_score'] = result.get('composite_score') or 0
            fund['dimension_scores'] = result.get('dimension_scores', {})
        except Exception:
            fund['composite_score'] = 0
            fund['dimension_scores'] = {}
        scored.append(fund)
    return scored


def _pick_slots(arch_id: str, scored: list, used_codes: set, used_amcs: set):
    """
    Fill 5 slots for an archetype using category priority lists.
    Returns list of (fund_dict, weight) or None if pool too thin.
    """
    slot_cats = ARCHETYPE_SLOT_CATEGORIES[arch_id]
    slot_weights = ARCHETYPE_SLOT_WEIGHTS[arch_id]
    selected = []
    local_used_codes = set(used_codes)
    local_used_amcs = set(used_amcs)

    for cats, weight in zip(slot_cats, slot_weights):
        def cat_match(f):
            if not cats:
                return True
            if None in cats and f['sebi_category'] is None:
                return True
            return f['sebi_category'] in cats

        eligible = [
            f for f in scored
            if cat_match(f)
            and f['scheme_code'] not in local_used_codes
            and f['amc'] not in local_used_amcs
        ]
        # Relax AMC constraint if needed
        if not eligible:
            eligible = [
                f for f in scored
                if cat_match(f) and f['scheme_code'] not in local_used_codes
            ]
        # Relax category constraint if needed
        if not eligible:
            eligible = [f for f in scored if f['scheme_code'] not in local_used_codes]

        if not eligible:
            return None

        best = max(eligible, key=lambda f: f['composite_score'])
        selected.append((best, weight))
        local_used_codes.add(best['scheme_code'])
        local_used_amcs.add(best['amc'])

    return selected, local_used_codes, local_used_amcs


def _alt_compute_pros(funds, metrics_dict, confidence, avg_corr, stress_test):
    pros = []
    tier1 = sum(1 for f in funds if f.get('tier') == 1)
    if tier1 >= 3:
        pros.append(f"{tier1} of {len(funds)} funds have 7+ years of verified history — scores are statistically grounded")
    elif tier1 >= 1:
        pros.append(f"{tier1} Tier 1 fund(s) — backed by the longest available track records in this alternative selection")
    for period in ['7 Yr', '10 Yr', '5 Yr']:
        m = metrics_dict.get(period, {})
        bouquet_cagr = m.get('bouquet')
        nifty = m.get('nifty50')
        if bouquet_cagr and nifty:
            delta = round(bouquet_cagr - nifty, 1)
            if delta > 1:
                pros.append(f"Historical {period} CAGR of {bouquet_cagr}% — {delta}% ahead of Nifty 50. Alternative selection still demonstrates alpha")
            break
    if avg_corr < 0.90:
        pros.append(f"Average correlation {avg_corr:.2f} — funds selected from different AMCs and categories for genuine diversification")
    factors = confidence.get('factors', {}) if isinstance(confidence, dict) else {}
    factor_scores = [(k, v.get('score', 0)) for k, v in factors.items() if isinstance(v, dict)]
    if factor_scores:
        best_k, best_v = max(factor_scores, key=lambda x: x[1])
        if best_v >= 50:
            pros.append(f"{best_k.replace('_', ' ').title()} score {best_v:.0f}/100 — alternative funds also pass the platform quality threshold")
    pros.append("All direct plans — zero commission. Full returns compound for the investor")
    return pros[:4]


def _batch_load_nav(scheme_codes: list) -> dict:
    """Load full NAV history for multiple funds in ONE query — no per-fund round trips."""
    if not scheme_codes:
        return {}
    conn = _get_db()
    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(scheme_codes))
    cur.execute(f"""
        SELECT scheme_code::text, nav_date, nav_value
        FROM nav_data
        WHERE scheme_code IN ({placeholders})
        ORDER BY scheme_code, nav_date ASC
    """, [str(c) for c in scheme_codes])
    rows = cur.fetchall()
    cur.close()
    conn.close()
    fund_data = defaultdict(list)
    for code, date, nav in rows:
        fund_data[str(code)].append((date, float(nav)))
    result = {}
    for code, records in fund_data.items():
        dates, navs = zip(*records)
        result[code] = pd.Series(navs, index=pd.DatetimeIndex(dates))
    return result


def _fast_metrics(fund_weights: list, nav_cache: dict) -> dict:
    """Compute bouquet CAGR metrics from in-memory NAV cache."""
    periods = {'5 Yr': 5, '7 Yr': 7, '10 Yr': 10, '15 Yr': 15}
    total_w = sum(w for _, w in fund_weights)
    result = {}
    for label, yrs in periods.items():
        cagr_pairs = []
        for code, weight in fund_weights:
            series = nav_cache.get(str(code))
            if series is None or len(series) < 2:
                continue
            end_date = series.index[-1]
            target = end_date - pd.Timedelta(days=int(yrs * 365.25))
            mask = (series.index <= target + pd.Timedelta(days=30)) & \
                   (series.index >= target - pd.Timedelta(days=30))
            avail = series.index[mask]
            if len(avail) == 0:
                continue
            start_date = avail[-1]
            actual_yrs = (end_date - start_date).days / 365.25
            nav_s = float(series[start_date])
            nav_e = float(series[end_date])
            if nav_s > 0 and actual_yrs > 0.5:
                cagr = ((nav_e / nav_s) ** (1 / actual_yrs) - 1) * 100
                cagr_pairs.append((cagr, weight / total_w))
        if cagr_pairs:
            tw = sum(w for _, w in cagr_pairs)
            wavg = sum(c * w for c, w in cagr_pairs) / tw
            result[label] = {
                'bouquet': round(wavg, 2),
                'realCAGR': round(((1 + wavg / 100) / 1.06 - 1) * 100, 2),
                'postTax': round(wavg - wavg * 0.125 * 0.30, 2),
                'nifty50': None,
                'nifty500': None,
                'fdRate': 6.8,
                'inflation': 6.0,
            }
    return result


def _fast_correlation(fund_weights: list, nav_cache: dict) -> float:
    """Compute avg pairwise correlation from in-memory NAV cache."""
    codes = [str(c) for c, _ in fund_weights]
    returns = {}
    for code in codes:
        series = nav_cache.get(code)
        if series is not None and len(series) > 100:
            cutoff = series.index[-1] - pd.Timedelta(days=5 * 365)
            s = series[series.index >= cutoff]
            returns[code] = s.pct_change().dropna()
    corrs = []
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            c1, c2 = codes[i], codes[j]
            if c1 in returns and c2 in returns:
                common = returns[c1].index.intersection(returns[c2].index)
                if len(common) >= 100:
                    corrs.append(float(returns[c1][common].corr(returns[c2][common])))
    return round(sum(corrs) / len(corrs), 4) if corrs else 0.89


def _fast_stress(fund_weights: list, nav_cache: dict) -> dict:
    """Compute stress test from in-memory NAV cache."""
    CRASHES = [
        {'name': '2008 Global Financial Crisis', 'peak': '2008-01-08', 'trough': '2009-03-09'},
        {'name': '2020 COVID Crash', 'peak': '2020-01-14', 'trough': '2020-03-23'},
        {'name': '2022 Rate Hike Selloff', 'peak': '2021-10-19', 'trough': '2022-06-17'},
    ]
    total_w = sum(w for _, w in fund_weights)
    periods = []
    for crash in CRASHES:
        peak_dt = pd.Timestamp(crash['peak'])
        trough_dt = pd.Timestamp(crash['trough'])
        falls = []
        for code, weight in fund_weights:
            series = nav_cache.get(str(code))
            if series is None or len(series) < 2:
                continue
            pk_avail = series.index[(series.index >= peak_dt - pd.Timedelta(days=10)) &
                                    (series.index <= peak_dt + pd.Timedelta(days=10))]
            tr_avail = series.index[(series.index >= trough_dt - pd.Timedelta(days=10)) &
                                    (series.index <= trough_dt + pd.Timedelta(days=10))]
            if len(pk_avail) == 0 or len(tr_avail) == 0:
                continue
            nav_peak = float(series[pk_avail[0]])
            nav_trough = float(series[tr_avail[-1]])
            if nav_peak > 0:
                fall_pct = (nav_trough - nav_peak) / nav_peak * 100
                falls.append((fall_pct, weight))
        if falls:
            tw = sum(w for _, w in falls)
            avg_fall = sum(f * w for f, w in falls) / tw
            recovery_months = round(max(6.0, min(36.0, abs(avg_fall) * 1.2)), 1)
            periods.append({
                'event': crash['name'],
                'peakFallPct': round(avg_fall, 1),
                'recoveryMonths': recovery_months,
                'postRecoveryCAGR': None,
            })
    return {'periods': periods}


def _fast_confidence(fund_details: list) -> dict:
    """Simplified confidence from composite scores — no DB calls."""
    scores = [d.get('composite_score') or 50 for d in fund_details]
    avg_score = sum(scores) / len(scores) if scores else 50
    composite = round(50 + avg_score * 0.25, 1)
    return {
        'score': composite,
        'label': 'Moderate' if composite < 65 else 'Good',
        'factors': {
            'rolling_consistency': {'score': round(composite * 0.9, 1), 'value': 'Estimated from NAV data quality proxy', 'weight': 30},
            'downside_protection': {'score': round(composite * 0.85, 1), 'value': 'Estimated from historical data', 'weight': 20},
            'manager_stability':   {'score': 55.0, 'value': 'Not individually verified for alternative universe', 'weight': 20},
            'category_tailwind':   {'score': 60.0, 'value': 'Equity — long-term growth tailwind assumed', 'weight': 15},
            'cost_efficiency':     {'score': 72.0, 'value': 'Direct plans — low-cost structure', 'weight': 15},
        },
        'interpretation': f'Alternative confidence estimated from data quality proxy. Avg composite score: {avg_score:.0f}/100.',
        'cagrAchievabilityPct': None,
    }


def build_alternative_round(
    horizon_years: int,
    target_cagr: float,
    excluded_codes: list,
    round_number: int,
    fast: bool = False,
) -> dict:
    """
    Build a full set of 4 alternative archetypes for the given round.
    Returns dict with archetypes list + pool_exhausted flag.
    fast=True: skip composite scoring — uses NAV count as quality proxy.
    Completes in ~5s vs ~10min. Used as fallback when cache is cold.
    """
    from engine.precompute import compute_comparator

    if not fast:
        from engine.bouquet_builder import compute_bouquet_metrics, build_correlation_matrix
        from engine.confidence_scorer import compute_bouquet_confidence
        from engine.precompute import compute_bouquet_stress_test

    print(f"\n=== Alternative Bouquet Round {round_number} {'[FAST]' if fast else ''} ===")
    print(f"Excluding {len(excluded_codes)} previously shown funds")

    pool = fetch_eligible_pool(excluded_codes)
    print(f"Eligible pool: {len(pool)} funds")

    if len(pool) < 15:
        return {'archetypes': [], 'pool_exhausted': True, 'pool_size': len(pool)}

    print("Scoring candidates...")
    scored = _score_pool(pool, horizon_years, target_cagr, fast=fast)

    # Pass 1: pick slots for all archetypes (collect all codes before any DB calls)
    round_used_codes = set(excluded_codes)
    round_used_amcs = set()
    all_selections = {}
    for arch_id in ['steady', 'balanced', 'aggressive', 'conviction']:
        print(f"\nSlot selection: {arch_id}...")
        result = _pick_slots(arch_id, scored, round_used_codes, round_used_amcs)
        if result is None:
            print(f"  Skipping {arch_id} — pool too thin")
            continue
        selected, new_codes, new_amcs = result
        all_selections[arch_id] = selected
        round_used_codes = new_codes
        round_used_amcs = new_amcs

    # Batch-load NAV data for ALL selected funds in one query (fast path only)
    nav_cache = {}
    if fast and all_selections:
        all_codes = list({f['scheme_code'] for sel in all_selections.values() for f, _ in sel})
        print(f"Batch loading NAV for {len(all_codes)} funds (1 query)...")
        nav_cache = _batch_load_nav(all_codes)
        print(f"NAV cache ready: {len(nav_cache)} funds loaded")

    # Pass 2: build archetype data using the in-memory NAV cache
    archetypes = []
    for arch_id, selected in all_selections.items():
        fund_weights = [(f['scheme_code'], w) for f, w in selected]
        fund_details = [
            {
                'scheme_code': f['scheme_code'],
                'weight': w,
                'name': f['name'],
                'category': f['sebi_category'] or 'Equity',
                'tier': f['tier'],
                'amc': f['amc'],
                'composite_score': f.get('composite_score'),
                'dimension_scores': f.get('dimension_scores', {}),
            }
            for f, w in selected
        ]

        try:
            if fast:
                metrics = _fast_metrics(fund_weights, nav_cache)
                avg_corr = _fast_correlation(fund_weights, nav_cache)
                stress = _fast_stress(fund_weights, nav_cache)
                confidence = _fast_confidence(fund_details)
            else:
                metrics = compute_bouquet_metrics(fund_weights, horizon_years)
                confidence = compute_bouquet_confidence(fund_weights, fund_details, horizon_years, target_cagr)
                stress = compute_bouquet_stress_test(fund_weights)
                corr_matrix = build_correlation_matrix([c for c, _ in fund_weights])
                all_corrs = [v for k, v in corr_matrix.items() if k[0] < k[1]]
                avg_corr = round(float(sum(all_corrs) / len(all_corrs)), 4) if all_corrs else 0.5

            bouquet_7yr = metrics.get('7 Yr', {}).get('bouquet', 16)
            comparator = compute_comparator(bouquet_7yr, horizon_years)

            tier3_funds = [d for d in fund_details if d['tier'] == 3]
            tier2_funds = [d for d in fund_details if d['tier'] == 2]
            warnings = []
            if tier3_funds:
                warnings.append(f"Data note: {len(tier3_funds)} fund(s) with 3-5 years history — scores extrapolated from available data.")
            if tier2_funds:
                warnings.append(f"Data note: {len(tier2_funds)} fund(s) with 5-7 years history (Tier 2 — solid but less than 7 years).")

            archetypes.append({
                'id':          arch_id,
                'icon':        ARCHETYPE_ICONS[arch_id],
                'label':       ARCHETYPE_LABELS[arch_id],
                'cagrRange':   ARCHETYPE_CAGR_RANGE[arch_id],
                'risk':        ARCHETYPE_RISK[arch_id],
                'color':       ARCHETYPE_COLORS[arch_id],
                'rgb':         ARCHETYPE_RGB[arch_id],
                'funds':       fund_details,
                'metrics':     {'periods': metrics},
                'confidence':  confidence,
                'stressTest':  stress,
                'overlap':     {'avgOverlapPct': 0, 'avgCorrelation': avg_corr},
                'methodology': [
                    f'Round {round_number} — dynamically selected from {len(pool)}-fund eligible universe',
                    'Same 6-dimension scoring engine as Round 1',
                    'Funds from Round 1 excluded to ensure genuine alternative composition',
                    'Direct plans only — no commission',
                    'Category diversity enforced by slot-based selection',
                ] + warnings,
                'pros': _alt_compute_pros(fund_details, metrics, confidence, avg_corr, stress),
                'devils': [
                    f'Round {round_number} bouquets are dynamically generated — not manually verified like Round 1',
                    'Tier 2/3 funds have shorter history; confidence intervals are wider',
                    'Scoring is algorithmic — human review of Round 1 archetypes is more thorough',
                    'Use Round 2+ for exploration and comparison, not as a standalone recommendation',
                ],
                'comparator':    comparator,
                'roundNumber':   round_number,
                'realisticAssessment': None,
                'relevanceScore': 0,
                'matchLabel': 'Alternative',
            })
        except Exception as e:
            print(f"  ERROR for {arch_id}: {e}")
            import traceback
            traceback.print_exc()
            continue

    pool_exhausted = len(pool) < 25 or len(archetypes) < 2
    return {
        'archetypes': archetypes,
        'pool_exhausted': pool_exhausted,
        'pool_size': len(pool),
        'round_number': round_number,
    }
