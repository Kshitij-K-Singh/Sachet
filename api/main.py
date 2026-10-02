"""
Sachet API — FastAPI service for Track E (Promotion-vs-Education analyzer).

Contract (v1, kept small — only fields the UI displays):
  POST /api/analyze  { "text": str, "language_hint"?: str }
  -> {
       "classification": "education" | "mixed" | "promotion",
       "caution_level": "low" | "medium" | "high",
       "caution_score": int,
       "summary": str,
       "claims": [
         { "quote": str, "claim_type": str, "flags": [str], "reason": str }
       ],
       "flags": [str],
       "flag_labels": [str],
       "verification": [ { "label": str, "status": str, "url": str, "note": str } ],
       "disclaimer": str,
       "rubric_version": str
     }

Run:  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from analyzer import DISCLAIMER, RUBRIC_VERSION, analyze_text  # noqa: F401 (re-exported in /api/meta)
from errors import PipelineError
from ml.infer import second_opinion
from transcribe import ALLOWED_EXT, MAX_BYTES, transcribe_file

app = FastAPI(title="Sachet API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=10, max_length=8000)
    language_hint: str = Field(default="auto", max_length=16)


class Claim(BaseModel):
    quote: str
    claim_type: str
    flags: list[str]
    reason: str


class VerificationItem(BaseModel):
    label: str
    status: Literal["present", "missing", "cannot_verify"]
    url: str
    note: str


class ModelOpinion(BaseModel):
    """Shadow classifier second opinion. Never decides the verdict."""

    label: Literal["education", "mixed", "promotion"]
    confidence: float


class AnalyzeResponse(BaseModel):
    # "out_of_scope" means the text was not financial content at all, so
    # no verdict applies and caution_level is "not_applicable" (not "low":
    # low caution would imply we rated it and found nothing wrong).
    classification: Literal["education", "mixed", "promotion", "out_of_scope"]
    caution_level: Literal["low", "medium", "high", "not_applicable"]
    caution_score: int
    summary: str
    claims: list[Claim]
    flags: list[str]
    flag_labels: list[str]
    verification: list[VerificationItem]
    disclaimer: str
    rubric_version: str
    model: ModelOpinion | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "rubric_version": RUBRIC_VERSION}


@app.get("/api/meta")
def meta() -> dict:
    return {
        "rubric_version": RUBRIC_VERSION,
        "labels": ["education", "mixed", "promotion", "out_of_scope"],
        "caution_levels": ["low", "medium", "high", "not_applicable"],
        "disclaimer": DISCLAIMER,
        "audio_upload": "whisper-cpp",
    }


class TranscribeResponse(BaseModel):
    transcript: str
    detected_language: str
    duration_sec: float
    model: str

@app.post("/api/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile, language_hint: str = "auto") -> dict:
    name = (file.filename or "").lower()
    ext = Path(name).suffix
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {ext or '(none)'}. Send MP3, WAV, or MP4.",
        )
    if language_hint not in ("auto", "hi", "en"):
        raise HTTPException(status_code=400, detail="language_hint is auto, hi, or en.")
    blob = await file.read()
    if len(blob) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large; 25 MB max.")
    if not blob:
        raise HTTPException(status_code=400, detail="Empty upload.")
    with tempfile.TemporaryDirectory(prefix="sachet-up-") as tmp:
        src = Path(tmp) / f"upload{ext}"
        src.write_bytes(blob)
        try:
            return transcribe_file(src, language_hint)
        except PipelineError as e:
            raise HTTPException(status_code=e.status, detail=str(e))


class OcrBlock(BaseModel):
    text: str
    confidence: float


class OcrResponse(BaseModel):
    text: str
    blocks: list[OcrBlock]
    model: str


@app.post("/api/ocr", response_model=OcrResponse)
async def ocr(file: UploadFile) -> dict:
    from ocr import ALLOWED_IMAGE_EXT, MAX_IMAGE_BYTES, ocr_image

    name = (file.filename or "").lower()
    ext = Path(name).suffix
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type {ext or '(none)'}. Send JPG, PNG, or WebP.",
        )
    blob = await file.read()
    if len(blob) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large; 10 MB max.")
    if not blob:
        raise HTTPException(status_code=400, detail="Empty upload.")
    with tempfile.TemporaryDirectory(prefix="sachet-ocr-") as tmp:
        src = Path(tmp) / f"shot{ext}"
        src.write_bytes(blob)
        try:
            return ocr_image(src)
        except PipelineError as e:
            raise HTTPException(status_code=e.status, detail=str(e))


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> dict:
    out = analyze_text(req.text)
    op = second_opinion(req.text)
    if op is not None:
        out["model"] = op
    return out
