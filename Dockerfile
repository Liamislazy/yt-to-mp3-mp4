# Container image for hosting the web UI (Hugging Face Spaces, Render, Koyeb, ...).
FROM python:3.12-slim

# ffmpeg for converting; Deno is the JavaScript runtime yt-dlp needs for YouTube.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates \
 && curl -fsSL -o /tmp/deno.zip \
      https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip \
 && unzip -q /tmp/deno.zip -d /usr/local/bin \
 && rm /tmp/deno.zip \
 && apt-get purge -y curl unzip && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run containers as uid 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt gunicorn

COPY --chown=user ytconvert ./ytconvert

ENV YTC_CLOUD=1 \
    YTC_CLEANUP_HOURS=1 \
    YTC_DOWNLOAD_DIR=/tmp/ytc-downloads \
    PORT=7860
EXPOSE 7860

# One worker so the in-memory job list is shared; threads handle parallel requests.
CMD gunicorn --workers 1 --threads 8 --timeout 0 --bind 0.0.0.0:${PORT} ytconvert.web:app
