"""Transcription tests. Hosted STT is mocked at the HTTP boundary;
mechanics + transliteration tests run fully offline with ffmpeg only."""

import subprocess
from pathlib import Path

import pytest

import transcribe
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


def test_missing_stt_config_is_a_500(monkeypatch, tmp_path):
    """No API key anywhere -> clean 500, not a crash or a network call."""
    for var in (
        "SACHET_STT_PROVIDER", "SACHET_STT_ENDPOINT", "SACHET_STT_MODEL",
        "SACHET_STT_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    tone = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-ac", "1", "-ar", "16000", str(tone)],
        check=True,
    )
    with pytest.raises(PipelineError) as e:
        transcribe_file(tone, "en")
    assert e.value.status == 500
    assert "GROQ_API_KEY" in str(e)


def _mock_stt(monkeypatch, text, model="whisper-large-v3-turbo", label="groq"):
    monkeypatch.setattr(
        transcribe, "_transcribe_wav", lambda wav, lang: (text, model, label)
    )


@pytest.mark.skipif(not EN_CLIP.exists(), reason="no EN speech fixture")
def test_english_clip_end_to_end(monkeypatch):
    _mock_stt(
        monkeypatch,
        "Guaranteed returns! Double your money in 30 days. Join our premium group now!",
    )
    out = transcribe_file(EN_CLIP, "en")
    assert "guaranteed returns" in out["transcript"].lower()
    assert "premium group" in out["transcript"].lower()
    assert out["detected_language"] == "en"
    assert "hosted" in out["model"]


@pytest.mark.skipif(not HI_CLIP.exists(), reason="no HI speech fixture")
def test_hindi_clip_pipeline_is_flaggable(monkeypatch):
    # wav-path Hindi decodes to Latin transliteration; the rubric must
    # still flag it (Devanagari normalization is unit-tested above).
    _mock_stt(monkeypatch, "pakka munafa, double paisa in 30 days! Join our premium group now, limited seats, hurry!")
    out = transcribe_file(HI_CLIP, "hi")
    lowered = out["transcript"].lower()
    assert "pakka" in lowered or "पक्का" in out["transcript"]
    assert "premium" in lowered or "प्रीमियम" in out["transcript"]
    from analyzer import analyze_text

    verdict = analyze_text(out["transcript"])
    assert verdict["classification"] == "promotion"


def test_stt_config_prefers_explicit_endpoint(monkeypatch):
    monkeypatch.setenv("SACHET_STT_ENDPOINT", "https://example.test/v1")
    monkeypatch.setenv("SACHET_STT_API_KEY", "sk-test")
    monkeypatch.setenv("SACHET_STT_MODEL", "custom-model")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    endpoint, key, model, _ = transcribe._resolve_stt_config()
    assert endpoint == "https://example.test/v1"
    assert key == "sk-test"
    assert model == "custom-model"


def test_stt_config_groq_shortcut(monkeypatch):
    for var in ("SACHET_STT_ENDPOINT", "SACHET_STT_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.delenv("SACHET_STT_MODEL", raising=False)
    endpoint, key, model, label = transcribe._resolve_stt_config()
    assert endpoint == transcribe._DEFAULT_GROQ_ENDPOINT
    assert key == "gsk-test"
    assert model == transcribe._DEFAULT_GROQ_MODEL
    assert label == "groq"
