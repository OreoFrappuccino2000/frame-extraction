import os
import json
import subprocess
import tempfile
import urllib.request
import uuid

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
FFMPEG_BIN  = "ffmpeg"
FFPROBE_BIN = "ffprobe"

# Output directory — must be served by a static file server.
# Override via environment variable if needed.
OUTPUT_DIR      = os.environ.get("MERGED_DIR", "/tmp/media/merged")
OUTPUT_BASE_URL = os.environ.get("OUTPUT_BASE_URL", "http://localhost:8000/merged")


def main(
    video_url: str,
    audio_url: str,
    video_duration: float,
    audio_duration: float,
    job_id: str = "",
) -> dict:
    """
    Dify Code Node: Audio-Video Merge

    Downloads the original video and the TTS audio, then uses ffmpeg to
    replace the video's audio track with the synthesised voiceover.

    Handles duration mismatches:
      - audio shorter than video → pad with silence
      - audio longer than video  → truncate audio to video length

    Args:
        video_url:       URL of the original video file.
        audio_url:       URL of the TTS-synthesised audio file (WAV/MP3).
        video_duration:  Known video duration in seconds (from frame extraction).
        audio_duration:  Known audio duration in seconds (from TTS node).
        job_id:          Optional job identifier for output file naming.

    Returns:
        dict with keys:
            output_video_url   – publicly accessible URL of the merged video
            video_duration     – video duration (seconds)
            audio_duration     – audio duration used (seconds, after pad/trim)
            job_id             – job identifier used
            error              – None on success, error dict on failure
    """
    if not video_url:
        return _error("input_validation", "NO_VIDEO_URL", "video_url is required.")
    if not audio_url:
        return _error("input_validation", "NO_AUDIO_URL", "audio_url is required.")

    job_id = job_id or str(uuid.uuid4())[:8]
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        # ── 1. Download video ─────────────────────────────────────────────────
        video_ext  = _ext_from_url(video_url, ".mp4")
        video_path = os.path.join(tmpdir, f"input_video{video_ext}")
        try:
            _download(video_url, video_path)
        except Exception as exc:
            return _error("download", "VIDEO_DOWNLOAD_FAILED", str(exc))

        # ── 2. Download audio ─────────────────────────────────────────────────
        audio_ext  = _ext_from_url(audio_url, ".wav")
        audio_path = os.path.join(tmpdir, f"input_audio{audio_ext}")
        try:
            _download(audio_url, audio_path)
        except Exception as exc:
            return _error("download", "AUDIO_DOWNLOAD_FAILED", str(exc))

        # ── 3. Probe actual durations if not provided ─────────────────────────
        if video_duration <= 0:
            try:
                video_duration = _probe_duration(video_path)
            except Exception as exc:
                return _error("ffprobe", "VIDEO_PROBE_FAILED", str(exc))

        if audio_duration <= 0:
            try:
                audio_duration = _probe_duration(audio_path)
            except Exception as exc:
                return _error("ffprobe", "AUDIO_PROBE_FAILED", str(exc))

        # ── 4. Prepare audio: pad or trim to match video duration ─────────────
        prepared_audio_path = os.path.join(tmpdir, "prepared_audio.wav")
        try:
            effective_audio_duration = _prepare_audio(
                audio_path, prepared_audio_path, video_duration, audio_duration
            )
        except Exception as exc:
            return _error("ffmpeg", "AUDIO_PREP_FAILED", str(exc))

        # ── 5. Merge video + prepared audio ───────────────────────────────────
        output_filename = f"voiceover_{job_id}.mp4"
        output_path     = os.path.join(OUTPUT_DIR, output_filename)
        try:
            _merge_av(video_path, prepared_audio_path, output_path, video_duration)
        except Exception as exc:
            return _error("ffmpeg", "MERGE_FAILED", str(exc))

        output_video_url = f"{OUTPUT_BASE_URL.rstrip('/')}/{output_filename}"

        return {
            "output_video_url":  output_video_url,
            "video_duration":    round(video_duration, 3),
            "audio_duration":    round(effective_audio_duration, 3),
            "job_id":            job_id,
            "error":             None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _download(url: str, dest_path: str):
    """Download a URL to dest_path with a streaming read."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, \
         open(dest_path, "wb") as out:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out.write(chunk)


def _probe_duration(path: str) -> float:
    """Use ffprobe to get media duration in seconds."""
    cmd = [
        FFPROBE_BIN,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr.strip()}")
    info = json.loads(result.stdout)
    return float(info.get("format", {}).get("duration", 0))


def _prepare_audio(
    src_path: str,
    dst_path: str,
    video_duration: float,
    audio_duration: float,
) -> float:
    """
    Pad (with silence) or trim the audio so it matches video_duration exactly.
    Returns the effective audio duration after adjustment.
    """
    if abs(audio_duration - video_duration) < 0.05:
        # Close enough — just copy
        cmd = [FFMPEG_BIN, "-y", "-i", src_path, "-c", "copy", dst_path]
        _run_ffmpeg(cmd)
        return audio_duration

    if audio_duration < video_duration:
        # Pad with silence at the end
        silence_duration = video_duration - audio_duration
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", src_path,
            "-f", "lavfi", "-t", str(silence_duration), "-i", "anullsrc=r=44100:cl=mono",
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[outa]",
            "-map", "[outa]",
            dst_path,
        ]
        _run_ffmpeg(cmd)
        return video_duration
    else:
        # Trim audio to video duration
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", src_path,
            "-t", str(video_duration),
            "-c", "copy",
            dst_path,
        ]
        _run_ffmpeg(cmd)
        return video_duration


def _merge_av(
    video_path: str,
    audio_path: str,
    output_path: str,
    video_duration: float,
):
    """
    Replace the video's audio track with the prepared audio.
    Preserves original video codec and quality.
    """
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", video_path,
        "-i", audio_path,
        # Map video stream from input 0, audio stream from input 1
        "-map", "0:v:0",
        "-map", "1:a:0",
        # Copy video codec (no re-encode → preserves quality)
        "-c:v", "copy",
        # Encode audio as AAC for MP4 container compatibility
        "-c:a", "aac",
        "-b:a", "128k",
        # Ensure output duration matches video
        "-t", str(video_duration),
        # Shortest flag as safety net
        "-shortest",
        output_path,
    ]
    _run_ffmpeg(cmd)


def _run_ffmpeg(cmd: list):
    """Run an ffmpeg command and raise on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")


def _ext_from_url(url: str, default: str = ".mp4") -> str:
    """Extract file extension from URL path."""
    path = url.split("?")[0]
    ext  = os.path.splitext(path)[1].lower()
    return ext if ext else default


def _error(stage: str, code: str, message: str) -> dict:
    """Return a standardised error response."""
    return {
        "output_video_url": "",
        "video_duration":   0.0,
        "audio_duration":   0.0,
        "job_id":           "",
        "error": {
            "error_stage":   stage,
            "error_code":    code,
            "error_message": message,
        },
    }
