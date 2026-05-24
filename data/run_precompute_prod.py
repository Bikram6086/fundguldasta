"""Regenerate bouquet cache for production Timescale Cloud with new holdings data."""
import sys, os
sys.path.insert(0, '/home/hpbikram6086/fundguldasta')

tsdb_pass = os.getenv("TSDB_PASS", "")
if not tsdb_pass:
    print("ERROR: set TSDB_PASS"); sys.exit(1)

# Must set DATABASE_URL BEFORE importing engine modules (DB_CONFIG resolved at import time)
os.environ["DATABASE_URL"] = (
    f"postgres://tsdbadmin:{tsdb_pass}"
    "@oiwukb56wf.rfzjm4xx0h.tsdb.cloud.timescale.com:31740/tsdb?sslmode=require"
)

from engine.precompute import run_precomputation

horizons = [(5, 14), (7, 16), (10, 16)]
for h, c in horizons:
    print(f"\nPrecomputing {h}yr/{c}% CAGR...")
    try:
        run_precomputation(horizon_years=h, target_cagr=c)
        print(f"  ✓ Done: {h}yr")
    except Exception as e:
        print(f"  ✗ Error: {e}")

print("\nDone — bouquet cache updated with real overlap data.")
