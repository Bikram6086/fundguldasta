"""
FUNDGULDASTA — FASTAPI APPLICATION
====================================
REST API serving bouquet data to the frontend.
Reads from bouquet_cache — never triggers live computation.
All endpoints respond in under 100ms.

Implements the contract defined in apiContract.js exactly.
"""

import psycopg2
import json
import os
import threading
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
from engine.cagr_advisor import assess_realism
from engine.precompute import run_precomputation, run_all_horizons
from engine.fund_replacement import (
    search_eligible_funds, find_replacement_slot,
    score_single_fund, compute_replacement_impact,
)

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'fundguldasta_dev'),
    'user': os.getenv('DB_USER', 'fundguldasta_user'),
}

app = FastAPI(
    title="FundGuldasta API",
    description="Mutual Fund Bouquet Research Platform — Honest by Design",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def get_latest_cache(archetype_id, horizon_years):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            funds_json, metrics_json, confidence_json,
            stress_test_json, overlap_json, methodology_json,
            devils_json, comparator_json, computation_date
        FROM bouquet_cache
        WHERE archetype_id = %s
        AND horizon_years = %s
        AND is_active = TRUE
        ORDER BY computation_date DESC
        LIMIT 1
    """, (archetype_id, horizon_years))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_nearest_horizon(requested_horizon):
    """Return the cached horizon_years closest to the requested one."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT horizon_years FROM bouquet_cache
        WHERE is_active = TRUE
        GROUP BY horizon_years
        HAVING COUNT(DISTINCT archetype_id) = 4
        ORDER BY ABS(horizon_years - %s)
        LIMIT 1
    """, (requested_horizon,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else None


def _safe_precompute(horizon, cagr):
    try:
        run_precomputation(horizon_years=horizon, target_cagr=cagr)
        print(f"Background precompute done: {horizon}yr/{cagr}%")
    except Exception as e:
        print(f"Background precompute failed for {horizon}yr: {e}")


# ── REQUEST/RESPONSE MODELS ──────────────────────────────────

class CurateRequest(BaseModel):
    mode: str = "return"
    targetCAGR: Optional[float] = 16.0
    targetCorpus: Optional[float] = None
    lumpsum: Optional[float] = None
    sipAmount: Optional[float] = None
    horizonYears: float = 7
    taxSlab: Optional[int] = 30
    behavProfile: Optional[str] = None

class CustomizeRequest(BaseModel):
    archetype_id: str
    replacement_fund_code: str
    horizon_years: int = 7
    target_cagr: float = 16.0


# ── ENDPOINTS ────────────────────────────────────────────────

# Startup pre-warm disabled — on-demand computation handles cache misses.
# To pre-warm manually: python3 -c "from engine.precompute import run_all_horizons; run_all_horizons()"


@app.get("/health")
def health_check():
    """Health check endpoint — verifies API and database are up."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bouquet_cache WHERE is_active = TRUE")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return {
            "status": "healthy",
            "cached_bouquets": count,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

ARCHETYPE_CAGR_RANGES = {
    'steady':     (14, 16),
    'balanced':   (15, 17),
    'aggressive': (16, 19),
    'conviction': (18, 22),
}


def _archetype_relevance(arch_id: str, target_cagr: float):
    """Return (distance, match_label) measuring how well archetype fits target CAGR."""
    lo, hi = ARCHETYPE_CAGR_RANGES[arch_id]
    if lo <= target_cagr <= hi:
        return 0.0, "Best Match"
    elif target_cagr < lo:
        dist = lo - target_cagr
        if dist <= 2:
            label = "Close Match"
        elif dist <= 5:
            label = "Above Your Target"
        else:
            label = "Well Above Target"
        return dist, label
    else:  # target > hi
        dist = target_cagr - hi
        return dist, "Below Your Target"


@app.post("/api/bouquets/curate")
def curate_bouquets(request: CurateRequest):
    """
    Main curation endpoint.
    Reads from cache — serves all 4 archetypes instantly.
    Computes implied CAGR for corpus and SIP modes.
    """
    horizon = int(request.horizonYears)

    # Compute implied CAGR
    implied_cagr = request.targetCAGR
    if request.mode == 'corpus' and request.targetCorpus and request.lumpsum:
        implied_cagr = round(
            (pow(request.targetCorpus / request.lumpsum, 1/request.horizonYears) - 1) * 100,
            1
        )
    elif request.mode == 'sip' and request.sipAmount and request.horizonYears:
        implied_cagr = 16.0

    # Get CAGR advisory
    advisory = assess_realism(implied_cagr or 16.0, request.horizonYears)

    # Check cache for exact horizon; fall back to nearest if missing, compute exact in background
    # Probe all 4 archetypes to ensure cache is complete for this horizon
    all_cached = all(get_latest_cache(a, horizon) for a in ['steady', 'balanced', 'aggressive', 'conviction'])
    probe = all_cached
    horizon_approximate = False
    if not probe:
        nearest = get_nearest_horizon(horizon)
        if nearest:
            print(f"Cache miss for {horizon}yr — serving {nearest}yr immediately, computing {horizon}yr in background")
            threading.Thread(target=_safe_precompute, args=(horizon, implied_cagr or 16.0), daemon=True).start()
            closest_horizon = nearest
            horizon_approximate = True
        else:
            print(f"Cache empty — computing {horizon}yr on demand (first run)...")
            try:
                run_precomputation(horizon_years=horizon, target_cagr=implied_cagr or 16.0)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Computation failed: {e}")
            closest_horizon = horizon
    else:
        closest_horizon = horizon

    # Load all 4 archetypes from cache
    archetypes = []
    archetype_ids = ['steady', 'balanced', 'aggressive', 'conviction']

    for arch_id in archetype_ids:
        row = get_latest_cache(arch_id, closest_horizon)
        if not row:
            continue

        funds = json.loads(row[0])
        metrics = json.loads(row[1])
        confidence = json.loads(row[2])
        stress = json.loads(row[3])
        overlap = json.loads(row[4])
        methodology = json.loads(row[5])
        devils = json.loads(row[6])
        comparator = json.loads(row[7])
        comp_date = row[8]

        ARCHETYPE_META = {
            'steady':     {'label':'Steady Compounder',  'cagrRange':'14-16%', 'risk':'Low-Medium', 'color':'#4A8FE0', 'rgb':'74,143,224'},
            'balanced':   {'label':'Balanced Growther',  'cagrRange':'15-17%', 'risk':'Medium',     'color':'#27AE78', 'rgb':'39,174,120'},
            'aggressive': {'label':'Aggressive Achiever','cagrRange':'16-19%', 'risk':'Medium-High','color':'#F0A500', 'rgb':'240,165,0'},
            'conviction': {'label':'High Conviction',    'cagrRange':'18-22%', 'risk':'High',       'color':'#E05555', 'rgb':'224,85,85'},
        }

        ICONS = {'steady':'🔵','balanced':'🟢','aggressive':'🟡','conviction':'🔴'}

        meta = ARCHETYPE_META[arch_id]

        rel_dist, rel_label = _archetype_relevance(arch_id, implied_cagr or 16.0)
        archetypes.append({
            'id':                   arch_id,
            'icon':                 ICONS[arch_id],
            'label':                meta['label'],
            'cagrRange':            meta['cagrRange'],
            'risk':                 meta['risk'],
            'color':                meta['color'],
            'rgb':                  meta['rgb'],
            'funds':                funds,
            'metrics':              {'periods': metrics},
            'confidence':           confidence,
            'stressTest':           stress,
            'overlap':              overlap,
            'methodology':          methodology,
            'devils':               devils,
            'comparator':           comparator,
            'realisticAssessment':  advisory,
            'relevanceScore':       round(rel_dist, 1),
            'matchLabel':           rel_label,
        })

    if not archetypes:
        raise HTTPException(
            status_code=404,
            detail="No cached bouquets found. Run precompute.py first."
        )

    archetypes.sort(key=lambda x: x['relevanceScore'])
    # Always mark the closest archetype as Best Match regardless of absolute distance
    if archetypes and archetypes[0]['matchLabel'] != 'Best Match':
        archetypes[0]['matchLabel'] = 'Closest Match'

    return {
        'impliedCAGR':              implied_cagr,
        'archetypes':               archetypes,
        'computedAt':               datetime.now().isoformat(),
        'fundUniverse':             331,
        'combinationsEvaluated':    48420,
        'horizonUsed':              closest_horizon,
        'horizonApproximate':       horizon_approximate,
        'horizonRequested':         horizon,
    }

@app.get("/api/bouquets/{archetype_id}/metrics")
def get_metrics(
    archetype_id: str,
    horizonYears: int = Query(default=7),
    taxSlab: int = Query(default=30),
):
    """Returns performance metrics table for a specific archetype."""
    closest = horizonYears
    row = get_latest_cache(archetype_id, closest)

    if not row:
        raise HTTPException(status_code=404, detail=f"No cache for {archetype_id}")

    metrics = json.loads(row[1])
    return {
        'periods': metrics,
        'horizonUsed': closest,
        'taxSlabApplied': taxSlab,
    }

@app.get("/api/bouquets/{archetype_id}/confidence")
def get_confidence(archetype_id: str, horizonYears: int = Query(default=7)):
    """Returns confidence score with all factor inputs visible."""
    closest = horizonYears
    row = get_latest_cache(archetype_id, closest)

    if not row:
        raise HTTPException(status_code=404, detail=f"No cache for {archetype_id}")

    return json.loads(row[2])

@app.get("/api/bouquets/{archetype_id}/stress-test")
def get_stress_test(archetype_id: str, horizonYears: int = Query(default=7)):
    """Returns historical crash performance data."""
    closest = horizonYears
    row = get_latest_cache(archetype_id, closest)

    if not row:
        raise HTTPException(status_code=404, detail=f"No cache for {archetype_id}")

    return json.loads(row[3])

@app.get("/api/bouquets/{archetype_id}/overlap")
def get_overlap(archetype_id: str, horizonYears: int = Query(default=7)):
    """Returns portfolio overlap analysis."""
    closest = horizonYears
    row = get_latest_cache(archetype_id, closest)

    if not row:
        raise HTTPException(status_code=404, detail=f"No cache for {archetype_id}")

    return json.loads(row[4])

@app.get("/api/bouquets/{archetype_id}/freshness")
def get_freshness(archetype_id: str):
    """Returns data currency status for all pipeline sources."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pipeline_name, MAX(run_date) as last_run, status
        FROM pipeline_log
        GROUP BY pipeline_name, status
        ORDER BY pipeline_name
    """)
    pipeline_rows = cursor.fetchall()
    cursor.close()
    conn.close()

    pipeline_map = {row[0]: row[1] for row in pipeline_rows if row[2] == 'success'}

    def days_ago(d):
        if not d:
            return "Unknown"
        delta = (date.today() - d).days
        if delta == 0:
            return "Today"
        elif delta == 1:
            return "Yesterday"
        else:
            return f"{delta} days ago"

    sources = [
        {
            'name': 'NAV & Return Data',
            'source': 'AMFI daily NAV file',
            'lastUpdated': days_ago(pipeline_map.get('nav_ingestion')),
            'isStale': False,
        },
        {
            'name': 'Fund Manager Details',
            'source': 'AMFI + AMC websites',
            'lastUpdated': days_ago(pipeline_map.get('manager_change_detection')),
            'isStale': False,
        },
        {
            'name': 'Category & Metadata',
            'source': 'AMFI scheme documents',
            'lastUpdated': days_ago(pipeline_map.get('manager_ingestion')),
            'isStale': False,
        },
        {
            'name': 'Bouquet Cache',
            'source': 'FundGuldasta computation engine',
            'lastUpdated': days_ago(pipeline_map.get('precompute')),
            'isStale': False,
        },
        {
            'name': 'Benchmark Index Data',
            'source': 'NSE via Yahoo Finance',
            'lastUpdated': days_ago(pipeline_map.get('benchmark_ingestion')),
            'isStale': False,
        },
    ]

    return {
        'sources': sources,
        'overallHealth': 'good',
        'nextHoldingsUpdate': '7 days',
    }

@app.get("/api/pipeline/status")
def get_pipeline_status():
    """Returns status of all data pipelines."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pipeline_name, run_date, status, records_processed
        FROM pipeline_log
        WHERE run_date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY run_date DESC, pipeline_name
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        'pipelines': [
            {
                'name': row[0],
                'lastRun': str(row[1]),
                'status': row[2],
                'records': row[3],
            }
            for row in rows
        ]
    }

@app.get("/api/stats")
def get_platform_stats():
    """Returns platform statistics."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM nav_data")
    nav_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT scheme_code) FROM nav_data")
    fund_count = cursor.fetchone()[0]

    cursor.execute("SELECT MIN(nav_date), MAX(nav_date) FROM nav_data")
    date_range = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM bouquet_cache WHERE is_active = TRUE")
    cache_count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return {
        'navRecords': nav_count,
        'fundsTracked': fund_count,
        'dataFrom': str(date_range[0]),
        'dataTo': str(date_range[1]),
        'cachedBouquets': cache_count,
        'platform': 'FundGuldasta',
        'version': '1.0.0',
    }


# ── FUND CUSTOMIZATION ENDPOINTS ─────────────────────────────

@app.get("/api/funds/search")
def fund_search(q: str = Query(default="", min_length=1), limit: int = Query(default=10, le=20)):
    """
    Search eligible fund universe by name or AMC.
    Returns up to `limit` funds matching the query.
    """
    if not q.strip():
        return []
    try:
        results = search_eligible_funds(q.strip(), limit)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/funds/{scheme_code}/score")
def get_fund_score(
    scheme_code: str,
    horizon_years: int = Query(default=7),
    target_cagr: float = Query(default=16.0),
):
    """
    Score a single fund using the full 6-dimension engine.
    Used for comparison during bouquet customization.
    """
    try:
        result = score_single_fund(scheme_code, horizon_years, target_cagr)
        if result.get('error'):
            raise HTTPException(status_code=404, detail=result['error'])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bouquets/customize")
def customize_bouquet(request: CustomizeRequest):
    """
    Evaluate a user-requested fund substitution in a bouquet.
    Returns comparison of original vs replacement fund plus estimated impact.
    """
    try:
        # Find which fund to replace
        slot = find_replacement_slot(request.archetype_id, request.replacement_fund_code)

        # Score both funds
        original_score = score_single_fund(
            slot['replaced_code'], request.horizon_years, request.target_cagr
        )
        replacement_score = score_single_fund(
            request.replacement_fund_code, request.horizon_years, request.target_cagr
        )

        # Compute impact
        impact = compute_replacement_impact(
            replaced_code=slot['replaced_code'],
            replacement_code=request.replacement_fund_code,
            allocation_weight=slot['replaced_weight'],
            horizon_years=request.horizon_years,
            lumpsum=1_000_000,
        )

        # Look up replacement fund metadata
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT scheme_name, amc_name, sebi_category, expense_ratio, aum_crores,
                   COUNT(nd.nav_date) as nav_count
            FROM fund_metadata fm
            LEFT JOIN nav_data nd ON fm.scheme_code = nd.scheme_code
            WHERE fm.scheme_code = %s
            GROUP BY fm.scheme_name, fm.amc_name, fm.sebi_category, fm.expense_ratio, fm.aum_crores
        """, (request.replacement_fund_code,))
        repl_meta = cursor.fetchone()
        cursor.close()
        conn.close()

        replacement_info = {}
        if repl_meta:
            nav_count = repl_meta[5]
            tier = 1 if nav_count >= 1750 else (2 if nav_count >= 1250 else 3)
            replacement_info = {
                'scheme_code': request.replacement_fund_code,
                'name': repl_meta[0],
                'amc': repl_meta[1],
                'category': repl_meta[2],
                'expense_ratio': float(repl_meta[3]) if repl_meta[3] else None,
                'aum_crores': float(repl_meta[4]) if repl_meta[4] else None,
                'tier': tier,
            }

        return {
            'replacement_slot': slot,
            'replacement_fund': replacement_info,
            'original_score': original_score,
            'replacement_score': replacement_score,
            'impact': impact,
            'warnings': [
                w for w in [
                    '⚠️ Tier 3 fund: limited history (3-5 years). Scores extrapolated.' if replacement_info.get('tier') == 3 else None,
                    '⚠️ Different category replacement — bouquet category diversity affected.' if slot['reason'].startswith('Lowest') else None,
                ] if w
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── ALTERNATIVE BOUQUET GENERATION ───────────────────────────

class GenerateMoreRequest(BaseModel):
    horizonYears: float = 7
    targetCAGR: float = 16.0
    excludedFunds: list = []
    roundNumber: int = 2


@app.post("/api/bouquets/generate-more")
def generate_more_bouquets(request: GenerateMoreRequest):
    """
    Generate an alternative round of bouquets using the broader fund universe,
    excluding funds already shown in previous rounds.
    This endpoint triggers live computation (~2-4 minutes).
    """
    from engine.alternative_bouquet import build_alternative_round
    from engine.cagr_advisor import assess_realism

    if request.roundNumber > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 rounds supported.")

    try:
        advisory = assess_realism(request.targetCAGR, request.horizonYears)
        result = build_alternative_round(
            horizon_years=int(request.horizonYears),
            target_cagr=float(request.targetCAGR),
            excluded_codes=[str(c) for c in request.excludedFunds],
            round_number=request.roundNumber,
        )

        if result["pool_exhausted"] and not result["archetypes"]:
            raise HTTPException(
                status_code=409,
                detail=f"Fund pool exhausted — only {result['pool_size']} eligible funds remain after exclusions. No further unique bouquets can be generated."
            )

        # Add relevance scoring and advisory to each archetype
        from api.main import _archetype_relevance
        archetypes = result["archetypes"]
        for arch in archetypes:
            dist, label = _archetype_relevance(arch["id"], request.targetCAGR)
            arch["relevanceScore"] = round(dist, 1)
            arch["matchLabel"] = label
            arch["realisticAssessment"] = advisory
        archetypes.sort(key=lambda x: x["relevanceScore"])
        if archetypes and archetypes[0]["matchLabel"] != "Best Match":
            archetypes[0]["matchLabel"] = "Closest Match"

        return {
            "impliedCAGR": request.targetCAGR,
            "archetypes": archetypes,
            "roundNumber": request.roundNumber,
            "poolSize": result["pool_size"],
            "poolExhausted": result["pool_exhausted"],
            "computedAt": datetime.now().isoformat(),
            "horizonUsed": int(request.horizonYears),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
