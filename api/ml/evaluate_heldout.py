"""Score a trained model on the HELD-OUT set.

The held-out set is authored separately from the training pool and is never
returned by load_items, so it cannot be trained on. Batch 1+2's random split
could not make that claim: train and test shared a generator, and the README
already flagged the risk that the model was keying on template artifacts.

Usage:
  .venv/bin/python -m ml.evaluate_heldout            # TF-IDF + probe + LoRA
  .venv/bin/python -m ml.evaluate_heldout --only lora
"""

from __future__ import annotations

import argparse

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import make_pipeline

from . import dataset, evaluate

ARTIFACTS = __import__("pathlib").Path(__file__).resolve().parent / "artifacts"


def run_tfidf(train: list[dict], splits: dict[str, list[dict]]):
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    pipe = make_pipeline(vec, clf)
    pipe.fit([i["text"] for i in train], [i["label_id"] for i in train])
    return {
        name: pipe.predict([i["text"] for i in ds]).tolist()
        for name, ds in splits.items()
    }


def run_probe(train: list[dict], splits: dict[str, list[dict]], model_name: str):
    from transformers import AutoModel, AutoTokenizer
    import torch

    tok = AutoTokenizer.from_pretrained(model_name)
    enc = AutoModel.from_pretrained(model_name)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced")

    def embed(texts: list[str]):
        e = tok(texts, truncation=True, padding=True, max_length=256, return_tensors="pt")
        with torch.no_grad():
            out = enc(**e).last_hidden_state[:, 0]
        return out.numpy()

    clf.fit(embed([i["text"] for i in train]), [i["label_id"] for i in train])
    return {n: clf.predict(embed([i["text"] for i in ds])).tolist() for n, ds in splits.items()}


def run_lora(splits: dict[str, list[dict]]):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    adapter = ARTIFACTS / "muril-lora"
    if not (adapter / "adapter_model.safetensors").exists():
        print("no LoRA adapter yet; skipping (run ml.finetune first)")
        return None
    tok = AutoTokenizer.from_pretrained(str(adapter))
    base = AutoModelForSequenceClassification.from_pretrained(
        "google/muril-base-cased", num_labels=3
    )
    model = PeftModel.from_pretrained(base, str(adapter))
    model.eval()
    preds = {}
    for name, ds in splits.items():
        out = []
        texts = [i["text"] for i in ds]
        for s in range(0, len(texts), 16):
            e = tok(texts[s : s + 16], truncation=True, padding=True,
                    max_length=256, return_tensors="pt")
            with torch.no_grad():
                out.extend(model(**e).logits.argmax(-1).tolist())
        preds[name] = out
    return preds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["tfidf", "probe", "lora"], default=None)
    args = ap.parse_args()

    train_pool, reviewed = dataset.load_items()
    splits = dataset.stratified_split(train_pool, seed=42)
    heldout = dataset.load_heldout()
    dataset.assert_disjoint(splits["train"], heldout)
    splits["HELDOUT"] = heldout

    print(f"train pool {len(train_pool)} | train {len(splits['train'])} "
          f"val {len(splits['val'])} test {len(splits['test'])} | "
          f"HELD-OUT {len(heldout)}")
    print("data status:", "REVIEWED" if reviewed else "PRE-REVIEW (candidates only)")
    print()

    which = [args.only] if args.only else ["tfidf", "probe", "lora"]
    if "tfidf" in which:
        p = run_tfidf(splits["train"], splits)
        for n in ("test", "HELDOUT"):
            print(evaluate.report(
                [i["label_id"] for i in splits[n]], p[n], f"TF-IDF+LogReg / {n}"))
            print()
    if "probe" in which:
        p = run_probe(splits["train"], splits, "google/muril-base-cased")
        for n in ("test", "HELDOUT"):
            y = [i["label_id"] for i in splits[n]]
            print(f"== frozen MuRIL probe / {n} ==")
            print(f"accuracy: {np.mean([a==b for a,b in zip(y,p[n])]):.3f}  "
                  f"macro_f1: {f1_score(y, p[n], average='macro'):.3f}  (n={len(y)})")
            print()
    if "lora" in which:
        p = run_lora(splits)
        if p:
            for n in ("test", "HELDOUT"):
                print(evaluate.report(
                    [i["label_id"] for i in splits[n]], p[n], f"LoRA MuRIL / {n}"))
                print()


if __name__ == "__main__":
    main()
