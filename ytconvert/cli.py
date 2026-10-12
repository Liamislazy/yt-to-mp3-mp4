"""Command-line interface: python -m ytconvert URL [URL ...] -f mp3|mp4"""

from __future__ import annotations

import argparse
import sys

from .core import FORMATS, MP3_BITRATES, MP4_HEIGHTS, download


def _print_progress(p: dict) -> None:
    stage = p.get("stage")
    if stage == "downloading":
        pct = p.get("percent")
        pct_txt = f"{pct:5.1f}%" if pct is not None else "  ...  "
        sys.stdout.write(f"\r  downloading {pct_txt}")
        sys.stdout.flush()
    elif stage == "converting":
        sys.stdout.write("\r  converting...          \n")
        sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ytconvert",
        description="Download YouTube links as MP3 (audio) or MP4 (video).",
    )
    parser.add_argument("urls", nargs="*", help="YouTube video URL(s)")
    parser.add_argument(
        "-f", "--format", choices=FORMATS, default="mp3", help="output format (default: mp3)"
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="",
        help=(
            f"MP3 bitrate kbps {'/'.join(MP3_BITRATES)} (default 192) or "
            f"MP4 max height {'/'.join(MP4_HEIGHTS)} (default best)"
        ),
    )
    parser.add_argument(
        "-o", "--output", default="downloads", help="output folder (default: ./downloads)"
    )
    parser.add_argument(
        "--playlist", action="store_true", help="download the whole playlist if the URL has one"
    )
    parser.add_argument(
        "--web", action="store_true", help="start the web UI instead of downloading"
    )
    parser.add_argument("--port", type=int, default=5000, help="web UI port (default: 5000)")
    args = parser.parse_args(argv)

    if args.web:
        from .web import run

        run(port=args.port)
        return 0

    if not args.urls:
        parser.error("give at least one URL, or use --web to open the web UI")

    failed = 0
    for url in args.urls:
        print(f"[{args.format}] {url}")
        try:
            results = download(
                url,
                fmt=args.format,
                quality=args.quality,
                outdir=args.output,
                playlist=args.playlist,
                on_progress=_print_progress,
            )
        except Exception as exc:  # yt-dlp raises DownloadError and friends
            failed += 1
            sys.stdout.flush()
            print(f"  error: {str(exc).removeprefix('ERROR: ')}", file=sys.stderr)
            continue
        for r in results:
            print(f"  saved: {r.path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
