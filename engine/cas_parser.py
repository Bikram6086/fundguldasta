"""
CAS (Consolidated Account Statement) PDF parser.

Supports CAMS and KFintech (Karvy) formats.
Strategy: anchor on "Closing Balance" lines (always present), then look
backward for the fund name. This is more robust than forward scanning.

Public API:
  parse_cas_pdf(pdf_bytes: bytes) -> dict
  parse_cas_text(text: str)        -> dict  (for testing without a real PDF)
"""
import re
import io
from typing import Optional

import pdfplumber
import psycopg2
from rapidfuzz import fuzz, process


# ── Number helpers ────────────────────────────────────────────────────────────

def _clean_num(s: str) -> float:
    return float(s.replace(",", "").replace("₹", "").strip())


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
# CAMS closing balance line (single line or split):
#   "Closing Balance : 234.567 Units  NAV : ₹48.920  Value : ₹11,470.99"

_CAMS_CB = re.compile(
    r"[Cc]losing\s+[Bb]alance\s*[:\-]?\s*([\d,]+\.?\d*)\s*[Uu]nits?"
    r".*?NAV\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d+)"
    r".*?[Vv]alue\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d+)",
)
# Multi-line variant where NAV/Value are on the next line
_CAMS_CB_UNITS = re.compile(
    r"[Cc]losing\s+[Bb]alance\s*[:\-]?\s*([\d,]+\.?\d*)\s*[Uu]nits?"
)
_CAMS_NAV_VAL = re.compile(
    r"NAV\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d+).*?[Vv]alue\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d+)"
)

# Fund name: a long line containing "Fund" or "Scheme" and "Direct" or "Growth"
_FUND_NAME_RE = re.compile(
    r"^(.{8,}(?:Fund|ETF|Scheme|FoF).{0,120}(?:Direct|Growth|IDCW).*)$",
    re.IGNORECASE,
)
_NOISE_LINE = re.compile(
    r"(statement|transaction|folio|opening|closing|balance|period|date|page"
    r"|registrar|amc\s*name|investor|pan\s*no|email|mobile|address)",
    re.IGNORECASE,
)


def _extract_fund_name_before(lines: list, before_idx: int) -> Optional[str]:
    """Scan lines[before_idx-1] back to find the nearest fund name line."""
    for i in range(before_idx - 1, max(before_idx - 30, -1), -1):
        line = lines[i].strip()
        if _FUND_NAME_RE.match(line) and not _NOISE_LINE.search(line) and len(line) > 20:
            return line.strip(" -–—|")
    return None


def _parse_text_cams(text: str) -> list:
    lines = text.split("\n")
    holdings = []

    for idx, line in enumerate(lines):
        line_s = line.strip()

        # Try single-line closing balance (most common in CAMS)
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
            fname = _extract_fund_name_before(lines, idx)
            if fname:
                holdings.append({"fund_name_raw": fname, "units": units, "nav": nav, "value": value})
            continue

        # Two-line variant: units on this line, NAV+Value on next
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
                fname = _extract_fund_name_before(lines, idx)
                if fname:
                    holdings.append({"fund_name_raw": fname, "units": units, "nav": nav, "value": value})

    return holdings


# ── KFintech parser ───────────────────────────────────────────────────────────
# KFintech closing balance line:
#   "Closing Balance : 234.567 Units"
# Market value often on same or next line:
#   "Market Value as on 31-Mar-2025 :  ₹ 11,470.99"

_KF_CB = re.compile(
    r"[Cc]losing\s+[Bb]alance\s*[:\-]?\s*([\d,]+\.?\d*)\s*[Uu]nits?"
)
_KF_MV = re.compile(
    r"[Mm]arket\s+[Vv]alue[^:\n]*:\s*[₹]?\s*([\d,]+\.?\d+)"
)
_KF_NAV = re.compile(
    r"\bNAV\b[^:\n]*:\s*[₹]?\s*([\d,]+\.?\d+)"
)


def _parse_text_kfintech(text: str) -> list:
    lines = text.split("\n")
    holdings = []

    for idx, line in enumerate(lines):
        line_s = line.strip()
        mu = _KF_CB.search(line_s)
        if not mu:
            continue
        try:
            units = _clean_num(mu.group(1))
        except ValueError:
            continue
        if units <= 0:
            continue

        # Search for market value in same line or next 4 lines
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

        fname = _extract_fund_name_before(lines, idx)
        if fname:
            holdings.append({"fund_name_raw": fname, "units": units, "nav": nav, "value": value})

    return holdings


# ── Generic fallback ──────────────────────────────────────────────────────────

def _parse_text_generic(text: str) -> list:
    """Last-resort: find any Closing Balance line, look backward for fund name."""
    lines = text.split("\n")
    holdings = []
    cb_re = re.compile(
        r"[Cc]losing\s+[Bb]alance\s*[:\-]?\s*([\d,]+\.?\d*)\s*[Uu]nits?"
    )
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
                "units": units,
                "nav": 0.0,
                "value": value_candidates[-1],
            })

    return holdings


# ── Deduplication + allocation ────────────────────────────────────────────────

def _match_and_dedupe(raw_holdings: list, fund_list: list) -> list:
    """
    Fuzzy-match each raw holding to a scheme_code; deduplicate by scheme_code
    (sum values for multiple folios of the same fund).
    Returns enriched holding list sorted by value descending.
    """
    merged: dict = {}  # scheme_code -> holding

    for h in raw_holdings:
        sc, matched_name, confidence = match_fund_name(h["fund_name_raw"], fund_list)

        key = sc if sc else h["fund_name_raw"]  # fallback key if no match

        if key in merged:
            merged[key]["value"] += h["value"]
            merged[key]["units"] += h["units"]
        else:
            merged[key] = {
                "fund_name_raw": h["fund_name_raw"],
                "scheme_code": sc,
                "matched_name": matched_name,
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


# ── Public API ────────────────────────────────────────────────────────────────

def parse_cas_text(text: str, fund_list: Optional[list] = None) -> dict:
    """
    Parse CAS text (already extracted from PDF or provided directly).
    fund_list: [(scheme_code, scheme_name)] — pass None to load from DB.
    """
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
        raw = _parse_text_cams(text)
    elif fmt == "kfintech":
        raw = _parse_text_kfintech(text)
    else:
        raw = _parse_text_cams(text)
        if not raw:
            raw = _parse_text_kfintech(text)
        if not raw:
            raw = _parse_text_generic(text)

    errors = []
    if db_err:
        errors.append(f"DB lookup unavailable: {db_err}")
    if not raw:
        errors.append(
            "No fund holdings detected. Ensure the PDF is a standard CAMS or KFintech CAS. "
            "Try exporting a fresh copy from CAMS Online or KFintech."
        )

    matched = _match_and_dedupe(raw, fund_list)
    total = sum(h["value"] for h in matched)

    return {
        "format": fmt,
        "holdings": matched,
        "total_value": round(total, 2),
        "fund_count": len(matched),
        "parse_errors": errors,
    }


def parse_cas_pdf(pdf_bytes: bytes, fund_list: Optional[list] = None) -> dict:
    """
    Main entry point. Accept raw PDF bytes, return parsed holdings.
    """
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
            "format": "unknown",
            "holdings": [],
            "total_value": 0,
            "fund_count": 0,
            "parse_errors": [f"PDF read error: {e}"],
        }

    if not text.strip():
        return {
            "format": "unknown",
            "holdings": [],
            "total_value": 0,
            "fund_count": 0,
            "parse_errors": ["Could not extract text from PDF. The file may be scanned/image-based."],
        }

    return parse_cas_text(text, fund_list=fund_list)
