"""Screenshot OCR via a hosted vision API (Hindi + English).

Pipeline: upload -> sanity checks -> hosted DOCUMENT_TEXT_DETECTION ->
blocks in reading order -> joined text. Temp files are always deleted.
Nothing is stored.

Why hosted: the old local EasyOCR path required torch + torchvision +
opencv plus ~100 MB of detection/recognition weights downloaded at first
run, and ran CPU inference in seconds per screenshot. A hosted vision
endpoint needs no heavyweight install (this module is stdlib + Pillow),
builds in seconds, answers in ~1-2 s, and matches or beats EasyOCR on
Devanagari + noisy reel screenshots.

Configuration (environment, first match wins):
  SACHET_OCR_PROVIDER  auto | google | azure (default: auto)
  GOOGLE_VISION_KEY / SACHET_OCR_API_KEY
      Google Cloud Vision `images:annotate` with DOCUMENT_TEXT_DETECTION
      and languageHints ["hi", "en"].
  AZURE_VISION_ENDPOINT + AZURE_VISION_KEY
      Azure AI Vision 3.2 Read (`/vision/v3.2/read/analyze` + polling).
  SACHET_OCR_TIMEOUT   HTTP timeout in seconds (default: 30)
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

from errors import PipelineError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_SIDE_PX = 4000
MIN_CONFIDENCE = 0.25

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

TIMEOUT_SEC = int(os.environ.get("SACHET_OCR_TIMEOUT", "30"))

# A custom UA: some provider front doors (Cloudflare etc.) ban default
# library user-agents with 403. See transcribe.py for the full story.
_USER_AGENT = "Sachet/1.0 (+https://github.com/Kshitij-K-Singh/Sachet)"


def _resolve_ocr_config() -> tuple[str, dict]:
    """Return (provider, config). Raises PipelineError(500) when unconfigured."""
    provider = os.environ.get("SACHET_OCR_PROVIDER", "auto").strip().lower() or "auto"
    google_key = (
        os.environ.get("GOOGLE_VISION_KEY", "").strip()
        or os.environ.get("SACHET_OCR_API_KEY", "").strip()
    )
    azure_endpoint = os.environ.get("AZURE_VISION_ENDPOINT", "").strip().rstrip("/")
    azure_key = os.environ.get("AZURE_VISION_KEY", "").strip()

    if provider in ("auto", "google") and google_key:
        return "google", {"api_key": google_key}
    if provider in ("auto", "azure") and azure_endpoint and azure_key:
        return "azure", {"endpoint": azure_endpoint, "api_key": azure_key}
    if provider not in ("auto", "google", "azure"):
        raise PipelineError(
            f"Unknown SACHET_OCR_PROVIDER {provider!r}. Use auto, google, or azure.",
            500,
        )
    if provider == "google" or (provider == "auto" and (azure_endpoint or azure_key)):
        # Operator named a provider (or half-configured Azure): say exactly
        # what is missing instead of a generic "not configured".
        if provider == "azure" or azure_endpoint or azure_key:
            raise PipelineError(
                "OCR is half-configured: set both AZURE_VISION_ENDPOINT and "
                "AZURE_VISION_KEY (or use GOOGLE_VISION_KEY).",
                500,
            )
        raise PipelineError(
            "OCR is not configured on this server (set GOOGLE_VISION_KEY, "
            "or AZURE_VISION_ENDPOINT + AZURE_VISION_KEY).",
            500,
        )
    raise PipelineError(
        "OCR is not configured on this server (set GOOGLE_VISION_KEY, "
        "or AZURE_VISION_ENDPOINT + AZURE_VISION_KEY).",
        500,
    )


def _http_json(
    req: urllib.request.Request, *, what: str = "OCR service"
) -> tuple[dict | list, dict[str, str]]:
    """POST/GET JSON via stdlib. Returns (parsed_body, response_headers)."""
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            headers = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = ""
        if e.code == 401:
            raise PipelineError(
                "OCR credentials were rejected. Check the vision API key.", 500
            )
        if e.code == 403:
            # 403 from Google carries the actionable reason in the body
            # ("billing not enabled", "API not enabled", ...): surface it
            # instead of a generic credentials complaint.
            raise PipelineError(
                f"OCR refused ({e.code}). {detail}".strip()
                if detail
                else "OCR credentials were rejected. Check the vision API key.",
                500,
            )
    except urllib.error.URLError:
        raise PipelineError(
            f"Could not reach the {what}. Retry in a moment.", 502
        )
    except TimeoutError:
        raise PipelineError("OCR took too long. Retry in a moment.", 504)
    try:
        return json.loads(raw), headers
    except json.JSONDecodeError:
        raise PipelineError("OCR returned an unreadable response.", 502)


def _ocr_via_google(image_bytes: bytes, api_key: str) -> list[dict]:
    from urllib.parse import quote_plus

    payload = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode()},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                "imageContext": {"languageHints": ["hi", "en"]},
            }
        ]
    }
    req = urllib.request.Request(
        f"https://vision.googleapis.com/v1/images:annotate?key={quote_plus(api_key)}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
        method="POST",
    )
    data, _ = _http_json(req)
    if not isinstance(data, dict):
        raise PipelineError("OCR returned an unreadable response.", 502)
    responses = data.get("responses", [])
    if not responses or not isinstance(responses, list):
        raise PipelineError("OCR returned an unreadable response.", 502)
    first = responses[0]
    if first.get("error"):
        raise PipelineError(
            f"OCR failed: {first['error'].get('message', 'unknown error')}", 502
        )
    annotation = first.get("fullTextAnnotation") or {}
    blocks: list[dict] = []
    for page in annotation.get("pages", []):
        for block in page.get("blocks", []):
            words: list[tuple[str, float]] = []
            for para in block.get("paragraphs", []):
                for word in para.get("words", []):
                    text = "".join(
                        s.get("text", "") for s in word.get("symbols", [])
                    )
                    conf = word.get("confidence", 0.0)
                    try:
                        conf = float(conf)
                    except (TypeError, ValueError):
                        conf = 0.0
                    if text.strip():
                        words.append((text.strip(), conf))
            if not words:
                continue
            text = " ".join(w for w, _ in words)
            conf = sum(c for _, c in words) / len(words)
            if text.strip() and conf >= MIN_CONFIDENCE:
                blocks.append(
                    {"text": text.strip(), "confidence": round(conf, 3)}
                )
    if not blocks:
        # Fallback: full-text only (no per-word confidence available).
        full = (annotation.get("text") or "").strip()
        if full:
            blocks = [{"text": line.strip(), "confidence": 1.0} for line in full.splitlines() if line.strip()]
    return blocks


def _ocr_via_azure(image_bytes: bytes, endpoint: str, api_key: str) -> list[dict]:
    submit = urllib.request.Request(
        endpoint + "/vision/v3.2/read/analyze",
        data=image_bytes,
        headers={
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/octet-stream",
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(submit, timeout=TIMEOUT_SEC) as resp:
            op_location = resp.headers.get("Operation-Location", "")
            status = resp.status
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PipelineError(
                "OCR credentials were rejected. Check the vision API key.", 500
            )
        if e.code == 429:
            raise PipelineError("OCR is rate-limited right now. Retry in a moment.", 503)
        raise PipelineError(f"OCR failed ({e.code}).", 502)
    except urllib.error.URLError:
        raise PipelineError("Could not reach the OCR service. Retry in a moment.", 502)
    except TimeoutError:
        raise PipelineError("OCR took too long. Retry in a moment.", 504)
    if status != 202 or not op_location:
        raise PipelineError("OCR failed to start (no operation URL).", 502)

    deadline = time.time() + TIMEOUT_SEC
    while True:
        poll = urllib.request.Request(
            op_location,
            headers={
                "Ocp-Apim-Subscription-Key": api_key,
                "User-Agent": _USER_AGENT,
            },
            method="GET",
        )
        data, _ = _http_json(poll)
        if not isinstance(data, dict):
            raise PipelineError("OCR returned an unreadable response.", 502)
        state = data.get("status", "")
        if state == "succeeded":
            break
        if state == "failed":
            raise PipelineError("OCR could not read that image.", 502)
        if time.time() > deadline:
            raise PipelineError("OCR took too long. Retry in a moment.", 504)
        time.sleep(1)

    blocks: list[dict] = []
    result = data.get("analyzeResult", {})
    for page in result.get("readResults", []):
        for line in page.get("lines", []):
            text = (line.get("text") or "").strip()
            words = line.get("words", [])
            confs: list[float] = []
            for w in words:
                try:
                    confs.append(float(w.get("confidence", 0.0)))
                except (TypeError, ValueError):
                    continue
            conf = sum(confs) / len(confs) if confs else 1.0
            if text and conf >= MIN_CONFIDENCE:
                blocks.append({"text": text, "confidence": round(conf, 3)})
    return blocks


def ocr_image(src: Path) -> dict:
    """OCR one image file via the hosted vision API. Raises PipelineError."""
    try:
        with Image.open(src) as img:
            img.verify()
        with Image.open(src) as img:
            w, h = img.size
    except Exception:
        raise PipelineError("Could not read that image. Send JPG, PNG, or WebP.")
    if max(w, h) > MAX_SIDE_PX:
        raise PipelineError("Image too large; 4000px per side max.", 413)

    try:
        image_bytes = src.read_bytes()
    except OSError:
        raise PipelineError("Could not read that image. Send JPG, PNG, or WebP.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise PipelineError("Image too large; 10 MB max.", 413)
    if not image_bytes:
        raise PipelineError("Could not read that image. Send JPG, PNG, or WebP.")

    provider, config = _resolve_ocr_config()
    if provider == "google":
        blocks = _ocr_via_google(image_bytes, config["api_key"])
        model = "google vision hi+en (hosted)"
    else:
        blocks = _ocr_via_azure(
            image_bytes, config["endpoint"], config["api_key"]
        )
        model = "azure vision read hi+en (hosted)"

    if not blocks:
        raise PipelineError("No readable text found in that screenshot.", 400)
    return {
        "text": "\n".join(b["text"] for b in blocks),
        "blocks": blocks,
        "model": model,
    }
