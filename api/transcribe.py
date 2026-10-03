"""Audio/video transcription via a hosted speech-to-text API.

Pipeline: upload -> ffmpeg (16 kHz mono wav, max 180 s) -> hosted STT
(OpenAI-compatible `POST {endpoint}/audio/transcriptions`) -> script
routing -> Devanagari normalization for Hindi. Temp files are always
deleted. Nothing is stored.

Why hosted: the old local whisper.cpp path required compiling C++ from
source on every Docker build and ran base-model CPU inference (tens of
seconds per clip). A hosted large-model endpoint builds in seconds
(no compiler, no torch, no model download) and transcribes a 3-minute
clip in seconds instead of minutes, with accuracy at least as good as
whisper-base on Hindi/Hinglish code-switch.

Language routing: explicit hint (hi/en) forces the decoder language.
Auto mode lets the provider detect, then routes on output script:
Perso-Arabic output is transliterated to Devanagari (models spell Hindi
words correctly but in the wrong script); Devanagari passes through;
anything else is treated as English. The user always sees the transcript
and can retry with an explicit hint.

Configuration (environment):
  SACHET_STT_PROVIDER  auto | groq | openai | compatible (default: auto)
  SACHET_STT_ENDPOINT  explicit base URL, e.g. https://api.groq.com/openai/v1
                       (covers Groq, OpenAI, Together, Fireworks, Sarvam
                       OpenAI-compatible gateways, self-hosted, ...)
  SACHET_STT_MODEL     explicit model id (default depends on provider)
  SACHET_STT_API_KEY   explicit bearer token
  GROQ_API_KEY         shortcut: endpoint=https://api.groq.com/openai/v1,
                       model defaults to whisper-large-v3-turbo
  OPENAI_API_KEY       shortcut: endpoint=https://api.openai.com/v1,
                       model defaults to whisper-1
  SACHET_STT_TIMEOUT   HTTP timeout in seconds (default: 60)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

try:  # package import (uvicorn main:app with api/ as package root)
    from .transliterate import transliterate
    from .errors import PipelineError
except ImportError:  # top-level import (pytest run inside api/)
    from transliterate import transliterate
    from errors import PipelineError

HERE = Path(__file__).resolve().parent

MAX_BYTES = 25 * 1024 * 1024
MAX_SEC = 180
TIMEOUT_SEC = int(os.environ.get("SACHET_STT_TIMEOUT", "60"))

ALLOWED_EXT = {
    ".mp3", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".flac", ".opus",
    ".mp4", ".mov", ".webm", ".mkv",
}

_URDU_RE = re.compile(r"[\u0600-\u06FF]")
_DEVA_RE = re.compile(r"[\u0900-\u097F]")

_DEFAULT_GROQ_ENDPOINT = "https://api.groq.com/openai/v1"
_DEFAULT_OPENAI_ENDPOINT = "https://api.openai.com/v1"
_DEFAULT_GROQ_MODEL = "whisper-large-v3-turbo"
_DEFAULT_OPENAI_MODEL = "whisper-1"

# Cloudflare (in front of api.groq.com) bans default library user-agents
# ("Python-urllib/3.x" -> HTTP 403 "error code: 1010"). Identify the app
# instead; a custom UA passes while the stdlib default does not.
_USER_AGENT = "Sachet/1.0 (+https://github.com/Kshitij-K-Singh/Sachet)"


def _run(cmd: list[str], timeout: int = 120) -> tuple[str, str]:
    """Run a subprocess (ffmpeg/ffprobe only)."""
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


def _resolve_stt_config() -> tuple[str, str, str, str]:
    """Return (endpoint, api_key, model, provider_label).

    Raises PipelineError(500) when no provider is configured.
    """
    provider = os.environ.get("SACHET_STT_PROVIDER", "auto").strip().lower() or "auto"
    endpoint = os.environ.get("SACHET_STT_ENDPOINT", "").strip().rstrip("/")
    model = os.environ.get("SACHET_STT_MODEL", "").strip()
    api_key = os.environ.get("SACHET_STT_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if provider in ("auto", "groq", "compatible", "openai"):
        if endpoint and api_key:
            label = provider if provider != "auto" else "hosted"
            return endpoint, api_key, model or _DEFAULT_GROQ_MODEL, label
        if groq_key and provider in ("auto", "groq"):
            return (
                _DEFAULT_GROQ_ENDPOINT,
                groq_key,
                model or _DEFAULT_GROQ_MODEL,
                "groq",
            )
        if openai_key and provider in ("auto", "openai"):
            return (
                _DEFAULT_OPENAI_ENDPOINT,
                openai_key,
                model or _DEFAULT_OPENAI_MODEL,
                "openai",
            )
        if endpoint or api_key or model:
            # Half-configured: tell the operator exactly what is missing
            # instead of failing later with an opaque 401 from the provider.
            raise PipelineError(
                "Speech transcription is half-configured: set both "
                "SACHET_STT_ENDPOINT and SACHET_STT_API_KEY (or use "
                "GROQ_API_KEY / OPENAI_API_KEY).",
                500,
            )
    raise PipelineError(
        "Transcription is not configured on this server (set GROQ_API_KEY "
        "or OPENAI_API_KEY, or SACHET_STT_ENDPOINT + SACHET_STT_API_KEY).",
        500,
    )


def _encode_multipart(
    fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]
) -> tuple[bytes, str]:
    """Minimal multipart/form-data encoder (stdlib only, no requests dep)."""
    boundary = f"----sachet-{uuid.uuid4().hex}"
    buf = bytearray()
    for name, value in fields.items():
        buf += f"--{boundary}\r\n".encode()
        buf += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        buf += f"{value}\r\n".encode()
    for name, (filename, data, content_type) in files.items():
        buf += f"--{boundary}\r\n".encode()
        buf += (
            f'Content-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\n'
        ).encode()
        buf += f"Content-Type: {content_type}\r\n\r\n".encode()
        buf += data
        buf += b"\r\n"
    buf += f"--{boundary}--\r\n".encode()
    return bytes(buf), f"multipart/form-data; boundary={boundary}"


def _stt_post(endpoint: str, api_key: str, body: bytes, content_type: str) -> dict:
    url = endpoint + "/audio/transcriptions"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = ""
        if e.code == 401:
            raise PipelineError(
                "Transcription credentials were rejected. Check the STT API key.", 500
            )
        if e.code == 403:
            # Usually NOT the key: provider WAF/bot block or a key-scoped
            # restriction. Surface the body so the cause is diagnosable.
            raise PipelineError(
                f"Transcription refused ({e.code}). {detail}".strip(), 502
            )
        if e.code == 429:
            raise PipelineError(
                "Transcription is rate-limited right now. Retry in a moment.", 503
            )
        raise PipelineError(
            f"Transcription failed ({e.code}). {detail}".strip(), 502
        )
    except urllib.error.URLError:
        raise PipelineError(
            "Could not reach the transcription service. Retry in a moment.", 502
        )
    except TimeoutError:
        raise PipelineError("Transcription took too long; try a shorter clip.", 504)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise PipelineError("Transcription returned an unreadable response.", 502)
    if not isinstance(data, dict):
        raise PipelineError("Transcription returned an unreadable response.", 502)
    return data


def _transcribe_wav(wav: Path, language: str | None) -> tuple[str, str, str]:
    """Send one normalized wav to the hosted STT API. Returns (text, model, label)."""
    endpoint, api_key, model, label = _resolve_stt_config()
    fields: dict[str, str] = {"model": model, "response_format": "json", "temperature": "0"}
    if language:
        fields["language"] = language
    try:
        audio = wav.read_bytes()
    except OSError:
        raise PipelineError("Could not read that file. Try MP3, WAV, or MP4.", 400)
    body, content_type = _encode_multipart(
        fields, {"file": (wav.name, audio, "audio/wav")}
    )
    data = _stt_post(endpoint, api_key, body, content_type)
    text = data.get("text", "")
    if not isinstance(text, str):
        raise PipelineError("Transcription returned an unreadable response.", 502)
    text = re.sub(r"\s+", " ", text).strip()
    return text, model, label


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
        # Models spell Hindi words correctly but in the wrong script.
        return transliterate(text), "hi"
    if _DEVA_RE.search(text):
        return text, "hi"
    return text, "en"


def transcribe_file(src: Path, language_hint: str = "auto") -> dict:
    """Full pipeline for one uploaded file. Raises PipelineError."""
    decoder_lang = {"hi": "hi", "en": "en"}.get(language_hint)
    with tempfile.TemporaryDirectory(prefix="sachet-") as tmp:
        wav = Path(tmp) / "audio.wav"
        duration = extract_wav(src, wav)
        raw, model, label = _transcribe_wav(wav, decoder_lang)

    transcript, detected = normalize_transcript(raw, language_hint)
    if not transcript:
        raise PipelineError("No speech detected in that clip.", 400)
    return {
        "transcript": transcript,
        "detected_language": detected,
        "duration_sec": round(duration, 1),
        "model": f"{model} ({label}, hosted)",
    }
