# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## GitHub Repository

Remote: `https://github.com/Bikram6086/fundguldasta` (public)

**Auto-push policy:** After completing any meaningful set of changes (feature, fix, visual update, refactor), commit and push to GitHub without waiting for explicit instructions. Use clear commit messages. Push at minimum after every session and after any significant milestone.

---

## Project Overview

**FundGuldasta** — Indian mutual fund research and education platform. Tagline: "Mutual Fund Research. Unfiltered."

Research/education only. Never investment advice. Never guarantee returns. Direct plans only. No commission. User has full agency — platform educates but never overrides user choice.

The actual project lives in WSL2 at `~/fundguldasta/`. This Windows directory (`c:\Users\HP\Fund Guldasta`) is the Claude Code workspace pointing to it.

---

## Running the Platform

Three terminals required (all in WSL2):

**Terminal 1 — API server (FastAPI on port 8000):**
```bash
cd ~/fundguldasta && source venv/bin/activate
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — React frontend (port 3000):**
```bash
cd ~/fundguldasta/frontend/fundguldasta-ui && npm start
```

**Terminal 3 — Commands/scripts:**
```bash
cd ~/fundguldasta && source venv/bin/activate
```

Browser: http://localhost:3000

---

## Architecture

```
UI (React, port 3000)
  → apiCall() helper in App.js
  → FastAPI (port 8000)
  → bouquet_cache table in PostgreSQL
  → (cache populated nightly by engine/precompute.py)
```

Switching prototype → production: one flag change in `dataService.js`.

### Key paths in WSL2
| Path | Purpose |
|---|---|
| `~/fundguldasta/config/scheme_codes.py` | Verified scheme codes + archetype compositions |
| `~/fundguldasta/config/thresholds.py` | All algorithm thresholds (calibrated for Indian MF market) |
| `~/fundguldasta/config/.env` | Environment variables |
| `~/fundguldasta/engine/eligibility_filter.py` | Layer 1: Fund eligibility + tier classification |
| `~/fundguldasta/engine/fund_scorer.py` | Layer 2: 6-dimension scoring |
| `~/fundguldasta/engine/bouquet_builder.py` | Layer 3: Bouquet construction + correlation matrix |
| `~/fundguldasta/engine/confidence_scorer.py` | Layer 4: Confidence scoring (5 factors) |
| `~/fundguldasta/engine/precompute.py` | Layer 5: Pre-computation orchestrator (nightly job) |
| `~/fundguldasta/api/main.py` | FastAPI app — all endpoints |
| `~/fundguldasta/frontend/fundguldasta-ui/src/App.js` | React 18 SPA (single file, all components) |
| `~/fundguldasta/docs/schema.sql` | PostgreSQL schema |
| `~/fundguldasta/data/` | Data ingestion pipelines |

### Computation engine (5 layers)
1. **Eligibility Filter** — Direct plan, AUM ≥ ₹500Cr, expense ratio ≤ 1.5%, tier by NAV history length
2. **Fund Scorer** — Return Consistency 25%, Risk-Adjusted Quality 20%, Downside Behaviour 20%, Manager Stability 15%, Portfolio Quality 10%, Forward Context 10%
3. **Bouquet Builder** — Correlation matrix, weighted metrics, benchmark comparisons
4. **Confidence Scorer** — Rolling Consistency 30%, Downside Protection 20%, Manager Stability 20%, Category Tailwind 15%, Cost Efficiency 15%
5. **Precompute** — Writes to `bouquet_cache`; API reads only from cache, never triggers live computation

### API endpoints
```
GET  /health
POST /api/bouquets/curate              ← main endpoint, returns 4 archetypes
GET  /api/bouquets/{id}/metrics
GET  /api/bouquets/{id}/confidence
GET  /api/bouquets/{id}/stress-test
GET  /api/bouquets/{id}/overlap
GET  /api/bouquets/{id}/freshness
GET  /api/pipeline/status
GET  /api/stats
```

---

## Database

- PostgreSQL 18.3 + TimescaleDB
- DB: `fundguldasta_dev`, User: `fundguldasta_user`
- Auth: trust mode via TCP from localhost (no password for local dev)
- `/etc/postgresql/18/main/pg_hba.conf`: `host all all 127.0.0.1/32 trust`

**Current state:** 877,758 NAV records, 14,366 funds, 4 archetypes cached (7-year horizon)

**9 tables:** `fund_metadata`, `nav_data`, `fund_managers`, `manager_change_log`, `portfolio_holdings` (empty — parser not built), `benchmark_data`, `computed_metrics`, `bouquet_cache`, `pipeline_log`

**Schema note:** `fund_metadata.sebi_category` and `fund_type` are VARCHAR(200) (not 100 — increased during build).

Quick health check:
```bash
curl http://localhost:8000/api/stats
```

---

## Populating the Cache

The API only reads from `bouquet_cache`. Run precomputation for each horizon/CAGR combo needed:

```bash
cd ~/fundguldasta && source venv/bin/activate

# 5-year horizon
python3 -c "from engine.precompute import run_precomputation; run_precomputation(horizon_years=5, target_cagr=14)"

# 7-year horizon (already cached)
python3 -c "from engine.precompute import run_precomputation; run_precomputation(horizon_years=7, target_cagr=16)"

# 10-year horizon
python3 -c "from engine.precompute import run_precomputation; run_precomputation(horizon_years=10, target_cagr=16)"
```

---

## Verified Scheme Codes (do not change without DB verification)

| Code | Fund | Tier |
|---|---|---|
| 118825 | Mirae Asset Large Cap Fund | 1 |
| 120152 | Kotak Large Cap Fund | 1 |
| 118834 | Mirae Asset Large & Midcap Fund | 1 |
| 122639 | Parag Parikh Flexi Cap Fund | 1 |
| 118955 | HDFC Flexi Cap Fund | 1 |
| 120505 | Axis Midcap Fund | 1 |
| 119071 | DSP Midcap Fund | 1 |
| 118989 | HDFC Mid Cap Fund Growth | 1 |
| 118778 | Nippon India Small Cap Fund | 1 |
| 120828 | Quant Small Cap Fund | 1 |
| 149134 | SBI Balanced Advantage Fund | 2 |
| 145552 | Motilal Oswal Nasdaq 100 FOF | 2 |
| 135800 | Tata Digital India Fund | 2 |

Critical corrections: 119553 is a debt IDCW fund (not HDFC Flexi Cap). 118988 is IDCW (not HDFC Mid Cap Growth). "Kotak Equity Opportunities" scheme code doesn't exist — use 120152.

---

## Indian MF Correlation Reality

Indian equity funds correlate at **0.85–0.98** with each other. This is structural, not a bug. Genuine diversifiers:
- Motilal Nasdaq vs Indian equity: 0.33–0.37
- Tata Digital vs Indian equity: 0.59–0.66

Thresholds in `config/thresholds.py`: HARD_REJECT=0.95, WARNING=0.85. **Category diversity** is the primary bouquet construction constraint, not correlation.

---

## Frontend Design System

Dark gold-on-black aesthetic (intentional — financial gravitas). Fonts: Cormorant Garamond (headings), Outfit (body), JetBrains Mono (numbers). Color palette in `const G` at top of `App.js`. All UI is a single-file React SPA.

---

## Python Environment

- Python 3.14 in `~/fundguldasta/venv/`
- Key packages: `pandas numpy sqlalchemy psycopg2-binary requests pdfplumber fastapi uvicorn httpx pytest python-dotenv anthropic mftool yfinance`
- `engine/` and `data/` both have `__init__.py` (required for module imports)

---

## Priority 7 — Holistic Refinements (build before deployment)

Execute in order. Test each before moving to next.

### 7.1 — Flexible Horizon and CAGR Support

**Problem:** Platform only supports cached horizons and fails for any other value.

**Goal:** Accept ANY horizon (3–20 years) and ANY CAGR. Show advisory if unrealistic, but still compute — user has agency.

**Realistic CAGR bands (Indian equity MF historical data):**
```
3-year:   8-14% realistic   | 15-18% aggressive   | 19%+ unrealistic
5-year:   10-15% realistic  | 16-19% aggressive   | 20%+ unrealistic
7-year:   12-16% realistic  | 17-20% aggressive   | 21%+ unrealistic
10-year:  13-17% realistic  | 18-21% aggressive   | 22%+ unrealistic
15-year:  13-18% realistic  | 19-22% aggressive   | 23%+ unrealistic
```

**New file:** `engine/cagr_advisor.py`
- Function: `assess_realism(target_cagr, horizon_years)`
- Returns: `{'category': 'realistic|aggressive|unrealistic', 'message': '...', 'realistic_range': [low, high]}`

**`engine/precompute.py` changes:**
- Pre-cache horizons 3, 5, 7, 10, 15 on startup with default CAGR 16%
- Add on-demand computation path for non-cached horizons (cache result after first request)

**`api/main.py` changes:**
- `POST /api/bouquets/curate` accepts any horizon — return from cache or trigger on-demand (2-3s)
- Add `realisticAssessment` field to curate response

**Frontend changes:**
- Advisory banner (amber background) when CAGR is outside realistic range
- "Proceed anyway" option — never block the user

### 7.2 — Brand Prominence on Hero

**Specific changes to App.js hero section:**
- Brand mark: 46px → 72px, gold glow effect
- Brand name: 26px → 42px Cormorant Garamond
- Tagline "Mutual Fund Research. Unfiltered." → 18px italic gold, prominent below brand name
- Secondary tagline above headline: "India's First Honest-by-Design Mutual Fund Research Platform"
- Headline: `clamp(48px, 8vw, 84px)`
- Decorative element below tagline (thin gold line or three dots)

### 7.3 — Reorder Metrics Table Columns

**Current order:** Bouquet CAGR → Real CAGR → Post-Tax → Nifty → FD

**Required order:** Period → Bouquet CAGR → Post-Tax CAGR → Real CAGR → Nifty 50 → FD Rate → FD Real

Modify `<table className="mt">` in App.js only — backend already computes all values.

### 7.4 — User Fund Preference and Customization

**New file:** `engine/fund_replacement.py`
- Smart slot replacement: same-category first, else lowest-scoring fund
- Side-by-side comparison: composite score, rolling CAGR, Sortino, manager tenure, expense ratio, rolling consistency
- Impact calculation: recomputed CAGR, confidence score, corpus difference on ₹10L, correlation check

**New API endpoints in `api/main.py`:**
```
GET  /api/funds/search?q=<query>&limit=10        ← autocomplete by name/AMC/code
GET  /api/funds/{scheme_code}/score?horizon_years=7&target_cagr=16
POST /api/bouquets/customize                      ← body: {original_archetype, replacement_fund_code}
```

**New frontend section** (between Box 3 Composition and Box 4 Metrics):
- "Customize Bouquet" toggle → fund search input with dropdown
- Comparison view (all metrics side by side)
- Accept / Reject buttons
- "Customized" badge visible if substitution active

**Constraints:** Replacement must pass eligibility filter. Show Tier 3 warning. Recompute correlations and stress test for modified bouquet.

---

## Deferred Work

- `portfolio_holdings` table is empty — holdings parser not built; overlap shows 0%
- `fund_managers` has placeholder data — SID parser designed but not built; manager scores default to 40–45

---

## Roadmap After Priority 7

- **Priority 8 — Cloud Deployment:** Frontend → Vercel, Backend → Railway/Render, DB → Supabase; DNS for fundguldasta.com
- **Priority 9 — Monitoring:** UptimeRobot health checks, email alerts for pipeline failures, manager change detection
- **Priority 10 — User Features:** Accounts (email + password), saved bouquets, existing portfolio analyser, email alerts
- **Priority 11 — SEO Content:** Algorithm transparency, rolling returns explainer, survivorship bias, confidence score guide, why direct plans matter

---

## 4 Bouquet Archetypes

| Archetype | CAGR Target | Funds |
|---|---|---|
| Steady Compounder | 14–16% | 118825(25%), 122639(25%), 120152(20%), 149134(15%), 118955(15%) |
| Balanced Growther | 15–17% | 118825(20%), 122639(20%), 120505(25%), 118778(20%), 145552(15%) |
| Aggressive Achiever | 16–19% | 118989(25%), 118778(20%), 119071(20%), 120505(20%), 120828(15%) |
| High Conviction | 18–22% | 118778(30%), 118989(25%), 120828(20%), 118834(15%), 135800(10%) |
