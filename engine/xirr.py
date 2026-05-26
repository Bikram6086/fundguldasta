"""
XIRR computation using Newton-Raphson method.

compute_xirr(cash_flows) -> annualized return as a decimal (e.g. 0.154 = 15.4%)

cash_flows: list of (date, amount) tuples
  - Investments (outflows) are NEGATIVE amounts
  - Redemptions and current value (inflows) are POSITIVE amounts

Indian MF Tax helpers:
  compute_tax_summary(lots, current_date) -> LTCG/STCG breakdown
  Equity funds: >1 year = LTCG (12.5% above ₹1.25L exemption, grandfathered pre-Feb-2018 at cost)
  Debt funds post-2023: always taxed as income (slab rate)
"""
from datetime import date, datetime
from typing import Optional


def compute_xirr(cash_flows: list, guess: float = 0.1, tol: float = 1e-6, max_iter: int = 200) -> Optional[float]:
    """
    Compute XIRR from a list of (date, amount) tuples.
    Returns annualized rate as decimal, or None if no convergence.
    Amounts: negative = cash out (purchase), positive = cash in (redemption/current value).
    """
    if len(cash_flows) < 2:
        return None

    dates = [cf[0] if isinstance(cf[0], date) else cf[0].date() for cf in cash_flows]
    amounts = [float(cf[1]) for cf in cash_flows]
    base = dates[0]

    def _years(d):
        return (d - base).days / 365.25

    def _npv(rate):
        return sum(a / (1 + rate) ** _years(d) for d, a in zip(dates, amounts))

    def _dnpv(rate):
        return sum(-_years(d) * a / (1 + rate) ** (_years(d) + 1)
                   for d, a in zip(dates, amounts))

    rate = guess
    for _ in range(max_iter):
        npv = _npv(rate)
        d_npv = _dnpv(rate)
        if abs(d_npv) < 1e-12:
            break
        rate_new = rate - npv / d_npv
        if abs(rate_new - rate) < tol:
            return round(rate_new, 6)
        rate = rate_new
        if rate < -0.999:
            rate = -0.5

    # Try negative guess if positive guess failed
    if guess > 0:
        return compute_xirr(cash_flows, guess=-0.1, tol=tol, max_iter=max_iter)
    return None


def build_cash_flows(transactions: list, current_holdings: list, nav_lookup: dict) -> list:
    """
    Build cash flow list for XIRR from transactions + current holdings.

    transactions: list of dicts with keys: txn_date, amount, is_redemption
    current_holdings: list of dicts with keys: scheme_code, units
    nav_lookup: {scheme_code: current_nav}

    Returns list of (date, amount) for XIRR input.
    """
    flows = []

    for t in transactions:
        d = t.get("txn_date")
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()
        amt = float(t.get("amount") or 0)
        if amt == 0:
            continue
        if t.get("is_redemption"):
            flows.append((d, abs(amt)))  # inflow
        else:
            flows.append((d, -abs(amt)))  # outflow

    today = date.today()
    for h in current_holdings:
        sc = h.get("scheme_code")
        units = float(h.get("units") or 0)
        nav = nav_lookup.get(sc)
        if nav and units > 0:
            flows.append((today, units * float(nav)))

    flows.sort(key=lambda x: x[0])
    return flows


# ── Indian MF Tax ─────────────────────────────────────────────────────────────

LTCG_EXEMPTION = 125000  # ₹1.25 lakh per FY
LTCG_RATE = 0.125        # 12.5%
STCG_RATE = 0.20         # 20%
GRANDFATHERING_DATE = date(2018, 1, 31)


def compute_tax_summary(realized_gains: list, fund_type: str = "equity") -> dict:
    """
    Compute LTCG/STCG from realized gains list.

    realized_gains: list of dicts:
      { purchase_date, sell_date, purchase_nav, sell_nav, units, gain_amount }

    fund_type: 'equity' | 'debt' | 'hybrid_equity' | 'hybrid_debt'

    Returns:
      { ltcg_gross, stcg_gross, ltcg_exempt, ltcg_taxable, ltcg_tax, stcg_tax, total_tax }
    """
    is_equity = fund_type in ("equity", "hybrid_equity")

    ltcg_gross = 0.0
    stcg_gross = 0.0

    for g in realized_gains:
        p_date = g.get("purchase_date")
        s_date = g.get("sell_date")
        if isinstance(p_date, str):
            p_date = datetime.strptime(p_date, "%Y-%m-%d").date()
        if isinstance(s_date, str):
            s_date = datetime.strptime(s_date, "%Y-%m-%d").date()

        gain = float(g.get("gain_amount") or 0)
        holding_days = (s_date - p_date).days if p_date and s_date else 0

        if is_equity:
            if holding_days > 365:
                ltcg_gross += gain
            else:
                stcg_gross += gain
        else:
            # Post Apr 2023: debt funds taxed as income (STCG always)
            stcg_gross += gain

    ltcg_exempt = min(ltcg_gross, LTCG_EXEMPTION) if ltcg_gross > 0 else 0
    ltcg_taxable = max(0, ltcg_gross - ltcg_exempt)
    ltcg_tax = ltcg_taxable * LTCG_RATE
    stcg_tax = max(0, stcg_gross) * STCG_RATE

    return {
        "ltcg_gross": round(ltcg_gross, 2),
        "stcg_gross": round(stcg_gross, 2),
        "ltcg_exempt": round(ltcg_exempt, 2),
        "ltcg_taxable": round(ltcg_taxable, 2),
        "ltcg_tax": round(ltcg_tax, 2),
        "stcg_tax": round(stcg_tax, 2),
        "total_tax": round(ltcg_tax + stcg_tax, 2),
    }


def fifo_realized_gains(transactions: list) -> list:
    """
    Apply FIFO lot matching to a transaction list for one fund.
    transactions: sorted list of dicts with txn_date, units (positive=buy, negative=sell), nav
    Returns list of realized gain dicts.
    """
    lots = []  # [(purchase_date, nav, units_remaining)]
    realized = []

    for t in sorted(transactions, key=lambda x: x.get("txn_date") or ""):
        units = float(t.get("units") or 0)
        nav = float(t.get("nav") or 0)
        d = t.get("txn_date")
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()

        if units > 0:
            lots.append([d, nav, units])
        elif units < 0:
            sell_units = abs(units)
            sell_nav = nav
            while sell_units > 0 and lots:
                lot_date, lot_nav, lot_units = lots[0]
                consumed = min(sell_units, lot_units)
                gain = consumed * (sell_nav - lot_nav)
                realized.append({
                    "purchase_date": lot_date,
                    "sell_date": d,
                    "purchase_nav": lot_nav,
                    "sell_nav": sell_nav,
                    "units": consumed,
                    "gain_amount": gain,
                })
                lots[0][2] -= consumed
                sell_units -= consumed
                if lots[0][2] <= 0:
                    lots.pop(0)

    return realized
