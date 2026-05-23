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


def _score_pool(pool: list, horizon_years: int, target_cagr: float, max_funds: int = 30) -> list:
    """Score candidate funds. Caps at max_funds by NAV count to manage time."""
    from engine.fund_scorer import compute_composite_score

    candidates = sorted(pool, key=lambda x: x['nav_count'], reverse=True)[:max_funds]
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


def build_alternative_round(
    horizon_years: int,
    target_cagr: float,
    excluded_codes: list,
    round_number: int,
) -> dict:
    """
    Build a full set of 4 alternative archetypes for the given round.
    Returns dict with archetypes list + pool_exhausted flag.
    """
    from engine.bouquet_builder import compute_bouquet_metrics, build_correlation_matrix
    from engine.confidence_scorer import compute_bouquet_confidence
    from engine.precompute import compute_bouquet_stress_test, compute_comparator

    print(f"\n=== Alternative Bouquet Round {round_number} ===")
    print(f"Excluding {len(excluded_codes)} previously shown funds")

    pool = fetch_eligible_pool(excluded_codes)
    print(f"Eligible pool: {len(pool)} funds")

    if len(pool) < 15:
        return {'archetypes': [], 'pool_exhausted': True, 'pool_size': len(pool)}

    print("Scoring candidates...")
    scored = _score_pool(pool, horizon_years, target_cagr)

    archetypes = []
    round_used_codes = set(excluded_codes)
    round_used_amcs = set()

    for arch_id in ['steady', 'balanced', 'aggressive', 'conviction']:
        print(f"\nBuilding {arch_id}...")
        result = _pick_slots(arch_id, scored, round_used_codes, round_used_amcs)
        if result is None:
            print(f"  Skipping {arch_id} — pool too thin")
            continue

        selected, new_codes, new_amcs = result
        round_used_codes = new_codes
        round_used_amcs = new_amcs

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
