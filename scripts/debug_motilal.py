import requests, openpyxl, io

url = "https://www.motilaloswalmf.com/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/may/Motilal%20Portfolio%2030%20April%202026%20-%20Final.xlsx"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
r = requests.get(url, headers=headers, timeout=30)
print("status:", r.status_code, "size:", len(r.content))
wb = openpyxl.load_workbook(io.BytesIO(r.content), data_only=True)
ws = wb["YO13"]
for i, row in enumerate(ws.iter_rows(values_only=True)):
    print(f"row {i:3d}:", row)
