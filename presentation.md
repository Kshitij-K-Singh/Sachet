# Sachet — 5-Slide Presentation Brief

Purpose: give this file to an AI slide maker to produce a polished hackathon presentation.
Project: Sachet, a promotion-vs-education analyzer for financial reels, captions, audio, screenshots, and links.
Event/track: Sangyan 2026, Track E.
Tone: trustworthy, calm, evidence-first; no hype, no investment advice.

## Global design directions for the slide maker
- Theme: premium dark-first with one light alternative; do not use rainbow gradients.
- Palette: near-black warm background, cream text, burnt-orange accent `#e95a2b`.
- Severity colors only for verdicts: green/amber/red as status signals, not decoration.
- Typography: large display headlines, generous whitespace, tabular numerals for scores.
- Devanagari-first: Hindi headlines must use correct conjuncts and matras; never split Devanagari glyphs character-by-character.
- Visual language: rounded cards, soft elevation, subtle orange pixel/dot texture in backgrounds.
- Imagery: product UI screenshots preferred over stock photos; show verdict, flagged claims, guidance, and SEBI links.
- Avoid: investment tips, profit promises, “AI guarantees truth,” cluttered bullet walls.

## Slide 1 — The problem
Cover: “Does it teach, or does it sell?”
- Financial reels mix real lessons with paid-group pitches, guaranteed returns, urgency, testimonials, and fake authority.
- Viewers cannot easily tell education from promotion.
- Sachet’s job: flag exact claims and rate content as teaches, sells, or both.
- Visual: split hero image or headline with “teach” vs “sell.”
- Speaker note: frame this as investor-awareness, not investment advice.

## Slide 2 — How Sachet works
Cover: paste text, audio, screenshot, tab audio, or video link.
- Inputs: pasted text, uploaded audio/video, screenshot OCR, live tab capture, public reel/video links.
- Pipeline: transcribe or extract text, match rubric patterns, score caution, surface verbatim evidence.
- Outputs: verdict, caution score, flagged claims, verification checklist, next steps.
- Visual: simple 3-step pipeline diagram: Input → Rubric → Verdict plus evidence.
- Speaker note: emphasize review-before-verdict and offline demo fallback.

## Slide 3 — Evidence, not black-box AI
Cover: rubric v1.5 and auditable results.
- Fixed rubric categories: unrealistic returns, risk denial, fake authority, paid CTA, urgency, social proof, missing disclosure.
- Every claim shows verbatim quote, claim type, flags, and reason.
- Official verification panel links to SEBI pages; promotion results include SEBI SCORES reporting.
- Visual: screenshot of flagged source, flagged claims, caution meter, and official-source cards.
- Speaker note: the system explains itself; users can audit the match.

## Slide 4 — Built for real users
Cover: Hindi/English, dark/light, mobile-first.
- Full UI language switch: English and Hindi chrome plus localized result prose.
- Dark and light themes with accessible severity colors.
- Mobile-first responsive layout; verified at 390px, 768px, and 1280px.
- Privacy posture: uploads discarded, text analyzed in memory, uncertainty shown as “cannot verify.”
- Visual: side-by-side Hindi/English screenshots and dark/light screenshots.
- Speaker note: localization is functional, not cosmetic.

## Slide 5 — Demo and deployment
Cover: live flow plus readiness.
- Demo path: paste promotional reel text → verdict → flagged claims → guidance → SEBI SCORES report link.
- API: FastAPI service with health check and localized `/api/analyze` responses.
- Deployment: API-only Dockerfile with pinned whisper.cpp, CPU-only torch, ffmpeg, HF cache warm-up, non-root runtime, and healthcheck.
- Visual: live demo screenshot plus architecture strip: Web UI → FastAPI → rubric/ML assist → official sources.
- Speaker note: end with awareness-tool disclaimer, not investment advice.
