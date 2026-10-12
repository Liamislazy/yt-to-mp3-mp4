#!/usr/bin/env bash
# One-time setup when a codespace is created.
set -euo pipefail

pip install --no-cache-dir -r requirements.txt

# Deno: the JavaScript runtime yt-dlp needs for YouTube.
curl -fsSL -o /tmp/deno.zip \
  https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip
python -c "import zipfile; zipfile.ZipFile('/tmp/deno.zip').extractall('/tmp/deno')"
sudo install -m 755 /tmp/deno/deno /usr/local/bin/deno
rm -rf /tmp/deno /tmp/deno.zip
deno --version
