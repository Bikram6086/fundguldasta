"""
FUNDGULDASTA — ROLLING RETURN CALCULATOR
=========================================
The foundation of the entire computation engine.

What it does:
- Computes all possible rolling CAGR windows for a fund
- For a 7-year horizon: every possible 7-year period in history
- Returns mean, median, std deviation of all those periods
- Returns % of periods that beat a target CAGR
- Returns % of periods that beat the benchmark

Why rolling returns matter more than point-to-point:
A point-to-point return (Jan 2015 to Jan 2025) is ONE data point.
It is heavily influenced by start and end date luck.
Rolling returns across ALL possible periods give a statistically
meaningful picture of how consistently a fund delivers.

This is non-negotiable in a rigorous algorithm.
"""

import psycopg2
import numpy as np
import pandas as pd
import os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'fundguldasta_dev'),
    'user': os.getenv('DB_USER', 'fundguldasta_user'),
}

def get_nav_series(scheme_code):
    """
    Fetch complete NAV history for a fund.
    Returns a pandas Series with date index, sorted ascending.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nav_date, nav_value
        FROM nav_data
        WHERE scheme_code = %s
        ORDER BY nav_date ASC
    """, (scheme_code,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return None

    dates = [row[0] for row in rows]
    values = [float(row[1]) for row in rows]
    series = pd.Series(values, index=pd.DatetimeIndex(dates))
    return series

def get_benchmark_series(index_code):
    """
    Fetch complete benchmark history.
    Returns a pandas Series with date index, sorted ascending.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT price_date, closing_value
        FROM benchmark_data
        WHERE index_code = %s
        ORDER BY price_date ASC
    """, (index_code,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return None

    dates = [row[0] for row in rows]
    values = [float(row[1]) for row in rows]
    series = pd.Series(values, index=pd.DatetimeIndex(dates))
    return series

def compute_cagr(start_value, end_value, years):
    """
    Compute CAGR between two NAV values over a given period.
    Returns CAGR as a percentage (e.g. 15.4 means 15.4%).
    """
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return None
    try:
        cagr = (pow(end_value / start_value, 1.0 / years) - 1) * 100
        return round(cagr, 4)
    except Exception:
        return None

def compute_rolling_returns(scheme_code, horizon_years, benchmark_code='NIFTY500'):
    """
    Core function. Computes all rolling CAGR windows for a fund.

    For a 7-year horizon:
    - Takes every possible start date in the NAV history
    - Finds the NAV exactly 7 years later
    - Computes CAGR for that 7-year window
    - Repeats for all possible start dates
    - Returns statistics across all windows

    Parameters:
        scheme_code:    AMFI scheme code
        horizon_years:  Investment horizon in years (3, 5, 7, 10, 15)
        benchmark_code: Benchmark index for comparison

    Returns dict with all rolling return statistics.
    """
    nav_series = get_nav_series(scheme_code)
    if nav_series is None or len(nav_series) < horizon_years * 200:
        return None

    benchmark_series = get_benchmark_series(benchmark_code)

    horizon_days = int(horizon_years * 365.25)
    tolerance_days = 45  # Allow +/- 45 days to find matching NAV date

    rolling_cagrs = []
    benchmark_cagrs = []

    dates = nav_series.index

    for i, start_date in enumerate(dates):
        target_date = start_date + pd.Timedelta(days=horizon_days)

        # Find closest NAV date to target
        future_dates = dates[dates >= target_date - pd.Timedelta(days=tolerance_days)]
        future_dates = future_dates[future_dates <= target_date + pd.Timedelta(days=tolerance_days)]

        if len(future_dates) == 0:
            continue

        end_date = future_dates[0]
        actual_years = (end_date - start_date).days / 365.25

        if actual_years < horizon_years * 0.9:
            continue

        start_nav = nav_series[start_date]
        end_nav = nav_series[end_date]

        cagr = compute_cagr(start_nav, end_nav, actual_years)
        if cagr is None:
            continue

        rolling_cagrs.append(cagr)

        # Compute benchmark CAGR for same period
        if benchmark_series is not None:
            bench_start_dates = benchmark_series.index[
                (benchmark_series.index >= start_date - pd.Timedelta(days=5)) &
                (benchmark_series.index <= start_date + pd.Timedelta(days=5))
            ]
            bench_end_dates = benchmark_series.index[
                (benchmark_series.index >= end_date - pd.Timedelta(days=5)) &
                (benchmark_series.index <= end_date + pd.Timedelta(days=5))
            ]

            if len(bench_start_dates) > 0 and len(bench_end_dates) > 0:
                bench_start_val = benchmark_series[bench_start_dates[0]]
                bench_end_val = benchmark_series[bench_end_dates[0]]
                bench_cagr = compute_cagr(bench_start_val, bench_end_val, actual_years)
                if bench_cagr is not None:
                    benchmark_cagrs.append((cagr, bench_cagr))

    if len(rolling_cagrs) < 10:
        return None

    arr = np.array(rolling_cagrs)

    result = {
        'scheme_code':          scheme_code,
        'horizon_years':        horizon_years,
        'rolling_period_count': len(rolling_cagrs),
        'cagr_mean':            round(float(np.mean(arr)), 4),
        'cagr_median':          round(float(np.median(arr)), 4),
        'cagr_std':             round(float(np.std(arr)), 4),
        'cagr_min':             round(float(np.min(arr)), 4),
        'cagr_max':             round(float(np.max(arr)), 4),
        'cagr_25th':            round(float(np.percentile(arr, 25)), 4),
        'cagr_75th':            round(float(np.percentile(arr, 75)), 4),
        'rolling_cagrs':        rolling_cagrs,
    }

    # Percent of periods beating various targets
    for target in [8, 10, 12, 14, 15, 16, 17, 18, 20]:
        pct = round(float(np.mean(arr >= target) * 100), 2)
        result[f'pct_beat_{target}'] = pct

    # Percent of periods beating benchmark
    if len(benchmark_cagrs) >= 10:
        beat_benchmark = sum(1 for f, b in benchmark_cagrs if f > b)
        result['pct_beat_benchmark'] = round(beat_benchmark / len(benchmark_cagrs) * 100, 2)
        result['avg_outperformance'] = round(
            float(np.mean([f - b for f, b in benchmark_cagrs])), 4
        )
    else:
        result['pct_beat_benchmark'] = None
        result['avg_outperformance'] = None

    return result

def compute_point_to_point_cagr(scheme_code, years):
    """
    Simple point-to-point CAGR for the metrics table display.
    Uses most recent NAV as end point, goes back 'years' from there.
    """
    nav_series = get_nav_series(scheme_code)
    if nav_series is None or len(nav_series) < 2:
        return None

    end_date = nav_series.index[-1]
    target_start = end_date - pd.Timedelta(days=int(years * 365.25))

    # Find closest date to target start
    available = nav_series.index[nav_series.index <= target_start + pd.Timedelta(days=30)]
    available = available[available >= target_start - pd.Timedelta(days=30)]

    if len(available) == 0:
        return None

    start_date = available[-1]
    actual_years = (end_date - start_date).days / 365.25

    return compute_cagr(
        float(nav_series[start_date]),
        float(nav_series[end_date]),
        actual_years
    )

def get_inception_date(scheme_code):
    """Return the inception date of a fund from nav_data."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MIN(nav_date) FROM nav_data WHERE scheme_code = %s
    """, (scheme_code,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

def compute_since_inception_cagr(scheme_code):
    """CAGR from inception to today."""
    nav_series = get_nav_series(scheme_code)
    if nav_series is None or len(nav_series) < 2:
        return None

    start_date = nav_series.index[0]
    end_date = nav_series.index[-1]
    actual_years = (end_date - start_date).days / 365.25

    if actual_years < 0.5:
        return None

    return compute_cagr(
        float(nav_series[start_date]),
        float(nav_series[end_date]),
        actual_years
    )


if __name__ == "__main__":
    # Test on Parag Parikh Flexi Cap Direct Growth
    TEST_SCHEME = '122639'
    TEST_NAME = 'Parag Parikh Flexi Cap Fund - Direct Growth'

    print("=" * 60)
    print("ROLLING RETURN CALCULATOR — TEST")
    print(f"Fund: {TEST_NAME}")
    print("=" * 60)

    # Test point-to-point CAGR
    print("\nPoint-to-Point CAGR:")
    for years in [1, 3, 5, 7, 10]:
        cagr = compute_point_to_point_cagr(TEST_SCHEME, years)
        if cagr:
            print(f"  {years} Year:  {cagr:.2f}%")

    since_inc = compute_since_inception_cagr(TEST_SCHEME)
    if since_inc:
        print(f"  Since Inception: {since_inc:.2f}%")

    # Test rolling returns for 7-year horizon
    print("\nComputing 7-year rolling returns...")
    print("(This takes 20-30 seconds for a fund with 13 years of data)")
    start = datetime.now()

    result = compute_rolling_returns(TEST_SCHEME, 7)

    elapsed = (datetime.now() - start).seconds

    if result:
        print(f"\n7-Year Rolling Return Analysis ({elapsed}s):")
        print(f"  Rolling periods computed: {result['rolling_period_count']}")
        print(f"  Mean CAGR:               {result['cagr_mean']:.2f}%")
        print(f"  Median CAGR:             {result['cagr_median']:.2f}%")
        print(f"  Std Deviation:           {result['cagr_std']:.2f}%")
        print(f"  Best period:             {result['cagr_max']:.2f}%")
        print(f"  Worst period:            {result['cagr_min']:.2f}%")
        print(f"  25th percentile:         {result['cagr_25th']:.2f}%")
        print(f"  75th percentile:         {result['cagr_75th']:.2f}%")
        print()
        print("  % of periods beating target:")
        for target in [10, 12, 14, 15, 16]:
            print(f"    Beat {target}%: {result.get(f'pct_beat_{target}', 0):.1f}% of periods")
        if result['pct_beat_benchmark']:
            print(f"\n  Beat Nifty 500:  {result['pct_beat_benchmark']:.1f}% of periods")
            print(f"  Avg outperformance: {result['avg_outperformance']:.2f}%")
    else:
        print("Insufficient data for rolling return analysis")

    print("\nROLLING RETURN CALCULATOR — TEST COMPLETE")
