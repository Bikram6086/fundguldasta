"""
FUNDGULDASTA — RISK METRIC CALCULATOR
=======================================
Computes risk-adjusted return metrics for individual funds.

All metrics computed within category peer groups.
A small cap fund is NEVER compared to a large cap fund.
Each fund judged only against its category peers.

Metrics computed:
- Sortino Ratio: return per unit of DOWNSIDE risk only
  (more relevant than Sharpe — upside volatility is not a problem)
- Sharpe Ratio: return per unit of total risk
- Calmar Ratio: annualised return / maximum drawdown
- Maximum Drawdown: largest peak-to-trough fall
- Drawdown Duration: how long it stayed below previous peak
- Upside/Downside Capture vs benchmark
- Crash period specific analysis
"""

import psycopg2
import numpy as np
import pandas as pd
import os
from datetime import datetime, date
from dotenv import load_dotenv
from engine.rolling_returns import get_nav_series, get_benchmark_series, compute_cagr

from config.db import get_db_config
DB_CONFIG = get_db_config()

# Risk-free rate — approximate 6-month T-bill rate in India
RISK_FREE_RATE_ANNUAL = 6.5
RISK_FREE_RATE_DAILY = RISK_FREE_RATE_ANNUAL / 100 / 252

# Major crash periods — precise dates
CRASH_PERIODS = [
    {
        'name': '2008 Global Financial Crisis',
        'peak_date': '2008-01-08',
        'trough_date': '2009-03-09',
    },
    {
        'name': '2015-16 Slowdown',
        'peak_date': '2015-03-03',
        'trough_date': '2016-02-29',
    },
    {
        'name': '2020 COVID Crash',
        'peak_date': '2020-01-14',
        'trough_date': '2020-03-23',
    },
    {
        'name': '2022 Rate Hike Selloff',
        'peak_date': '2021-10-19',
        'trough_date': '2022-06-17',
    },
]

def compute_daily_returns(nav_series):
    """Convert NAV series to daily return series."""
    return nav_series.pct_change().dropna()

def compute_sortino_ratio(nav_series, years=5):
    """
    Sortino Ratio = (Annualised Return - Risk Free Rate) / Downside Deviation

    Uses only NEGATIVE returns in denominator.
    More relevant than Sharpe for long-term investors
    who only care about downside risk.
    """
    if len(nav_series) < 252:
        return None

    # Use last N years
    cutoff = nav_series.index[-1] - pd.Timedelta(days=int(years * 365.25))
    series = nav_series[nav_series.index >= cutoff]

    if len(series) < 100:
        return None

    daily_returns = compute_daily_returns(series)

    # Annualised return
    total_return = series.iloc[-1] / series.iloc[0]
    actual_years = (series.index[-1] - series.index[0]).days / 365.25
    annualised_return = (pow(total_return, 1/actual_years) - 1) * 100

    # Downside deviation — only negative daily returns
    downside_returns = daily_returns[daily_returns < 0]
    if len(downside_returns) < 10:
        return None

    downside_std = float(np.std(downside_returns)) * np.sqrt(252) * 100

    if downside_std == 0:
        return None

    sortino = (annualised_return - RISK_FREE_RATE_ANNUAL) / downside_std
    return round(sortino, 4)

def compute_sharpe_ratio(nav_series, years=5):
    """
    Sharpe Ratio = (Annualised Return - Risk Free Rate) / Annualised Std Dev
    """
    if len(nav_series) < 252:
        return None

    cutoff = nav_series.index[-1] - pd.Timedelta(days=int(years * 365.25))
    series = nav_series[nav_series.index >= cutoff]

    if len(series) < 100:
        return None

    daily_returns = compute_daily_returns(series)

    total_return = series.iloc[-1] / series.iloc[0]
    actual_years = (series.index[-1] - series.index[0]).days / 365.25
    annualised_return = (pow(total_return, 1/actual_years) - 1) * 100

    annualised_std = float(np.std(daily_returns)) * np.sqrt(252) * 100

    if annualised_std == 0:
        return None

    sharpe = (annualised_return - RISK_FREE_RATE_ANNUAL) / annualised_std
    return round(sharpe, 4)

def compute_max_drawdown(nav_series):
    """
    Maximum Drawdown = largest peak-to-trough fall in history.
    Returns: (max_drawdown_pct, drawdown_start, drawdown_trough, recovery_date, duration_days)
    """
    if len(nav_series) < 10:
        return None

    values = nav_series.values
    dates = nav_series.index

    peak = values[0]
    peak_idx = 0
    max_dd = 0
    max_dd_start = dates[0]
    max_dd_trough = dates[0]
    max_dd_trough_idx = 0

    for i in range(1, len(values)):
        if values[i] > peak:
            peak = values[i]
            peak_idx = i
        else:
            dd = (values[i] - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
                max_dd_start = dates[peak_idx]
                max_dd_trough = dates[i]
                max_dd_trough_idx = i

    # Find recovery date
    recovery_date = None
    peak_val_at_trough_start = nav_series[max_dd_start]
    for i in range(max_dd_trough_idx, len(values)):
        if values[i] >= peak_val_at_trough_start:
            recovery_date = dates[i]
            break

    duration_days = (max_dd_trough - max_dd_start).days if max_dd_start and max_dd_trough else None

    return {
        'max_drawdown_pct': round(max_dd, 4),
        'drawdown_start': max_dd_start,
        'drawdown_trough': max_dd_trough,
        'recovery_date': recovery_date,
        'duration_days': duration_days,
    }

def compute_calmar_ratio(nav_series, years=3):
    """
    Calmar Ratio = Annualised Return / Absolute Max Drawdown
    Higher is better. Measures return per unit of worst-case loss.
    """
    if len(nav_series) < 252:
        return None

    cutoff = nav_series.index[-1] - pd.Timedelta(days=int(years * 365.25))
    series = nav_series[nav_series.index >= cutoff]

    total_return = series.iloc[-1] / series.iloc[0]
    actual_years = (series.index[-1] - series.index[0]).days / 365.25
    annualised_return = (pow(total_return, 1/actual_years) - 1) * 100

    dd = compute_max_drawdown(series)
    if dd is None or dd['max_drawdown_pct'] == 0:
        return None

    calmar = annualised_return / abs(dd['max_drawdown_pct'])
    return round(calmar, 4)

def compute_capture_ratios(nav_series, benchmark_series, years=5):
    """
    Upside Capture: how much of benchmark gains does fund capture?
    Downside Capture: how much of benchmark losses does fund suffer?

    Ideal: high upside capture, low downside capture.
    """
    if nav_series is None or benchmark_series is None:
        return None, None

    cutoff = nav_series.index[-1] - pd.Timedelta(days=int(years * 365.25))
    fund = nav_series[nav_series.index >= cutoff]
    bench = benchmark_series[benchmark_series.index >= cutoff]

    # Align dates
    common_dates = fund.index.intersection(bench.index)
    if len(common_dates) < 100:
        return None, None

    fund_aligned = fund[common_dates]
    bench_aligned = bench[common_dates]

    fund_returns = compute_daily_returns(fund_aligned)
    bench_returns = compute_daily_returns(bench_aligned)

    # Align return series
    common = fund_returns.index.intersection(bench_returns.index)
    fr = fund_returns[common]
    br = bench_returns[common]

    # Upside: periods when benchmark was positive
    up_mask = br > 0
    down_mask = br < 0

    if up_mask.sum() < 10 or down_mask.sum() < 10:
        return None, None

    upside_capture = (fr[up_mask].mean() / br[up_mask].mean()) * 100
    downside_capture = (fr[down_mask].mean() / br[down_mask].mean()) * 100

    return round(float(upside_capture), 2), round(float(downside_capture), 2)

def compute_crash_performance(nav_series, crash_periods=CRASH_PERIODS):
    """
    Analyse fund performance during each historical crash period.
    Returns peak fall, recovery months, and post-recovery CAGR.
    """
    results = []

    for crash in crash_periods:
        try:
            peak_date = pd.Timestamp(crash['peak_date'])
            trough_date = pd.Timestamp(crash['trough_date'])

            # Check if fund existed during this crash
            if nav_series.index[0] > peak_date:
                continue

            # Find closest NAV to peak and trough dates
            peak_candidates = nav_series.index[
                (nav_series.index >= peak_date - pd.Timedelta(days=10)) &
                (nav_series.index <= peak_date + pd.Timedelta(days=10))
            ]
            trough_candidates = nav_series.index[
                (nav_series.index >= trough_date - pd.Timedelta(days=10)) &
                (nav_series.index <= trough_date + pd.Timedelta(days=10))
            ]

            if len(peak_candidates) == 0 or len(trough_candidates) == 0:
                continue

            peak_nav = float(nav_series[peak_candidates[0]])
            trough_nav = float(nav_series[trough_candidates[0]])

            peak_fall_pct = round((trough_nav - peak_nav) / peak_nav * 100, 2)

            # Find recovery date — when NAV recovered to pre-crash peak
            post_trough = nav_series[nav_series.index > trough_candidates[0]]
            recovery_date = None
            for d, v in post_trough.items():
                if float(v) >= peak_nav:
                    recovery_date = d
                    break

            recovery_months = None
            if recovery_date:
                recovery_months = round(
                    (recovery_date - trough_candidates[0]).days / 30.44, 1
                )

            # Post-recovery CAGR (3 years after recovery if available)
            post_recovery_cagr = None
            if recovery_date:
                three_yr_later = recovery_date + pd.Timedelta(days=3*365)
                post_candidates = nav_series.index[
                    (nav_series.index >= three_yr_later - pd.Timedelta(days=30)) &
                    (nav_series.index <= three_yr_later + pd.Timedelta(days=30))
                ]
                if len(post_candidates) > 0:
                    post_recovery_cagr = compute_cagr(
                        peak_nav,
                        float(nav_series[post_candidates[0]]),
                        (post_candidates[0] - peak_candidates[0]).days / 365.25
                    )

            results.append({
                'event': crash['name'],
                'peak_fall_pct': peak_fall_pct,
                'recovery_months': recovery_months,
                'post_recovery_cagr': post_recovery_cagr,
                'fund_existed': True,
            })

        except Exception as e:
            continue

    return results

def compute_all_risk_metrics(scheme_code, benchmark_code='NIFTY500'):
    """
    Master function — computes all risk metrics for a fund.
    Returns complete risk profile dictionary.
    """
    nav_series = get_nav_series(scheme_code)
    if nav_series is None or len(nav_series) < 100:
        return None

    benchmark_series = get_benchmark_series(benchmark_code)

    result = {'scheme_code': scheme_code}

    result['sortino_5yr'] = compute_sortino_ratio(nav_series, years=5)
    result['sortino_3yr'] = compute_sortino_ratio(nav_series, years=3)
    result['sharpe_5yr'] = compute_sharpe_ratio(nav_series, years=5)
    result['calmar_3yr'] = compute_calmar_ratio(nav_series, years=3)

    dd = compute_max_drawdown(nav_series)
    if dd:
        result.update(dd)

    upside, downside = compute_capture_ratios(nav_series, benchmark_series)
    result['upside_capture'] = upside
    result['downside_capture'] = downside

    result['crash_performance'] = compute_crash_performance(nav_series)

    return result


if __name__ == "__main__":
    TEST_SCHEME = '122639'
    TEST_NAME = 'Parag Parikh Flexi Cap Fund - Direct Growth'

    print("=" * 60)
    print("RISK METRIC CALCULATOR — TEST")
    print(f"Fund: {TEST_NAME}")
    print("=" * 60)

    result = compute_all_risk_metrics(TEST_SCHEME)

    if result:
        print(f"\nRisk Metrics:")
        print(f"  Sortino Ratio (5yr):    {result.get('sortino_5yr', 'N/A')}")
        print(f"  Sortino Ratio (3yr):    {result.get('sortino_3yr', 'N/A')}")
        print(f"  Sharpe Ratio (5yr):     {result.get('sharpe_5yr', 'N/A')}")
        print(f"  Calmar Ratio (3yr):     {result.get('calmar_3yr', 'N/A')}")
        print(f"  Max Drawdown:           {result.get('max_drawdown_pct', 'N/A')}%")
        print(f"  Drawdown Duration:      {result.get('duration_days', 'N/A')} days")
        print(f"  Upside Capture:         {result.get('upside_capture', 'N/A')}%")
        print(f"  Downside Capture:       {result.get('downside_capture', 'N/A')}%")

        print(f"\nCrash Period Performance:")
        for crash in result.get('crash_performance', []):
            print(f"\n  {crash['event']}")
            print(f"    Peak Fall:        {crash['peak_fall_pct']}%")
            print(f"    Recovery:         {crash['recovery_months']} months")
            if crash['post_recovery_cagr']:
                print(f"    Post-Recovery CAGR: {crash['post_recovery_cagr']:.2f}%")
    else:
        print("Insufficient data")

    print("\nRISK METRIC CALCULATOR — TEST COMPLETE")
