"""
CAS (Consolidated Account Statement) PDF parser.

Supports CAMS and KFintech (Karvy) formats.
Extracts both closing-balance holdings AND individual transaction history.

Public API:
  parse_cas_pdf(pdf_bytes: bytes) -> dict
  parse_cas_text(text: str)        -> dict  (for testing without a real PDF)

Output dict keys:
  format, holdings, transactions, total_value, fund_count, parse_errors
"""
import re
import io
from datetime import datetime
from typing import Optional

import pdfplumber
import psycopg2
from rapidfuzz import fuzz, process


# ── Number helpers ────────────────────────────────────────────────────────────

def _clean_num(s: str) -> float:
    return float(s.replace(",", "").replace("₹", "").strip())


def _parse_date(s: str) -> Optional[str]:
    """Try common CAS date formats; return ISO yyyy-mm-dd or None."""
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ── DB: load fund name → scheme_code lookup table ────────────────────────────

def _load_fund_names(
    conn_str: str = "host=127.0.0.1 dbname=fundguldasta_dev user=fundguldasta_user",
) -> list:
    """Return [(scheme_code_str, scheme_name)] for all funds in fund_metadata."""
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    cur.execute("SELECT scheme_code, scheme_name FROM fund_metadata LIMIT 25000")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [(str(r[0]), r[1]) for r in rows]


# ── Fuzzy matching ────────────────────────────────────────────────────────────

_NOISE = ["growth", "direct plan", "- direct", "direct -", "(direct)",
          "idcw", "dividend", "reinvestment", "option", "plan", "-", "–"]


def _normalise(name: str) -> str:
    n = name.lower()
    for w in _NOISE:
        n = n.replace(w, " ")
    return " ".join(n.split())


def match_fund_name(fund_name: str, fund_list: list) -> tuple:
    """
    Fuzzy-match fund_name against fund_list using token-sort ratio.
    Returns (scheme_code, matched_name, confidence_score 0-100).
    """
    if not fund_list:
        return None, None, 0

    query = _normalise(fund_name)
    choices = {sc: _normalise(name) for sc, name in fund_list}

    result = process.extractOne(query, choices, scorer=fuzz.token_sort_ratio)
    if result is None:
        return None, None, 0

    _, score, matched_code = result
    original_name = next((name for sc, name in fund_list if sc == matched_code), "")
    return matched_code, original_name, int(score)


# ── Format detection ──────────────────────────────────────────────────────────

def _detect_format(text: str) -> str:
    t = text.lower()
    if "computer age management" in t or ("cams" in t[:600] and "consolidated" in t[:600]):
        return "cams"
    if "kfin" in t[:600] or "karvy" in t[:600]:
        return "kfintech"
    return "unknown"


# ── CAMS parser ───────────────────────────────────────────────────────────────

_CAMS_CB = re.compile(
    r"[Cc]losing\s+[Bb]alance\s*[:\-]?\s*([\d,]+\.?\d*)\s*[Uu]nits?"
    r".*?NAV\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d+)"
    r".*?[Vv]alue\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d+)",
)
_CAMS_CB_UNITS = re.compile(
    r"[Cc]losing\s+[Bb]alance\s*[:\-]?\s*([\d,]+\.?\d*)\s*[Uu]nits?"
)
_CAMS_NAV_VAL = re.compile(
    r"NAV\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d+).*?[Vv]alue\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d+)"
)

_FUND_NAME_RE = re.compile(
    r"^(.{8,}(?:Fund|ETF|Scheme|FoF).{0,120}(?:Direct|Growth|IDCW).*)$",
    re.IGNORECASE,
)
_NOISE_LINE = re.compile(
    r"(statement|transaction|folio|opening|closing|balance|period|date|page"
    r"|registrar|amc\s*name|investor|pan\s*no|email|mobile|address)",
    re.IGNORECASE,
)

# CAMS transaction line:
# "01-Apr-2023  Purchase-SIP  5,000.00  110.8234  45.123  45.123"
# "01-Apr-2023  Redemption    -5,000.00  118.5432  -42.201  3.000"
_CAMS_TXN = re.compile(
    r"^(\d{2}-[A-Za-z]{3}-\d{4})\s+"           # date
    r"(.+?)\s+"                                  # description (lazy)
    r"([\-\d,]+\.?\d*)\s+"                       # amount
    r"([\d,]+\.?\d+)\s+"                         # nav/price
    r"([\-\d,]+\.?\d*)\s+"                       # units
    r"([\d,]+\.?\d*)$"                           # balance
)

# Alternative CAMS format: date and description on one line, numbers on next
_CAMS_TXN_DATE_DESC = re.compile(
    r"^(\d{2}-[A-Za-z]{3}-\d{4})\s+(.{3,60}?)$"
)
_CAMS_TXN_NUMS = re.compile(
    r"^\s*([\-\d,]+\.?\d*)\s+([\d,]+\.?\d+)\s+([\-\d,]+\.?\d*)\s+([\d,]+\.?\d*)$"
)

_TXN_TYPE_MAP = {
    "purchase": "purchase",
    "sip": "sip",
    "lump": "purchase",
    "redemption": "redemption",
    "redeem": "redemption",
    "switch in": "switch_in",
    "switch out": "switch_out",
    "switch-in": "switch_in",
    "switch-out": "switch_out",
    "dividend": "dividend",
    "bonus": "bonus",
    "segregation": "segregation",
    "transmission": "transmission",
    "merger": "merger",
}


def _classify_txn_type(desc: str) -> str:
    d = desc.lower()
    for key, val in _TXN_TYPE_MAP.items():
        if key in d:
            return val
    if "purchase" in d or "invest" in d or "allot" in d:
        return "purchase"
    return "other"


def _extract_fund_name_before(lines: list, before_idx: int) -> Optional[str]:
    for i in range(before_idx - 1, max(before_idx - 30, -1), -1):
        line = lines[i].strip()
        if _FUND_NAME_RE.match(line) and not _NOISE_LINE.search(line) and len(line) > 20:
            return line.strip(" -–—|")
    return None


def _parse_text_cams(text: str) -> tuple:
    """Returns (holdings_list, transactions_list)."""
    lines = text.split("\n")
    holdings = []
    transactions = []

    current_fund_name = None
    current_folio = None

    _folio_re = re.compile(r"[Ff]olio\s*[Nn]o[:\.]?\s*([\w\/\-]+)")

    for idx, line in enumerate(lines):
        line_s = line.strip()

        # Track current fund name
        if _FUND_NAME_RE.match(line_s) and not _NOISE_LINE.search(line_s) and len(line_s) > 20:
            current_fund_name = line_s.strip(" -–—|")

        # Track folio number
        fm = _folio_re.search(line_s)
        if fm:
            current_folio = fm.group(1).strip()

        # Closing balance (single-line)
        m = _CAMS_CB.search(line_s)
        if m:
            try:
                units = _clean_num(m.group(1))
                nav = _clean_num(m.group(2))
                value = _clean_num(m.group(3))
            except (ValueError, IndexError):
                continue
            if units <= 0 or value <= 0:
                continue
            fname = current_fund_name or _extract_fund_name_before(lines, idx)
            if fname:
                holdings.append({
                    "fund_name_raw": fname,
                    "folio": current_folio,
                    "units": units,
                    "nav": nav,
                    "value": value,
                })
            continue

        # Closing balance (two-line variant)
        mu = _CAMS_CB_UNITS.search(line_s)
        if mu and idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            mnv = _CAMS_NAV_VAL.search(next_line)
            if mnv:
                try:
                    units = _clean_num(mu.group(1))
                    nav = _clean_num(mnv.group(1))
                    value = _clean_num(mnv.group(2))
                except (ValueError, IndexError):
                    continue
                if units <= 0 or value <= 0:
                    continue
                fname = current_fund_name or _extract_fund_name_before(lines, idx)
                if fname:
                    holdings.append({
                        "fund_name_raw": fname,
                        "folio": current_folio,
                        "units": units,
                        "nav": nav,
                        "value": value,
                    })
            continue

        # Transaction line (single-line: date desc amount nav units balance)
        tm = _CAMS_TXN.match(line_s)
        if tm and current_fund_name:
            try:
                txn_date = _parse_date(tm.group(1))
                desc = tm.group(2).strip()
                amount = _clean_num(tm.group(3))
                nav_val = _clean_num(tm.group(4))
                units_txn = _clean_num(tm.group(5))
                if txn_date and nav_val > 0:
                    transactions.append({
                        "fund_name_raw": current_fund_name,
                        "folio": current_folio,
                        "txn_date": txn_date,
                        "txn_type": _classify_txn_type(desc),
                        "description": desc,
                        "amount": abs(amount),
                        "nav": nav_val,
                        "units": units_txn,
                        "is_redemption": amount < 0 or units_txn < 0,
                    })
            except (ValueError, IndexError):
                pass

    return holdings, transactions


# ── KFintech parser ───────────────────────────────────────────────────────────

_KF_CB = re.compile(
    r"[Cc]losing\s+[Bb]alance\s*[:\-]?\s*([\d,]+\.?\d*)\s*[Uu]nits?"
)
_KF_MV = re.compile(
    r"[Mm]arket\s+[Vv]alue[^:\n]*:\s*[₹]?\s*([\d,]+\.?\d+)"
)
_KF_NAV = re.compile(
    r"\bNAV\b[^:\n]*:\s*[₹]?\s*([\d,]+\.?\d+)"
)

# KFintech transaction: "01-Apr-2023  SIP-Purchase  5000.00  110.8234  45.123  45.123"
_KF_TXN = re.compile(
    r"^(\d{2}[-/][A-Za-z]{3}[-/]\d{4}|\d{2}[-/]\d{2}[-/]\d{4})\s+"
    r"(.+?)\s+"
    r"([\-\d,]+\.?\d*)\s+"
    r"([\d,]+\.?\d+)\s+"
    r"([\-\d,]+\.?\d*)\s+"
    r"([\d,]+\.?\d*)$"
)


def _parse_text_kfintech(text: str) -> tuple:
    """Returns (holdings_list, transactions_list)."""
    lines = text.split("\n")
    holdings = []
    transactions = []

    current_fund_name = None
    current_folio = None

    _folio_re = re.compile(r"[Ff]olio[:\s]*([\w\/\-]+)")

    for idx, line in enumerate(lines):
        line_s = line.strip()

        if _FUND_NAME_RE.match(line_s) and not _NOISE_LINE.search(line_s) and len(line_s) > 20:
            current_fund_name = line_s.strip(" -–—|")

        fm = _folio_re.search(line_s)
        if fm:
            current_folio = fm.group(1).strip()

        mu = _KF_CB.search(line_s)
        if not mu:
            continue

        try:
            units = _clean_num(mu.group(1))
        except ValueError:
            continue
        if units <= 0:
            continue

        value = 0.0
        nav = 0.0
        window = line_s + " " + " ".join(lines[idx + 1: idx + 5])
        mv_m = _KF_MV.search(window)
        if mv_m:
            try:
                value = _clean_num(mv_m.group(1))
            except ValueError:
                pass
        nav_m = _KF_NAV.search(window)
        if nav_m:
            try:
                nav = _clean_num(nav_m.group(1))
            except ValueError:
                pass

        if value <= 0 and nav > 0:
            value = round(units * nav, 2)
        if value <= 0:
            continue

        fname = current_fund_name or _extract_fund_name_before(lines, idx)
        if fname:
            holdings.append({
                "fund_name_raw": fname,
                "folio": current_folio,
                "units": units,
                "nav": nav,
                "value": value,
            })

        # Scan nearby lines for transactions
        for scan_idx in range(max(0, idx - 60), idx):
            scan_line = lines[scan_idx].strip()
            tm = _KF_TXN.match(scan_line)
            if tm and current_fund_name:
                try:
                    txn_date = _parse_date(tm.group(1))
                    desc = tm.group(2).strip()
                    amount = _clean_num(tm.group(3))
                    nav_val = _clean_num(tm.group(4))
                    units_txn = _clean_num(tm.group(5))
                    if txn_date and nav_val > 0:
                        transactions.append({
                            "fund_name_raw": current_fund_name,
                            "folio": current_folio,
                            "txn_date": txn_date,
                            "txn_type": _classify_txn_type(desc),
                            "description": desc,
                            "amount": abs(amount),
                            "nav": nav_val,
                            "units": units_txn,
                            "is_redemption": amount < 0 or units_txn < 0,
                        })
                except (ValueError, IndexError):
                    pass

    return holdings, transactions


# ── Generic fallback ──────────────────────────────────────────────────────────

def _parse_text_generic(text: str) -> tuple:
    lines = text.split("\n")
    holdings = []
    cb_re = re.compile(r"[Cc]losing\s+[Bb]alance\s*[:\-]?\s*([\d,]+\.?\d*)\s*[Uu]nits?")
    num_re = re.compile(r"([\d,]+\.\d{2,4})")

    for idx, line in enumerate(lines):
        m = cb_re.search(line.strip())
        if not m:
            continue
        try:
            units = _clean_num(m.group(1))
        except ValueError:
            continue
        if units <= 0:
            continue

        window = " ".join(lines[idx: idx + 4])
        nums = num_re.findall(window)
        value_candidates = []
        for n in nums:
            try:
                v = _clean_num(n)
                if v >= 100:
                    value_candidates.append(v)
            except ValueError:
                pass
        if not value_candidates:
            continue

        fname = _extract_fund_name_before(lines, idx)
        if fname:
            holdings.append({
                "fund_name_raw": fname,
                "folio": None,
                "units": units,
                "nav": 0.0,
                "value": value_candidates[-1],
            })

    return holdings, []


# ── Deduplication + allocation ────────────────────────────────────────────────

def _match_and_dedupe(raw_holdings: list, fund_list: list) -> list:
    merged: dict = {}

    for h in raw_holdings:
        sc, matched_name, confidence = match_fund_name(h["fund_name_raw"], fund_list)
        key = sc if sc else h["fund_name_raw"]

        if key in merged:
            merged[key]["value"] += h["value"]
            merged[key]["units"] += h["units"]
        else:
            merged[key] = {
                "fund_name_raw": h["fund_name_raw"],
                "scheme_code": sc,
                "matched_name": matched_name,
                "folio": h.get("folio"),
                "units": h["units"],
                "nav": h["nav"],
                "value": h["value"],
                "confidence": confidence,
            }

    result = list(merged.values())
    total = sum(r["value"] for r in result)

    for r in result:
        r["units"] = round(r["units"], 3)
        r["nav"] = round(r["nav"], 4)
        r["value"] = round(r["value"], 2)
        r["allocation_pct"] = round(r["value"] / total * 100, 2) if total > 0 else 0

    result.sort(key=lambda x: -x["value"])
    return result


def _match_transactions(raw_txns: list, fund_list: list) -> list:
    """Add scheme_code to each transaction via fuzzy match on fund_name_raw."""
    # Build a name → scheme_code cache to avoid re-matching the same fund repeatedly
    name_cache: dict = {}
    result = []
    for t in raw_txns:
        fname = t["fund_name_raw"]
        if fname not in name_cache:
            sc, _, conf = match_fund_name(fname, fund_list)
            name_cache[fname] = (sc, conf)
        sc, conf = name_cache[fname]
        if sc and conf >= 65:
            result.append({**t, "scheme_code": sc})
    # Deduplicate: same fund+folio+date+type+amount should appear once
    seen = set()
    deduped = []
    for t in result:
        key = (t["scheme_code"], t.get("folio"), t["txn_date"], t["txn_type"], round(t["amount"], 0))
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    deduped.sort(key=lambda x: x["txn_date"])
    return deduped


# ── Public API ────────────────────────────────────────────────────────────────

def parse_cas_text(text: str, fund_list: Optional[list] = None) -> dict:
    if fund_list is None:
        try:
            fund_list = _load_fund_names()
        except Exception as e:
            fund_list = []
            db_err = str(e)
        else:
            db_err = None
    else:
        db_err = None

    fmt = _detect_format(text)

    if fmt == "cams":
        raw_holdings, raw_txns = _parse_text_cams(text)
    elif fmt == "kfintech":
        raw_holdings, raw_txns = _parse_text_kfintech(text)
    else:
        raw_holdings, raw_txns = _parse_text_cams(text)
        if not raw_holdings:
            raw_holdings, raw_txns = _parse_text_kfintech(text)
        if not raw_holdings:
            raw_holdings, raw_txns = _parse_text_generic(text)

    errors = []
    if db_err:
        errors.append(f"DB lookup unavailable: {db_err}")
    if not raw_holdings:
        errors.append(
            "No fund holdings detected. Ensure the PDF is a standard CAMS or KFintech CAS. "
            "Try exporting a fresh copy from CAMS Online or KFintech."
        )

    matched_holdings = _match_and_dedupe(raw_holdings, fund_list)
    matched_txns = _match_transactions(raw_txns, fund_list)
    total = sum(h["value"] for h in matched_holdings)

    return {
        "format": fmt,
        "holdings": matched_holdings,
        "transactions": matched_txns,
        "total_value": round(total, 2),
        "fund_count": len(matched_holdings),
        "transaction_count": len(matched_txns),
        "parse_errors": errors,
    }


def parse_cas_pdf(pdf_bytes: bytes, fund_list: Optional[list] = None) -> dict:
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
            text = "\n".join(pages)
    except Exception as e:
        return {
            "format": "unknown", "holdings": [], "transactions": [],
            "total_value": 0, "fund_count": 0, "transaction_count": 0,
            "parse_errors": [f"PDF read error: {e}"],
        }

    if not text.strip():
        return {
            "format": "unknown", "holdings": [], "transactions": [],
            "total_value": 0, "fund_count": 0, "transaction_count": 0,
            "parse_errors": ["Could not extract text from PDF. The file may be scanned/image-based."],
        }

    return parse_cas_text(text, fund_list=fund_list)
