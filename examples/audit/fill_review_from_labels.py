"""Fill `stated_by_source` in an example review.csv from the answer key in pairs.jsonl.

Only for this example: in a real audit a person fills the column by reading each memory next
to its source. Usage: python examples/audit/fill_review_from_labels.py examples/audit/report-en
"""

import csv
import json
import sys
from pathlib import Path

here = Path(__file__).parent
labels = {}
for line in (here / "pairs.jsonl").read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    if row.get("label"):
        labels[row["id"]] = "yes" if row["label"] == "S" else "no"

review = Path(sys.argv[1]) / "review.csv"
with review.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
for row in rows:
    row["stated_by_source"] = labels[row["id"]]
    row["reviewer_note"] = "filled from the answer key in pairs.jsonl"
with review.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"{len(rows)} rows filled in {review}")
