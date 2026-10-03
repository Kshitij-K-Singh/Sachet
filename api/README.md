# Sachet API — Day-1 MVP

## Run
```
cd api
.venv/bin/python -m uvicorn main:app --reload --port 8000
# health: GET http://127.0.0.1:8000/health
```

## Contract v1 (only fields the UI displays)
`POST /api/analyze` — body `{ "text": str(10..8000), "language_hint"?: str, "ui_language"?: "en" | "hi" }`
→ `{ classification, caution_level, caution_score, summary, claims[],
     flags, flag_labels, guidance[], verification[], disclaimer,
     rubric_version, model? }`
- `ui_language` localizes display prose only (summary, reasons, checklists,
  verification notes, labels, disclaimer). Rubric codes, verbatim quotes,
  and URLs never change; unknown values fall back to English.
- `model`: shadow classifier second opinion `{ label, confidence }`,
  present when the LoRA adapter is deployed; never decides the verdict.
  Set `SACHET_MODEL=off` to disable (keeps tests fast).
  Kept in the API for the eval track, **not rendered in the UI** — the data
  is pre-review synthetic and at ~0.4 confidence it only told users our own
  tool disagreed with itself.
- `scope`: in_scope | out_of_scope | insufficient_context
- `label`: promotion | educational | unclear  (`mixed` = educational + red_flags)
- `classification`: education | mixed | promotion | out_of_scope |
  insufficient_context | question
- `confidence`: 0..1, auditable from observed evidence (see Confidence above)
- `red_flags[]`: `{ category, label, quote (verbatim), note }`
- `what_to_verify[]`: checks specific to the categories that actually fired
- `caution_level`: low | medium | high | not_applicable
- `claims[]`: `{ quote (verbatim), claim_type, flags[], reason }`
- `guidance[]`: populated only for `classification: "question"`; empty otherwise
- `verification[]`: `{ label, status (present|missing|cannot_verify), url, note }`

## Rubric v1.3 (sourced, Oct 1)
Weights: unrealistic_returns ×3 · risk_downplay / fake_authority /
paid_service_cta ×2 · urgency_pressure / social_proof / missing_disclosure ×1.
Score 0–1 → low/education · 2–4 → medium/mixed · 5+ → high/promotion.
Every flag cites its source document in `analyzer.py` (FLAG_SOURCES):
S1 = IA/RA advertisement code CIR/2023/51; S2 = finfluencer association
framework (Jun 2024 Board decision, Aug 2024 regs, Oct 2024 + Jan 2025
circulars); S3 = MF Regulations Sixth Schedule ad code.

### Scope gate (`out_of_scope`, added in v1.2)
Off-topic input (pizza, weather, recipes) used to come back as
`education` / `low`, which reads as a clean bill of health. v1.2 returns
`classification: "out_of_scope"` with `caution_level: "not_applicable"`
instead — no verdict, no score. It fires only when **both** hold:
- no rubric pattern matched (`_FINANCE_RE` gate in `analyzer.py`), and
- the text contains no finance-domain vocabulary (`_FINANCE_RE`).

Any single promo flag keeps the normal verdict, since scam captions
("Join our premium group, guaranteed 10x returns") are topic-agnostic and
must never be hidden behind an out-of-scope banner. The vocabulary is
deliberately broad and bilingual (English, Hinglish, Devanagari); a false
positive only means the normal rubric runs on off-topic text, while a false
negative would hide a real scam.

### Evidence model (v1.5 — replaces the weighted score ladder)
v1.3/v1.4 summed per-pattern weights and cut at fixed thresholds. That made
the verdict a function of **which keywords happened to be written down**:

| Input | Old score | Old verdict |
|---|---|---|
| "will it **double** in 2 years" | 0 | question |
| "will it **triple** in 2 years" | 3 + 1 derived | mixed |
| "will it **quadruple** in 2 years" | 0 | question |

`tripl\w+` and `10x` were in the pattern list; `quadrupl\w+` was not. A
*more extreme* claim produced a *gentler* verdict because one word was absent
from a regex. A single match (3) plus the derived `missing_disclosure` (+1)
was enough to cross a threshold, so one keyword decided the outcome.

v1.5 counts **independent persuasion categories** instead:

| Categories | Verdict | Meaning |
|---|---|---|
| ≥ 2 | `promotion` | a pattern, not a bad sentence |
| 1 | `mixed` | one tactic = a claim, not a pattern |
| 0 | `education` | no persuasion signal found |

Thresholds are measured, not guessed. Category-count distribution over the
254-item corpus:

| Gold label | 0 cats | 1 cat | 2 cats | 3+ cats |
|---|---|---|---|---|
| education (95) | **95** | 0 | 0 | 0 |
| mixed (71) | 0 | **59** | 12 | 0 |
| promotion (88) | 0 | 3 | **55** | 30 |

Corpus agreement 239/254 = **94.1%**, with education at 95/95 and no false
positives into education. The 15 misses are all the 1-vs-2 category boundary
on genuinely ambiguous funnel content.

### Why this is stable
- Repeating one tactic 5× does **not** change the verdict or the confidence.
  Volume cannot manufacture strength.
- A synonym swap cannot flip anything: all 8 variants of
  `"will it {} in 2 years"` return identical output.
- Escalation requires a genuinely *different* tactic, not another keyword in
  the same one. `test_repeating_one_tactic_cannot_manufacture_a_pattern` and
  `test_verdict_is_invariant_to_synonym_choice` pin both properties.

### Confidence
Auditable, not a model logit — a documented function of the evidence
observed, so a reviewer can recompute it and argue with the inputs rather
than the number. Promotion is the only branch that asserts a pattern and is
the only one that scores above 0.6. Abstentions (`question`,
`out_of_scope`, `insufficient_context`) return ≤0.5 by construction, and
`mixed` caps at 0.55, so "I can't tell" is visibly weaker than "I checked".

### Output shape
Two orthogonal axes instead of one label:

```
scope  : in_scope | out_of_scope | insufficient_context
label  : promotion | educational | unclear
```

`mixed` is not a third opinion — it is `label: "educational"` with a
non-empty `red_flags` list, matching the brief's "mostly educational video
with a hidden pitch". Also new: `red_flags[]` (each with a verbatim span),
`what_to_verify[]`, `education_markers[]`, `persuasion_categories[]`,
`confidence`.
A user asking a question is not content to grade. "if I invest 100 rupees
will it double in next 2 years" scored 0 and came back as
`education` / "straightforward financial education" — a confident verdict
about the user's own doubt, on content nobody submitted. Same failure mode as
the scope gate above.

v1.4 returns `classification: "question"` with `caution_level:
"not_applicable"`, plus a `guidance[]` list that answers with arithmetic and
regulation instead of a return forecast (predicting returns would be
investment advice, which `DISCLAIMER` disclaims). It fires only when all of:
- every clause in the text is interrogative (`_is_question`),
- the text has finance-domain vocabulary (`_FINANCE_RE`), and
- no **substantive** promo flag fired (`_PROMO_SUBSTANTIVE`).

Those three gates are deliberate. Captions are routinely phrased as a
question ("Paisa kaise lagaye? Mutual fund SIP start karo…") and must stay on
the rubric path; and "should I join their group for guaranteed 10x returns?"
is a question *about* a pitch, where grading the pitch is exactly what the
user wants. Validated against all 254 corpus items → 0 reclassified, and
`test_no_dataset_item_is_reclassified_as_a_question` guards that.

### Second opinion (hidden in the UI, kept in the API)
`model` is still returned so the eval track has evidence, but the UI no
longer renders it. It is pre-review synthetic data (n=38, documented
template-artifact risk in `ml/README.md`), so surfacing "disagrees" at 0.41
confidence told users the tool contradicts itself on the very content it had
just ruled on.

### Word order (fixed in v1.3)
The `unrealistic_returns` pattern originally only matched a percentage
*before* its noun ("5% profit every week"), so the noun-first phrasing in
real captions ("a return of 60%", "profit of 90% within 6 weeks") scored 0
and returned `education`. All three orders are now covered:

| Order | Example |
|---|---|
| `5% profit every week` | EN, percent first |
| `return of 60%` | EN, noun first (v1.3) |
| `3 mahine me 60 percent` | Hinglish, horizon first (v1.3) |
| `60% over the next three months` | EN, spelled-out horizon (v1.3) |

Every added alternative requires a **horizon token** (day/week/month/
quarter, digit or spelled out). A bare "returns of 12%" still does not
fire, so edu-0003 ("12% annualised returns over very long periods")
stays education — the horizon, not the number, is what separates a
promise from a historical fact.

Corpus result after the fix: heuristic agreement 231→236 of 254 (91%→93%),
education false positives 5→0 (the 5 were the out_of_scope gate missing
`credit score`, `commission`, `expense ratio`, `finfluencer`).

Note for future edits: `data/validate.py` prints agreement and the
out-of-scope gate can silently starve an education item of its verdict.
Run it on all six JSONL batches after touching `_PATTERNS` or
`_FINANCE_RE`, and treat education FPs as the regression that matters
more than aggregate agreement.

## Web
```
cd web
npm install
VITE_API_URL=http://127.0.0.1:8000 npm run dev   # or plain `npm run dev` (vite proxies /api)
```
If the API is down, the UI shows a labelled offline demo response so the flow is always demoable.

## Tests
```
cd api && .venv/bin/python -m pytest -q   # 124 passed
cd web && npm test                         # 20 passed
```

## Tab audio capture (frontend only)

`web/src/hooks/useTabCapture.ts` records the audio of a tab the user picks,
via `navigator.mediaDevices.getDisplayMedia`. It POSTs to the **existing**
`/api/transcribe` endpoint — there is no second ingest path, no gateway, and no
new server surface. `.webm` is already in `ALLOWED_EXT`, so MediaRecorder's
`audio/webm;codecs=opus` output goes straight through ffmpeg to whisper.

Four browser facts drive the implementation, all noted at the top of the hook:

1. `video: true` is mandatory even though only audio is wanted; the video track
   is taken and immediately stopped.
2. Tab audio is Chromium-only and needs "Share tab audio" ticked. Omitting it
   yields a *silent* recording, not an error.
3. The level meter uses `setInterval`, **not** `requestAnimationFrame`. During
   capture the reel tab is foreground and Sachet is backgrounded, where rAF is
   frozen solid. Sampling still works (throttled to ~1 Hz), which is all the
   silence check needs.
4. The browser's "Stop sharing" bar ends the track, so `track.onended` closes
   the recorder explicitly rather than trusting the spec's auto-stop.

### Why there is UA sniffing in here

Gecko and WebKit both expose `getDisplayMedia` and both ignore the audio
request — Firefox's own test suite asserts `getAudioTracks().length === 0` for
`{video: true, audio: true}` — and the spec permits exactly that ("the user
agent is allowed not to return audio even if the audio constraint is
present"). So there is **no feature detection** that can tell you in advance,
and an API-only check hands Firefox and Zen a working Listen button that can
only ever record silence. Hence `browserFamily()`, matched in UA order because
Edge and Opera both impersonate Chrome or Safari and are the browsers that *do*
work.

The same split applies to the failure copy: only Chromium's picker has a
"Share tab audio" checkbox, so telling a Zen user to tick it is nonsense advice.
`hasTabAudioCheckbox()` gates that message.

Note also that `canCaptureTabAudio()` deliberately does not require
`AudioContext`, unlike `isTabCaptureSupported()`. The audio graph only drives
the level meter, which is already wrapped in its own try/catch; requiring one
would refuse browsers that can in fact record.

Silence is detected from a running peak RMS and reported as its own failure
mode, distinct from "no audio track" and from the backend's "no speech". The
three need different fixes, so they get different messages.

`web/public/capture-spike.html` (`/capture-spike.html`) is a standalone
harness for verifying capture in a real browser. It is the one part of this
flow that cannot be covered by automated tests — `getDisplayMedia` needs a real
picker and a real gesture.

Two limits worth stating plainly: the flow is two steps (transcript lands in the
textarea for review, then the user analyses) because tab audio is the noisiest
input the app takes and whisper-base will occasionally mishear it; and the
recorded audio is discarded as soon as transcription finishes.

## Link ingest (paste a reel URL)

`POST /api/ingest-url` — JSON `{ "url": str, "language_hint"?: "auto"|"hi"|"en" }`
→
`{ transcript, detected_language, duration_sec, model, source, title,
truncated, dropped_chars }`.

`source` is `"captions"` or `"media"`, i.e. which of two paths ran:

1. **captions** — `yt-dlp --write-auto-subs --skip-download`, then a VTT
   parser. Seconds, no ffmpeg, no Whisper CPU. This is the common case on
   YouTube and it is why link import is not just the upload path with extra
   steps.
2. **media** — download the audio-only stream (`--max-filesize` capped) and run
   the normal `transcribe_file()` pipeline.

Both paths route language through `transcribe.normalize_transcript()`, so a reel
reports the same `detected_language` whether it arrived as a link or an upload.

The duration cap is checked from metadata **before** any download, so a
20-minute video is rejected without pulling it. Transcripts longer than
`MAX_ANALYZE_CHARS` are clipped and reported via `truncated` / `dropped_chars`
rather than silently truncated, because `/api/analyze` would clip them anyway
and a verdict computed on part of a reel is worse than an honest warning.

### Security

This endpoint makes the server fetch a user-supplied URL, so it is an SSRF
sink. Gates, in order, all before the first byte moves:

- **platform allowlist** (`ingest._ALLOWED_HOSTS`) — the only control that
  actually bounds the blast radius, since yt-dlp resolves DNS and follows
  redirects itself and we never see post-redirect hops. Host matching is
  anchored on `.` so `notyoutube.com` cannot pass as `youtube.com`.
- **resolved-IP check** (`ingest._ip_is_blocked`) — rejects loopback, private,
  link-local (incl. `169.254.169.254` cloud metadata), CGNAT, multicast and
  reserved ranges, after unwrapping IPv4-mapped (`::ffff:127.0.0.1`) and
  6to4 forms.
- scheme allowlist (`http`/`https`), embedded-credential rejection, length cap.
- `--ignore-config` so a host `~/.config/yt-dlp` cannot inject options.
- `SACHET_MAX_CONCURRENT_INGEST` semaphore bounds concurrent fetches; overflow
  gets a 503 rather than piling up.

Adding a host to `_ALLOWED_HOSTS` is a security decision, not a config change.
There is **no authentication and no rate limiting** on this API, so until that
exists treat the allowlist as the only thing standing between a public user and
your network's private address space.

Login-gated platforms are not supported: yt-dlp would need the user's cookies,
which collides with the "no accounts, nothing stored" promise. Instagram reels
behind a login will return an explanatory 400.

## Screenshot OCR (hosted vision API, hi+en)

`POST /api/ocr` — multipart image (JPG/PNG/WebP, 10 MB, 4000px max) →
`{ text, blocks: [{text, confidence}], model }`. Hosted `DOCUMENT_TEXT_DETECTION`
(Google Cloud Vision by default, Azure AI Vision Read as alternative) with
`hi`+`en` hints; temp files deleted. Configure with `GOOGLE_VISION_KEY`
(or `AZURE_VISION_ENDPOINT` + `AZURE_VISION_KEY`). OCR text lands in the
UI textarea for user review before analysis, so minor read errors
(scrambled block order, Devanagari digits) never silently decide a
verdict. Fixtures: `data/fixtures/shot_en.png`, `shot_hi.png`.
Tests mock the provider boundary so they run offline with no key.

## Transcription (hosted STT API, hi+en)

`POST /api/transcribe?language_hint=auto|hi|en` — multipart `file`
(MP3/WAV/MP4, 25 MB, 3 min max) →
`{ transcript, detected_language, duration_sec, model }`.
ffmpeg normalizes to 16 kHz mono; a hosted OpenAI-compatible STT endpoint
(Groq `whisper-large-v3-turbo` by default, OpenAI `whisper-1` as fallback,
or any `SACHET_STT_ENDPOINT` gateway) transcribes it in seconds; temp
files are deleted. Configure with `GROQ_API_KEY` (or `OPENAI_API_KEY`,
or `SACHET_STT_ENDPOINT` + `SACHET_STT_API_KEY` + `SACHET_STT_MODEL`).
Hindi speech may decode to Urdu
script or Latin transliteration: `transliterate.py` normalizes Urdu
script to Devanagari, and the rubric covers Latin-Hindi stems
(PESA DUBBAL etc., all observed from real decoder output, never guessed).

Setup: export an STT key. No compiler, no model download, no GPU needed.

## Docker

`docker build -t sachet-api .` from the repo root, then
`docker run --rm -p 8000:8000 -e GROQ_API_KEY=... -e GOOGLE_VISION_KEY=... sachet-api`.

Single stage (no compiler, no model downloads). Notes worth knowing before you
change it:

- ffmpeg is apt-installed. Copying `/usr/bin/ffmpeg` out of another stage
  would not work: it would not resolve `libavcodec`.
- No torch/transformers in the image. The MuRIL shadow classifier is optional
  (`SACHET_MODEL=off` by default) and `ml/infer.py` degrades to `None` when
  torch is absent. Install `api/requirements-ml.txt` only for local
  training/eval.
- One uvicorn worker by design. Hosted STT/OCR are network-bound and
  `ingest.MAX_CONCURRENT` bounds fetches inside the process; more workers
  multiply concurrent API spend. Scale with replicas.
