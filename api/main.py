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
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
from engine.cagr_advisor import assess_realism
from engine.precompute import run_precomputation, run_all_horizons
from engine.fund_replacement import (
    search_eligible_funds, search_funds_broad, find_replacement_slot,
    score_single_fund, compute_replacement_impact,
)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env'))

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


# ── Slow-request logger ───────────────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
import time as _time

_SLOW_REQUEST_THRESHOLD_S = 5.0   # log any endpoint that takes longer than this

class SlowRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        t0 = _time.monotonic()
        response = await call_next(request)
        elapsed = _time.monotonic() - t0
        if elapsed >= _SLOW_REQUEST_THRESHOLD_S:
            print(
                f"[SLOW] {request.method} {request.url.path} "
                f"took {elapsed:.1f}s — review for optimisation"
            )
        return response

app.add_middleware(SlowRequestMiddleware)

# ── Connection pool — replaces per-request psycopg2.connect() ────────────────
_pool = None
_pool_lock = threading.Lock()

def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                # maxconn=10 per worker. With --workers 2 that is 20 total.
                # Timescale Cloud Hobby allows 25 connections — safe headroom.
                _pool = pg_pool.ThreadedConnectionPool(minconn=2, maxconn=10, **DB_CONFIG)
    return _pool

class _PooledConn:
    """Wraps a pooled connection; close() returns it to the pool instead of closing."""
    def __init__(self, conn):
        self._conn = conn
    def cursor(self):   return self._conn.cursor()
    def commit(self):   return self._conn.commit()
    def rollback(self): return self._conn.rollback()
    def close(self):
        try:
            _get_pool().putconn(self._conn)
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass

def get_db():
    try:
        return _PooledConn(_get_pool().getconn())
    except pg_pool.PoolError as e:
        # Pool exhausted — surface a 503 rather than hanging
        raise HTTPException(status_code=503, detail="DB connection pool exhausted. Retry in a moment.")
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

_HEALTH_CHECK_INTERVAL_HOURS = 0.5   # 30 minutes — fast self-correction
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
        if age_hours is not None and age_hours > 72:
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
        if staleness <= 1:
            # staleness <= 0: AMFI pre-published tomorrow's data (timezone edge) — healthy
            # staleness == 1: yesterday's data — normal AMFI publishing cadence
            status = "healthy"
            detail = ("NAV data is current (today)" if staleness == 0
                      else "NAV data from yesterday (normal — AMFI publishes end-of-day)" if staleness == 1
                      else f"NAV data pre-published ({-staleness} day ahead) — healthy")
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
        _log_remediation("Cache stale — auto-triggering precompute for all horizons [5,7,10,15,20,30]")
        age_h = cache.get("age_hours") or 0
        if age_h > 48:
            from api.alerts import send_cache_stale_alert
            threading.Thread(target=send_cache_stale_alert, args=(age_h,), daemon=True).start()
        def _bg_precompute():
            try:
                for h, c in [(5, 14), (7, 16), (10, 16), (15, 16), (20, 16), (30, 16)]:
                    run_precomputation(horizon_years=h, target_cagr=c)
                _log_remediation("Auto-precompute complete — all 6 horizons refreshed")
            except Exception as e:
                _log_remediation(f"Auto-precompute failed: {e}")
        threading.Thread(target=_bg_precompute, daemon=True).start()

    # Heal stale NAV data — call ingestion module directly (works on Railway + local)
    if nav.get("staleness_days") and nav["staleness_days"] >= 2:
        _log_remediation(f"NAV data {nav['staleness_days']} days old — auto-triggering ingestion")
        def _bg_nav():
            try:
                from data.nav_ingestion import fetch_nav_data, parse_nav_data, insert_nav_records, log_pipeline
                raw = fetch_nav_data()
                records = parse_nav_data(raw)
                inserted, skipped = insert_nav_records(records)
                log_pipeline("success", inserted)
                _log_remediation(f"Auto NAV ingestion: {inserted} new, {skipped} skipped")
                # Re-run precompute so bouquet cache stays fresh
                for h, c in [(5, 14), (7, 16), (10, 16), (15, 16), (20, 16), (30, 16)]:
                    run_precomputation(horizon_years=h, target_cagr=c)
                _log_remediation("Auto precompute after NAV refresh: all 6 horizons complete")
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
    """Background thread: initial check after 20s, then every 30 minutes."""
    import time
    time.sleep(20)
    while True:
        try:
            _run_diagnostics()
        except Exception as e:
            print(f"[HEALTH] Diagnostic loop error: {e}")
            with _diag_lock:
                _health_state["last_check"] = datetime.now().isoformat()
        time.sleep(_HEALTH_CHECK_INTERVAL_HOURS * 3600)


# Start health loop as daemon thread at import time
_health_thread = threading.Thread(target=_health_loop, daemon=True, name="health-loop")
_health_thread.start()


# ── Nightly precompute scheduler ──────────────────────────────────────────────
def _nightly_scheduler():
    """
    Runs every night at 02:00 IST (20:30 UTC).
    Refreshes bouquet_cache for all horizons so the cache is never stale.
    Runs as a daemon thread — Railway keeps the process alive between requests.
    With --workers 2 both workers start this thread; that's harmless (DB writes
    are idempotent and the second run completes instantly from warm cache).
    """
    import time
    from datetime import datetime, timedelta

    # Delay startup by 60s so the pool and health thread initialise first
    time.sleep(60)

    while True:
        now = datetime.utcnow()
        # Next 20:30 UTC (= 02:00 IST)
        target = now.replace(hour=20, minute=30, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        sleep_secs = (target - now).total_seconds()
        print(f"[NIGHTLY] Next precompute scheduled in {sleep_secs/3600:.1f}h at {target.strftime('%Y-%m-%d %H:%M UTC')}")
        time.sleep(sleep_secs)

        run_ts = datetime.utcnow().isoformat()
        print(f"[NIGHTLY] Starting scheduled precomputation — {run_ts}")
        try:
            # Refresh portfolio holdings first (monthly disclosures) — overlap depends on this
            try:
                from data.portfolio_fetcher import fetch_all_configured, last_month_end
                from config.db import get_db_config
                _db = get_db_config()
                # psycopg2 uses 'dbname' key; portfolio_fetcher uses 'database'
                _pf_cfg = {k if k != 'dbname' else 'database': v for k, v in _db.items()}
                _as_of = last_month_end()
                print(f"[NIGHTLY] Refreshing portfolio holdings as of {_as_of}")
                fetch_all_configured(as_of=_as_of, db_config=_pf_cfg)
                print("[NIGHTLY] Portfolio holdings refresh complete")
            except Exception as _pf_err:
                print(f"[NIGHTLY] Portfolio holdings refresh failed (non-fatal): {_pf_err}")

            from engine.precompute import run_all_horizons
            run_all_horizons(target_cagr=16.0)
            print(f"[NIGHTLY] Precomputation complete — {datetime.utcnow().isoformat()}")
        except Exception as e:
            print(f"[NIGHTLY] Precomputation failed: {e}")
            try:
                threading.Thread(
                    target=send_pipeline_failure_alert,
                    args=('nightly_precompute', str(e)),
                    daemon=True,
                ).start()
            except Exception:
                pass

_nightly_thread = threading.Thread(target=_nightly_scheduler, daemon=True, name="nightly-precompute")
_nightly_thread.start()

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


@app.api_route("/health", methods=["GET", "HEAD"])
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

@app.get("/api/funds/{scheme_code}/full-analysis")
def fund_full_analysis(scheme_code: str):
    """
    Comprehensive multi-dimensional intelligence analysis of any mutual fund.
    Computes 30+ parameters across 7 dimensions: structural quality, downside
    protection, risk profile, consistency, cost efficiency, category opportunity,
    and investor suitability.
    Response time: ~3-6 seconds (real-time computation from NAV history).
    """
    import json, math
    from engine.fund_analyst import analyse_fund

    def _jsonify(obj):
        """Recursively convert numpy/non-serialisable types to native Python."""
        if obj is None:
            return None
        if isinstance(obj, dict):
            return {k: _jsonify(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_jsonify(i) for i in obj]
        if hasattr(obj, 'item'):           # numpy scalar
            v = obj.item()
            return None if (isinstance(v, float) and math.isnan(v)) else v
        if isinstance(obj, float) and math.isnan(obj):
            return None
        return obj

    result = analyse_fund(scheme_code)
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])

    # Augment with nav_count and plan_type so frontend can show data quality warnings
    try:
        _ac = get_db()
        _c = _ac.cursor()
        _c.execute(
            "SELECT fm.plan_type, COUNT(nd.nav_date) FROM fund_metadata fm "
            "LEFT JOIN nav_data nd ON fm.scheme_code=nd.scheme_code "
            "WHERE fm.scheme_code=%s GROUP BY fm.plan_type",
            (scheme_code,)
        )
        _row = _c.fetchone()
        if _row:
            result['plan_type'] = _row[0]
            result['nav_count'] = int(_row[1])
        _c.close()
        _ac.close()
    except Exception:
        pass

    return _jsonify(result)


@app.get("/api/calibration/achievement-probs")
def get_calibration_probs(horizon: int = 7, refresh: bool = False):
    """
    Return data-calibrated CAGR achievement probabilities computed from actual
    NAV data of 10 Tier 1 Indian equity MFs. Cached daily.
    horizon: investment horizon in years (nearest available: 3, 5, 7, 10)
    """
    from engine.calibration import get_horizon_probs, get_calibration_summary
    try:
        if refresh:
            data = get_calibration_summary(force_refresh=True).get(horizon)
        else:
            data = get_horizon_probs(horizon)
        if not data:
            raise HTTPException(status_code=503, detail="Calibration data unavailable — building in background")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


@app.get("/api/calibration/summary")
def get_calibration_full():
    """Return calibration data for all available horizons."""
    from engine.calibration import get_calibration_summary
    try:
        return get_calibration_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


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
            label = "Slightly Above Your Goal"
        elif dist <= 5:
            label = "Higher Risk Than Needed"
        else:
            label = "Much Higher Risk Than Needed"
        return dist, label
    else:  # target > hi — archetype historically below user's goal
        dist = target_cagr - hi
        if dist <= 2:
            label = "May Fall Short of Your Goal"
        else:
            label = "Unlikely to Reach Your Target"
        return dist, label


def _cagr_buffer(arch_id: str, target_cagr: float) -> str:
    """Human-readable string showing how far archetype range is from user's target."""
    lo, hi = ARCHETYPE_CAGR_RANGES[arch_id]
    buf_lo = lo - target_cagr
    buf_hi = hi - target_cagr
    if buf_lo >= 0:
        return f"+{buf_lo:.0f}% to +{buf_hi:.0f}% above your goal"
    elif buf_hi < 0:
        return f"{buf_lo:.0f}% to {buf_hi:.0f}% below your goal"
    else:
        return "Your goal sits within this range"


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
            'steady':     {'label':'Steady Compounder',  'cagrRange':'10-13%', 'risk':'Low-Medium', 'color':'#4A8FE0', 'rgb':'74,143,224'},
            'balanced':   {'label':'Balanced Growther',  'cagrRange':'12-15%', 'risk':'Medium',     'color':'#27AE78', 'rgb':'39,174,120'},
            'aggressive': {'label':'Aggressive Achiever','cagrRange':'15-18%', 'risk':'Medium-High','color':'#F0A500', 'rgb':'240,165,0'},
            'conviction': {'label':'High Conviction',    'cagrRange':'16-19%', 'risk':'High',       'color':'#E05555', 'rgb':'224,85,85'},
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
            'cagrBuffer':           _cagr_buffer(arch_id, implied_cagr or 16.0),
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

class GoalBouquetRequest(BaseModel):
    horizon_years: int = 7
    target_cagr: float = 16.0


@app.get("/api/bouquets/index")
def index_bouquets_endpoint():
    """Returns all curated index (passive) bouquets with performance data."""
    from engine.index_bouquet import get_index_bouquets as _get_index_bouquets
    try:
        return {'bouquets': _get_index_bouquets()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bouquets/goal")
def curate_goal_bouquet(request: GoalBouquetRequest):
    """
    Screen 2: Build a bespoke bouquet from the full 271-fund eligible universe
    for the user's specific CAGR + horizon goal.
    Reads from computed_metrics (populated by bulk_scorer).
    """
    from engine.goal_bouquet import build_goal_bouquet
    from engine.cagr_advisor import assess_realism

    horizon = int(request.horizon_years)
    target = float(request.target_cagr)

    advisory = assess_realism(target, horizon)

    result = build_goal_bouquet(horizon_years=horizon, target_cagr=target)

    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Goal Bouquet scoring data not yet ready. The Fund Intelligence Engine is still scoring the full fund universe. Please try again in a few minutes."
        )

    result['advisory'] = advisory
    result['computedAt'] = datetime.now().isoformat()
    return result


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

    # Use actual data tables — more accurate than pipeline_log entries
    cursor.execute("SELECT MAX(price_date) FROM benchmark_data")
    max_bench_date = (cursor.fetchone() or [None])[0]

    cursor.execute("SELECT MAX(computation_date) FROM bouquet_cache")
    max_cache_date = (cursor.fetchone() or [None])[0]

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

    nav_date   = max_nav_date
    bench_date = max_bench_date   # from benchmark_data table directly
    cache_date = max_cache_date   # from bouquet_cache table directly
    mgr_date   = pipeline_map.get('manager_change_detection')
    cat_date   = pipeline_map.get('manager_ingestion')

    # Nav and benchmark: daily cadence (weekdays). Allow 3 days for weekends.
    nav_status   = stale_status(nav_date,   3)
    bench_status = stale_status(bench_date, 3)
    # Manager and category: SID documents change rarely — 14-day cadence is appropriate.
    mgr_status  = stale_status(mgr_date,  14)
    cat_status  = stale_status(cat_date,  14)
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

@app.post("/api/pipeline/trigger-nav")
def trigger_nav_pipeline():
    """Manually trigger NAV ingestion. Cooldown: 2 hours between runs."""
    conn = get_db()
    cursor = conn.cursor()

    # Check cooldown: successful run within the last 2 hours
    cursor.execute("""
        SELECT MAX(completed_at) FROM pipeline_log
        WHERE pipeline_name = 'nav_ingestion' AND status = 'success'
        AND completed_at > NOW() - INTERVAL '2 hours'
    """)
    recent = cursor.fetchone()[0]

    if recent:
        cursor.execute("SELECT MAX(nav_date) FROM nav_data")
        max_nav = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return {
            'status': 'cooldown',
            'message': 'NAV data was refreshed recently. Next manual refresh available after 2-hour cooldown.',
            'nav_data_through': str(max_nav) if max_nav else None,
        }

    cursor.close()
    conn.close()

    try:
        from data.nav_ingestion import fetch_nav_data, parse_nav_data, insert_nav_records, log_pipeline as nav_log
        raw = fetch_nav_data()
        records = parse_nav_data(raw)
        inserted, _ = insert_nav_records(records)
        nav_log('success', inserted)

        conn2 = get_db()
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT MAX(nav_date) FROM nav_data")
        max_nav = cursor2.fetchone()[0]
        cursor2.close()
        conn2.close()

        return {
            'status': 'ok',
            'nav_data_through': str(max_nav) if max_nav else None,
            'records_inserted': inserted,
        }
    except Exception as e:
        try:
            from data.nav_ingestion import log_pipeline as nav_log
            nav_log('failed', 0, str(e))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"NAV ingestion failed: {e}")

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
    Manually trigger NAV + benchmark ingestion + precompute refresh.
    Enforces a 60-minute cooldown to prevent repeated runs.
    Uses direct function calls (not subprocess) so it works on Railway.
    """
    global _last_trigger_time
    from datetime import datetime, timedelta

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

    # Step 1 — NAV ingestion (direct import, works on Railway)
    try:
        from data.nav_ingestion import main as nav_main
        nav_main()
        results['nav_ingestion'] = 'completed'
        results['nav_status'] = 'ok'
    except Exception as e:
        results['nav_ingestion'] = str(e)
        results['nav_status'] = 'error'
        from api.alerts import send_pipeline_failure_alert
        threading.Thread(target=send_pipeline_failure_alert, args=('nav_ingestion', str(e)), daemon=True).start()

    # Step 2 — Benchmark ingestion (direct import)
    try:
        from data.benchmark_ingestion import main as bench_main
        bench_main()
        results['benchmark_ingestion'] = 'completed'
        results['benchmark_status'] = 'ok'
    except Exception as e:
        results['benchmark_ingestion'] = str(e)
        results['benchmark_status'] = 'error'

    # Step 3 — Precompute common horizons
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

    # Step 4 — Return updated freshness
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

@app.post("/api/pipeline/trigger-alt-precompute")
def trigger_alt_precompute():
    """
    Trigger alternative bouquet precomputation in the background.
    Populates steady_r2, balanced_r2, aggressive_r2, conviction_r2 in bouquet_cache.
    Returns immediately — computation runs in background thread (~10-20 min).
    """
    import threading
    from engine.precompute import run_alternative_precomputation

    def _run():
        for h, c in [(7, 16), (5, 14), (10, 16)]:
            try:
                run_alternative_precomputation(horizon_years=h, target_cagr=c)
            except Exception as e:
                print(f"  Alt precompute {h}yr failed: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return {
        'status': 'started',
        'message': 'Alternative precompute running in background. Check bouquet_cache for steady_r2 etc. in ~15 min.',
    }


# ── FUND CUSTOMIZATION ENDPOINTS ─────────────────────────────

@app.get("/api/funds/search")
def fund_search(q: str = Query(default="", min_length=1), limit: int = Query(default=15, le=30)):
    """
    Search all active funds by name or AMC — broad universe, returns quality flags.
    Excludes IDCW/dividend variants and pure debt/liquid/overnight/gilt/arbitrage.
    """
    if not q.strip():
        return []
    try:
        results = search_funds_broad(q.strip(), limit)
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


def _load_alt_from_cache(horizon_years: int, target_cagr: float) -> list | None:
    """Try to load pre-cached round-2 alternative archetypes from bouquet_cache."""
    arch_ids = ['steady_r2', 'balanced_r2', 'aggressive_r2', 'conviction_r2']
    closest = min([3, 5, 7, 10, 15], key=lambda h: abs(h - horizon_years))
    try:
        conn, cur = None, None
        conn = _get_pool().getconn()
        cur = conn.cursor()
        cur.execute("""
            SELECT archetype_id, funds_json, metrics_json, confidence_json,
                   stress_test_json, overlap_json, methodology_json, devils_json, comparator_json
            FROM bouquet_cache
            WHERE archetype_id = ANY(%s) AND horizon_years = %s AND is_active = TRUE
            ORDER BY computation_date DESC
        """, (arch_ids, closest))
        rows = cur.fetchall()
        cur.close()
        _get_pool().putconn(conn)
        if len(rows) < 2:
            return None

        LABELS = {'steady_r2': 'Steady Compounder', 'balanced_r2': 'Balanced Growther',
                  'aggressive_r2': 'Aggressive Achiever', 'conviction_r2': 'High Conviction'}
        COLORS = {'steady_r2': '#4A8FE0', 'balanced_r2': '#27AE78',
                  'aggressive_r2': '#F0A500', 'conviction_r2': '#E05555'}
        RISK = {'steady_r2': 'Low-Medium', 'balanced_r2': 'Medium',
                'aggressive_r2': 'Medium-High', 'conviction_r2': 'High'}
        CAGR = {'steady_r2': '10-13%', 'balanced_r2': '12-15%',
                'aggressive_r2': '15-18%', 'conviction_r2': '16-19%'}
        ICONS = {'steady_r2': 'B', 'balanced_r2': 'G', 'aggressive_r2': 'Y', 'conviction_r2': 'R'}

        archetypes = []
        seen = set()
        for row in rows:
            aid = row[0]
            if aid in seen:
                continue
            seen.add(aid)
            base_id = aid.replace('_r2', '')
            metrics_obj = json.loads(row[2])
            archetypes.append({
                'id': base_id,
                'icon': ICONS.get(aid, 'G'),
                'label': LABELS.get(aid, aid),
                'cagrRange': CAGR.get(aid, '14-18%'),
                'risk': RISK.get(aid, 'Medium'),
                'color': COLORS.get(aid, '#27AE78'),
                'rgb': '',
                'funds': json.loads(row[1]),
                'metrics': metrics_obj,
                'confidence': json.loads(row[3]),
                'stressTest': json.loads(row[4]),
                'overlap': json.loads(row[5]),
                'methodology': json.loads(row[6]),
                'devils': json.loads(row[7]),
                'comparator': json.loads(row[8]),
                'roundNumber': 2,
            })
        return archetypes if archetypes else None
    except Exception as e:
        print(f"  _load_alt_from_cache error: {e}")
        if conn:
            try:
                _get_pool().putconn(conn)
            except Exception:
                pass
        return None


@app.post("/api/bouquets/generate-more")
def generate_more_bouquets(request: GenerateMoreRequest):
    """
    Generate alternative bouquets. Round 2 is served from pre-computed cache
    (< 100ms). Rounds 3+ trigger live computation with reduced pool.
    """
    from engine.alternative_bouquet import build_alternative_round
    from engine.cagr_advisor import assess_realism

    if request.roundNumber > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 rounds supported.")

    try:
        advisory = assess_realism(request.targetCAGR, request.horizonYears)

        # Round 2: serve from pre-computed cache (no timeout risk)
        if request.roundNumber == 2:
            cached = _load_alt_from_cache(int(request.horizonYears), float(request.targetCAGR))
            if cached:
                for arch in cached:
                    dist, label = _archetype_relevance(arch["id"], request.targetCAGR)
                    arch["relevanceScore"] = round(dist, 1)
                    arch["matchLabel"] = label
                    arch["realisticAssessment"] = advisory
                cached.sort(key=lambda x: x["relevanceScore"])
                if cached and cached[0]["matchLabel"] != "Best Match":
                    cached[0]["matchLabel"] = "Closest Match"
                return {
                    "impliedCAGR": request.targetCAGR,
                    "archetypes": cached,
                    "roundNumber": 2,
                    "poolSize": 0,
                    "poolExhausted": False,
                    "computedAt": datetime.now().isoformat(),
                    "horizonUsed": int(request.horizonYears),
                    "fromCache": True,
                }

        # Round 2 cache miss or rounds 3+: fast mode (NAV-count proxy, no scoring DB calls)
        # Completes in ~5s. Quality is lower than scored but avoids Railway timeout.
        result = build_alternative_round(
            horizon_years=int(request.horizonYears),
            target_cagr=float(request.targetCAGR),
            excluded_codes=[str(c) for c in request.excludedFunds],
            round_number=request.roundNumber,
            fast=True,
        )

        if result["pool_exhausted"] and not result["archetypes"]:
            raise HTTPException(
                status_code=409,
                detail=f"Fund pool exhausted — only {result['pool_size']} eligible funds remain after exclusions. No further unique bouquets can be generated."
            )

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



ADVISOR_SYSTEM_PROMPT = """You are the Guldasta Advisor — an Indian mutual fund research and education assistant built into FundGuldasta.

SCOPE: You cover the complete Indian mutual fund ecosystem — fund categories, portfolio construction, tax rules, cost analysis, goal-based planning, SEBI/AMFI regulations, risk metrics, benchmarks, and investor behaviour. You are NOT limited to FundGuldasta's specific bouquets.

STRICT RULES:
- Education and research only. Never say "invest in X", "buy this", "you should invest", or imply a specific buy/sell action.
- Never provide personalised investment advice. Always clarify you are a research tool.
- Use "based on historical data" when referencing returns. Never imply future guarantees.
- Keep responses clear and direct: 3–5 paragraphs. Avoid jargon; explain concepts plainly.
- Be honest about data limitations — India has ~25 years of reliable MF data (2001–2026).
- Always maintain conversation context — remember what was discussed earlier in the session.
- End every response with exactly this line: "— Research & education only. Not investment advice."

INDIAN MF KNOWLEDGE BASE:
- SEBI categories: Large Cap (top 100 mcap), Midcap (101–250), Small Cap (251+), Flexi Cap (any allocation), Multi Cap (min 25% each in large/mid/small), ELSS (tax-saving, 3yr lock), Balanced Advantage/DAF (dynamic equity-debt), Aggressive Hybrid (65–80% equity), Arbitrage, Index/ETF, FOF, Debt categories (Liquid, Ultra Short, Short, Medium, Long, Gilt, Credit Risk, Dynamic Bond)
- Tax rules (current as of 2024–25): Equity LTCG 12.5% above ₹1.25L/year (held >12m); STCG 20% (≤12m); Debt/FOF/International — income slab rate regardless of holding period. Indexation removed for debt from Apr 2023. ELSS — ₹1.5L deduction under 80C.
- Direct vs Regular: No distributor commission in Direct plans. Typically 0.8–1.2% lower TER. Over 10yr, 1% p.a. difference compounds to ~10% extra corpus.
- Indian equity correlation: 0.85–0.98 between equity funds is structural. True diversifiers: International funds (Nasdaq 100 ~0.35 corr vs Indian equity), Balanced Advantage (uncorrelated to equity beta).
- Expense ratio: SEBI caps — Large Cap max 1.05% (direct), typically 0.35–0.6% for large direct funds. Small Cap up to 1.5%. ETFs: 0.1–0.2%.
- SIP: Rupee-cost averaging. Not market-timing. Annual review, not monthly monitoring.
- Rebalancing: Annual calendar + 5-point threshold trigger. SIP redirection preferred (no tax event vs redemption).
- Rolling returns: More reliable than point-to-point for evaluating funds. Measures all possible start dates.
- Survivorship bias: Funds wound up or merged are excluded from historical averages, inflating apparent sector returns.
- AMFI: Association of Mutual Funds in India — regulatory body for MF industry. NAV disclosure, AUM reporting.
- SEBI: Securities and Exchange Board of India — regulates fund houses, mandates categories, expense ratio caps.
- Manager stability: Lead manager changes are a risk signal. Look for managers with 7+ year tenure on a fund."""


class AdvisorMessage(BaseModel):
    role: str
    content: str

class AdvisorRequest(BaseModel):
    messages: List[AdvisorMessage]


@app.post("/api/ai/advisor")
def ai_advisor(request: AdvisorRequest):
    """Stream multi-turn Guldasta Advisor responses with full conversation history."""
    import anthropic as ant
    from fastapi.responses import StreamingResponse
    import json as _json

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        raise HTTPException(status_code=503, detail="AI feature not configured — add ANTHROPIC_API_KEY to config/.env")

    client = ant.Anthropic(api_key=api_key)
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    def generate():
        try:
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                system=ADVISOR_SYSTEM_PROMPT,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield "data: " + _json.dumps({"text": text}) + "\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield "data: " + _json.dumps({"error": str(exc)}) + "\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


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


# ══════════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

import re as _re
from api.auth import hash_password, verify_password, create_token, decode_token
import jwt as _jwt


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


def _get_user_from_token(authorization: str = None):
    """Extract user from Bearer token header. Returns user dict or raises 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization[7:]
    try:
        payload = decode_token(token)
    except _jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired — please log in again")
    except _jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.post("/api/auth/register")
def register(request: RegisterRequest):
    """Create a new user account."""
    email = request.email.strip().lower()
    if not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        pw_hash = hash_password(request.password)
        display = (request.display_name or "").strip() or email.split("@")[0]
        cur.execute(
            "INSERT INTO users (email, password_hash, display_name) VALUES (%s, %s, %s) RETURNING id",
            (email, pw_hash, display),
        )
        user_id = cur.fetchone()[0]
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    token = create_token(user_id, email)
    return {"token": token, "user": {"id": user_id, "email": email, "display_name": display}}


@app.post("/api/auth/login")
def login(request: LoginRequest):
    """Authenticate and return a JWT token."""
    email = request.email.strip().lower()
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, password_hash, display_name FROM users WHERE email = %s", (email,)
        )
        row = cur.fetchone()
        if not row or not verify_password(request.password, row[1]):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        user_id, _, display = row
        cur.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user_id,))
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    token = create_token(user_id, email)
    return {"token": token, "user": {"id": user_id, "email": email, "display_name": display}}


from fastapi import Header as _Header


@app.get("/api/auth/me")
def get_me(authorization: Optional[str] = _Header(default=None)):
    """Return current user info from JWT. Requires Authorization: Bearer <token>."""
    payload = _get_user_from_token(authorization)
    user_id = int(payload["sub"])
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, email, display_name, created_at FROM users WHERE id = %s", (user_id,)
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": row[0],
        "email": row[1],
        "display_name": row[2],
        "created_at": str(row[3]),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SAVED BOUQUETS (Priority 10b)
# ══════════════════════════════════════════════════════════════════════════════

class SaveBouquetRequest(BaseModel):
    archetype_id: str
    horizon_years: int = 7
    target_cagr: float = 16.0
    name: Optional[str] = None
    snapshot: Optional[dict] = None


@app.post("/api/user/saved-bouquets")
def save_bouquet(
    request: SaveBouquetRequest,
    authorization: Optional[str] = _Header(default=None),
):
    """Save a bouquet to the authenticated user's library."""
    payload = _get_user_from_token(authorization)
    user_id = int(payload["sub"])

    name = (request.name or "").strip() or f"{request.archetype_id.title()} · {request.horizon_years}yr · {request.target_cagr}% CAGR"
    snap = json.dumps(request.snapshot) if request.snapshot else None

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO saved_bouquets (user_id, name, archetype_id, horizon_years, target_cagr, snapshot_json)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, saved_at""",
            (user_id, name, request.archetype_id, request.horizon_years, request.target_cagr, snap),
        )
        row = cur.fetchone()
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    return {"id": row[0], "name": name, "saved_at": str(row[1])}


@app.get("/api/user/saved-bouquets")
def list_saved_bouquets(authorization: Optional[str] = _Header(default=None)):
    """List all saved bouquets for the authenticated user."""
    payload = _get_user_from_token(authorization)
    user_id = int(payload["sub"])

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, name, archetype_id, horizon_years, target_cagr, saved_at
               FROM saved_bouquets WHERE user_id = %s ORDER BY saved_at DESC""",
            (user_id,),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return [
        {"id": r[0], "name": r[1], "archetype_id": r[2],
         "horizon_years": r[3], "target_cagr": r[4], "saved_at": str(r[5])}
        for r in rows
    ]


@app.delete("/api/user/saved-bouquets/{bouquet_id}")
def delete_saved_bouquet(
    bouquet_id: int,
    authorization: Optional[str] = _Header(default=None),
):
    """Delete a saved bouquet (must belong to authenticated user)."""
    payload = _get_user_from_token(authorization)
    user_id = int(payload["sub"])

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM saved_bouquets WHERE id = %s AND user_id = %s RETURNING id",
            (bouquet_id, user_id),
        )
        deleted = cur.fetchone()
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    if not deleted:
        raise HTTPException(status_code=404, detail="Bouquet not found or not yours")
    return {"deleted": bouquet_id}


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ANALYSER (Priority 10d)
# ══════════════════════════════════════════════════════════════════════════════

# /api/funds/search is already defined earlier in this file (fund replacement feature)
# Portfolio analyser reuses that endpoint — no duplicate needed


class PortfolioFund(BaseModel):
    scheme_code: int
    allocation_pct: float


class PortfolioRequest(BaseModel):
    funds: List[PortfolioFund]
    horizon_years: int = 7


@app.post("/api/portfolio/analyse")
def analyse_portfolio(request: PortfolioRequest):
    """Analyse user portfolio: metrics + archetype similarity."""
    funds = request.funds
    if not funds:
        raise HTTPException(status_code=400, detail="No funds provided")
    total_alloc = sum(f.allocation_pct for f in funds)
    if total_alloc < 80 or total_alloc > 120:
        raise HTTPException(status_code=400, detail=f"Allocations sum to {total_alloc:.0f}% — must be near 100%")

    # Normalise allocations to 100
    scale = 100.0 / total_alloc
    # scheme_code is stored as VARCHAR in fund_metadata/computed_metrics — use strings throughout
    alloc_map = {str(f.scheme_code): f.allocation_pct * scale for f in funds}
    codes = list(alloc_map.keys())

    conn = get_db()
    cur = conn.cursor()
    try:
        # Fund metadata (scheme_code is VARCHAR)
        cur.execute(
            "SELECT scheme_code, scheme_name, amc_name, sebi_category, expense_ratio FROM fund_metadata WHERE scheme_code = ANY(%s)",
            (codes,),
        )
        meta = {r[0]: {"scheme_name": r[1], "amc_name": r[2], "sebi_category": r[3], "expense_ratio": r[4]} for r in cur.fetchall()}

        # Archetypes from cache — also extract per-fund composite scores
        cur.execute(
            """SELECT archetype_id, funds_json, metrics_json, confidence_json
               FROM bouquet_cache
               WHERE horizon_years = %s AND is_active = true
               ORDER BY archetype_id""",
            (request.horizon_years,),
        )
        archetypes = []
        fund_scores_cache: dict = {}  # scheme_code_str -> composite_score from bouquet data
        for r in cur.fetchall():
            funds_json = r[1] if isinstance(r[1], list) else json.loads(r[1])
            metrics_json = r[2] if isinstance(r[2], dict) else json.loads(r[2])
            conf_json = r[3] if isinstance(r[3], dict) else json.loads(r[3])
            archetypes.append({"id": r[0], "funds": funds_json, "metrics": metrics_json, "confidence": conf_json})
            for f in funds_json:
                sc = str(f.get("scheme_code", ""))
                if sc and sc not in fund_scores_cache:
                    fund_scores_cache[sc] = float(f.get("composite_score") or 0)
    finally:
        cur.close()
        conn.close()

    # ── Weighted portfolio metrics ──────────────────────────────────────────
    w_expense = 0.0
    w_score = 0.0
    cat_dist = {}
    fund_details = []

    for code, alloc in alloc_map.items():
        w = alloc / 100.0
        fm = meta.get(code, {})
        cat = (fm.get("sebi_category") or "Unknown").split(" - ")[-1][:30]
        cat_dist[cat] = cat_dist.get(cat, 0) + alloc
        er = float(fm.get("expense_ratio") or 0)
        w_expense += er * w
        score = fund_scores_cache.get(code, 0)
        w_score += score * w

        fund_details.append({
            "scheme_code": int(code),
            "scheme_name": fm.get("scheme_name", f"Fund {code}"),
            "amc_name": fm.get("amc_name", ""),
            "sebi_category": fm.get("sebi_category", ""),
            "allocation_pct": round(alloc, 1),
            "composite_score": round(score, 1),
            "expense_ratio": float(fm.get("expense_ratio") or 0),
            "in_bouquets": code in fund_scores_cache,
        })

    portfolio_metrics = {
        "weighted_expense_ratio": round(w_expense, 3),
        "weighted_composite_score": round(w_score, 1),
        "category_distribution": {k: round(v, 1) for k, v in sorted(cat_dist.items(), key=lambda x: -x[1])},
        "fund_count": len(codes),
    }

    # ── Archetype similarity ────────────────────────────────────────────────
    archetype_matches = []
    # Normalise user codes to strings for comparison (bouquet_cache stores as strings)
    user_codes_str = {str(c) for c in codes}
    alloc_map_str = {str(k): v for k, v in alloc_map.items()}

    for at in archetypes:
        at_codes = {str(f["scheme_code"]) if isinstance(f, dict) else str(f) for f in at["funds"]}
        at_alloc = {
            str(f["scheme_code"] if isinstance(f, dict) else f):
            (f.get("weight") or f.get("weight_pct") or 20) if isinstance(f, dict) else 20
            for f in at["funds"]
        }

        # Fund overlap score (Jaccard + weighted)
        common = user_codes_str & at_codes
        jaccard = len(common) / len(user_codes_str | at_codes) if (user_codes_str | at_codes) else 0

        # Weighted overlap: sum of min(user_alloc, archetype_alloc) for common funds
        w_overlap = sum(min(alloc_map_str.get(c, 0), at_alloc.get(c, 0)) for c in common)

        # Category similarity
        at_metrics = at.get("metrics", {})
        at_cagr = at_metrics.get("expected_cagr") or at_metrics.get("cagr_pct") or 0
        at_cagr = float(at_cagr) if at_cagr else 0

        similarity_score = round((jaccard * 40 + min(w_overlap, 60)) * 1.0, 1)

        archetype_matches.append({
            "archetype_id": at["id"],
            "similarity_score": similarity_score,
            "common_funds": len(common),
            "total_archetype_funds": len(at_codes),
            "weighted_overlap_pct": round(w_overlap, 1),
            "archetype_cagr": at_cagr,
            "archetype_confidence": at.get("confidence", {}).get("overall_score") or at.get("confidence", {}).get("score") or 0,
        })

    archetype_matches.sort(key=lambda x: -x["similarity_score"])

    # ── Gap analysis vs best matching archetype ────────────────────────────────
    gap_analysis = None
    if archetype_matches and archetypes:
        best_id = archetype_matches[0]["archetype_id"]
        best_at = next((a for a in archetypes if a["id"] == best_id), None)
        if best_at:
            at_fund_map = {
                str(f["scheme_code"] if isinstance(f, dict) else f):
                {
                    "scheme_code": str(f["scheme_code"] if isinstance(f, dict) else f),
                    "scheme_name": f.get("fund_name", f.get("scheme_name", f"Fund {f['scheme_code']}")) if isinstance(f, dict) else "",
                    "suggested_weight": float(f.get("weight") or f.get("weight_pct") or 20) if isinstance(f, dict) else 20.0,
                    "composite_score": float(f.get("composite_score") or 0) if isinstance(f, dict) else 0.0,
                }
                for f in best_at["funds"]
            }
            # Enrich names from metadata already loaded
            for sc, fd in at_fund_map.items():
                if sc in meta:
                    fd["scheme_name"] = meta[sc].get("scheme_name", fd["scheme_name"])

            common = user_codes_str & set(at_fund_map.keys())
            missing_codes = set(at_fund_map.keys()) - user_codes_str
            extra_codes = user_codes_str - set(at_fund_map.keys())

            gap_analysis = {
                "archetype_id": best_id,
                "missing_funds": [at_fund_map[sc] for sc in missing_codes],
                "extra_funds": [
                    {
                        "scheme_code": sc,
                        "scheme_name": meta.get(sc, {}).get("scheme_name", f"Fund {sc}"),
                        "allocation_pct": round(alloc_map_str.get(sc, 0), 1),
                    }
                    for sc in extra_codes
                ],
                "overlap_pct": round(archetype_matches[0]["weighted_overlap_pct"], 1),
            }

    return {
        "portfolio_metrics": portfolio_metrics,
        "fund_details": fund_details,
        "archetype_matches": archetype_matches,
        "gap_analysis": gap_analysis,
        "horizon_years": request.horizon_years,
        "missing_data_codes": [c for c in codes if c not in fund_scores_cache],
    }


# ══════════════════════════════════════════════════════════════════════════════
# PRIORITY 13a+13b — HISTORICAL SIP BACKTEST + PROBABILISTIC SIMULATION
# ══════════════════════════════════════════════════════════════════════════════

class BacktestRequest(BaseModel):
    monthly_sip: float = 10000
    horizon_years: int = 7
    future_years: int = 5


@app.post("/api/bouquets/{archetype_id}/backtest")
async def bouquet_backtest(archetype_id: str, body: BacktestRequest):
    import random
    horizon_years = max(1, min(30, body.horizon_years))
    future_years = max(1, min(10, body.future_years))

    # ── Fetch archetype fund weights from cache ────────────────────────────────
    row = get_latest_cache(archetype_id, 7)
    if not row:
        # Try any cached entry for this archetype
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT funds_json FROM bouquet_cache WHERE archetype_id = %s "
            "AND is_active = TRUE ORDER BY computation_date DESC LIMIT 1",
            (archetype_id,)
        )
        r = cur.fetchone()
        cur.close(); conn.close()
        if not r:
            raise HTTPException(404, "Archetype not found in cache")
        funds_raw = json.loads(r[0]) if isinstance(r[0], str) else r[0]
    else:
        funds_raw = json.loads(row[0]) if isinstance(row[0], str) else row[0]

    fund_weights = {}
    for f in funds_raw:
        code = str(f["scheme_code"])
        w = float(f.get("weight") or f.get("weight_pct") or 20)
        fund_weights[code] = w
    total_w = sum(fund_weights.values())
    fund_weights = {k: v / total_w for k, v in fund_weights.items()}

    # ── Determine start date (horizon or fund availability) ───────────────────
    from datetime import timedelta
    today = date.today()
    requested_start = today.replace(year=today.year - horizon_years)

    conn = get_db()
    cur = conn.cursor()

    # Get monthly first NAV for each fund
    fund_navs = {}
    actual_starts = []
    for code in fund_weights:
        cur.execute("""
            SELECT DISTINCT ON (DATE_TRUNC('month', nav_date))
                DATE_TRUNC('month', nav_date)::date AS month,
                nav_value
            FROM nav_data
            WHERE scheme_code = %s AND nav_date >= %s
            ORDER BY DATE_TRUNC('month', nav_date), nav_date
        """, (code, requested_start))
        rows = cur.fetchall()
        if rows:
            fund_navs[code] = {r[0].strftime("%Y-%m"): float(r[1]) for r in rows}
            actual_starts.append(rows[0][0])

    # Nifty 50 monthly
    cur.execute("""
        SELECT DISTINCT ON (DATE_TRUNC('month', price_date))
            DATE_TRUNC('month', price_date)::date AS month,
            closing_value
        FROM benchmark_data
        WHERE index_name = 'Nifty 50' AND price_date >= %s
        ORDER BY DATE_TRUNC('month', price_date), price_date
    """, (requested_start,))
    nifty_navs = {r[0].strftime("%Y-%m"): float(r[1]) for r in cur.fetchall()}
    cur.close(); conn.close()

    # ── Build common month list ────────────────────────────────────────────────
    common_start = max(actual_starts) if actual_starts else requested_start
    months = []
    m = common_start.replace(day=1)
    end_month = today.replace(day=1)
    while m <= end_month:
        months.append(m.strftime("%Y-%m"))
        if m.month == 12:
            m = m.replace(year=m.year + 1, month=1)
        else:
            m = m.replace(month=m.month + 1)

    # ── SIP simulation ─────────────────────────────────────────────────────────
    fund_units = {code: 0.0 for code in fund_weights}
    nifty_units = 0.0
    total_invested = 0.0
    series = []

    # Also collect weighted monthly returns for Monte Carlo
    prev_nav = None
    monthly_returns = []

    for month in months:
        navs = {}
        all_ok = True
        for code in fund_weights:
            nav = fund_navs.get(code, {}).get(month)
            if nav is None:
                all_ok = False
                break
            navs[code] = nav
        nifty_nav = nifty_navs.get(month)
        if not all_ok or not nifty_nav:
            continue

        # Record weighted return before investing this month
        curr_nav_wtd = sum(fund_weights[c] * navs[c] for c in fund_weights)
        if prev_nav is not None and prev_nav > 0:
            monthly_returns.append(curr_nav_wtd / prev_nav - 1)
        prev_nav = curr_nav_wtd

        # Invest
        total_invested += body.monthly_sip
        for code, w in fund_weights.items():
            fund_units[code] += (body.monthly_sip * w) / navs[code]
        nifty_units += body.monthly_sip / nifty_nav

        # Portfolio value
        bouquet_val = sum(fund_units[c] * navs[c] for c in fund_weights)
        nifty_val = nifty_units * nifty_nav
        series.append({
            "m": month,
            "b": round(bouquet_val),
            "n": round(nifty_val),
            "i": round(total_invested),
        })

    # ── Historical summary ─────────────────────────────────────────────────────
    n_months = len(series)
    summary = {}
    if n_months > 0 and total_invested > 0:
        fin = series[-1]
        r_mo = 0.07 / 12
        fd_val = body.monthly_sip * ((1 + r_mo) ** n_months - 1) / r_mo * (1 + r_mo)
        b_cagr = ((fin["b"] / total_invested) ** (12 / n_months) - 1) * 100 if fin["b"] > 0 else 0
        n_cagr = ((fin["n"] / total_invested) ** (12 / n_months) - 1) * 100 if fin["n"] > 0 else 0
        summary = {
            "total_invested": round(total_invested),
            "bouquet_final": fin["b"],
            "nifty_final": fin["n"],
            "fd_final": round(fd_val),
            "bouquet_cagr": round(b_cagr, 2),
            "nifty_cagr": round(n_cagr, 2),
            "months": n_months,
            "actual_start": series[0]["m"] if series else None,
        }

    # ── Monte Carlo future projection ─────────────────────────────────────────
    future_bands = []
    if monthly_returns and n_months >= 12:
        N_SIM = 500
        n_future = future_years * 12
        year_buckets = {yr: [] for yr in range(1, future_years + 1)}
        for _ in range(N_SIM):
            v = 0.0
            for mo in range(1, n_future + 1):
                r = random.choice(monthly_returns)
                v = (v + body.monthly_sip) * (1 + r)
                if mo % 12 == 0:
                    year_buckets[mo // 12].append(v)
        for yr in range(1, future_years + 1):
            vals = sorted(year_buckets[yr])
            n = len(vals)
            future_bands.append({
                "y": yr,
                "p10": round(vals[max(0, int(n * 0.10))]),
                "p25": round(vals[max(0, int(n * 0.25))]),
                "p50": round(vals[max(0, int(n * 0.50))]),
                "p75": round(vals[max(0, int(n * 0.75))]),
                "p90": round(vals[min(n - 1, int(n * 0.90))]),
                "i": round(body.monthly_sip * yr * 12),
            })

    return {
        "series": series,
        "summary": summary,
        "future": future_bands,
        "monthly_sip": body.monthly_sip,
        "future_years": future_years,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PRIORITY 13c — FUND DETAIL PAGE
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/funds/{scheme_code}/detail")
async def fund_detail(scheme_code: str):
    conn = get_db()
    cur = conn.cursor()
    try:
        # Fund metadata
        cur.execute("""
            SELECT scheme_name, sebi_category, fund_type, aum_crores, expense_ratio
            FROM fund_metadata WHERE scheme_code = %s
        """, (scheme_code,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Fund not found")
        name, category, fund_type, aum, expense_ratio = row

        # Manager
        cur.execute("""
            SELECT manager_name, appointment_date FROM fund_managers
            WHERE scheme_code = %s ORDER BY appointment_date DESC LIMIT 1
        """, (scheme_code,))
        mgr = cur.fetchone()
        manager_name = mgr[0] if mgr else None
        appt_date = str(mgr[1]) if mgr and mgr[1] else None

        # Monthly NAV last 5 years
        cur.execute("""
            SELECT DISTINCT ON (DATE_TRUNC('month', nav_date))
                DATE_TRUNC('month', nav_date)::date AS month, nav_value
            FROM nav_data
            WHERE scheme_code = %s AND nav_date >= CURRENT_DATE - INTERVAL '5 years'
            ORDER BY DATE_TRUNC('month', nav_date), nav_date
        """, (scheme_code,))
        nav_series = [{"m": str(r[0]), "v": float(r[1])} for r in cur.fetchall()]

        # Current NAV
        cur.execute("SELECT nav_value FROM nav_data WHERE scheme_code = %s ORDER BY nav_date DESC LIMIT 1", (scheme_code,))
        curr_row = cur.fetchone()
        curr_nav = float(curr_row[0]) if curr_row else None

        # Rolling returns (fund)
        def fund_nav_at(interval_str):
            cur.execute(
                "SELECT nav_value FROM nav_data WHERE scheme_code = %s "
                "AND nav_date <= CURRENT_DATE - INTERVAL %s ORDER BY nav_date DESC LIMIT 1",
                (scheme_code, interval_str)
            )
            r = cur.fetchone()
            return float(r[0]) if r else None

        r1 = fund_nav_at("1 year");  r3 = fund_nav_at("3 years");  r5 = fund_nav_at("5 years")
        rolling = {}
        if curr_nav and r1: rolling["1yr"] = round((curr_nav / r1 - 1) * 100, 2)
        if curr_nav and r3: rolling["3yr"] = round(((curr_nav / r3) ** (1/3) - 1) * 100, 2)
        if curr_nav and r5: rolling["5yr"] = round(((curr_nav / r5) ** (1/5) - 1) * 100, 2)

        # Nifty 50 rolling returns
        def nifty_at(interval_str):
            cur.execute(
                "SELECT closing_value FROM benchmark_data WHERE index_name = 'Nifty 50' "
                "AND price_date <= CURRENT_DATE - INTERVAL %s ORDER BY price_date DESC LIMIT 1",
                (interval_str,)
            )
            r = cur.fetchone()
            return float(r[0]) if r else None

        cur.execute("SELECT closing_value FROM benchmark_data WHERE index_name = 'Nifty 50' ORDER BY price_date DESC LIMIT 1")
        nc = cur.fetchone(); nc_val = float(nc[0]) if nc else None
        n1 = nifty_at("1 year"); n3 = nifty_at("3 years"); n5 = nifty_at("5 years")
        nifty_rolling = {}
        if nc_val and n1: nifty_rolling["1yr"] = round((nc_val / n1 - 1) * 100, 2)
        if nc_val and n3: nifty_rolling["3yr"] = round(((nc_val / n3) ** (1/3) - 1) * 100, 2)
        if nc_val and n5: nifty_rolling["5yr"] = round(((nc_val / n5) ** (1/5) - 1) * 100, 2)

    finally:
        cur.close(); conn.close()

    return {
        "scheme_code": scheme_code,
        "name": name,
        "category": category,
        "fund_type": fund_type,
        "aum_cr": float(aum) if aum else None,
        "expense_ratio": float(expense_ratio) if expense_ratio else None,
        "manager_name": manager_name,
        "appointment_date": appt_date,
        "nav_series": nav_series,
        "current_nav": curr_nav,
        "rolling_returns": rolling,
        "nifty_rolling": nifty_rolling,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PRIORITY 14c — FUND ELIGIBILITY / "WHY NOT IN BOUQUET?" ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/funds/{scheme_code}/eligibility")
async def fund_eligibility(scheme_code: str):
    """Explain why a fund is or isn't in any bouquet archetype."""
    conn = get_db()
    cur = conn.cursor()
    try:
        # ── Fund metadata ──────────────────────────────────────────────────────
        cur.execute("""
            SELECT scheme_name, sebi_category, fund_type, aum_crores, expense_ratio
            FROM fund_metadata WHERE scheme_code = %s
        """, (scheme_code,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Fund not found in our database")
        name, category, fund_type, aum, expense_ratio = row
        aum = float(aum) if aum else None
        expense_ratio = float(expense_ratio) if expense_ratio else None

        # ── NAV history → tier ─────────────────────────────────────────────────
        cur.execute("""
            SELECT MIN(nav_date), MAX(nav_date), COUNT(*) FROM nav_data WHERE scheme_code = %s
        """, (scheme_code,))
        nav_row = cur.fetchone()
        nav_start, nav_end, nav_count = nav_row if nav_row else (None, None, 0)
        nav_years = 0
        if nav_start and nav_end:
            nav_years = (nav_end - nav_start).days / 365.25
        tier = 1 if nav_years >= 5 else (2 if nav_years >= 2 else 3)

        # ── Is it in any bouquet? ──────────────────────────────────────────────
        cur.execute("""
            SELECT archetype_id, funds_json FROM bouquet_cache
            WHERE is_active = TRUE ORDER BY computation_date DESC
        """)
        cache_rows = cur.fetchall()

        in_bouquets = []
        bouquet_scores = {}  # archetype_id -> composite_score of this fund
        all_bouquet_fund_scores = []

        for arch_id, fj in cache_rows:
            if arch_id in [b["archetype_id"] for b in in_bouquets]:
                continue  # already checked this archetype
            funds_list = json.loads(fj) if isinstance(fj, str) else fj
            for f in funds_list:
                sc = str(f.get("scheme_code", ""))
                cs = f.get("composite_score")
                if cs is not None:
                    all_bouquet_fund_scores.append(float(cs))
                if sc == str(scheme_code):
                    in_bouquets.append({
                        "archetype_id": arch_id,
                        "weight": f.get("weight") or f.get("weight_pct"),
                        "composite_score": float(cs) if cs is not None else None,
                    })
                    if cs is not None:
                        bouquet_scores[arch_id] = float(cs)

    finally:
        cur.close(); conn.close()

    # ── Eligibility checks ────────────────────────────────────────────────────
    is_direct = "direct" in name.lower() if name else False
    passes_direct = is_direct
    passes_aum = (aum is not None and aum >= 500)
    passes_expense = (expense_ratio is not None and expense_ratio <= 1.5)
    passes_tier = tier <= 2  # tier 3 not eligible
    overall_eligible = passes_direct and passes_aum and passes_expense and passes_tier

    # ── Build failure reasons ──────────────────────────────────────────────────
    reasons_not_included = []
    if in_bouquets:
        reasons_not_included = []  # it IS in a bouquet — no exclusion reasons
    else:
        if not passes_direct:
            reasons_not_included.append("Not a direct plan — only direct plans are considered (SEBI requires AMCs to offer both regular and direct variants; direct plans have no distributor commission)")
        if not passes_aum:
            reasons_not_included.append(
                f"AUM ₹{aum:.0f}Cr is below our ₹500Cr minimum — funds below this threshold have higher liquidity risk and are more susceptible to manager turnover impact"
                if aum else "AUM data not available — we require verifiable AUM ≥ ₹500Cr"
            )
        if not passes_expense:
            reasons_not_included.append(
                f"Expense ratio {expense_ratio:.2f}% exceeds our 1.5% ceiling — high TER is a structural drag on long-term compounding that no performance can reliably overcome"
                if expense_ratio else "Expense ratio data not available"
            )
        if not passes_tier:
            reasons_not_included.append(
                f"NAV history only {nav_years:.1f} years — we require ≥ 2 years to evaluate rolling returns, drawdown behaviour, and manager consistency through at least one market cycle"
            )
        if overall_eligible and not in_bouquets:
            min_bouquet_score = min(all_bouquet_fund_scores) if all_bouquet_fund_scores else None
            reasons_not_included.append(
                f"Fund passes all eligibility filters but was not selected. Our algorithm selects the highest-scoring fund per SEBI category within each archetype. "
                f"The lowest composite score among current bouquet funds is {min_bouquet_score:.1f}/100. "
                f"This fund's score may be below that threshold, or another fund in the same category scored higher."
                if min_bouquet_score else
                "Fund passes all eligibility filters. Selection is based on composite score ranking within each SEBI category."
            )

    return {
        "scheme_code": scheme_code,
        "name": name,
        "category": category,
        "fund_type": fund_type,
        "in_bouquets": in_bouquets,
        "eligibility": {
            "is_direct_plan": is_direct,
            "passes_direct": passes_direct,
            "aum_crores": aum,
            "passes_aum": passes_aum,
            "expense_ratio": expense_ratio,
            "passes_expense": passes_expense,
            "nav_years": round(nav_years, 1),
            "tier": tier,
            "passes_tier": passes_tier,
            "overall_eligible": overall_eligible,
        },
        "reasons_not_included": reasons_not_included,
        "lowest_bouquet_score": round(min(all_bouquet_fund_scores), 1) if all_bouquet_fund_scores else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PRIORITY 15 — USER PREFERENCES (MANAGER ALERTS + MONTHLY DIGEST)
# ══════════════════════════════════════════════════════════════════════════════

class PreferencesUpdate(BaseModel):
    manager_alert: Optional[bool] = None
    monthly_digest: Optional[bool] = None


def _require_user(authorization: Optional[str] = None):
    """Extract user_id from Bearer token; raise 401 if invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization[7:]
    import hashlib, base64
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, email, display_name FROM users WHERE password_hash = %s", (token,))
        row = cur.fetchone()
    finally:
        cur.close(); conn.close()
    if not row:
        raise HTTPException(401, "Invalid token")
    return {"id": row[0], "email": row[1], "display_name": row[2]}


@app.get("/api/user/preferences")
async def get_preferences(authorization: Optional[str] = _Header(default=None)):
    payload = _get_user_from_token(authorization)
    user_id = int(payload["sub"])
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT manager_alert, monthly_digest FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()
    finally:
        cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "User not found")
    return {"manager_alert": bool(row[0]), "monthly_digest": bool(row[1])}


@app.patch("/api/user/preferences")
async def update_preferences(body: PreferencesUpdate, authorization: Optional[str] = _Header(default=None)):
    payload = _get_user_from_token(authorization)
    user_id = int(payload["sub"])
    conn = get_db()
    cur = conn.cursor()
    try:
        if body.manager_alert is not None:
            cur.execute("UPDATE users SET manager_alert = %s WHERE id = %s", (body.manager_alert, user_id))
        if body.monthly_digest is not None:
            cur.execute("UPDATE users SET monthly_digest = %s WHERE id = %s", (body.monthly_digest, user_id))
        conn.commit()
    finally:
        cur.close(); conn.close()
    return {"ok": True}


# ── Background: check manager changes and alert users ─────────────────────────
def run_manager_change_alerts():
    """Called by nightly pipeline. Finds manager changes in last 30 days, emails affected users."""
    try:
        conn = get_db()
        cur = conn.cursor()
        # Recent confirmed manager changes
        cur.execute("""
            SELECT mcl.scheme_code, fm.scheme_name,
                   mcl.old_manager_name, mcl.new_manager_name, mcl.detected_date
            FROM manager_change_log mcl
            JOIN fund_metadata fm ON fm.scheme_code = mcl.scheme_code
            WHERE mcl.detected_date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY mcl.detected_date DESC
        """)
        changes = cur.fetchall()
        if not changes:
            cur.close(); conn.close()
            return
        change_codes = {str(c[0]) for c in changes}
        change_map = {str(c[0]): c for c in changes}

        # Users who want manager alerts
        cur.execute("""
            SELECT DISTINCT u.id, u.email, u.display_name
            FROM users u
            JOIN saved_bouquets sb ON sb.user_id = u.id
            WHERE u.manager_alert = TRUE
        """)
        users = cur.fetchall()
        cur.close(); conn.close()

        for uid, email, display_name in users:
            # Check their saved bouquets' funds
            conn2 = get_db(); cur2 = conn2.cursor()
            cur2.execute("SELECT snapshot_json FROM saved_bouquets WHERE user_id = %s", (uid,))
            bqs = cur2.fetchall()
            cur2.close(); conn2.close()
            affected = []
            for (snap,) in bqs:
                if snap:
                    funds = snap if isinstance(snap, list) else snap.get("funds", [])
                    for f in funds:
                        code = str(f.get("scheme_code", ""))
                        if code in change_codes:
                            c = change_map[code]
                            affected.append({"fund_name": c[1], "old_manager": c[2], "new_manager": c[3], "detected_date": str(c[4])})
            if affected:
                from api.alerts import send_manager_change_alert
                threading.Thread(target=send_manager_change_alert, args=(email, display_name, affected), daemon=True).start()
    except Exception as e:
        print(f"[P15] run_manager_change_alerts error: {e}")


# ── Background: send monthly digests ─────────────────────────────────────────
def run_monthly_digests():
    """Called monthly. Emails digest to opted-in users."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.email, u.display_name FROM users u WHERE u.monthly_digest = TRUE
        """)
        users = cur.fetchall()
        cur.close(); conn.close()
        for uid, email, display_name in users:
            conn2 = get_db(); cur2 = conn2.cursor()
            cur2.execute("""
                SELECT name, archetype_id, horizon_years, target_cagr
                FROM saved_bouquets WHERE user_id = %s ORDER BY saved_at DESC
            """, (uid,))
            bouquets = [{"name": r[0], "archetype_id": r[1], "horizon_years": r[2], "target_cagr": r[3]} for r in cur2.fetchall()]
            cur2.close(); conn2.close()
            if bouquets:
                from api.alerts import send_monthly_digest
                threading.Thread(target=send_monthly_digest, args=(email, display_name, bouquets), daemon=True).start()
    except Exception as e:
        print(f"[P15] run_monthly_digests error: {e}")


# Admin trigger endpoint (protected by API key in header)
@app.post("/api/admin/send-digests")
async def trigger_monthly_digests(x_admin_key: Optional[str] = None):
    expected = os.getenv("ADMIN_KEY", "")
    if not expected or x_admin_key != expected:
        raise HTTPException(403, "Forbidden")
    threading.Thread(target=run_monthly_digests, daemon=True).start()
    return {"ok": True, "message": "Monthly digest dispatch started"}


# ══════════════════════════════════════════════════════════════════════════════
# PRIORITY 16 — CAS IMPORT
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/portfolio/import-cas")
async def import_cas(file: UploadFile = File(...), authorization: Optional[str] = _Header(default=None)):
    """
    Accept a CAMS or KFintech CAS PDF, parse it. If the user is authenticated,
    also persist the holdings to user_portfolios so the My Portfolio dashboard works.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted. Export a CAS PDF from CAMS Online or KFintech.")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 15 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 15 MB).")
    if len(pdf_bytes) < 1024:
        raise HTTPException(400, "File appears empty or corrupted.")

    from engine.cas_parser import parse_cas_pdf
    result = parse_cas_pdf(pdf_bytes)

    # If authenticated, persist holdings to user_portfolios
    user_id = None
    if authorization:
        try:
            from api.auth import decode_token
            payload = decode_token(authorization.removeprefix("Bearer ").strip())
            user_id = payload.get("sub")
        except Exception:
            pass

    if user_id and result.get("holdings"):
        conn = get_db()
        cur = conn.cursor()
        try:
            saved = 0
            for h in result["holdings"]:
                sc = h.get("scheme_code")
                if not sc:
                    continue
                cur.execute(
                    """INSERT INTO user_portfolios
                           (user_id, scheme_code, fund_name_raw, folio_number, units, nav_at_import,
                            value_at_import, avg_cost_per_unit, import_source, cas_date)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'cas', CURRENT_DATE)
                       ON CONFLICT (user_id, scheme_code)
                       DO UPDATE SET units=EXCLUDED.units, nav_at_import=EXCLUDED.nav_at_import,
                           value_at_import=EXCLUDED.value_at_import, avg_cost_per_unit=EXCLUDED.avg_cost_per_unit,
                           fund_name_raw=EXCLUDED.fund_name_raw, folio_number=EXCLUDED.folio_number,
                           import_source='cas', cas_date=CURRENT_DATE, imported_at=NOW()""",
                    (user_id, sc, h.get("fund_name_raw"), h.get("folio"),
                     h.get("units"), h.get("nav"), h.get("value"), h.get("nav"))
                )
                saved += 1

            # Persist transactions (deduplicate by scheme_code + txn_date + amount)
            txns_saved = 0
            for t in result.get("transactions", []):
                sc = t.get("scheme_code")
                txn_date = t.get("txn_date")
                if not txn_date:
                    continue
                try:
                    cur.execute(
                        """INSERT INTO user_transactions
                               (user_id, scheme_code, folio_number, txn_type, txn_date,
                                description, amount, nav, units, balance_units, is_redemption)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT DO NOTHING""",
                        (user_id, sc, t.get("folio"), t.get("txn_type"), txn_date,
                         t.get("description"), t.get("amount"), t.get("nav"),
                         t.get("units"), t.get("balance_units"),
                         t.get("is_redemption", False))
                    )
                    txns_saved += cur.rowcount
                except Exception:
                    pass

            conn.commit()
            result["saved_to_portfolio"] = saved
            result["transactions_saved"] = txns_saved
        except Exception as e:
            conn.rollback()
            result["save_error"] = str(e)[:120]
        finally:
            cur.close()
            conn.close()

    return result


@app.get("/api/portfolio/my-holdings")
def get_my_holdings(authorization: Optional[str] = _Header(default=None)):
    """Return the authenticated user's stored holdings with current NAV and P&L."""
    user = _get_user_from_token(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT up.scheme_code, up.fund_name_raw, up.units,
                      up.nav_at_import, up.value_at_import, up.cas_date, up.imported_at,
                      fm.scheme_name, fm.amc_name, fm.sebi_category,
                      (SELECT nd.nav_value FROM nav_data nd WHERE nd.scheme_code = up.scheme_code
                       ORDER BY nd.nav_date DESC LIMIT 1) AS current_nav,
                      (SELECT nd2.nav_value FROM nav_data nd2 WHERE nd2.scheme_code = up.scheme_code
                       ORDER BY nd2.nav_date DESC LIMIT 1 OFFSET 1) AS prev_nav,
                      (SELECT nd3.nav_date FROM nav_data nd3 WHERE nd3.scheme_code = up.scheme_code
                       ORDER BY nd3.nav_date DESC LIMIT 1) AS nav_date
               FROM user_portfolios up
               LEFT JOIN fund_metadata fm ON fm.scheme_code = up.scheme_code
               WHERE up.user_id = %s
               ORDER BY up.value_at_import DESC""",
            (user["id"],)
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    holdings = []
    total_import_val = 0.0
    total_current_val = 0.0

    for r in rows:
        (sc, fname_raw, units, nav_imp, val_imp, cas_date, imported_at,
         scheme_name, amc_name, category, cur_nav, prev_nav, nav_date) = r

        units_f = float(units or 0)
        nav_imp_f = float(nav_imp or 0)
        val_imp_f = float(val_imp or 0)
        cur_nav_f = float(cur_nav or nav_imp_f)
        prev_nav_f = float(prev_nav or cur_nav_f)

        current_val = units_f * cur_nav_f
        pnl_abs = current_val - val_imp_f
        pnl_pct = (pnl_abs / val_imp_f * 100) if val_imp_f > 0 else 0.0
        day_change_pct = ((cur_nav_f - prev_nav_f) / prev_nav_f * 100) if prev_nav_f > 0 else 0.0
        day_change_abs = units_f * (cur_nav_f - prev_nav_f)

        total_import_val += val_imp_f
        total_current_val += current_val

        holdings.append({
            "scheme_code": sc,
            "fund_name": scheme_name or fname_raw or sc,
            "fund_name_raw": fname_raw,
            "amc_name": amc_name or "",
            "category": category or "",
            "units": round(units_f, 3),
            "nav_at_import": round(nav_imp_f, 4),
            "value_at_import": round(val_imp_f, 2),
            "current_nav": round(cur_nav_f, 4),
            "current_value": round(current_val, 2),
            "pnl_abs": round(pnl_abs, 2),
            "pnl_pct": round(pnl_pct, 2),
            "day_change_pct": round(day_change_pct, 2),
            "day_change_abs": round(day_change_abs, 2),
            "nav_date": str(nav_date) if nav_date else None,
            "cas_date": str(cas_date) if cas_date else None,
        })

    total_pnl = total_current_val - total_import_val
    total_pnl_pct = (total_pnl / total_import_val * 100) if total_import_val > 0 else 0.0

    # Category allocation
    cat_alloc: dict = {}
    for h in holdings:
        cat = (h["category"] or "Other").split(" - ")[-1][:30]
        cat_alloc[cat] = cat_alloc.get(cat, 0) + h["current_value"]

    cat_alloc_pct = {}
    if total_current_val > 0:
        cat_alloc_pct = {k: round(v / total_current_val * 100, 1) for k, v in
                         sorted(cat_alloc.items(), key=lambda x: -x[1])}

    return {
        "holdings": holdings,
        "summary": {
            "fund_count": len(holdings),
            "total_value_at_import": round(total_import_val, 2),
            "total_current_value": round(total_current_val, 2),
            "total_pnl_abs": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
        },
        "category_allocation": cat_alloc_pct,
    }


@app.delete("/api/portfolio/reset")
def reset_portfolio(authorization: Optional[str] = _Header(default=None)):
    """Delete all holdings for the authenticated user."""
    user = _get_user_from_token(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM user_transactions WHERE user_id = %s", (user["id"],))
        cur.execute("DELETE FROM user_portfolios WHERE user_id = %s", (user["id"],))
        deleted = cur.rowcount
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return {"deleted": deleted}


@app.post("/api/portfolio/add-holding")
def add_holding_manual(
    body: dict,
    authorization: Optional[str] = _Header(default=None)
):
    """
    Manually add or update one or more holdings.
    body: { holdings: [ {scheme_code, units, avg_cost_per_unit?, value?} ] }
    Upserts into user_portfolios with import_source='manual'.
    """
    user = _get_user_from_token(authorization)
    items = body.get("holdings", [])
    if not items:
        raise HTTPException(status_code=400, detail="holdings list is required")

    conn = get_db()
    cur = conn.cursor()
    saved = 0
    errors = []
    try:
        for item in items:
            sc = str(item.get("scheme_code", "")).strip()
            if not sc:
                errors.append("scheme_code is required for each holding")
                continue
            units = float(item.get("units") or 0)
            if units <= 0:
                errors.append(f"{sc}: units must be positive")
                continue
            avg_cost = item.get("avg_cost_per_unit")
            value = item.get("value")
            if avg_cost:
                avg_cost = float(avg_cost)
                nav_at_import = avg_cost
                value_at_import = units * avg_cost if value is None else float(value)
            elif value:
                value_at_import = float(value)
                nav_at_import = value_at_import / units
                avg_cost = nav_at_import
            else:
                nav_at_import = None
                value_at_import = None
                avg_cost = None

            # Look up fund name if not provided
            fname = item.get("fund_name")
            if not fname:
                cur.execute("SELECT scheme_name FROM fund_metadata WHERE scheme_code = %s", (sc,))
                row = cur.fetchone()
                fname = row[0] if row else sc

            cur.execute(
                """INSERT INTO user_portfolios
                       (user_id, scheme_code, fund_name_raw, units, nav_at_import,
                        value_at_import, avg_cost_per_unit, import_source, cas_date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'manual', CURRENT_DATE)
                   ON CONFLICT (user_id, scheme_code)
                   DO UPDATE SET
                       units = EXCLUDED.units,
                       nav_at_import = COALESCE(EXCLUDED.nav_at_import, user_portfolios.nav_at_import),
                       value_at_import = COALESCE(EXCLUDED.value_at_import, user_portfolios.value_at_import),
                       avg_cost_per_unit = COALESCE(EXCLUDED.avg_cost_per_unit, user_portfolios.avg_cost_per_unit),
                       fund_name_raw = COALESCE(EXCLUDED.fund_name_raw, user_portfolios.fund_name_raw),
                       import_source = 'manual',
                       cas_date = CURRENT_DATE,
                       imported_at = NOW()""",
                (user["id"], sc, fname, units, nav_at_import, value_at_import, avg_cost)
            )
            saved += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e)[:200])
    finally:
        cur.close()
        conn.close()

    return {"saved": saved, "errors": errors}


@app.get("/api/portfolio/benchmark")
def get_portfolio_benchmark(authorization: Optional[str] = _Header(default=None)):
    """
    Compare portfolio performance vs Nifty 50 benchmark from import date to today.
    Returns absolute gain %, annualised CAGR for portfolio and benchmark over same period.
    """
    user = _get_user_from_token(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT up.scheme_code, up.units, up.nav_at_import, up.value_at_import, up.cas_date,
                      (SELECT nd.nav_value FROM nav_data nd WHERE nd.scheme_code = up.scheme_code
                       ORDER BY nd.nav_date DESC LIMIT 1) AS current_nav
               FROM user_portfolios up WHERE up.user_id = %s AND up.value_at_import > 0""",
            (user["id"],)
        )
        holding_rows = cur.fetchall()

        # Benchmark (Nifty 50) price on earliest cas_date and latest available
        cur.execute(
            """SELECT MIN(cas_date) FROM user_portfolios WHERE user_id = %s AND cas_date IS NOT NULL""",
            (user["id"],)
        )
        from_date = (cur.fetchone() or [None])[0]

        bench_start = bench_end = None
        if from_date:
            cur.execute(
                """SELECT closing_value FROM benchmark_data
                   WHERE index_code = 'NIFTY_50' AND price_date >= %s
                   ORDER BY price_date ASC LIMIT 1""",
                (from_date,)
            )
            r = cur.fetchone()
            bench_start = float(r[0]) if r else None

            cur.execute(
                """SELECT closing_value, price_date FROM benchmark_data
                   WHERE index_code = 'NIFTY_50'
                   ORDER BY price_date DESC LIMIT 1"""
            )
            r = cur.fetchone()
            bench_end = float(r[0]) if r else None
            bench_end_date = str(r[1]) if r else None
    finally:
        cur.close()
        conn.close()

    if not holding_rows:
        return {"has_data": False, "note": "No holdings with import value found."}

    from datetime import date as dt_date
    total_import_val = sum(float(r[3] or 0) for r in holding_rows)
    total_current_val = sum(float(r[1] or 0) * float(r[5] or r[2] or 0) for r in holding_rows)

    today = dt_date.today()
    from_date_dt = from_date if isinstance(from_date, dt_date) else (
        dt_date.fromisoformat(str(from_date)) if from_date else today
    )
    years = max((today - from_date_dt).days / 365.25, 0.01)

    pf_abs_gain_pct = ((total_current_val - total_import_val) / total_import_val * 100) if total_import_val > 0 else 0.0
    pf_cagr = (((total_current_val / total_import_val) ** (1 / years)) - 1) * 100 if total_import_val > 0 and total_current_val > 0 else None

    bench_abs_gain_pct = bench_cagr = None
    if bench_start and bench_end and bench_start > 0:
        bench_abs_gain_pct = (bench_end - bench_start) / bench_start * 100
        bench_cagr = (((bench_end / bench_start) ** (1 / years)) - 1) * 100

    return {
        "has_data": True,
        "from_date": str(from_date) if from_date else None,
        "to_date": str(today),
        "years": round(years, 2),
        "portfolio": {
            "import_value": round(total_import_val, 2),
            "current_value": round(total_current_val, 2),
            "abs_gain_pct": round(pf_abs_gain_pct, 2),
            "cagr_pct": round(pf_cagr, 2) if pf_cagr is not None else None,
        },
        "nifty50": {
            "start_value": round(bench_start, 2) if bench_start else None,
            "end_value": round(bench_end, 2) if bench_end else None,
            "abs_gain_pct": round(bench_abs_gain_pct, 2) if bench_abs_gain_pct is not None else None,
            "cagr_pct": round(bench_cagr, 2) if bench_cagr is not None else None,
            "end_date": bench_end_date if bench_end else None,
        },
        "alpha": round(pf_cagr - bench_cagr, 2) if pf_cagr is not None and bench_cagr is not None else None,
        "note": "Simple CAGR comparison from CAS import date. Not risk-adjusted.",
    }


@app.get("/api/portfolio/transactions")
def get_portfolio_transactions(
    scheme_code: Optional[str] = None,
    authorization: Optional[str] = _Header(default=None)
):
    """Return stored transaction history for the authenticated user."""
    user = _get_user_from_token(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        if scheme_code:
            cur.execute(
                """SELECT ut.id, ut.scheme_code, ut.folio_number, ut.txn_type, ut.txn_date,
                          ut.description, ut.amount, ut.nav, ut.units, ut.balance_units, ut.is_redemption,
                          fm.scheme_name
                   FROM user_transactions ut
                   LEFT JOIN fund_metadata fm ON fm.scheme_code = ut.scheme_code
                   WHERE ut.user_id = %s AND ut.scheme_code = %s
                   ORDER BY ut.txn_date DESC""",
                (user["id"], scheme_code)
            )
        else:
            cur.execute(
                """SELECT ut.id, ut.scheme_code, ut.folio_number, ut.txn_type, ut.txn_date,
                          ut.description, ut.amount, ut.nav, ut.units, ut.balance_units, ut.is_redemption,
                          fm.scheme_name
                   FROM user_transactions ut
                   LEFT JOIN fund_metadata fm ON fm.scheme_code = ut.scheme_code
                   WHERE ut.user_id = %s
                   ORDER BY ut.txn_date DESC""",
                (user["id"],)
            )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    cols = ["id", "scheme_code", "folio_number", "txn_type", "txn_date",
            "description", "amount", "nav", "units", "balance_units", "is_redemption", "scheme_name"]
    txns = []
    for r in rows:
        d = dict(zip(cols, r))
        d["txn_date"] = str(d["txn_date"]) if d["txn_date"] else None
        d["amount"] = float(d["amount"]) if d["amount"] else None
        d["nav"] = float(d["nav"]) if d["nav"] else None
        d["units"] = float(d["units"]) if d["units"] else None
        d["balance_units"] = float(d["balance_units"]) if d["balance_units"] else None
        txns.append(d)

    return {"transactions": txns, "count": len(txns)}


@app.get("/api/portfolio/performance")
def get_portfolio_performance(authorization: Optional[str] = _Header(default=None)):
    """
    Compute XIRR-based performance for the authenticated user's portfolio.
    Uses stored transactions + current holdings for cash flow construction.
    """
    user = _get_user_from_token(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        # Load transactions
        cur.execute(
            """SELECT scheme_code, txn_date, amount, nav, units, is_redemption
               FROM user_transactions WHERE user_id = %s ORDER BY txn_date""",
            (user["id"],)
        )
        txn_rows = cur.fetchall()

        # Load current holdings with live NAV and fund name
        cur.execute(
            """SELECT up.scheme_code, up.units,
                      (SELECT nd.nav_value FROM nav_data nd WHERE nd.scheme_code = up.scheme_code
                       ORDER BY nd.nav_date DESC LIMIT 1) AS current_nav,
                      COALESCE(fm.scheme_name, up.fund_name_raw, up.scheme_code) AS fund_name
               FROM user_portfolios up
               LEFT JOIN fund_metadata fm ON fm.scheme_code = up.scheme_code
               WHERE up.user_id = %s""",
            (user["id"],)
        )
        holding_rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    from engine.xirr import compute_xirr, build_cash_flows

    transactions = [
        {"txn_date": r[1], "amount": float(r[2] or 0),
         "nav": float(r[3] or 0), "units": float(r[4] or 0),
         "is_redemption": r[5], "scheme_code": r[0]}
        for r in txn_rows
    ]
    holdings = [{"scheme_code": r[0], "units": float(r[1] or 0)} for r in holding_rows]
    nav_lookup = {r[0]: float(r[2] or 0) for r in holding_rows if r[2]}
    name_lookup = {r[0]: r[3] for r in holding_rows}

    total_invested = sum(abs(t["amount"]) for t in transactions if not t["is_redemption"])
    total_redeemed = sum(abs(t["amount"]) for t in transactions if t["is_redemption"])
    current_value = sum(h["units"] * nav_lookup.get(h["scheme_code"], 0) for h in holdings)

    xirr_val = None
    if transactions:
        cash_flows = build_cash_flows(transactions, holdings, nav_lookup)
        if len(cash_flows) >= 2:
            xirr_val = compute_xirr(cash_flows)

    # Per-fund XIRR — keyed by scheme_code, with fund name included
    per_fund = {}
    scheme_codes = list({t["scheme_code"] for t in transactions if t["scheme_code"]})
    for sc in scheme_codes:
        sc_txns = [t for t in transactions if t["scheme_code"] == sc]
        sc_holdings = [h for h in holdings if h["scheme_code"] == sc]
        sc_flows = build_cash_flows(sc_txns, sc_holdings, nav_lookup)
        if len(sc_flows) >= 2:
            xirr_sc = compute_xirr(sc_flows)
            if xirr_sc is not None:
                per_fund[sc] = {
                    "xirr_pct": round(xirr_sc * 100, 2),
                    "fund_name": name_lookup.get(sc, sc),
                }

    return {
        "xirr_pct": round(xirr_val * 100, 2) if xirr_val is not None else None,
        "total_invested": round(total_invested, 2),
        "total_redeemed": round(total_redeemed, 2),
        "current_value": round(current_value, 2),
        "absolute_gain": round(current_value + total_redeemed - total_invested, 2),
        "has_transactions": len(transactions) > 0,
        "transaction_count": len(transactions),
        "per_fund_xirr": per_fund,
        "note": "XIRR computed from CAS transaction history. Import a fresh CAS for accurate results." if transactions else "No transaction history found. Import a CAS PDF to enable performance tracking.",
    }


@app.get("/api/portfolio/tax-report")
def get_tax_report(
    fy: Optional[str] = None,
    authorization: Optional[str] = _Header(default=None)
):
    """
    Generate LTCG/STCG tax report for the authenticated user.
    fy: financial year e.g. '2024-25'. Defaults to current FY.
    Uses FIFO lot matching on stored transactions.
    """
    user = _get_user_from_token(authorization)

    from datetime import date as dt_date
    today = dt_date.today()
    if fy:
        try:
            fy_start_yr = int(fy.split("-")[0])
        except Exception:
            fy_start_yr = today.year if today.month >= 4 else today.year - 1
    else:
        fy_start_yr = today.year if today.month >= 4 else today.year - 1

    fy_start = dt_date(fy_start_yr, 4, 1)
    fy_end = dt_date(fy_start_yr + 1, 3, 31)
    fy_label = f"{fy_start_yr}-{str(fy_start_yr + 1)[2:]}"

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT ut.scheme_code, ut.txn_date, ut.units, ut.nav, ut.is_redemption,
                      fm.sebi_category, fm.scheme_name
               FROM user_transactions ut
               LEFT JOIN fund_metadata fm ON fm.scheme_code = ut.scheme_code
               WHERE ut.user_id = %s AND ut.units IS NOT NULL AND ut.nav IS NOT NULL
               ORDER BY ut.scheme_code, ut.txn_date""",
            (user["id"],)
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    from engine.xirr import fifo_realized_gains, compute_tax_summary

    # Group by scheme_code
    by_fund: dict = {}
    for r in rows:
        sc = r[0]
        if sc not in by_fund:
            by_fund[sc] = {"scheme_name": r[6] or sc, "category": r[5] or "", "txns": []}
        by_fund[sc]["txns"].append({
            "txn_date": str(r[1]),
            "units": float(r[2]) if not r[4] else -float(r[2]),  # negative for redemptions
            "nav": float(r[3]),
            "is_redemption": r[4],
        })

    fund_reports = []
    total_ltcg = 0.0
    total_stcg = 0.0

    for sc, fd in by_fund.items():
        realized = fifo_realized_gains(fd["txns"])
        # Filter to redemptions within the FY
        fy_realized = [g for g in realized
                       if fy_start <= (g["sell_date"] if isinstance(g["sell_date"], dt_date)
                                       else dt_date.fromisoformat(str(g["sell_date"]))) <= fy_end]

        if not fy_realized:
            continue

        cat = fd["category"].lower()
        fund_type = "equity" if any(k in cat for k in ["equity", "elss", "flexi", "mid", "small", "large", "multi"]) else "debt"

        tax = compute_tax_summary(fy_realized, fund_type)
        total_ltcg += tax["ltcg_gross"]
        total_stcg += tax["stcg_gross"]

        fund_reports.append({
            "scheme_code": sc,
            "scheme_name": fd["scheme_name"],
            "fund_type": fund_type,
            "lots_redeemed": len(fy_realized),
            **tax,
        })

    overall = compute_tax_summary(
        [{"purchase_date": None, "sell_date": fy_end, "gain_amount": g, "units": 0}
         for g in [total_ltcg - total_stcg]],  # dummy — computed below properly
        "equity"
    )
    overall_ltcg_tax = max(0, total_ltcg - 125000) * 0.125
    overall_stcg_tax = max(0, total_stcg) * 0.20

    return {
        "financial_year": fy_label,
        "fund_reports": fund_reports,
        "summary": {
            "total_ltcg": round(total_ltcg, 2),
            "total_stcg": round(total_stcg, 2),
            "ltcg_exempt": min(total_ltcg, 125000) if total_ltcg > 0 else 0,
            "ltcg_taxable": round(max(0, total_ltcg - 125000), 2),
            "ltcg_tax": round(overall_ltcg_tax, 2),
            "stcg_tax": round(overall_stcg_tax, 2),
            "total_tax": round(overall_ltcg_tax + overall_stcg_tax, 2),
        },
        "note": "Based on FIFO lot matching of CAS transactions. Verify with your CA before filing.",
        "has_data": len(fund_reports) > 0,
    }


# ---------------------------------------------------------------------------
# INDEX FUND COMPARISON  (Priority 26)
# ---------------------------------------------------------------------------

_index_compare_cache: dict = {}
_index_compare_lock = threading.Lock()
_INDEX_COMPARE_TTL = 4 * 3600  # 4 hours

@app.get("/api/index-funds/compare")
def get_index_fund_compare():
    """
    Return tracking error, tracking difference, and key metrics
    for all curated index fund groups.
    Cached in memory for 4 hours — computation takes ~3-5s.
    """
    import time
    now = time.time()
    with _index_compare_lock:
        cached = _index_compare_cache.get("data")
        ts = _index_compare_cache.get("ts", 0)
        if cached is not None and (now - ts) < _INDEX_COMPARE_TTL:
            return {"groups": cached, "cached": True, "aum_note": "approx May 2026"}

    try:
        from engine.index_fund_metrics import get_all_index_comparisons
        groups = get_all_index_comparisons()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Index comparison error: {e}")

    with _index_compare_lock:
        _index_compare_cache["data"] = groups
        _index_compare_cache["ts"] = now

    return {"groups": groups, "cached": False, "aum_note": "approx May 2026"}


@app.get("/api/index-funds/core-satellite")
def get_core_satellite(
    core_index: str = Query(default="nifty50", description="Index group id for core"),
    horizon: int = Query(default=7, description="Horizon years for satellite scoring"),
):
    """
    Return a core-satellite portfolio suggestion.
    Core: lowest tracking-error fund from chosen index at 55%.
    Satellite: top 3 active mid/small cap funds from computed_metrics at 45%.
    """
    valid_indices = {"nifty50", "niftynxt50", "sensex"}
    if core_index not in valid_indices:
        raise HTTPException(status_code=400, detail=f"core_index must be one of {valid_indices}")
    if horizon not in (5, 7, 10):
        raise HTTPException(status_code=400, detail="horizon must be 5, 7, or 10")

    try:
        from engine.index_fund_metrics import get_core_satellite_suggestion
        result = get_core_satellite_suggestion(core_index=core_index, satellite_horizon=horizon)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Core-satellite error: {e}")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# PRIORITY 31 — FUND COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

_DIM_LABELS = {
    "return_consistency_score": "Return Consistency",
    "risk_adjusted_score":      "Risk-Adjusted Quality",
    "downside_score":           "Downside Protection",
    "manager_score":            "Manager Stability",
    "portfolio_quality_score":  "Portfolio Quality",
    "forward_context_score":    "Forward Context",
}

_DIM_WEIGHTS = {
    "return_consistency_score": 25,
    "risk_adjusted_score":      20,
    "downside_score":           20,
    "manager_score":            15,
    "portfolio_quality_score":  10,
    "forward_context_score":    10,
}


def _generate_verdict(funds: list, horizon_years: int) -> dict:
    """
    Produce a plain-language comparison verdict from scored fund dicts.
    Returns {winner_code, winner_name, summary, dimension_winners, score_wins}.
    """
    if not funds:
        return {}

    dims = list(_DIM_LABELS.keys())

    # Find per-dimension winners
    dim_winners: dict = {}
    for dim in dims:
        vals = [(f["scheme_code"], float(f.get(dim) or 0)) for f in funds]
        best_val = max(v for _, v in vals)
        winners = [c for c, v in vals if v == best_val]
        dim_winners[dim] = winners[0] if len(winners) == 1 else None  # None = tie

    # Count dimension wins per fund
    score_wins: dict = {f["scheme_code"]: 0 for f in funds}
    for dim, winner_code in dim_winners.items():
        if winner_code:
            score_wins[winner_code] = score_wins.get(winner_code, 0) + 1

    # Overall winner by composite score
    overall_winner = max(funds, key=lambda f: float(f.get("fund_score") or 0))
    w = overall_winner
    losers = [f for f in funds if f["scheme_code"] != w["scheme_code"]]

    # Build natural-language summary
    w_name = w["scheme_name_short"]
    horizon_label = f"{horizon_years}-year"

    # Advantages: dimensions where winner leads all others
    leading_dims = [
        _DIM_LABELS[dim] for dim in dims
        if dim_winners.get(dim) == w["scheme_code"]
    ]

    # Cost comparison
    cheapest = min(funds, key=lambda f: float(f.get("expense_ratio") or 99))
    cost_note = ""
    if cheapest["scheme_code"] != w["scheme_code"] and cheapest.get("expense_ratio"):
        cost_note = (
            f" {cheapest['scheme_name_short']} has the lowest expense ratio "
            f"({cheapest['expense_ratio']}%), which compounds meaningfully over long horizons."
        )

    # Drawdown comparison
    safest = min(funds, key=lambda f: abs(float(f.get("max_drawdown_pct") or 0)))
    drawdown_note = ""
    if safest["scheme_code"] != w["scheme_code"]:
        drawdown_note = (
            f" {safest['scheme_name_short']} shows shallower drawdowns, "
            f"making it better suited for risk-averse investors."
        )

    if leading_dims:
        advantage_text = f"leads on {', '.join(leading_dims[:3])}"
    else:
        advantage_text = f"scores highest overall ({round(float(w.get('fund_score') or 0), 1)}/100)"

    loser_names = " and ".join(f["scheme_name_short"] for f in losers)
    compared_to = f" compared to {loser_names}" if loser_names else ""

    summary = (
        f"For a {horizon_label} horizon, {w_name} {advantage_text}{compared_to}. "
        f"Its composite score of {round(float(w.get('fund_score') or 0), 1)}/100 "
        f"reflects stronger risk-adjusted compounding over the chosen period."
        f"{cost_note}{drawdown_note}"
    )

    return {
        "winner_code":      w["scheme_code"],
        "winner_name":      w_name,
        "summary":          summary,
        "dimension_winners": {dim: dim_winners[dim] for dim in dims},
        "score_wins":       score_wins,
    }


@app.get("/api/funds/compare")
def compare_funds(
    codes: str = Query(..., description="Comma-separated scheme codes, 2–3 funds"),
    horizon_years: int = Query(default=7, description="Scoring horizon: 5, 7, 10, 15"),
):
    """
    Side-by-side comparison of 2–3 funds using FundGuldasta's scoring engine.
    Returns composite + 6-dimension scores, risk metrics, manager data, and a
    plain-language verdict.
    """
    raw_codes = [c.strip() for c in codes.split(",") if c.strip()]
    if len(raw_codes) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 scheme codes.")
    if len(raw_codes) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 funds can be compared at once.")
    if horizon_years not in (5, 7, 10, 15, 20):
        raise HTTPException(status_code=400, detail="horizon_years must be 5, 7, 10, 15, or 20.")

    conn = get_db()
    cur = conn.cursor()
    try:
        # Fetch latest computed_metrics for each fund at the requested horizon
        cur.execute(
            """
            SELECT DISTINCT ON (cm.scheme_code)
                cm.scheme_code,
                cm.horizon_years,
                cm.fund_score,
                cm.return_consistency_score,
                cm.risk_adjusted_score,
                cm.downside_score,
                cm.manager_score,
                cm.portfolio_quality_score,
                cm.forward_context_score,
                cm.cagr_pct,
                cm.rolling_cagr_mean,
                cm.rolling_cagr_std,
                cm.sharpe_ratio,
                cm.sortino_ratio,
                cm.max_drawdown_pct,
                cm.upside_capture,
                cm.downside_capture,
                fm.scheme_name,
                fm.amc_name,
                fm.sebi_category,
                fm.expense_ratio,
                fm.aum_crores,
                fm.inception_date
            FROM computed_metrics cm
            JOIN fund_metadata fm ON fm.scheme_code = cm.scheme_code
            WHERE cm.scheme_code = ANY(%s) AND cm.horizon_years = %s
            ORDER BY cm.scheme_code, cm.computation_date DESC
            """,
            (raw_codes, horizon_years)
        )
        metric_rows = cur.fetchall()
        metric_cols = [d[0] for d in cur.description]

        # Fetch manager info
        cur.execute(
            """
            SELECT fm2.scheme_code,
                   STRING_AGG(fm2.manager_name, ', ' ORDER BY fm2.appointment_date) AS managers,
                   MIN(fm2.appointment_date) AS earliest_appt
            FROM fund_managers fm2
            WHERE fm2.scheme_code = ANY(%s) AND fm2.is_current = true
            GROUP BY fm2.scheme_code
            """,
            (raw_codes,)
        )
        mgr_rows = {r[0]: {"managers": r[1], "earliest_appt": r[2]} for r in cur.fetchall()}

        # Fetch CAGR across horizons for each fund (5/7/10yr)
        cur.execute(
            """
            SELECT DISTINCT ON (scheme_code, horizon_years) scheme_code, horizon_years, cagr_pct
            FROM computed_metrics
            WHERE scheme_code = ANY(%s) AND horizon_years IN (5, 7, 10)
            ORDER BY scheme_code, horizon_years, computation_date DESC
            """,
            (raw_codes,)
        )
        cagr_multi: dict = {}
        for r in cur.fetchall():
            sc, h, cagr = r
            if sc not in cagr_multi:
                cagr_multi[sc] = {}
            cagr_multi[sc][h] = float(cagr) if cagr else None

        # Which bouquets include each fund?
        cur.execute(
            """
            SELECT archetype_id, funds_json FROM bouquet_cache
            WHERE is_active = true AND horizon_years = %s
            ORDER BY computation_date DESC
            """,
            (horizon_years,)
        )
        bouquet_membership: dict = {sc: [] for sc in raw_codes}
        import json as _json
        for arch_id, funds_json in cur.fetchall():
            try:
                funds_list = _json.loads(funds_json)
                for fd in funds_list:
                    sc = str(fd.get("scheme_code", ""))
                    if sc in bouquet_membership:
                        bouquet_membership[sc].append(arch_id)
            except Exception:
                pass

    finally:
        cur.close()
        conn.close()

    # Build fund dicts
    from datetime import date as _date
    today = _date.today()
    funds_out = []
    found_codes = set()

    for row in metric_rows:
        d = dict(zip(metric_cols, row))
        sc = d["scheme_code"]
        found_codes.add(sc)

        mgr_info = mgr_rows.get(sc, {})
        appt = mgr_info.get("earliest_appt")
        tenure_years = round((today - appt).days / 365.25, 1) if appt else None

        short_name = (d["scheme_name"] or sc)
        # Trim common suffixes for display
        for suffix in [" - Direct Plan - Growth", " Direct Plan Growth",
                       " Direct Growth", " - Direct - Growth", " Direct"]:
            if short_name.endswith(suffix):
                short_name = short_name[: -len(suffix)]
                break

        f = {
            "scheme_code":              sc,
            "scheme_name":              d["scheme_name"],
            "scheme_name_short":        short_name,
            "amc_name":                 d["amc_name"] or "",
            "category":                 d["sebi_category"] or "",
            "expense_ratio":            float(d["expense_ratio"]) if d["expense_ratio"] else None,
            "aum_crores":               float(d["aum_crores"]) if d["aum_crores"] else None,
            "inception_date":           str(d["inception_date"]) if d["inception_date"] else None,
            "manager_names":            mgr_info.get("managers", ""),
            "manager_tenure_years":     tenure_years,
            # Primary horizon metrics
            "fund_score":               float(d["fund_score"]) if d["fund_score"] else None,
            "return_consistency_score": float(d["return_consistency_score"]) if d["return_consistency_score"] else None,
            "risk_adjusted_score":      float(d["risk_adjusted_score"]) if d["risk_adjusted_score"] else None,
            "downside_score":           float(d["downside_score"]) if d["downside_score"] else None,
            "manager_score":            float(d["manager_score"]) if d["manager_score"] else None,
            "portfolio_quality_score":  float(d["portfolio_quality_score"]) if d["portfolio_quality_score"] else None,
            "forward_context_score":    float(d["forward_context_score"]) if d["forward_context_score"] else None,
            # Returns
            "cagr_pct":                 float(d["cagr_pct"]) if d["cagr_pct"] else None,
            "rolling_cagr_mean":        float(d["rolling_cagr_mean"]) if d["rolling_cagr_mean"] else None,
            "rolling_cagr_std":         float(d["rolling_cagr_std"]) if d["rolling_cagr_std"] else None,
            "cagr_5y":                  cagr_multi.get(sc, {}).get(5),
            "cagr_7y":                  cagr_multi.get(sc, {}).get(7),
            "cagr_10y":                 cagr_multi.get(sc, {}).get(10),
            # Risk
            "sharpe_ratio":             float(d["sharpe_ratio"]) if d["sharpe_ratio"] else None,
            "sortino_ratio":            float(d["sortino_ratio"]) if d["sortino_ratio"] else None,
            "max_drawdown_pct":         float(d["max_drawdown_pct"]) if d["max_drawdown_pct"] else None,
            "upside_capture":           float(d["upside_capture"]) if d["upside_capture"] else None,
            "downside_capture":         float(d["downside_capture"]) if d["downside_capture"] else None,
            # Context
            "in_bouquets":              bouquet_membership.get(sc, []),
        }
        funds_out.append(f)

    # Report any requested codes with no data
    missing = [c for c in raw_codes if c not in found_codes]

    verdict = _generate_verdict(funds_out, horizon_years)

    return {
        "funds":        funds_out,
        "horizon_years": horizon_years,
        "verdict":      verdict,
        "missing_codes": missing,
        "dimension_labels": _DIM_LABELS,
        "dimension_weights": _DIM_WEIGHTS,
    }
