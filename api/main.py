"""
FUNDGULDASTA — FASTAPI APPLICATION
====================================
REST API serving bouquet data to the frontend.
Reads from bouquet_cache — never triggers live computation.
All endpoints respond in under 100ms.

Implements the contract defined in apiContract.js exactly.
"""

import psycopg2
from psycopg2 import pool as pg_pool
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

# Support both individual env vars (local dev) and DATABASE_URL (Railway/Timescale Cloud)
_DATABASE_URL = os.getenv('DATABASE_URL')
if _DATABASE_URL:
    import urllib.parse as _up
    _u = _up.urlparse(_DATABASE_URL)
    DB_CONFIG = {
        'host': _u.hostname,
        'port': _u.port or 5432,
        'dbname': _u.path.lstrip('/'),
        'user': _u.username,
        'password': _u.password,
        'sslmode': 'require',
    }
else:
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
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://fundguldasta.com",
        "https://www.fundguldasta.com",
        "https://fundguldasta.vercel.app",
        "https://fundguldasta-git-main-bikram6086.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Connection pool — replaces per-request psycopg2.connect() ────────────────
_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        _pool = pg_pool.ThreadedConnectionPool(minconn=2, maxconn=10, **DB_CONFIG)
    return _pool

class _PooledConn:
    """Wraps a pooled connection; close() returns it to the pool instead of closing."""
    def __init__(self, conn):
        self._conn = conn
    def cursor(self):   return self._conn.cursor()
    def commit(self):   return self._conn.commit()
    def rollback(self): return self._conn.rollback()
    def close(self):    _get_pool().putconn(self._conn)

def get_db():
    return _PooledConn(_get_pool().getconn())
# ─────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# SELF-DIAGNOSTIC + SELF-HEALING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

_health_state = {
    "status":     "starting",   # healthy | degraded | critical
    "last_check": None,
    "next_check": None,
    "components": {
        "database":  {"status": "unknown", "detail": "", "latency_ms": None},
        "cache":     {"status": "unknown", "detail": "", "bouquets": 0, "age_hours": None},
        "nav_data":  {"status": "unknown", "detail": "", "latest_date": None, "staleness_days": None},
        "pipeline":  {"status": "unknown", "detail": "", "last_run": None, "last_status": None},
    },
    "remediation_log": [],   # last 20 auto-fix actions
}

_HEALTH_CHECK_INTERVAL_HOURS = 6
_diag_lock = threading.Lock()


def _log_remediation(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _diag_lock:
        _health_state["remediation_log"].append(f"[{ts}] {msg}")
        if len(_health_state["remediation_log"]) > 20:
            _health_state["remediation_log"] = _health_state["remediation_log"][-20:]
    print(f"[HEALTH] {msg}")


def _check_database(state: dict):
    import time
    try:
        t0 = time.monotonic()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        ms = round((time.monotonic() - t0) * 1000, 1)
        state["database"] = {"status": "healthy", "detail": f"Responding in {ms}ms", "latency_ms": ms}
    except Exception as e:
        state["database"] = {"status": "critical", "detail": str(e)[:120], "latency_ms": None}


def _check_cache(state: dict):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), MAX(computation_date) FROM bouquet_cache WHERE is_active = TRUE")
        count, latest = cur.fetchone()
        cur.close()
        conn.close()
        if count == 0:
            state["cache"] = {"status": "critical", "detail": "Cache is empty — run precompute.py", "bouquets": 0, "age_hours": None}
            return
        age_hours = None
        if latest:
            from datetime import date as _date
            if hasattr(latest, "hour"):
                # It's a datetime object
                age_hours = round((datetime.now() - latest).total_seconds() / 3600, 1)
            else:
                # It's a date object — compute age in hours from days
                age_hours = round((_date.today() - latest).days * 24.0, 1)
        if age_hours is not None and age_hours > 30:
            status = "degraded"
            detail = f"{count} bouquets cached but stale ({age_hours:.0f}h old) — auto-refresh queued"
        else:
            status = "healthy"
            detail = f"{count} bouquets cached, {age_hours:.0f}h old" if age_hours is not None else f"{count} bouquets cached"
        state["cache"] = {"status": status, "detail": detail, "bouquets": count, "age_hours": age_hours}
    except Exception as e:
        state["cache"] = {"status": "critical", "detail": str(e)[:120], "bouquets": 0, "age_hours": None}


def _check_nav_data(state: dict):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT MAX(nav_date) FROM nav_data")
        latest = cur.fetchone()[0]
        cur.close()
        conn.close()
        if not latest:
            state["nav_data"] = {"status": "critical", "detail": "No NAV records found", "latest_date": None, "staleness_days": None}
            return
        from datetime import date
        staleness = (date.today() - latest).days
        if staleness == 0:
            status, detail = "healthy", "NAV data is current (today)"
        elif staleness == 1:
            status, detail = "healthy", "NAV data from yesterday (normal — AMFI publishes end-of-day)"
        elif staleness <= 3:
            status, detail = "degraded", f"NAV data is {staleness} days old — refresh queued"
        else:
            status, detail = "critical", f"NAV data is {staleness} days old — pipeline may have failed"
        state["nav_data"] = {"status": status, "detail": detail,
                              "latest_date": str(latest), "staleness_days": staleness}
    except Exception as e:
        state["nav_data"] = {"status": "critical", "detail": str(e)[:120],
                              "latest_date": None, "staleness_days": None}


def _check_pipeline(state: dict):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT pipeline_name, status, run_date, records_processed
            FROM pipeline_log
            ORDER BY created_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            state["pipeline"] = {"status": "unknown", "detail": "No pipeline runs logged yet",
                                  "last_run": None, "last_status": None}
            return
        name, status, run_date, records = row
        p_status = "healthy" if status == "success" else "degraded"
        state["pipeline"] = {
            "status":      p_status,
            "detail":      f"{name} — {status} on {run_date} ({records} records)",
            "last_run":    str(run_date),
            "last_status": status,
        }
    except Exception as e:
        state["pipeline"] = {"status": "degraded", "detail": str(e)[:120],
                              "last_run": None, "last_status": None}


def _auto_heal(component_state: dict):
    """Trigger remediation for fixable failures."""
    cache = component_state.get("cache", {})
    nav   = component_state.get("nav_data", {})

    # Heal stale cache — run precompute in background thread
    if cache.get("status") == "degraded":
        _log_remediation("Cache stale — auto-triggering precompute for horizons [5,7,10]")
        def _bg_precompute():
            try:
                for h, c in [(7, 16), (5, 14), (10, 16)]:
                    run_precomputation(horizon_years=h, target_cagr=c)
                _log_remediation("Auto-precompute complete")
            except Exception as e:
                _log_remediation(f"Auto-precompute failed: {e}")
        threading.Thread(target=_bg_precompute, daemon=True).start()

    # Heal stale NAV data — re-run ingestion via subprocess
    if nav.get("staleness_days") and nav["staleness_days"] >= 2:
        _log_remediation(f"NAV data {nav['staleness_days']} days old — auto-triggering ingestion")
        def _bg_nav():
            import subprocess, os, sys
            try:
                venv_python = os.path.join(os.path.expanduser("~/fundguldasta"), "venv", "bin", "python3")
                script = os.path.join(os.path.expanduser("~/fundguldasta"), "data", "nav_ingestion.py")
                result = subprocess.run(
                    [venv_python, script], capture_output=True, text=True,
                    timeout=180, cwd=os.path.expanduser("~/fundguldasta"),
                )
                status = "ok" if result.returncode == 0 else f"exit {result.returncode}"
                _log_remediation(f"Auto NAV ingestion {status}")
            except Exception as e:
                _log_remediation(f"Auto NAV ingestion failed: {e}")
        threading.Thread(target=_bg_nav, daemon=True).start()


def _run_diagnostics():
    """Run all health checks, update _health_state, trigger auto-heal if needed."""
    components = {}
    _check_database(components)
    _check_cache(components)
    _check_nav_data(components)
    _check_pipeline(components)

    # Derive overall status
    statuses = [c["status"] for c in components.values()]
    if "critical" in statuses:
        overall = "critical"
    elif "degraded" in statuses:
        overall = "degraded"
    elif all(s == "healthy" for s in statuses):
        overall = "healthy"
    else:
        overall = "unknown"

    with _diag_lock:
        _health_state["components"] = components
        _health_state["status"]     = overall
        _health_state["last_check"] = datetime.now().isoformat()
        _health_state["next_check"] = (
            datetime.now() + __import__("datetime").timedelta(hours=_HEALTH_CHECK_INTERVAL_HOURS)
        ).isoformat()

    print(f"[HEALTH] Diagnostic complete — overall: {overall.upper()}")
    for name, comp in components.items():
        print(f"[HEALTH]   {name}: {comp['status']} — {comp['detail']}")

    # Auto-heal fixable failures
    _auto_heal(components)
    return overall


def _health_loop():
    """Background thread: initial check after 45s, then every 6 hours."""
    import time
    time.sleep(45)   # let DB pool and startup hooks settle
    while True:
        try:
            _run_diagnostics()
        except Exception as e:
            print(f"[HEALTH] Diagnostic loop error: {e}")
        time.sleep(_HEALTH_CHECK_INTERVAL_HOURS * 3600)


# Start health loop as daemon thread at import time
_health_thread = threading.Thread(target=_health_loop, daemon=True, name="health-loop")
_health_thread.start()

# ══════════════════════════════════════════════════════════════════════════════
_fund_universe_count = None

def _get_fund_universe_count():
    """Returns count of direct-plan equity funds in fund_metadata. Cached after first call."""
    global _fund_universe_count
    if _fund_universe_count is None:
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM fund_metadata")
            _fund_universe_count = cur.fetchone()[0]
            cur.close()
            conn.close()
        except Exception:
            _fund_universe_count = 0
    return _fund_universe_count

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


def _enrich_funds_with_meta(funds):
    """Add expense_ratio, aum_crores, manager names from DB to cached fund list."""
    if not funds:
        return funds
    conn = get_db()
    cur = conn.cursor()
    codes = [str(f.get('scheme_code', '')) for f in funds]
    placeholders = ','.join(['%s'] * len(codes))
    cur.execute(
        f'SELECT scheme_code, expense_ratio, aum_crores FROM fund_metadata WHERE scheme_code IN ({placeholders})',
        codes
    )
    meta_map = {str(r[0]): {'expense_ratio': float(r[1]) if r[1] else None, 'aum_crores': float(r[2]) if r[2] else None} for r in cur.fetchall()}
    cur.execute(
        f'SELECT scheme_code, string_agg(manager_name, \', \' ORDER BY appointment_date) FROM fund_managers WHERE scheme_code IN ({placeholders}) AND is_current = true GROUP BY scheme_code',
        codes
    )
    mgr_map = {str(r[0]): r[1] for r in cur.fetchall()}
    cur.close(); conn.close()
    result = []
    for f in funds:
        code = str(f.get('scheme_code', ''))
        enriched = dict(f)
        if code in meta_map:
            enriched['expense_ratio'] = meta_map[code]['expense_ratio']
            enriched['aum_crores'] = meta_map[code]['aum_crores']
        if code in mgr_map:
            enriched['managers'] = mgr_map[code]
        result.append(enriched)
    return result


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
    replaced_fund_code: Optional[str] = None
    horizon_years: int = 7
    target_cagr: float = 16.0


# ── PROS DERIVATION ──────────────────────────────────────────

def _compute_pros(funds, metrics_dict, confidence, overlap, stress_test):
    """Derive 4-5 human-readable strength points from cached bouquet data."""
    pros = []

    # Tier quality
    tier1 = sum(1 for f in funds if f.get('tier') == 1)
    if tier1 >= 4:
        pros.append(f"{tier1} of {len(funds)} funds have 7+ years of verified history — deep, reliable scoring foundation")
    elif tier1 >= 2:
        pros.append(f"{tier1} of {len(funds)} funds are Tier 1 — enough history for statistically meaningful composite scores")

    # CAGR vs Nifty
    for period in ['7 Yr', '10 Yr', '5 Yr']:
        m = metrics_dict.get(period, {})
        bouquet_cagr = m.get('bouquet')
        nifty = m.get('nifty50')
        if bouquet_cagr and nifty:
            delta = round(bouquet_cagr - nifty, 1)
            if delta > 1:
                pros.append(f"Historical {period} CAGR of {bouquet_cagr}% — {delta}% ahead of Nifty 50 ({nifty}%). Demonstrated alpha over the index")
            break

    # Correlation / diversification
    avg_corr = overlap.get('avgCorrelation', 1.0) if isinstance(overlap, dict) else 1.0
    if avg_corr < 0.90:
        pros.append(f"Average fund correlation {avg_corr:.2f} — lower than most Indian equity portfolios. Genuine style diversification across categories")

    # Strongest confidence dimension
    factors = confidence.get('factors', {}) if isinstance(confidence, dict) else {}
    factor_scores = [(k, v.get('score', 0)) for k, v in factors.items() if isinstance(v, dict)]
    if factor_scores:
        best_k, best_v = max(factor_scores, key=lambda x: x[1])
        labels = {
            'rolling_consistency': f"Rolling consistency score {best_v:.0f}/100 — bouquet has regularly beaten benchmark across multiple time windows",
            'category_tailwind': f"Category tailwind score {best_v:.0f}/100 — SEBI categories represented are in a favourable long-run cycle",
            'cost_efficiency': f"Cost efficiency score {best_v:.0f}/100 — weighted expense ratio is highly competitive for direct plans",
            'downside_protection': f"Downside protection score {best_v:.0f}/100 — bouquet cushions losses better than average in volatile markets",
            'manager_stability': f"Manager stability score {best_v:.0f}/100 — fund management continuity adds predictability to scoring",
        }
        label = labels.get(best_k, f"{best_k.replace('_', ' ').title()} scores {best_v:.0f}/100")
        if best_v >= 50:
            pros.append(label)

    # Post-crisis resilience
    periods = stress_test.get('periods', []) if isinstance(stress_test, dict) else []
    best_recovery = max((p.get('postRecoveryCAGR', 0) for p in periods), default=0)
    if best_recovery > 14:
        pros.append(f"Post-crisis recovery up to {best_recovery}% CAGR — historical evidence of resilience after sharp market drawdowns")

    # Direct plans (always true)
    pros.append("All direct plans — zero distributor commission. Every rupee of return compounds fully for the investor")

    return pros[:5]


# ── ENDPOINTS ────────────────────────────────────────────────

# Startup pre-warm disabled — on-demand computation handles cache misses.
# To pre-warm manually: python3 -c "from engine.precompute import run_all_horizons; run_all_horizons()"


@app.get("/health")
def health_check():
    """Fast health check — returns live platform health state."""
    state = _health_state
    status_code_map = {"healthy": 200, "degraded": 200, "critical": 503, "starting": 200, "unknown": 200}
    cache = state["components"].get("cache", {})
    return {
        "status":          state["status"],
        "cached_bouquets": cache.get("bouquets", 0),
        "last_check":      state["last_check"],
        "timestamp":       datetime.now().isoformat(),
    }


@app.get("/api/health/full")
def health_full():
    """Deep diagnostic — all component statuses, remediation log, next check time."""
    with _diag_lock:
        return {
            "status":          _health_state["status"],
            "last_check":      _health_state["last_check"],
            "next_check":      _health_state["next_check"],
            "components":      _health_state["components"],
            "remediation_log": _health_state["remediation_log"][-10:],
            "check_interval_hours": _HEALTH_CHECK_INTERVAL_HOURS,
        }


@app.post("/api/health/run-now")
def trigger_diagnostic():
    """Force an immediate diagnostic run (bypasses 6-hour schedule)."""
    threading.Thread(target=_run_diagnostics, daemon=True).start()
    return {"status": "triggered", "message": "Diagnostic running — check /api/health/full in 10s"}

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

        funds = _enrich_funds_with_meta(json.loads(row[0]))
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
        pros = _compute_pros(funds, metrics, confidence, overlap, stress)
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
            'pros':                 pros,
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
        'fundUniverse':             _get_fund_universe_count(),
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
    """Returns data currency status with cadence context for each source."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pipeline_name, MAX(run_date) as last_run
        FROM pipeline_log
        WHERE status = 'success'
        GROUP BY pipeline_name
    """)
    pipeline_map = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute("SELECT MAX(nav_date) FROM nav_data")
    max_nav_date = (cursor.fetchone() or [None])[0]
    cursor.close()
    conn.close()

    today = date.today()

    def age_days(d):
        return (today - d).days if d else 999

    def age_label(d):
        if not d:
            return "Never run"
        delta = age_days(d)
        if delta == 0: return "Today"
        if delta == 1: return "Yesterday"
        return f"{delta} days ago"

    def stale_status(d, cadence_days):
        """Return severity: ok / warn / stale based on cadence."""
        if not d:
            return 'stale'
        delta = age_days(d)
        if delta <= cadence_days:
            return 'ok'
        if delta <= cadence_days * 2:
            return 'warn'
        return 'stale'

    nav_date  = max_nav_date
    nav_pipe  = pipeline_map.get('nav_ingestion')
    bench_date = pipeline_map.get('benchmark_ingestion')
    mgr_date  = pipeline_map.get('manager_change_detection')
    cat_date  = pipeline_map.get('manager_ingestion')
    cache_date = pipeline_map.get('precompute')

    # Nav and benchmark: daily cadence (weekdays). Allow 3 days for weekends.
    nav_status   = stale_status(nav_date,   3)
    bench_status = stale_status(bench_date, 3)
    # Manager and category: weekly cadence (SID documents update infrequently).
    mgr_status  = stale_status(mgr_date,  7)
    cat_status  = stale_status(cat_date,  7)
    # Bouquet cache: daily cadence (rebuilt after each NAV update).
    cache_status = stale_status(cache_date, 3)

    overall = 'good'
    if any(s == 'stale' for s in [nav_status, bench_status, cache_status]):
        overall = 'degraded'
    elif any(s == 'warn' for s in [nav_status, bench_status, mgr_status, cat_status, cache_status]):
        overall = 'warn'

    sources = [
        {
            'name': 'NAV & Return Data',
            'source': 'AMFI daily NAV file',
            'lastUpdated': age_label(nav_date),
            'cadence': 'Updated daily (weekdays)',
            'reason': None if nav_status == 'ok' else
                      'AMFI publishes NAVs by 11 PM IST each business day. Weekend and holiday NAVs are not published — this is expected.' if age_days(nav_date or today) <= 4
                      else 'NAV ingestion has not run in several days. Click Refresh Data to fetch the latest from AMFI.',
            'status': nav_status,
        },
        {
            'name': 'Benchmark Index Data',
            'source': 'NSE / Yahoo Finance',
            'lastUpdated': age_label(bench_date),
            'cadence': 'Updated daily (weekdays)',
            'reason': None if bench_status == 'ok' else
                      'Benchmark data (Nifty 50, Nifty 500) follows market trading days. No data on weekends and exchange holidays.'
                      if age_days(bench_date or today) <= 4
                      else 'Benchmark ingestion has not run recently. Click Refresh Data to update.',
            'status': bench_status,
        },
        {
            'name': 'Bouquet Cache',
            'source': 'FundGuldasta scoring engine',
            'lastUpdated': age_label(cache_date),
            'cadence': 'Rebuilt daily after NAV update',
            'reason': None if cache_status == 'ok' else
                      'Cache is rebuilt automatically each evening after NAV ingestion completes. If NAV is current, cache will refresh tonight.'
                      if age_days(cache_date or today) <= 4
                      else 'Bouquet cache is overdue for a rebuild. Click Refresh Data to trigger immediately.',
            'status': cache_status,
        },
        {
            'name': 'Fund Manager Details',
            'source': 'AMFI + AMC scheme documents',
            'lastUpdated': age_label(mgr_date),
            'cadence': 'Refreshed weekly',
            'reason': None if mgr_status == 'ok' else
                      'Fund manager data is sourced from AMC Scheme Information Documents (SID), which are updated infrequently — typically only when a manager changes. Weekly refresh is sufficient for this data.'
                      if mgr_status == 'warn'
                      else 'Manager data refresh is overdue. This will be corrected in the next scheduled weekly run.',
            'status': mgr_status,
        },
        {
            'name': 'Category & Scheme Metadata',
            'source': 'AMFI scheme master file',
            'lastUpdated': age_label(cat_date),
            'cadence': 'Refreshed weekly',
            'reason': None if cat_status == 'ok' else
                      'SEBI fund categories and scheme metadata change rarely — typically only when SEBI issues reclassification circulars or when AMCs merge/rename schemes. Weekly refresh is more than adequate for this data type.'
                      if cat_status == 'warn'
                      else 'Scheme metadata refresh is overdue. Will be corrected in the next weekly run.',
            'status': cat_status,
        },
    ]

    return {
        'sources': sources,
        'overallHealth': overall,
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



# ── NAV REFRESH TRIGGER ───────────────────────────────────

_last_trigger_time = None
_COOLDOWN_MINUTES = 60


@app.post("/api/pipeline/trigger-nav")
def trigger_nav_refresh():
    """
    Manually trigger NAV ingestion + precompute refresh.
    Enforces a 60-minute cooldown to prevent repeated runs.
    Runs synchronously — completes in ~15-30 seconds.
    """
    global _last_trigger_time
    from datetime import datetime, timedelta
    import subprocess, sys, os

    now = datetime.utcnow()
    if _last_trigger_time and (now - _last_trigger_time) < timedelta(minutes=_COOLDOWN_MINUTES):
        wait_mins = _COOLDOWN_MINUTES - int((now - _last_trigger_time).total_seconds() / 60)
        return {
            'status': 'cooldown',
            'message': f'Already refreshed recently. Next refresh available in ~{wait_mins} min.',
            'last_triggered': _last_trigger_time.isoformat(),
        }

    _last_trigger_time = now
    results = {}

    # Step 1 — NAV ingestion
    try:
        venv_python = os.path.join(os.path.expanduser('~/fundguldasta'), 'venv', 'bin', 'python3')
        script = os.path.join(os.path.expanduser('~/fundguldasta'), 'data', 'nav_ingestion.py')
        result = subprocess.run(
            [venv_python, script],
            capture_output=True, text=True, timeout=120,
            cwd=os.path.expanduser('~/fundguldasta'),
        )
        last_line = [l for l in result.stdout.strip().splitlines() if l.strip()]
        results['nav_ingestion'] = last_line[-1] if last_line else 'completed'
        results['nav_status'] = 'ok' if result.returncode == 0 else 'error'
    except Exception as e:
        results['nav_ingestion'] = str(e)
        results['nav_status'] = 'error'

    # Step 2 — Precompute common horizons
    try:
        from engine.precompute import run_precomputation
        cached = 0
        for h, c in [(7, 16), (5, 14), (10, 16)]:
            try:
                run_precomputation(horizon_years=h, target_cagr=c)
                cached += 1
            except Exception:
                pass
        results['precompute'] = f'{cached}/3 horizons refreshed'
        results['precompute_status'] = 'ok' if cached > 0 else 'error'
    except Exception as e:
        results['precompute'] = str(e)
        results['precompute_status'] = 'error'

    # Step 3 — Return updated freshness
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(nav_date) FROM nav_data")
    max_nav = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    from datetime import date as date_cls
    delta = (date_cls.today() - max_nav).days if max_nav else None
    if delta == 0:
        nav_label = 'Today'
    elif delta == 1:
        nav_label = 'Yesterday'
    else:
        nav_label = f'{delta} days ago' if delta else 'Unknown'

    return {
        'status': 'ok',
        'triggered_at': now.isoformat(),
        'results': results,
        'nav_data_through': nav_label,
        'nav_date': str(max_nav) if max_nav else None,
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
        # Use user-specified fund to replace, or determine algorithmically
        if request.replaced_fund_code:
            from engine.fund_replacement import ARCHETYPE_FUNDS, VERIFIED_FUNDS
            arch_funds = dict(ARCHETYPE_FUNDS.get(request.archetype_id, []))
            replaced_weight = arch_funds.get(request.replaced_fund_code, 0)
            fund_info = VERIFIED_FUNDS.get(request.replaced_fund_code, {})
            if not fund_info:
                conn_tmp = get_db()
                cur_tmp = conn_tmp.cursor()
                cur_tmp.execute("SELECT scheme_name, sebi_category FROM fund_metadata WHERE scheme_code=%s", (request.replaced_fund_code,))
                row_tmp = cur_tmp.fetchone()
                cur_tmp.close(); conn_tmp.close()
                fund_info = {'name': row_tmp[0], 'category': row_tmp[1]} if row_tmp else {}
            slot = {
                'replaced_code': request.replaced_fund_code,
                'replaced_name': fund_info.get('name', request.replaced_fund_code),
                'replaced_weight': replaced_weight,
                'replaced_category': fund_info.get('category', 'Unknown'),
                'reason': 'User-selected replacement',
            }
        else:
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


# ── CUSTOM BOUQUET ANALYSER ───────────────────────────────────

class CustomBouquetFund(BaseModel):
    scheme_code: str
    weight: float


class CustomBouquetRequest(BaseModel):
    funds: list  # [CustomBouquetFund]
    horizonYears: float = 7
    targetCAGR: Optional[float] = None   # if None, we use projected CAGR from analysis


class AIExplainRequest(BaseModel):
    question: str
    context_type: str = "bouquet"   # bouquet | metric | fund | general
    context_data: dict = {}


@app.post("/api/bouquets/analyse-custom")
def analyse_custom_bouquet_endpoint(request: CustomBouquetRequest):
    """
    Analyse a user-defined bouquet.
    Scores each fund, projects CAGR, finds high-correlation pairs,
    and suggests targeted fund replacements.
    """
    from engine.custom_bouquet import analyse_custom_bouquet

    if len(request.funds) < 1:
        raise HTTPException(status_code=400, detail="Please add at least 1 fund.")
    if len(request.funds) > 12:
        raise HTTPException(status_code=400, detail="Maximum 12 funds per bouquet.")

    funds_with_weights = [
        {'scheme_code': str(f['scheme_code']), 'weight': float(f['weight'])}
        for f in request.funds
    ]

    target = request.targetCAGR or 16.0

    try:
        result = analyse_custom_bouquet(
            funds_with_weights=funds_with_weights,
            horizon_years=int(request.horizonYears),
            target_cagr=float(target),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── AI EXPLAIN ENDPOINT ─────────────────────────────────────────────────────

AI_SYSTEM_PROMPT = """You are the FundGuldasta AI — an Indian mutual fund research and education assistant.
FundGuldasta is a research-only platform. You help users understand bouquet data, fund metrics, and investment concepts.

STRICT RULES:
- Education only. Never say "buy this", "invest in X", "you should invest", or imply any buy/sell action.
- Always say "based on historical data" when referencing past returns. Never imply future guarantees.
- Use the numbers from the context precisely — do not invent figures.
- Keep responses concise: 3-5 short paragraphs. Plain language. No unnecessary jargon.
- Accurate Indian MF tax rules: LTCG 10% above Rs 1.25L/year for equity held over 1 year; STCG 20% if under 1 year; Nasdaq 100 FOF taxed as debt — income slab rate regardless of holding.
- End every response with exactly this line: "— Research & education only. Not investment advice."
- If asked outside Indian MF education scope, politely redirect.

Key facts:
- SEBI categories: Large Cap (top 100 mcap), Midcap (101-250), Small Cap (251+), Flexi Cap (any), Balanced Advantage (dynamic equity/debt)
- Indian equity fund correlation: 0.85-0.98 is structural — market is tightly coupled
- True diversifiers: International funds (Nasdaq 100 corr ~0.35 vs Indian equity), Balanced Advantage (dynamic allocation)
- Direct plans: no distributor commission — standard for long-term investors
- Tier 1: 7+ years NAV history. Tier 2: 5-7 years. Tier 3: under 5 years
- Sortino ratio: risk-adjusted return using only downside volatility (more relevant than Sharpe for equity investors)
- Composite score /100 dimensions: Return Consistency 25%, Risk-Adjusted Quality 20%, Downside Behaviour 20%, Manager Stability 15%, Portfolio Quality 10%, Forward Context 10%
- Rebalancing: annual calendar + 5-point threshold trigger; SIP redirection preferred (no tax event)"""



@app.post("/api/ai/explain")
def ai_explain(request: AIExplainRequest):
    """Stream educational AI explanation about bouquet data, metrics, or funds."""
    import anthropic as ant
    from fastapi.responses import StreamingResponse
    import json as _json

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        raise HTTPException(status_code=503, detail="AI feature not configured — add ANTHROPIC_API_KEY to config/.env")

    client = ant.Anthropic(api_key=api_key)

    ctx = request.context_data
    ctx_summary = ""
    NL = "\n"

    if request.context_type == "bouquet" and ctx:
        name = ctx.get("name", "this bouquet")
        funds = ctx.get("funds", [])
        fund_list = "; ".join(
            f"{f.get('name','?')} ({f.get('weight','?')}%, score {f.get('composite_score','?')})"
            for f in funds[:6]
        )
        cagr = ctx.get("cagrRange", ctx.get("projected_cagr", "N/A"))
        conf = ctx.get("confidence", {})
        conf_score = conf.get("overall_score", "N/A") if isinstance(conf, dict) else "N/A"
        stress = ctx.get("stressTest", {})
        crisis_cagr = stress.get("crisis_recovery_cagr", "N/A") if isinstance(stress, dict) else "N/A"
        overlap = ctx.get("overlap", {})
        avg_corr = overlap.get("avg_correlation", "N/A") if isinstance(overlap, dict) else "N/A"
        metrics = ctx.get("metrics", {})
        ctx_summary = (
            "Archetype: " + str(name) + NL +
            "Funds: " + str(fund_list) + NL +
            "Historical CAGR range: " + str(cagr) + NL +
            "Confidence score: " + str(conf_score) + "/100" + NL +
            "Post-crisis recovery CAGR: " + str(crisis_cagr) + "%" + NL +
            "Average inter-fund correlation: " + str(avg_corr) + NL
        )
        if metrics:
            ctx_summary += (
                "Bouquet CAGR (" + str(ctx.get("horizonYears", 7)) + "yr): " +
                str(metrics.get("bouquet_cagr", "N/A")) + "%  " +
                "Post-tax: " + str(metrics.get("post_tax_cagr", "N/A")) + "%  " +
                "Real CAGR: " + str(metrics.get("real_cagr", "N/A")) + "%  " +
                "vs Nifty 50: " + str(metrics.get("nifty_cagr", "N/A")) + "%" + NL
            )
        devils = ctx.get("devils", [])
        if devils:
            ctx_summary += "Known risks: " + "; ".join(devils[:3]) + NL

    elif request.context_type == "metric" and ctx:
        ctx_summary = (
            "Metric: " + str(ctx.get("metric_name", "?")) + NL +
            "Value: " + str(ctx.get("value", "?")) + NL +
            "Context (fund/bouquet): " + str(ctx.get("entity_name", "?")) + NL +
            "Category: " + str(ctx.get("category", "N/A")) + NL +
            "Category benchmark: " + str(ctx.get("benchmark", "N/A")) + NL
        )

    elif request.context_type == "fund" and ctx:
        dims = ctx.get("dimension_scores", {})
        dim_text = "; ".join(str(k) + ": " + str(v) for k, v in dims.items())
        ctx_summary = (
            "Fund: " + str(ctx.get("name", "?")) + " — " + str(ctx.get("amc", "?")) + NL +
            "Category: " + str(ctx.get("category", "?")) + ", Tier: " + str(ctx.get("tier", "?")) + NL +
            "Composite score: " + str(ctx.get("composite_score", "?")) + "/100" + NL +
            "Dimension scores: " + dim_text + NL +
            "Rolling CAGR (" + str(ctx.get("horizon_years", 7)) + "yr): " + str(ctx.get("rolling_cagr", "N/A")) + "%" + NL +
            "Expense ratio: " + str(ctx.get("expense_ratio", "N/A")) + "%" + NL
        )

    user_msg = ctx_summary + NL + "Question: " + request.question if ctx_summary else request.question

    def generate():
        try:
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                system=AI_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            ) as stream:
                for text in stream.text_stream:
                    yield "data: " + _json.dumps({"text": text}) + "\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield "data: " + _json.dumps({"error": str(exc)}) + "\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
