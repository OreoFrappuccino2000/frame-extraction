import os
import uuid
import time
import shutil
import base64
import tempfile
import logging
import threading
import subprocess
import requests
from flask import Flask, request, jsonify, send_file, abort

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
FRAME_MAX_WIDTH = int(os.environ.get("FRAME_MAX_WIDTH", "512"))
FRAME_JPEG_QUALITY = int(os.environ.get("FRAME_JPEG_QUALITY", "8"))  # ffmpeg q:v 2(best)-31(worst)
MAX_FRAMES_DEFAULT = int(os.environ.get("MAX_FRAMES", "10"))
FRAMES_STORE = os.path.join(tempfile.gettempdir(), "frame_store")
FRAME_TTL_SECONDS = 600  # auto-delete frames after 10 minutes
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")

os.makedirs(FRAMES_STORE, exist_ok=True)

# Make bundled ffmpeg executable if present
_bundled = os.path.join(os.path.dirname(__file__), "bin", "ffmpeg")
if os.path.exists(_bundled):
    os.chmod(_bundled, 0o755)
    os.environ["PATH"] = os.path.dirname(_bundled) + ":" + os.environ.get("PATH", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cleanup_old_jobs():
    """Remove frame directories older than FRAME_TTL_SECONDS."""
    now = time.time()
    try:
        for name in os.listdir(FRAMES_STORE):
            job_dir = os.path.join(FRAMES_STORE, name)
            if os.path.isdir(job_dir):
                age = now - os.path.getmtime(job_dir)
                if age > FRAME_TTL_SECONDS:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    logger.info(f"Cleaned up expired job: {name}")
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")


def _probe_duration(video_path: str) -> float:
    """Get video duration in seconds via ffprobe."""
    cmd = [
        FFPROBE_BIN,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return float(result.stdout.strip())


def _extract_single_frame(video_path: str, timestamp: float, output_path: str):
    """Extract one frame as a downscaled JPEG."""
    scale_filter = f"scale='min({FRAME_MAX_WIDTH},iw)':-2"
    cmd = [
        FFMPEG_BIN,
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-vf", scale_filter,
        "-q:v", str(FRAME_JPEG_QUALITY),
        "-y",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error at ts={timestamp}: {result.stderr.strip()}")


def _extract_frames(video_path: str, max_frames: int, job_dir: str) -> dict:
    """Extract frames to job_dir and return metadata."""
    duration = _probe_duration(video_path)
    if duration <= 0:
        raise ValueError("Video duration is 0 or could not be determined.")

    n_frames = max(1, min(max_frames, int(duration)))
    interval = duration / n_frames
    timestamps = [round(interval * (i + 0.5), 3) for i in range(n_frames)]

    extracted = []
    for idx, ts in enumerate(timestamps):
        fname = f"frame_{idx + 1:03d}.jpg"
        out_path = os.path.join(job_dir, fname)
        try:
            _extract_single_frame(video_path, ts, out_path)
        except Exception as e:
            logger.warning(f"Failed to extract frame at ts={ts}: {e}")
            continue

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            h = int(ts // 3600)
            m = int((ts % 3600) // 60)
            s = ts % 60
            extracted.append({
                "index": idx + 1,
                "filename": fname,
                "timestamp_seconds": ts,
                "timestamp_formatted": f"{h:02d}:{m:02d}:{s:05.2f}",
            })

    if not extracted:
        raise RuntimeError("ffmpeg produced no output frames.")

    return {"frames": extracted, "duration": round(duration, 3)}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify(status="ok", service="frame-extraction")


@app.route("/extract_frames", methods=["POST"])
def extract_frames():
    """
    Extract frames from a video and return image URLs.

    Accepts JSON:
        video_url:   str  — publicly accessible video URL
        max_frames:  int  — max frames to extract (default 10)

    Returns JSON:
        {
            "success": true,
            "frames": [
                {
                    "index": 1,
                    "url": "https://.../frames/<job_id>/frame_001.jpg",
                    "timestamp_seconds": 1.5,
                    "timestamp_formatted": "00:00:01.50"
                },
                ...
            ],
            "count": 5,
            "duration_seconds": 10.0,
            "job_id": "<uuid>"
        }
    """
    # Cleanup old jobs in background
    threading.Thread(target=_cleanup_old_jobs, daemon=True).start()

    data = request.get_json(silent=True) or {}
    video_url = data.get("video_url", "").strip()
    max_frames = int(data.get("max_frames", MAX_FRAMES_DEFAULT))

    if not video_url:
        return jsonify(success=False, error="Provide video_url"), 400

    if max_frames < 1 or max_frames > 100:
        return jsonify(success=False, error="max_frames must be 1-100"), 400

    # Create job directory
    job_id = uuid.uuid4().hex[:12]
    job_dir = os.path.join(FRAMES_STORE, job_id)
    os.makedirs(job_dir, exist_ok=True)

    tmp_video = None
    try:
        # Download video
        logger.info(f"[{job_id}] Downloading video from: {video_url[:80]}...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4", dir="/tmp") as f:
            tmp_video = f.name
            resp = requests.get(video_url, timeout=120, stream=True)
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        logger.info(f"[{job_id}] Extracting up to {max_frames} frames...")
        result = _extract_frames(tmp_video, max_frames, job_dir)

        # Build public URLs for each frame
        # Use the Host header so URLs work regardless of domain
        base_url = request.url_root.rstrip("/")
        frames_out = []
        for fr in result["frames"]:
            frames_out.append({
                "index": fr["index"],
                "url": f"{base_url}/frames/{job_id}/{fr['filename']}",
                "timestamp_seconds": fr["timestamp_seconds"],
                "timestamp_formatted": fr["timestamp_formatted"],
            })

        logger.info(f"[{job_id}] Done — {len(frames_out)} frames extracted")
        return jsonify(
            success=True,
            frames=frames_out,
            count=len(frames_out),
            duration_seconds=result["duration"],
            job_id=job_id,
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"[{job_id}] Download failed: {e}")
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(success=False, error=f"Failed to download video: {str(e)}"), 400
    except Exception as e:
        logger.exception(f"[{job_id}] Extraction failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify(success=False, error=str(e)), 500
    finally:
        if tmp_video and os.path.exists(tmp_video):
            os.remove(tmp_video)


@app.route("/frames/<job_id>/<filename>", methods=["GET"])
def serve_frame(job_id, filename):
    """Serve an extracted frame as a JPEG image."""
    # Sanitize inputs to prevent path traversal
    if "/" in job_id or ".." in job_id or "/" in filename or ".." in filename:
        abort(400)

    frame_path = os.path.join(FRAMES_STORE, job_id, filename)
    if not os.path.isfile(frame_path):
        abort(404)

    return send_file(frame_path, mimetype="image/jpeg")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
