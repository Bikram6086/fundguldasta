"""
FUNDGULDASTA — CAGR REALISM ADVISOR
=====================================
Assesses CAGR targets and investment horizons against Indian equity MF
historical data (2001-2026, Nifty 500 TRI rolling return analysis).

Platform principle: always compute results, never block the user.
This module provides honest education. User has full agency.
"""

# Bands: (realistic_lo, realistic_hi, aggressive_lo, aggressive_hi)
# realistic = achieved in 60%+ of rolling windows historically
# aggressive = achieved in 20-40% of windows (requires bull-favourable timing)
REALISTIC_BANDS = {
    1:  (0,  12, 12, 25),
    2:  (4,  13, 13, 22),
    3:  (8,  14, 15, 18),
    4:  (9,  14, 15, 18),
    5:  (10, 15, 16, 19),
    6:  (11, 15, 16, 19),
    7:  (12, 16, 17, 20),
    8:  (12, 16, 17, 20),
    10: (13, 17, 18, 21),
    12: (13, 17, 18, 21),
    15: (13, 18, 19, 22),
    20: (13, 18, 19, 22),
    25: (13, 18, 19, 22),
    30: (13, 18, 19, 22),
}

# level: unsuitable | caution | acceptable | good | ideal
HORIZON_SUITABILITY = {
    1:  ('unsuitable',
         "1-year horizon: Equity MFs are not appropriate. Markets can fall 40-60% in a single year with no time to recover. "
         "For a 1-year goal, use liquid funds or short-term debt funds."),
    2:  ('unsuitable',
         "2-year horizon: Equity MFs carry high risk at this timeframe. A bear market starting now could leave your corpus down 30-50% at the 2-year mark. "
         "Consider short-term debt funds. Equity only if you can extend to 5+ years when needed."),
    3:  ('caution',
         "3-year horizon: Below the recommended minimum for equity. Indian equity MFs delivered negative returns in roughly 15% of 3-year windows since 2001. "
         "This can work in favourable markets — but ensure you can stay invested longer if markets disappoint."),
    4:  ('caution',
         "4-year horizon: Short for equity. Around 10% of 4-year rolling windows in the last 25 years delivered negative or flat returns. "
         "Acceptable if you have the flexibility to extend by 1-2 years in a downturn."),
    5:  ('acceptable',
         "5-year horizon: Acceptable for equity. Positive real returns in approximately 90% of 5-year windows historically. "
         "Most bear markets are survivable within this timeframe."),
    6:  ('acceptable',
         "6-year horizon: Good for equity. Positive real returns in ~93% of 6-year rolling windows since 2001."),
    7:  ('good',
         "7-year horizon: Solid equity horizon. Time is your most powerful asset — most bear markets recover within 3-5 years."),
    8:  ('good',
         "8-year horizon: Strong equity horizon. All 8-year rolling windows in the last 25 years delivered positive real returns."),
    10: ('good',
         "10-year horizon: Strong equity horizon. In every 10-year window since 2001, Indian equity MFs delivered positive real returns."),
    12: ('ideal',
         "12-year horizon: Excellent equity horizon. Compounding begins to work powerfully at this timescale."),
    15: ('ideal',
         "15-year horizon: Ideal equity horizon. Stay invested through volatility — time eliminates short-term risk entirely."),
    20: ('ideal',
         "20-year horizon: Excellent. 20-year equity investors in India have never experienced negative real returns. Volatility becomes irrelevant."),
    25: ('ideal',
         "25-year horizon: Maximum compounding territory. Discipline and low cost matter more than timing at this scale."),
    30: ('ideal',
         "30-year horizon: Exceptional compounding horizon. Note: Indian equity MF data covers ~25 years — 30-year projections are forward extrapolations. Expense ratios and rebalancing discipline matter more than fund selection at this scale."),
}

# Approximate historical probability (%) of achieving ≥ given CAGR over that horizon
# Based on Nifty 500 TRI rolling windows 2001-2026
ACHIEVEMENT_PROB = {
    3:  {7: 88, 8: 80, 10: 65, 12: 50, 14: 36, 16: 24, 18: 14, 20: 8,  22: 4,  25: 1},
    5:  {7: 95, 8: 92, 10: 82, 12: 70, 14: 54, 16: 37, 18: 21, 20: 11, 22: 5,  25: 1},
    7:  {7: 99, 8: 97, 10: 92, 12: 82, 14: 65, 16: 46, 18: 27, 20: 13, 22: 6,  25: 2},
    10: {7: 100, 8: 99, 10: 97, 12: 90, 14: 75, 16: 54, 18: 30, 20: 15, 22: 7, 25: 2},
    15: {7: 100, 8: 100, 10: 99, 12: 96, 14: 85, 16: 63, 18: 38, 20: 19, 22: 9, 25: 3},
    20: {7: 100, 8: 100, 10: 100, 12: 98, 14: 90, 16: 70, 18: 46, 20: 24, 22: 11, 25: 4},
    25: {7: 100, 8: 100, 10: 100, 12: 99, 14: 93, 16: 75, 18: 52, 20: 28, 22: 13, 25: 5},
    30: {7: 100, 8: 100, 10: 100, 12: 99, 14: 94, 16: 77, 18: 54, 20: 30, 22: 14, 25: 6},
}


def _closest_horizon(horizon_years: int) -> int:
    keys = sorted(REALISTIC_BANDS.keys())
    return min(keys, key=lambda k: abs(k - horizon_years))


def _get_probability(target_cagr: float, horizon_years: int) -> int | None:
    prob_keys = sorted(ACHIEVEMENT_PROB.keys())
    h = min(prob_keys, key=lambda k: abs(k - int(round(horizon_years))))
    prob_map = ACHIEVEMENT_PROB.get(h)
    if not prob_map:
        return None
    cagr_int = int(round(target_cagr))
    thresholds = sorted(prob_map.keys())
    closest_t = min(thresholds, key=lambda t: abs(t - cagr_int))
    return prob_map[closest_t]


def get_horizon_suitability(horizon_years: float) -> dict:
    h = _closest_horizon(int(round(horizon_years)))
    level, message = HORIZON_SUITABILITY[h]
    return {'level': level, 'message': message, 'horizon_used': h}


def corpus_comparison(horizon_years: float, target_cagr: float, lumpsum: float = 1_000_000) -> dict:
    h = _closest_horizon(int(round(horizon_years)))
    real_lo, real_hi, _, _ = REALISTIC_BANDS[h]
    realistic_mid = round((real_lo + real_hi) / 2, 1)
    fd_rate = 7.0
    yrs = float(horizon_years)

    def grow(cagr):
        return round(lumpsum * ((1 + cagr / 100) ** yrs))

    return {
        'lumpsum': int(lumpsum),
        'horizon_years': yrs,
        'fd_corpus': grow(fd_rate),
        'realistic_corpus': grow(realistic_mid),
        'target_corpus': grow(target_cagr),
        'fd_cagr': fd_rate,
        'realistic_cagr': realistic_mid,
        'target_cagr': float(target_cagr),
    }


def assess_realism(target_cagr: float, horizon_years: float) -> dict:
    """
    Assess whether target_cagr is realistic for horizon_years.
    Always returns actionable data — never blocks computation.
    """
    h = _closest_horizon(int(round(horizon_years)))
    real_lo, real_hi, agg_lo, agg_hi = REALISTIC_BANDS[h]
    cagr = float(target_cagr)
    yrs = float(horizon_years)

    probability = _get_probability(cagr, yrs)
    horizon_suitability = get_horizon_suitability(yrs)
    corpus = corpus_comparison(yrs, cagr)

    if cagr < 7:
        category = "below_fd"
        message = (
            f"{cagr:.0f}% CAGR over {yrs:.0f} years is below what bank FDs currently offer (~7%). "
            f"Taking equity MF risk for this return level is generally not recommended. "
            f"Consider debt funds or FDs instead. Realistic equity range for {yrs:.0f} years: {real_lo}–{real_hi}%."
        )
    elif cagr < real_lo:
        category = "below_realistic"
        message = (
            f"{cagr:.0f}% CAGR over {yrs:.0f} years is below the typical equity MF return range ({real_lo}–{real_hi}%) for this horizon. "
            f"Equity MFs are likely to outperform your target — consider whether debt funds at lower risk might suit your goal better. "
            f"Historical probability of achieving at least {cagr:.0f}%: ~{probability}%."
        )
    elif cagr <= real_hi:
        category = "realistic"
        message = (
            f"{cagr:.0f}% CAGR over {yrs:.0f} years is within the historically achievable range "
            f"({real_lo}–{real_hi}%) for diversified Indian equity MF bouquets. "
            f"Based on 25-year rolling data, probability of achieving this: ~{probability}%."
        )
    elif cagr <= agg_hi:
        category = "aggressive"
        message = (
            f"{cagr:.0f}% CAGR over {yrs:.0f} years is in the aggressive range. "
            f"This has been achieved in strong bull market cycles, but is not consistently reliable. "
            f"Realistic range for {yrs:.0f} years: {real_lo}–{real_hi}%. "
            f"Historical probability of achieving {cagr:.0f}%+: ~{probability}%. "
            f"Results are shown — treat this as an optimistic scenario."
        )
    else:
        category = "unrealistic"
        message = (
            f"{cagr:.0f}% CAGR over {yrs:.0f} years is historically unrealistic for any diversified Indian equity MF bouquet. "
            f"The realistic range is {real_lo}–{real_hi}%. Even in the best bull markets, {agg_lo}–{agg_hi}% represents the upper boundary. "
            f"Historical probability of achieving {cagr:.0f}%+: ~{probability}%. "
            f"Results are shown for research purposes. Confidence scores will reflect this."
        )

    return {
        'category': category,
        'message': message,
        'realistic_range': [real_lo, real_hi],
        'aggressive_range': [agg_lo, agg_hi],
        'probability': probability,
        'horizon_used': h,
        'corpus_comparison': corpus,
        'horizon_suitability': horizon_suitability,
    }
