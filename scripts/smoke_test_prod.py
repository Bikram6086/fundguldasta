#!/usr/bin/env python3
"""
FundGuldasta — Production Smoke Test
=====================================
Hits the live Railway API to verify all critical endpoints are reachable
and returning expected data shapes. Run manually after any deployment.

Usage:
    python3 scripts/smoke_test_prod.py
    python3 scripts/smoke_test_prod.py --url https://custom.railway.app
"""
import sys, argparse
import requests

PROD_URL = "https://web-production-8f6bd.up.railway.app"

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

errors = []

def check(name, condition, detail=""):
    if condition:
        print(f"  {PASS}  {name}")
    else:
        print(f"  {FAIL}  {name}")
        if detail:
            print(f"       → {detail}")
        errors.append(name)

def get(path, timeout=15):
    try:
        r = requests.get(f"{PROD_URL}{path}", timeout=timeout)
        return r
    except Exception as e:
        return None

def post(path, body=None, timeout=15):
    try:
        r = requests.post(f"{PROD_URL}{path}", json=body or {}, timeout=timeout)
        return r
    except Exception as e:
        return None


def run_smoke_tests():
    print("\n══════════════════════════════════════════")
    print("  FundGuldasta Production Smoke Test")
    print(f"  Target: {PROD_URL}")
    print("══════════════════════════════════════════\n")

    # ── Health ───────────────────────────────────────────────────────────────
    print("[ Health ]")
    r = get("/health")
    check("GET /health returns 200", r and r.status_code == 200,
          f"status={r.status_code if r else 'no response'}")
    r2 = requests.head(f"{PROD_URL}/health", timeout=10) if r else None
    check("HEAD /health returns 200 (UptimeRobot-compatible)",
          r2 and r2.status_code == 200,
          f"status={r2.status_code if r2 else 'no response'} — UptimeRobot will show DOWN")

    # ── Stats ────────────────────────────────────────────────────────────────
    print("\n[ Stats ]")
    r = get("/api/stats")
    check("GET /api/stats returns 200", r and r.status_code == 200)
    if r and r.status_code == 200:
        d = r.json()
        nav_count = d.get("nav_records") or d.get("navRecords", 0)
        check("Stats has NAV count", nav_count is not None and nav_count > 0,
              f"keys: {list(d.keys())}")
        check("Stats NAV count > 500000", nav_count > 500000,
              f"nav_count={nav_count}")

    # ── Bouquet endpoints ────────────────────────────────────────────────────
    print("\n[ Bouquet Endpoints ]")
    for arch in ["steady", "balanced", "aggressive", "conviction"]:
        r = get(f"/api/bouquets/{arch}/metrics")
        check(f"GET /api/bouquets/{arch}/metrics → 200",
              r and r.status_code == 200,
              f"status={r.status_code if r else 'no response'}")

    r = post("/api/bouquets/curate", {"horizon_years": 7, "target_cagr": 16})
    check("POST /api/bouquets/curate → 200", r and r.status_code == 200,
          f"status={r.status_code if r else 'no response'}")
    if r and r.status_code == 200:
        d = r.json()
        check("Curate returns archetypes list", isinstance(d.get("archetypes"), list),
              f"keys: {list(d.keys())}")
        check("Curate returns ≥1 archetype", len(d.get("archetypes", [])) >= 1,
              "Empty archetypes — cache may be missing")

    # ── Fund search ──────────────────────────────────────────────────────────
    print("\n[ Fund Search ]")
    r = get("/api/funds/search?q=parag+parikh&limit=5")
    check("GET /api/funds/search returns 200", r and r.status_code == 200)
    if r and r.status_code == 200:
        d = r.json()
        funds = d if isinstance(d, list) else d.get("funds", [])
        check("Fund search returns results", len(funds) > 0,
              "No funds returned for 'parag parikh'")

    r = get("/api/funds/122639/detail")
    check("GET /api/funds/122639/detail → 200", r and r.status_code == 200,
          f"status={r.status_code if r else 'no response'}")

    # ── Pipeline status ──────────────────────────────────────────────────────
    print("\n[ Pipeline & Freshness ]")
    r = get("/api/pipeline/status")
    check("GET /api/pipeline/status returns 200", r and r.status_code == 200)

    r = get("/api/bouquets/steady/freshness")
    check("GET /api/bouquets/steady/freshness returns 200", r and r.status_code == 200)
    if r and r.status_code == 200:
        d = r.json()
        sources = d.get("sources", [])
        check("Freshness has sources", len(sources) > 0, "No sources in freshness response")
        for s in sources:
            if s.get("name") == "NAV & Return Data":
                check("NAV data not stale", s.get("status") != "error",
                      f"NAV status={s.get('status')}, lastUpdated={s.get('lastUpdated')}")
            if s.get("name") == "Benchmark Index Data":
                check("Benchmark data not stale", s.get("status") != "error",
                      f"Benchmark status={s.get('status')}, lastUpdated={s.get('lastUpdated')}")

    # ── Auth endpoints ───────────────────────────────────────────────────────
    print("\n[ Auth ]")
    r = get("/api/auth/me", timeout=25)
    check("GET /api/auth/me → 401 without token", r and r.status_code == 401,
          f"status={r.status_code if r else 'no response'} — auth guard not working")


def main():
    global PROD_URL
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=PROD_URL, help="Production API base URL")
    args = parser.parse_args()
    PROD_URL = args.url.rstrip("/")

    run_smoke_tests()

    print("\n══════════════════════════════════════════")
    if errors:
        print(f"  FAILED — {len(errors)} check(s) failed:")
        for e in errors:
            print(f"    ✗ {e}")
        sys.exit(1)
    else:
        print("  ALL SMOKE TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
