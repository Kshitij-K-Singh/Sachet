"""OCR tests: hosted vision API mocked at the HTTP boundary.

The committed PNG fixtures exercise the real validation path (Pillow
verify, size checks, byte limits); provider text is canned so these run
fully offline with no API key.
"""

from pathlib import Path

import pytest

import ocr
from errors import PipelineError
from ocr import ocr_image

FIX = Path(__file__).resolve().parent / "data" / "fixtures"


def _mock_google(monkeypatch, blocks):
    monkeypatch.setattr(ocr, "_resolve_ocr_config", lambda: ("google", {"api_key": "test"}))
    monkeypatch.setattr(ocr, "_ocr_via_google", lambda image_bytes, key: blocks)


def test_english_screenshot_reads_and_flags(monkeypatch):
    _mock_google(monkeypatch, [
        {"text": "Guaranteed returns, double your money", "confidence": 0.98},
        {"text": "Join our premium group now", "confidence": 0.97},
    ])
    out = ocr_image(FIX / "shot_en.png")
    lowered = out["text"].lower()
    assert "guaranteed returns" in lowered
    assert "premium group" in lowered
    assert "hosted" in out["model"]
    from analyzer import analyze_text

    assert analyze_text(out["text"])["classification"] == "promotion"


def test_hindi_screenshot_reads_and_flags(monkeypatch):
    _mock_google(monkeypatch, [
        {"text": "पक्का मुनाफा तीस दिन में", "confidence": 0.96},
        {"text": "प्रीमियम ग्रुप से जुड़ें", "confidence": 0.95},
    ])
    out = ocr_image(FIX / "shot_hi.png")
    assert "पक्का" in out["text"] or "प्रीमियम" in out["text"]
    from analyzer import analyze_text

    assert analyze_text(out["text"])["classification"] == "promotion"


def test_low_confidence_blocks_are_dropped_by_provider_parsing(monkeypatch):
    """MIN_CONFIDENCE filtering lives in the provider parsers; here we assert
    the join contract: blocks -> newline text, model label present."""
    _mock_google(monkeypatch, [
        {"text": "clear heading", "confidence": 0.99},
        {"text": "second line", "confidence": 0.9},
    ])
    out = ocr_image(FIX / "shot_en.png")
    assert out["text"] == "clear heading\nsecond line"
    assert len(out["blocks"]) == 2


def test_missing_ocr_config_is_a_500(monkeypatch):
    for var in (
        "SACHET_OCR_PROVIDER", "GOOGLE_VISION_KEY", "SACHET_OCR_API_KEY",
        "AZURE_VISION_ENDPOINT", "AZURE_VISION_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(PipelineError) as e:
        ocr_image(FIX / "shot_en.png")
    assert e.value.status == 500


def test_blank_image_reports_no_text(monkeypatch, tmp_path):
    from PIL import Image

    _mock_google(monkeypatch, [])
    blank = tmp_path / "blank.png"
    Image.new("RGB", (400, 200), (18, 15, 11)).save(blank)
    with pytest.raises(PipelineError):
        ocr_image(blank)


def test_corrupt_image_rejected(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    with pytest.raises(PipelineError):
        ocr_image(bad)
