"""
Tests for the 6-dimension fund scoring engine.
Validates composite scores, dimension ranges, and known-fund invariants.
"""
import sys
sys.path.insert(0, '/home/hpbikram6086/fundguldasta')

import pytest
from engine.fund_scorer import compute_composite_score
from tests.conftest import VERIFIED_CODES, MANAGER_SENTINEL, MANAGER_SENTINEL_ALT

HORIZON = 7
TARGET = 16


@pytest.fixture(scope="module")
def all_scores():
    """Compute scores for all verified funds once per test session."""
    results = {}
    for code in VERIFIED_CODES:
        import psycopg2, os
        from dotenv import load_dotenv
        load_dotenv(os.path.expanduser("~/fundguldasta/config/.env"))
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            dbname=os.getenv("DB_NAME", "fundguldasta_dev"),
            user=os.getenv("DB_USER", "fundguldasta_user"),
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT sebi_category FROM fund_metadata WHERE scheme_code=%s", (code,)
        )
        row = cur.fetchone()
        conn.close()
        category = row[0] if row else "Unknown"
        results[code] = compute_composite_score(code, HORIZON, TARGET, category)
    return results


def test_composite_score_structure(all_scores):
    """Result must contain required keys."""
    required = {"scheme_code", "composite_score", "dimension_scores", "details", "weights"}
    for code, result in all_scores.items():
        assert required.issubset(result.keys()), (
            f"Fund {code} result missing keys: {required - result.keys()}"
        )


def test_all_composite_scores_in_range(all_scores):
    """All composite scores must be in [0, 100]."""
    for code, result in all_scores.items():
        s = result["composite_score"]
        assert 0 <= s <= 100, f"Fund {code} composite score {s} out of range"


def test_all_dimension_scores_in_range(all_scores):
    """Every individual dimension score must be in [0, 100]."""
    dims = ["return_consistency", "risk_adjusted", "downside_behaviour",
            "manager_stability", "portfolio_quality", "forward_context"]
    for code, result in all_scores.items():
        for dim in dims:
            s = result["dimension_scores"].get(dim)
            assert s is not None, f"Fund {code} missing dimension {dim}"
            assert 0 <= s <= 100, f"Fund {code} dim={dim} score {s} out of range"


def test_no_manager_sentinel_in_dimension_scores(all_scores):
    """
    manager_stability dimension must never be the 40/41 sentinel.
    If it is, the DB query is broken or data is missing.
    """
    for code, result in all_scores.items():
        ms = result["dimension_scores"].get("manager_stability")
        assert ms not in (MANAGER_SENTINEL, MANAGER_SENTINEL_ALT), (
            f"Fund {code} has sentinel manager_stability score {ms}. "
            f"Fix: check fund_managers table and ORDER BY appointment_date ASC."
        )


def test_weights_sum_to_100(all_scores):
    """Score weights must always sum to 100."""
    for code, result in all_scores.items():
        total = sum(result["weights"].values())
        assert total == 100, f"Fund {code} weights sum to {total}, not 100"


def test_high_quality_funds_score_above_floor(all_scores):
    """
    Parag Parikh and HDFC Mid Cap are widely regarded as consistently high
    quality. Their composite scores should be above 55 at minimum.
    """
    floor = 55
    for code in ("122639", "118989"):
        score = all_scores[code]["composite_score"]
        assert score >= floor, (
            f"Fund {code} scored {score}, expected >= {floor}. "
            f"This fund is a known high-quality fund — a low score "
            f"indicates a data or logic regression."
        )
