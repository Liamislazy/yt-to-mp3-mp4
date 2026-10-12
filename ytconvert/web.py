"""Small local web UI: paste a link, pick MP3 or MP4, get the file."""

from __future__ import annotations

import hmac
import os
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, Response, abort, jsonify, render_template, request, send_file

from .core import FORMATS, download

# Settings, overridable through environment variables (used by the Docker image).
DOWNLOAD_DIR = Path(os.environ.get("YTC_DOWNLOAD_DIR", "downloads"))
MAX_PARALLEL = int(os.environ.get("YTC_MAX_PARALLEL", "3"))
# Delete finished files older than this many hours (0 = keep forever).
CLEANUP_HOURS = float(os.environ.get("YTC_CLEANUP_HOURS", "0"))
# True when hosted online: hides the "saved next to the app" hint.
CLOUD = os.environ.get("YTC_CLOUD", "") == "1"
# When set, the browser asks for this password (any username) before showing the app.
PASSWORD = os.environ.get("YTC_PASSWORD", "")

app = Flask(__name__)
_executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL)
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


@app.before_request
def _require_password():
    if not PASSWORD:
        return None
    auth = request.authorization
    given = (auth.password or "") if auth else ""
    if hmac.compare_digest(given.encode(), PASSWORD.encode()):
        return None
    return Response(
        "Password required.", 401, {"WWW-Authenticate": 'Basic realm="YT Convert"'}
    )


def _cookies_file() -> str | None:
    """Cookies for yt-dlp: a file path (YTC_COOKIES_FILE) or the raw cookies.txt
    text (YT_COOKIES, handy as a hosting secret), which is written to a temp file."""
    path = os.environ.get("YTC_COOKIES_FILE")
    if path:
        return path
    text = os.environ.get("YT_COOKIES", "").strip()
    if not text:
        return None
    fd, tmp = tempfile.mkstemp(prefix="ytc-cookies-", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return tmp


COOKIES = _cookies_file()


def _cleanup_old_files() -> None:
    if CLEANUP_HOURS <= 0 or not DOWNLOAD_DIR.is_dir():
        return
    cutoff = time.time() - CLEANUP_HOURS * 3600
    for f in DOWNLOAD_DIR.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def _update(job_id: str, **fields) -> None:
    with _lock:
        _jobs[job_id].update(fields)


def _run_job(job_id: str, url: str, fmt: str, quality: str) -> None:
    def on_progress(p: dict) -> None:
        fields = {"stage": p.get("stage"), "percent": p.get("percent")}
        if p.get("title"):
            fields["title"] = p["title"]
        _update(job_id, **fields)

    _update(job_id, status="running", stage="starting")
    _cleanup_old_files()
    try:
        results = download(
            url,
            fmt=fmt,
            quality=quality,
            outdir=DOWNLOAD_DIR,
            on_progress=on_progress,
            cookies=COOKIES,
        )
    except Exception as exc:
        _update(job_id, status="error", error=str(exc).replace("ERROR: ", ""))
        return
    if not results:
        _update(job_id, status="error", error="Nothing was downloaded.")
        return
    _update(
        job_id,
        status="done",
        stage="done",
        percent=100,
        title=results[0].title,
        files=[str(r.path) for r in results],
    )


def _public(job_id: str, job: dict) -> dict:
    files = job.get("files") or []
    return {
        "id": job_id,
        "status": job["status"],
        "stage": job.get("stage"),
        "percent": job.get("percent"),
        "title": job.get("title"),
        "format": job["format"],
        "error": job.get("error"),
        "files": [
            {"name": Path(f).name, "url": f"/api/jobs/{job_id}/files/{i}"}
            for i, f in enumerate(files)
        ],
    }


@app.get("/")
def index():
    return render_template("index.html", cloud=CLOUD)


@app.post("/api/jobs")
def create_job():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    fmt = str(data.get("format", "mp3")).lower()
    quality = str(data.get("quality", "")).strip()

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return jsonify(error="Please paste a valid http(s) link."), 400
    if fmt not in FORMATS:
        return jsonify(error=f"Format must be one of {', '.join(FORMATS)}."), 400

    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {"status": "queued", "format": fmt, "url": url}
    _executor.submit(_run_job, job_id, url, fmt, quality)
    return jsonify(id=job_id), 202


@app.get("/api/jobs/<job_id>")
def job_status(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            abort(404)
        return jsonify(_public(job_id, job))


@app.get("/api/jobs/<job_id>/files/<int:index>")
def job_file(job_id: str, index: int):
    with _lock:
        job = _jobs.get(job_id)
        files = list(job.get("files") or []) if job else []
    if not 0 <= index < len(files):
        abort(404)
    path = Path(files[index])
    if not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=path.name)


def run(host: str = "127.0.0.1", port: int = 5000) -> None:
    print(f"YT Convert running at http://{host}:{port}  (files saved to {DOWNLOAD_DIR.resolve()})")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run()
