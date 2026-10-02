"""TF-IDF + logistic regression baseline (the number to beat, per plan).

Word unigrams+bigrams plus character 3-5 grams: char grams carry the
Hinglish/Devanagari signal where word tokens fragment. Class-balanced,
fixed seed. Artifacts land in api/ml/artifacts/.
"""

from __future__ import annotations

import json
from pathlib import Path

from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"


def build_model() -> make_pipeline:
    word_vec = TfidfVectorizer(
        ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=20000
    )
    char_vec = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True,
        max_features=30000,
    )
    clf = LogisticRegression(
        max_iter=2000, class_weight="balanced", C=2.0, random_state=42
    )
    return word_vec, char_vec, clf


def train(train_texts: list[str], train_ids: list[int]) -> dict:
    word_vec, char_vec, clf = build_model()
    X = hstack([word_vec.fit_transform(train_texts), char_vec.fit_transform(train_texts)])
    clf.fit(X, train_ids)
    return {"word_vec": word_vec, "char_vec": char_vec, "clf": clf}


def predict(model: dict, texts: list[str]) -> list[int]:
    import numpy as np

    X = hstack(
        [model["word_vec"].transform(texts), model["char_vec"].transform(texts)]
    )
    return [int(i) for i in model["clf"].predict(X)]


def save(model: dict, path: Path = ARTIFACTS / "baseline.json") -> None:
    import pickle

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)
    meta = {"model": "tfidf-word+char_logreg", "labels": ["education", "mixed", "promotion"]}
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
