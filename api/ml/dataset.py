"""Dataset loader for the Sachet classifier track.

Reads candidate JSONL files, applies review decisions, and produces
stratified train/val/test splits with a fixed seed for reproducibility.

Review contract (see data/generation_spec.md): an item with
"review": "reject" is dropped; an item with a "review_text" string uses
the corrected text. Items without review fields are used as-is and the
run is stamped PRE-REVIEW.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

LABELS = ["education", "mixed", "promotion"]
LABEL2ID = {label: i for i, label in enumerate(LABELS)}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CANDIDATE_FILES = [
    "education.jsonl",
    "education2.jsonl",
    "education3.jsonl",
    "mixed.jsonl",
    "mixed2.jsonl",
    "mixed3.jsonl",
    "mixed4.jsonl",
    "promotion.jsonl",
    "promotion2.jsonl",
    "promotion3.jsonl",
]

# Held-out evaluation set. Loaded ONLY by evaluate_heldout, never by
# load_items, so it cannot reach training even by accident. Batch 1+2 used a
# random split of one pool, which meant train and test shared a generator --
# the "template artifact" risk called out in data/generation_spec.md. This
# set is authored separately, with wider length and structure, and is never
# shuffled into train.
HELDOUT_FILES = ["heldout/test.jsonl"]


def _read(paths, data_dir: Path) -> list[dict]:
    items: list[dict] = []
    for name in paths:
        path = data_dir / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj.get("review") == "reject":
                continue
            items.append(
                {
                    "id": obj["id"],
                    "lang": obj["lang"],
                    "label": obj["label"],
                    "label_id": LABEL2ID[obj["label"]],
                    "text": obj.get("review_text") or obj["text"],
                }
            )
    return items


def load_items(data_dir: Path = DATA_DIR) -> tuple[list[dict], bool]:
    """Return (items, reviewed). Each item: id/lang/label/label_id/text."""
    items: list[dict] = []
    reviewed_any = False
    for name in CANDIDATE_FILES:
        path = data_dir / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj.get("review") == "reject":
                continue
            if "review" in obj or "review_text" in obj:
                reviewed_any = True
            items.append(
                {
                    "id": obj["id"],
                    "lang": obj["lang"],
                    "label": obj["label"],
                    "label_id": LABEL2ID[obj["label"]],
                    "text": obj.get("review_text") or obj["text"],
                }
            )
    return items, reviewed_any


def load_heldout(data_dir: Path = DATA_DIR) -> list[dict]:
    """The held-out set. Never returned by load_items, so never trained on."""
    return _read(HELDOUT_FILES, data_dir)


def assert_disjoint(train: list[dict], heldout: list[dict]) -> None:
    """Fail loudly if any held-out text also appears in training.

    Guards against a copy-paste regression reintroducing the leak that
    stratified_split made possible in batch 1+2.
    """
    train_ids = {i["id"] for i in train}
    train_text = {i["text"].strip().lower() for i in train}
    dup_ids = [i["id"] for i in heldout if i["id"] in train_ids]
    dup_text = [i["id"] for i in heldout if i["text"].strip().lower() in train_text]
    if dup_ids or dup_text:
        raise AssertionError(
            f"held-out leak: {len(dup_ids)} shared ids, {len(dup_text)} shared texts"
        )


def stratified_split(
    items: list[dict], seed: int = 42, val_frac: float = 0.15, test_frac: float = 0.15
) -> dict[str, list[dict]]:
    """Stratified train/val/test split, deterministic for a fixed seed."""
    import random

    rng = random.Random(seed)
    by_label: dict[str, list[dict]] = {label: [] for label in LABELS}
    for item in items:
        by_label[item["label"]].append(item)
    splits: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    for label, group in by_label.items():
        rng.shuffle(group)
        n = len(group)
        n_test = max(1, round(n * test_frac))
        n_val = max(1, round(n * val_frac))
        splits["test"].extend(group[:n_test])
        splits["val"].extend(group[n_test : n_test + n_val])
        splits["train"].extend(group[n_test + n_val :])
    for split in splits.values():
        rng.shuffle(split)
    return splits


def describe(items: list[dict]) -> str:
    counts = Counter((i["label"], i["lang"]) for i in items)
    lines = [f"total={len(items)}"]
    for label in LABELS:
        langs = {lang: counts[(label, lang)] for lang in ("en", "hi", "hinglish")}
        lines.append(f"  {label}: " + " ".join(f"{k}={v}" for k, v in langs.items()))
    return "\n".join(lines)
