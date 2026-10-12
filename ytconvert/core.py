"""Core download/convert logic shared by the CLI and the web UI."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

FORMATS = ("mp3", "mp4")
MP3_BITRATES = ("320", "256", "192", "128")
MP4_HEIGHTS = ("best", "2160", "1440", "1080", "720", "480", "360")

ProgressCallback = Callable[[dict], None]


def ffmpeg_path() -> Optional[str]:
    """Return an ffmpeg executable: the system one if on PATH, else the bundled one."""
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


@dataclass
class Result:
    title: str
    path: Path


class _SilentLogger:
    """Swallow yt-dlp's own console output; errors still surface as exceptions."""

    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


def _build_options(fmt: str, quality: str, outdir: Path, playlist: bool) -> dict:
    ffmpeg = ffmpeg_path()
    if ffmpeg is None:
        raise RuntimeError(
            "ffmpeg not found. Install it or run `pip install imageio-ffmpeg`."
        )

    opts: dict = {
        "outtmpl": str(outdir / "%(title)s [%(id)s].%(ext)s"),
        "ffmpeg_location": ffmpeg,
        "noplaylist": not playlist,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _SilentLogger(),
        "restrictfilenames": False,
        "windowsfilenames": True,
    }

    if fmt == "mp3":
        bitrate = quality if quality in MP3_BITRATES else "192"
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            },
            {"key": "FFmpegMetadata"},
        ]
    elif fmt == "mp4":
        height = quality if quality in MP4_HEIGHTS else "best"
        cap = "" if height == "best" else f"[height<={height}]"
        # Prefer H.264 + AAC so the file plays everywhere; fall back to anything.
        opts["format"] = (
            f"bv*{cap}[vcodec^=avc1]+ba[acodec^=mp4a]/"
            f"bv*{cap}+ba/b{cap}/b"
        )
        opts["merge_output_format"] = "mp4"
        opts["postprocessors"] = [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
            {"key": "FFmpegMetadata"},
        ]
    else:
        raise ValueError(f"Unsupported format {fmt!r}; choose one of {FORMATS}")

    return opts


def download(
    url: str,
    fmt: str = "mp3",
    quality: str = "",
    outdir: str | Path = "downloads",
    playlist: bool = False,
    on_progress: Optional[ProgressCallback] = None,
) -> list[Result]:
    """Download ``url`` and convert it to ``fmt`` ("mp3" or "mp4").

    ``quality`` is an MP3 bitrate in kbps (e.g. "320") or an MP4 max height
    (e.g. "1080"). Returns one Result per finished file.
    """
    outdir = Path(outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    opts = _build_options(fmt, quality, outdir, playlist)
    results: list[Result] = []

    def progress_hook(d: dict) -> None:
        if on_progress is None:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            on_progress(
                {
                    "stage": "downloading",
                    "percent": (done / total * 100) if total else None,
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                    "title": (d.get("info_dict") or {}).get("title"),
                }
            )
        elif d.get("status") == "finished":
            on_progress({"stage": "converting", "percent": 100})

    def postprocessor_hook(d: dict) -> None:
        # Fires after every postprocessor; the last "finished" one has the final path.
        if d.get("status") != "finished":
            return
        info = d.get("info_dict") or {}
        path = info.get("filepath")
        if path and d.get("postprocessor") == "MoveFiles":
            results.append(Result(title=info.get("title", ""), path=Path(path)))

    opts["progress_hooks"] = [progress_hook]
    opts["postprocessor_hooks"] = [postprocessor_hook]

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if on_progress is not None:
        on_progress({"stage": "done", "percent": 100})
    return results
