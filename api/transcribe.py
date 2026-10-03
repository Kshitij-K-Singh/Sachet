"""Audio/video transcription via local Whisper.cpp (base multilingual).

Pipeline: upload -> ffmpeg (16 kHz mono wav, max 180 s) -> whisper-cli ->
script routing -> Devanagari normalization for Hindi. Temp files are
always deleted. Nothing is stored.

Language routing: explicit hint (hi/en) forces the decoder language.
Auto mode runs once and routes on output script: Perso-Arabic output is
transliterated to Devanagari (Whisper spells Hindi words correctly but
in the wrong script); Devanagari passes through; anything else is
treated as English. The user always sees the transcript and can retry
with an explicit hint.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

try:  # package import (uvicorn main:app with api/ as package root)
    from .transliterate import transliterate
    from .errors import PipelineError
except ImportError:  # top-level import (pytest run inside api/)
    from transliterate import transliterate
    from errors import PipelineError

HERE = Path(__file__).resolve().parent
WHISPER_BIN = HERE / "whisper.cpp" / "build" / "bin" / "whisper-cli"
MODEL_PATH = HERE / "whisper.cpp" / "models" / "ggml-base.bin"

MAX_BYTES = 25 * 1024 * 1024
MAX_SEC = 180
TIMEOUT_SEC = 300

ALLOWED_EXT = {
    ".mp3", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".flac", ".opus",
    ".mp4", ".mov", ".webm", ".mkv",
}

_SEGMENT_RE = re.compile(r"^\[.*?-->\s*.*?\]\s*", re.MULTILINE)
_URDU_RE = re.compile(r"[\u0600-\u06FF]")
_DEVA_RE = re.compile(r"[\u0900-\u097F]")


def _run(cmd: list[str], timeout: int = TIMEOUT_SEC) -> tuple[str, str]:
    """Run a subprocess. Returns (stdout, stderr); whisper segments print
    to stdout while engine logs go to stderr, so callers must not mix them."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise PipelineError("Transcription took too long; try a shorter clip.", 504)
    if proc.returncode != 0:
        raise PipelineError("Could not process that file. Try MP3, WAV, or MP4.", 400)
    return proc.stdout, proc.stderr


def extract_wav(src: Path, dst: Path) -> float:
    """Normalize any supported upload to 16 kHz mono wav, capped at MAX_SEC."""
    info, _ = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(src),
    ], timeout=60)
    try:
        duration = float(info.strip().split()[0])
    except (ValueError, IndexError):
        raise PipelineError("Could not read that file. Try MP3, WAV, or MP4.", 400)
    if duration > MAX_SEC + 1:
        raise PipelineError(
            f"Clip is {duration:.0f}s; the limit is {MAX_SEC}s. Trim it and retry.", 413
        )
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src),
        "-ac", "1", "-ar", "16000", "-t", str(MAX_SEC), str(dst),
    ], timeout=120)
    return min(duration, MAX_SEC)


def _clean(raw: str) -> str:
    text = _SEGMENT_RE.sub("", raw)
    return re.sub(r"\s+", " ", text).strip()


def _whisper(wav: Path, language: str | None) -> str:
    cmd = [str(WHISPER_BIN), "-m", str(MODEL_PATH), "-f", str(wav),
           "--no-prints", "-t", "8"]
    if language:
        cmd += ["--language", language]
    stdout, _ = _run(cmd)
    return _clean(stdout)


def normalize_transcript(text: str, language_hint: str = "auto") -> tuple[str, str]:
    """Apply an explicit hint plus script routing to raw text.

    Shared by the audio path (decoder output) and the paste-a-link path (caption
    track text) so both classify language identically -- otherwise the same reel
    could report a different detected_language depending on how it arrived.

    Returns (text, detected_language).
    """
    if language_hint == "hi":
        return transliterate(text), "hi"
    if language_hint == "en":
        return text, "en"
    if _URDU_RE.search(text):
        # Whisper spells Hindi words correctly but in the wrong script.
        return transliterate(text), "hi"
    if _DEVA_RE.search(text):
        return text, "hi"
    return text, "en"


def transcribe_file(src: Path, language_hint: str = "auto") -> dict:
    """Full pipeline for one uploaded file. Raises PipelineError."""
    if not WHISPER_BIN.exists() or not MODEL_PATH.exists():
        raise PipelineError("Transcription engine not installed on this server.", 500)

    decoder_lang = {"hi": "hi", "en": "en"}.get(language_hint)
    with tempfile.TemporaryDirectory(prefix="sachet-") as tmp:
        wav = Path(tmp) / "audio.wav"
        duration = extract_wav(src, wav)
        raw = _whisper(wav, decoder_lang)

    transcript, detected = normalize_transcript(raw, language_hint)
    if not transcript:
        raise PipelineError("No speech detected in that clip.", 400)
    return {
        "transcript": transcript,
        "detected_language": detected,
        "duration_sec": round(duration, 1),
        "model": "whisper-base (whisper.cpp, local)",
    }
