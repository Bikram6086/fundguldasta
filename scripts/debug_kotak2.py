import requests, openpyxl, io

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.kotakmf.com/Information/portfolios",
    "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
}

for url in [
    "https://www.kotakmf.com/documents/portfolio/April2026Portfolio.xlsx",
    "https://kotakmf.com/staticdata/portfolios/KotakMonthlyPortfolio_April2026.xlsx",
]:
    print(f"\nTrying: {url}")
    try:
        r = requests.get(url, headers=headers, timeout=60, allow_redirects=True, stream=True)
        print(f"  status={r.status_code}")
        content = b""
        for chunk in r.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > 100000:
                break
        print(f"  downloaded {len(content)} bytes")
        if len(content) > 5000:
            try:
                wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
                print(f"  sheets: {wb.sheetnames[:5]}")
            except Exception as e:
                print(f"  parse: {e}")
    except Exception as e:
        print(f"  error: {e}")
