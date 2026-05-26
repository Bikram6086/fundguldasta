import requests, json

r = requests.post("http://localhost:8000/api/bouquets/curate", json={"horizon_years": 7, "target_cagr": 16}, timeout=15)
d = r.json()
for arch in d.get("archetypes", []):
    ov = arch.get("overlap", {})
    print(f"{arch.get('archetypeId', arch.get('id','?')):12s}: overlap={ov.get('avgOverlapPct')}%  coverage={ov.get('holdingsCoveragePct')}%")
