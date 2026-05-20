"""
FUNDGULDASTA — ALGORITHM THRESHOLDS
=====================================
Calibrated specifically for the Indian MF market.

Key insight from correlation analysis (May 2026):
Indian domestic equity funds correlate at 0.85-0.98 with each other.
This is a structural characteristic of the Indian market — most funds
hold the same large cap stocks in their top positions.

Global diversification theory (correlation < 0.85) does not apply
directly to Indian domestic equity fund selection.

True diversification in Indian bouquets comes from:
1. International fund allocation (correlation ~0.35 with Indian equity)
2. Sectoral funds with different macro drivers (correlation ~0.60)
3. Category spread for different return profiles
4. Balanced Advantage funds with equity hedging

Our approach:
- Show correlation data transparently to users
- Flag genuinely redundant pairs (>0.95 — essentially same portfolio)
- Use category diversity as the primary hard constraint
- Treat international allocation as the true diversifier
"""

# Correlation thresholds
CORRELATION_HARD_REJECT = 0.95    # Funds with this correlation are essentially identical
CORRELATION_WARNING = 0.85        # Flag for user awareness — shown in UI
CORRELATION_GOOD = 0.70           # Below this is considered genuinely diversified

# Overlap thresholds
MAX_HOLDING_OVERLAP = 0.25        # 25% maximum stock overlap between any pair

# AUM thresholds
MIN_AUM_CRORES = 500

# Expense ratio ceiling
MAX_EXPENSE_RATIO = 1.5

# Evidence tier NAV record thresholds
TIER_1_MIN_RECORDS = 1750         # ~7 years daily NAV
TIER_2_MIN_RECORDS = 1250         # ~5 years daily NAV
TIER_3_MIN_RECORDS = 750          # ~3 years daily NAV

# Bouquet construction
MAX_FUNDS_PER_AMC = 2
MIN_BOUQUET_FUNDS = 5
MAX_BOUQUET_FUNDS = 5

# Confidence score thresholds
CONFIDENCE_HIGH = 70
CONFIDENCE_MEDIUM_HIGH = 55
CONFIDENCE_MEDIUM = 40
CONFIDENCE_LOW_MEDIUM = 25

# Rolling return periods to compute
ROLLING_HORIZONS = [3, 5, 7, 10, 15]

# Inflation assumption for real CAGR
INFLATION_ASSUMPTION = 6.0

# LTCG tax rate for post-tax CAGR
LTCG_RATE = 0.125

# Risk-free rate for Sharpe/Sortino
RISK_FREE_RATE = 6.5

# Crash periods for stress testing
CRASH_PERIODS = [
    {'name': '2008 Global Crisis',    'peak': '2008-01-08', 'trough': '2009-03-09'},
    {'name': '2015-16 Slowdown',      'peak': '2015-03-03', 'trough': '2016-02-29'},
    {'name': '2020 COVID Crash',      'peak': '2020-01-14', 'trough': '2020-03-23'},
    {'name': '2022 Rate Hike Selloff','peak': '2021-10-19', 'trough': '2022-06-17'},
]
