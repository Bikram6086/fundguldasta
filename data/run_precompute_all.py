import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.precompute import run_precomputation

horizons = [(3, 14), (5, 14), (7, 16), (10, 16), (15, 16)]
for h, c in horizons:
    try:
        run_precomputation(horizon_years=h, target_cagr=c)
        print(f'Horizon {h}yr / CAGR {c}%: OK')
    except Exception as e:
        print(f'Horizon {h}yr / CAGR {c}%: FAILED — {e}')
