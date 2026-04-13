"""
test_frame_service.py
─────────────────────
Quick test to verify the frame extraction service is running.

Usage:
    python test_frame_service.py
    python test_frame_service.py --url http://10.x.x.x:5000
    python test_frame_service.py --url http://10.x.x.x:5000 --video <video_url>
"""

import sys
import json
import argparse
import urllib.request
import urllib.error

def test_health(base_url: str) -> bool:
    print(f"\n[1] Health check → {base_url}/health")
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=5) as r:
            data = json.loads(r.read())
            if data.get("status") == "ok":
                print("    ✅ Service is UP")
                return True
            else:
                print(f"    ⚠️  Unexpected response: {data}")
                return False
    except Exception as e:
        print(f"    ❌ FAILED: {e}")
        print(f"\n    Make sure the service is running:")
        print(f"      python frame_extraction_service.py")
        print(f"    Or on Windows: double-click start_service.bat")
        return False


def test_extract(base_url: str, video_url: str, max_frames: int = 5):
    print(f"\n[2] Extract frames → {base_url}/extract")
    print(f"    Video URL: {video_url[:80]}...")
    print(f"    Max frames: {max_frames}")

    payload = json.dumps({
        "video_url":  video_url,
        "max_frames": max_frames,
        "filename":   "test_video.mp4",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/extract",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"    ❌ HTTP {e.code}: {body[:300]}")
        return
    except Exception as e:
        print(f"    ❌ FAILED: {e}")
        return

    if data.get("error"):
        err = data["error"]
        print(f"    ❌ Service error [{err.get('error_code')}]: {err.get('error_message')}")
        return

    frames = data.get("frames", [])
    duration = data.get("video_duration", 0)
    print(f"    ✅ Success!")
    print(f"    Video duration : {duration:.2f}s")
    print(f"    Frames extracted: {len(frames)}")
    print(f"\n    Frame timestamps:")
    for f in frames:
        b64_len = len(f.get("image_base64", ""))
        print(f"      [{f['frame_index']:02d}] {f['timestamp_formatted']}  "
              f"({f['timestamp_seconds']:.3f}s)  "
              f"image size: {b64_len // 1024}KB (base64)")


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test frame extraction service")
    parser.add_argument("--url", default="http://127.0.0.1:5000",
                        help="Service base URL (default: http://127.0.0.1:5000)")
    parser.add_argument("--video", default="",
                        help="Video URL to test frame extraction (optional)")
    parser.add_argument("--frames", type=int, default=5,
                        help="Max frames to extract in test (default: 5)")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    print("=" * 55)
    print(" Frame Extraction Service - Test")
    print("=" * 55)

    ok = test_health(base_url)

    if ok and args.video:
        test_extract(base_url, args.video, args.frames)
    elif ok and not args.video:
        print("\n[2] Skipping extract test (no --video provided)")
        print("    To test extraction, run:")
        print(f"      python test_frame_service.py --url {base_url} --video <video_url>")

    # Print Dify config hint
    local_ip = get_local_ip()
    print("\n" + "=" * 55)
    print(" Dify Configuration")
    print("=" * 55)
    print(f"\n  In your Dify Code Node (frame_extraction_node.py),")
    print(f"  set the input variable 'frame_service_url' to:\n")
    print(f"    http://{local_ip}:5000")
    print(f"\n  Or update DEFAULT_FRAME_SERVICE_URL in frame_extraction_node.py:")
    print(f"    DEFAULT_FRAME_SERVICE_URL = \"http://{local_ip}:5000/extract_frames\"")
    print()
