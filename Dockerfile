# syntax=docker/dockerfile:1
#
# Sachet API image.
#
#   docker build -t sachet-api .
#   docker run --rm -p 8000:8000 sachet-api
#
# Three stages, because the heavy dependencies have incompatible needs:
#
#   whisper  compiles whisper.cpp; only its output needs to survive.
#   deps     resolves the Python tree once into a venv and warms the HuggingFace
#            cache while the network is obviously available.
#   runtime  carries no compiler, no git, no apt cache.
#
# Four things this file exists to get right, each a common way a containerised
# ML service breaks:
#
#   1. GGML_NATIVE=OFF. whisper.cpp defaults to -march=native, baking the build
#      machine's CPU into the binary. Build somewhere with AVX-512, run
#      elsewhere, and whisper-cli takes SIGILL on the first request.
#   2. CPU-only torch. requirements.txt does not pin torch, so a plain
#      `pip install -r` drags in the CUDA build and gigabytes of driver
#      libraries for an image that will never see a GPU.
#   3. ffmpeg is installed in the runtime stage by apt, not copied from deps.
#      Copying /usr/bin/ffmpeg alone yields a binary that cannot resolve
#      libavcodec and friends.
#   4. The Whisper model and the FFmpeg/yt-dlp binaries are real dependencies of
#      this service, so they get installed rather than assumed present on a host.

ARG PYTHON_VERSION=3.12
ARG WHISPER_COMMIT=6e4ab854f67f743900934a703d5603419384c961
ARG WHISPER_MODEL=ggml-base.bin


# --------------------------------------------------------------- whisper.cpp --
FROM debian:bookworm-slim AS whisper

ARG WHISPER_COMMIT
ARG WHISPER_MODEL

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates cmake g++ git make \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --filter=blob:none https://github.com/ggml-org/whisper.cpp.git . \
 && git checkout --detach "${WHISPER_COMMIT}" \
 && git submodule update --init --recursive

# BUILD_SHARED_LIBS=OFF keeps whisper-cli statically linked against ggml, so the
# runtime stage needs no LD_LIBRARY_PATH and no .so files to keep in sync.
RUN cmake -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_NATIVE=OFF \
      -DBUILD_SHARED_LIBS=OFF \
 && cmake --build build --config Release --target whisper-cli -j "$(nproc)" \
 && install -D -m 0755 build/bin/whisper-cli /out/build/bin/whisper-cli

# Belt and braces: if a future cmake ignores BUILD_SHARED_LIBS, whisper-cli ends
# up dynamically linked. Drop the .so files next to the binary so its $ORIGIN
# RPATH resolves them, rather than relying on LD_LIBRARY_PATH in the runtime.
RUN find build/bin -name '*.so*' -exec install -m 0755 {} /out/build/bin/ \; || true

RUN curl -fsSL -o "/out/models/${WHISPER_MODEL}" \
      "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${WHISPER_MODEL}" \
 && test -s "/out/models/${WHISPER_MODEL}"


# ----------------------------------------------------------------- python deps --
FROM python:${PYTHON_VERSION}-slim AS deps

# A venv at a fixed path keeps the runtime stage's COPY honest: the paths below
# do not have to hardcode a python3.X version, so --build-arg PYTHON_VERSION
# actually works.
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf \
    PATH="/opt/venv/bin:${PATH}"

COPY api/requirements.txt /tmp/requirements.txt

RUN python -m venv /opt/venv

# CPU-only torch first: the later `pip install -r` then finds its requirement
# already satisfied instead of resolving back to the CUDA wheel.
RUN pip install --upgrade pip \
 && pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r /tmp/requirements.txt

# Pre-fetch the MuRIL base model. Otherwise the shadow classifier reaches for
# huggingface.co on its first request and fails on an air-gapped demo machine.
# infer.py already degrades gracefully when the LoRA adapter is absent, but a
# missing *base* model is a hard error. Deliberately a one-liner rather than a
# heredoc, so the build needs no BuildKit-specific syntax.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('google/muril-base-cased', allow_patterns=['config.json','modules.json','generation_config.json','tokenizer*','vocab*','special_tokens_map.json','sentencepiece*','model.safetensors'])"

# yt-dlp is a console script from requirements.txt, which is what puts it on
# PATH for ingest.py; assert it here so a missing entry fails the build, not
# the first paste.
RUN python -c "import fastapi, uvicorn, torch, easyocr, yt_dlp" \
 && yt-dlp --version \
 && test -s /opt/hf


# --------------------------------------------------------------------- runtime --
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf \
    PATH="/opt/venv/bin:${PATH}"

# ffmpeg/ffprobe are hard runtime dependencies: transcribe.py shells out to both
# with no Python fallback. libgomp1 is torch's OpenMP runtime -- without it
# `import torch` warns and easyocr's detection passes fail.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && ffmpeg -version > /dev/null \
 && ffprobe -version > /dev/null

COPY --from=deps /opt/venv /opt/venv
COPY --from=deps /opt/hf /opt/hf

# transcribe.py resolves these relative to __file__, so the layout has to match
# the repo: whisper.cpp/build/bin/whisper-cli and whisper.cpp/models/ggml-*.bin.
COPY --from=whisper /out /app/whisper.cpp

WORKDIR /app
COPY api/*.py ./
COPY api/ml ./ml
COPY api/data ./data

RUN chmod 0755 /app/whisper.cpp/build/bin/whisper-cli \
 && useradd --create-home --uid 10001 sachet \
 && chown -R sachet:sachet /app /opt/hf

# Every upload, URL fetch and intermediate wav is written under /tmp, so it must
# be writable by the unprivileged app user.
RUN chmod 1777 /tmp
USER sachet

EXPOSE 8000

# transcribe.py only returns after a 300 s whisper timeout, so the probe has to
# be far shorter than that to notice a wedged worker.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request as u,sys; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

# One worker on purpose. Whisper is CPU-bound and ingest.py's MAX_CONCURRENT
# bounds paste requests inside a process; extra uvicorn workers would multiply
# both and oversubscribe the box. Scale with replicas, not workers.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
