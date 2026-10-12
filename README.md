# YT Convert — YouTube to MP3 / MP4

Paste a YouTube link and get an **MP3** (audio) or **MP4** (video) file.
Comes with a simple local **web UI** and a **command-line** tool. Built on
[yt-dlp](https://github.com/yt-dlp/yt-dlp); ffmpeg is bundled through
`imageio-ffmpeg`, so you don't need to install it separately.

## Install

Requires Python 3.9+.

```bash
git clone https://github.com/Liamislazy/yt-to-mp3-mp4.git
cd yt-to-mp3-mp4
pip install -r requirements.txt
```

## Web UI

```bash
python -m ytconvert --web
```

Open <http://127.0.0.1:5000>, paste a link, choose MP3 or MP4 and a quality,
then click **Convert**. When it's ready, click **Download**. You can queue
several links at once. On Windows you can also just double-click `run_web.bat`.

## Command line

```bash
# MP3 (default 192 kbps)
python -m ytconvert "https://www.youtube.com/watch?v=VIDEO_ID"

# MP3 at 320 kbps
python -m ytconvert -f mp3 -q 320 "https://youtu.be/VIDEO_ID"

# MP4, best quality up to 1080p
python -m ytconvert -f mp4 -q 1080 "https://youtu.be/VIDEO_ID"

# Several links, custom folder
python -m ytconvert -f mp4 -o ~/Videos URL1 URL2 URL3

# Whole playlist
python -m ytconvert --playlist "https://www.youtube.com/playlist?list=..."
```

| Option | Meaning |
| --- | --- |
| `-f, --format` | `mp3` or `mp4` (default `mp3`) |
| `-q, --quality` | MP3: `320` / `256` / `192` / `128` kbps. MP4: `best` / `2160` / `1440` / `1080` / `720` / `480` / `360` (max height) |
| `-o, --output` | Output folder (default `./downloads`) |
| `--playlist` | Download every video if the link points to a playlist |
| `--web` / `--port` | Start the web UI (default port 5000) |

If you install the package (`pip install .`), the `ytconvert` command is
available directly, e.g. `ytconvert -f mp4 URL`.

## Use from Python

```python
from ytconvert import download

for r in download("https://youtu.be/VIDEO_ID", fmt="mp3", quality="320"):
    print(r.title, r.path)
```

## Notes

- MP4 output prefers H.264 video + AAC audio so it plays everywhere; if a
  video isn't available in that codec, the best stream is used instead.
- If downloads start failing, YouTube has probably changed something —
  update yt-dlp: `pip install -U yt-dlp`.
- Only download content you own or have permission to download, and respect
  YouTube's Terms of Service and copyright law.
