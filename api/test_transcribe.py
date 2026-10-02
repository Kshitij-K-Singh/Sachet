"""Transcription tests. Speech-fixture tests skip when fixtures are absent;
mechanics + transliteration tests always run offline."""

import subprocess
from pathlib import Path

import pytest

from transcribe import PipelineError, extract_wav
from transcribe import transcribe_file
from transliterate import transliterate

EN_CLIP = Path(__file__).resolve().parent / "data" / "fixtures" / "clip_en.mp3"
HI_CLIP = Path(__file__).resolve().parent / "data" / "fixtures" / "clip_hi.mp3"


def test_transliterate_urdu_to_devanagari():
    out = transliterate("پککہ منافہ تیس دن میں پیسہ دبل")
    assert out == "पक्का मुनाफा तीस दिन में पैसा डबल"


def test_transliterate_leaves_latin_and_devanagari():
    assert transliterate("Join now, दोस्तों!") == "Join now, दोस्तों!"


def test_transliterate_bigram_join():
    assert "जॉइन करें" in transliterate("گروپ جون کریں")


def test_extract_wav_from_audio(tmp_path):
    tone = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-ac", "1", "-ar", "16000", str(tone)],
        check=True,
    )
    out = tmp_path / "out.wav"
    assert extract_wav(tone, out) == pytest.approx(2.0, abs=0.2)
    assert out.exists()


def test_extract_rejects_unreadable(tmp_path):
    bad = tmp_path / "bad.mp3"
    bad.write_bytes(b"not audio at all")
    with pytest.raises(PipelineError):
        extract_wav(bad, tmp_path / "out.wav")


def test_duration_cap_enforced(monkeypatch, tmp_path):
    import transcribe as t

    monkeypatch.setattr(t, "MAX_SEC", 1)
    tone = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-ac", "1", "-ar", "16000", str(tone)],
        check=True,
    )
    with pytest.raises(PipelineError) as e:
        extract_wav(tone, tmp_path / "out.wav")
    assert e.value.status == 413


@pytest.mark.skipif(not EN_CLIP.exists(), reason="no EN speech fixture")
def test_english_clip_end_to_end():
    out = transcribe_file(EN_CLIP, "en")
    assert "guaranteed returns" in out["transcript"].lower()
    assert "premium group" in out["transcript"].lower()
    assert out["detected_language"] == "en"


@pytest.mark.skipif(not HI_CLIP.exists(), reason="no HI speech fixture")
def test_hindi_clip_pipeline_is_flaggable():
    # wav-path Hindi decodes to Latin transliteration; the rubric must
    # still flag it (Devanagari normalization is unit-tested above).
    out = transcribe_file(HI_CLIP, "hi")
    lowered = out["transcript"].lower()
    assert "pakka" in lowered or "पक्का" in out["transcript"]
    assert "premium" in lowered or "प्रीमियम" in out["transcript"]
    from analyzer import analyze_text

    verdict = analyze_text(out["transcript"])
    assert verdict["classification"] == "promotion"
