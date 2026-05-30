"""
Compute tracking error, tracking difference, and historical returns
for curated index funds vs their benchmarks.
"""
import psycopg2
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config.db import get_db_config
from config.index_fund_config import INDEX_GROUPS

DB_CONFIG = get_db_config()


def _get_conn():
    return psycopg2.connect(**DB_CONFIG)


def _fetch_nav_series(scheme_codes: list[str], start_date: date) -> dict[str, pd.Series]:
    """Fetch NAV series for multiple funds in one query."""
    if not scheme_codes:
        return {}
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT scheme_code, nav_date, nav_value
        FROM nav_data
        WHERE scheme_code = ANY(%s) AND nav_date >= %s
        ORDER BY scheme_code, nav_date
    """, (scheme_codes, start_date))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    result: dict[str, pd.Series] = {}
    for code, nav_date, nav in rows:
        if code not in result:
            result[code] = {}
        result[code][nav_date] = float(nav)
    return {k: pd.Series(v) for k, v in result.items()}


def _fetch_benchmark_series(benchmark_code: str, start_date: date) -> pd.Series:
    """Fetch benchmark closing values as a dated Series."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT price_date, closing_value
        FROM benchmark_data
        WHERE index_code = %s AND price_date >= %s
        ORDER BY price_date
    """, (benchmark_code, start_date))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        return pd.Series(dtype=float)
    dates, vals = zip(*rows)
    return pd.Series([float(v) for v in vals], index=list(dates))


def _cagr(series: pd.Series, years: float) -> float | None:
    """Annualized return over given years from end of series."""
    if series.empty or years <= 0:
        return None
    end_date = series.index[-1]
    start_target = end_date - timedelta(days=int(years * 365.25))
    available = series.loc[series.index >= start_target]
    if len(available) < 20:
        return None
    v_end = float(available.iloc[-1])
    v_start = float(available.iloc[0])
    actual_years = (available.index[-1] - available.index[0]).days / 365.25
    if v_start <= 0 or actual_years < years * 0.8:
        return None
    return round(((v_end / v_start) ** (1 / actual_years) - 1) * 100, 2)


def _tracking_error(fund_series: pd.Series, bench_series: pd.Series, years: float) -> float | None:
    """Annualized std dev of daily excess returns over last N years."""
    if fund_series.empty or bench_series.empty:
        return None
    end_date = min(fund_series.index[-1], bench_series.index[-1])
    start_target = end_date - timedelta(days=int(years * 365.25))
    f = fund_series.loc[(fund_series.index >= start_target) & (fund_series.index <= end_date)]
    b = bench_series.loc[(bench_series.index >= start_target) & (bench_series.index <= end_date)]
    common = f.index.intersection(b.index)
    if len(common) < 50:
        return None
    f_ret = f[common].pct_change().dropna()
    b_ret = b[common].pct_change().dropna()
    excess = f_ret - b_ret
    if len(excess) < 50:
        return None
    return round(float(excess.std() * np.sqrt(252)) * 100, 2)


def _tracking_difference(fund_series: pd.Series, bench_series: pd.Series, years: float) -> float | None:
    """Fund CAGR minus benchmark CAGR over N years (negative = fund lagged)."""
    f_cagr = _cagr(fund_series, years)
    b_cagr = _cagr(bench_series, years)
    if f_cagr is None or b_cagr is None:
        return None
    return round(f_cagr - b_cagr, 2)


def compute_group_comparisons(group: dict) -> list[dict]:
    """Return comparison metrics for all funds in a group."""
    benchmark_code = group['benchmark_code']
    funds = group['funds']
    scheme_codes = [f['scheme_code'] for f in funds]

    start_date = date.today() - timedelta(days=int(5.5 * 365.25))
    nav_map = _fetch_nav_series(scheme_codes, start_date)
    bench = _fetch_benchmark_series(benchmark_code, start_date)

    results = []
    for fund in funds:
        code = fund['scheme_code']
        nav = nav_map.get(code, pd.Series(dtype=float))
        row = {
            'scheme_code':    code,
            'name':           fund['name'],
            'amc':            fund['amc'],
            'aum_cr':         fund['aum_cr'],
            'er':             fund['er'],
            'returns_1yr':    _cagr(nav, 1),
            'returns_3yr':    _cagr(nav, 3),
            'returns_5yr':    _cagr(nav, 5),
            'tracking_error_1yr': _tracking_error(nav, bench, 1),
            'tracking_error_3yr': _tracking_error(nav, bench, 3),
            'tracking_diff_1yr':  _tracking_difference(nav, bench, 1),
            'tracking_diff_3yr':  _tracking_difference(nav, bench, 3),
            'tracking_diff_5yr':  _tracking_difference(nav, bench, 5),
            'nav_from': str(nav.index[0]) if not nav.empty else None,
            'nav_to':   str(nav.index[-1]) if not nav.empty else None,
        }
        results.append(row)
    return results


def get_all_index_comparisons() -> list[dict]:
    """Return comparison data for all index groups."""
    output = []
    for group in INDEX_GROUPS:
        fund_rows = compute_group_comparisons(group)
        output.append({
            'group_id':       group['group_id'],
            'group_name':     group['group_name'],
            'benchmark_name': group['benchmark_name'],
            'funds':          fund_rows,
        })
    return output


def get_core_satellite_suggestion(core_index: str = 'nifty50',
                                   satellite_horizon: int = 7) -> dict:
    """
    Core: lowest tracking-error Nifty 50 fund at 55%.
    Satellite: top 3 mid/small cap funds from computed_metrics at 45%.
    """
    from engine.index_fund_metrics import get_all_index_comparisons
    comparisons = get_all_index_comparisons()

    core_group = next((g for g in comparisons if g['group_id'] == core_index), None)
    core_fund = None
    if core_group:
        valid = [f for f in core_group['funds'] if f.get('tracking_error_3yr') is not None]
        if valid:
            core_fund = min(valid, key=lambda f: f['tracking_error_3yr'])

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT cm.scheme_code, fm.scheme_name, fm.sebi_category,
               cm.fund_score, cm.cagr_pct, cm.sharpe_ratio
        FROM computed_metrics cm
        JOIN fund_metadata fm ON cm.scheme_code = fm.scheme_code
        WHERE cm.horizon_years = %s
        AND fm.sebi_category IN ('Mid Cap', 'Small Cap', 'Flexi Cap', 'Multi Cap')
        AND fm.plan_type = 'Direct'
        ORDER BY cm.fund_score DESC
        LIMIT 3
    """, (satellite_horizon,))
    satellite_rows = [
        {
            'scheme_code':     r[0],
            'name':            r[1],
            'category':        r[2],
            'fund_score': round(float(r[3]), 1) if r[3] else None,
            'cagr_pct':        round(float(r[4]), 2) if r[4] else None,
            'sharpe_ratio':    round(float(r[5]), 2) if r[5] else None,
            'weight_pct':      15,
        }
        for r in cur.fetchall()
    ]
    cur.close()
    conn.close()

    if satellite_rows:
        n = len(satellite_rows)
        each = round(45 / n)
        for i, s in enumerate(satellite_rows):
            s['weight_pct'] = each if i < n - 1 else 45 - each * (n - 1)

    return {
        'core': {
            **core_fund,
            'weight_pct': 55,
            'index':      core_index,
        } if core_fund else None,
        'satellite': satellite_rows,
        'satellite_horizon_years': satellite_horizon,
        'rationale': (
            'Core (55%): A low-cost index fund guarantees you capture market returns with '
            'minimal cost drag. Satellite (45%): Active funds in less-efficient mid/small '
            'cap segments where skilled managers have historically generated alpha over index.'
        ),
    }
