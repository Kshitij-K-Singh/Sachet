"""Linear probe: frozen MuRIL mean-pooled embeddings + logistic regression.

The stable small-data alternative to LoRA: no gradient updates to the
encoder, so 178 examples cannot collapse training. Same splits and same
report format as the baseline for direct comparison.

Usage:  .venv/bin/python -m ml.probe [--model google/muril-base-cased]
"""

from __future__ import annotations

import argparse

import numpy as np


def embed(texts: list[str], model_name: str, batch_size: int = 32) -> np.ndarray:
    import torch
    from transformers import AutoModel, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_name)
    enc = AutoModel.from_pretrained(model_name)
    enc.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    enc.to(device)
    out: list[np.ndarray] = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = tok(
                texts[i : i + batch_size], truncation=True, padding=True,
                max_length=256, return_tensors="pt",
            ).to(device)
            hidden = enc(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-6)
            out.append(pooled.cpu().numpy())
    return np.concatenate(out)


def main() -> None:
    from sklearn.linear_model import LogisticRegression

    from . import dataset, evaluate

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/muril-base-cased")
    args = parser.parse_args()

    items, reviewed = dataset.load_items()
    print(dataset.describe(items))
    print("data status:", "REVIEWED" if reviewed else "PRE-REVIEW (candidates only)")
    splits = dataset.stratified_split(items)

    print("embedding train...")
    X_train = embed([i["text"] for i in splits["train"]], args.model)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0, random_state=42)
    clf.fit(X_train, [i["label_id"] for i in splits["train"]])

    for split in ("val", "test"):
        X = embed([i["text"] for i in splits[split]], args.model)
        pred = [int(i) for i in clf.predict(X)]
        print()
        print(evaluate.report(
            [i["label_id"] for i in splits[split]], pred, f"probe({args.model})/{split}"
        ))


if __name__ == "__main__":
    main()
