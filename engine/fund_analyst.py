"""
FUNDGULDASTA — Mutual Fund Intelligence & Decision Engine
==========================================================
Evaluates any mutual fund across 7 dimensions, 30+ parameters.
Produces a composite decision-quality score, sub-scores, warnings,
strengths, and investor suitability profile.

Philosophy: probability-adjusted quality and attractiveness —
NOT guaranteed future performance.

Public API:
    analyse_fund(scheme_code) -> dict   (full analysis, ~2-4s)
    analyse_fund_fast(scheme_code) -> dict  (metadata + quick metrics only)
"""
import math
import psycopg2
import numpy as np
import pandas as pd
from datetime import date, timedelta

from config.db import get_db_config
from engine.rolling_returns import get_nav_series, get_benchmark_series, compute_cagr
from engine.risk_metrics import (
    compute_sharpe_ratio, compute_sortino_ratio,
    compute_max_drawdown, compute_capture_ratios,
)

_DB_CONFIG = get_db_config()
_RISK_FREE = 6.5          # India 10yr G-Sec approximate (%)
_BENCHMARK  = 'NIFTY500'  # default benchmark

# ── Category risk profiles (typical volatility, max DD, risk level 1-5) ──────
_CAT_PROFILE = {
    'Large Cap':           dict(vol=16, max_dd=32, risk=2, peer_cagr_5yr=12.5),
    'Mid Cap':             dict(vol=22, max_dd=45, risk=3, peer_cagr_5yr=15.0),
    'Small Cap':           dict(vol=28, max_dd=58, risk=5, peer_cagr_5yr=16.5),
    'Flexi Cap':           dict(vol=18, max_dd=38, risk=3, peer_cagr_5yr=14.0),
    'Multi Cap':           dict(vol=20, max_dd=40, risk=3, peer_cagr_5yr=14.0),
    'Large & MidCap':      dict(vol=20, max_dd=40, risk=3, peer_cagr_5yr=13.5),
    'Value':               dict(vol=18, max_dd=38, risk=3, peer_cagr_5yr=13.0),
    'ELSS':                dict(vol=20, max_dd=40, risk=3, peer_cagr_5yr=13.5),
    'Focused':             dict(vol=20, max_dd=42, risk=3, peer_cagr_5yr=14.0),
    'Aggressive Hybrid':   dict(vol=16, max_dd=32, risk=2, peer_cagr_5yr=12.0),
    'Balanced Advantage':  dict(vol=12, max_dd=25, risk=2, peer_cagr_5yr=10.5),
    'Conservative Hybrid': dict(vol=9,  max_dd=18, risk=1, peer_cagr_5yr=9.0),
    'Equity Savings':      dict(vol=8,  max_dd=15, risk=1, peer_cagr_5yr=8.5),
    'International':       dict(vol=18, max_dd=38, risk=3, peer_cagr_5yr=13.0),
    'Sectoral/Thematic':   dict(vol=26, max_dd=52, risk=4, peer_cagr_5yr=14.0),
    'Index':               dict(vol=17, max_dd=35, risk=2, peer_cagr_5yr=12.5),
}
_DEFAULT_PROFILE = dict(vol=20, max_dd=40, risk=3, peer_cagr_5yr=13.0)


# ── Raw metric helpers ────────────────────────────────────────────────────────

def _point_cagr(nav_series: pd.Series, years: float) -> float | None:
    """CAGR from nav_series over the last `years` years."""
    if nav_series is None or len(nav_series) < 50:
        return None
    end_val   = nav_series.iloc[-1]
    target_dt = nav_series.index[-1] - pd.DateOffset(years=int(years),
                                                       months=round((years % 1) * 12))
    avail = nav_series[nav_series.index <= target_dt]
    if avail.empty:
        return None
    start_val = avail.iloc[-1]
    actual_years = (nav_series.index[-1] - avail.index[-1]).days / 365.25
    if actual_years < years * 0.75:   # need at least 75% of the horizon
        return None
    result = compute_cagr(start_val, end_val, actual_years)
    return round(result, 2) if result is not None else None


def _rolling_cagr_stats(nav_series: pd.Series, window_years: int) -> dict:
    """
    Monthly-sampled rolling CAGR over `window_years`.
    Returns mean, median, std, win_rate (>0%), consistency_7 (>7%),
    consistency_10 (>10%), positive_periods, total_periods.
    """
    if nav_series is None or len(nav_series) < window_years * 200:
        return {}
    monthly = nav_series.resample('ME').last().dropna()
    window  = window_years * 12
    if len(monthly) < window + 6:
        return {}
    cagrs = []
    for i in range(len(monthly) - window):
        s, e = monthly.iloc[i], monthly.iloc[i + window]
        if s > 0:
            cagrs.append(((e / s) ** (1 / window_years) - 1) * 100)
    if not cagrs:
        return {}
    arr = np.array(cagrs)
    return {
        'mean':            round(float(arr.mean()), 2),
        'median':          round(float(np.median(arr)), 2),
        'std':             round(float(arr.std()), 2),
        'win_rate':        round(float((arr > 0).mean() * 100), 1),
        'consistency_7':   round(float((arr > 7).mean() * 100), 1),
        'consistency_10':  round(float((arr > 10).mean() * 100), 1),
        'total_periods':   len(cagrs),
    }


def _beta_alpha(fund: pd.Series, bench: pd.Series, years: float = 5) -> tuple:
    """Jensen's alpha (annualised %) and beta vs benchmark."""
    if fund is None or bench is None:
        return None, None
    cutoff = fund.index[-1] - pd.DateOffset(years=int(years))
    f = fund[fund.index >= cutoff].resample('W').last().pct_change().dropna()
    b = bench[bench.index >= cutoff].resample('W').last().pct_change().dropna()
    aligned = pd.DataFrame({'f': f, 'b': b}).dropna()
    if len(aligned) < 50:
        return None, None
    cov  = aligned.cov()
    beta = round(float(cov.loc['f', 'b'] / cov.loc['b', 'b']), 3)
    # Annualised alpha: Jensen's alpha
    fund_cagr  = _point_cagr(fund, years) or 0
    bench_cagr = _point_cagr(bench, years) or 0
    alpha = round(fund_cagr - (_RISK_FREE + beta * (bench_cagr - _RISK_FREE)), 2)
    return alpha, beta


def _annual_volatility(nav_series: pd.Series, years: float = 5) -> float | None:
    if nav_series is None or len(nav_series) < 100:
        return None
    cutoff = nav_series.index[-1] - pd.DateOffset(years=int(years))
    sliced = nav_series[nav_series.index >= cutoff]
    if len(sliced) < 50:
        return None
    daily = sliced.pct_change().dropna()
    return round(float(daily.std() * math.sqrt(252) * 100), 2)


# ── Scoring functions (all return 0-100) ─────────────────────────────────────

def _clamp(v, lo=0, hi=100):
    return int(max(lo, min(hi, round(v))))


def _s_cagr(cagr, peer_cagr=13.0):
    if cagr is None:
        return 40
    excess = cagr - peer_cagr
    return _clamp(50 + excess * 5)


def _s_sharpe(s):
    if s is None:
        return 40
    return _clamp(s / 1.5 * 100)


def _s_sortino(s):
    if s is None:
        return 40
    return _clamp(s / 2.0 * 100)


def _s_alpha(a):
    if a is None:
        return 50
    return _clamp(50 + a * 5)


def _s_beta(b):
    if b is None:
        return 55
    if b <= 0.7:
        return 65    # very low beta — defensive but may lag in rallies
    if b <= 1.0:
        return 85
    if b <= 1.15:
        return 75
    if b <= 1.3:
        return 60
    return _clamp(60 - (b - 1.3) * 60)


def _s_volatility(vol, typical=19.0):
    if vol is None:
        return 50
    return _clamp(75 - (vol - typical) * 2.5)


def _s_max_drawdown(dd, typical=-38.0):
    # dd is negative; less negative = better
    if dd is None:
        return 50
    return _clamp(70 + (dd - typical) * 1.2)


def _s_capture(upside, downside):
    if upside is None or downside is None:
        return 50
    score_up   = _clamp(upside / 1.1)
    score_down = _clamp((130 - downside) / 0.9)
    return (score_up + score_down) // 2


def _s_consistency(pct):
    # % of 3yr rolling windows beating 7%
    if pct is None:
        return 40
    return _clamp(pct)


def _s_rolling_stability(std_of_rolling):
    # Lower std = more consistent = better
    if std_of_rolling is None:
        return 50
    return _clamp(90 - std_of_rolling * 5)


def _s_expense_ratio(er):
    if er is None:
        return 50
    if er <= 0.50:
        return 95
    if er <= 0.80:
        return 85
    if er <= 1.10:
        return 72
    if er <= 1.50:
        return 55
    return _clamp(55 - (er - 1.5) * 20)


def _s_aum(aum_cr, category=''):
    if aum_cr is None:
        return 55
    is_smallmid = any(k in category for k in ('Small', 'Mid'))
    if aum_cr < 100:
        return 25
    if aum_cr < 500:
        return 50
    if aum_cr < 5000:
        return 80
    if aum_cr < 30000:
        return 90
    # Very large AUM — capacity concern for small/mid cap
    if is_smallmid and aum_cr > 30000:
        return 65
    return 80


def _s_fund_age(years):
    if years is None:
        return 30
    if years >= 15:
        return 98
    if years >= 10:
        return 88
    if years >= 7:
        return 75
    if years >= 5:
        return 62
    if years >= 3:
        return 45
    return 28


def _s_momentum_heat(cagr_1yr, cagr_5yr):
    """Penalise when 1yr CAGR is dramatically above long-term average."""
    if cagr_1yr is None or cagr_5yr is None:
        return 70
    gap = cagr_1yr - cagr_5yr
    if gap > 20:
        return 35  # severe overheating
    if gap > 12:
        return 50
    if gap > 6:
        return 65
    return 80   # healthy or recent underperformance — buy opportunity signal


# ── Dimension composers ───────────────────────────────────────────────────────

def _dim_structural_quality(m: dict, profile: dict) -> int:
    pc = profile.get('peer_cagr_5yr', 13.0)
    s_cagr3  = _s_cagr(m.get('cagr_3yr'),  pc - 1)
    s_cagr5  = _s_cagr(m.get('cagr_5yr'),  pc)
    s_cagr7  = _s_cagr(m.get('cagr_7yr'),  pc + 0.5)
    s_cagr10 = _s_cagr(m.get('cagr_10yr'), pc + 1.0)
    s_sharpe = _s_sharpe(m.get('sharpe_5yr'))
    s_alpha  = _s_alpha(m.get('alpha'))
    # Weighted average — weight heavier towards 5yr and 7yr
    cagr_composite = (
        0.20 * s_cagr3 + 0.35 * s_cagr5 + 0.30 * s_cagr7 + 0.15 * s_cagr10
        if m.get('cagr_10yr') is not None
        else 0.25 * s_cagr3 + 0.45 * s_cagr5 + 0.30 * s_cagr7
        if m.get('cagr_7yr') is not None
        else 0.35 * s_cagr3 + 0.65 * s_cagr5
    )
    return _clamp(0.40 * cagr_composite + 0.30 * s_sharpe + 0.30 * s_alpha)


def _dim_downside_protection(m: dict, profile: dict) -> int:
    s_dd      = _s_max_drawdown(m.get('max_drawdown_pct'), -(profile.get('max_dd', 38)))
    s_sortino = _s_sortino(m.get('sortino_5yr'))
    s_capture = _s_capture(m.get('upside_capture'), m.get('downside_capture'))
    return _clamp(0.38 * s_dd + 0.35 * s_sortino + 0.27 * s_capture)


def _dim_risk_profile(m: dict, profile: dict) -> int:
    s_beta  = _s_beta(m.get('beta'))
    s_vol   = _s_volatility(m.get('volatility_annual'), profile.get('vol', 19))
    s_aum   = _s_aum(m.get('aum_crores'), m.get('sebi_category', ''))
    s_er    = _s_expense_ratio(m.get('expense_ratio'))
    return _clamp(0.30 * s_beta + 0.35 * s_vol + 0.20 * s_aum + 0.15 * s_er)


def _dim_consistency(m: dict) -> int:
    r3 = m.get('rolling_3yr', {})
    s_win     = _s_consistency(r3.get('win_rate'))
    s_beat7   = _s_consistency(r3.get('consistency_7'))
    s_stable  = _s_rolling_stability(r3.get('std'))
    s_age     = _s_fund_age(m.get('fund_age_years'))
    return _clamp(0.25 * s_win + 0.30 * s_beat7 + 0.25 * s_stable + 0.20 * s_age)


def _dim_cost_efficiency(m: dict) -> int:
    s_er  = _s_expense_ratio(m.get('expense_ratio'))
    s_aum = _s_aum(m.get('aum_crores'), m.get('sebi_category', ''))
    return _clamp(0.70 * s_er + 0.30 * s_aum)


def _dim_category_opportunity(m: dict, profile: dict) -> int:
    s_heat = _s_momentum_heat(m.get('cagr_1yr'), m.get('cagr_5yr'))
    # Risk level inversely affects opportunity score during elevated markets
    risk   = profile.get('risk', 3)
    s_risk = _clamp((5 - risk) / 4 * 100)
    return _clamp(0.60 * s_heat + 0.40 * s_risk)


def _dim_suitability(m: dict, profile: dict) -> int:
    # Derived: conservative funds score high, consistent funds score high
    s_risk_adj = _clamp(100 - (profile.get('risk', 3) - 1) * 12)
    r3         = m.get('rolling_3yr', {})
    s_con      = _s_consistency(r3.get('consistency_7'))
    return _clamp(0.50 * s_risk_adj + 0.50 * s_con)


# ── Warning & strength generators ────────────────────────────────────────────

def _generate_warnings(m: dict, profile: dict) -> list[str]:
    warnings = []
    dd = m.get('max_drawdown_pct')
    if dd is not None and dd < -50:
        warnings.append(f"History of very severe drawdowns ({dd:.1f}%) — emotionally demanding for most investors.")
    elif dd is not None and dd < -40:
        warnings.append(f"Significant max drawdown of {dd:.1f}% recorded — requires long-term conviction.")

    beta = m.get('beta')
    if beta is not None and beta > 1.3:
        warnings.append(f"High market sensitivity (beta {beta:.2f}) — amplifies both gains and losses.")

    sharpe = m.get('sharpe_5yr')
    if sharpe is not None and sharpe < 0.5:
        warnings.append(f"Below-average risk-adjusted returns (Sharpe {sharpe:.2f}) — not compensating adequately for risk.")

    aum = m.get('aum_crores')
    cat = m.get('sebi_category', '')
    if aum is not None and aum < 200:
        warnings.append(f"Small fund (AUM ₹{aum:,.0f} Cr) — higher liquidity risk and potential fund closure risk.")
    if aum is not None and aum > 30000 and any(k in cat for k in ('Small', 'Mid')):
        warnings.append(f"Very large AUM (₹{aum:,.0f} Cr) for a Small/Mid Cap fund — may face capacity constraints.")

    er = m.get('expense_ratio')
    if er is not None and er > 1.5:
        warnings.append(f"High expense ratio ({er:.2f}%) — costs compound negatively over time.")

    cagr1 = m.get('cagr_1yr')
    cagr5 = m.get('cagr_5yr')
    if cagr1 is not None and cagr5 is not None and cagr1 - cagr5 > 15:
        warnings.append(f"Recent 1-year return ({cagr1:.1f}%) is significantly above long-term CAGR ({cagr5:.1f}%) — exercise caution on lump sum entry.")

    alpha = m.get('alpha')
    if alpha is not None and alpha < -2:
        warnings.append(f"Consistent benchmark underperformance (alpha {alpha:.1f}%) — consider if active management cost is justified.")

    r3 = m.get('rolling_3yr', {})
    cons7 = r3.get('consistency_7')
    if cons7 is not None and cons7 < 50:
        warnings.append(f"Only {cons7:.0f}% of 3-year rolling periods delivered above 7% CAGR — inconsistent track record.")

    age = m.get('fund_age_years')
    if age is not None and age < 5:
        warnings.append(f"Limited track record ({age:.1f} years) — insufficient data to assess long-term reliability.")

    return warnings


def _generate_strengths(m: dict, profile: dict) -> list[str]:
    strengths = []
    sharpe = m.get('sharpe_5yr')
    if sharpe is not None and sharpe > 1.0:
        strengths.append(f"Strong risk-adjusted returns (Sharpe {sharpe:.2f}) — rewarding investors well per unit of risk.")

    alpha = m.get('alpha')
    if alpha is not None and alpha > 3:
        strengths.append(f"Consistent benchmark outperformance — alpha of +{alpha:.1f}% annualised over 5 years.")
    elif alpha is not None and alpha > 1.5:
        strengths.append(f"Positive alpha ({alpha:.1f}%) demonstrates active management adding value.")

    dd = m.get('max_drawdown_pct')
    typical_dd = -(profile.get('max_dd', 38))
    if dd is not None and dd > typical_dd + 8:
        strengths.append(f"Better-than-category downside control (max drawdown {dd:.1f}% vs typical {typical_dd:.0f}%).")

    sortino = m.get('sortino_5yr')
    if sortino is not None and sortino > 1.2:
        strengths.append(f"Excellent downside risk management (Sortino {sortino:.2f}) — strong protection on bad days.")

    er = m.get('expense_ratio')
    if er is not None and er <= 0.70:
        strengths.append(f"Very cost-efficient (expense ratio {er:.2f}%) — maximises investor take-home returns.")

    r3 = m.get('rolling_3yr', {})
    cons7 = r3.get('consistency_7')
    if cons7 is not None and cons7 > 80:
        strengths.append(f"{cons7:.0f}% of all 3-year rolling periods delivered above 7% CAGR — highly consistent compounder.")

    upside = m.get('upside_capture')
    downside = m.get('downside_capture')
    if upside is not None and downside is not None and upside > 90 and downside < 80:
        strengths.append(f"Excellent capture ratio — captures {upside:.0f}% of bull market gains, only {downside:.0f}% of drawdowns.")

    age = m.get('fund_age_years')
    if age is not None and age >= 10:
        strengths.append(f"Long and proven track record of {age:.0f} years across multiple market cycles.")

    aum = m.get('aum_crores')
    if aum is not None and 2000 < aum < 30000:
        strengths.append(f"Well-scaled fund (AUM ₹{aum:,.0f} Cr) — sufficient size for stability, not yet constrained by capacity.")

    return strengths


def _suitability_profile(m: dict, profile: dict) -> dict:
    risk = profile.get('risk', 3)
    dd   = m.get('max_drawdown_pct') or -40
    vol  = m.get('annual_volatility') or profile.get('vol', 20)
    conservative  = risk <= 2 and dd > -30
    moderate      = risk <= 3
    aggressive    = True  # any equity fund can suit an aggressive investor
    sip_good      = True  # SIP is always suitable for equity
    lump_suitable = m.get('cagr_1yr') is not None and m.get('cagr_5yr') is not None \
                    and (m['cagr_1yr'] - m['cagr_5yr']) < 10
    min_horizon   = {1: 3, 2: 5, 3: 7, 4: 10, 5: 10}.get(risk, 7)
    rec_horizon   = {1: '3-5', 2: '5-7', 3: '7-10', 4: '10+', 5: '10+'}.get(risk, '7-10')
    return {
        'conservative': conservative,
        'moderate': moderate,
        'aggressive': aggressive,
        'sip_recommended': sip_good,
        'lumpsum_suitable': lump_suitable,
        'min_horizon_years': min_horizon,
        'recommended_horizon': rec_horizon + ' years',
    }


def _confidence_level(fund_age_years, nav_count) -> str:
    if fund_age_years is None:
        return 'Low'
    if fund_age_years >= 10 and nav_count >= 2000:
        return 'High'
    if fund_age_years >= 7 and nav_count >= 1400:
        return 'Moderate-High'
    if fund_age_years >= 5 and nav_count >= 900:
        return 'Moderate'
    if fund_age_years >= 3:
        return 'Low-Moderate'
    return 'Low'


def _verdict(composite: int, warnings: list, profile: dict) -> str:
    quality = 'exceptional' if composite >= 85 else \
              'strong' if composite >= 75 else \
              'reasonable' if composite >= 62 else \
              'below-average' if composite >= 50 else 'poor'
    risk    = profile.get('risk', 3)
    cat     = {1: 'conservative', 2: 'moderate-conservative', 3: 'moderate',
               4: 'moderately aggressive', 5: 'aggressive'}.get(risk, 'moderate')
    warn_count = len(warnings)
    suffix = (
        " Exercise caution — multiple risk flags present." if warn_count >= 3 else
        " One area of caution noted — review warnings before investing." if warn_count == 1 else
        " No major red flags detected."
    )
    return (
        f"Overall {quality} fund ({composite}/100) suited to a {cat} investor. "
        f"Invest via SIP for best long-term outcome.{suffix}"
    )


# ── DB fetch for metadata ─────────────────────────────────────────────────────

def _fetch_metadata(scheme_code: str) -> dict:
    conn = psycopg2.connect(**_DB_CONFIG)
    cur  = conn.cursor()
    cur.execute("""
        SELECT scheme_name, amc_name, sebi_category, sebi_sub_category,
               inception_date, expense_ratio, aum_crores, plan_type, fund_type
        FROM fund_metadata WHERE scheme_code = %s
    """, (scheme_code,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {}
    cols = ['scheme_name', 'amc_name', 'sebi_category', 'sebi_sub_category',
            'inception_date', 'expense_ratio', 'aum_crores', 'plan_type', 'fund_type']
    return dict(zip(cols, row))


# ── Master analysis function ──────────────────────────────────────────────────

def analyse_fund(scheme_code: str) -> dict:
    """
    Full multi-dimensional analysis of a mutual fund.
    Returns comprehensive dict with scores, raw metrics, warnings,
    strengths, suitability, and verdict.
    Computation time: ~2-5 seconds.
    """
    meta = _fetch_metadata(scheme_code)
    if not meta:
        return {'error': 'Fund not found in database.', 'scheme_code': scheme_code}

    nav = get_nav_series(scheme_code)
    if nav is None or len(nav) < 150:
        return {
            'error': 'Insufficient NAV history for meaningful analysis (need ≥6 months).',
            'scheme_code': scheme_code,
            'scheme_name': meta.get('scheme_name', ''),
        }

    bench = get_benchmark_series(_BENCHMARK)

    # ── Fund age ──
    nav_count       = len(nav)
    first_date      = nav.index[0].date()
    last_date       = nav.index[-1].date()
    fund_age_years  = round((last_date - first_date).days / 365.25, 1)

    # ── Category profile ──
    cat = meta.get('sebi_category') or ''
    profile = next((v for k, v in _CAT_PROFILE.items() if k in cat), _DEFAULT_PROFILE)

    # ── Point-in-time CAGRs ──
    cagr_1yr  = _point_cagr(nav, 1)
    cagr_3yr  = _point_cagr(nav, 3)
    cagr_5yr  = _point_cagr(nav, 5)
    cagr_7yr  = _point_cagr(nav, 7)
    cagr_10yr = _point_cagr(nav, 10)

    # ── Risk metrics (reuse existing engine) ──
    sharpe_5yr  = compute_sharpe_ratio(nav, years=5)
    sortino_5yr = compute_sortino_ratio(nav, years=5)
    dd_dict     = compute_max_drawdown(nav) or {}
    max_dd      = dd_dict.get('max_drawdown_pct')
    upside_cap, downside_cap = compute_capture_ratios(nav, bench, years=5)

    # ── Alpha, beta, volatility ──
    alpha, beta = _beta_alpha(nav, bench, years=5)
    vol_annual  = _annual_volatility(nav, years=5)

    # ── Rolling stats ──
    rolling_3yr = _rolling_cagr_stats(nav, 3)
    rolling_5yr = _rolling_cagr_stats(nav, 5)

    # ── Assemble raw metrics dict ──
    er  = float(meta['expense_ratio']) if meta.get('expense_ratio') else None
    aum = float(meta['aum_crores'])    if meta.get('aum_crores')    else None

    m = {
        'cagr_1yr':          cagr_1yr,
        'cagr_3yr':          cagr_3yr,
        'cagr_5yr':          cagr_5yr,
        'cagr_7yr':          cagr_7yr,
        'cagr_10yr':         cagr_10yr,
        'sharpe_5yr':        round(sharpe_5yr, 3) if sharpe_5yr else None,
        'sortino_5yr':       round(sortino_5yr, 3) if sortino_5yr else None,
        'beta':              beta,
        'alpha':             alpha,
        'volatility_annual': vol_annual,
        'max_drawdown_pct':  round(max_dd, 2) if max_dd is not None else None,
        'upside_capture':    round(upside_cap, 1) if upside_cap else None,
        'downside_capture':  round(downside_cap, 1) if downside_cap else None,
        'rolling_3yr':       rolling_3yr,
        'rolling_5yr':       rolling_5yr,
        'expense_ratio':     er,
        'aum_crores':        aum,
        'fund_age_years':    fund_age_years,
        'nav_count':         nav_count,
        'sebi_category':     cat,
    }

    # ── Dimension scores ──
    dim_a = _dim_structural_quality(m, profile)
    dim_b = _dim_downside_protection(m, profile)
    dim_c = _dim_risk_profile(m, profile)
    dim_d = _dim_consistency(m)
    dim_e = _dim_cost_efficiency(m)
    dim_f = _dim_category_opportunity(m, profile)
    dim_g = _dim_suitability(m, profile)

    composite = _clamp(
        0.30 * dim_a + 0.20 * dim_b + 0.15 * dim_c +
        0.15 * dim_d + 0.10 * dim_e + 0.05 * dim_f + 0.05 * dim_g
    )

    warnings  = _generate_warnings(m, profile)
    strengths = _generate_strengths(m, profile)
    suit      = _suitability_profile(m, profile)
    verdict   = _verdict(composite, warnings, profile)
    confidence = _confidence_level(fund_age_years, nav_count)

    return {
        'scheme_code':    scheme_code,
        'scheme_name':    meta.get('scheme_name', ''),
        'amc_name':       meta.get('amc_name', ''),
        'sebi_category':  cat,
        'sebi_sub_category': meta.get('sebi_sub_category', ''),
        'plan_type':      meta.get('plan_type', ''),
        'inception_date': str(meta['inception_date']) if meta.get('inception_date') else None,
        'data_from':      str(first_date),
        'data_to':        str(last_date),
        'fund_age_years': fund_age_years,
        'nav_count':      nav_count,
        'composite_score': composite,
        'confidence':     confidence,
        'dimensions': {
            'structural_quality':    {'score': dim_a, 'label': 'Structural Quality',       'weight': 30},
            'downside_protection':   {'score': dim_b, 'label': 'Downside Protection',       'weight': 20},
            'risk_profile':          {'score': dim_c, 'label': 'Risk Profile',              'weight': 15},
            'consistency':           {'score': dim_d, 'label': 'Consistency & Track Record','weight': 15},
            'cost_efficiency':       {'score': dim_e, 'label': 'Cost Efficiency',           'weight': 10},
            'category_opportunity':  {'score': dim_f, 'label': 'Category Opportunity',      'weight':  5},
            'suitability':           {'score': dim_g, 'label': 'Investor Suitability',      'weight':  5},
        },
        'raw_metrics': {
            k: v for k, v in m.items()
            if k not in ('sebi_category', 'rolling_3yr', 'rolling_5yr')
        },
        'rolling_stats': {
            '3yr': rolling_3yr,
            '5yr': rolling_5yr,
        },
        'strengths':  strengths,
        'warnings':   warnings,
        'suitability': suit,
        'verdict':    verdict,
        'category_profile': {
            'typical_volatility':   profile['vol'],
            'typical_max_drawdown': -profile['max_dd'],
            'risk_level':           profile['risk'],
            'peer_cagr_5yr':        profile['peer_cagr_5yr'],
        },
    }
