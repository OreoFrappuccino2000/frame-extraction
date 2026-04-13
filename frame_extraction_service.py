"""
frame_extraction_service.py
────────────────────────────
Lightweight Flask HTTP service that performs ffmpeg-based video frame
extraction. Designed to be called by the Dify Code Node (frame_extraction_node.py)
which cannot run subprocess or write files directly.

Usage:
    pip install flask
    python frame_extraction_service.py

Endpoints:
    POST /extract
        Request JSON:
            {
                "video_url":  "<url>",
                "max_frames": 20,          # optional, default 20
                "filename":   "video.mp4", # optional, for logging
                "mime_type":  "video/mp4"  # optional, for logging
            }
        Response JSON:
            {
                "frames": [...],
                "video_duration": 15.3,
                "total_frames_extracted": 20,
                "error": null
            }

    GET /health
        Returns {"status": "ok"}
"""

import os
import json
import base64
import subprocess
import tempfile
import urllib.request
from flask import Flask, request, jsonify

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
MAX_FRAMES           = 20
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
FFMPEG_BIN           = os.environ.get("FFMPEG_BIN",  "ffmpeg")
FFPROBE_BIN          = os.environ.get("FFPROBE_BIN", "ffprobe")
HOST                 = os.environ.get("HOST", "0.0.0.0")
PORT                 = int(os.environ.get("PORT", 10000))  # Render uses PORT env var

app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/extract", methods=["POST"])
def extract():
    body = request.get_json(force=True, silent=True) or {}

    video_url  = body.get("video_url", "").strip()
    max_frames = int(body.get("max_frames", MAX_FRAMES))
    filename   = body.get("filename", "video.mp4")

    if not video_url:
        return jsonify(_error("input_validation", "NO_VIDEO_URL",
                              "video_url is required.")), 400

    extension = _splitext(filename) or ".mp4"
    if extension not in SUPPORTED_EXTENSIONS:
        return jsonify(_error("input_validation", "UNSUPPORTED_FORMAT",
                              f"Extension '{extension}' not supported.")), 400

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Download video
        video_path = os.path.join(tmpdir, f"input{extension}")
        try:
            _download(video_url, video_path)
        except Exception as exc:
            return jsonify(_error("download", "DOWNLOAD_FAILED", str(exc))), 502

        # 2. Probe duration
        try:
            duration = _probe_duration(video_path)
        except Exception as exc:
            return jsonify(_error("ffprobe", "PROBE_FAILED", str(exc))), 500

        if duration <= 0:
            return jsonify(_error("ffprobe", "INVALID_DURATION",
                                  "Video duration is 0 or could not be determined.")), 422

        # 3. Calculate uniform timestamps
        n_frames   = max(1, min(max_frames, int(duration)))
        interval   = duration / n_frames
        timestamps = [round(interval * (i + 0.5), 3) for i in range(n_frames)]

        # 4. Extract frames
        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        extracted_frames = []
        for idx, ts in enumerate(timestamps):
            frame_path = os.path.join(frames_dir, f"frame_{idx+1:03d}.jpg")
            try:
                _extract_frame(video_path, ts, frame_path)
            except Exception:
                continue  # skip unextractable frames

            if not os.path.exists(frame_path):
                continue

            with open(frame_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            extracted_frames.append({
                "frame_index":         idx + 1,
                "timestamp_seconds":   ts,
                "timestamp_formatted": _fmt_ts(ts),
                "image_base64":        b64,
                "image_mime":          "image/jpeg",
            })

        if not extracted_frames:
            return jsonify(_error("ffmpeg", "NO_FRAMES_EXTRACTED",
                                  "ffmpeg ran but produced no output frames.")), 500

        return jsonify({
            "frames":                extracted_frames,
            "video_duration":        round(duration, 3),
            "total_frames_extracted": len(extracted_frames),
            "error":                 None,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _download(url: str, dest_path: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, \
         open(dest_path, "wb") as out:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out.write(chunk)


def _probe_duration(video_path: str) -> float:
    cmd = [FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
           "-show_format", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr.strip()}")
    info = json.loads(result.stdout)
    return float(info.get("format", {}).get("duration", 0))


def _extract_frame(video_path: str, timestamp: float, output_path: str):
    cmd = [
        FFMPEG_BIN,
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        "-y",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error at ts={timestamp}: {result.stderr.strip()}")


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def _splitext(filename: str) -> str:
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _error(stage: str, code: str, message: str) -> dict:
    return {
        "frames":                [],
        "video_duration":        0.0,
        "total_frames_extracted": 0,
        "error": {
            "error_stage":   stage,
            "error_code":    code,
            "error_message": message,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
