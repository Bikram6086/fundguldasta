"""
Priority 14 integrity tests — Risk Profiler logic, Fund Eligibility endpoint.
Run: pytest tests/test_priority14.py -v
"""
import pytest
import asyncio
import sys
sys.path.insert(0, "/home/hpbikram6086/fundguldasta")

from api.main import fund_eligibility


def run(coro):
    return asyncio.run(coro)


# ── 14c: Fund Eligibility Endpoint ────────────────────────────────────────────

class TestFundEligibility:

    def test_bouquet_fund_detected(self):
        """Mirae Large Cap (118825) is in the steady and balanced bouquets."""
        data = run(fund_eligibility("118825"))
        assert len(data["in_bouquets"]) > 0, "118825 should be in at least one bouquet"
        arch_ids = [b["archetype_id"] for b in data["in_bouquets"]]
        assert any(a in arch_ids for a in ["steady", "balanced"]), f"Expected steady/balanced, got {arch_ids}"

    def test_bouquet_fund_no_exclusion_reasons(self):
        """If a fund is in a bouquet, reasons_not_included should be empty."""
        data = run(fund_eligibility("118825"))
        assert data["reasons_not_included"] == [], \
            f"Bouquet fund should have no exclusion reasons, got: {data['reasons_not_included']}"

    def test_required_fields_present(self):
        data = run(fund_eligibility("118825"))
        for field in ["scheme_code", "name", "category", "in_bouquets", "eligibility", "reasons_not_included"]:
            assert field in data, f"Missing field: {field}"

    def test_eligibility_sub_fields(self):
        data = run(fund_eligibility("118825"))
        elig = data["eligibility"]
        for field in ["is_direct_plan", "passes_direct", "aum_crores", "passes_aum",
                      "expense_ratio", "passes_expense", "nav_years", "tier", "passes_tier", "overall_eligible"]:
            assert field in elig, f"Missing eligibility field: {field}"

    def test_mirae_passes_all_criteria(self):
        """Mirae Large Cap Direct should pass all eligibility criteria."""
        data = run(fund_eligibility("118825"))
        elig = data["eligibility"]
        assert elig["passes_direct"], "Should be a direct plan"
        assert elig["passes_aum"], f"AUM {elig['aum_crores']} should be ≥ 500Cr"
        assert elig["passes_expense"], f"TER {elig['expense_ratio']} should be ≤ 1.5%"
        assert elig["passes_tier"], f"Tier {elig['tier']} should be ≤ 2"
        assert elig["overall_eligible"], "Should be overall eligible"

    def test_nav_years_positive(self):
        data = run(fund_eligibility("118825"))
        assert data["eligibility"]["nav_years"] > 0

    def test_tier_valid_range(self):
        data = run(fund_eligibility("118825"))
        assert data["eligibility"]["tier"] in [1, 2, 3]

    def test_all_bouquet_funds_eligible(self):
        """All 13 bouquet funds should pass all eligibility checks."""
        codes = ['118825', '120152', '118834', '122639', '118955',
                 '120505', '119071', '118989', '118778', '120828',
                 '149134', '145552', '135800']
        for code in codes:
            data = run(fund_eligibility(code))
            elig = data["eligibility"]
            assert elig["overall_eligible"], \
                f"Fund {code} ({data['name']}) should be eligible but failed: " \
                f"direct={elig['passes_direct']}, aum={elig['passes_aum']}, " \
                f"expense={elig['passes_expense']}, tier={elig['passes_tier']}"

    def test_all_bouquet_funds_in_bouquet(self):
        """All bouquet funds should show up as being in at least one bouquet."""
        codes = ['118825', '120152', '118834', '122639', '118955',
                 '120505', '119071', '118989', '118778', '120828',
                 '149134', '145552', '135800']
        for code in codes:
            data = run(fund_eligibility(code))
            assert len(data["in_bouquets"]) > 0, \
                f"Fund {code} ({data['name']}) should be in a bouquet"

    def test_parag_parikh_in_bouquet(self):
        data = run(fund_eligibility("122639"))
        assert len(data["in_bouquets"]) > 0
        assert "Parag Parikh" in data["name"]

    def test_conviction_funds_in_bouquet(self):
        """Nippon Small Cap (118778) and Quant Small Cap (120828) should be in conviction."""
        for code in ["118778", "120828"]:
            data = run(fund_eligibility(code))
            arch_ids = [b["archetype_id"] for b in data["in_bouquets"]]
            assert "conviction" in arch_ids or "aggressive" in arch_ids, \
                f"{code} not found in conviction or aggressive: {arch_ids}"

    def test_not_found_raises_404(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            run(fund_eligibility("999999"))
        assert exc_info.value.status_code == 404

    def test_lowest_bouquet_score_present(self):
        data = run(fund_eligibility("118825"))
        assert data["lowest_bouquet_score"] is not None
        assert 0 < data["lowest_bouquet_score"] <= 100


# ── 14a: Risk Profiler scoring logic (pure Python replication) ────────────────

class TestRiskProfilerLogic:
    """Test the quiz scoring logic matches what the frontend implements."""

    SCORES = [
        [1, 2, 3, 4],  # Q1 horizon
        [1, 2, 3, 4],  # Q2 crash reaction
        [1, 2, 3, 4],  # Q3 income stability
        [1, 2, 3, 4],  # Q4 savings portion
        [1, 2, 3, 4],  # Q5 goal
    ]

    def quiz_score(self, answers):
        return sum(self.SCORES[i][a] for i, a in enumerate(answers))

    def recommend(self, score):
        if score <= 9:   return "steady"
        if score <= 12:  return "balanced"
        if score <= 16:  return "aggressive"
        return "conviction"

    def test_min_score_is_steady(self):
        """All lowest options → steady."""
        answers = [0, 0, 0, 0, 0]  # all option A (score=1 each)
        assert self.quiz_score(answers) == 5
        assert self.recommend(5) == "steady"

    def test_max_score_is_conviction(self):
        """All highest options → conviction."""
        answers = [3, 3, 3, 3, 3]  # all option D (score=4 each)
        assert self.quiz_score(answers) == 20
        assert self.recommend(20) == "conviction"

    def test_score_9_is_steady(self):
        assert self.recommend(9) == "steady"

    def test_score_10_is_balanced(self):
        assert self.recommend(10) == "balanced"

    def test_score_12_is_balanced(self):
        assert self.recommend(12) == "balanced"

    def test_score_13_is_aggressive(self):
        assert self.recommend(13) == "aggressive"

    def test_score_16_is_aggressive(self):
        assert self.recommend(16) == "aggressive"

    def test_score_17_is_conviction(self):
        assert self.recommend(17) == "conviction"

    def test_all_boundaries_covered(self):
        """No score 5-20 should be unmapped."""
        for score in range(5, 21):
            result = self.recommend(score)
            assert result in ["steady", "balanced", "aggressive", "conviction"], \
                f"Score {score} returned unexpected: {result}"
