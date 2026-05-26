import requests, openpyxl, io

base = "https://www.miraeassetmf.co.in/docs/default-source/portfolios/"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
slugs = ["malcf", "macf", "mlcf", "largecap", "lc", "largecapfund", "malgrowth", "malargecap", "malfund", "focus", "mafocus", "mafocused", "focused"]

for s in slugs:
    url = base + s + "-april2026.xlsx"
    r = requests.get(url, headers=headers, timeout=15)
    if len(r.content) < 5000:
        print(f"{s}: small response ({len(r.content)} bytes) — likely error page")
        continue
    try:
        wb = openpyxl.load_workbook(io.BytesIO(r.content), data_only=True)
        ws = wb.active
        # Print first few non-empty cell values to identify the fund
        for row in ws.iter_rows(values_only=True):
            vals = [v for v in row if v and str(v).strip()]
            if vals:
                print(f"{s}: {vals[:3]}")
                break
    except Exception as e:
        print(f"{s}: parse error — {e}")
