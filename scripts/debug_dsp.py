import requests, openpyxl, zipfile, io

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

dsp_url = "https://www.dspim.com/media/pages/mandatory-disclosures/portfolio-disclosures/d80216af21-1778404078/monthend-portfolios_30-april-2026.zip"
r = requests.get(dsp_url, headers=headers, timeout=60)
z = zipfile.ZipFile(io.BytesIO(r.content))
equity_file = "DSP Equity ISIN Portfolio as on 30 Apr 2026.xlsx"
with z.open(equity_file) as f:
    content = f.read()

wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
print("Sheets:", wb.sheetnames)
for sheet in wb.sheetnames:
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    # Print first 3 non-empty rows
    count = 0
    for row in rows:
        vals = [v for v in row if v is not None]
        if vals:
            print(f"  {sheet} row: {[str(v)[:40] for v in vals[:5]]}")
            count += 1
            if count >= 2:
                break
