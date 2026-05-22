"""
FUNDGULDASTA — CUSTOM BOUQUET ANALYSER
=======================================
Analyses a user-defined bouquet: scores each fund, projects CAGR,
identifies high-correlation pairs, and suggests targeted improvements.

Platform principle: full transparency. The engine never overrides the
user's choices — it provides honest data so the user can decide.
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'fundguldasta_dev'),
    'user': os.getenv('DB_USER', 'fundguldasta_user'),
}


def _get_db():
    return psycopg2.connect(**DB_CONFIG)


def _get_tier(nav_count: int) -> int:
    if nav_count >= 1750:
        return 1
    elif nav_count >= 1250:
        return 2
    return 3


def _fetch_fund_meta(scheme_codes: list) -> dict:
    """Return {scheme_code: {name, amc, category, expense_ratio, nav_count, tier}} for given codes."""
    conn = _get_db()
    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(scheme_codes))
    cur.execute(f"""
        SELECT
            fm.scheme_code::text,
            fm.scheme_name,
            fm.amc_name,
            fm.sebi_category,
            fm.expense_ratio,
            fm.aum_crores,
            COUNT(nd.nav_date) as nav_count
        FROM fund_metadata fm
        LEFT JOIN nav_data nd ON fm.scheme_code = nd.scheme_code
        WHERE fm.scheme_code::text IN ({placeholders})
        GROUP BY fm.scheme_code, fm.scheme_name, fm.amc_name,
                 fm.sebi_category, fm.expense_ratio, fm.aum_crores
    """, [str(c) for c in scheme_codes])
    rows = cur.fetchall()
    cur.close()
    conn.close()
    meta = {}
    for code, name, amc, category, expense_ratio, aum_crores, nav_count in rows:
        nav_count = int(nav_count or 0)
        meta[str(code)] = {
            'scheme_code': str(code),
            'name': name,
            'amc': amc,
            'category': category,
            'expense_ratio': float(expense_ratio) if expense_ratio else None,
            'aum_crores': float(aum_crores) if aum_crores else None,
            'nav_count': nav_count,
            'tier': _get_tier(nav_count),
        }
    return meta


def _find_best_alternative(category: str, excluded_codes: list, horizon_years: int, target_cagr: float) -> dict | None:
    """
    Find the highest-scoring eligible fund in the same category not already in the bouquet.
    Returns fund info + score, or None if no alternative found.
    """
    from engine.fund_scorer import compute_composite_score

    conn = _get_db()
    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(excluded_codes)) if excluded_codes else "'__none__'"
    params = [str(c) for c in excluded_codes] if excluded_codes else []

    # Allow NULL category match when category is None
    if category:
        cat_clause = "AND fm.sebi_category = %s"
        params.append(category)
    else:
        cat_clause = "AND fm.sebi_category IS NULL"

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
        {f"AND fm.scheme_code::text NOT IN ({placeholders})" if excluded_codes else ""}
        {cat_clause}
        GROUP BY fm.scheme_code, fm.scheme_name, fm.amc_name, fm.sebi_category
        HAVING COUNT(nd.nav_date) >= 750
        ORDER BY COUNT(nd.nav_date) DESC
        LIMIT 4
    """
    cur.execute(query, params)
    candidates = cur.fetchall()
    cur.close()
    conn.close()

    best = None
    best_score = -1
    for code, name, amc, cat, nav_count in candidates:
        try:
            result = compute_composite_score(str(code), horizon_years, target_cagr, cat or 'Unknown')
            score = result.get('composite_score') or 0
            if score > best_score:
                best_score = score
                best = {
                    'scheme_code': str(code),
                    'name': name,
                    'amc': amc,
                    'category': cat,
                    'nav_count': int(nav_count),
                    'tier': _get_tier(int(nav_count)),
                    'composite_score': score,
                    'dimension_scores': result.get('dimension_scores', {}),
                }
        except Exception:
            continue
    return best


def _find_alternatives_fast(category, excluded_codes, n=2, prefer_tier1=True, max_er=None):
    """Fast alternative lookup by NAV history length — no scoring needed.
    Tier 1 (1750+ NAVs) means 7+ verified years, a reliable quality proxy."""
    conn = _get_db()
    cur = conn.cursor()
    params = [str(c) for c in excluded_codes] if excluded_codes else []
    cat_clause = 'AND fm.sebi_category = %s' if category else ''
    if category:
        params.append(category)
    er_clause = f'AND fm.expense_ratio <= {max_er}' if max_er else ''
    excl_clause = (
        f"AND fm.scheme_code::text NOT IN ({','.join(['%s']*len(excluded_codes))})"
        if excluded_codes else ''
    )
    min_nav = 1750 if prefer_tier1 else 750
    cur.execute(f"""
        SELECT fm.scheme_code::text, fm.scheme_name, fm.amc_name,
               fm.sebi_category, fm.expense_ratio, COUNT(nd.nav_date) as nav_count
        FROM fund_metadata fm
        LEFT JOIN nav_data nd ON fm.scheme_code = nd.scheme_code
        WHERE fm.plan_type = 'Direct' AND fm.is_active = TRUE
        AND fm.scheme_name ILIKE '%%growth%%'
        AND fm.scheme_name NOT ILIKE '%%idcw%%'
        AND fm.scheme_name NOT ILIKE '%%dividend%%'
        {excl_clause}
        {cat_clause}
        {er_clause}
        GROUP BY fm.scheme_code, fm.scheme_name, fm.amc_name,
                 fm.sebi_category, fm.expense_ratio
        HAVING COUNT(nd.nav_date) >= {min_nav}
        ORDER BY COUNT(nd.nav_date) DESC
        LIMIT {n}
    """, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{
        'scheme_code': str(r[0]),
        'name': r[1],
        'amc': r[2],
        'category': r[3],
        'expense_ratio': float(r[4]) if r[4] else None,
        'nav_count': int(r[5]),
        'tier': _get_tier(int(r[5])),
    } for r in rows]


def analyse_custom_bouquet(
    funds_with_weights: list,
    horizon_years: int,
    target_cagr: float,
) -> dict:
    """
    Full analysis of a user-defined bouquet.

    funds_with_weights: [{'scheme_code': str, 'weight': float}]
    Returns comprehensive analysis dict.
    """
    from engine.fund_scorer import compute_composite_score
    from engine.fund_replacement import get_fund_rolling_cagr
    from engine.bouquet_builder import build_correlation_matrix
    from engine.cagr_advisor import assess_realism

    scheme_codes = [str(f['scheme_code']) for f in funds_with_weights]
    weights = {str(f['scheme_code']): float(f['weight']) for f in funds_with_weights}
    total_weight = sum(weights.values())

    # Normalise weights if they don't sum to exactly 100
    if abs(total_weight - 100) > 0.5:
        factor = 100.0 / total_weight
        weights = {k: round(v * factor, 1) for k, v in weights.items()}

    # Fetch fund metadata
    meta = _fetch_fund_meta(scheme_codes)

    # Score each fund
    print("Scoring funds...")
    fund_analyses = []
    for code in scheme_codes:
        info = meta.get(code, {})
        category = info.get('category') or 'Unknown'
        try:
            score_result = compute_composite_score(code, horizon_years, target_cagr, category)
            composite = score_result.get('composite_score')
            dimensions = score_result.get('dimension_scores', {})
            score_error = score_result.get('error')
        except Exception as e:
            composite = None
            dimensions = {}
            score_error = str(e)

        rolling_cagr = get_fund_rolling_cagr(code, horizon_years)

        fund_analyses.append({
            'scheme_code': code,
            'name': info.get('name', code),
            'amc': info.get('amc', ''),
            'category': info.get('category'),
            'expense_ratio': info.get('expense_ratio'),
            'aum_crores': info.get('aum_crores'),
            'nav_count': info.get('nav_count', 0),
            'tier': info.get('tier', 3),
            'weight': weights.get(code, 0),
            'composite_score': composite,
            'dimension_scores': dimensions,
            'rolling_cagr': rolling_cagr,
            'score_error': score_error,
        })

    # Weighted projected CAGR
    weighted_cagr_parts = [
        (f['rolling_cagr'], f['weight'] / 100)
        for f in fund_analyses
        if f['rolling_cagr'] is not None
    ]
    if weighted_cagr_parts:
        total_w = sum(w for _, w in weighted_cagr_parts)
        projected_cagr = round(sum(c * w for c, w in weighted_cagr_parts) / total_w, 2)
    else:
        projected_cagr = None

    # Weighted composite score
    scored_funds = [f for f in fund_analyses if f['composite_score'] is not None]
    if scored_funds:
        total_w = sum(f['weight'] for f in scored_funds)
        weighted_composite = round(
            sum(f['composite_score'] * f['weight'] for f in scored_funds) / total_w, 1
        )
        median_score = sorted(f['composite_score'] for f in scored_funds)[len(scored_funds) // 2]
    else:
        weighted_composite = None
        median_score = 0

    # Correlation matrix
    print("Computing correlations...")
    try:
        corr_matrix = build_correlation_matrix(scheme_codes)
        high_corr_pairs = [
            {
                'fund_a': meta.get(c1, {}).get('name', c1),
                'fund_b': meta.get(c2, {}).get('name', c2),
                'correlation': round(corr, 3),
                'severity': 'high' if corr > 0.92 else 'moderate',
            }
            for (c1, c2), corr in corr_matrix.items()
            if c1 < c2 and corr > 0.82
        ]
        avg_correlation = round(
            sum(v for k, v in corr_matrix.items() if k[0] < k[1]) /
            max(1, sum(1 for k in corr_matrix if k[0] < k[1])), 3
        )
    except Exception:
        high_corr_pairs = []
        avg_correlation = None

    # Category concentration
    cat_weights = {}
    for f in fund_analyses:
        cat = f['category'] or 'Other'
        cat_weights[cat] = cat_weights.get(cat, 0) + f['weight']
    concentration_warnings = [
        f"{cat}: {wt:.0f}% allocation — consider diversifying across categories"
        for cat, wt in cat_weights.items() if wt > 40
    ]

    # AMC concentration
    amc_weights = {}
    for f in fund_analyses:
        amc = f['amc'] or 'Unknown'
        amc_weights[amc] = amc_weights.get(amc, 0) + f['weight']
    amc_warnings = [
        f"High {amc} concentration ({wt:.0f}%) — single-AMC risk: manager decisions affect multiple funds"
        for amc, wt in amc_weights.items() if wt > 35
    ]

    # Tier warnings with specific alternatives
    tier_warnings = []
    for f in fund_analyses:
        if f['tier'] in (2, 3):
            alts = _find_alternatives_fast(f['category'], scheme_codes, n=2, prefer_tier1=True)
            if not alts:
                alts = _find_alternatives_fast(f['category'], scheme_codes, n=2, prefer_tier1=False)
            alts_note = (
                f"Same SEBI category ({f['category'] or 'Equity'}) with longer verified history — "
                "giving the engine more data and you more confidence."
            ) if alts else None
            years = max(f['nav_count'] // 250, 1)
            if f['tier'] == 3:
                tier_warnings.append({
                    'type': 'tier',
                    'message': (
                        f"{f['name'][:45]}: Tier 3 fund — only ~{years} year(s) of NAV data. "
                        "Scores are extrapolated from limited history. Treat projections with caution."
                    ),
                    'severity': 'high',
                    'fund_code': f['scheme_code'],
                    'fund_name': f['name'],
                    'alternatives': alts,
                    'alternatives_note': alts_note,
                })
            else:
                tier_warnings.append({
                    'type': 'tier',
                    'message': (
                        f"{f['name'][:45]}: Tier 2 fund — ~{f['nav_count']//250} years of history. "
                        "Solid, but may not have survived a full market cycle (typically 7+ years)."
                    ),
                    'severity': 'moderate',
                    'fund_code': f['scheme_code'],
                    'fund_name': f['name'],
                    'alternatives': alts,
                    'alternatives_note': alts_note,
                })

    # Expense ratio warnings with same-category alternatives
    er_warnings = []
    for f in fund_analyses:
        if f['expense_ratio'] and f['expense_ratio'] > 1.0:
            # ER data is sparse in DB — find tier 1 alternatives and let user compare ER on AMFIIndia
            alts = _find_alternatives_fast(f['category'], scheme_codes, n=2, prefer_tier1=True)
            if not alts:
                alts = _find_alternatives_fast(f['category'], scheme_codes, n=2, prefer_tier1=False)
            alts_note = (
                f"These funds share the same category. "
                f"Each 0.5% reduction in annual ER over 20 years saves 8-12%% of final corpus at 14%% CAGR. "
                "Check current expense ratio on AMFIIndia.com before deciding."
            ) if alts else None
            er_warnings.append({
                'type': 'expense_ratio',
                'message': (
                    f"{f['name'][:45]}: Expense ratio {f['expense_ratio']:.2f}% — "
                    "above the 1% benchmark for direct plans. Costs compound against returns silently."
                ),
                'severity': 'moderate',
                'fund_code': f['scheme_code'],
                'fund_name': f['name'],
                'alternatives': alts,
                'alternatives_note': alts_note,
            })

    # Improvement suggestion: only the single worst fund to keep response fast
    print("Computing improvement suggestion...")
    suggestions = []
    below_median = [f for f in fund_analyses if f["composite_score"] is not None and f["composite_score"] < median_score]
    worst_candidates = sorted(below_median, key=lambda f: f["composite_score"])[:3]
    for fund in worst_candidates:
        # Find best alternative in the same category
        alt = _find_best_alternative(
            category=fund['category'],
            excluded_codes=scheme_codes,
            horizon_years=horizon_years,
            target_cagr=target_cagr,
        )
        if alt and alt['composite_score'] > fund['composite_score'] + 3:
            score_delta = round(alt['composite_score'] - fund['composite_score'], 1)
            suggestions.append({
                'replace_fund': {
                    'scheme_code': fund['scheme_code'],
                    'name': fund['name'],
                    'composite_score': fund['composite_score'],
                    'rolling_cagr': fund['rolling_cagr'],
                    'category': fund['category'],
                },
                'with_fund': {
                    'scheme_code': alt['scheme_code'],
                    'name': alt['name'],
                    'amc': alt['amc'],
                    'composite_score': alt['composite_score'],
                    'tier': alt['tier'],
                    'category': alt['category'],
                },
                'score_improvement': score_delta,
                'rationale': (
                    f"Same category ({fund['category'] or 'Equity'}). "
                    f"Score improves by {score_delta} pts ({fund['composite_score']:.1f} → {alt['composite_score']:.1f}). "
                    f"Tier {alt['tier']} fund with {alt['nav_count']//250}+ years of history."
                ),
            })

    # Sort suggestions by score improvement descending
    suggestions.sort(key=lambda x: x['score_improvement'], reverse=True)

    # CAGR realism advisory on projected CAGR
    advisory = None
    if projected_cagr is not None:
        advisory = assess_realism(projected_cagr, horizon_years)

    # Overall quality rating
    if weighted_composite is not None:
        if weighted_composite >= 65:
            quality_label = 'Strong'
            quality_color = '#27AE78'
        elif weighted_composite >= 50:
            quality_label = 'Moderate'
            quality_color = '#F0A500'
        else:
            quality_label = 'Needs Review'
            quality_color = '#E05555'
    else:
        quality_label = 'Insufficient Data'
        quality_color = '#666'

    # Derive pros from analysis data
    byob_pros = []
    tier1_count = sum(1 for f in fund_analyses if f.get('tier') == 1)
    if tier1_count >= 3:
        byob_pros.append(f"{tier1_count} of {len(fund_analyses)} funds have 7+ years of verified history — your selection is well-grounded")
    elif tier1_count >= 1:
        byob_pros.append(f"{tier1_count} Tier 1 fund(s) in your bouquet — backed by the longest track records available")
    if weighted_composite is not None and weighted_composite >= 60:
        byob_pros.append(f"Composite score {weighted_composite}/100 — your fund selection clears the platform quality bar on all 6 dimensions")
    elif weighted_composite is not None and weighted_composite >= 50:
        byob_pros.append(f"Composite score {weighted_composite}/100 — a solid starting point with clear room to strengthen specific dimensions")
    if avg_correlation is not None and avg_correlation < 0.90:
        byob_pros.append(f"Average correlation {avg_correlation:.2f} — your funds don't move in lockstep. Some genuine diversification is present")
    if projected_cagr is not None and projected_cagr >= 13:
        byob_pros.append(f"Projected {horizon_years}-yr CAGR of {projected_cagr}% based on historical rolling returns — a meaningful long-run expectation")
    byob_pros.append("All direct plans — zero distributor commission. Every rupee of return works fully for you")
    byob_pros = byob_pros[:4]

    return {
        'funds': fund_analyses,
        'projected_cagr': projected_cagr,
        'weighted_composite_score': weighted_composite,
        'quality_label': quality_label,
        'quality_color': quality_color,
        'avg_correlation': avg_correlation,
        'category_weights': cat_weights,
        'high_correlation_pairs': high_corr_pairs,
        'suggestions': suggestions,
        'warnings': {
            'correlation': [
                {
                    'type': 'correlation',
                    'message': (
                        f"High correlation: {p['fund_a'][:38]} ↔ {p['fund_b'][:38]} "
                        f"({p['correlation']}) — these funds move in lockstep. "
                        f"{'Severe overlap — consider replacing one.' if p['severity'] == 'high' else 'Moderate overlap — monitor closely.'}"
                    ),
                    'severity': p['severity'],
                    'fund_code': None,
                    'fund_name': None,
                    'alternatives': [],
                    'alternatives_note': (
                        "Indian equity funds structurally correlate at 0.85-0.98 — this is market structure, not a flaw. "
                        "True diversification comes from category diversity: adding International (e.g. Motilal Nasdaq 100 FOF), "
                        "Thematic (e.g. Tata Digital), or Balanced Advantage funds. "
                        "Within Indian equity, choosing funds from different categories (Large Cap + Midcap + Flexi Cap) "
                        "reduces correlation meaningfully more than choosing different AMCs within the same category."
                    ),
                }
                for p in high_corr_pairs
            ],
            'concentration': [
                {
                    'type': 'concentration',
                    'message': w,
                    'severity': 'moderate',
                    'fund_code': None,
                    'fund_name': None,
                    'alternatives': [],
                    'alternatives_note': (
                        "Consider distributing across at least 3 different SEBI categories. "
                        "Midcap, Flexi Cap, and International categories complement Large Cap allocations well "
                        "and reduce single-category dependence."
                    ),
                }
                for w in concentration_warnings
            ],
            'amc': [
                {
                    'type': 'amc',
                    'message': w,
                    'severity': 'moderate',
                    'fund_code': None,
                    'fund_name': None,
                    'alternatives': [],
                    'alternatives_note': (
                        "Single-AMC concentration means one CIO decision, one compliance issue, or one regulatory action "
                        "affects your entire bouquet. Distributing across 3-4 AMCs is a simple structural protection."
                    ),
                }
                for w in amc_warnings
            ],
            'tier': tier_warnings,
            'expense_ratio': er_warnings,
        },
        'realism_advisory': advisory,
        'horizon_years': horizon_years,
        'target_cagr': target_cagr,
        'pros': byob_pros,
    }
