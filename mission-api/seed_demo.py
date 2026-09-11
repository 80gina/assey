"""Insert 100 deterministic time-series records for the mission demonstration."""
from datetime import date, timedelta
import requests

BASE = "http://localhost:8000"
start = date(2026, 1, 1)
for i in range(100):
    response = requests.post(f"{BASE}/api/data", json={
        "date": str(start + timedelta(days=i)),
        "value": round(50 + i * 0.2 + (i % 7) * 0.45, 2),
        "memo": f"demo record {i + 1}",
    }, timeout=10)
    response.raise_for_status()
print(requests.get(f"{BASE}/api/data/summary", timeout=10).json())

