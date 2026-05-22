"""
Tests for bouquet cache integrity.
These tests query the live DB cache — they catch stale or corrupt cache entries
that would serve wrong data to real users.
"""
import sys
sys.path.insert(0, '/home/hpbikram6086/fundguldasta')

import pytest
import json
import psycopg2
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from tests.conftest import ARCHETYPES, MANAGER_SENTINEL, MANAGER_SENTINEL_ALT

load_dotenv(os.path.expanduser("~/fundguldasta/config/.env"))

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    dbname=os.getenv("DB_NAME", "fundguldasta_dev"),
    user=os.getenv("DB_USER", "fundguldasta_user"),
)


def fresh_conn():
    """Return a fresh autocommit connection — avoids cascade failures."""
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    return conn


@pytest.fixture(scope="module")
def latest_cache():
    """Fetch the most recent cache row for each archetype (horizon=7)."""
    conn = fresh_conn()
    cur = conn.cursor()
    results = {}
    for arch in ARCHETYPES:
        cur.execute("""
            SELECT confidence_json, computation_date
            FROM bouquet_cache
            WHERE archetype_id=%s AND horizon_years=7
            ORDER BY computation_date DESC LIMIT 1
        """, (arch,))
        row = cur.fetchone()
        assert row is not None, (
            f"No cache entry found for archetype='{arch}' horizon=7. "
            f"Run: python3 recompute_7yr.py"
        )
        conf = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        results[arch] = {"confidence": conf, "computed_at": row[1]}
    cur.close()
    conn.close()
    return results


def test_all_archetypes_present_in_cache(latest_cache):
    """All 4 archetypes must have a cache entry for horizon=7."""
    for arch in ARCHETYPES:
        assert arch in latest_cache, f"Archetype '{arch}' missing from cache"


def test_cache_is_not_stale(latest_cache):
    """Cache must have been computed within the last 35 days."""
    cutoff = date.today() - timedelta(days=35)
    for arch, data in latest_cache.items():
        computed = data["computed_at"]
        assert computed >= cutoff, (
            f"Archetype '{arch}' cache is stale: computed {computed}, "
            f"cutoff {cutoff}. Run recompute_7yr.py or check the daily cron."
        )


def test_cached_confidence_scores_above_60(latest_cache):
    """Cached confidence scores must be above 60 for all archetypes."""
    for arch, data in latest_cache.items():
        score = data["confidence"].get("score") or data["confidence"].get("overall_score")
        assert score is not None, f"Archetype '{arch}' cache has no confidence score"
        assert score >= 60, (
            f"Archetype '{arch}' cached confidence score {score} < 60. "
            f"Recompute after verifying manager data integrity."
        )


def test_no_sentinel_manager_score_in_cache(latest_cache):
    """
    manager_stability factor in cache must never be 40-45 sentinel.
    If it is, the cache was built with broken manager queries.
    """
    for arch, data in latest_cache.items():
        factors = data["confidence"].get("factors", {})
        ms = factors.get("manager_stability", {})
        ms_score = ms.get("score")
        if ms_score is not None:
            assert ms_score > 50, (
                f"Archetype '{arch}' has sentinel manager_stability score "
                f"{ms_score} in cache. Cache is stale from before the fix. "
                f"Run: python3 recompute_7yr.py"
            )


def test_nav_data_not_stale():
    """Latest NAV record must be within 10 calendar days."""
    conn = fresh_conn()
    cur = conn.cursor()
    cur.execute("SELECT MAX(nav_date) FROM nav_data")
    max_date = cur.fetchone()[0]
    cur.close()
    conn.close()
    assert max_date is not None, "nav_data table is empty"
    staleness = (date.today() - max_date).days
    assert staleness <= 10, (
        f"NAV data is {staleness} days stale (last: {max_date}). "
        f"Run: python3 data/nav_ingestion.py or check the daily cron."
    )


def test_all_13_verified_funds_have_nav_data():
    """Every verified fund must have at least 3 years of NAV records."""
    from tests.conftest import VERIFIED_CODES
    conn = fresh_conn()
    cur = conn.cursor()
    for code in VERIFIED_CODES:
        cur.execute(
            "SELECT COUNT(*), MIN(nav_date), MAX(nav_date) FROM nav_data WHERE scheme_code=%s",
            (code,)
        )
        count, min_d, max_d = cur.fetchone()
        assert count >= 750, (
            f"Fund {code} has only {count} NAV records (min {min_d} to {max_d}). "
            f"Expected 750+ (3 years of trading days)."
        )
    cur.close()
    conn.close()


def test_all_13_verified_funds_have_manager_data():
    """Every verified fund must have at least one non-sentinel manager record."""
    from tests.conftest import VERIFIED_CODES
    conn = fresh_conn()
    cur = conn.cursor()
    for code in VERIFIED_CODES:
        cur.execute(
            """SELECT manager_name FROM fund_managers
               WHERE scheme_code=%s AND is_current=TRUE
               AND manager_name != 'Pending SID enrichment'
               ORDER BY appointment_date ASC LIMIT 1""",
            (code,)
        )
        row = cur.fetchone()
        assert row is not None, (
            f"Fund {code} has no verified manager data in fund_managers table."
        )
    cur.close()
    conn.close()
