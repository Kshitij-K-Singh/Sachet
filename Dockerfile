# syntax=docker/dockerfile:1
#
# Sachet API image.
#
#   docker build -t sachet-api .
#   docker run --rm -p 8000:8000 \
#     -e GROQ_API_KEY=... -e GOOGLE_VISION_KEY=... sachet-api
#
# Single stage, no compiler, no model downloads. Transcription and OCR are
# hosted APIs (see api/transcribe.py and api/ocr.py), so this image builds
# in ~1-2 minutes with only:
#
#   system  ffmpeg/ffprobe (apt, seconds) for audio normalization
#   python  slim runtime deps from api/requirements.txt (no torch, no
#           transformers, no easyocr, no whisper.cpp compile)
#
# Configuration is by environment at RUN time, never baked into the image:
#
#   GROQ_API_KEY / OPENAI_API_KEY (or SACHET_STT_ENDPOINT + SACHET_STT_API_KEY)
#   GOOGLE_VISION_KEY (or AZURE_VISION_ENDPOINT + AZURE_VISION_KEY)
#   SACHET_MODEL=off to disable the optional MuRIL shadow classifier
#     (the slim image has no torch, so it is off by default)
#
# Two things this file exists to get right:
#
#   1. ffmpeg is installed by apt, not copied between stages. Copying
#      /usr/bin/ffmpeg alone yields a binary that cannot resolve
#      libavcodec and friends.
#   2. One uvicorn worker on purpose. Hosted STT/OCR are network-bound and
#      ingest.py's MAX_CONCURRENT bounds paste requests inside the process;
#      extra workers would multiply concurrent API spend. Scale with
#      replicas, not workers.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SACHET_MODEL=off \
    PATH="/opt/venv/bin:${PATH}"

# ffmpeg/ffprobe are hard runtime dependencies: transcribe.py shells out to
# both with no Python fallback.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && ffmpeg -version > /dev/null \
 && ffprobe -version > /dev/null

COPY api/requirements.txt /tmp/requirements.txt

RUN python -m venv /opt/venv \
 && pip install --upgrade pip \
 && pip install -r /tmp/requirements.txt \
 && python -c "import fastapi, uvicorn, yt_dlp, PIL" \
 && yt-dlp --version

WORKDIR /app
COPY api/*.py ./
COPY api/ml ./ml
COPY api/data ./data

RUN useradd --create-home --uid 10001 sachet \
 && chown -R sachet:sachet /app

# Every upload, URL fetch and intermediate wav is written under /tmp, so it must
# be writable by the unprivileged app user.
RUN chmod 1777 /tmp
USER sachet

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request as u,sys; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

# One worker on purpose (see header comment). Scale with replicas.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
