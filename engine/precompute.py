"""
FUNDGULDASTA — PRE-COMPUTATION ENGINE (LAYER 5)
================================================
Nightly job that computes all bouquet combinations
and stores results in the bouquet_cache table.

The API reads from this cache — never triggers live
computation per user request. This keeps API response
times under 100ms regardless of computation complexity.

Computes: 4 archetypes × 6 horizons (5, 7, 10, 15, 20, 30yr) = 24 combinations
"""

import psycopg2
import json
import os
from datetime import datetime, date
from dotenv import load_dotenv
from engine.bouquet_builder import build_bouquet
from engine.dynamic_archetypes import build_dynamic_archetype_bouquet
from engine.confidence_scorer import compute_bouquet_confidence
from engine.risk_metrics import compute_crash_performance, CRASH_PERIODS
from engine.rolling_returns import get_nav_series
from config.scheme_codes import ARCHETYPE_FUNDS, VERIFIED_FUNDS

from config.db import get_db_config
DB_CONFIG = get_db_config()

ARCHETYPES = {
    'steady': {
        'label': 'Steady Compounder',
        'cagr_range': '14-16%',
        'risk': 'Low-Medium',
        'color': '#4A8FE0',
        'description': 'Large and flexi cap dominant. Lower volatility. For investors who need to stay invested through market cycles without watching their portfolio daily.',
        'devils': [
            'Balanced Advantage allocation may underperform in strong bull markets due to equity hedging',
            'International allocation in Parag Parikh adds currency risk not captured in historical INR returns',
            'Large cap dominance means this bouquet may lag mid/small cap options by 4-6% in bull cycles',
            'Historical 14-16% CAGR does not guarantee future returns — the next 7 years may deliver more or less',
            'Manager tenure data pending full verification — scores will improve as SID enrichment completes',
        ],
        'methodology': [
            'Large and flexi cap dominant — appropriate for investors requiring lower volatility',
            'International allocation via Parag Parikh provides genuine cross-market diversification',
            'All funds direct plans only — zero trail commission conflict',
            'Balanced Advantage inclusion provides equity hedging during expensive market phases',
            'Survivorship disclosure: 87 large/flexi cap funds wound up or merged in last 15 years',
        ],
    },
    'balanced': {
        'label': 'Balanced Growther',
        'cagr_range': '15-17%',
        'risk': 'Medium',
        'color': '#27AE78',
        'description': 'Diversified across large, mid and small cap with international exposure. Most commonly appropriate for 7+ year horizons.',
        'devils': [
            '55% mid and small cap exposure — portfolio can fall 40-55% in a sharp correction',
            'Requires staying fully invested through potentially 2-3 years of negative returns',
            'Motilal Oswal Nasdaq 100 FOF is taxed as a DEBT fund — income slab rate applies, not 12.5% LTCG',
            'Small cap allocation may face liquidity constraints during industry-wide panic redemptions',
            'High correlation between India small and mid cap — 45% of bouquet moves nearly in tandem in crashes',
        ],
        'methodology': [
            'Funds selected across 5 distinct SEBI categories — genuine category diversification',
            'Motilal Oswal Nasdaq 100 provides genuine international diversification — correlation 0.37 with Indian equity',
            'Each fund top 25% of category for 7-year rolling return consistency',
            'No two funds from same AMC — AMC concentration risk avoided',
            'All funds direct plans only — zero commission conflict',
            'Survivorship disclosure: 340+ equity funds wound up or merged in last 15 years',
        ],
        'intl_tax_warning': True,
    },
    'aggressive': {
        'label': 'Aggressive Achiever',
        'cagr_range': '16-19%',
        'risk': 'Medium-High',
        'color': '#F0A500',
        'description': 'Mid and small cap dominant. Higher return potential with higher volatility. Requires genuine long-term conviction.',
        'devils': [
            '75% mid and small cap exposure — this bouquet can fall 50-65% in a severe bear market',
            '3 of 5 funds in mid or small cap — category concentration exists despite different fund houses',
            'Quant Small Cap uses quantitative approach — different risk profile from fundamental managers',
            'Small cap funds can take 30-50 days to liquidate 50% of portfolio under SEBI stress tests',
            'Demands minimum 7-year commitment — exiting in year 3 or 4 in a downturn converts paper loss to real loss',
            'Mid and small cap valuations elevated relative to historical averages as of May 2026',
        ],
        'methodology': [
            'Mid and small cap dominant — appropriate for 7+ year horizon with high risk tolerance',
            'Three different fund managers across mid cap allocation — manager concentration reduced',
            'Quant Small Cap included for quantitative style diversification alongside fundamental managers',
            'No two funds from same AMC — different AMC philosophy and risk management',
            'All funds direct plans only',
            'Survivorship disclosure: 180+ mid and small cap funds wound up or merged in last 15 years',
        ],
    },
    'conviction': {
        'label': 'High Conviction',
        'cagr_range': '18-22%',
        'risk': 'High',
        'color': '#E05555',
        'description': 'Concentrated small cap and thematic. Highest historical return potential. Highest crash risk. Only for investors who have stayed invested through a 40%+ portfolio fall.',
        'devils': [
            'This bouquet can fall 60-70% in a severe bear market — Rs 10 Lakhs becomes Rs 3-4 Lakhs temporarily',
            'Recovery from a full crash at this concentration has historically taken 3+ years',
            'Tata Digital adds technology concentration — global tech correction hits this hard',
            '50% in small cap means redemption difficulty during market stress',
            'Historical high CAGR partly driven by exceptional post-COVID small cap recovery — may not repeat',
            'Confidence score reflects that target was beaten in only ~90% of rolling periods — not guaranteed',
            'Suitable ONLY for investors who have previously stayed invested through a 40%+ fall',
        ],
        'methodology': [
            'High conviction construction for maximum long-term return potential',
            'Quant AMC quantitative approach provides genuine style diversification',
            'Tata Digital 10% allocation limits but does not eliminate sectoral concentration risk',
            'All funds direct plans only',
            'Survivorship disclosure: 180+ small and mid cap funds wound up or merged in last 15 years',
        ],
    },
}

HORIZONS = [5, 7, 10, 15, 20, 30]
DEFAULT_TARGET_CAGR = 16

def compute_bouquet_stress_test(fund_weights):
    """Compute stress test data for a bouquet."""
    weighted_crashes = []

    for crash in CRASH_PERIODS:
        falls = []
        recoveries = []
        post_cagrs = []

        for scheme_code, weight in fund_weights:
            nav_series = get_nav_series(scheme_code)
            if nav_series is None:
                continue

            crashes = compute_crash_performance(nav_series, [crash])
            if crashes:
                c = crashes[0]
                falls.append((c['peak_fall_pct'], weight))
                if c['recovery_months']:
                    recoveries.append((c['recovery_months'], weight))
                if c['post_recovery_cagr']:
                    post_cagrs.append((c['post_recovery_cagr'], weight))

        if falls:
            total_w = sum(w for _, w in falls)
            avg_fall = sum(f * w for f, w in falls) / total_w
            avg_rec = None
            if recoveries:
                total_w = sum(w for _, w in recoveries)
                avg_rec = sum(r * w for r, w in recoveries) / total_w
            avg_post = None
            if post_cagrs:
                total_w = sum(w for _, w in post_cagrs)
                avg_post = sum(p * w for p, w in post_cagrs) / total_w

            weighted_crashes.append({
                'event': crash['name'],
                'peakFallPct': round(avg_fall, 1),
                'recoveryMonths': round(avg_rec, 1) if avg_rec else None,
                'postRecoveryCAGR': round(avg_post, 1) if avg_post else None,
            })

    return {'periods': weighted_crashes}

def compute_comparator(bouquet_cagr_7yr, horizon_years=7, investment=1000000):
    """Compute corpus comparison vs alternatives."""
    def corpus(cagr, years, principal):
        return round(principal * pow(1 + cagr/100, years) / 100000, 1)

    return {
        'bouquetCorpus': corpus(bouquet_cagr_7yr, horizon_years, investment),
        'niftyCorpus': corpus(12.0, horizon_years, investment),
        'fdCorpus': corpus(6.8, horizon_years, investment),
    }

def run_precomputation(horizon_years=7, target_cagr=DEFAULT_TARGET_CAGR):
    """
    Main pre-computation job.
    Builds and caches all 4 archetypes for a given horizon.
    """
    print(f"\n{'='*60}")
    print(f"PRE-COMPUTATION ENGINE")
    print(f"Horizon: {horizon_years} years | Target: {target_cagr}% CAGR")
    print(f"Started: {datetime.now()}")
    print(f"{'='*60}")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    results = {}

    for arch_id, arch_meta in ARCHETYPES.items():
        print(f"\nProcessing archetype: {arch_id.upper()}")
        try:
            bouquet = build_dynamic_archetype_bouquet(arch_id, horizon_years, target_cagr)
            if not bouquet:
                print(f"  FAILED to build bouquet for {arch_id}")
                continue

            fund_weights = [(f['scheme_code'], f['weight']) for f in bouquet['funds']]
            fund_details = [
                {
                    "scheme_code": f['scheme_code'],
                    "weight":      f['weight'],
                    "name":        f['name'],
                    "category":    f['category'],
                    "tier":        f.get('tier', 1),
                    "amc":         f['amc'],
                }
                for f in bouquet['funds']
            ]

            print(f"  Computing confidence score...")
            confidence = compute_bouquet_confidence(
                fund_weights, fund_details, horizon_years, target_cagr
            )

            print(f"  Computing stress test...")
            stress_test = compute_bouquet_stress_test(fund_weights)

            bouquet_7yr_cagr = bouquet["metrics"].get("7 Yr", {}).get("bouquet", 16)
            comparator = compute_comparator(bouquet_7yr_cagr, horizon_years)

            cache_entry = {
                "archetype_id": arch_id,
                "label": arch_meta["label"],
                "cagrRange": arch_meta["cagr_range"],
                "risk": arch_meta["risk"],
                "color": arch_meta["color"],
                "description": arch_meta["description"],
                "funds": bouquet["funds"],
                "metrics": bouquet["metrics"],
                "confidence": confidence,
                "stressTest": stress_test,
                "overlap": {
                    "avgOverlapPct": bouquet["avg_overlap_pct"],
                    "avgCorrelation": bouquet["avg_correlation"],
                },
                "methodology": arch_meta["methodology"],
                "devils": arch_meta["devils"],
                "comparator": comparator,
                "intlTaxWarning": arch_meta.get("intl_tax_warning", False),
            }

            cursor.execute("""
                INSERT INTO bouquet_cache (
                    archetype_id, horizon_years, target_cagr, computation_date,
                    funds_json, metrics_json, confidence_json, stress_test_json,
                    overlap_json, methodology_json, devils_json, comparator_json,
                    is_active
                ) VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (archetype_id, horizon_years, computation_date)
                DO UPDATE SET
                    funds_json       = EXCLUDED.funds_json,
                    metrics_json     = EXCLUDED.metrics_json,
                    confidence_json  = EXCLUDED.confidence_json,
                    stress_test_json = EXCLUDED.stress_test_json,
                    overlap_json     = EXCLUDED.overlap_json,
                    methodology_json = EXCLUDED.methodology_json,
                    devils_json      = EXCLUDED.devils_json,
                    comparator_json  = EXCLUDED.comparator_json,
                    is_active        = TRUE
            """, (
                arch_id, horizon_years, target_cagr,
                json.dumps(bouquet["funds"]),
                json.dumps(bouquet["metrics"]),
                json.dumps(confidence),
                json.dumps(stress_test),
                json.dumps({"avgOverlapPct": bouquet["avg_overlap_pct"],
                             "holdingsCoveragePct": bouquet.get("holdings_coverage_pct", 0),
                             "avgCorrelation": bouquet["avg_correlation"]}),
                json.dumps(arch_meta["methodology"]),
                json.dumps(arch_meta["devils"]),
                json.dumps(comparator),
            ))
            conn.commit()
            results[arch_id] = cache_entry
            print(f"  \u2705 {arch_id} cached \u2014 Confidence: {confidence['score']}/100 ({confidence['level']})")
        except Exception as arch_err:
            print(f"  \u274c {arch_id} FAILED: {arch_err}")
            try:
                conn.rollback()
            except Exception:
                pass

    cursor.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"PRE-COMPUTATION COMPLETE")
    print(f"Archetypes cached: {len(results)}")
    print(f"Completed: {datetime.now()}")
    print(f"{'='*60}")

    log_precompute_run('success', len(results))

    # Collect all R1 fund codes for exclusion in the alternative bouquet round
    r1_codes = list({
        f['scheme_code']
        for bouquet in results.values()
        for f in bouquet.get('funds', [])
    })

    import threading
    threading.Thread(
        target=lambda: _run_alt_precompute_safe(horizon_years, target_cagr, r1_codes),
        daemon=True,
    ).start()

    return results


def _run_alt_precompute_safe(horizon_years, target_cagr, r1_codes=None):
    try:
        run_alternative_precomputation(horizon_years, target_cagr, r1_fund_codes=r1_codes)
    except Exception as e:
        print(f"  Alternative precompute background thread failed: {e}")

def log_precompute_run(status, count, error=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pipeline_log
        (pipeline_name, run_date, started_at, completed_at, status, records_processed, error_message)
        VALUES ('precompute', CURRENT_DATE, NOW(), NOW(), %s, %s, %s)
    """, (status, count, error))
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    try:
        results = run_precomputation(horizon_years=7, target_cagr=16)
        log_precompute_run('success', len(results))

        print("\nVerifying cache contents:")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT archetype_id, horizon_years, computation_date,
                   is_active, created_at
            FROM bouquet_cache
            ORDER BY archetype_id
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        for row in rows:
            print(f"  ✅ {row[0]:<12} {row[1]} yrs  {row[2]}  active:{row[3]}")

    except Exception as e:
        print(f"ERROR: {e}")
        log_precompute_run('failed', 0, str(e))
        raise


def run_alternative_precomputation(horizon_years=7, target_cagr=16.0, r1_fund_codes: list | None = None):
    """
    Pre-compute round 2 alternative bouquets (excludes all Round 1 fund codes).
    Stores in bouquet_cache with archetype_ids like 'steady_r2'.
    r1_fund_codes: list of scheme_codes selected in Round 1 (passed by run_precomputation).
    Falls back to ARCHETYPE_FUNDS if not supplied (legacy path).
    """
    from engine.alternative_bouquet import build_alternative_round

    if r1_fund_codes:
        excluded = list(set(str(c) for c in r1_fund_codes))
    else:
        excluded = list(set(str(code) for codes in ARCHETYPE_FUNDS.values() for code, _ in codes))

    print(f"\n{'='*60}")
    print(f"ALTERNATIVE PRECOMPUTE (Round 2)")
    print(f"Horizon: {horizon_years}yr | Target: {target_cagr}% | Excluding {len(excluded)} Round-1 funds")
    print(f"{'='*60}")

    try:
        result = build_alternative_round(
            horizon_years=horizon_years,
            target_cagr=target_cagr,
            excluded_codes=excluded,
            round_number=2,
        )
    except Exception as e:
        print(f"  build_alternative_round failed: {e}")
        return {}

    if not result.get('archetypes'):
        print("  No alternative archetypes generated")
        return {}

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    saved = {}

    for arch in result['archetypes']:
        arch_id_r2 = f"{arch['id']}_r2"
        try:
            funds_json = arch.get('funds', [])
            metrics_obj = arch.get('metrics', {})
            periods = metrics_obj.get('periods', metrics_obj) if isinstance(metrics_obj, dict) else {}
            cursor.execute("""
                INSERT INTO bouquet_cache (
                    archetype_id, horizon_years, target_cagr, computation_date,
                    funds_json, metrics_json, confidence_json, stress_test_json,
                    overlap_json, methodology_json, devils_json, comparator_json,
                    is_active
                ) VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (archetype_id, horizon_years, computation_date)
                DO UPDATE SET
                    funds_json       = EXCLUDED.funds_json,
                    metrics_json     = EXCLUDED.metrics_json,
                    confidence_json  = EXCLUDED.confidence_json,
                    stress_test_json = EXCLUDED.stress_test_json,
                    overlap_json     = EXCLUDED.overlap_json,
                    methodology_json = EXCLUDED.methodology_json,
                    devils_json      = EXCLUDED.devils_json,
                    comparator_json  = EXCLUDED.comparator_json,
                    is_active        = TRUE
            """, (
                arch_id_r2, horizon_years, target_cagr,
                json.dumps(funds_json),
                json.dumps({'periods': periods}),
                json.dumps(arch.get('confidence', {})),
                json.dumps(arch.get('stressTest', {})),
                json.dumps(arch.get('overlap', {})),
                json.dumps(arch.get('methodology', [])),
                json.dumps(arch.get('devils', [])),
                json.dumps(arch.get('comparator', {})),
            ))
            conn.commit()
            saved[arch_id_r2] = True
            print(f"  ✅ {arch_id_r2} cached")
        except Exception as e:
            print(f"  ❌ {arch_id_r2} FAILED: {e}")
            try:
                conn.rollback()
            except Exception:
                pass

    cursor.close()
    conn.close()
    print(f"Alternative precompute done: {len(saved)} cached")
    return saved


def run_all_horizons(target_cagr: float = 16.0):
    """Pre-warm cache for all common horizons. Called at API startup in a background thread."""
    horizons = [5, 7, 10, 15, 20, 30]
    for h in horizons:
        try:
            run_precomputation(horizon_years=h, target_cagr=target_cagr)
            run_alternative_precomputation(horizon_years=h, target_cagr=target_cagr)
        except Exception as e:
            print(f"  run_all_horizons: skipped {h}yr — {e}")


def precompute_goal_bouquets(
    horizons: list | None = None,
    cagrs: list | None = None,
) -> dict:
    """
    Pre-compute and cache Goal Bouquet results for common (horizon, cagr) combos.
    Stores in bouquet_cache using archetype_id = 'goal_h{h}_c{c}'.
    Safe to run nightly — overwrites stale cache entries.
    """
    from engine.goal_bouquet import build_goal_bouquet

    if horizons is None:
        horizons = [5, 7, 10, 15, 20, 25, 30]
    if cagrs is None:
        cagrs = [12, 14, 16, 18, 20]

    total = len(horizons) * len(cagrs)
    print(f"\n{'='*60}")
    print(f"GOAL BOUQUET PRECOMPUTE — {total} combinations")
    print(f"Horizons: {horizons} | CAGR targets: {cagrs}")
    print(f"Started: {datetime.now()}")
    print(f"{'='*60}")

    done = 0
    skipped = 0
    failed = 0

    for h in horizons:
        for c in cagrs:
            label = f"h{h}_c{c}"
            try:
                result = build_goal_bouquet(
                    horizon_years=h,
                    target_cagr=float(c),
                    use_cache=False,
                    store_cache=True,
                )
                if result:
                    done += 1
                    n = result.get('universe_size', 0)
                    score = result.get('avg_fund_score', 0)
                    print(f"  ✅ {label}  universe={n}  avg_score={score}")
                else:
                    skipped += 1
                    print(f"  ⚠️  {label}  skipped — insufficient scored data")
            except Exception as e:
                failed += 1
                print(f"  ❌ {label}  FAILED: {e}")

    print(f"\nGoal bouquet precompute done: {done} cached, {skipped} skipped, {failed} failed")
    print(f"Completed: {datetime.now()}")
    return {'done': done, 'skipped': skipped, 'failed': failed}
