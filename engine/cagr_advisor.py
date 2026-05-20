"""
FUNDGULDASTA — CAGR REALISM ADVISOR
=====================================
Assesses whether a user-requested CAGR target is realistic for a given
investment horizon, based on Indian equity MF historical data (2006-2026).

Platform principle: always compute results regardless of realism — user has full
agency. This module only provides advisory context, never blocks computation.
"""

# Bands: (real_lo, real_hi, agg_lo, agg_hi)
# real = historically achievable with consistent fund selection
# agg  = possible in strong bull cycles, not reliable
REALISTIC_BANDS = {
    3:  (8,  14, 15, 18),
    5:  (10, 15, 16, 19),
    7:  (12, 16, 17, 20),
    10: (13, 17, 18, 21),
    15: (13, 18, 19, 22),
    20: (12, 17, 18, 21),
}


def _closest_horizon(horizon_years: int) -> int:
    """Map any horizon to the nearest band key."""
    keys = sorted(REALISTIC_BANDS.keys())
    return min(keys, key=lambda k: abs(k - horizon_years))


def assess_realism(target_cagr: float, horizon_years: int) -> dict:
    """
    Assess whether target_cagr is realistic for horizon_years.

    Returns dict with keys:
      category      — 'realistic' | 'aggressive' | 'unrealistic'
      message       — human-readable advisory string
      realistic_range — [lo, hi] of the realistic band
      aggressive_range — [lo, hi] of the aggressive band
    """
    h = _closest_horizon(int(round(horizon_years)))
    real_lo, real_hi, agg_lo, agg_hi = REALISTIC_BANDS[h]

    cagr = float(target_cagr)

    if cagr <= real_hi:
        category = "realistic"
        message = (
            f"{cagr:.0f}% CAGR over {horizon_years:.0f} years is within the historically "
            f"achievable range ({real_lo}–{real_hi}%) for diversified Indian equity MF bouquets."
        )
    elif cagr <= agg_hi:
        category = "aggressive"
        message = (
            f"{cagr:.0f}% CAGR over {horizon_years:.0f} years is in the aggressive range. "
            f"It has been achieved in strong bull cycles but is not consistently reliable. "
            f"Realistic range: {real_lo}–{real_hi}%. Expect medium-to-low confidence scores."
        )
    else:
        category = "unrealistic"
        message = (
            f"{cagr:.0f}% CAGR over {horizon_years:.0f} years is historically unrealistic "
            f"for any diversified Indian equity MF bouquet. "
            f"Realistic range: {real_lo}–{real_hi}%. Aggressive range: {agg_lo}–{agg_hi}%. "
            f"Confidence scores will be very low. You may proceed — results are shown for research."
        )

    return {
        "category": category,
        "message": message,
        "realistic_range": [real_lo, real_hi],
        "aggressive_range": [agg_lo, agg_hi],
        "horizon_used": h,
    }
