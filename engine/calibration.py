"""
FUNDGULDASTA — Historical Calibration Engine (C2)
===================================================
Computes actual rolling-return achievement probabilities from live NAV data.
These figures provide data-calibrated estimates vs the hardcoded ACHIEVEMENT_PROB
table in cagr_advisor.py (which is based on Nifty 500 TRI estimates).

Algorithm:
  1. Sample start dates at monthly intervals across the full NAV history
  2. For each start date, find the NAV at start + horizon_years (nearest available)
  3. Compute CAGR for that window
  4. Return: % of windows that achieved each CAGR threshold

Public API:
  compute_rolling_achievement(horizon_years, scheme_codes=None) -> dict
  get_calibration_summary() -> dict   (cached, refreshed daily)
"""
import threading
import psycopg2
from datetime import date, timedelta
from config.db import get_db_config

_DB_CONFIG = get_db_config()

CALIBRATION_FUNDS = [
    '118825', '120152', '118834', '122639', '118955',
    '120505', '119071', '118989', '118778', '120828',
]

CAGR_THRESHOLDS = [7, 8, 10, 12, 14, 16, 18, 20, 22, 25]
CALIBRATION_HORIZONS = [3, 5, 7, 10]  # horizons with enough actual data


def compute_rolling_achievement(horizon_years: int, scheme_codes=None) -> dict:
    """
    For each fund in scheme_codes, sample monthly rolling windows of horizon_years.
    Returns {cagr_threshold: achievement_pct} aggregated across all funds.
    Returns {} if insufficient data.
    """
    codes = scheme_codes or CALIBRATION_FUNDS
    horizon_days = int(horizon_years * 365.25)
    all_cagrs = []

    conn = psycopg2.connect(**_DB_CONFIG)
    cur = conn.cursor()

    for code in codes:
        cur.execute(
            "SELECT nav_date, nav_value FROM nav_data WHERE scheme_code=%s ORDER BY nav_date",
            (code,)
        )
        rows = cur.fetchall()
        if len(rows) < 200:
            continue

        nav_by_date = {r[0]: float(r[1]) for r in rows}
        dates = sorted(nav_by_date.keys())

        # Build a fast lookup: for a target date, find the nearest available trading date
        date_set = set(dates)

        def nearest_date(target):
            for delta in range(11):
                for sign in (0, 1, -1):
                    d = target + timedelta(days=delta * sign)
                    if d in date_set:
                        return d
            return None

        # Sample start dates monthly (1st of each month)
        if not dates:
            continue
        start = dates[0]
        end = dates[-1]

        # Generate monthly sample dates
        current = date(start.year, start.month, 1)
        while current <= end:
            start_nav_date = nearest_date(current)
            if start_nav_date is None:
                current = (current.replace(day=28) + timedelta(days=5)).replace(day=1)
                continue

            target_end = start_nav_date + timedelta(days=horizon_days)
            if target_end > end:
                break

            end_nav_date = nearest_date(target_end)
            if end_nav_date is None:
                current = (current.replace(day=28) + timedelta(days=5)).replace(day=1)
                continue

            actual_years = (end_nav_date - start_nav_date).days / 365.25
            if actual_years < horizon_years * 0.85:
                current = (current.replace(day=28) + timedelta(days=5)).replace(day=1)
                continue

            nav_s = nav_by_date[start_nav_date]
            nav_e = nav_by_date[end_nav_date]
            if nav_s > 0:
                cagr = ((nav_e / nav_s) ** (1 / actual_years) - 1) * 100
                all_cagrs.append(cagr)

            current = (current.replace(day=28) + timedelta(days=5)).replace(day=1)

    cur.close()
    conn.close()

    if not all_cagrs:
        return {}

    total = len(all_cagrs)
    return {
        t: round(sum(1 for c in all_cagrs if c >= t) / total * 100)
        for t in CAGR_THRESHOLDS
    }, total


def _safe_compute(horizon_years):
    """Wraps compute_rolling_achievement, returns ({probs}, count) or ({}, 0)."""
    try:
        result = compute_rolling_achievement(horizon_years)
        if isinstance(result, tuple):
            return result
        return result, 0
    except Exception as e:
        print(f"[CALIBRATION] Error computing {horizon_years}yr: {e}")
        return {}, 0


# ── Module-level cache ────────────────────────────────────────────────────────

_cache = {}          # {horizon: {"probs": {...}, "period_count": int}}
_cache_date = None
_cache_lock = threading.Lock()


def _build_cache():
    global _cache, _cache_date
    from engine.cagr_advisor import ACHIEVEMENT_PROB  # noqa: PLC0415
    result = {}
    for h in CALIBRATION_HORIZONS:
        probs, count = _safe_compute(h)
        if probs:
            expected = ACHIEVEMENT_PROB.get(h, {})
            cal_factors = {}
            for t in CAGR_THRESHOLDS:
                if t in expected and expected[t] > 0 and t in probs:
                    cal_factors[t] = round(probs[t] / expected[t], 2)
            result[h] = {
                "horizon_years": h,
                "actual_probs": probs,
                "expected_probs": {t: expected.get(t) for t in CAGR_THRESHOLDS},
                "calibration_factors": cal_factors,
                "period_count": count,
                "fund_count": len(CALIBRATION_FUNDS),
            }
    with _cache_lock:
        _cache = result
        _cache_date = date.today()
    print(f"[CALIBRATION] Cache built for horizons: {list(result.keys())}")


def get_calibration_summary(force_refresh=False) -> dict:
    """Return cached calibration data, building cache if needed."""
    global _cache, _cache_date
    with _cache_lock:
        stale = _cache_date is None or _cache_date < date.today()
    if force_refresh or stale or not _cache:
        _build_cache()
    with _cache_lock:
        return dict(_cache)


def get_horizon_probs(horizon_years: int, force_refresh=False) -> dict:
    """Return calibrated probs for a specific horizon (nearest available)."""
    summary = get_calibration_summary(force_refresh=force_refresh)
    if not summary:
        return {}
    available = sorted(summary.keys())
    nearest = min(available, key=lambda h: abs(h - horizon_years))
    return summary.get(nearest, {})
