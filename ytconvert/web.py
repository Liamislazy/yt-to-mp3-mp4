"""Small local web UI: paste a link, pick MP3 or MP4, get the file."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, render_template, request, send_file

from .core import FORMATS, download

DOWNLOAD_DIR = Path("downloads")
MAX_PARALLEL = 3

app = Flask(__name__)
_executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL)
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


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
    try:
        results = download(url, fmt=fmt, quality=quality, outdir=DOWNLOAD_DIR, on_progress=on_progress)
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
    return render_template("index.html")


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
