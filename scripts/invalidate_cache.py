#!/usr/bin/env python3
"""
FundGuldasta — Cache Invalidation Guard
========================================
Detects changes to engine/*.py files since the last cache build.
If any engine file changed, triggers a full cache recompute.

Run this:
  - After every git pull / code change
  - As a post-deploy step when on Railway
  - Manually: python3 scripts/invalidate_cache.py

Exit codes:
  0  — no changes detected, cache is valid
  0  — changes detected, recompute succeeded
  1  — changes detected, recompute failed
"""
import sys, os, hashlib, json
sys.path.insert(0, '/home/hpbikram6086/fundguldasta')

ENGINE_DIR  = '/home/hpbikram6086/fundguldasta/engine'
CONFIG_DIR  = '/home/hpbikram6086/fundguldasta/config'
HASH_FILE   = '/home/hpbikram6086/fundguldasta/.engine_hash'
HORIZONS    = [(7, 16)]  # extend to [(5,14),(7,16),(10,16)] when needed


def compute_engine_hash():
    """SHA-256 of all engine/*.py and config/scheme_codes.py + thresholds.py"""
    h = hashlib.sha256()
    files = sorted([
        os.path.join(ENGINE_DIR, f)
        for f in os.listdir(ENGINE_DIR)
        if f.endswith('.py') and not f.startswith('__')
    ]) + [
        os.path.join(CONFIG_DIR, 'scheme_codes.py'),
        os.path.join(CONFIG_DIR, 'thresholds.py'),
    ]
    for path in files:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                h.update(f.read())
    return h.hexdigest()


def load_stored_hash():
    if not os.path.exists(HASH_FILE):
        return None
    with open(HASH_FILE) as f:
        try:
            data = json.load(f)
            return data.get("hash")
        except Exception:
            return None


def save_hash(digest):
    import datetime
    with open(HASH_FILE, 'w') as f:
        json.dump({"hash": digest, "saved_at": str(datetime.datetime.now())}, f)


def recompute_all():
    from engine.precompute import run_precomputation
    failed = []
    for horizon, target in HORIZONS:
        print(f"  Recomputing horizon={horizon}yr target={target}%...")
        try:
            run_precomputation(horizon_years=horizon, target_cagr=target)
            print(f"  ✓ horizon={horizon}yr done")
        except Exception as e:
            print(f"  ✗ horizon={horizon}yr FAILED: {e}")
            failed.append((horizon, target, str(e)))
    return failed


def main():
    print("\n[ Cache Invalidation Check ]")
    current = compute_engine_hash()
    stored  = load_stored_hash()

    if stored == current:
        print(f"  ✓ Engine files unchanged (hash: {current[:12]}…) — cache valid")
        sys.exit(0)

    if stored is None:
        print(f"  ℹ No stored hash found — treating as first run")
    else:
        print(f"  ⚠ Engine files changed!")
        print(f"    stored:  {stored[:12]}…")
        print(f"    current: {current[:12]}…")

    print("  Triggering full cache recompute…")
    failed = recompute_all()

    if failed:
        print(f"\n  ✗ Recompute failed for {len(failed)} horizon(s):")
        for h, t, err in failed:
            print(f"    horizon={h} target={t}: {err}")
        sys.exit(1)
    else:
        save_hash(current)
        print(f"\n  ✓ Cache recomputed and hash updated ({current[:12]}…)")
        sys.exit(0)


if __name__ == "__main__":
    main()
