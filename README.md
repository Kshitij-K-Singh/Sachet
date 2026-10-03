# Sachet

Sachet helps people spot the difference between financial education and
promotion in short-form content. Paste text, paste a reel link, upload a
screenshot, or add an audio/video clip; the app returns an explainable caution
rating and points to official sources. It is an awareness tool, not investment
advice.

## Run the demo

Start the API in one terminal:

```sh
cd api
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Start the web app in another terminal:

```sh
cd web
npm install
npm run dev
```

Open the local URL printed by Vite. Vite proxies `/api` requests to the local
API. Audio/video transcription and screenshot OCR use hosted APIs — set
`GROQ_API_KEY` (or `OPENAI_API_KEY`) and `GOOGLE_VISION_KEY` (or Azure
vision keys); the optional MuRIL second opinion needs the ML extras
(`pip install -r api/requirements-ml.txt`).

### Or run the API in Docker

This is the path that actually works on a clean machine — it installs ffmpeg
and the slim Python runtime; STT/OCR keys are passed at run time, nothing
heavy is compiled or downloaded at build time.

```sh
docker build -t sachet-api .
docker run --rm -p 8000:8000 \
  -e GROQ_API_KEY=... -e GOOGLE_VISION_KEY=... sachet-api
```

Build args: `PYTHON_VERSION` (default 3.12).

## Pasting a link

Paste a public YouTube, Instagram, X/Twitter or TikTok link and Sachet turns it
into a transcript. It prefers the post's own caption track, and only downloads
audio and transcribes it when there is none.

Because the server fetches a URL the user supplied, `POST /api/ingest-url` is
treated as an SSRF sink and is gated on an explicit platform allowlist plus a
resolved-IP check — see the "Residual risk" note in `api/ingest.py` before
adding a platform. Sachet never signs in to anything, so private and
login-gated posts do not work.

## Listening to a tab

The lowest-friction input: press **Listen**, pick the tab with the reel, and
Sachet records up to 30s of that tab's audio and transcribes it. No download, no
sign-in, no cookies — which is why it is worth having alongside link pasting.

It uses `navigator.mediaDevices.getDisplayMedia` and needs:

- **Chrome or Edge on desktop.** Tab audio is Chromium-only. **Firefox does not
  support it, and neither does Zen** — Zen is a Firefox fork, so it exposes
  `getDisplayMedia` but ignores the audio request and always returns a
  video-only stream. The UI detects this and says so up front rather than
  offering a button that can only record silence.
- **A secure page** — `https`, or `localhost`. A plain `http://` LAN address
  will not work, which matters if you are demoing off a projector.
- **"Share tab audio" ticked** in the picker. Miss it and the capture is
  *silent*, not broken, so the UI says so specifically rather than letting it
  surface later as "no speech detected".

The reel also has to be playing **with sound** — a lot of web video autoplays
muted, and that produces exactly the same silence. DRM-protected streams cannot
be captured at all; browsers block that deliberately.

Served from `web/public/capture-spike.html` (`/capture-spike.html`) is a
standalone harness for checking capture in your own browser before trusting the
app. Chrome's capture of DRM/EME content is intentionally blocked, and this app
does not attempt to work around it.

Implementation and evaluation details live under `api/README.md` and
`api/ml/README.md`.
