import requests, openpyxl, zipfile, io

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Verify the two Kotak 200-status URLs
kotak_candidates = [
    "https://www.kotakmf.com/documents/portfolio/April2026Portfolio.xlsx",
    "https://kotakmf.com/staticdata/portfolios/KotakMonthlyPortfolio_April2026.xlsx",
]
for url in kotak_candidates:
    r = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
    print(f"\n{url}")
    print(f"  status={r.status_code} size={len(r.content)}")
    if len(r.content) > 5000:
        try:
            wb = openpyxl.load_workbook(io.BytesIO(r.content), data_only=True)
            print(f"  sheets: {wb.sheetnames[:5]}")
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                vals = [v for v in row if v and str(v).strip()]
                if vals:
                    print(f"  first row: {vals[:4]}")
                    break
        except Exception as e:
            print(f"  parse error: {e}")
    else:
        print(f"  too small — likely HTML error page")

# Inspect DSP equity file
print("\n--- DSP Equity Portfolio ---")
dsp_url = "https://www.dspim.com/media/pages/mandatory-disclosures/portfolio-disclosures/d80216af21-1778404078/monthend-portfolios_30-april-2026.zip"
r = requests.get(dsp_url, headers=headers, timeout=60)
z = zipfile.ZipFile(io.BytesIO(r.content))
equity_file = "DSP Equity ISIN Portfolio as on 30 Apr 2026.xlsx"
with z.open(equity_file) as f:
    wb = openpyxl.load_workbook(io.BytesIO(f.read()), data_only=True)
    print(f"DSP equity sheets: {wb.sheetnames}")
    # Look for sheet containing midcap
    for sheet in wb.sheetnames:
        if 'mid' in sheet.lower() or 'midcap' in sheet.lower():
            print(f"  Found midcap sheet: {sheet}")
        ws = wb[sheet]
        for row in ws.iter_rows(values_only=True):
            vals = [str(v) for v in row if v and str(v).strip()]
            if any('mid' in v.lower() for v in vals):
                print(f"  Sheet {sheet} first midcap row: {vals[:4]}")
                break
