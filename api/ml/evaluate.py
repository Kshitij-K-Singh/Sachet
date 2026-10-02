"""Evaluation: accuracy, per-class P/R/F1, confusion matrix, and the metric
judges care about: the false-positive rate on educational content
(education items classified as mixed or promotion).
"""

from __future__ import annotations

from sklearn.metrics import classification_report, confusion_matrix

LABELS = ["education", "mixed", "promotion"]


def report(y_true: list[int], y_pred: list[int], title: str = "") -> str:
    lines = []
    if title:
        lines.append(f"== {title} ==")
    acc = sum(a == b for a, b in zip(y_true, y_pred)) / max(len(y_true), 1)
    lines.append(f"accuracy: {acc:.3f}  (n={len(y_true)})")
    lines.append(classification_report(y_true, y_pred, target_names=LABELS, digits=3))
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2])
    lines.append("confusion matrix (rows=true edu/mix/pro, cols=pred edu/mix/pro):")
    for row in cm:
        lines.append("  " + " ".join(f"{v:4d}" for v in row))
    edu_idx = [i for i, t in enumerate(y_true) if t == 0]
    fp_edu = sum(1 for i in edu_idx if y_pred[i] != 0)
    lines.append(
        f"false-positive rate on education: {fp_edu}/{len(edu_idx)} = "
        f"{fp_edu / max(len(edu_idx), 1):.3f}"
    )
    return "\n".join(lines)
