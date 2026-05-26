from engine.precompute import run_precomputation
for h, c in [(5, 14), (7, 16), (10, 16), (15, 16), (20, 16), (30, 16)]:
    print(f"horizon={h} cagr={c}...")
    run_precomputation(horizon_years=h, target_cagr=c)
    print(f"  done")
print("All precompute runs complete.")
