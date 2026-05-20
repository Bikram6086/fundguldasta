"""
FUNDGULDASTA — VERIFIED SCHEME CODES
======================================
All scheme codes verified against AMFI database.
NAV history confirmed for each fund.
Last verified: May 2026

These are the ONLY scheme codes used in bouquet construction.
Any change here propagates through the entire engine.
"""

# ── BOUQUET FUND UNIVERSE ────────────────────────────────────
# All funds verified as Direct Growth plans with full history

VERIFIED_FUNDS = {

    # LARGE CAP
    '118825': {
        'name': 'Mirae Asset Large Cap Fund',
        'category': 'Large Cap',
        'amc': 'Mirae Asset',
        'nav_records': 3289,
        'tier': 1,
    },
    '120152': {
        'name': 'Kotak Large Cap Fund',
        'category': 'Large Cap',
        'amc': 'Kotak AMC',
        'nav_records': 3288,
        'tier': 1,
    },

    # LARGE & MID CAP
    '118834': {
        'name': 'Mirae Asset Large & Midcap Fund',
        'category': 'Large & Mid Cap',
        'amc': 'Mirae Asset',
        'nav_records': 3288,
        'tier': 1,
        'note': 'Previously known as Mirae Asset Emerging Bluechip — renamed 2018',
    },

    # FLEXI CAP
    '122639': {
        'name': 'Parag Parikh Flexi Cap Fund',
        'category': 'Flexi Cap',
        'amc': 'PPFAS AMC',
        'nav_records': 3189,
        'tier': 1,
    },
    '118955': {
        'name': 'HDFC Flexi Cap Fund',
        'category': 'Flexi Cap',
        'amc': 'HDFC AMC',
        'nav_records': 3290,
        'tier': 1,
    },

    # MID CAP
    '120505': {
        'name': 'Axis Midcap Fund',
        'category': 'Mid Cap',
        'amc': 'Axis AMC',
        'nav_records': 3296,
        'tier': 1,
    },
    '119071': {
        'name': 'DSP Midcap Fund',
        'category': 'Mid Cap',
        'amc': 'DSP AMC',
        'nav_records': 3290,
        'tier': 1,
    },
    '118989': {
        'name': 'HDFC Mid Cap Fund',
        'category': 'Mid Cap',
        'amc': 'HDFC AMC',
        'nav_records': 3290,
        'tier': 1,
    },

    # SMALL CAP
    '118778': {
        'name': 'Nippon India Small Cap Fund',
        'category': 'Small Cap',
        'amc': 'Nippon India',
        'nav_records': 3288,
        'tier': 1,
    },
    '120828': {
        'name': 'Quant Small Cap Fund',
        'category': 'Small Cap',
        'amc': 'Quant AMC',
        'nav_records': 3288,
        'tier': 1,
        'note': 'Quantitative investment approach — differentiates from other small caps',
    },

    # BALANCED ADVANTAGE
    '149134': {
        'name': 'SBI Balanced Advantage Fund',
        'category': 'Balanced Advantage',
        'amc': 'SBI MF',
        'nav_records': 1161,
        'tier': 2,
    },

    # INTERNATIONAL
    '145552': {
        'name': 'Motilal Oswal Nasdaq 100 FOF',
        'category': 'International',
        'amc': 'Motilal Oswal',
        'nav_records': 1835,
        'tier': 2,
        'tax_note': 'Taxed as debt fund — income slab rate applies regardless of holding period',
    },

    # SECTORAL
    '135800': {
        'name': 'Tata Digital India Fund',
        'category': 'Sectoral-Technology',
        'amc': 'Tata AMC',
        'nav_records': 2555,
        'tier': 2,
    },
}

# ── ARCHETYPE COMPOSITIONS ───────────────────────────────────
# Verified fund combinations per archetype
# All scheme codes confirmed correct

ARCHETYPE_FUNDS = {
    'steady': [
        ('118825', 25),   # Mirae Asset Large Cap
        ('122639', 25),   # Parag Parikh Flexi Cap
        ('120152', 20),   # Kotak Large Cap
        ('149134', 15),   # SBI Balanced Advantage
        ('118955', 15),   # HDFC Flexi Cap
    ],
    'balanced': [
        ('118825', 20),   # Mirae Asset Large Cap
        ('122639', 20),   # Parag Parikh Flexi Cap
        ('120505', 25),   # Axis Midcap
        ('118778', 20),   # Nippon India Small Cap
        ('145552', 15),   # Motilal Oswal Nasdaq 100
    ],
    'aggressive': [
        ('118989', 25),   # HDFC Mid Cap
        ('118778', 20),   # Nippon India Small Cap
        ('119071', 20),   # DSP Midcap
        ('120505', 20),   # Axis Midcap
        ('120828', 15),   # Quant Small Cap
    ],
    'conviction': [
        ('118778', 30),   # Nippon India Small Cap
        ('118989', 25),   # HDFC Mid Cap
        ('120828', 20),   # Quant Small Cap
        ('118834', 15),   # Mirae Asset Large & Midcap
        ('135800', 10),   # Tata Digital India
    ],
}

# ── BENCHMARK CODES ──────────────────────────────────────────
BENCHMARKS = {
    'NIFTY50':     'Nifty 50',
    'NIFTY500':    'Nifty 500',
    'NIFTYMID150': 'Nifty Midcap 150',
}
