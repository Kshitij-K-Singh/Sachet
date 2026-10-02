"""OCR tests: fixtures are committed PNGs, so these run fully offline
after the one-time EasyOCR model download."""

from pathlib import Path

import pytest

from errors import PipelineError
from ocr import ocr_image

FIX = Path(__file__).resolve().parent / "data" / "fixtures"


def test_english_screenshot_reads_and_flags():
    out = ocr_image(FIX / "shot_en.png")
    lowered = out["text"].lower()
    assert "guaranteed returns" in lowered
    assert "premium group" in lowered
    from analyzer import analyze_text

    assert analyze_text(out["text"])["classification"] == "promotion"


def test_hindi_screenshot_reads_and_flags():
    out = ocr_image(FIX / "shot_hi.png")
    assert "पक्का" in out["text"] or "प्रीमियम" in out["text"]
    from analyzer import analyze_text

    assert analyze_text(out["text"])["classification"] == "promotion"


def test_blank_image_reports_no_text(tmp_path):
    from PIL import Image

    blank = tmp_path / "blank.png"
    Image.new("RGB", (400, 200), (18, 15, 11)).save(blank)
    with pytest.raises(PipelineError):
        ocr_image(blank)


def test_corrupt_image_rejected(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    with pytest.raises(PipelineError):
        ocr_image(bad)
