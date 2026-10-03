"""Classifier shadow inference: LoRA MuRIL loaded lazily, once per process.

The heuristic analyzer stays the decision-maker (it explains every claim).
The model only offers a second opinion with its confidence, clearly marked
pre-review until the gold dataset lands. Disabled entirely when the
SACHET_MODEL env var is "off" or artifacts are absent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

LABELS = ["education", "mixed", "promotion"]
ADAPTER_DIR = Path(__file__).resolve().parent / "artifacts" / "muril-lora"

_loaded: dict | None = None
_disabled = object()


def _load() -> dict | object:
    global _loaded
    if _loaded is not None:
        return _loaded
    if os.environ.get("SACHET_MODEL") == "off":
        _loaded = _disabled
        return _loaded
    if not (ADAPTER_DIR / "adapter_model.safetensors").exists():
        _loaded = _disabled
        return _loaded
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError:
        # Slim runtime image ships without torch/transformers: the shadow
        # classifier is optional (hidden in the UI), so degrade to None
        # instead of crashing the /api/analyze endpoint.
        _loaded = _disabled
        return _loaded

    base_name = json.loads((ADAPTER_DIR / "adapter_config.json").read_text()).get(
        "base_model_name_or_path", "google/muril-base-cased"
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(base_name)
    base = AutoModelForSequenceClassification.from_pretrained(base_name, num_labels=3)
    model = PeftModel.from_pretrained(base, str(ADAPTER_DIR)).to(device)
    model.eval()
    _loaded = {"tok": tok, "model": model, "device": device, "torch": torch}
    return _loaded


def second_opinion(text: str) -> dict | None:
    """Return {label, confidence} or None when the model is unavailable."""
    bundle = _load()
    if bundle is _disabled or not text.strip():
        return None
    try:
        import torch
    except ImportError:
        return None

    assert isinstance(bundle, dict)
    tok, model, device = bundle["tok"], bundle["model"], bundle["device"]
    enc = tok(text.strip()[:2000], truncation=True, max_length=256, return_tensors="pt")
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        logits = model(**enc).logits[0]
    probs = logits.softmax(dim=-1).tolist()
    best = max(range(3), key=lambda i: probs[i])
    return {"label": LABELS[best], "confidence": round(probs[best], 3)}
