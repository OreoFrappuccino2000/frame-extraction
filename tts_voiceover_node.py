import json
import struct
import urllib.request
import urllib.error
import urllib.parse

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
WORDS_PER_SECOND_EN = 2.5   # average English speaking rate
CHARS_PER_SECOND_ZH = 4.5   # average Mandarin speaking rate (chars/sec)
MAX_RETRIES         = 2      # max speed-adjustment retries
DURATION_TOLERANCE  = 0.20   # 20% tolerance before speed adjustment
SPEED_MIN           = 0.75
SPEED_MAX           = 1.50


def main(
    script_text: str,
    video_duration: float,
    tts_api_url: str,
    tts_api_key: str,
    language: str = "en",
    voice_id: str = "default",
    speed: float = 1.0,
    retry_count: int = 0,
) -> dict:
    """
    Dify Code Node: TTS Voiceover Synthesis

    Calls a TTS HTTP API to synthesise the voiceover script, then checks
    whether the resulting audio duration is within ±20% of the video duration.
    If not, it adjusts the speed and retries (up to MAX_RETRIES times).

    Args:
        script_text:    The full voiceover script text.
        video_duration: Target video duration in seconds.
        tts_api_url:    TTS service endpoint (e.g. "https://tts.example.com/v1/synthesize").
        tts_api_key:    Bearer token / API key for the TTS service.
        language:       "en" or "zh".
        voice_id:       Voice identifier string (service-specific).
        speed:          Initial playback speed multiplier (1.0 = normal).
        retry_count:    Current retry attempt (managed by Dify loop node).

    Returns:
        dict with keys:
            audio_url          – URL of the synthesised audio file
            audio_duration     – duration of the audio in seconds (float)
            speed_used         – actual speed value used for this synthesis
            retry_count        – echo of the input retry_count
            needs_retry        – "yes" / "no"
            next_speed         – suggested speed for next retry (if needs_retry)
            error              – None on success, error dict on failure
    """
    # ── 1. Estimate target duration from script length ────────────────────────
    estimated_script_duration = _estimate_duration(script_text, language, speed)

    # ── 2. Auto-adjust initial speed if estimate is way off ───────────────────
    if video_duration > 0 and estimated_script_duration > 0:
        ratio = estimated_script_duration / video_duration
        if ratio > 1 + DURATION_TOLERANCE or ratio < 1 - DURATION_TOLERANCE:
            # Clamp to safe range
            adjusted_speed = round(min(SPEED_MAX, max(SPEED_MIN, speed * ratio)), 3)
            speed = adjusted_speed

    # ── 3. Call TTS API ───────────────────────────────────────────────────────
    try:
        audio_url, raw_audio_bytes = _call_tts_api(
            tts_api_url, tts_api_key, script_text, language, voice_id, speed
        )
    except Exception as exc:
        return _error("tts_api", "TTS_API_FAILED", str(exc))

    # ── 4. Measure actual audio duration ─────────────────────────────────────
    audio_duration = _measure_duration(raw_audio_bytes)
    if audio_duration <= 0:
        # Fallback: estimate from byte length (WAV 16kHz mono 16-bit)
        audio_duration = max(0.1, (len(raw_audio_bytes) - 44) / (16000 * 1 * 2))

    # ── 5. Check duration tolerance ───────────────────────────────────────────
    needs_retry = False
    next_speed   = speed

    if video_duration > 0:
        diff_ratio = abs(audio_duration - video_duration) / video_duration
        if diff_ratio > DURATION_TOLERANCE and retry_count < MAX_RETRIES:
            needs_retry = True
            # Compute corrective speed: if audio is too long, speed up
            correction  = audio_duration / video_duration
            next_speed  = round(min(SPEED_MAX, max(SPEED_MIN, speed * correction)), 3)

    return {
        "audio_url":       audio_url,
        "audio_duration":  round(audio_duration, 3),
        "speed_used":      speed,
        "retry_count":     retry_count,
        "needs_retry":     "yes" if needs_retry else "no",
        "next_speed":      next_speed,
        "error":           None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_duration(text: str, language: str, speed: float) -> float:
    """Estimate how long it will take to speak the text at the given speed."""
    if not text:
        return 0.0
    if language.startswith("zh"):
        # Count CJK characters as the unit
        char_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        if char_count == 0:
            char_count = len(text.split())
        base_duration = char_count / CHARS_PER_SECOND_ZH
    else:
        word_count = len(text.split())
        base_duration = word_count / WORDS_PER_SECOND_EN
    return round(base_duration / max(speed, 0.1), 3)


def _call_tts_api(
    api_url: str,
    api_key: str,
    text: str,
    language: str,
    voice_id: str,
    speed: float,
) -> tuple:
    """
    Call the TTS REST API.

    Expected request format (JSON POST):
        {
          "text": "...",
          "language": "en",
          "voice_id": "default",
          "speed": 1.0
        }

    Expected response: raw audio bytes (WAV or MP3) in the response body,
    with the audio URL returned in the 'X-Audio-URL' response header,
    OR a JSON body with an 'audio_url' field.

    Adapt this function to match your actual TTS service contract.
    """
    payload = json.dumps({
        "text":     text,
        "language": language,
        "voice_id": voice_id,
        "speed":    speed,
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        method="POST",
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept":        "audio/wav, audio/mpeg, application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read()

    # Case A: response body is raw audio
    if content_type.startswith("audio/"):
        # Try to get a hosted URL from response header
        audio_url = resp.headers.get("X-Audio-URL", "")
        if not audio_url:
            # No hosted URL — caller will use base64 or re-upload; return empty string
            audio_url = ""
        return audio_url, body

    # Case B: response body is JSON with an audio_url field
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        raise RuntimeError(f"TTS API returned unexpected content-type: {content_type}")

    audio_url = data.get("audio_url") or data.get("url") or ""
    if not audio_url:
        raise RuntimeError("TTS API JSON response missing 'audio_url' field.")

    # Download the audio to measure duration
    audio_req = urllib.request.Request(audio_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(audio_req, timeout=60) as audio_resp:
        raw_bytes = audio_resp.read()

    return audio_url, raw_bytes


def _measure_duration(audio_bytes: bytes) -> float:
    """
    Parse WAV header to get exact duration.
    Falls back to 0.0 if the bytes are not a valid WAV.
    """
    if len(audio_bytes) < 44:
        return 0.0
    try:
        # WAV header layout (little-endian):
        #   offset 22: num_channels (uint16)
        #   offset 24: sample_rate  (uint32)
        #   offset 34: bits_per_sample (uint16)
        #   offset 40: data_chunk_size (uint32)
        num_channels    = struct.unpack_from("<H", audio_bytes, 22)[0]
        sample_rate     = struct.unpack_from("<I", audio_bytes, 24)[0]
        bits_per_sample = struct.unpack_from("<H", audio_bytes, 34)[0]
        data_size       = struct.unpack_from("<I", audio_bytes, 40)[0]

        bytes_per_second = sample_rate * num_channels * (bits_per_sample // 8)
        if bytes_per_second == 0:
            return 0.0
        return round(data_size / bytes_per_second, 3)
    except Exception:
        return 0.0


def _error(stage: str, code: str, message: str) -> dict:
    """Return a standardised error response."""
    return {
        "audio_url":      "",
        "audio_duration": 0.0,
        "speed_used":     1.0,
        "retry_count":    0,
        "needs_retry":    "no",
        "next_speed":     1.0,
        "error": {
            "error_stage":   stage,
            "error_code":    code,
            "error_message": message,
        },
    }
