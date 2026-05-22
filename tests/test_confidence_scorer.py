"""
Tests for the bouquet-level confidence scoring engine.
Validates that all 4 archetypes produce reasonable confidence scores
and that the manager stability factor never shows sentinel values.
"""
import sys
sys.path.insert(0, '/home/hpbikram6086/fundguldasta')

import pytest
from engine.confidence_scorer import compute_bouquet_confidence
from config.scheme_codes import ARCHETYPE_FUNDS, VERIFIED_FUNDS
from tests.conftest import ARCHETYPES, MANAGER_SENTINEL, MANAGER_SENTINEL_ALT

HORIZON = 7
TARGET = 16


@pytest.fixture(scope="module")
def all_confidence():
    results = {}
    for arch_id in ARCHETYPES:
        fund_weights = ARCHETYPE_FUNDS[arch_id]
        fund_details = [
            {
                "scheme_code": code,
                "weight": weight,
                "name": VERIFIED_FUNDS.get(code, {}).get("name", ""),
                "category": VERIFIED_FUNDS.get(code, {}).get("category", "Unknown"),
                "tier": VERIFIED_FUNDS.get(code, {}).get("tier", 1),
                "amc": VERIFIED_FUNDS.get(code, {}).get("amc", ""),
            }
            for code, weight in fund_weights
        ]
        results[arch_id] = compute_bouquet_confidence(
            fund_weights, fund_details, HORIZON, TARGET
        )
    return results


def test_confidence_structure(all_confidence):
    """Result must have score, level, factors keys."""
    required = {"score", "level", "factors"}
    factor_keys = {
        "rolling_consistency", "downside_protection",
        "manager_stability", "category_tailwind", "cost_efficiency"
    }
    for arch, result in all_confidence.items():
        assert required.issubset(result.keys()), (
            f"{arch}: missing keys {required - result.keys()}"
        )
        assert factor_keys.issubset(result["factors"].keys()), (
            f"{arch}: missing factor keys"
        )


def test_all_archetypes_score_above_60(all_confidence):
    """
    All 4 archetypes use Tier 1/2 funds with real NAV data going back 7+ years.
    A score below 60 indicates a data regression, not legitimate low quality.
    """
    for arch, result in all_confidence.items():
        score = result["score"]
        assert score >= 60, (
            f"Archetype '{arch}' confidence score {score} is below 60. "
            f"This indicates a data regression — check NAV data freshness "
            f"and manager data integrity."
        )


def test_no_manager_sentinel_in_confidence(all_confidence):
    """
    manager_stability factor must never be sentinel 40-45.
    All 4 archetypes use funds with verified manager data.
    """
    for arch, result in all_confidence.items():
        ms_score = result["factors"]["manager_stability"]["score"]
        assert ms_score > 50, (
            f"Archetype '{arch}' manager_stability confidence factor = {ms_score}. "
            f"Expected >50 — all funds have verified SID data. "
            f"Check: confidence_scorer.py ORDER BY appointment_date ASC."
        )


def test_all_factor_scores_in_range(all_confidence):
    """Every factor score must be in [0, 100]."""
    for arch, result in all_confidence.items():
        for factor, data in result["factors"].items():
            s = data["score"]
            assert 0 <= s <= 100, (
                f"Archetype '{arch}' factor '{factor}' score {s} out of [0,100]"
            )


def test_confidence_levels_are_valid_strings(all_confidence):
    """Level must be one of the defined bands."""
    valid = {"High", "Medium-High", "Medium", "Low-Medium", "Low"}
    for arch, result in all_confidence.items():
        assert result["level"] in valid, (
            f"Archetype '{arch}' has invalid confidence level: {result['level']}"
        )
