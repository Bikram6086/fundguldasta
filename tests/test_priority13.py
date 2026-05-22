"""
Priority 13 integrity tests — Historical SIP Backtest, Probabilistic Simulation, Fund Detail.
Run: pytest tests/test_priority13.py -v
"""
import pytest
import asyncio
import sys
sys.path.insert(0, "/home/hpbikram6086/fundguldasta")

from api.main import bouquet_backtest, BacktestRequest, fund_detail


# ── helpers ───────────────────────────────────────────────────────────────────
def run(coro):
    return asyncio.run(coro)


# ── 13a+13b: Backtest + Simulation ────────────────────────────────────────────

class TestBacktest:

    def test_backtest_returns_series(self):
        r = run(bouquet_backtest("balanced", BacktestRequest(monthly_sip=10000, horizon_years=5, future_years=3)))
        assert "series" in r
        assert len(r["series"]) >= 12, "Need at least 12 months of data"

    def test_series_fields(self):
        r = run(bouquet_backtest("aggressive", BacktestRequest(monthly_sip=10000, horizon_years=5, future_years=3)))
        s = r["series"]
        assert len(s) > 0
        first = s[0]
        assert "m" in first, "month field"
        assert "b" in first, "bouquet value"
        assert "n" in first, "nifty value"
        assert "i" in first, "invested amount"

    def test_bouquet_outperforms_invested(self):
        """Bouquet final value must exceed invested amount (positive real return over 5yr)."""
        r = run(bouquet_backtest("balanced", BacktestRequest(monthly_sip=10000, horizon_years=5, future_years=3)))
        s = r["summary"]
        assert s["bouquet_final"] > s["total_invested"], \
            f"Bouquet {s['bouquet_final']} should exceed invested {s['total_invested']}"

    def test_invested_amount_correct(self):
        r = run(bouquet_backtest("conviction", BacktestRequest(monthly_sip=10000, horizon_years=5, future_years=3)))
        s = r["summary"]
        expected = s["months"] * 10000
        assert abs(s["total_invested"] - expected) <= 10000, \
            f"Invested {s['total_invested']} should ≈ months×sip = {expected}"

    def test_cagr_positive(self):
        r = run(bouquet_backtest("balanced", BacktestRequest(monthly_sip=10000, horizon_years=5, future_years=3)))
        assert r["summary"]["bouquet_cagr"] > 0, "Bouquet CAGR should be positive over 5 years"

    def test_future_bands_structure(self):
        r = run(bouquet_backtest("balanced", BacktestRequest(monthly_sip=10000, horizon_years=5, future_years=3)))
        bands = r["future"]
        assert len(bands) == 3, "Should have 3 future year bands"
        for b in bands:
            assert b["p10"] <= b["p25"] <= b["p50"] <= b["p75"] <= b["p90"], \
                f"Percentile order violated: {b}"
            assert b["p50"] > b["i"] * 0.5, "Median outcome should be above half the invested"

    def test_future_invested_grows(self):
        r = run(bouquet_backtest("balanced", BacktestRequest(monthly_sip=10000, horizon_years=5, future_years=3)))
        bands = r["future"]
        investeds = [b["i"] for b in bands]
        assert investeds == sorted(investeds), "Invested should increase year over year"

    def test_steady_capped_by_sbi_baf(self):
        """Steady Compounder includes SBI BAF (started Sep 2021) — actual history < 7yr."""
        r = run(bouquet_backtest("steady", BacktestRequest(monthly_sip=10000, horizon_years=7, future_years=3)))
        s = r["summary"]
        assert s["months"] < 84, \
            f"Steady should have < 84 months (limited by SBI BAF start date), got {s['months']}"

    def test_all_archetypes_work(self):
        for arch in ["steady", "balanced", "aggressive", "conviction"]:
            r = run(bouquet_backtest(arch, BacktestRequest(monthly_sip=10000, horizon_years=5, future_years=2)))
            assert r["summary"]["months"] > 0, f"{arch} returned 0 months"

    def test_sip_scaling(self):
        """Higher SIP should scale final value proportionally."""
        r1 = run(bouquet_backtest("balanced", BacktestRequest(monthly_sip=10000, horizon_years=5, future_years=2)))
        r2 = run(bouquet_backtest("balanced", BacktestRequest(monthly_sip=20000, horizon_years=5, future_years=2)))
        ratio = r2["summary"]["bouquet_final"] / r1["summary"]["bouquet_final"]
        assert 1.9 < ratio < 2.1, f"Doubling SIP should ~double corpus, got ratio {ratio:.3f}"


# ── 13c: Fund Detail ────────────────────────────────────────────────────────────

class TestFundDetail:

    def test_fund_exists(self):
        fd = run(fund_detail("118825"))
        assert fd["name"] is not None
        assert "Mirae" in fd["name"]

    def test_required_fields(self):
        fd = run(fund_detail("118825"))
        for field in ["scheme_code", "name", "category", "expense_ratio", "nav_series", "rolling_returns"]:
            assert field in fd, f"Missing field: {field}"

    def test_nav_series_populated(self):
        fd = run(fund_detail("118825"))
        assert len(fd["nav_series"]) >= 50, "Should have at least 50 monthly NAV points (5 years)"
        first = fd["nav_series"][0]
        assert "m" in first and "v" in first

    def test_rolling_returns_present(self):
        fd = run(fund_detail("118825"))
        rr = fd["rolling_returns"]
        assert "1yr" in rr and "3yr" in rr and "5yr" in rr

    def test_nifty_rolling_present(self):
        fd = run(fund_detail("118825"))
        nr = fd["nifty_rolling"]
        assert "1yr" in nr

    def test_expense_ratio_sane(self):
        fd = run(fund_detail("118825"))
        er = fd["expense_ratio"]
        assert er is not None
        assert 0.0 < er < 3.0, f"Expense ratio {er} out of sane range"

    def test_current_nav_positive(self):
        fd = run(fund_detail("118825"))
        assert fd["current_nav"] is not None
        assert fd["current_nav"] > 0

    def test_all_bouquet_funds_have_detail(self):
        """All 13 verified fund codes should have detail pages."""
        codes = ['118825','120152','118834','122639','118955',
                 '120505','119071','118989','118778','120828',
                 '149134','145552','135800']
        for code in codes:
            fd = run(fund_detail(code))
            assert fd["name"] is not None, f"No name for {code}"
            assert len(fd["nav_series"]) > 0, f"No NAV series for {code}"

    def test_parag_parikh_detail(self):
        fd = run(fund_detail("122639"))
        assert "Parag Parikh" in fd["name"]
        assert fd["category"] == "Flexi Cap"
