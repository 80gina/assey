"""Write 100 demo records directly to Firestore.

Run only after FIRESTORE_PROJECT_ID and Google credentials are configured.
"""
import os
from datetime import date, timedelta
from google.cloud import firestore

project = os.environ.get("FIRESTORE_PROJECT_ID")
if not project:
    raise SystemExit("FIRESTORE_PROJECT_ID is required")

db = firestore.Client(project=project)
batch = db.batch()
start = date(2026, 1, 1)
for i in range(100):
    ref = db.collection("data").document(f"demo-{i + 1:03d}")
    batch.set(ref, {
        "date": str(start + timedelta(days=i)),
        "value": round(50 + i * 0.2 + (i % 7) * 0.45, 2),
        "memo": f"demo record {i + 1}",
    })
batch.commit()
print("100 Firestore demo records written")

