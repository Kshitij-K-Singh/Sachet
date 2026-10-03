"""Paste-a-link ingest for POST /api/ingest-url.

Turns a public video/reel URL into a transcript, preferring the cheap path:

  1. captions  -- yt-dlp --write-auto-subs --skip-download. Seconds, no ffmpeg,
     no STT call. This is the common case for YouTube.
  2. media     -- download the audio-only stream and run the normal
     transcribe_file() pipeline. One hosted STT call; works for reels
     and posts that ship no caption track.

Both paths land in a temp dir that is always deleted. Nothing is persisted.

SECURITY: this accepts a user-supplied URL and makes the server fetch it, which
makes it an SSRF sink. It is treated as one. See _resolve_public_url for the
two independent gates (platform allowlist, then resolved-IP check) and read the
"Residual risk" note there before widening _ALLOWED_HOSTS.
"""

from __future__ import annotations

import html
import ipaddress
import json
import os
import re
import socket
import subprocess
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

from errors import PipelineError
from transcribe import MAX_BYTES, MAX_SEC, normalize_transcript, transcribe_file

# Mirrors AnalyzeRequest.text max_length in main.py. Single source of truth:
# main.py imports this so the two can never drift apart.
MAX_ANALYZE_CHARS = 8000

YTDLP = os.environ.get("SACHET_YTDLP", "yt-dlp")
PROBE_TIMEOUT = 45
CAPTION_TIMEOUT = 45
MEDIA_TIMEOUT = 180
MAX_URL_LEN = 2048

# Platforms we accept. Short-form finance content lives here, and an explicit
# allowlist is the only control that meaningfully contains an SSRF sink: we
# cannot see what yt-dlp follows after the first request, so the first request
# must already be to a host we chose. Adding a host is a security decision, not
# a config change.
_ALLOWED_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "instagram.com",
        "www.instagram.com",
        "twitter.com",
        "www.twitter.com",
        "x.com",
        "www.x.com",
        "tiktok.com",
        "www.tiktok.com",
        "vm.tiktok.com",
    }
)

# Ranges that ipaddress's is_private/is_reserved do not reliably flag across
# Python versions. CGNAT (100.64/10) and the benchmark range (198.18/15) are
# both routable-looking but must never be reachable from a user-supplied URL.
_EXTRA_BLOCKED = tuple(
    ipaddress.ip_network(n)
    for n in ("100.64.0.0/10", "198.18.0.0/15", "192.0.0.0/24", "192.0.2.0/24")
)

# Caption languages to try, most-preferred first. Kept to two per request on
# purpose: each extra language is another chance to hit a 429. Urdu-script
# Hindi is filed under "hi" by YouTube anyway, and normalize_transcript()
# transliterates Urdu script regardless of which language code delivered it, so
# a separate "ur" request buys nothing.
#
# Ordered by the caller's hint so the usual case costs exactly one yt-dlp call.
_SUB_LANG_ORDER = {
    "hi": ("hi.*", "en.*"),
    "en": ("en.*", "hi.*"),
    "auto": ("hi.*", "en.*"),
}

_CUE_TIME_RE = re.compile(r"^\s*(\d+:)?\d\d:\d\d[.,]\d\d\d?\s*-->")
_VTT_META_RE = re.compile(r"^(WEBVTT|NOTE|STYLE|REGION|Kind:|Language:)", re.I)
_VTT_NUM_RE = re.compile(r"^\d+$")
_TAG_RE = re.compile(r"<[^>]*>")

# One slot per concurrent STT job; without a ceiling N paste requests tie up
# N times the CPU and the event loop starves. Override for a bigger box.
MAX_CONCURRENT = max(1, int(os.environ.get("SACHET_MAX_CONCURRENT_INGEST", "2")))
_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT)
_QUEUE_TIMEOUT = 30


# --------------------------------------------------------------------------- #
# SSRF guard
# --------------------------------------------------------------------------- #


def _ip_is_blocked(addr: ipaddress._BaseAddress) -> bool:
    """True if this address must never be reachable from a user-supplied URL.

    Unwraps IPv4-mapped (::ffff:127.0.0.1) and 6to4 (2002::) forms first --
    otherwise both are trivial loopback bypasses.
    """
    for attr in ("ipv4_mapped", "sixtofour"):
        inner = getattr(addr, attr, None)
        if inner is not None:
            addr = inner
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or any(addr in net for net in _EXTRA_BLOCKED)
    )


def _host_allowed(host: str) -> bool:
    """Exact host or a subdomain of an allowed platform.

    The suffix check is anchored on "." so "notyoutube.com" cannot match
    "youtube.com".
    """
    host = host.lower().rstrip(".")
    return any(host == a or host.endswith("." + a) for a in _ALLOWED_HOSTS)


def validate_url(raw: str) -> tuple[str, str]:
    """Parse and syntactically validate a paste. Returns (url, host)."""
    url = (raw or "").strip()
    if not url:
        raise PipelineError("Paste a video link first.", 400)
    if len(url) > MAX_URL_LEN:
        raise PipelineError("That link is too long.", 400)
    # Bare "youtube.com/watch?v=x" is what people actually paste.
    if "://" not in url:
        url = "https://" + url

    try:
        parts = urlparse(url)
    except ValueError:
        raise PipelineError("That does not look like a link.", 400)

    if parts.scheme.lower() not in ("http", "https"):
        raise PipelineError("Only http/https links are supported.", 400)
    if parts.username or parts.password:
        # user:pass@host is a classic parser-confusion trick.
        raise PipelineError("That link has embedded credentials; paste a plain link.", 400)
    host = parts.hostname
    if not host:
        raise PipelineError("That link has no host in it.", 400)
    return url, host.lower().rstrip(".")


def _resolve_public_url(raw: str) -> tuple[str, str]:
    """Validate the paste and confirm it points at a public platform host.

    Gate 1 (allowlist) is the strong one: it decides, before any network I/O,
    that we will only ever talk to platforms we picked.

    Gate 2 (resolved IPs) is defence in depth -- it catches an allowed hostname
    that resolves to a private address via a poisoned or hijacked DNS response.

    Residual risk, and it is real: yt-dlp resolves DNS and follows redirects
    itself, so a TOCTOU window exists between this check and its request, and we
    do not see post-redirect hops. The allowlist is what bounds the blast radius
    to "a platform we already trust fetching us"; the IP check is a tripwire, not
    a sandbox. Do not add a host here without accepting that trade.
    """
    url, host = validate_url(raw)

    if not _host_allowed(host):
        raise PipelineError(
            "That platform is not supported yet. Paste a public YouTube, Instagram, "
            "X/Twitter, or TikTok link.",
            400,
        )

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise PipelineError("Could not resolve that link. Check it and retry.", 400)

    if not infos:
        raise PipelineError("Could not resolve that link. Check it and retry.", 400)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _ip_is_blocked(ip):
            raise PipelineError("That link resolves to a blocked address.", 400)

    return url, host


# --------------------------------------------------------------------------- #
# yt-dlp plumbing
# --------------------------------------------------------------------------- #


def _base_args(workdir: Path) -> list[str]:
    return [
        YTDLP,
        "--ignore-config",       # never inherit a host ~/.config/yt-dlp
        "--no-playlist",         # one paste == one item
        "--no-cache-dir",
        "--no-progress",
        "--no-warnings",
        "--no-color",
        "--socket-timeout", "20",
        "--retries", "2",
        "--paths", str(workdir),
    ]


def _ytdlp(args: list[str], timeout: int, what: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise PipelineError(
            "Link import is unavailable on this server (yt-dlp not installed).", 500
        )
    except subprocess.TimeoutExpired:
        raise PipelineError(f"Fetching that {what} took too long.", 504)


def _probe(url: str, workdir: Path) -> dict:
    """Cheap metadata read. Runs before any download so the duration cap can
    reject a long video without pulling hundreds of megabytes first."""
    proc = _ytdlp(
        _base_args(workdir) + ["--skip-download", "--dump-single-json", url],
        PROBE_TIMEOUT,
        "link",
    )
    if proc.returncode != 0:
        raise PipelineError(_friendly_ytdlp_error(proc.stderr), 400)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise PipelineError("Could not read that link. Check it and retry.", 400)


def _friendly_ytdlp_error(stderr: str) -> str:
    """Turn yt-dlp's stderr into something actionable for a non-technical user.

    Deliberately takes only stderr: the user's URL is never echoed back into a
    response body, so a hostile URL cannot ride out through an error message.
    """
    blob = (stderr or "").lower()
    if "private video" in blob or "this video is private" in blob:
        return "That video is private. Sachet can only read public posts."
    if "login" in blob or "sign in" in blob or "cookies" in blob or "authentication" in blob:
        return (
            "That post needs a login to read. Sachet does not use your accounts, "
            "so login-gated reels will not work -- paste a public one."
        )
    if "unsupported url" in blob or "no suitable extractor" in blob:
        return "We cannot read links from that site. Paste a YouTube, Instagram, X, or TikTok link."
    if "unavailable" in blob or "removed" in blob or "404" in blob:
        return "That post is unavailable or has been deleted."
    if "age restricted" in blob or "confirm your age" in blob:
        return "That video is age-restricted. Sachet only reads public, unrestricted posts."
    return "Could not read that link. Check it is public and try again."


# --------------------------------------------------------------------------- #
# Captions path
# --------------------------------------------------------------------------- #


def parse_vtt(raw: str) -> str:
    """VTT caption text -> one clean string.

    Two things make naive VTT parsing produce garbage on auto-generated tracks:
    cue metadata blocks, and rolling captions that repeat the tail of the
    previous cue as the speaker keeps talking.
    """
    cues: list[str] = []
    for block in re.split(r"\r?\n\s*\r?\n", raw):
        lines: list[str] = []
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _VTT_META_RE.match(stripped) or _CUE_TIME_RE.match(stripped):
                continue
            if _VTT_NUM_RE.match(stripped):  # cue identifier
                continue
            lines.append(_TAG_RE.sub("", stripped))
        if lines:
            cues.append(html.unescape(" ".join(lines)).strip())
    return re.sub(r"\s+", " ", _dedupe_rolling(cues)).strip()


def _dedupe_rolling(cues: list[str]) -> str:
    """Collapse YouTube-style rolling auto-captions.

    When a cue extends the previous one, keep only the new tail; when a cue
    merely repeats the tail of the one before it, drop it. Compares against the
    immediately preceding accepted cue only, so a phrase genuinely repeated much
    later is still kept.
    """
    out: list[str] = []
    prev = ""
    for cue in cues:
        if not cue:
            continue
        if prev and (prev == cue or prev.endswith(cue)):
            continue
        if prev and cue.startswith(prev):
            remainder = cue[len(prev):].strip()
            if remainder:
                out.append(remainder)
            prev = cue
            continue
        out.append(cue)
        prev = cue
    return " ".join(out)


def _best_vtt(workdir: Path) -> str:
    """Longest usable caption text among any VTT files in workdir, else ""."""
    best = ""
    for path in sorted(workdir.glob("caps*.vtt")):
        try:
            text = parse_vtt(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        # A manual track (caps.en.vtt) and the rolling auto-generated one
        # (caps.en-orig.vtt) can both land; the longer text is the better one.
        if len(text) > len(best):
            best = text
    return best


def _fetch_captions(url: str, workdir: Path, language_hint: str = "auto") -> str | None:
    """Best-effort caption download. Returns text, or None if there is none.

    Languages are requested one at a time, in the user's preferred order, rather
    than as one comma-separated list. Two reasons, both learned the hard way
    against live YouTube:

    * YouTube rate-limits caption fetches per language (HTTP 429). yt-dlp
      treats a failure in *any* requested language as failure of the whole
      invocation -- so asking for "hi.*,en.*" means a 429 on Hindi discards the
      English track too, and the caller pays for a full download plus CPU
      transcription to get a worse answer.
    * One call per language also means the common case is a single call: the
      hint picks which language is tried first.

    Within an attempt the exit code is ignored and the filesystem decides,
    because yt-dlp can write a usable track and *then* fail on a later language.
    """
    for lang in _SUB_LANG_ORDER.get(language_hint, _SUB_LANG_ORDER["auto"]):
        for stale in workdir.glob("caps*.vtt"):
            stale.unlink(missing_ok=True)
        args = _base_args(workdir) + [
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", lang,
            "--sub-format", "vtt",
            "--output", "caps",
            url,
        ]
        _ytdlp(args, CAPTION_TIMEOUT, "captions")
        text = _best_vtt(workdir)
        if text:
            return text
    # Nothing usable for any language: either no caption track exists, or every
    # fetch failed. Both mean the caller should fall through to the media path.
    return None



# --------------------------------------------------------------------------- #
# Media path
# --------------------------------------------------------------------------- #


def _fetch_media(url: str, workdir: Path) -> Path | None:
    """Download the audio-only stream. Returns the file, or None."""
    args = _base_args(workdir) + [
        "-f", "bestaudio[ext=m4a]/bestaudio/best",
        "--max-filesize", f"{MAX_BYTES}",
        "--output", "media.%(ext)s",
        url,
    ]
    proc = _ytdlp(args, MEDIA_TIMEOUT, "clip")
    stderr = (proc.stderr or "").lower()
    if "larger than max-filesize" in stderr or "requested format not available" in stderr:
        raise PipelineError(
            f"That clip is over the {MAX_BYTES // (1024 * 1024)} MB limit and has no "
            "smaller audio stream. Paste a shorter one.",
            413,
        )
    if proc.returncode != 0:
        return None

    candidates = [
        p for p in sorted(workdir.glob("media.*")) if p.suffix.lower() != ".part"
    ]
    return candidates[0] if candidates else None


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def ingest_url(url: str, language_hint: str = "auto") -> dict:
    """Fetch a public video/reel link and return a transcript. Raises PipelineError.

    Returns the transcribe.py response shape plus:
      source     "captions" | "media" -- which path produced the text
      title      best-effort, for display only
      truncated  True if the transcript was cut to MAX_ANALYZE_CHARS
      dropped_chars  how much was cut (0 when not truncated)
    """
    if language_hint not in ("auto", "hi", "en"):
        raise PipelineError("language_hint is auto, hi, or en.", 400)

    resolved, _host = _resolve_public_url(url)

    if not _SLOTS.acquire(timeout=_QUEUE_TIMEOUT):
        raise PipelineError("The server is busy transcribing. Retry in a moment.", 503)
    try:
        with tempfile.TemporaryDirectory(prefix="sachet-url-") as tmp:
            work = Path(tmp)
            meta = _probe(resolved, work)
            title = meta.get("title") or None

            # Reject an over-long video here, before spending bandwidth on it.
            # The upload path can only check after the bytes have arrived.
            duration = meta.get("duration")
            if isinstance(duration, (int, float)) and duration > MAX_SEC + 1:
                raise PipelineError(
                    f"That video is {duration:.0f}s; the limit is {MAX_SEC}s. "
                    "Paste a short clip or a reel instead.",
                    413,
                )

            source = "captions"
            caption_text = _fetch_captions(resolved, work, language_hint)
            if caption_text:
                transcript, detected = normalize_transcript(caption_text, language_hint)
                model = "platform captions"
                if not isinstance(duration, (int, float)):
                    duration = 0.0
            else:
                media = _fetch_media(resolved, work)
                if media is None:
                    raise PipelineError(
                        "Could not get audio from that link, and it has no captions "
                        "to read. Try a different post.",
                        400,
                    )
                result = transcribe_file(media, language_hint)
                source = "media"
                transcript = result["transcript"]
                detected = result["detected_language"]
                model = result["model"]
                duration = result["duration_sec"]

            if not transcript:
                raise PipelineError("No speech found in that link.", 400)
    finally:
        _SLOTS.release()

    dropped = max(0, len(transcript) - MAX_ANALYZE_CHARS)
    if dropped:
        # The analyze endpoint caps at MAX_ANALYZE_CHARS, so an untruncated
        # transcript would be silently clipped server-side anyway. Cut here and
        # say so, rather than returning a verdict computed on part of the reel.
        transcript = transcript[:MAX_ANALYZE_CHARS].rstrip()

    return {
        "transcript": transcript,
        "detected_language": detected,
        "duration_sec": round(float(duration), 1),
        "model": model,
        "source": source,
        "title": title,
        "truncated": bool(dropped),
        "dropped_chars": dropped,
    }
