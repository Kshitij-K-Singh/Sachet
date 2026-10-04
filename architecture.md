# Sachet — Architecture

> **One-line summary:** Sachet helps people spot the difference between financial
> *education* and *promotion* in short-form content (reels, forwards, captions).
> Paste text, a reel link, a screenshot, or an audio/video clip — the app returns
> an explainable caution rating and points to official sources. It is an
> **awareness tool, not investment advice**, built for **Sangyan 2026, Track E**.

---

## 1. System overview

```
                         ┌──────────────────────────────┐
                         │        React SPA (web/)       │
                         │  Vite + TS · EN/हिंदी · a11y │
                         └──────┬───────────────┬───────┘
                                │               │ /capture-spike.html
                    /api/* ─────┘               │ (standalone harness)
                                                ▼
                         ┌──────────────────────────────┐
                         │     FastAPI service (api/)    │
                         │  main.py — 5 endpoints        │
                         └──┬───────┬───────┬────────┬───┘
                            │       │       │        │
              ┌─────────────┘       │       │        └──────────────┐
              ▼                     ▼       ▼                       ▼
     ┌────────────────┐  ┌──────────────┐ ┌──────────────┐ ┌───────────────┐
     │ Rubric analyzer │  │ Hosted STT   │ │ Hosted vision │ │ yt-dlp link   │
     │ analyzer.py     │  │ transcribe.py│ │ OCR ocr.py    │ │ ingest ingest.py│
     │ pure Python,    │  │ Groq/OpenAI  │ │ Google/Azure  │ │ captions-first,│
     │ no network      │  │ + ffmpeg     │ │ + Pillow      │ │ SSRF-gated    │
     └────────────────┘  └──────────────┘ └──────────────┘ └───────────────┘
              │
              │ optional second opinion (never decides)
              ▼
     ┌────────────────┐
     │ MuRIL shadow   │  api/ml/ — training/eval track only,
     │ classifier     │  disabled in prod (SACHET_MODEL=off)
     └────────────────┘
```

**Two deployables, one repo:**

| Service | Source | Runtime | Live on Railway |
|---|---|---|---|
| `web` | `web/` (Vite build → `vite preview`) | Node, `rootDirectory: web` | `web-production-cde2c.up.railway.app` |
| `sachet` (API) | `Dockerfile` at repo root (`api/`) | Python 3.12 slim + ffmpeg, 1 uvicorn worker | `sachet-production.up.railway.app` (port 8000) |

The web app talks to the API at same-origin `/api` locally (Vite proxy) and via
`VITE_API_URL` in production. If the API is down, the UI degrades to a clearly
labelled **offline demo response** so the flow is always demoable.

---

## 2. Input paths — five ways text gets in

Every input path converges on **one textarea → one `/api/analyze` call**.
Audio, screenshots and links never get their own verdict path; they only
produce *text for the user to review first*, because transcription/OCR is noisy
and a verdict resting on misheard words must be checkable.

| # | Input | Frontend | Backend | Notes |
|---|---|---|---|---|
| 1 | Paste text / try a sample | `App.tsx` textarea (10–8000 chars) | `POST /api/analyze` | 4 built-in samples (promotion / education / mixed / off-topic) |
| 2 | Reel/video link | link box → `POST /api/ingest-url` | `ingest.py` | **Captions-first**: tries `--write-auto-subs` (seconds, no download); falls back to audio download + STT. Reports `source: captions \| media`, duration, truncation |
| 3 | Audio/video file | file picker → `POST /api/transcribe` | `transcribe.py` | 25 MB / 3 min cap; ffmpeg → 16 kHz mono → hosted Whisper |
| 4 | **Listen to a tab** | `useTabCapture.ts` → same `/api/transcribe` | (same as 3) | `getDisplayMedia` tab-audio capture, ≤30 s, Chromium-only; level meter via `setInterval` (rAF freezes in background tabs); silent-capture detected as its own failure mode |
| 5 | Screenshot | file picker → `POST /api/ocr` | `ocr.py` | 10 MB, JPG/PNG/WebP; `DOCUMENT_TEXT_DETECTION` with `hi`+`en` hints; blocks + confidence returned |

Deliberate UX rule: long transcripts are **clipped with an explicit warning**
("only the first 8,000 characters were kept…") instead of silently — a verdict
on half a reel presented as a verdict on the whole reel would be dishonest.

---

## 3. The analysis engine — a fixed rubric, not a black box

`api/analyzer.py` is the heart of the project: a **pure-Python, deterministic,
zero-network heuristic baseline** over a fixed 7-flag taxonomy. The model
(and later, hosted LLMs — there are none in the loop) never decides; the rubric
decides, and every claim cites the input **verbatim**.

### 3.1 The seven flags (rubric v1.3 taxonomy)

| Flag | Weight class | Example trigger |
|---|---|---|
| `unrealistic_returns` | ×3 | "guaranteed returns", "double your money in 30 days", "10x" |
| `risk_downplay` | ×2 | "no risk", "100% safe" |
| `fake_authority` | ×2 | "my secret strategy", unverifiable insider claims |
| `paid_service_cta` | ×2 | "join our premium Telegram group" |
| `urgency_pressure` | ×1 | "limited seats, hurry!" |
| `social_proof` | ×1 | "my student earned 2 lakh profit" as evidence |
| `missing_disclosure` | ×1 (derived) | risky content with no risk disclaimer |

Patterns are bilingual by construction — English, Hinglish, and Devanagari —
including word-order variants found in real captions (noun-first "a return of
60%", Hinglish horizon-first "3 mahine me 60 percent"). Each flag cites its
source SEBI document (`FLAG_SOURCES`): S1 = IA/RA advertisement code
CIR/2023/51, S2 = finfluencer framework (2024–25), S3 = MF Regulations
advertisement code.

### 3.2 The v1.5 evidence model — count categories, not keywords

The key design evolution (see `api/README.md`): v1.3 summed pattern weights
against thresholds, which made the verdict a function of *which keywords were
written down*. A *"triple in 2 years"* scored 3 and *"quadruple in 2 years"*
scored 0 — a more extreme claim getting a gentler verdict because one word was
missing from a regex.

v1.5 counts **independent persuasion categories** instead (thresholds measured
on the 254-item corpus, not guessed):

| Categories observed | Classification | Reading |
|---|---|---|
| ≥ 2 | `promotion` | a pattern, not a bad sentence |
| 1 | `mixed` | one tactic = a claim, not a pattern |
| 0 | `education` | no persuasion signal found |

Corpus agreement: **239/254 (94.1%)**, education 95/95 with zero false
positives. Repeating one tactic 5× cannot manufacture a pattern; synonym swaps
cannot flip a verdict — both properties are pinned by regression tests.

### 3.3 Scope and question gates — knowing when *not* to judge

Two abstention mechanisms prevent confident verdicts on ungradeable input
(both return `caution_level: "not_applicable"`, never a score):

- **`out_of_scope`** — no promo flag fired *and* no finance vocabulary present
  ("pizza with friends" → not financial content, not a "clean bill of health").
- **`question`** — every clause interrogative + finance vocabulary + no
  substantive promo flag ("will ₹100 double in 2 years?" → answered with
  arithmetic/regulation in `guidance[]`, never a return forecast, which would
  be investment advice).
- **`insufficient_context`** — too short/fragmentary to rule either way.

### 3.4 Confidence and verification

- `confidence` is **auditable, not a logit** — a documented function of
  observed evidence. Only `promotion` (which asserts a pattern) scores above
  0.6; abstentions cap at ≤0.5 by construction, so "I can't tell" visibly
  reads weaker than "I checked".
- `verification[]` checks three official-source items (SEBI registration,
  risk disclosure, cited circulars) with honest statuses:
  `present | missing | cannot_verify` — never "false".
- `ui_language` (`en | hi`) localizes display prose server-side; rubric
  codes, verbatim quotes, and URLs never change.

---

## 4. API contract (v1)

`api/main.py` — FastAPI, Pydantic-validated, CORS origins env-driven
(`SACHET_CORS_ORIGINS`; localhost defaults preserved for dev).

| Method & path | Input | Output |
|---|---|---|
| `GET /health` | — | `{ status, rubric_version }` (also the Docker `HEALTHCHECK`) |
| `GET /api/meta` | — | rubric version, label vocabularies, capability flags, disclaimer |
| `POST /api/analyze` | `{ text (10–8000), language_hint, ui_language }` | `AnalyzeResponse` (scope, label, classification, caution, claims, flags, red_flags, verification, …) |
| `POST /api/transcribe?language_hint=` | multipart audio/video | `{ transcript, detected_language, duration_sec, model }` |
| `POST /api/ocr` | multipart image | `{ text, blocks[{text, confidence}], model }` |
| `POST /api/ingest-url` | `{ url, language_hint }` | `{ transcript, detected_language, duration_sec, model, source, title, truncated, dropped_chars }` |

Security posture, stated plainly: `/api/ingest-url` is an SSRF sink and is
gated by a platform allowlist + resolved-IP blocking (loopback, private,
link-local incl. cloud metadata, CGNAT, multicast) + scheme/credential/length
checks + `--ignore-config` for yt-dlp + a concurrency semaphore (503 on
overflow). Uploads are validated by extension and size, processed in temp dirs,
and discarded. **No auth and no rate limiting exist yet** — the allowlist is
currently the only thing between a public user and the network.

---

## 5. Frontend architecture (`web/`)

Vite + React 19 + TypeScript. Styling is token-driven: `App.css` owns the
theme (custom properties, dark default + real light theme), `effects.css` owns
animation, `index.css` the reset. No component ever uses a literal colour.

```
web/src/
├── App.tsx            # whole flow: landing → result; all 5 input paths
├── main.tsx           # fonts (Outfit / Space Grotesk / Noto Sans Devanagari)
├── prefs.tsx / prefs-context.ts   # theme · lang · fontScale · contrast (localStorage)
├── i18n.ts            # EN/HI interface strings; t() falls back EN → key
├── hooks/useTabCapture.ts         # tab-audio state machine (+ jsdom tests)
├── bits/              # Backdrop, PixelBlast, SplitText, Magnet, ScrollProgress…
├── ui/                # Card, Meter, Logo, ListenPanel, AccessibilityBar
└── effects.css / App.css / index.css
```

Notable decisions:

- **Prefs as data attributes** — `data-theme`, `data-lang`, `data-font`,
  `data-contrast` on `<html>` drive all CSS; `index.html` restores them
  pre-paint to avoid a flash. Devanagari-first font stacks kick in via
  `[data-lang="hi"]`.
- **Bilingual contract** — interface chrome is translated in `i18n.ts`;
  *result prose* is translated server-side via `ui_language`; sample bodies,
  quotes, codes, URLs stay byte-identical (translating a promotional sample
  would change what the rubric demonstrates).
- **Result screen** — verdict card with severity edge (green/amber/red/grey —
  grey for abstentions so they never read as a pass), caution `Meter`,
  highlighted source transcript, per-claim cards with rubric reasons,
  next-steps + official-source checklist; promotion verdicts get a
  **Report on SEBI SCORES** action (link-out only, never auto-files).
- **Tests** — Vitest + jsdom (28 tests: tab-capture state machine); `tsc -b`
  gates every build.

### Accessibility (SEBI/NSDL-inspired)

Government sites (SEBI, NSDL) ship an accessibility strip — skip link, `A−/A/A+`
text sizing, contrast switchers. Sachet mirrors it with `ui/AccessibilityBar.tsx`:

- **Skip to main content** link (visible on keyboard focus) → `#main-content`.
- **Text size** `A− / A / A+` across 4 steps (90% → 125% via `zoom`, persisted).
- **Contrast** `STD / HC / GS`: default, black-yellow **high contrast** (low
  vision), and **grayscale** (colour-blind aid — nothing on the page depends on
  red-vs-green alone; verdicts always carry text labels). Persisted, restored
  pre-paint.
- Lesson learned the hard way: the first version was transparent text over the
  animated backdrop and effectively invisible — an embarrassing failure mode
  for an accessibility feature. It is now a solid card strip.

---

## 6. ML track (`api/ml/`) — the honest-failure log

A parallel, explicitly **pre-review** classifier track: TF-IDF+LogReg
baselines, a frozen-MuRIL probe, and a LoRA MuRIL fine-tune over a
synthetic bilingual corpus (`api/data/`, 254 → 408 items + a 329-item held-out
set that training can never see). Headline findings, documented in
`api/ml/README.md` rather than hidden:

- LoRA **collapses on `mixed`** (precision/recall 0.000) — the rare boundary
  class a weak encoder + r=16 LoRA cannot learn. Recommendation recorded:
  predict 2 classes and let the deterministic layer assign `mixed`.
- Relabelling gold from the heuristic was caught and reverted as circular.
- Batch-1+2 train/test shared a generator (template-artifact risk) — fixed for
  batch 3 with a genuinely unlike-training held-out set.

The fine-tuned model survives in prod only as an unevaluated **shadow second
opinion** (`model` field, `SACHET_MODEL=off` by default, auto-`None` without
torch) — **kept in the API for the eval track, deliberately not rendered**,
because a 0.4-confidence "disagreement" told users the tool contradicts itself.

---

## 7. Deployment & operations

- **Docker** (repo-root `Dockerfile`): single stage, Python slim + apt
  `ffmpeg` (never copied between stages — libavcodec wouldn't resolve),
  slim `requirements.txt` (no torch/transformers/OCR libs — all hosted APIs),
  non-root `sachet` user, `/tmp` writable, `HEALTHCHECK` on `/health`,
  **one uvicorn worker on purpose** (hosted APIs are network-bound; more
  workers multiply API spend — scale with replicas).
- **Railway**: two services in one project/environment (`sachet` prod env).
  `web` deploys from `web/` with `VITE_API_URL` set; `sachet` from the
  Dockerfile with `GROQ_API_KEY`, `GOOGLE_VISION_KEY`, `SACHET_CORS_ORIGINS`.
  Gotchas encountered: `vite preview` 403s on unknown Host headers (fixed via
  `allowedHosts`), and `railway up` must upload the **repo root** so the
  service's `rootDirectory: web` resolves (uploading `./web` as root breaks
  the railpack prepare step).
- **Local dev**: API via `uvicorn main:app --reload --port 8000` (needs
  `GROQ_API_KEY` + vision keys for live STT/OCR); web via Vite (proxies
  `/api` to localhost). Hosted APIs mean no GPU, no model downloads, no
  compiler — at the cost of requiring API keys.

---

## 8. Tests & quality gates

- **API**: `pytest` (~124 tests) — rubric agreement over the JSONL corpus,
  gate invariants (synonym-invariance, repeat-can't-manufacture-pattern, no
  dataset item reclassified as question), provider boundaries mocked (offline).
- **Web**: Vitest (28 tests, jsdom) + `eslint` + `tsc -b` in the build chain.
- **Manual-only**: real tab capture (`getDisplayMedia` needs a real picker —
  covered by `/capture-spike.html` harness, not automation).

## 9. Known limitations / next steps

1. No auth or rate limiting on the API (SSRF allowlist is the lone guard).
2. ML classifier is pre-review synthetic-data work — needs real labelled data
   before it can decide anything.
3. `mixed` remains the boundary the heuristic owns and the model cannot learn.
4. Only YouTube/Instagram/X/TikTok public posts ingestible; login-gated
   content unsupported by design (no accounts, nothing stored).
5. UI languages EN/HI only; Devanagari-first typography is done, wider
   language coverage is not.
