"""
Tests for manager stability scoring.
Core invariant: lead manager (earliest appointment) is always used.
No fund in our verified universe should return the 40/41 sentinel.
"""
import sys, os
sys.path.insert(0, '/home/hpbikram6086/fundguldasta')

import pytest
from engine.fund_scorer import score_manager_stability
from tests.conftest import VERIFIED_CODES, HIGH_MANAGER_TENURE, MANAGER_SENTINEL, MANAGER_SENTINEL_ALT


def test_no_sentinel_scores_in_verified_universe():
    """No verified fund should return the 40/41 default sentinel."""
    for code in VERIFIED_CODES:
        score, detail = score_manager_stability(code)
        assert score not in (MANAGER_SENTINEL, MANAGER_SENTINEL_ALT), (
            f"Fund {code} returned sentinel score {score} — manager data "
            f"not loaded or ORDER BY bug re-introduced. Detail: {detail}"
        )


def test_no_pending_enrichment_in_verified_universe():
    """No verified fund should have 'Pending SID enrichment' as manager name."""
    for code in VERIFIED_CODES:
        score, detail = score_manager_stability(code)
        note = detail.get("note", "")
        assert "Pending" not in note, (
            f"Fund {code} still has pending manager data: {note}"
        )


def test_lead_manager_is_earliest_appointed():
    """
    For multi-manager funds, the returned manager must be the earliest appointed
    (i.e. ORDER BY appointment_date ASC is working correctly).
    """
    import psycopg2, os
    from dotenv import load_dotenv
    from datetime import datetime

    load_dotenv(os.path.expanduser("~/fundguldasta/config/.env"))
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "fundguldasta_dev"),
        user=os.getenv("DB_USER", "fundguldasta_user"),
    )
    cur = conn.cursor()

    multi_manager_funds = []
    for code in VERIFIED_CODES:
        cur.execute(
            "SELECT COUNT(*) FROM fund_managers WHERE scheme_code=%s AND is_current=TRUE",
            (code,)
        )
        if cur.fetchone()[0] > 1:
            multi_manager_funds.append(code)

    for code in multi_manager_funds:
        # What the scorer returns
        score, detail = score_manager_stability(code)
        returned_name = detail.get("manager_name")

        # What the earliest-appointed manager actually is
        cur.execute(
            """SELECT manager_name FROM fund_managers
               WHERE scheme_code=%s AND is_current=TRUE
               ORDER BY appointment_date ASC LIMIT 1""",
            (code,)
        )
        expected_name = cur.fetchone()[0]

        assert returned_name == expected_name, (
            f"Fund {code}: scorer returned '{returned_name}' but lead manager "
            f"(earliest appointment) is '{expected_name}'. ORDER BY bug may have "
            f"re-appeared."
        )

    cur.close()
    conn.close()


def test_parag_parikh_scores_on_rajeev_thakkar():
    """
    Parag Parikh (122639) has Rajeev Thakkar since 2009 (~16yr tenure).
    Score must reflect this — expected 95+.
    """
    score, detail = score_manager_stability("122639")
    assert detail.get("manager_name") == "Rajeev Thakkar", (
        f"Parag Parikh manager should be Rajeev Thakkar, got: {detail.get('manager_name')}"
    )
    assert score >= 95, (
        f"Rajeev Thakkar (16yr tenure, 28yr exp) should score >=95, got {score}"
    )


def test_known_high_tenure_funds_score_above_80():
    """Funds with lead managers appointed before 2017 must score > 80."""
    for code, (name, appt_year) in HIGH_MANAGER_TENURE.items():
        if appt_year < 2017:
            score, detail = score_manager_stability(code)
            assert score > 80, (
                f"Fund {code} ({name}, since {appt_year}) should score >80, "
                f"got {score}. detail={detail}"
            )


def test_all_scores_in_valid_range():
    """All manager stability scores must be in [0, 100]."""
    for code in VERIFIED_CODES:
        score, _ = score_manager_stability(code)
        assert 0 <= score <= 100, f"Fund {code} score {score} out of [0,100]"
