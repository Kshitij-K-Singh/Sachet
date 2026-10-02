"""Train + evaluate the baseline in one command.

Usage:  .venv/bin/python -m ml.train_baseline [--seed 42]
"""

from __future__ import annotations

import argparse

from . import baseline, dataset, evaluate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    items, reviewed = dataset.load_items()
    print(dataset.describe(items))
    print("data status:", "REVIEWED" if reviewed else "PRE-REVIEW (candidates only)")

    splits = dataset.stratified_split(items, seed=args.seed)
    print({k: len(v) for k, v in splits.items()})

    model = baseline.train(
        [i["text"] for i in splits["train"]], [i["label_id"] for i in splits["train"]]
    )
    baseline.save(model)

    for split in ("val", "test"):
        pred = baseline.predict(model, [i["text"] for i in splits[split]])
        print()
        print(evaluate.report([i["label_id"] for i in splits[split]], pred, f"baseline/{split}"))


if __name__ == "__main__":
    main()
