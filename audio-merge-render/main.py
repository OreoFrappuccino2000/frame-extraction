import os
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import List

import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


app = FastAPI(title="Audio Merge Service")

BASE_DIR = Path("/tmp/audio_merge_service")
INPUT_DIR = BASE_DIR / "inputs"
OUTPUT_DIR = BASE_DIR / "outputs"

INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")


class MergeRequest(BaseModel):
    audio_urls: List[str]
    output_filename: str = "merged_audio.mp3"


def run_cmd(cmd: list):
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result


def download_file(url: str, output_path: Path):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    with requests.get(url, stream=True, timeout=60, headers=headers) as r:
        r.raise_for_status()
        with open(output_path, "wb") as f:
            shutil.copyfileobj(r.raw, f)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "audio-merge"}


@app.post("/merge-audio")
def merge_audio(payload: MergeRequest):
    if not payload.audio_urls:
        raise HTTPException(status_code=400, detail="audio_urls is empty")

    job_id = uuid.uuid4().hex
    job_input_dir = INPUT_DIR / job_id
    job_input_dir.mkdir(parents=True, exist_ok=True)

    converted_files = []

    try:
        for index, url in enumerate(payload.audio_urls):
            raw_path = job_input_dir / f"input_{index}.bin"
            wav_path = job_input_dir / f"converted_{index}.wav"

            download_file(url, raw_path)

            # Normalize every input to the same WAV format to avoid concat
            # errors between mp3/wav/bin files with different encodings.
            run_cmd([
                "ffmpeg",
                "-y",
                "-i", str(raw_path),
                "-ar", "44100",
                "-ac", "2",
                "-c:a", "pcm_s16le",
                str(wav_path)
            ])

            converted_files.append(wav_path)

        concat_list_path = job_input_dir / "concat_list.txt"

        with open(concat_list_path, "w", encoding="utf-8") as f:
            for wav_file in converted_files:
                f.write(f"file '{wav_file.as_posix()}'\n")

        safe_output_name = payload.output_filename.strip() or "merged_audio.mp3"

        if not safe_output_name.endswith(".mp3"):
            safe_output_name += ".mp3"

        final_filename = f"{job_id}_{safe_output_name}"
        final_output_path = OUTPUT_DIR / final_filename

        run_cmd([
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(final_output_path)
        ])

        final_audio_url = f"/files/{final_filename}"

        return {
            "final_audio_url": final_audio_url,
            "filename": final_filename,
            "input_count": len(payload.audio_urls)
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to download audio: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")

    finally:
        shutil.rmtree(job_input_dir, ignore_errors=True)
