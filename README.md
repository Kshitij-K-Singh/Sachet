# Sachet

Sachet helps people spot the difference between financial education and
promotion in short-form content. Paste text, upload a screenshot, or add an
audio/video clip; the app returns an explainable caution rating and points to
official sources. It is an awareness tool, not investment advice.

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
API. Audio/video transcription additionally needs `ffmpeg` and the bundled
Whisper.cpp executable and base model. Screenshot OCR and the optional model
second opinion use local model packages/artifacts.

Implementation and evaluation details live under `api/README.md` and
`api/ml/README.md`.
