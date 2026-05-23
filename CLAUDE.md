# CLAUDE.md — FundGuldasta Canonical Reference

This file is the authoritative starting point for every Claude Code session. It reflects the complete current state of the platform after Priorities 1–17.

---

## GitHub Repository

Remote: `https://github.com/Bikram6086/fundguldasta` (public)

**Auto-push policy:** After any meaningful change (feature, fix, refactor), commit and push immediately. Do not wait for instructions. Use descriptive commit messages. The pre-push hook runs the full test suite — if it fails, fix it before pushing.

---

## Project

**FundGuldasta** — Indian mutual fund research and education platform.  
Tagline: *"Mutual Fund Research. Unfiltered."*

- Research and education only. Never investment advice. Never guarantee returns.
- Direct plans only. No commission. User has full agency — platform educates, never overrides.
- Domain: fundguldasta.com (not yet live — cloud deployment is next priority)

**WSL2 path:** `~/fundguldasta/`  
**Windows workspace:** `c:\Users\HP\Fund Guldasta` (holds only CLAUDE.md — all code is in WSL2)

---

## Running the Platform

Three WSL2 terminals required:

```bash
# Terminal 1 — API (port 8000)
cd ~/fundguldasta && source venv/bin/activate
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — React frontend (port 3000)
cd ~/fundguldasta/frontend/fundguldasta-ui && npm start

# Terminal 3 — scripts / DB / CLI
cd ~/fundguldasta && source venv/bin/activate
```

Browser: http://localhost:3000 | API health: http://localhost:8000/health

**IMPORTANT — PowerShell → WSL2 command pattern that works:**
```powershell
wsl -d Ubuntu -e bash -lc "cd /home/hpbikram6086/fundguldasta && source venv/bin/activate && <command>"
```
Use `-lc` (login shell) so the venv activates correctly. `-e bash -c` without `-l` loses the environment and fails silently.

---

## Architecture

```
React SPA (port 3000, App.js single file)
  → apiCall() / fetch()
  → FastAPI (port 8000, api/main.py)
  → PostgreSQL 18.3 + TimescaleDB (fundguldasta_dev)
      ↑ populated nightly by engine/precompute.py
```

### Key file paths (WSL2)

| Path | Purpose |
|---|---|
| `api/main.py` | FastAPI — all endpoints (~2300 lines) |
| `api/auth.py` | bcrypt password hash + JWT (direct bcrypt, NOT passlib) |
| `frontend/fundguldasta-ui/src/App.js` | React 18 SPA — single file, all components |
| `engine/eligibility_filter.py` | Layer 1: eligibility + tier classification |
| `engine/fund_scorer.py` | Layer 2: 6-dimension composite score |
| `engine/bouquet_builder.py` | Layer 3: bouquet construction + correlation |
| `engine/confidence_scorer.py` | Layer 4: confidence scoring (5 factors) |
| `engine/precompute.py` | Layer 5: nightly pre-computation orchestrator |
| `engine/cagr_advisor.py` | CAGR realism assessment (P7.1) |
| `engine/fund_replacement.py` | Fund substitution + impact calc (P7.4) |
| `engine/cas_parser.py` | CAS PDF parser — CAMS + KFintech (P16) |
| `config/scheme_codes.py` | Verified scheme codes + archetype compositions |
| `config/thresholds.py` | All algorithm thresholds (calibrated for Indian MF) |
| `config/.env` | Environment variables — **gitignored, never commit** |
| `docs/schema.sql` | PostgreSQL schema |
| `data/` | Data ingestion pipelines |
| `tests/` | 119 tests across multiple test files |

---

## Database

- PostgreSQL 18.3 + TimescaleDB
- DB: `fundguldasta_dev`, User: `fundguldasta_user`
- Local auth: trust mode via TCP (`/etc/postgresql/18/main/pg_hba.conf`: `host all all 127.0.0.1/32 trust`)

**Current state:** 877,758 NAV records | 14,366 funds | 84 cached bouquets (multiple horizons)

**11 tables:**

| Table | Notes |
|---|---|
| `fund_metadata` | sebi_category, fund_type are VARCHAR(200) |
| `nav_data` | TimescaleDB hypertable |
| `fund_managers` | Placeholder data — SID parser not built |
| `manager_change_log` | Used by P15 alert system |
| `portfolio_holdings` | Empty — holdings parser not built |
| `benchmark_data` | Nifty 50 NAV series |
| `computed_metrics` | Per-fund computed scores |
| `bouquet_cache` | API reads only from here; archetypes: `steady`, `balanced`, `aggressive`, `conviction` |
| `pipeline_log` | Precomputation run history |
| `users` | id, email, password_hash, display_name, manager_alert (bool), monthly_digest (bool) |
| `saved_bouquets` | user_id FK, archetype_id, horizon_years, target_cagr, snapshot JSON |

Quick health check:
```bash
curl http://localhost:8000/api/stats
```

### Populating the cache

```bash
cd ~/fundguldasta && source venv/bin/activate

python3 -c "from engine.precompute import run_precomputation; run_precomputation(horizon_years=5, target_cagr=14)"
python3 -c "from engine.precompute import run_precomputation; run_precomputation(horizon_years=7, target_cagr=16)"
python3 -c "from engine.precompute import run_precomputation; run_precomputation(horizon_years=10, target_cagr=16)"
```

---

## All API Endpoints (current, verified 24/24 operational)

### Public / core
```
GET  /health
GET  /api/stats
GET  /api/pipeline/status
POST /api/bouquets/curate                     body: {horizon_years, target_cagr}
GET  /api/bouquets/{id}/metrics               id = steady|balanced|aggressive|conviction
GET  /api/bouquets/{id}/confidence
GET  /api/bouquets/{id}/stress-test
GET  /api/bouquets/{id}/overlap
GET  /api/bouquets/{id}/freshness
POST /api/bouquets/{id}/backtest              body: {monthly_sip, horizon_years, future_years}
POST /api/bouquets/customize                  body: {archetype_id, replacement_fund_code, horizon_years, target_cagr}
```

### Fund search & detail
```
GET  /api/funds/search?q=<query>&limit=10
GET  /api/funds/{scheme_code}/detail
GET  /api/funds/{scheme_code}/score?horizon_years=7&target_cagr=16
```

### Auth (JWT, 30-day expiry)
```
POST /api/auth/register                       body: {email, password, display_name?}
POST /api/auth/login                          body: {email, password}
GET  /api/auth/me                             header: Authorization: Bearer <token>
```

### User
```
GET   /api/user/preferences                   header: Authorization: Bearer <token>
PATCH /api/user/preferences                   body: {manager_alert?, monthly_digest?}
POST  /api/user/saved-bouquets                saves current bouquet with snapshot
GET   /api/user/saved-bouquets                list saved bouquets
DELETE /api/user/saved-bouquets/{id}          delete one
```

### Portfolio (P16)
```
POST /api/portfolio/import-cas                multipart PDF upload (CAMS or KFintech), max 15MB
POST /api/portfolio/analyse                   body: {holdings: [{scheme_code, units, value}]}
```

---

## Auth System

`api/auth.py` uses **direct `bcrypt`** — NOT `passlib`. passlib 1.7.4 is incompatible with bcrypt 5.0.0 (bcrypt enforces 72-byte limit, passlib's detection probe exceeds it).

```python
import bcrypt
hash_password(password)   → bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()
verify_password(plain, h) → bcrypt.checkpw(plain.encode(), h.encode())
create_token(user_id, email) → jwt.encode({sub, email, exp}, _SECRET, HS256)
decode_token(token)       → jwt.decode(token, _SECRET, algorithms=["HS256"])
```

JWT secret lives in `config/.env` as `JWT_SECRET_KEY`. Default fallback only for local dev.

All protected endpoints use `_Header(default=None)` + `_get_user_from_token(authorization)` — NOT query params.

---

## Security Rules (non-negotiable)

1. `config/.env` is gitignored. **Never commit it.**
2. No API keys, DB passwords, or JWT secrets in any committed file.
3. Old Anthropic key `sk-ant-api03-rapmaiZYPmaQ85...` is compromised — never reference or use.
4. Timescale Cloud production credentials are in Claude memory only, never in git.
5. Do not add any environment variables or credentials to `CLAUDE.md`.

---

## Frontend Design System

Dark gold-on-black aesthetic (intentional — financial gravitas).

- Fonts: Cormorant Garamond (headings), Outfit (body), JetBrains Mono (numbers)
- Color palette: `const G` object at top of `App.js`
- Single-file SPA: `frontend/fundguldasta-ui/src/App.js`
- Build: `npm run build` inside `fundguldasta-ui/` — must pass with zero ESLint errors

**ESLint no-shadow rule is enforced.** The translation helper is `const tr = (en, hi) => ...` — never rename it to `t` (shadows `.map(t => ...)` parameter and causes build failure).

**Hindi/English toggle:** `const [lang, setLang] = useState('en')` — translation via `tr(en, hi)` calls.

---

## Computation Engine (5 layers)

1. **Eligibility Filter** — Direct plan, AUM ≥ ₹500Cr, expense ratio ≤ 1.5%, tier by NAV history
2. **Fund Scorer** — Return Consistency 25%, Risk-Adjusted Quality 20%, Downside Behaviour 20%, Manager Stability 15%, Portfolio Quality 10%, Forward Context 10%
3. **Bouquet Builder** — Correlation matrix, category diversity constraint, weighted metrics, benchmark comparisons
4. **Confidence Scorer** — Rolling Consistency 30%, Downside Protection 20%, Manager Stability 20%, Category Tailwind 15%, Cost Efficiency 15%
5. **Precompute** — Writes to `bouquet_cache`; API never triggers live computation

---

## CAS Parser (P16)

`engine/cas_parser.py` — parses Consolidated Account Statements from CAMS and KFintech.

- Format detection: looks for "computer age management" or "cams" (CAMS); "kfin" or "karvy" (KFintech)
- Strategy: anchor-based backward lookup — finds "Closing Balance" lines, scans back for fund name
- Fuzzy matching: `rapidfuzz.fuzz.token_sort_ratio` via `process.extractOne` — handles name variants
- Returns: `{format, holdings: [{fund_name_raw, scheme_code, matched_name, units, nav, value, allocation_pct, confidence}], total_value, fund_count, parse_errors}`
- Public API: `parse_cas_pdf(pdf_bytes, fund_list=None)` and `parse_cas_text(text, fund_list=None)`

---

## CAGR Realism Bands (P7.1)

`engine/cagr_advisor.py` — `assess_realism(target_cagr, horizon_years)` returns `{category, message, realistic_range}`.

```
3-year:   8–14% realistic  | 15–18% aggressive  | 19%+ unrealistic
5-year:  10–15% realistic  | 16–19% aggressive  | 20%+ unrealistic
7-year:  12–16% realistic  | 17–20% aggressive  | 21%+ unrealistic
10-year: 13–17% realistic  | 18–21% aggressive  | 22%+ unrealistic
15-year: 13–18% realistic  | 19–22% aggressive  | 23%+ unrealistic
```

Frontend shows amber advisory banner for aggressive/unrealistic — user can always proceed.

---

## Archetype IDs (cache keys — exact strings required)

| Cache ID | Display Name | CAGR Target | Funds |
|---|---|---|---|
| `steady` | Steady Compounder | 14–16% | 118825(25%), 122639(25%), 120152(20%), 149134(15%), 118955(15%) |
| `balanced` | Balanced Growther | 15–17% | 118825(20%), 122639(20%), 120505(25%), 118778(20%), 145552(15%) |
| `aggressive` | Aggressive Achiever | 16–19% | 118989(25%), 118778(20%), 119071(20%), 120505(20%), 120828(15%) |
| `conviction` | High Conviction | 18–22% | 118778(30%), 118989(25%), 120828(20%), 118834(15%), 135800(10%) |

---

## Verified Scheme Codes

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

**Do not change without DB verification.**  
Critical: 119553 = debt IDCW (not HDFC Flexi Cap). 118988 = IDCW (not HDFC Mid Cap Growth). "Kotak Equity Opportunities" does not exist — use 120152.

---

## Indian MF Correlation Reality

Indian equity funds correlate at **0.85–0.98** with each other. Structural, not a bug.  
Genuine diversifiers: Motilal Nasdaq (0.33–0.37 vs Indian equity), Tata Digital (0.59–0.66).  
Thresholds: HARD_REJECT=0.95, WARNING=0.85. Category diversity is the primary constraint.

---

## Python Environment

- Python 3.14, venv at `~/fundguldasta/venv/`
- Key packages: `pandas numpy sqlalchemy psycopg2-binary requests pdfplumber fastapi uvicorn httpx pytest python-dotenv anthropic mftool yfinance bcrypt PyJWT rapidfuzz python-multipart`
- `engine/` and `data/` have `__init__.py` (required for module imports)
- `passlib` is installed but must NOT be used for bcrypt — incompatible with bcrypt 5.0.0

---

## Testing

```bash
cd ~/fundguldasta && source venv/bin/activate
python3 -m pytest tests/ -v
```

**Current state: 119/119 passing.** Pre-push hook runs full suite before every push.

Test files:
- `tests/test_priority15_17.py` — manager alerts, digest, DB schema, Hindi translation logic
- `tests/test_priority16.py` — CAS parser (format detection, CAMS, KFintech, fuzzy match, gap analysis)
- (earlier test files for engine layers)

Operational audit script: `/tmp/test_correct_ids.py` — verifies all 24 live endpoints.

---

## What Is Deferred (known gaps)

| Gap | Impact | Fix |
|---|---|---|
| `portfolio_holdings` empty — holdings parser not built | overlap shows 0% | Build SID/AMFI holdings importer |
| `fund_managers` has placeholder data | Manager stability scores default to 40–45 | Build SID PDF parser |
| Email sending for alerts/digest | Alerts computed but not sent (no SMTP key) | Add SendGrid/SES config to `config/.env` |

---

## Roadmap (Priority 18 onward)

| Priority | What |
|---|---|
| **18 — Cloud Deployment** | Frontend → Vercel, Backend → Railway/Render, DB → Timescale Cloud (already provisioned, Mumbai); DNS for fundguldasta.com |
| **19 — Monitoring** | UptimeRobot health checks, email alerts for pipeline failures, manager change detection pipeline |
| **20 — SEO Content** | Algorithm transparency, rolling returns explainer, survivorship bias, confidence score guide, why direct plans |
| **21 — Holdings Parser** | Build portfolio_holdings importer from AMFI/SID data to enable real overlap analysis |
| **22 — Manager SID Parser** | Parse SEBI SID PDFs for real fund_managers data |

---

## Commit Message Convention

```
Priority X: <what changed and why>
Fix: <bug description>
```

Use present tense. Keep under 72 chars for the subject line.
