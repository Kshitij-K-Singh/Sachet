# Sachet API — Day-1 MVP

## Run
```
cd api
.venv/bin/python -m uvicorn main:app --reload --port 8000
# health: GET http://127.0.0.1:8000/health
```

## Contract v1 (only fields the UI displays)
`POST /api/analyze` — body `{ "text": str(10..8000), "language_hint"?: str }`
→ `{ classification, caution_level, caution_score, summary, claims[],
     flags, flag_labels, verification[], disclaimer, rubric_version,
     model? }`
- `model`: shadow classifier second opinion `{ label, confidence }`,
  present when the LoRA adapter is deployed; never decides the verdict.
  Set `SACHET_MODEL=off` to disable (keeps tests fast).
- `classification`: education | mixed | promotion
- `caution_level`: low | medium | high
- `claims[]`: `{ quote (verbatim), claim_type, flags[], reason }`
- `verification[]`: `{ label, status (present|missing|cannot_verify), url, note }`

## Rubric v1.1 (sourced, Oct 1)
Weights: unrealistic_returns ×3 · risk_downplay / fake_authority /
paid_service_cta ×2 · urgency_pressure / social_proof / missing_disclosure ×1.
Score 0–1 → low/education · 2–4 → medium/mixed · 5+ → high/promotion.
Every flag cites its source document in `analyzer.py` (FLAG_SOURCES):
S1 = IA/RA advertisement code CIR/2023/51; S2 = finfluencer association
framework (Jun 2024 Board decision, Aug 2024 regs, Oct 2024 + Jan 2025
circulars); S3 = MF Regulations Sixth Schedule ad code.

## Web
```
cd web
npm install
VITE_API_URL=http://127.0.0.1:8000 npm run dev   # or plain `npm run dev` (vite proxies /api)
```
If the API is down, the UI shows a labelled offline demo response so the flow is always demoable.

## Tests
```
cd api && .venv/bin/python -m pytest -q   # 20 passed
```

## Screenshot OCR (EasyOCR, local)

`POST /api/ocr` — multipart image (JPG/PNG/WebP, 10 MB, 4000px max) →
`{ text, blocks: [{text, confidence}], model }`. EasyOCR `hi`+`en`
reader, GPU when available; temp files deleted. OCR text lands in the
UI textarea for user review before analysis, so minor read errors
(scrambled block order, Devanagari digits) never silently decide a
verdict. Fixtures: `data/fixtures/shot_en.png`, `shot_hi.png`
(regenerate with `data/make_ocr_fixtures.py`).

## Transcription (Whisper.cpp, local)

`POST /api/transcribe?language_hint=auto|hi|en` — multipart `file`
(MP3/WAV/MP4, 25 MB, 3 min max) →
`{ transcript, detected_language, duration_sec, model }`.
ffmpeg normalizes to 16 kHz mono; whisper.cpp base multilingual model
runs on CPU; temp files are deleted. Hindi speech may decode to Urdu
script or Latin transliteration: `transliterate.py` normalizes Urdu
script to Devanagari, and the rubric covers Latin-Hindi stems
(PESA DUBBAL etc., all observed from real decoder output, never guessed).

Setup (one time): `git clone whisper.cpp`, `cmake --build` (needs
cmake/g++/ffmpeg), then `models/download-ggml-model.sh base`.
Binaries live in `api/whisper.cpp/` (build output, not source).
