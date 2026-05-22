"""
Priority 16 tests — CAS PDF parser + portfolio import endpoint + gap analysis.
Run: pytest tests/test_priority16.py -v
"""
import pytest
import asyncio
import sys
sys.path.insert(0, "/home/hpbikram6086/fundguldasta")

from engine.cas_parser import (
    _parse_text_cams,
    _parse_text_kfintech,
    _parse_text_generic,
    _detect_format,
    _match_and_dedupe,
    match_fund_name,
    parse_cas_text,
)
from api.main import analyse_portfolio, PortfolioRequest, PortfolioFund


def run(coro):
    return asyncio.run(coro)


# ── Shared test fixtures ──────────────────────────────────────────────────────

FUND_LIST = [
    ("122639", "Parag Parikh Flexi Cap Fund - Direct Plan - Growth"),
    ("118989", "HDFC Mid-Cap Opportunities Fund - Direct Plan - Growth"),
    ("118825", "Mirae Asset Large Cap Fund - Direct Plan - Growth"),
    ("119071", "DSP Midcap Fund - Direct Plan - Growth"),
    ("118778", "Nippon India Small Cap Fund - Direct Plan - Growth"),
    ("120505", "Axis Midcap Fund - Direct Plan - Growth"),
    ("120152", "Kotak Large Cap Fund - Direct Plan - Growth"),
]

CAMS_TEXT = """Computer Age Management Services
CONSOLIDATED ACCOUNT STATEMENT
Period: 01-Apr-2024 to 31-Mar-2025

Parag Parikh Flexi Cap Fund - Direct Plan - Growth
Folio No: 12345678/01
Opening Balance: 200.000 Units
Closing Balance : 220.000 Units  NAV : 65.44  Value : 14396.80

HDFC Mid-Cap Opportunities Fund - Direct Plan - Growth
Folio No: 87654321/02
Opening Balance: 100.000 Units
Closing Balance : 150.234 Units  NAV : 48.92  Value : 7349.44
"""

KFINTECH_TEXT = """KFin Technologies Limited
CONSOLIDATED ACCOUNT STATEMENT

Mirae Asset Large Cap Fund - Direct Plan - Growth
Folio No: 20012345
Closing Balance : 345.678 Units
Market Value as on 31-Mar-2025 : 18923.45
NAV as on 31-Mar-2025 : 54.745

DSP Midcap Fund - Direct Plan - Growth
Folio No: 30098765
Closing Balance : 200.000 Units
NAV as on 31-Mar-2025 : 110.50
Market Value as on 31-Mar-2025 : 22100.00
"""


# ── Format detection ──────────────────────────────────────────────────────────

class TestFormatDetection:

    def test_cams_detected(self):
        assert _detect_format(CAMS_TEXT) == "cams"

    def test_kfintech_detected(self):
        assert _detect_format(KFINTECH_TEXT) == "kfintech"

    def test_unknown_returns_unknown(self):
        assert _detect_format("Some random PDF text with no identifiers.") == "unknown"

    def test_cams_case_insensitive(self):
        assert _detect_format("COMPUTER AGE MANAGEMENT SERVICES\nCONSOLIDATED") == "cams"


# ── CAMS text parser ──────────────────────────────────────────────────────────

class TestCamsParser:

    def test_parse_two_funds(self):
        result = _parse_text_cams(CAMS_TEXT)
        assert len(result) == 2

    def test_cams_fund_names_extracted(self):
        result = _parse_text_cams(CAMS_TEXT)
        names = [h["fund_name_raw"] for h in result]
        assert any("Parag Parikh" in n for n in names)
        assert any("HDFC Mid-Cap" in n for n in names)

    def test_cams_units_correct(self):
        result = _parse_text_cams(CAMS_TEXT)
        pp = next(h for h in result if "Parag" in h["fund_name_raw"])
        assert abs(pp["units"] - 220.0) < 0.01

    def test_cams_nav_correct(self):
        result = _parse_text_cams(CAMS_TEXT)
        pp = next(h for h in result if "Parag" in h["fund_name_raw"])
        assert abs(pp["nav"] - 65.44) < 0.01

    def test_cams_value_correct(self):
        result = _parse_text_cams(CAMS_TEXT)
        pp = next(h for h in result if "Parag" in h["fund_name_raw"])
        assert abs(pp["value"] - 14396.80) < 0.01

    def test_empty_text_returns_empty(self):
        result = _parse_text_cams("")
        assert result == []

    def test_no_closing_balance_returns_empty(self):
        text = "Parag Parikh Flexi Cap Fund - Direct Plan - Growth\nSome random lines\nNo balance data"
        result = _parse_text_cams(text)
        assert result == []


# ── KFintech text parser ──────────────────────────────────────────────────────

class TestKFintechParser:

    def test_parse_two_funds(self):
        result = _parse_text_kfintech(KFINTECH_TEXT)
        assert len(result) == 2

    def test_kfintech_fund_names_extracted(self):
        result = _parse_text_kfintech(KFINTECH_TEXT)
        names = [h["fund_name_raw"] for h in result]
        assert any("Mirae Asset" in n for n in names)
        assert any("DSP Midcap" in n for n in names)

    def test_kfintech_nav_not_date(self):
        """Nav should not be a date fragment like 31."""
        result = _parse_text_kfintech(KFINTECH_TEXT)
        for h in result:
            assert h["nav"] > 10, f"NAV={h['nav']} looks like a date fragment"

    def test_kfintech_value_correct(self):
        result = _parse_text_kfintech(KFINTECH_TEXT)
        mirae = next(h for h in result if "Mirae" in h["fund_name_raw"])
        assert abs(mirae["value"] - 18923.45) < 0.01

    def test_kfintech_units_correct(self):
        result = _parse_text_kfintech(KFINTECH_TEXT)
        dsp = next(h for h in result if "DSP" in h["fund_name_raw"])
        assert abs(dsp["units"] - 200.0) < 0.01


# ── Fuzzy matching ────────────────────────────────────────────────────────────

class TestFuzzyMatching:

    def test_exact_match_high_confidence(self):
        sc, name, conf = match_fund_name(
            "Parag Parikh Flexi Cap Fund Direct Plan Growth", FUND_LIST
        )
        assert sc == "122639"
        assert conf >= 85

    def test_partial_match_correct_fund(self):
        sc, name, conf = match_fund_name("HDFC Mid Cap Opportunities Direct Growth", FUND_LIST)
        assert sc == "118989"
        assert conf >= 70

    def test_dsp_short_name_matches(self):
        sc, name, conf = match_fund_name("DSP Midcap Fund Direct Growth", FUND_LIST)
        assert sc == "119071"
        assert conf >= 70

    def test_empty_fund_list_returns_none(self):
        sc, name, conf = match_fund_name("Any Fund Name", [])
        assert sc is None
        assert conf == 0

    def test_mirae_large_cap_matches(self):
        sc, name, conf = match_fund_name("Mirae Asset Large Cap Fund Direct Growth", FUND_LIST)
        assert sc == "118825"


# ── parse_cas_text (integration) ─────────────────────────────────────────────

class TestParseCasText:

    def test_cams_returns_correct_count(self):
        result = parse_cas_text(CAMS_TEXT, fund_list=FUND_LIST)
        assert result["fund_count"] == 2

    def test_format_identified(self):
        result = parse_cas_text(CAMS_TEXT, fund_list=FUND_LIST)
        assert result["format"] == "cams"

    def test_total_value_correct(self):
        result = parse_cas_text(CAMS_TEXT, fund_list=FUND_LIST)
        assert abs(result["total_value"] - (14396.80 + 7349.44)) < 0.01

    def test_allocation_pct_sums_100(self):
        result = parse_cas_text(CAMS_TEXT, fund_list=FUND_LIST)
        total_alloc = sum(h["allocation_pct"] for h in result["holdings"])
        assert abs(total_alloc - 100.0) < 0.5

    def test_scheme_codes_assigned(self):
        result = parse_cas_text(CAMS_TEXT, fund_list=FUND_LIST)
        matched = [h for h in result["holdings"] if h["scheme_code"] is not None]
        assert len(matched) == 2

    def test_duplicate_folio_merged(self):
        """Same fund appearing twice (two folios) should be merged into one."""
        doubled_text = CAMS_TEXT + """
Parag Parikh Flexi Cap Fund - Direct Plan - Growth
Folio No: 11111111/99
Opening Balance: 50.000 Units
Closing Balance : 50.000 Units  NAV : 65.44  Value : 3272.00
"""
        result = parse_cas_text(doubled_text, fund_list=FUND_LIST)
        pp_holdings = [h for h in result["holdings"] if h["scheme_code"] == "122639"]
        assert len(pp_holdings) == 1
        assert pp_holdings[0]["units"] > 220.0  # merged

    def test_kfintech_text_parsed(self):
        result = parse_cas_text(KFINTECH_TEXT, fund_list=FUND_LIST)
        assert result["fund_count"] == 2
        assert result["format"] == "kfintech"

    def test_empty_text_has_errors(self):
        result = parse_cas_text("", fund_list=FUND_LIST)
        assert len(result["parse_errors"]) > 0
        assert result["fund_count"] == 0


# ── Portfolio analyse gap analysis ───────────────────────────────────────────

class TestGapAnalysis:

    def _do_analyse(self, funds, horizon=7):
        req = PortfolioRequest(
            funds=[PortfolioFund(scheme_code=f["sc"], allocation_pct=f["alloc"]) for f in funds],
            horizon_years=horizon,
        )
        return analyse_portfolio(req)

    def test_gap_analysis_present_in_response(self):
        result = self._do_analyse([
            {"sc": 118825, "alloc": 50},
            {"sc": 122639, "alloc": 50},
        ])
        assert "gap_analysis" in result

    def test_gap_analysis_has_archetype_id(self):
        result = self._do_analyse([
            {"sc": 118825, "alloc": 50},
            {"sc": 122639, "alloc": 50},
        ])
        if result["gap_analysis"]:
            assert "archetype_id" in result["gap_analysis"]

    def test_gap_analysis_has_missing_and_extra(self):
        result = self._do_analyse([
            {"sc": 118825, "alloc": 50},
            {"sc": 122639, "alloc": 50},
        ])
        if result["gap_analysis"]:
            assert "missing_funds" in result["gap_analysis"]
            assert "extra_funds" in result["gap_analysis"]

    def test_gap_analysis_missing_funds_are_dicts(self):
        result = self._do_analyse([
            {"sc": 118825, "alloc": 50},
            {"sc": 122639, "alloc": 50},
        ])
        if result["gap_analysis"] and result["gap_analysis"]["missing_funds"]:
            mf = result["gap_analysis"]["missing_funds"][0]
            assert "scheme_code" in mf
            assert "scheme_name" in mf

    def test_overlap_pct_between_0_and_100(self):
        result = self._do_analyse([
            {"sc": 118825, "alloc": 50},
            {"sc": 122639, "alloc": 50},
        ])
        if result["gap_analysis"]:
            assert 0 <= result["gap_analysis"]["overlap_pct"] <= 100

    def test_fund_details_returned(self):
        result = self._do_analyse([
            {"sc": 118825, "alloc": 100},
        ])
        assert "fund_details" in result
        assert len(result["fund_details"]) == 1
