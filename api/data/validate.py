"""Validate candidate JSONL batches against generation_spec.md.

Usage:  .venv/bin/python data/validate.py data/education.jsonl [more files...]
Checks schema, taxonomy, length, exact duplicates, and prints label /
language / flag distributions plus heuristic agreement vs analyzer.py
(informational only, never a gate).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer import analyze_text  # noqa: E402

LABELS = {"education", "mixed", "promotion"}
LANGS = {"en", "hi", "hinglish"}
FLAGS = {
    "unrealistic_returns",
    "risk_downplay",
    "fake_authority",
    "paid_service_cta",
    "urgency_pressure",
    "social_proof",
    "missing_disclosure",
}

errors: list[str] = []
items: list[dict] = []
seen: dict[str, str] = {}

for path in sys.argv[1:]:
    for lineno, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"{path}:{lineno}: invalid JSON")
            continue
        items.append(obj)
        loc = f"{path}:{lineno} ({obj.get('id', '?')})"
        for key in ("id", "lang", "label", "flags", "text", "source"):
            if key not in obj:
                errors.append(f"{loc}: missing key {key}")
        if obj.get("label") not in LABELS:
            errors.append(f"{loc}: bad label {obj.get('label')}")
        if obj.get("lang") not in LANGS:
            errors.append(f"{loc}: bad lang {obj.get('lang')}")
        for f in obj.get("flags", []):
            if f not in FLAGS:
                errors.append(f"{loc}: bad flag {f}")
        text = obj.get("text", "")
        if not (20 <= len(text) <= 600):
            errors.append(f"{loc}: length {len(text)} outside 20-600")
        if obj.get("label") == "education" and obj.get("flags"):
            errors.append(f"{loc}: education item lists flags")
        norm = " ".join(text.lower().split())
        if norm in seen:
            errors.append(f"{loc}: duplicate of {seen[norm]}")
        else:
            seen[norm] = loc

print(f"items: {len(items)}")
print("labels:", dict(Counter(i["label"] for i in items)))
print("langs:", dict(Counter(i["lang"] for i in items)))
flag_counts = Counter(f for i in items for f in i["flags"])
print("flags:", dict(flag_counts))
# missing_disclosure is computed doc-level by the analyzer, never item-labeled.
missing_flags = FLAGS - set(flag_counts) - {"missing_disclosure"}
print("uncovered flags:", sorted(missing_flags) or "none")

agree = sum(1 for i in items if analyze_text(i["text"])["classification"] == i["label"])
print(f"heuristic agreement: {agree}/{len(items)} ({agree / max(len(items), 1):.0%})")

if errors:
    print(f"\nERRORS ({len(errors)}):")
    for e in errors[:30]:
        print(" -", e)
    sys.exit(1)
print("\nOK: schema, taxonomy, length, dedup all pass.")
