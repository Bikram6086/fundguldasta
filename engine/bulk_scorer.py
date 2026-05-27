"""
FUNDGULDASTA — BULK FUND SCORER
=================================
Scores all eligible Tier 1+2 funds across key investment horizons and
writes results to computed_metrics. This is the foundation for Screen 2
(Goal Bouquet) — without these scores, Goal Bouquet cannot select funds.

Run manually (from project root):
    python3 -m engine.bulk_scorer

Runs automatically as part of the nightly precompute pipeline.

Design decisions:
- Scores at target_cagr=16 (mid-range baseline). Return_consistency
  dimension is the only one that varies with target; the other 5 dimensions
  (~75% of the score) are target-independent. Rankings are ~85% stable
  across realistic target ranges.
- Risk metrics (sortino, sharpe, max_drawdown, capture ratios) are
  horizon-independent — computed once per fund and reused across horizons.
- Upsert logic: safe to re-run; updates stale rows.
"""

import psycopg2
import traceback
from datetime import date, datetime

from config.db import get_db_config
from engine.eligibility_filter import run_eligibility_filter
from engine.fund_scorer import compute_composite_score
from engine.rolling_returns import compute_rolling_returns, compute_point_to_point_cagr
from engine.risk_metrics import compute_all_risk_metrics
from engine.regular_plan_proxy import find_regular_plan

DB_CONFIG = get_db_config()

HORIZONS = [5, 7, 10, 15, 20, 30]


def _f(v):
    """Convert numpy/decimal types to native Python float, or None."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    """Convert to native Python int, or None."""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
TARGET_CAGR = 16.0

# Only confirmed eligible SEBI categories — exclude Unknown/unclassified
CONFIRMED_ELIGIBLE_CATEGORIES = {
    'Large Cap', 'Mid Cap', 'Small Cap', 'Flexi Cap', 'Multi Cap',
    'Large & Mid Cap', 'ELSS', 'Focused', 'Contra', 'Value',
    'Balanced Advantage', 'Aggressive Hybrid', 'Equity Savings',
}


def get_eligible_funds():
    """Return Tier 1+2 funds with confirmed SEBI categories only."""
    eligible, _ = run_eligibility_filter(verbose=False)
    return [
        f for f in eligible
        if f['evidence_tier'] in (1, 2)
        and f.get('sebi_category') in CONFIRMED_ELIGIBLE_CATEGORIES
    ]


def score_and_store(fund: dict, horizons: list) -> dict:
    """
    Score a single fund across all horizons and upsert into computed_metrics.
    Returns {horizon: score_result or None} for reporting.
    """
    code = fund['scheme_code']
    category = fund['sebi_category']
    today = date.today()

    # Compute risk metrics once — horizon-independent
    try:
        risk = compute_all_risk_metrics(code) or {}
    except Exception:
        risk = {}

    sortino = risk.get('sortino_5yr')
    sharpe = risk.get('sharpe_5yr')
    calmar = risk.get('calmar_3yr')
    max_dd = risk.get('max_drawdown_pct')
    max_dd_days = risk.get('max_drawdown_duration_days')
    upside = risk.get('upside_capture')
    downside = risk.get('downside_capture')

    # Find regular plan proxy once per fund (used for 15/20/30yr horizons)
    proxy_code = find_regular_plan(code)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    results = {}

    for horizon in horizons:
        try:
            # Rolling return stats — proxy used automatically when direct plan
            # lacks sufficient history (pre-2013 periods for 15/20/30yr horizons)
            rolling = compute_rolling_returns(code, horizon, proxy_code=proxy_code)
            if not rolling:
                results[horizon] = None
                continue

            # Point-to-point CAGR for this horizon
            try:
                cagr_ptp = compute_point_to_point_cagr(code, horizon, proxy_code=proxy_code)
            except Exception:
                cagr_ptp = rolling.get('cagr_mean')

            # Composite score — proxy_code threads into return_consistency only
            score = compute_composite_score(code, horizon, TARGET_CAGR, category, proxy_code=proxy_code)
            dims = score['dimension_scores']

            cur.execute("""
                INSERT INTO computed_metrics (
                    scheme_code, computation_date, horizon_years,
                    cagr_pct, rolling_cagr_mean, rolling_cagr_median, rolling_cagr_std,
                    pct_periods_beat_target, pct_periods_beat_benchmark, rolling_period_count,
                    sortino_ratio, sharpe_ratio, calmar_ratio,
                    max_drawdown_pct, max_drawdown_duration_days,
                    upside_capture, downside_capture,
                    fund_score,
                    return_consistency_score, risk_adjusted_score, downside_score,
                    manager_score, portfolio_quality_score, forward_context_score
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s,
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (scheme_code, computation_date, horizon_years)
                DO UPDATE SET
                    cagr_pct                 = EXCLUDED.cagr_pct,
                    rolling_cagr_mean        = EXCLUDED.rolling_cagr_mean,
                    rolling_cagr_median      = EXCLUDED.rolling_cagr_median,
                    rolling_cagr_std         = EXCLUDED.rolling_cagr_std,
                    pct_periods_beat_target  = EXCLUDED.pct_periods_beat_target,
                    pct_periods_beat_benchmark = EXCLUDED.pct_periods_beat_benchmark,
                    rolling_period_count     = EXCLUDED.rolling_period_count,
                    sortino_ratio            = EXCLUDED.sortino_ratio,
                    sharpe_ratio             = EXCLUDED.sharpe_ratio,
                    calmar_ratio             = EXCLUDED.calmar_ratio,
                    max_drawdown_pct         = EXCLUDED.max_drawdown_pct,
                    max_drawdown_duration_days = EXCLUDED.max_drawdown_duration_days,
                    upside_capture           = EXCLUDED.upside_capture,
                    downside_capture         = EXCLUDED.downside_capture,
                    fund_score               = EXCLUDED.fund_score,
                    return_consistency_score = EXCLUDED.return_consistency_score,
                    risk_adjusted_score      = EXCLUDED.risk_adjusted_score,
                    downside_score           = EXCLUDED.downside_score,
                    manager_score            = EXCLUDED.manager_score,
                    portfolio_quality_score  = EXCLUDED.portfolio_quality_score,
                    forward_context_score    = EXCLUDED.forward_context_score
            """, (
                code, today, horizon,
                _f(cagr_ptp),
                _f(rolling.get('cagr_mean')), _f(rolling.get('cagr_median')), _f(rolling.get('cagr_std')),
                _f(rolling.get('pct_beat_16')), _f(rolling.get('pct_beat_benchmark')),
                _i(rolling.get('rolling_period_count')),
                _f(sortino), _f(sharpe), _f(calmar),
                _f(max_dd), _i(max_dd_days),
                _f(upside), _f(downside),
                _f(score['composite_score']),
                _f(dims.get('return_consistency')), _f(dims.get('risk_adjusted')),
                _f(dims.get('downside_behaviour')), _f(dims.get('manager_stability')),
                _f(dims.get('portfolio_quality')), _f(dims.get('forward_context')),
            ))
            conn.commit()
            results[horizon] = score['composite_score']

        except Exception as e:
            conn.rollback()
            results[horizon] = f"ERROR: {e}"

    cur.close()
    conn.close()
    return results


def run_bulk_scoring(horizons=None, verbose=True):
    """
    Score all Tier 1+2 eligible funds and populate computed_metrics.
    Returns summary dict.
    """
    horizons = horizons or HORIZONS
    funds = get_eligible_funds()

    if verbose:
        print("=" * 65)
        print(f"BULK FUND SCORING — Fund Intelligence Engine")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Funds:    {len(funds)} eligible (Tier 1+2, confirmed categories)")
        print(f"Horizons: {horizons}")
        print(f"Target:   {TARGET_CAGR}% CAGR (baseline)")
        print("=" * 65)

    total = 0
    errors = 0
    skipped = 0

    for i, fund in enumerate(funds, 1):
        code = fund['scheme_code']
        name = fund['scheme_name'][:48]
        tier = fund['evidence_tier']
        cat = fund['sebi_category']

        proxy = find_regular_plan(code)
        proxy_tag = f"[proxy:{proxy}]" if proxy else ""

        if verbose:
            print(f"[{i:>3}/{len(funds)}] T{tier} {code} {name[:38]:<38} {proxy_tag:<16}", end=" ", flush=True)

        try:
            results = score_and_store(fund, horizons)
            scored = sum(1 for v in results.values() if isinstance(v, float))
            errs = sum(1 for v in results.values() if isinstance(v, str))
            total += scored
            errors += errs
            if verbose:
                scores_str = " | ".join(
                    f"{h}yr:{v:.0f}" if isinstance(v, float) else f"{h}yr:ERR"
                    for h, v in results.items()
                )
                print(f"→ {scores_str}")
        except Exception as e:
            errors += 1
            skipped += 1
            if verbose:
                print(f"→ SKIPPED ({e})")

    if verbose:
        print()
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Scored:    {total} fund-horizon rows written")
        print(f"Errors:    {errors}")
        print("=" * 65)

    return {'funds': len(funds), 'scored': total, 'errors': errors}


if __name__ == "__main__":
    run_bulk_scoring()
