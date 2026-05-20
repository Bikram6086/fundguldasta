# FundGuldasta

**Mutual Fund Research. Unfiltered.**

Indian mutual fund research and education platform. Research/education only — not investment advice.

## What it does

User inputs a CAGR target + horizon (or corpus target, or SIP capacity). Platform returns 4 bouquet archetypes (Steady Compounder, Balanced Growther, Aggressive Achiever, High Conviction) with full transparency: composition, performance metrics, confidence score, stress tests across 4 historical crashes, overlap analysis, devil's advocate section, and benchmark comparisons.

**Non-negotiable principles:** Direct plans only. No commission. Honest about uncertainty. User has full agency — platform advises, never overrides.

## Stack

- **Backend:** FastAPI (Python 3.14) on port 8000
- **Database:** PostgreSQL 18.3 + TimescaleDB (~877K NAV records, 14K funds, 20 years)
- **Frontend:** React 18 SPA on port 3000

## Running locally (WSL2)

Three terminals required:

**Terminal 1 — API:**
```
cd ~/fundguldasta && source venv/bin/activate
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```
cd ~/fundguldasta/frontend/fundguldasta-ui && npm start
```

**Terminal 3 — scripts/commands:**
```
cd ~/fundguldasta && source venv/bin/activate
```

Open http://localhost:3000

## Populating the cache

The API reads only from `bouquet_cache` — never triggers live computation per request. Run precomputation for each horizon/CAGR combo needed:

```
python3 -c "from engine.precompute import run_precomputation; run_precomputation(horizon_years=7, target_cagr=16)"
python3 -c "from engine.precompute import run_all_horizons"  # pre-warms 3,5,7,10,15 yr
```

## Project structure

```
config/
  scheme_codes.py        # verified scheme codes + archetype compositions
  thresholds.py          # algorithm thresholds calibrated for Indian MF market
  .env                   # DB connection (not committed)
data/                    # ingestion pipelines: AMFI, NAV, benchmarks, managers
engine/
  eligibility_filter.py  # Layer 1: direct plan filter, AUM, expense ratio, tier
  fund_scorer.py         # Layer 2: 6-dimension scoring
  bouquet_builder.py     # Layer 3: correlation matrix + bouquet assembly
  confidence_scorer.py   # Layer 4: 5-factor confidence scoring
  precompute.py          # Layer 5: nightly cache writer
  cagr_advisor.py        # CAGR realism assessment by horizon
  fund_replacement.py    # User fund substitution + impact calculation
api/main.py              # FastAPI app — reads from cache, never live computation
frontend/                # React 18 single-file SPA (src/App.js)
docs/schema.sql          # PostgreSQL schema (9 tables)
tests/                   # pytest suite
```

## Database setup

PostgreSQL 18.3 + TimescaleDB. Trust auth for local dev:
- DB: `fundguldasta_dev`, User: `fundguldasta_user`
- `/etc/postgresql/18/main/pg_hba.conf`: `host all all 127.0.0.1/32 trust`

## Deployment targets

- Frontend: Vercel (auto-deploy from GitHub)
- Backend: Railway or Render
- Database: Supabase
- Domain: fundguldasta.com (GoDaddy)
