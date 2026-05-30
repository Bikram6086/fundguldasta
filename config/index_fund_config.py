# Curated index fund universe for comparison screen.
# AUM/ER: approximate values from AMC websites, May 2026. Recheck quarterly.
# Only direct growth plans with >= 100 NAV records are included.

INDEX_GROUPS = [
    {
        'group_id':       'nifty50',
        'group_name':     'Nifty 50',
        'benchmark_code': 'NIFTY50',
        'benchmark_name': 'Nifty 50',
        'funds': [
            {'scheme_code': '119827', 'name': 'SBI Nifty 50',        'amc': 'SBI MF',     'aum_cr': 7200,  'er': 0.19},
            {'scheme_code': '120716', 'name': 'UTI Nifty 50',        'amc': 'UTI MF',     'aum_cr': 22000, 'er': 0.20},
            {'scheme_code': '148978', 'name': 'Kotak Nifty 50',      'amc': 'Kotak MF',   'aum_cr': 5800,  'er': 0.20},
            {'scheme_code': '118741', 'name': 'Nippon Nifty 50',     'amc': 'Nippon MF',  'aum_cr': 12000, 'er': 0.20},
            {'scheme_code': '119648', 'name': 'ABSL Nifty 50',       'amc': 'ABSL MF',    'aum_cr': 1800,  'er': 0.20},
            {'scheme_code': '118482', 'name': 'Bandhan Nifty 50',    'amc': 'Bandhan MF', 'aum_cr': 1100,  'er': 0.10},
            {'scheme_code': '118581', 'name': 'Franklin Nifty 50',   'amc': 'Franklin MF','aum_cr': 2400,  'er': 0.20},
            {'scheme_code': '146376', 'name': 'DSP Nifty 50',        'amc': 'DSP MF',     'aum_cr': 680,   'er': 0.20},
            {'scheme_code': '147794', 'name': 'Motilal Nifty 50',    'amc': 'Motilal MF', 'aum_cr': 1700,  'er': 0.20},
        ],
    },
    {
        'group_id':       'niftynxt50',
        'group_name':     'Nifty Next 50',
        'benchmark_code': 'NIFTYNXT50',
        'benchmark_name': 'Nifty Next 50',
        'funds': [
            {'scheme_code': '120684', 'name': 'ICICI Nifty Next 50',  'amc': 'ICICI Pru', 'aum_cr': 4200,  'er': 0.36},
            {'scheme_code': '143341', 'name': 'UTI Nifty Next 50',    'amc': 'UTI MF',    'aum_cr': 3100,  'er': 0.31},
            {'scheme_code': '146381', 'name': 'DSP Nifty Next 50',    'amc': 'DSP MF',    'aum_cr': 600,   'er': 0.28},
            {'scheme_code': '146513', 'name': 'Nippon Nxt50 FoF',     'amc': 'Nippon MF', 'aum_cr': 1800,  'er': 0.19},
            {'scheme_code': '148945', 'name': 'SBI Nifty Next 50',    'amc': 'SBI MF',    'aum_cr': 1100,  'er': 0.30},
            {'scheme_code': '149288', 'name': 'HDFC Nifty Next 50',   'amc': 'HDFC MF',   'aum_cr': 900,   'er': 0.30},
        ],
    },
    {
        'group_id':       'niftymid150',
        'group_name':     'Nifty Midcap 150',
        'benchmark_code': 'NIFTYMID150',
        'benchmark_name': 'Nifty Midcap 150',
        'funds': [
            {'scheme_code': '148726', 'name': 'Nippon Nifty Midcap 150',  'amc': 'Nippon MF', 'aum_cr': 3100, 'er': 0.30},
            {'scheme_code': '148807', 'name': 'ABSL Nifty Midcap 150',    'amc': 'ABSL MF',   'aum_cr': 2200, 'er': 0.35},
            {'scheme_code': '149389', 'name': 'ICICI Nifty Midcap 150',   'amc': 'ICICI Pru', 'aum_cr': 1800, 'er': 0.36},
            {'scheme_code': '150673', 'name': 'SBI Nifty Midcap 150',     'amc': 'SBI MF',    'aum_cr': 900,  'er': 0.35},
            {'scheme_code': '151724', 'name': 'HDFC Nifty Midcap 150',    'amc': 'HDFC MF',   'aum_cr': 600,  'er': 0.35},
        ],
    },
    {
        'group_id':       'sensex',
        'group_name':     'BSE Sensex',
        'benchmark_code': 'SENSEX',
        'benchmark_name': 'BSE Sensex',
        'funds': [
            {'scheme_code': '120308', 'name': 'LIC MF Sensex',    'amc': 'LIC MF',   'aum_cr': 500,  'er': 0.20},
            {'scheme_code': '149803', 'name': 'UTI Sensex',       'amc': 'UTI MF',   'aum_cr': 1200, 'er': 0.20},
            {'scheme_code': '151769', 'name': 'SBI Sensex',       'amc': 'SBI MF',   'aum_cr': 800,  'er': 0.20},
        ],
    },
]

AUM_DATA_NOTE = "approx May 2026"
