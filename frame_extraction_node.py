import json
import urllib.request
import urllib.error
import base64
import os
import io

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
MAX_FRAMES           = 10  # 改为默认10帧，符合需求文档要求
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".flv", ".wmv", ".m4v", ".3gp", ".mpeg", ".mpg"}

# External frame-extraction service endpoint.
# This service accepts a video URL and returns extracted frames as base64 JPEGs.
# Override by passing frame_service_url as an input parameter.
DEFAULT_FRAME_SERVICE_URL = "http://localhost:10000"  # 更新默认端口


def main(
    files: list,
    frame_service_url: str = "",
    max_frames: int = MAX_FRAMES,
) -> dict:
    """
    Dify Code Node: Video Frame Extraction (sandbox-safe, HTTP-based)

    Sends the video file to an external frame-extraction HTTP service that runs
    ffmpeg server-side. Returns up to max_frames uniformly sampled frames as
    base64-encoded JPEGs with timestamps.

    Args:
        files:             Dify array[file] — list of Dify file objects.
        frame_service_url: URL of the external frame-extraction service.
                           Defaults to DEFAULT_FRAME_SERVICE_URL.
        max_frames:        Maximum number of frames to extract (default 10).

    Returns:
        dict with keys:
            frames                 – list of frame objects
            video_duration         – total video duration in seconds (float)
            total_frames_extracted – actual number of frames extracted (int)
            error                  – None on success, error dict on failure

    Frame object schema:
        {
            "frame_index":        int,
            "timestamp_seconds":  float,
            "timestamp_formatted": "HH:MM:SS.ss",
            "image_base64":       str,   # base64-encoded JPEG
            "image_mime":         "image/jpeg"
        }
    """
    service_url = (frame_service_url or DEFAULT_FRAME_SERVICE_URL).rstrip("/")

    # ── 1. Validate input ─────────────────────────────────────────────────────
    if not files:
        return _error("input_validation", "NO_FILES",
                      "Input 'files' array is empty.")

    video_obj = _find_video(files)
    if video_obj is None:
        return _error("input_validation", "NO_VIDEO_FILE",
                      "No supported video file found in input array. "
                      f"Supported formats: {sorted(SUPPORTED_EXTENSIONS)}")

    # ── 2. Call external frame-extraction service ─────────────────────────────
    try:
        # 尝试多个端点路径
        endpoints = ["/extract", "/extract_frames", "/api/extract"]
        response = None
        
        for endpoint in endpoints:
            try:
                # 使用文件上传方式
                response = _http_post_file(service_url + endpoint, video_obj, max_frames)
                break  # 成功则退出循环
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    continue  # 端点不存在，尝试下一个
                else:
                    raise  # 其他HTTP错误直接抛出
    
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return _error("service_call", "HTTP_ERROR",
                      f"Frame service returned HTTP {exc.code}: {body}")
    except Exception as exc:
        return _error("service_call", "REQUEST_FAILED", str(exc))

    # ── 3. Validate service response ──────────────────────────────────────────
    if not isinstance(response, dict):
        return _error("service_response", "INVALID_RESPONSE",
                      "Frame service returned a non-JSON or non-object response.")

    # 检查新的响应格式（包含success字段）
    if "success" in response:
        if not response.get("success"):
            svc_error = response.get("error", {})
            stage   = svc_error.get("error_stage", "service")
            code    = svc_error.get("error_code", "SERVICE_ERROR")
            message = svc_error.get("error_message", str(svc_error))
            return _error(stage, code, message)
    else:
        # 兼容旧的响应格式
        svc_error = response.get("error")
        if svc_error:
            stage   = svc_error.get("error_stage", "service")
            code    = svc_error.get("error_code", "SERVICE_ERROR")
            message = svc_error.get("error_message", str(svc_error))
            return _error(stage, code, message)

    frames = response.get("frames", [])
    if not frames:
        return _error("service_response", "NO_FRAMES",
                      "Frame service returned an empty frames array.")

    video_duration = float(response.get("video_duration", 0.0))
    total_extracted = int(response.get("total_frames_extracted", len(frames)))

    return {
        "frames":                frames,
        "video_duration":        round(video_duration, 3),
        "total_frames_extracted": total_extracted,
        "error":                 None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _find_video(files: list):
    """Return the first file object whose extension or MIME type is a video."""
    for f in files:
        filename = _get_field(f, "filename", "")
        mime     = _get_field(f, "mime_type", "")
        ext      = _splitext(filename)
        if ext in SUPPORTED_EXTENSIONS or mime.startswith("video/"):
            return f
    return None


def _get_url(file_obj) -> str:
    """
    Prefer out_url (COS direct link) over url (internal preview link).
    Handles both dict and object-style Dify file representations.
    """
    out_url = _get_field(file_obj, "out_url", "")
    if out_url and out_url.startswith("http"):
        return out_url
    url = _get_field(file_obj, "url", "")
    if url and url.startswith("http"):
        return url
    return ""


def _get_field(obj, key: str, default=""):
    """Safely get a field from either a dict or an object."""
    try:
        val = obj[key]
        return val if val is not None else default
    except (KeyError, TypeError):
        pass
    try:
        val = getattr(obj, key, default)
        return val if val is not None else default
    except Exception:
        return default


def _splitext(filename: str) -> str:
    """Return lowercase file extension including the dot, e.g. '.mp4'."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _http_post_file(url: str, video_obj, max_frames: int, timeout: int = 120) -> dict:
    """
    POST a video file using multipart/form-data to url and return the parsed JSON response.
    Raises urllib.error.HTTPError on non-2xx status.
    """
    # 获取文件URL和下载文件内容
    video_url = _get_url(video_obj)
    if not video_url:
        raise ValueError("Video file has no accessible URL")
    
    # 下载文件内容
    req = urllib.request.Request(video_url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        file_content = resp.read()
    
    # 准备multipart/form-data
    boundary = "----WebKitFormBoundary" + base64.b64encode(os.urandom(16)).decode('ascii')
    
    filename = _get_field(video_obj, "filename", "video.mp4")
    mime_type = _get_field(video_obj, "mime_type", "video/mp4")
    
    # 构建multipart数据
    data_parts = []
    
    # 文件部分
    data_parts.append(f"--{boundary}")
    data_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"')
    data_parts.append(f"Content-Type: {mime_type}")
    data_parts.append("")
    data_parts.append(file_content.decode('latin-1'))
    
    # 参数部分
    data_parts.append(f"--{boundary}")
    data_parts.append('Content-Disposition: form-data; name="max_frames"')
    data_parts.append("")
    data_parts.append(str(max_frames))
    
    data_parts.append(f"--{boundary}--")
    data_parts.append("")
    
    # 合并数据
    data = "\r\n".join(data_parts).encode('latin-1')
    
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _error(stage: str, code: str, message: str) -> dict:
    """Return a standardised error response."""
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
