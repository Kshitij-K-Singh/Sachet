"""Screenshot OCR via local EasyOCR (Hindi + English), GPU when available.

Pipeline: upload -> sanity checks -> EasyOCR hi+en -> blocks in reading
order -> joined text. Temp files are always deleted. Nothing is stored.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from errors import PipelineError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_SIDE_PX = 4000
MIN_CONFIDENCE = 0.25

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

_reader = None


def get_reader():
    """Lazy singleton: model download + GPU init happen once, not per request."""
    global _reader
    if _reader is None:
        import easyocr
        import torch

        _reader = easyocr.Reader(["hi", "en"], gpu=torch.cuda.is_available())
    return _reader


def ocr_image(src: Path) -> dict:
    """OCR one image file. Raises PipelineError."""
    try:
        with Image.open(src) as img:
            img.verify()
        with Image.open(src) as img:
            w, h = img.size
    except Exception:
        raise PipelineError("Could not read that image. Send JPG, PNG, or WebP.")
    if max(w, h) > MAX_SIDE_PX:
        raise PipelineError("Image too large; 4000px per side max.", 413)

    results = get_reader().readtext(str(src))
    blocks = [
        {"text": text.strip(), "confidence": round(float(conf), 3)}
        for (_, text, conf) in results
        if text and text.strip() and float(conf) >= MIN_CONFIDENCE
    ]
    if not blocks:
        raise PipelineError("No readable text found in that screenshot.", 400)
    return {
        "text": "\n".join(b["text"] for b in blocks),
        "blocks": blocks,
        "model": "easyocr hi+en (local)",
    }
