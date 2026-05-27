"""
FUNDGULDASTA — REGULAR PLAN PROXY LOOKUP
=========================================
Direct plans launched January 2013. For 15/20/30yr horizon scoring,
we fall back to the regular plan equivalent, which shares the identical
portfolio, manager, and strategy — differing only by a higher expense ratio.
The direct plan would have performed marginally BETTER over the same period.

Usage:
    from engine.regular_plan_proxy import find_regular_plan
    proxy_code = find_regular_plan('118778')  # Nippon Small Cap Direct
    # Returns '113177' (Nippon Small Cap Regular - Growth)
"""

import re
import psycopg2
from config.db import get_db_config

DB_CONFIG = get_db_config()

_proxy_cache: dict = {}

_STRIP_PATTERNS = [
    r'\s*[-–]\s*direct\s+plan\s*[-–]?\s*',
    r'\s*[-–]\s*direct\s*[-–]?\s*',
    r'\bdirect\s+plan\b',
    r'\bdirect\b',
    r'\s*[-–]\s*regular\s+plan\s*[-–]?\s*',
    r'\s*[-–]\s*regular\s*[-–]?\s*',
    r'\bregular\s+plan\b',
    r'\bregular\b',
    r'\bgrowth\s+plan\b',
    r'\bgrowth\s+option\b',
    r'\bgrowth\b',
    r'\boption\b',
    r'\bplan\b',
]


def _core_name(name: str) -> str:
    """Strip plan-type and option tokens for name comparison."""
    n = name.lower()
    for pat in _STRIP_PATTERNS:
        n = re.sub(pat, ' ', n, flags=re.IGNORECASE)
    n = re.sub(r'[-–]+', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def find_regular_plan(direct_scheme_code: str) -> str | None:
    """
    Return the scheme_code of the regular plan counterpart of a direct plan,
    or None if no reliable match is found.

    Matching logic:
    1. Same AMC
    2. No 'direct' in scheme_name
    3. No 'idcw'/'dividend' (growth plan only, to avoid option mismatch)
    4. At least 1000 NAV rows (genuine history)
    5. Highest token-overlap with the core fund name
    6. Among tied scores, prefer the one with the earliest inception
    """
    if direct_scheme_code in _proxy_cache:
        return _proxy_cache[direct_scheme_code]

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        "SELECT scheme_name, amc_name FROM fund_metadata WHERE scheme_code = %s",
        (direct_scheme_code,)
    )
    row = cur.fetchone()
    if not row or 'direct' not in row[0].lower():
        cur.close(); conn.close()
        _proxy_cache[direct_scheme_code] = None
        return None

    direct_name, amc_name = row
    core = _core_name(direct_name)
    core_tokens = set(core.split())

    cur.execute("""
        SELECT fm.scheme_code, fm.scheme_name, MIN(nd.nav_date) AS inception
        FROM fund_metadata fm
        JOIN nav_data nd ON fm.scheme_code = nd.scheme_code
        WHERE fm.amc_name = %s
          AND fm.scheme_code != %s
          AND fm.scheme_name NOT ILIKE '%%direct%%'
          AND fm.scheme_name NOT ILIKE '%%idcw%%'
          AND fm.scheme_name NOT ILIKE '%%dividend%%'
          AND fm.scheme_name NOT ILIKE '%%payout%%'
        GROUP BY fm.scheme_code, fm.scheme_name
        HAVING COUNT(*) > 1000
        ORDER BY inception ASC
    """, (amc_name, direct_scheme_code))
    candidates = cur.fetchall()
    cur.close(); conn.close()

    best_code = None
    best_overlap = 0.0
    best_inception = None

    for code, name, inception in candidates:
        cand_tokens = set(_core_name(name).split())
        if not core_tokens or not cand_tokens:
            continue
        overlap = len(core_tokens & cand_tokens) / len(core_tokens | cand_tokens)
        if overlap > best_overlap or (overlap == best_overlap and best_inception and inception < best_inception):
            best_overlap = overlap
            best_code = code
            best_inception = inception

    result = best_code if best_overlap >= 0.55 else None
    _proxy_cache[direct_scheme_code] = result
    return result


def clear_cache():
    _proxy_cache.clear()
