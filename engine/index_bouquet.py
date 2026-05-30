"""
FUNDGULDASTA — INDEX BOUQUET ENGINE
Curated passive bouquets using verified low-cost index funds.
Fund selection criteria: TER (50%) + history/AUM proxy (30%) + inception age (20%).
TER values hardcoded from AMFI (May 2026) — change rarely.
"""
import psycopg2
from datetime import date, timedelta
from config.db import get_db_config

DB_CONFIG = get_db_config()

# Verified scheme codes with known TERs (AMFI, May 2026)
INDEX_FUNDS = {
    'nifty50': {
        'scheme_code': '120716',
        'name': 'UTI Nifty 50 Index Fund',
        'short_name': 'UTI Nifty 50',
        'index': 'Nifty 50',
        'ter': 0.17,
        'fund_house': 'UTI',
        'category': 'Large Cap',
    },
    'niftynext50': {
        'scheme_code': '120684',
        'name': 'ICICI Prudential Nifty Next 50 Index Fund',
        'short_name': 'ICICI Nifty Next 50',
        'index': 'Nifty Next 50',
        'ter': 0.27,
        'fund_house': 'ICICI Prudential',
        'category': 'Large Cap Extended',
    },
    'midcap150': {
        'scheme_code': '148726',
        'name': 'Nippon India Nifty Midcap 150 Index Fund',
        'short_name': 'Nippon Midcap 150',
        'index': 'Nifty Midcap 150',
        'ter': 0.32,
        'fund_house': 'Nippon India',
        'category': 'Mid Cap',
    },
    'smallcap250': {
        'scheme_code': '148519',
        'name': 'Nippon India Nifty Smallcap 250 Index Fund',
        'short_name': 'Nippon Smallcap 250',
        'index': 'Nifty Smallcap 250',
        'ter': 0.38,
        'fund_house': 'Nippon India',
        'category': 'Small Cap',
    },
    'nasdaq100': {
        'scheme_code': '145552',
        'name': 'Motilal Oswal Nasdaq 100 Fund of Fund',
        'short_name': 'Motilal Nasdaq 100',
        'index': 'Nasdaq 100',
        'ter': 0.58,
        'fund_house': 'Motilal Oswal',
        'category': 'International',
    },
}

BOUQUET_DEFS = [
    {
        'id': 'index_simple',
        'name': 'Simple 2-Fund',
        'subtitle': 'The least complicated path to market returns',
        'horizon_label': '7yr+',
        'horizon_min': 7,
        'type': 'simple',
        'color': '#27AE78',
        'rationale': (
            'Two funds. Full diversification. Nothing complicated to manage. '
            'UTI Nifty 50 captures India\'s 50 largest companies — approximately 75% of total '
            'market capitalisation — with a TER of just 0.17%. Motilal Nasdaq 100 adds global '
            'technology exposure with historically 0.33 correlation to Indian equity, providing '
            'genuine diversification. This portfolio requires one rebalance per year to maintain '
            '75/25. Most long-term investors need nothing more.'
        ),
        'drawdown_note': '~35–40% max drawdown in severe bear markets',
        'allocations': [
            {'slot': 'nifty50',   'weight': 75, 'role': 'India Core'},
            {'slot': 'nasdaq100', 'weight': 25, 'role': 'Global Technology'},
        ],
    },
    {
        'id': 'index_foundation',
        'name': 'Index Foundation',
        'subtitle': 'Large-cap stability with one international anchor',
        'horizon_label': '5–7yr',
        'horizon_min': 5,
        'type': 'detailed',
        'color': '#4A8FE0',
        'rationale': (
            'A 5–7 year horizon is too short for mid/small-cap index volatility — these segments '
            'can fall 50–60% and take 4–5 years to recover. Large-cap only, with Nifty Next 50 '
            'extending coverage to ranks 51–100 by market cap. Nasdaq 100 adds global diversification '
            'at 15% — enough to matter, not enough to destabilise.'
        ),
        'drawdown_note': '~25–35% max drawdown (large-cap dominant)',
        'allocations': [
            {'slot': 'nifty50',      'weight': 65, 'role': 'India Core'},
            {'slot': 'niftynext50',  'weight': 20, 'role': 'India Extended'},
            {'slot': 'nasdaq100',    'weight': 15, 'role': 'Global'},
        ],
    },
    {
        'id': 'index_balanced',
        'name': 'Index Balanced',
        'subtitle': 'Large-cap core, mid-cap growth, global anchor',
        'horizon_label': '7–10yr',
        'horizon_min': 7,
        'type': 'detailed',
        'color': '#27AE78',
        'rationale': (
            'At 7–10 years, mid-cap index exposure becomes appropriate — there is enough time to '
            'recover from the 40–50% drawdowns that mid-cap indices experience in bear markets. '
            'Nifty Midcap 150 replaces Nifty Next 50 as the growth engine. Nasdaq 100 is kept '
            'at 10% as a pure diversifier.'
        ),
        'drawdown_note': '~35–45% max drawdown',
        'allocations': [
            {'slot': 'nifty50',     'weight': 45, 'role': 'India Core'},
            {'slot': 'midcap150',   'weight': 30, 'role': 'India Mid-Cap'},
            {'slot': 'niftynext50', 'weight': 15, 'role': 'India Extended'},
            {'slot': 'nasdaq100',   'weight': 10, 'role': 'Global'},
        ],
    },
    {
        'id': 'index_growth',
        'name': 'Index Growth',
        'subtitle': 'Full market-cap spectrum, meaningful international',
        'horizon_label': '10–15yr',
        'horizon_min': 10,
        'type': 'detailed',
        'color': '#F0A500',
        'rationale': (
            '10+ years allows meaningful small-cap allocation. Nifty Smallcap 250 has delivered '
            'the highest long-run returns of any domestic index — at the cost of 50–60% drawdowns. '
            'Time is the risk manager at this horizon. Nasdaq 100 at 15% adds genuine global '
            'diversification that cannot be replicated by any domestic index.'
        ),
        'drawdown_note': '~45–55% max drawdown — requires unwavering discipline',
        'allocations': [
            {'slot': 'nifty50',    'weight': 35, 'role': 'India Core'},
            {'slot': 'midcap150',  'weight': 30, 'role': 'India Mid-Cap'},
            {'slot': 'smallcap250','weight': 20, 'role': 'India Small-Cap'},
            {'slot': 'nasdaq100',  'weight': 15, 'role': 'Global'},
        ],
    },
    {
        'id': 'index_longterm',
        'name': 'Index Long-Term',
        'subtitle': 'Maximum equity across all segments and geographies',
        'horizon_label': '15yr+',
        'horizon_min': 15,
        'type': 'detailed',
        'color': '#E05555',
        'rationale': (
            '15+ years is when compounding works at maximum power. Higher small-cap and international '
            'weights are justified — short-term volatility is irrelevant over this horizon. '
            'Expect 50–60% drawdowns in severe bear markets. This is not a concern at 15 years; '
            'it is an opportunity. The only risk at this scale is selling at the wrong time.'
        ),
        'drawdown_note': '~50–60% max drawdown · Only for investors with true long-term conviction',
        'allocations': [
            {'slot': 'nifty50',    'weight': 25, 'role': 'India Core'},
            {'slot': 'midcap150',  'weight': 30, 'role': 'India Mid-Cap'},
            {'slot': 'smallcap250','weight': 25, 'role': 'India Small-Cap'},
            {'slot': 'nasdaq100',  'weight': 20, 'role': 'Global'},
        ],
    },
]


def _compute_cagr(nav_rows, years):
    """CAGR from sorted (date, nav_value) list over `years` years back from latest."""
    if not nav_rows or len(nav_rows) < 50:
        return None
    latest_date, latest_nav = nav_rows[-1]
    target_date = latest_date - timedelta(days=int(years * 365.25))
    best = min(nav_rows, key=lambda r: abs((r[0] - target_date).days))
    if abs((best[0] - target_date).days) > 90:
        return None
    start_nav = float(best[1])
    if start_nav <= 0:
        return None
    return round(((float(latest_nav) / start_nav) ** (1.0 / years) - 1) * 100, 2)


def get_index_bouquets():
    """Return all index bouquets with fund-level performance data."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    codes = [f['scheme_code'] for f in INDEX_FUNDS.values()]
    cur.execute("""
        SELECT scheme_code, nav_date, nav_value
        FROM nav_data
        WHERE scheme_code = ANY(%s)
        ORDER BY scheme_code, nav_date
    """, (codes,))

    nav_by_code = {}
    for scheme_code, nav_date, nav_value in cur.fetchall():
        nav_by_code.setdefault(scheme_code, []).append((nav_date, nav_value))

    cur.close()
    conn.close()

    fund_details = {}
    for slot_key, fund in INDEX_FUNDS.items():
        rows = nav_by_code.get(fund['scheme_code'], [])
        fund_details[slot_key] = {
            **fund,
            'nav_count': len(rows),
            'inception': str(rows[0][0]) if rows else None,
            'latest_nav': float(rows[-1][1]) if rows else None,
            'cagr_1y': _compute_cagr(rows, 1),
            'cagr_3y': _compute_cagr(rows, 3),
            'cagr_5y': _compute_cagr(rows, 5),
        }

    bouquets = []
    for bdef in BOUQUET_DEFS:
        allocs = bdef['allocations']
        weighted_ter = round(
            sum(fund_details[a['slot']]['ter'] * a['weight'] / 100 for a in allocs), 3
        )

        def _weighted_cagr(yr_key):
            parts = [
                fund_details[a['slot']][yr_key] * a['weight'] / 100
                for a in allocs
                if fund_details[a['slot']][yr_key] is not None
            ]
            return round(sum(parts), 2) if len(parts) == len(allocs) else None

        funds_out = [
            {
                'slot_key': a['slot'],
                'role': a['role'],
                'weight': a['weight'],
                **{k: fund_details[a['slot']][k] for k in (
                    'scheme_code', 'name', 'short_name', 'index', 'ter',
                    'fund_house', 'category', 'nav_count', 'inception',
                    'latest_nav', 'cagr_1y', 'cagr_3y', 'cagr_5y'
                )},
            }
            for a in allocs
        ]

        bouquets.append({
            'id': bdef['id'],
            'name': bdef['name'],
            'subtitle': bdef['subtitle'],
            'horizon_label': bdef['horizon_label'],
            'horizon_min': bdef['horizon_min'],
            'type': bdef['type'],
            'color': bdef['color'],
            'rationale': bdef['rationale'],
            'drawdown_note': bdef['drawdown_note'],
            'funds': funds_out,
            'weighted_ter': weighted_ter,
            'composite_cagr_3y': _weighted_cagr('cagr_3y'),
            'composite_cagr_5y': _weighted_cagr('cagr_5y'),
        })

    return bouquets
