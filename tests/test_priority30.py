"""
Priority 30 tests — Portfolio Intelligence: manual entry, benchmark, XIRR engine.
Run: pytest tests/test_priority30.py -v
"""
import sys
sys.path.insert(0, "/home/hpbikram6086/fundguldasta")

from datetime import date, timedelta
from engine.xirr import compute_xirr, build_cash_flows, fifo_realized_gains, compute_tax_summary


class TestXIRR:
    def test_basic_sip_xirr(self):
        today = date.today()
        cash_flows = [
            (today - timedelta(days=365 * 3), -100000),
            (today, 150000),
        ]
        xirr = compute_xirr(cash_flows)
        assert xirr is not None
        assert 0.12 < xirr < 0.18  # ~14.5% for 3yr 50% gain

    def test_flat_return_near_zero(self):
        today = date.today()
        cash_flows = [
            (today - timedelta(days=365), -100000),
            (today, 100000),
        ]
        xirr = compute_xirr(cash_flows)
        assert xirr is not None
        assert abs(xirr) < 0.02  # ~0% XIRR

    def test_negative_return(self):
        today = date.today()
        cash_flows = [
            (today - timedelta(days=365), -100000),
            (today, 80000),
        ]
        xirr = compute_xirr(cash_flows)
        assert xirr is not None
        assert xirr < 0

    def test_insufficient_flows_returns_none(self):
        today = date.today()
        assert compute_xirr([(today, -10000)]) is None
        assert compute_xirr([]) is None

    def test_build_cash_flows_outflows_negative(self):
        today = date.today()
        txns = [{"txn_date": today, "amount": 50000, "is_redemption": False, "scheme_code": "AAA"}]
        holdings = [{"scheme_code": "AAA", "units": 100}]
        nav_lookup = {"AAA": 600.0}
        flows = build_cash_flows(txns, holdings, nav_lookup)
        assert any(f[1] < 0 for f in flows)  # purchase = negative
        assert any(f[1] > 0 for f in flows)  # current value = positive

    def test_build_cash_flows_redemption_positive(self):
        today = date.today()
        txns = [{"txn_date": today - timedelta(days=30), "amount": 10000, "is_redemption": True, "scheme_code": "BBB"}]
        flows = build_cash_flows(txns, [], {})
        assert flows[0][1] > 0  # redemption = positive inflow


class TestFIFOTax:
    def test_ltcg_after_one_year(self):
        today = date.today()
        txns = [
            {"txn_date": today - timedelta(days=400), "units": 100, "nav": 100, "is_redemption": False},
            {"txn_date": today, "units": -100, "nav": 150, "is_redemption": True},
        ]
        realized = fifo_realized_gains(txns)
        assert len(realized) == 1
        assert realized[0]["gain_amount"] == pytest.approx(5000, rel=0.01)

    def test_stcg_under_one_year(self):
        today = date.today()
        txns = [
            {"txn_date": today - timedelta(days=200), "units": 100, "nav": 100, "is_redemption": False},
            {"txn_date": today, "units": -50, "nav": 130, "is_redemption": True},
        ]
        realized = fifo_realized_gains(txns)
        assert len(realized) == 1
        assert realized[0]["gain_amount"] == pytest.approx(1500, rel=0.01)

    def test_partial_redemption_fifo(self):
        today = date.today()
        txns = [
            {"txn_date": today - timedelta(days=500), "units": 100, "nav": 100, "is_redemption": False},
            {"txn_date": today - timedelta(days=100), "units": 100, "nav": 120, "is_redemption": False},
            {"txn_date": today, "units": -150, "nav": 150, "is_redemption": True},
        ]
        realized = fifo_realized_gains(txns)
        # First lot fully consumed (100 units), second lot partially (50 units)
        total_units = sum(r["units"] for r in realized)
        assert abs(total_units - 150) < 0.01

    def test_no_redemption_returns_empty(self):
        today = date.today()
        txns = [
            {"txn_date": today - timedelta(days=200), "units": 100, "nav": 100, "is_redemption": False},
        ]
        realized = fifo_realized_gains(txns)
        assert realized == []

    def test_tax_summary_equity_ltcg_exempt(self):
        today = date.today()
        gains = [{"purchase_date": today - timedelta(days=400), "sell_date": today,
                  "gain_amount": 100000, "units": 100}]
        tax = compute_tax_summary(gains, "equity")
        assert tax["ltcg_gross"] == pytest.approx(100000)
        assert tax["ltcg_exempt"] == pytest.approx(100000)  # under 1.25L
        assert tax["ltcg_tax"] == 0

    def test_tax_summary_equity_ltcg_taxable(self):
        today = date.today()
        gains = [{"purchase_date": today - timedelta(days=400), "sell_date": today,
                  "gain_amount": 200000, "units": 100}]
        tax = compute_tax_summary(gains, "equity")
        assert tax["ltcg_taxable"] == pytest.approx(75000)  # 200k - 125k
        assert tax["ltcg_tax"] == pytest.approx(9375)  # 75k * 12.5%

    def test_tax_summary_stcg_rate(self):
        today = date.today()
        gains = [{"purchase_date": today - timedelta(days=100), "sell_date": today,
                  "gain_amount": 50000, "units": 50}]
        tax = compute_tax_summary(gains, "equity")
        assert tax["stcg_gross"] == pytest.approx(50000)
        assert tax["stcg_tax"] == pytest.approx(10000)  # 50k * 20%

    def test_tax_summary_debt_all_stcg(self):
        today = date.today()
        gains = [{"purchase_date": today - timedelta(days=800), "sell_date": today,
                  "gain_amount": 30000, "units": 30}]
        tax = compute_tax_summary(gains, "debt")
        # Debt: even long-term is treated as STCG (post Apr 2023)
        assert tax["stcg_gross"] == pytest.approx(30000)
        assert tax["ltcg_gross"] == 0


import pytest
