import os
import uuid
import json
import time
import subprocess
import threading
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import whisperx

app = FastAPI()

BASE_DIR = os.environ.get("BASE_DIR", "/tmp/media")
FRAMES_DIR = os.path.join(BASE_DIR, "frames")
MERGED_DIR = os.path.join(BASE_DIR, "merged")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(MERGED_DIR, exist_ok=True)
app.mount("/frames", StaticFiles(directory=FRAMES_DIR), name="frames")
app.mount("/merged", StaticFiles(directory=MERGED_DIR), name="merged")

MAX_FRAMES             = int(os.environ.get("MAX_FRAMES", "20"))
FONTS_DIR              = os.environ.get("FONTS_DIR", "/opt/app/fonts")
JOB_TTL_SECONDS        = int(os.environ.get("JOB_TTL_SECONDS", "7200"))
DEBUG                  = os.environ.get("DEBUG", "0").strip().lower() in ("1", "true", "yes", "y")
FFMPEG_BIN             = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN            = os.environ.get("FFPROBE_BIN", "ffprobe")
FC_MATCH_BIN           = os.environ.get("FC_MATCH_BIN", "fc-match")
SUB_EFFECT             = os.environ.get("SUB_EFFECT", "pop").strip().lower()

DEFAULT_PERSONA_ID    = os.environ.get("DEFAULT_PERSONA_ID", "persona_a").strip().lower()
FONT_NAME_EN          = os.environ.get("FONT_NAME_EN", "Komika Axis")
FONT_NAME_ZH          = os.environ.get("FONT_NAME_ZH", "DouyinSans")
FONT_NAME_EN_FALLBACK = os.environ.get("FONT_NAME_EN_FALLBACK", "Arial")
FONT_NAME_ZH_FALLBACK = os.environ.get("FONT_NAME_ZH_FALLBACK", "Noto Sans CJK SC")
ALIGN_LANG_EN         = os.environ.get("ALIGN_LANG_EN", "en")
ALIGN_LANG_ZH         = os.environ.get("ALIGN_LANG_ZH", "zh")
ENABLE_ALIGN_EN       = os.environ.get("ENABLE_ALIGN_EN", "1").strip().lower() in ("1", "true", "yes", "y")
ENABLE_ALIGN_ZH       = os.environ.get("ENABLE_ALIGN_ZH", "1").strip().lower() in ("1", "true", "yes", "y")

PERSONA_SUBTITLE_CONFIG = {
    "persona_a": {"lang": "en", "font_name": FONT_NAME_EN},
    "persona_b": {"lang": "en", "font_name": FONT_NAME_EN},
    "persona_c": {"lang": "zh", "font_name": FONT_NAME_ZH},
    "persona_d": {"lang": "zh", "font_name": FONT_NAME_ZH},
}

MAX_WORDS_PER_LINE        = int(os.environ.get("MAX_WORDS_PER_LINE", "6"))
FADE_MS                   = int(os.environ.get("FADE_MS", "40"))
FINAL_SUB_COVERAGE_BUFFER = float(os.environ.get("FINAL_SUB_COVERAGE_BUFFER", "0.15"))
CHUNK_TAIL_PAD            = float(os.environ.get("CHUNK_TAIL_PAD", "0.15"))
WORD_TS_SLACK             = float(os.environ.get("WORD_TS_SLACK", "0.5"))
SUB_LEAD_OUT              = float(os.environ.get("SUB_LEAD_OUT", "0.12"))
POP_SCALE                 = int(os.environ.get("POP_SCALE", "115"))
POP_WORD_PAD_OUT          = float(os.environ.get("POP_WORD_PAD_OUT", "0.05"))
POP_MIN_ACTIVE_DUR        = float(os.environ.get("POP_MIN_ACTIVE_DUR", "0.12"))
MIN_LINE_DUR              = float(os.environ.get("MIN_LINE_DUR", "0.70"))
MIN_LINE_DUR_ZH           = float(os.environ.get("MIN_LINE_DUR_ZH", "0.58"))
SUB_LEAD_IN_EN            = float(os.environ.get("SUB_LEAD_IN_EN", "0.12"))
SUB_LEAD_IN_ZH            = float(os.environ.get("SUB_LEAD_IN_ZH", "0.40"))
SUB_LEAD_OUT_EN           = float(os.environ.get("SUB_LEAD_OUT_EN", "0.03"))
SUB_LEAD_OUT_ZH           = float(os.environ.get("SUB_LEAD_OUT_ZH", "0.05"))
SUB_HOLD_MAX_EN           = float(os.environ.get("SUB_HOLD_MAX_EN", "0.60"))
SUB_HOLD_MAX_ZH           = float(os.environ.get("SUB_HOLD_MAX_ZH", "0.45"))
SUB_WPS_EN                = float(os.environ.get("SUB_WPS_EN", "2.1"))
SUB_CPS_ZH                = float(os.environ.get("SUB_CPS_ZH", "5.3"))
ZH_CHARS_PER_LINE         = int(os.environ.get("ZH_CHARS_PER_LINE", "9"))
ZH_SOFT_MAX               = int(os.environ.get("ZH_SOFT_MAX", str(ZH_CHARS_PER_LINE)))
ZH_PARTICLE_SPLIT_MIN     = int(os.environ.get("ZH_PARTICLE_SPLIT_MIN", "7"))
ZH_PARTICLE_SPLIT_MAX     = int(os.environ.get("ZH_PARTICLE_SPLIT_MAX", "18"))
ZH_MERGE_TINY_MAX         = int(os.environ.get("ZH_MERGE_TINY_MAX", "2"))
ZH_PHRASE_SPLIT_MIN       = int(os.environ.get("ZH_PHRASE_SPLIT_MIN", "4"))
ZH_PHRASE_SPLIT_MAX       = int(os.environ.get("ZH_PHRASE_SPLIT_MAX", "10"))
ZH_PUNCT        = set("，。！？；：、,.!?;:…")
ZH_SOFT_TOKENS  = {"吧", "啊", "呢", "了", "嘛", "呀", "哈", "哇"}
ZH_PHRASE_BREAKS = ["家人们","兄弟们","宝子们","来看看","看看","这波","真的","我天","哎哟","怎么办"]

# ─────────────────────────────────────────────────────────────────────────────
# Audio placement / stretch config
# ─────────────────────────────────────────────────────────────────────────────
# atempo ratio range.  1.0 = natural speed.
# Speed UP  (ratio > 1): clip is too long for its slot → compress time.
# Slow DOWN (ratio < 1): clip is shorter than slot → we don't actually slow
#   down deliberately; ATEMPO_MIN is a safety floor in case of rounding.
ATEMPO_MIN = float(os.environ.get("ATEMPO_MIN", "0.85"))
ATEMPO_MAX = float(os.environ.get("ATEMPO_MAX", "1.55"))


# --- Language / font helpers ---

def is_zh_lang(lang: Optional[str]) -> bool:
    return (lang or "").strip().lower() in ("zh", "zh-cn", "zh_hans", "zh-hans", "cn", "chs")

def normalize_persona_id(persona_id: Optional[str]) -> str:
    s = (persona_id or "").strip().lower()
    aliases = {
        "a": "persona_a", "persona a": "persona_a", "persona-a": "persona_a", "persona_a": "persona_a", "personaa": "persona_a",
        "b": "persona_b", "persona b": "persona_b", "persona-b": "persona_b", "persona_b": "persona_b", "personab": "persona_b",
        "c": "persona_c", "persona c": "persona_c", "persona-c": "persona_c", "persona_c": "persona_c", "personac": "persona_c",
        "d": "persona_d", "persona d": "persona_d", "persona-d": "persona_d", "persona_d": "persona_d", "personad": "persona_d",
    }
    return aliases.get(s, s)

def fc_match_family(pattern: Optional[str]) -> str:
    if not pattern: return ""
    try:
        out = subprocess.check_output([FC_MATCH_BIN, "-f", "%{family[0]}\n", pattern], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", "ignore").strip()
    except Exception: return ""

def resolve_font_name(requested_font: Optional[str], lang: Optional[str]) -> str:
    requested = (requested_font or "").strip()
    zh_mode = is_zh_lang(lang)
    def norm(s): return (s or "").replace(" ", "").replace("-", "").replace("_", "").lower()
    if requested:
        matched = fc_match_family(requested)
        if matched and (norm(requested) in norm(matched) or norm(matched) in norm(requested)): return matched
        if matched and not zh_mode: return matched
    fallback = FONT_NAME_ZH_FALLBACK if zh_mode else FONT_NAME_EN_FALLBACK
    return fc_match_family(fallback) or fallback or requested or ("Noto Sans CJK SC" if zh_mode else "Arial")

def get_subtitle_profile(persona_id: Optional[str] = None, lang: Optional[str] = None) -> Dict[str, str]:
    pid = normalize_persona_id(persona_id) or DEFAULT_PERSONA_ID
    profile = PERSONA_SUBTITLE_CONFIG.get(pid, PERSONA_SUBTITLE_CONFIG["persona_a"]).copy()
    if lang:
        profile["lang"] = "zh" if is_zh_lang(lang) else "en"
        profile["font_name"] = FONT_NAME_ZH if profile["lang"] == "zh" else FONT_NAME_EN
    profile["font_name"] = resolve_font_name(profile["font_name"], profile["lang"])
    return profile

def parse_texts_payload(texts_json: Any, persona_id: Optional[str] = None, lang: Optional[str] = None) -> List[str]:
    if texts_json is None: raise HTTPException(400, "Empty texts_json")
    if isinstance(texts_json, str):
        s = texts_json.strip()
        if not s: raise HTTPException(400, "Empty texts_json")
        try: raw = json.loads(s)
        except Exception: raise HTTPException(400, "texts_json not valid JSON")
    else: raw = texts_json
    if not isinstance(raw, list): raise HTTPException(400, "texts_json must be a JSON array")
    profile = get_subtitle_profile(persona_id, lang)
    want_zh = is_zh_lang(profile["lang"])
    out: List[str] = []
    for item in raw:
        text = None
        if isinstance(item, str): text = item.strip()
        elif isinstance(item, dict):
            keys = ["text_zh","subtitle_zh","zh","text","subtitle"] if want_zh else ["text_en","subtitle_en","en","text","subtitle"]
            for k in keys:
                v = item.get(k)
                if isinstance(v, str) and v.strip(): text = v.strip(); break
        if text: out.append(text)
    if not out: raise HTTPException(400, "Empty texts_json")
    return out


# --- WhisperX align cache ---

_WHISPERX_LOCK = threading.Lock()
_WHISPERX: Dict[str, Any] = {"align_model": None, "metadata": None, "lang": None}

# Cache for the WhisperX transcription (ASR) model used by /validate-tts.
# Keyed by (model_size, lang) so we don't reload when the same language is
# reused across segments.  Guarded by the same _WHISPERX_LOCK.
_ASR_MODEL_CACHE: Dict[str, Any] = {}   # key: "<size>_<lang>" → model object

def ensure_align_model(lang: str = "en"):
    with _WHISPERX_LOCK:
        if _WHISPERX["align_model"] is None or _WHISPERX["lang"] != lang:
            model, meta = whisperx.load_align_model(language_code=lang, device="cpu")
            _WHISPERX.update({"align_model": model, "metadata": meta, "lang": lang})

def ensure_asr_model(model_size: str = "base", lang: str = "en") -> Any:
    """Return a cached WhisperX ASR model, loading it once on first call."""
    cache_key = f"{model_size}_{lang}"
    with _WHISPERX_LOCK:
        if cache_key not in _ASR_MODEL_CACHE:
            _ASR_MODEL_CACHE[cache_key] = whisperx.load_model(
                model_size, "cpu", compute_type="int8", language=lang
            )
        return _ASR_MODEL_CACHE[cache_key]


# --- Job store ---

class JobStatus(str, Enum):
    pending = "pending"; running = "running"; done = "done"; error = "error"

SUBTITLE_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
SUBTITLE_SEM = threading.Semaphore(int(os.environ.get("SUBTITLE_CONCURRENCY", "1")))

def _background_cleanup_loop(interval: float = 300.0):
    while True:
        time.sleep(interval)
        try: cleanup_old_jobs()
        except Exception: pass

threading.Thread(target=_background_cleanup_loop, daemon=True).start()


# --- General utilities ---

def safe_remove(path: str):
    try:
        if path and os.path.exists(path): os.remove(path)
    except Exception: pass

def cleanup_old_jobs():
    now = time.time()
    with _LOCK:
        expired = [jid for jid, j in SUBTITLE_JOBS.items() if now - j.get("created_at", now) > JOB_TTL_SECONDS]
        for jid in expired:
            for sfx in [".mp4", "_sub.mp4", ".ass"]: safe_remove(os.path.join(MERGED_DIR, f"{jid}{sfx}"))
            SUBTITLE_JOBS.pop(jid, None)

def download_file(url: str, dst: str, retries: int = 4, backoff: float = 0.6):
    if not isinstance(url, str) or not url.startswith("http"): raise HTTPException(400, "Invalid URL")
    last_err: Optional[Exception] = None
    for i in range(retries + 1):
        try:
            with requests.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(dst, "wb") as f:
                    for c in r.iter_content(1024 * 1024):
                        if c: f.write(c)
            return
        except Exception as e:
            last_err = e
            if i >= retries: break
            time.sleep(backoff * (2 ** i))
    raise RuntimeError(f"download failed: {url} -> {last_err}")

def run(cmd: List[str]):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if DEBUG: print("[DEBUG] CMD:", " ".join(cmd)); print("[DEBUG] STDERR:\n", p.stderr.decode("utf-8","ignore")[:12000])
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr.decode('utf-8','ignore')[:12000]}")

def probe_duration(path: str) -> float:
    out = subprocess.check_output([FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path])
    return float(out.decode().strip())

def probe_video_duration(path: str) -> float:
    try:
        out = subprocess.check_output([FFPROBE_BIN, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "default=nk=1:nw=1", path])
        val = out.decode().strip()
        if val and val.upper() != "N/A": return float(val)
    except Exception: pass
    return probe_duration(path)

def probe_wh_rotate(path: str):
    out = subprocess.check_output([FFPROBE_BIN, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_tags=rotate", "-of", "json", path])
    j = json.loads(out.decode("utf-8", "ignore"))
    s = (j.get("streams") or [{}])[0]
    w, h = int(s.get("width") or 1080), int(s.get("height") or 1920)
    try: rot = int((s.get("tags") or {}).get("rotate") or 0)
    except Exception: rot = 0
    if rot in (90, 270) and w > h: w, h = h, w
    return w, h, rot

def ensure_wav_16k_mono(src: str, dst: str):
    run([FFMPEG_BIN, "-y", "-i", src, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-vn", dst])

def ffmpeg_filter_escape_path(p: str) -> str:
    return p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(" ", "\\ ")

def ffmpeg_force_style_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(":", "\\:").replace(",", "\\,").replace("'", "\\'")

def concat_quote_path(p: str) -> str:
    return p.replace("\\", "/").replace("'", r"'\''")

def ass_font_tag(font_name: str) -> str:
    return rf"\fn{(font_name or 'Arial').replace(',', ' ')}"

def build_subtitles_filter(ass_path: str, font_name: Optional[str] = None) -> str:
    vf = f"subtitles='{ffmpeg_filter_escape_path(ass_path)}'"
    if FONTS_DIR: vf += f":fontsdir='{ffmpeg_filter_escape_path(FONTS_DIR)}'"
    if font_name: vf += f":force_style='FontName={ffmpeg_force_style_escape(font_name)}'"
    return vf


# --- Segment ID helpers ---

def _get_seg_id(obj: Dict[str, Any]) -> Optional[str]:
    if not isinstance(obj, dict): return None
    sid = obj.get("segment_id") or obj.get("segmentId")
    return sid if isinstance(sid, str) and sid.strip() else None

def _get_audio_url(obj: Dict[str, Any]) -> Optional[str]:
    if not isinstance(obj, dict): return None
    url = obj.get("audio_url") or obj.get("audioUrl")
    return url if isinstance(url, str) and url.strip() else None

def _parse_seg_num(sid: str) -> Optional[int]:
    if not isinstance(sid, str) or not sid.startswith("seg_"): return None
    try: return int(sid.split("_", 1)[1])
    except Exception: return None

def _detect_off_by_one(placement_ids: List[str], audio_ids: List[str]) -> Optional[Dict[str, Any]]:
    p_nums = [_parse_seg_num(x) for x in placement_ids]
    a_nums = [_parse_seg_num(x) for x in audio_ids]
    if any(v is None for v in p_nums) or any(v is None for v in a_nums): return None
    if len(p_nums) != len(a_nums) or not p_nums: return None
    p_s, a_s = sorted(p_nums), sorted(a_nums)
    diffs = [p - a for p, a in zip(p_s, a_s)]
    if all(d == 1 for d in diffs):
        return {"error": "segment_id_off_by_one", "hint": "placement is 1-based, audios are 0-based.", "placement_range": [min(p_s), max(p_s)], "audio_range": [min(a_s), max(a_s)]}
    if all(d == -1 for d in diffs):
        return {"error": "segment_id_off_by_one", "hint": "placement is 0-based, audios are 1-based.", "placement_range": [min(p_s), max(p_s)], "audio_range": [min(a_s), max(a_s)]}
    return None


# --- Subtitle helpers ---

def ass_time(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h}:{m:02}:{s:05.2f}"

def esc(text: str) -> str:
    return (text or "").replace("\n", " ").replace("\r", " ").replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")

def subtitle_pos_tag(play_w: int, play_h: int, margin_v: int) -> str:
    return rf"\an2\q2\pos({play_w // 2},{play_h - margin_v})"

def _dialogue_line(layer: int, start: float, end: float, style: str, text: str, tags: str = "") -> str:
    return f"Dialogue: {layer},{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{tags}{text}"

def get_chunk_unit_limit(lang: str) -> int:
    return ZH_CHARS_PER_LINE if is_zh_lang(lang) else MAX_WORDS_PER_LINE

def has_word_level_timings(segments: List[Dict[str, Any]]) -> bool:
    return any(isinstance(seg, dict) and isinstance(seg.get("words"), list) and seg.get("words") for seg in segments)

# ZH-only punctuation that should never stand alone as a pop token.
# ASCII punctuation (,.!?) is intentionally excluded — for English, WhisperX
# sometimes returns trailing punctuation as a separate token with a later
# timestamp (e.g. the pause after "."), and merging it would extend the
# word's end time into post-speech silence, causing EN last lines to hang.
_ZH_PUNCT_TOKENS = set("，。！？；：、…～~")

def _clean_word_ts(words: List[Dict[str, Any]], render_limit: float, lang: str = "en") -> List[Tuple[str, float, float]]:
    cleaned = []
    zh_mode = is_zh_lang(lang)
    for w in words:
        if not isinstance(w, dict): continue
        txt = (w.get("word") or w.get("text") or "").strip()
        if not txt: continue
        try: ws, we = float(w.get("start")), float(w.get("end"))
        except Exception: continue
        if ws < 0.0 or we <= ws or ws > render_limit + WORD_TS_SLACK: continue

        # ZH only: merge standalone punctuation tokens into the preceding token
        # so punctuation pops together with the character before it.
        # Skipped for EN — ASCII punctuation tokens in EN carry a post-speech
        # pause timestamp that would incorrectly extend the subtitle display.
        if zh_mode:
            is_punct_only = bool(txt) and all(ch in _ZH_PUNCT_TOKENS for ch in txt if not ch.isspace())
            if is_punct_only and cleaned:
                prev_txt, prev_ws, prev_we = cleaned[-1]
                cleaned[-1] = (prev_txt + txt, prev_ws, max(prev_we, max(we, ws + 0.01)))
                continue

        cleaned.append((txt, ws, max(we, ws + 0.01)))
    return cleaned

def _line_text_from_cleaned(cleaned: List[Tuple[str, float, float]], lang: str) -> str:
    parts = [t for t, _, _ in cleaned]
    return "".join(parts) if is_zh_lang(lang) else " ".join(parts)

def _pop_full_line_text(cleaned: List[Tuple[str, float, float]], active_idx: int, lang: str) -> str:
    active_font = resolve_font_name(FONT_NAME_ZH if is_zh_lang(lang) else FONT_NAME_EN, lang)
    parts = []
    for i, (txt, _, _) in enumerate(cleaned):
        token = esc(txt)
        if i == active_idx:
            parts.append(r"{" + ass_font_tag(active_font) + r"\1c&H00FF00&\3c&H000000&\4c&H64000000&\bord3.5\shad1.5" + rf"\fscx{POP_SCALE}\fscy{POP_SCALE}" + r"}" + token + r"{\r}")
        else: parts.append(token)
    return "".join(parts) if is_zh_lang(lang) else " ".join(parts)

def _split_words_into_chunks(cleaned: List[Tuple[str, float, float]], max_words: int) -> List[List[Tuple[str, float, float]]]:
    if not cleaned: return []
    chunks = [cleaned[i:i + max_words] for i in range(0, len(cleaned), max_words)]
    # Rescue tiny last chunks (1 or 2 tokens) by pulling from previous chunk.
    # A 2-char ZH chunk displays too briefly and looks cut off — merge it back
    # so the last line always has at least 3 characters for readability.
    if len(chunks) >= 2 and len(chunks[-1]) <= 2 and len(chunks[-2]) >= 3:
        while len(chunks[-1]) <= 2 and len(chunks[-2]) >= 3:
            chunks[-1].insert(0, chunks[-2].pop())
    return chunks

def _normalize_timestamps(
    cleaned: List[Tuple[str, float, float]],
    chunk_start: float,
    chunk_end: float,
    lang: str,
) -> List[Tuple[str, float, float]]:
    """
    Ensure word timestamps are spread across the full chunk window.

    Problem: WhisperX for ZH frequently bunches all timestamps into the first
    30-60% of the clip (the "rushed" symptom — all pops fire early, subtitle
    sits static for the rest). For EN this is rare but can also happen.

    Strategy:
      1. Clamp every timestamp to [chunk_start, chunk_end].
      2. If the spread (last_end - first_start) covers < SPREAD_THRESHOLD of
         chunk_dur, redistribute evenly so each token gets equal screen time.
      3. Always ensure last token ends at chunk_end so the final character
         is highlighted until the clip actually goes silent.
    """
    if not cleaned:
        return cleaned
    chunk_dur = chunk_end - chunk_start
    if chunk_dur <= 0.01:
        return cleaned

    n = len(cleaned)

    # Step 1: clamp all timestamps into [chunk_start, chunk_end]
    clamped = []
    for txt, ws, we in cleaned:
        ws = max(chunk_start, min(ws, chunk_end))
        we = max(ws + 0.01, min(we, chunk_end))
        clamped.append((txt, ws, we))

    # Step 2: redistribute if timestamps are bunched or all collapsed.
    # Bunched = spread covers < 55% of chunk duration.
    # Collapsed = all tokens clamped to the same point (spread ~0).
    spread = clamped[-1][2] - clamped[0][1]
    SPREAD_THRESHOLD = 0.55
    needs_redistribute = spread < chunk_dur * SPREAD_THRESHOLD
    if needs_redistribute:
        slot = chunk_dur / n
        clamped = [
            (txt, chunk_start + i * slot, chunk_start + (i + 1) * slot)
            for i, (txt, _, _) in enumerate(clamped)
        ]

    # Step 3: force last token to end exactly at chunk_end — hard rule.
    txt, ws, _ = clamped[-1]
    clamped[-1] = (txt, min(ws, chunk_end - 0.01), chunk_end)

    return clamped


def _build_non_overlapping_pop_events(
    cleaned: List[Tuple[str, float, float]],
    chunk_start: float,
    chunk_end: float,
    lang: str,
) -> List[Tuple[float, float, str]]:
    """
    Build one pop-highlight event per token.
    Guarantees:
      - Every token gets highlighted for at least POP_MIN_ACTIVE_DUR.
      - Last token always highlighted until chunk_end (clip goes silent).
      - No event exceeds chunk_end.
      - No overlap between consecutive events.
    """
    cleaned = _normalize_timestamps(cleaned, chunk_start, chunk_end, lang)
    if not cleaned:
        return []

    events = []
    n = len(cleaned)
    for i, (_, ws, we) in enumerate(cleaned):
        is_last = (i == n - 1)
        ev_start = max(chunk_start, ws)
        if is_last:
            ev_end = chunk_end
            if ev_start >= ev_end:
                ev_start = max(chunk_start, ev_end - POP_MIN_ACTIVE_DUR)
        else:
            next_ws = cleaned[i + 1][1]
            ev_end = min(chunk_end, max(we + POP_WORD_PAD_OUT, ws + POP_MIN_ACTIVE_DUR))
            ev_end = min(ev_end, next_ws)  # never bleed into next token
        if ev_end <= ev_start:
            ev_end = min(ev_start + POP_MIN_ACTIVE_DUR, chunk_end)
        if ev_end <= ev_start:
            continue
        events.append((ev_start, ev_end, _pop_full_line_text(cleaned, i, lang)))
    return events

def build_display_chunks_from_segments(
    segments: List[Dict[str, Any]],
    render_limit: float,
    lang: str = "en",
    max_words: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Split WhisperX-aligned segments into display chunks (lines of text).

    seg["end"] is set by run_subtitle_job to actual_clip_end — the precise
    moment the WAV file goes silent. This is the hard ceiling for all chunks.

    For ZH: last chunk always extends to seg["end"] (actual_clip_end) because
    WhisperX timestamps end early for Chinese. _normalize_timestamps handles
    the internal pop distribution.
    For EN: last chunk uses natural word end + pad, clamped to seg["end"].
    """
    out = []
    per_line = max_words if max_words is not None else get_chunk_unit_limit(lang)
    zh = is_zh_lang(lang)

    for seg in segments:
        words = seg.get("words") if isinstance(seg.get("words"), list) else None
        if not words:
            continue
        cleaned = _clean_word_ts(words, render_limit=render_limit, lang=lang)
        if not cleaned:
            continue

        # Authoritative end = actual_clip_end set by run_subtitle_job.
        actual_end = seg.get("end")
        actual_end_f = float(actual_end) if actual_end else None

        # Soft ceiling for inter-chunk boundaries: last word end + small pad,
        # never beyond actual_end_f.
        soft_ceil = cleaned[-1][2] + SUB_LEAD_OUT
        if actual_end_f is not None:
            soft_ceil = min(soft_ceil, actual_end_f)

        if DEBUG:
            print(f"[CHUNKS] seg={seg.get('start'):.2f} last_word={cleaned[-1][2]:.3f} "
                  f"soft_ceil={soft_ceil:.3f} actual_end={actual_end_f}")

        chunks = _split_words_into_chunks(cleaned, max_words=per_line)
        n_chunks = len(chunks)

        # seg_start_f: the actual start of this segment in the video timeline
        seg_start_f = float(seg.get("start") or 0)

        for idx, chunk in enumerate(chunks):
            if not chunk:
                continue
            is_last = (idx == n_chunks - 1)
            # chunk_start: use first word's WhisperX timestamp but floor it
            # at the segment's actual start so it never precedes placement.
            # chunk_start: floor at seg_start, cap at actual_end_f - 0.01
            # so it is always strictly before chunk_end even when WhisperX
            # returns timestamps far beyond the clip window.
            chunk_start = max(chunk[0][1], seg_start_f)
            if actual_end_f is not None:
                chunk_start = min(chunk_start, actual_end_f - 0.01)

            next_cs = max(chunks[idx + 1][0][1], seg_start_f) if not is_last else soft_ceil
            natural_end = chunk[-1][2] + CHUNK_TAIL_PAD

            if is_last and actual_end_f is not None:
                if zh:
                    # ZH: extend to actual_clip_end — WhisperX timestamps end
                    # too early for Chinese so we hold until the clip is silent.
                    chunk_end = actual_end_f
                else:
                    # EN: use last word end + pad, capped to clip end.
                    # Never extends into TTS trailing silence.
                    chunk_end = min(max(chunk[-1][2], natural_end), actual_end_f)
            else:
                chunk_end = min(max(chunk[-1][2], natural_end), next_cs, soft_ceil)

            if chunk_end <= chunk_start:
                # Fallback: place a minimum-duration chunk ending at actual_end_f
                chunk_end = min(chunk_start + 0.10,
                                actual_end_f if actual_end_f else chunk_start + 0.10)

            chunk_text = _line_text_from_cleaned(chunk, lang)

            # Drop non-last chunks whose text is pure punctuation — they add
            # no value. NEVER drop the last chunk regardless of content: it
            # carries the final word/character and must always be rendered
            # with visual effects and then disappear.
            if not is_last and not _is_displayable(chunk_text):
                continue

            out.append({
                "words": chunk,
                "start": chunk_start,
                "end":   chunk_end,
                "text":  chunk_text,
            })

    out.sort(key=lambda x: x["start"])
    return out

def compute_subtitle_render_limit(segments: List[Dict[str, Any]], audio_duration: float) -> float:
    # Use segment end times (already capped to last word + SUB_END_PAD) rather
    # than audio_duration, so render_limit reflects when speech actually stops
    # rather than the full silence-padded track length.
    ends = [float(seg.get("end", 0.0)) for seg in segments if seg.get("end")]
    return (max(ends) if ends else audio_duration) + WORD_TS_SLACK

def compute_last_caption_end(segments: List[Dict[str, Any]], render_limit: float, lang: str = "en") -> Optional[float]:
    chunks = build_display_chunks_from_segments(segments, render_limit=render_limit, lang=lang, max_words=get_chunk_unit_limit(lang))
    if not chunks: return None
    if SUB_EFFECT != "pop": return max(ch["end"] for ch in chunks)
    last_end = None
    for ch in chunks:
        pop_events = _build_non_overlapping_pop_events(ch["words"], ch["start"], ch["end"], lang=lang)
        ce = max(pop_events[-1][1], ch["end"]) if pop_events else ch["end"]
        last_end = ce if last_end is None or ce > last_end else last_end
    return last_end


# --- CJK text utilities ---

def is_cjk(s: str) -> bool:
    for ch in s:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0x20000 <= o <= 0x2A6DF or 0xF900 <= o <= 0xFAFF: return True
    return False

def _vis_len_zh(s: str) -> int:
    return sum(1 for ch in s if ch and not ch.isspace())

def zh_split_clauses(text: str) -> List[str]:
    text = (text or "").replace("\r", " ").replace("\n", " ").strip()
    if not text: return []
    clauses, buf = [], []
    def flush():
        s = "".join(buf).strip()
        if s: clauses.append(s)
        buf.clear()
    for i, ch in enumerate(text):
        if ch.isspace(): flush(); continue
        buf.append(ch)
        buf_str = "".join(buf)
        if ch in ZH_PUNCT: flush(); continue
        for p in ZH_PHRASE_BREAKS:
            if buf_str.endswith(p):
                nxt = next((text[j] for j in range(i+1, len(text)) if not text[j].isspace()), None)
                if nxt and is_cjk(nxt) and ZH_PHRASE_SPLIT_MIN <= _vis_len_zh(buf_str) <= ZH_PHRASE_SPLIT_MAX: flush()
                break
        if ch in ZH_SOFT_TOKENS:
            nxt = next((text[j] for j in range(i+1, len(text)) if not text[j].isspace()), None)
            if nxt and is_cjk(nxt) and nxt not in ZH_SOFT_TOKENS and ZH_PARTICLE_SPLIT_MIN <= _vis_len_zh(buf_str) <= ZH_PARTICLE_SPLIT_MAX: flush()
    flush()
    merged, i = [], 0
    while i < len(clauses):
        cur = clauses[i]
        if _vis_len_zh(cur) <= ZH_MERGE_TINY_MAX and i + 1 < len(clauses): clauses[i + 1] = (cur + clauses[i + 1]).strip()
        else: merged.append(cur)
        i += 1
    return [c for c in merged if c.strip()]

def _split_long_clause(clause: str, max_len: int) -> List[str]:
    clause = (clause or "").strip()
    if not clause or _vis_len_zh(clause) <= max_len: return [clause] if clause else []
    parts, cur = [], ""
    for ch in clause:
        cur += ch
        if _vis_len_zh(cur) >= max_len: parts.append(cur.strip()); cur = ""
    if cur.strip(): parts.append(cur.strip())
    return parts

# Characters that are never meaningful as a standalone subtitle line.
# A line consisting only of these (plus spaces) is dropped entirely.
_PUNCT_ONLY_CHARS = set('，。！？；：、…～~,.!?;:·—–-=+*()（）【】《》`@#$%^&|_')

def _is_displayable(line: str) -> bool:
    """Return True only if the line contains at least one non-punctuation,
    non-space character worth showing as a subtitle."""
    s = (line or "").strip()
    if not s:
        return False
    return any(ch not in _PUNCT_ONLY_CHARS and not ch.isspace() for ch in s)

def zh_pack_lines(text: str) -> List[str]:
    lines = []
    for c in zh_split_clauses(text):
        lines.extend(_split_long_clause(c, ZH_SOFT_MAX) if _vis_len_zh(c) > ZH_SOFT_MAX else [c])
    safe = []
    for ln in lines:
        safe.extend(_split_long_clause(ln, ZH_SOFT_MAX) if _vis_len_zh(ln) > ZH_SOFT_MAX else [ln])
    return [ln.strip() for ln in safe if _is_displayable(ln)]

def en_wrap_lines(text: str, max_words: int = 14) -> List[str]:
    words = (text or "").strip().split()
    lines = [" ".join(words[i:i+max_words]) for i in range(0, len(words), max_words) if words[i:i+max_words]]
    return [ln for ln in lines if _is_displayable(ln)]

def chunk_text_for_ass(raw_text: str, lang: str) -> List[str]:
    raw_text = (raw_text or "").strip()
    if not raw_text: return []
    return zh_pack_lines(raw_text) if is_zh_lang(lang) or is_cjk(raw_text) else en_wrap_lines(raw_text)


# --- ASS renderers ---

def _ass_header_pop(font_name: str, font_size: int, play_w: int, play_h: int, margin_lr: int, margin_v: int) -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3.5,1.5,2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

def _ass_header_linewise(font_name: str, font_size: int, play_w: int, play_h: int, margin_lr: int, margin_v: int) -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3.5,1.5,2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

def build_direct_ass(
    segments: List[Dict[str, Any]],
    font_name: str,
    play_w: int,
    play_h: int,
    lang: str,
) -> str:
    """
    Write one ASS Dialogue line per segment.
    Start = first word timestamp. End = last word timestamp + small pad.
    Zero lines during silence gaps — subtitles disappear exactly when audio ends.
    This is the simplest possible correct implementation.
    """
    font_name  = resolve_font_name(font_name, lang).replace(",", " ")
    font_tag   = ass_font_tag(font_name)
    font_size  = max(42, int(play_h * 0.050))
    margin_lr  = max(36, int(play_w * 0.055))
    margin_v   = max(60, int(play_h * 0.0625))
    SUB_PAD    = 0.10   # seconds to hold after last word

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3.5,1.5,2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = []
    for seg in segments:
        raw_text = (seg.get("text") or "").strip()
        if not raw_text:
            continue

        words = seg.get("words") or []
        first_ws = None
        last_we  = None

        # Find first word with a valid start timestamp (including t=0.0)
        for w in words:
            if not isinstance(w, dict): continue
            try:
                s = w.get("start")
                if s is not None:
                    first_ws = float(s)
                    break
            except Exception: pass

        # Find last word with a valid end timestamp (scan backwards)
        for w in reversed(words):
            if not isinstance(w, dict): continue
            try:
                e = w.get("end")
                if e is not None:
                    v = float(e)
                    if v > 0:
                        last_we = v
                        break
            except Exception: pass

        seg_start = float(seg.get("start") or 0)
        seg_end   = float(seg.get("end")   or seg_start)

        t_start = first_ws if first_ws is not None else seg_start

        if last_we is not None:
            t_end = last_we + SUB_PAD
        else:
            # WhisperX alignment failed — estimate from text length
            zh_mode = is_cjk(raw_text)
            unit_count = len([c for c in raw_text if not c.isspace()]) if zh_mode else len(raw_text.split())
            rate = 4.5 if zh_mode else 3.0
            est_end = t_start + (unit_count / rate) + 0.2
            t_end = min(est_end, seg_end)

        if t_end <= t_start:
            t_end = t_start + 0.5

        if DEBUG:
            print(f"[ASS] '{raw_text[:40]}' → {t_start:.3f}-{t_end:.3f}s")

        tags = f"{{\\an2\\q2\\fad({FADE_MS},{FADE_MS}){font_tag}\\bord3.5\\shad1.5}}"
        lines.append(f"Dialogue: 0,{ass_time(t_start)},{ass_time(t_end)},Default,,0,0,0,,{tags}{esc(raw_text)}")

    return header + "\n".join(lines) + "\n"


def build_line_ass_pop(segments: List[Dict[str, Any]], render_until: float, play_w: int, play_h: int, persona_id: Optional[str] = None, lang: Optional[str] = None) -> str:
    profile = get_subtitle_profile(persona_id, lang)
    subtitle_lang, font_name = profile["lang"], profile["font_name"]
    font_tag  = ass_font_tag(font_name)
    font_size = max(36, int(play_h * 0.055))
    margin_v  = max(28, int(play_h * 0.06))
    margin_lr = max(24, int(play_w * 0.05))
    pos_tag   = subtitle_pos_tag(play_w, play_h, margin_v)
    header    = _ass_header_pop(font_name, font_size, play_w, play_h, margin_lr, margin_v)

    event_rows: List[Dict[str, Any]] = []
    last_base_idx: Optional[int] = None
    last_sub_end = 0.0

    def add_event(layer, start, end, style, text, tags="", is_base=False):
        nonlocal last_base_idx, last_sub_end
        if end <= start: return
        event_rows.append({"layer": layer, "start": start, "end": end, "style": style, "text": text, "tags": tags})
        if is_base: last_base_idx = len(event_rows) - 1; last_sub_end = max(last_sub_end, end)

    chunks = build_display_chunks_from_segments(segments, render_limit=render_until, lang=subtitle_lang, max_words=get_chunk_unit_limit(subtitle_lang))
    n_chunks = len(chunks)
    for c_idx, chunk in enumerate(chunks):
        cw            = chunk["words"]
        cs            = chunk["start"]
        ce            = chunk["end"]
        is_last_chunk = (c_idx == n_chunks - 1)
        base_text     = esc(chunk["text"])

        pop_events = _build_non_overlapping_pop_events(cw, cs, ce, lang=subtitle_lang)

        if not pop_events:
            # WhisperX gave no usable timestamps — manufacture a single pop
            # event covering the whole chunk with the last token highlighted.
            # Hard rule: NEVER show plain static text for any chunk.
            last_idx = max(0, len(cw) - 1)
            full_pop = _pop_full_line_text(cw, last_idx, subtitle_lang) if cw else base_text
            add_event(0, cs, ce, "Default", full_pop, tags=f"{{{pos_tag}{font_tag}}}", is_base=True)
            continue

        # Emit pop events — each token highlights green in sequence.
        for i, (ev_start, ev_end, line_text) in enumerate(pop_events):
            add_event(0, ev_start, ev_end, "Default", line_text, tags=f"{{{pos_tag}{font_tag}}}", is_base=True)
            next_s = pop_events[i + 1][0] if i + 1 < len(pop_events) else None
            if next_s and next_s > ev_end:
                # Gap between consecutive pop events: show un-highlighted base
                # text only for non-last positions.
                add_event(0, ev_end, next_s, "Default", base_text, tags=f"{{{pos_tag}{font_tag}}}", is_base=True)

        # Hard rule: after the last pop event, the last token stays green
        # until ce (= actual_clip_end). No plain base text, no gap, no fade.
        last_ae = pop_events[-1][1]
        last_pop_text = pop_events[-1][2]
        if last_ae < ce:
            add_event(0, last_ae, ce, "Default", last_pop_text, tags=f"{{{pos_tag}{font_tag}}}", is_base=True)

    return header + "\n".join(_dialogue_line(r["layer"], r["start"], r["end"], r["style"], r["text"], r["tags"]) for r in event_rows) + "\n"


def build_line_ass_linewise(segments: List[Dict[str, Any]], timeline_duration: float, font_name: str, play_w: int, play_h: int, lang: str) -> str:
    font_name = resolve_font_name(font_name, lang).replace(",", " ")
    font_tag  = ass_font_tag(font_name)
    font_size = max(42, int(play_h * 0.050))
    margin_lr = max(36, int(play_w * 0.055))
    margin_v  = max(60, int(play_h * 0.0625))
    header    = _ass_header_linewise(font_name, font_size, play_w, play_h, margin_lr, margin_v)
    events: List[str] = []

    for idx, seg in enumerate(segments):
        raw_text = (seg.get("text") or "").strip()
        if not raw_text: continue
        zh_mode  = is_zh_lang(lang) or is_cjk(raw_text)
        min_line = MIN_LINE_DUR_ZH if zh_mode else MIN_LINE_DUR
        seg_start = float(seg.get("start", 0.0) or 0.0)

        # seg["end"] = actual_clip_end set by run_subtitle_job.
        # ZH: use it directly — WhisperX ends too early for Chinese.
        # EN: use last word timestamp + pad, clamped to actual_clip_end.
        actual_clip_end_f = float(seg["end"]) if seg.get("end") else None

        # Find last valid word end timestamp
        hard_end = None
        words = seg.get("words")
        if isinstance(words, list):
            for w in reversed(words):
                if not isinstance(w, dict): continue
                try:
                    v = w.get("end") or w.get("we")
                    if v:
                        fv = float(v)
                        if fv > 0:
                            hard_end = fv + 0.15
                            break
                except Exception:
                    pass

        # actual_clip_end_f = seg["end"] = real WAV end set by run_subtitle_job.
        # ZH: use directly — WhisperX ends too early for Chinese.
        # EN: cap word-derived hard_end to actual_clip_end but don't extend
        #     into TTS trailing silence (causes overlap symptom).
        if actual_clip_end_f is not None:
            if zh_mode:
                hard_end = actual_clip_end_f
            else:
                hard_end = min(hard_end, actual_clip_end_f) if hard_end else actual_clip_end_f
        elif hard_end is None:
            unit_count = len(raw_text.split()) if not zh_mode else _vis_len_zh(raw_text)
            hard_end = seg_start + (unit_count / (4.5 if zh_mode else 3.0)) + 0.3

        lines = chunk_text_for_ass(raw_text, "zh" if zh_mode else "en")
        if not lines: continue
        units_list  = [max(1, _vis_len_zh(l) if zh_mode else len(l.split())) for l in lines]
        total_units = max(1, sum(units_list))

        total_dur = max(hard_end - seg_start, min_line)
        cursor, remaining = seg_start, total_dur

        for i, (line, u) in enumerate(zip(lines, units_list)):
            if i == len(lines) - 1:
                line_dur = max(remaining, min_line)
            else:
                share = total_dur * (u / total_units)
                line_dur = max(share, min_line)
                min_needed = (len(lines) - i - 1) * min_line
                if remaining - line_dur < min_needed:
                    line_dur = max(min_line, remaining - min_needed)

            line_start = cursor
            # Always clamp line_end to hard_end — this is the single source of truth
            line_end   = min(cursor + line_dur, hard_end)
            if line_end - line_start < min_line:
                line_end = min(line_start + min_line, hard_end)
            if line_end <= line_start + 1e-4:
                break

            tags = f"{{\\an2\\q2\\fad({FADE_MS},{FADE_MS}){font_tag}\\bord3.5\\shad1.5}}"
            events.append(f"Dialogue: 0,{ass_time(line_start)},{ass_time(line_end)},Default,,0,0,0,,{tags}{esc(line)}")
            cursor = line_end
            remaining = max(0.0, hard_end - cursor)
            if cursor >= hard_end - 1e-3:
                break

    return header + "\n".join(events) + "\n"


# --- Frame extraction ---

class ExtractFramesRequest(BaseModel):
    video_url: str

def _extract_frames_with_pts(video: str, frame_count: int, duration: float, folder: str) -> List[float]:
    """
    Extract frames and capture their exact timestamps in one ffmpeg pass.
    Uses the showinfo filter to read pts_time for each output frame.
    Returns a list of video_time values (seconds from video start, i.e. 0-based).
    Falls back to uniform estimation if parsing fails.
    """
    import re
    fps = frame_count / duration
    # showinfo prints lines like: pts_time:1.485 to stderr
    try:
        result = subprocess.run(
            [FFMPEG_BIN, "-y", "-i", video,
             "-vf", f"fps={fps},showinfo",
             f"{folder}/frame_%03d.jpg"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        stderr = result.stderr.decode("utf-8", "ignore")
        # Extract pts_time values from showinfo output lines
        pts_list = []
        for m in re.finditer(r"pts_time:([\.\d]+)", stderr):
            pts_list.append(float(m.group(1)))
        if len(pts_list) == frame_count:
            return [round(t, 3) for t in pts_list]
        if DEBUG:
            print(f"[WARN] showinfo pts count {len(pts_list)} != frame_count {frame_count}, falling back")
    except Exception as e:
        if DEBUG:
            print(f"[WARN] _extract_frames_with_pts failed ({e}), falling back")
        # Still need to extract frames even if pts parsing failed
        run([FFMPEG_BIN, "-y", "-i", video, "-vf", f"fps={fps}", f"{folder}/frame_%03d.jpg"])
    # Fallback: uniform timestamps
    return [round(i * duration / frame_count, 3) for i in range(frame_count)]


@app.post("/extract-frames")
def extract_frames(payload: ExtractFramesRequest, request: Request):
    cleanup_old_jobs()
    job_id = str(uuid.uuid4())
    video  = f"/tmp/{job_id}.mp4"
    download_file(payload.video_url, video)
    duration    = probe_duration(video)
    frame_count = min(MAX_FRAMES, max(1, int(round(duration))))
    folder      = os.path.join(FRAMES_DIR, job_id)
    os.makedirs(folder, exist_ok=True)

    # Extract frames and get exact per-frame timestamps in one pass
    pts_list = _extract_frames_with_pts(video, frame_count, duration, folder)

    base = str(request.base_url).rstrip("/")
    frames = [
        {
            "frame_url":   f"{base}/frames/{job_id}/frame_{i+1:03d}.jpg",
            "frame_index": i,
            "video_time":  pts_list[i] if i < len(pts_list) else round(i * duration / frame_count, 3),
        }
        for i in range(frame_count)
    ]
    safe_remove(video)
    return {"job_id": job_id, "duration": round(duration, 3), "frame_count": frame_count, "frames": frames}


# ---------------------------------------------------------------------------
# Skills Validation Layer (Requirement 1 + 8)
# ---------------------------------------------------------------------------

# Priority mapping for V2 event types → internal priority (lower = higher priority)
_EVENT_PRIORITY_MAP: Dict[str, int] = {
    # kill-class  → 1
    "player_elimination": 1, "kill": 1, "final_kill": 1, "execution": 1,
    # knock-class → 2
    "player_knock": 2, "knock": 2, "down": 2,
    # damage-class → 3
    "damage": 3, "hit": 3, "grenade_damage": 3, "explosion": 3,
    # killfeed / UI updates → 3
    "killfeed_update": 3, "ui_update": 3,
    # movement / misc → 4
    "movement": 4, "revive": 4, "loot": 4, "zone": 4,
    "stair_hold": 4, "grenade_throw": 4, "reload": 4,
}

# Confidence threshold below which events are skipped
_CONFIDENCE_THRESHOLD = 0.55

# Max drift (seconds) before ground truth overrides VLM video_time
_TIMESTAMP_DRIFT_THRESHOLD = 0.5

# Minimum gap (seconds) between same-type events to avoid duplicates
_DEDUP_MIN_GAP = 1.0


def _build_gt_map(frames: List[Dict]) -> Dict[int, float]:
    """Build a k → video_time ground truth lookup from the frames list."""
    return {f["frame_index"]: round(float(f["video_time"]), 3) for f in frames}


def _resolve_video_time(entry: Dict, gt_map: Dict[int, float], drift_log: List[Dict]) -> Optional[float]:
    """
    Resolve the authoritative video_time for a VLM output entry.

    Priority:
      1. Ground truth from gt_map[k]  (always preferred)
      2. entry["video_time"] as fallback if k is missing from gt_map

    If VLM's video_time deviates > _TIMESTAMP_DRIFT_THRESHOLD from ground truth,
    the drift is logged and ground truth wins.
    """
    k = entry.get("k")
    vlm_vt = entry.get("video_time")

    if k is not None and k in gt_map:
        gt_vt = gt_map[k]
        if vlm_vt is not None:
            drift = abs(float(vlm_vt) - gt_vt)
            if drift > _TIMESTAMP_DRIFT_THRESHOLD:
                drift_log.append({
                    "k": k,
                    "vlm_video_time": vlm_vt,
                    "gt_video_time": gt_vt,
                    "drift_s": round(drift, 3),
                })
        return gt_vt

    # k not in gt_map (e.g. out-of-range k)
    if vlm_vt is not None:
        return round(float(vlm_vt), 3)
    return None


def _validate_events(
    events: List[Dict],
    gt_map: Dict[int, float],
    max_k: int,
    drift_log: List[Dict],
) -> List[Dict]:
    """
    Validate and clean VLM events list:
      - Drop entries with k > max_k (out-of-range)
      - Override video_time with ground truth
      - Drop entries with null video_time after resolution
      - Drop low-confidence events (confidence < threshold)
      - Deduplicate same-type events within _DEDUP_MIN_GAP seconds
      - Assign priority
    """
    validated = []
    last_by_type: Dict[str, float] = {}  # event_type → last accepted video_time

    for ev in events:
        k = ev.get("k")

        # 1. Drop out-of-range k
        if k is not None and k > max_k:
            if DEBUG:
                print(f"[SKILLS] Drop event k={k} (out of range, max_k={max_k})")
            continue

        # 2. Resolve ground truth video_time
        resolved_vt = _resolve_video_time(ev, gt_map, drift_log)
        if resolved_vt is None:
            if DEBUG:
                print(f"[SKILLS] Drop event k={k} (unresolvable video_time)")
            continue

        # 3. Confidence filter
        confidence = ev.get("confidence", 1.0)
        if confidence is not None and float(confidence) < _CONFIDENCE_THRESHOLD:
            if DEBUG:
                print(f"[SKILLS] Drop event k={k} type={ev.get('type')} confidence={confidence} < {_CONFIDENCE_THRESHOLD}")
            continue

        # 4. Deduplication: same event_type within _DEDUP_MIN_GAP seconds
        ev_type = ev.get("type", "unknown")
        last_vt = last_by_type.get(ev_type)
        if last_vt is not None and abs(resolved_vt - last_vt) < _DEDUP_MIN_GAP:
            if DEBUG:
                print(f"[SKILLS] Dedup event k={k} type={ev_type} vt={resolved_vt} (last={last_vt})")
            continue

        # 5. Build validated entry (override video_time with ground truth)
        validated_ev = {**ev, "video_time": resolved_vt}
        validated_ev["priority"] = _EVENT_PRIORITY_MAP.get(ev_type, 4)
        validated.append(validated_ev)
        last_by_type[ev_type] = resolved_vt

    # Sort by video_time ascending
    validated.sort(key=lambda e: e["video_time"])
    return validated


def _validate_section(
    entries: List[Dict],
    gt_map: Dict[int, float],
    max_k: int,
    drift_log: List[Dict],
    section_name: str,
) -> List[Dict]:
    """
    Generic validator for views / metrics / squads sections:
      - Drop out-of-range k
      - Override video_time with ground truth
      - Drop entries with unresolvable video_time
    """
    result = []
    for entry in entries:
        k = entry.get("k")
        if k is not None and k > max_k:
            if DEBUG:
                print(f"[SKILLS] Drop {section_name} k={k} (out of range)")
            continue
        resolved_vt = _resolve_video_time(entry, gt_map, drift_log)
        if resolved_vt is None:
            if DEBUG:
                print(f"[SKILLS] Drop {section_name} k={k} (unresolvable video_time)")
            continue
        result.append({**entry, "video_time": resolved_vt})
    result.sort(key=lambda e: e.get("video_time", 0))
    return result


class ValidateVlmRequest(BaseModel):
    vlm_output: Dict[str, Any]   # parsed VLM JSON (views/metrics/events/squads)
    frames: List[Dict[str, Any]] # frames list from /extract-frames response


@app.post("/validate-vlm")
def validate_vlm(payload: ValidateVlmRequest):
    """
    Enhanced Skills validation layer with intent recognition and player anonymization:
    - Builds ground truth k→video_time map from the /extract-frames frames list
    - Overrides all video_time fields in VLM output with ground truth values
    - Drops out-of-range k entries, low-confidence events, and near-duplicate events
    - Applies Skills.md rules for intent recognition and player name anonymization
    - Returns cleaned four-dimensional output with intent analysis and validation log
    """
    frames = payload.frames
    vlm = payload.vlm_output

    if not frames:
        raise HTTPException(400, "frames list is empty")

    gt_map = _build_gt_map(frames)
    max_k = max(gt_map.keys())
    drift_log: List[Dict] = []

    raw_events  = vlm.get("events",  []) or []
    raw_views   = vlm.get("views",   []) or []
    raw_metrics = vlm.get("metrics", []) or []
    raw_squads  = vlm.get("squads",  []) or []

    # Basic validation using existing logic
    validated_events  = _validate_events(raw_events, gt_map, max_k, drift_log)
    validated_views   = _validate_section(raw_views,   gt_map, max_k, drift_log, "views")
    validated_metrics = _validate_section(raw_metrics, gt_map, max_k, drift_log, "metrics")
    validated_squads  = _validate_section(raw_squads,  gt_map, max_k, drift_log, "squads")

    # Apply Skills validation layer with intent recognition
    try:
        from skills_node import main as skills_validate
        
        # Build frame timestamps for Skills validation
        frame_timestamps = [gt_map[k] for k in sorted(gt_map.keys()) if k <= max_k]
        
        # Prepare VLM output for Skills validation
        vlm_output_for_skills = {
            "events": validated_events,
            "views": validated_views,
            "metrics": validated_metrics,
            "squads": validated_squads
        }
        
        # Apply Skills validation
        skills_result = skills_validate(vlm_output_for_skills, frame_timestamps, "skills.md")
        
        # Return enhanced result with Skills analysis
        return {
            "views":     skills_result.get("views", validated_views),
            "metrics":   skills_result.get("metrics", validated_metrics),
            "events":    skills_result.get("events", validated_events),
            "squads":    skills_result.get("squads", validated_squads),
            "drift_log": drift_log,
            "intent_analysis": skills_result.get("intent_analysis", {}),
            "validation_log": skills_result.get("validation_log", {}),
            "stats": {
                "input_events":  len(raw_events),
                "output_events": len(skills_result.get("events", validated_events)),
                "dropped_events": len(raw_events) - len(skills_result.get("events", validated_events)),
                "drift_corrections": len(drift_log),
                "intent_detections": len(skills_result.get("intent_analysis", {}).get("multi_kill", [])) + 
                                     len(skills_result.get("intent_analysis", {}).get("rescue_attempt", [])) + 
                                     len(skills_result.get("intent_analysis", {}).get("team_fight", [])),
            },
        }
    except ImportError:
        # Fallback to basic validation if Skills module not available
        return {
            "views":     validated_views,
            "metrics":   validated_metrics,
            "events":    validated_events,
            "squads":    validated_squads,
            "drift_log": drift_log,
            "intent_analysis": {},
            "validation_log": {"skills_layer": "not_available"},
            "stats": {
                "input_events":  len(raw_events),
                "output_events": len(validated_events),
                "dropped_events": len(raw_events) - len(validated_events),
                "drift_corrections": len(drift_log),
                "intent_detections": 0,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# /validate-tts  — per-segment TTS pronunciation check + auto-retry
# ─────────────────────────────────────────────────────────────────────────────

TTS_VOICE_MAP = {
    "a": "f3297600-2172-40a7-b659-bc2f5c00597b",
    "b": "2047caa4-6d5d-4197-abb9-18c73d0c4ff8",
    "c": "57d33c20-1b5b-42a4-8de4-cd2a7e7ef802",
    "d": "1d8c086a-3509-4d83-9e2b-06e4b028c786",
}
TTS_REGEN_ENDPOINT = "http://ultrongw.woa.com/v2/tts/cyber-human/api/get_tts/sound.wav"
TTS_VALIDATE_MAX_RETRIES = 3
# Similarity threshold: 0.0 = accept anything, 1.0 = exact match required.
# 0.60 is intentionally lenient — TTS may paraphrase punctuation/particles.
TTS_SIM_THRESHOLD = float(os.environ.get("TTS_SIM_THRESHOLD", "0.60"))


class ValidateTtsSegment(BaseModel):
    segment_id: str
    audio_url:  str
    text:       str


class ValidateTtsRequest(BaseModel):
    segments:   List[ValidateTtsSegment]   # one entry per TTS segment
    persona_id: str = "a"                  # "a" | "b" | "c" | "d"


def _normalize_persona_key(persona_id: str) -> str:
    """Return lowercase single letter a/b/c/d from any persona_id format."""
    s = (persona_id or "a").strip().lower()
    # Handle "persona_a", "persona-a", "persona a", "a" etc.
    import re as _re
    m = _re.search(r'([abcd])$', s)
    return m.group(1) if m else "a"


def _is_zh_persona(persona_key: str) -> bool:
    return persona_key in ("c", "d")


def _asr_transcribe(wav_path: str, lang: str) -> str:
    """
    Run WhisperX transcription on a local WAV file.
    Returns the recognised text, or empty string on failure.
    Uses a cached ASR model — load_model() is only called once per language.
    """
    try:
        # ensure_asr_model() returns the cached model (loads once, reuses always)
        asr_model  = ensure_asr_model("base", lang)
        audio_data = whisperx.load_audio(wav_path)
        # MUST pass language= explicitly — without it Whisper auto-detects and
        # may output an English *translation* of Chinese audio instead of the
        # original Chinese transcription, causing similarity to always be 0.
        result     = asr_model.transcribe(audio_data, batch_size=8, language=lang)
        segments   = result.get("segments") or []
        return " ".join(s.get("text", "").strip() for s in segments).strip()
    except Exception as e:
        if DEBUG:
            print(f"[validate-tts] ASR error: {e}")
        return ""


def _text_similarity(ref: str, hyp: str, is_zh: bool) -> float:
    """
    Jaccard similarity on character-level tokens (ZH) or word-level (EN).
    Returns 0.0–1.0.
    """
    import re as _re
    def _clean(s: str) -> str:
        s = s.lower().strip()
        s = _re.sub(r"[^\w\s]", "", s)
        return s
    ref_c, hyp_c = _clean(ref), _clean(hyp)
    if not ref_c and not hyp_c:
        return 1.0
    if not ref_c or not hyp_c:
        return 0.0
    tokens_ref = list(ref_c) if is_zh else ref_c.split()
    tokens_hyp = list(hyp_c) if is_zh else hyp_c.split()
    s1, s2 = set(tokens_ref), set(tokens_hyp)
    union = len(s1 | s2)
    return len(s1 & s2) / union if union else 0.0


def _regen_tts(text: str, persona_key: str) -> Optional[str]:
    """
    Call the TTS endpoint to regenerate audio for `text`.
    Returns the audio URL on success, None on failure.
    """
    voice = TTS_VOICE_MAP.get(persona_key, TTS_VOICE_MAP["a"])
    payload = {
        "text":            text,
        "voice":           voice,
        "serviceProvider": "3",
    }
    try:
        resp = requests.get(TTS_REGEN_ENDPOINT, params=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        # Common response shapes: {"url": "..."} or {"audio_url": "..."} or {"out_url": "..."}
        url = (
            data.get("url")
            or data.get("audio_url")
            or data.get("out_url")
            or (resp.url if resp.url.endswith(".wav") else None)
        )
        return url if url else None
    except Exception as e:
        if DEBUG:
            print(f"[validate-tts] regen TTS error: {e}")
        return None


def _validate_one_segment(
    seg_id:       str,
    audio_url:    str,
    text:         str,
    persona_key:  str,
    is_zh:        bool,
    lang:         str,
) -> Dict[str, Any]:
    """
    Validate a single TTS segment:
      1. Download audio → temp WAV
      2. ASR transcribe
      3. Compute similarity vs expected text
      4. If below threshold → regen up to TTS_VALIDATE_MAX_RETRIES times
      5. If still failing after all retries → return original URL with warning

    Returns a result dict with:
      segment_id, audio_url (final accepted URL), passed, similarity,
      asr_text, retries_used, fallback_used
    """
    tmp_raw  = f"/tmp/vtts_{seg_id}_{uuid.uuid4().hex[:6]}.bin"
    tmp_wav  = f"/tmp/vtts_{seg_id}_{uuid.uuid4().hex[:6]}.wav"

    result: Dict[str, Any] = {
        "segment_id":   seg_id,
        "audio_url":    audio_url,   # will be updated if regen succeeds
        "passed":       False,
        "similarity":   0.0,
        "asr_text":     "",
        "retries_used": 0,
        "fallback_used": False,
        "error":        None,
    }

    def _try_url(url: str) -> Tuple[bool, float, str]:
        """Download url, ASR it, return (passed, similarity, asr_text)."""
        try:
            download_file(url, tmp_raw)
            ensure_wav_16k_mono(tmp_raw, tmp_wav)
            asr_text   = _asr_transcribe(tmp_wav, lang)
            similarity = _text_similarity(text, asr_text, is_zh)
            passed     = similarity >= TTS_SIM_THRESHOLD
            return passed, similarity, asr_text
        except Exception as e:
            if DEBUG:
                print(f"[validate-tts] _try_url error for {seg_id}: {e}")
            return False, 0.0, ""
        finally:
            for p in (tmp_raw, tmp_wav):
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except Exception:
                    pass

    # ── First attempt: original audio ───────────────────────────────────────
    passed, similarity, asr_text = _try_url(audio_url)
    result["similarity"] = similarity
    result["asr_text"]   = asr_text

    if passed:
        result["passed"] = True
        return result

    # ── Retry loop: regen up to TTS_VALIDATE_MAX_RETRIES times ──────────────
    for attempt in range(1, TTS_VALIDATE_MAX_RETRIES + 1):
        if DEBUG:
            print(f"[validate-tts] {seg_id}: sim={similarity:.2f} < {TTS_SIM_THRESHOLD} "
                  f"— regen attempt {attempt}/{TTS_VALIDATE_MAX_RETRIES}")

        new_url = _regen_tts(text, persona_key)
        if not new_url:
            if DEBUG:
                print(f"[validate-tts] {seg_id}: regen attempt {attempt} returned no URL")
            continue

        passed, similarity, asr_text = _try_url(new_url)
        result["retries_used"] = attempt
        result["similarity"]   = similarity
        result["asr_text"]     = asr_text

        if passed:
            result["audio_url"] = new_url   # use the regenerated audio
            result["passed"]    = True
            return result

    # ── All retries exhausted — fall back to original URL ───────────────────
    if DEBUG:
        print(f"[validate-tts] {seg_id}: all retries exhausted (sim={similarity:.2f}), "
              f"falling back to original URL")
    result["audio_url"]    = audio_url   # keep original
    result["passed"]       = False       # mark as not passed but still usable
    result["fallback_used"] = True
    return result


@app.post("/validate-tts")
def validate_tts(payload: ValidateTtsRequest):
    """
    Validate pronunciation accuracy for each TTS segment using WhisperX ASR.

    For each segment:
      - Transcribe the audio with WhisperX
      - Compare against the expected LLM text (Jaccard similarity)
      - If below threshold, regenerate via TTS endpoint up to 3 times
      - If still failing, return the original URL with fallback_used=True

    Request body:
      {
        "segments": [
          {"segment_id": "seg_00", "audio_url": "https://...", "text": "..."},
          ...
        ],
        "persona_id": "c"   // "a" | "b" | "c" | "d"
      }

    Response:
      {
        "results": [
          {
            "segment_id":    "seg_00",
            "audio_url":     "https://...",   // final accepted URL
            "passed":        true,
            "similarity":    0.87,
            "asr_text":      "...",
            "retries_used":  0,
            "fallback_used": false,
            "error":         null
          },
          ...
        ],
        "all_passed":      true,
        "pass_count":      3,
        "total":           3,
        "fallback_count":  0
      }
    """
    persona_key = _normalize_persona_key(payload.persona_id)
    is_zh       = _is_zh_persona(persona_key)
    lang        = "zh" if is_zh else "en"

    # Pre-warm the ASR model before spawning threads so the first segment
    # doesn't pay the cold-start penalty inside a worker thread.
    try:
        ensure_asr_model("base", lang)
    except Exception as e:
        if DEBUG:
            print(f"[validate-tts] ASR model pre-warm failed: {e}")

    # Process all segments in parallel — each segment is independent.
    # ThreadPoolExecutor is safe here because WhisperX transcribe() releases
    # the GIL during the heavy C/ONNX inference work.
    import concurrent.futures
    results: List[Dict[str, Any]] = [None] * len(payload.segments)  # type: ignore

    def _run(idx: int, seg: ValidateTtsSegment) -> None:
        results[idx] = _validate_one_segment(
            seg_id      = seg.segment_id,
            audio_url   = seg.audio_url,
            text        = seg.text,
            persona_key = persona_key,
            is_zh       = is_zh,
            lang        = lang,
        )

    max_workers = min(len(payload.segments), int(os.environ.get("VALIDATE_TTS_WORKERS", "4")))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = [pool.submit(_run, i, seg) for i, seg in enumerate(payload.segments)]
        concurrent.futures.wait(futs)

    pass_count     = sum(1 for r in results if r["passed"])
    fallback_count = sum(1 for r in results if r.get("fallback_used"))

    return {
        "results":        results,
        "all_passed":     pass_count == len(results),
        "pass_count":     pass_count,
        "total":          len(results),
        "fallback_count": fallback_count,
    }


# --- Subtitle worker helpers ---

def make_coarse_segments(texts: List[str], dur: float, lang: str = "en") -> List[Dict[str, Any]]:
    def units(t): return max(1, len([c for c in t if not c.isspace()]) if is_zh_lang(lang) else len(t.split()))
    wc = [units(t) for t in texts]; total = sum(wc) or 1
    cur, segs = 0.0, []
    for t, w in zip(texts, wc):
        d = dur * (w / total); segs.append({"start": cur, "end": cur + d, "text": t}); cur += d
    if segs: segs[-1]["end"] = dur
    return segs

def make_coarse_segments_linewise(texts: List[str], dur: float, lang: str) -> List[Dict[str, Any]]:
    if not texts: return []
    zh_mode = is_zh_lang(lang)
    est = [max(0.45, (max(1, _vis_len_zh(t)) if zh_mode else max(1, len(t.split()))) / max(0.1, SUB_CPS_ZH if zh_mode else SUB_WPS_EN)) for t in texts]
    scale = dur / max(1e-6, sum(est)) if dur > 0 else 1.0
    cur, segs = 0.0, []
    for t, e in zip(texts, est):
        d = max(0.30, e * scale); segs.append({"start": cur, "end": cur + d, "text": t}); cur += d
    if segs:
        segs[-1]["end"] = dur
        for i in range(1, len(segs)):
            if segs[i]["start"] < segs[i-1]["end"]: segs[i]["start"] = segs[i-1]["end"]
            if segs[i]["end"] < segs[i]["start"]:   segs[i]["end"]   = segs[i]["start"] + 0.01
        segs[-1]["end"] = dur
    return segs

def make_coarse_segments_from_placements(
    texts: List[str],
    placements: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build WhisperX coarse segments using the ACTUAL placement time windows
    instead of distributing text proportionally across the full audio duration.

    This is the correct approach when audio has been silence-padded to specific
    start_time offsets. Each text is paired with its placement's start/end so
    WhisperX aligns it against the right time window, and the resulting ASS
    events only appear while speech is actually playing.

    texts and placements must be in the same order (index-aligned).
    Segments where text is empty are skipped so WhisperX ignores silent gaps.
    """
    segs: List[Dict[str, Any]] = []
    for text, placement in zip(texts, placements):
        text = (text or "").strip()
        if not text:
            continue
        try:
            start = float(placement.get("start_time") or 0)
            end   = float(placement.get("end_time")   or start)
        except Exception:
            continue
        if end <= start:
            end = start + 0.1
        segs.append({"start": start, "end": end, "text": text})
    return segs

def _attach_words_if_missing(word_segments: Any, segments: List[Dict[str, Any]]):
    if not segments or (isinstance(segments[0], dict) and segments[0].get("words")): return
    if not isinstance(word_segments, list) or not word_segments: return
    for seg in segments:
        try: s0, e0 = float(seg.get("start", 0.0) or 0.0), float(seg.get("end", 0.0) or 0.0)
        except Exception: continue
        seg_words = []
        for w in word_segments:
            if not isinstance(w, dict): continue
            try: ws, we = float(w.get("start", -1)), float(w.get("end", -1))
            except Exception: continue
            if we > s0 and ws < e0:
                if "word" not in w and "text" in w: w = dict(w); w["word"] = w.get("text")
                seg_words.append(w)
        if seg_words: seg["words"] = seg_words


# ─────────────────────────────────────────────────────────────────────────────
# Audio track builder — silence-padded slot placement
# ─────────────────────────────────────────────────────────────────────────────
#
# Strategy:
#   Each TTS clip is placed at its placement start_time by prepending a silence
#   chunk of the exact gap duration.  This locks each clip to its video event.
#
#   Overflow handling (clip longer than its natural slot):
#     1. Strip leading/trailing TTS silence (already done below).
#     2. If stripped_dur <= available gap (time until next clip's start_time):
#        → play at natural speed, bleed into trailing silence — fine.
#     3. If stripped_dur > available gap:
#        a. Compute required atempo ratio = stripped_dur / natural_slot_dur.
#        b. Clamp ratio to [ATEMPO_MIN, ATEMPO_MAX].
#        c. Apply atempo to compressed clip; accept residual bleed if ratio
#           was clamped (it will fall in trailing silence, not over speech).
#
#   Subtitle timing:
#     WhisperX runs on the final master_wav after this function returns, so
#     all timestamps reflect actual audio playback position — no adjustment
#     needed in the subtitle pipeline.

def _build_atempo_filter(ratio: float) -> str:
    """
    Build a chained atempo filter string for ffmpeg.
    atempo is constrained to [0.5, 2.0] per stage; chain stages for extremes.
    ratio > 1 → speed up (compress);  ratio < 1 → slow down (expand).
    """
    stages: List[str] = []
    r = ratio
    # Speed-up chain
    while r > 2.0:
        stages.append("atempo=2.0")
        r /= 2.0
    # Slow-down chain
    while r < 0.5:
        stages.append("atempo=0.5")
        r /= 0.5
    stages.append(f"atempo={r:.6f}")
    return ",".join(stages)


def build_timed_audio_track(
    placements: List[Dict[str, Any]],
    audio_map: Dict[str, str],
    merge_id: str,
    total_duration: float,
    tmp_files: List[str],
) -> str:
    """
    Build a WAV audio track of exactly `total_duration` seconds where each
    TTS clip starts at its placement start_time.

    Returns the path to the final concatenated master WAV.
    """

    def make_silence(path: str, dur: float) -> str:
        """Write a silent WAV of `dur` seconds and register it for cleanup."""
        tmp_files.append(path)
        run([
            FFMPEG_BIN, "-y",
            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
            "-t", f"{dur:.6f}",
            "-c:a", "pcm_s16le", path,
        ])
        return path

    # ── 1. Sort placements by start_time ────────────────────────────────────
    ordered: List[Dict[str, Any]] = sorted(
        [p for p in placements if isinstance(p, dict) and _get_seg_id(p) and _get_seg_id(p) in audio_map],
        key=lambda p: float(p.get("start_time", 0) or 0),
    )
    if not ordered:
        raise RuntimeError("build_timed_audio_track: no audio clips found in placement map")

    # ── 2. Pre-compute slot boundaries ──────────────────────────────────────
    # natural_end  = placement's own end_time (the "ideal" window for this clip)
    # avail_end    = start_time of the next clip (hard ceiling before intruding
    #                on another segment's speech)
    slot_start:   List[float] = []
    slot_nat_end: List[float] = []   # placement end_time
    slot_avail_end: List[float] = [] # next clip's start_time (or total_duration)

    for i, seg in enumerate(ordered):
        s = float(seg.get("start_time", 0) or 0)
        e = float(seg.get("end_time", s)   or s)
        if i + 1 < len(ordered):
            next_s = float(ordered[i + 1].get("start_time", total_duration) or total_duration)
        else:
            next_s = total_duration
        slot_start.append(s)
        slot_nat_end.append(max(e, s))
        slot_avail_end.append(min(next_s, total_duration))  # never exceed video length

    # ── 3. TTS质量检查 ─────────────────────────────────────────────────────
    # 在执行音频处理前进行TTS质量检查，确保音频质量符合要求
    quality_check_results = []
    
    for i, seg in enumerate(ordered):
        sid = _get_seg_id(seg)
        audio_url = audio_map.get(sid, "")
        
        if not audio_url:
            quality_check_results.append({
                "segment_id": sid,
                "passed": False,
                "error": "音频URL为空",
                "audio_duration": 0.0
            })
            continue
        
        try:
            # 执行TTS质量检查
            quality_check = _perform_tts_quality_check(
                audio_url=audio_url,
                segment_id=sid,
                expected_text=seg.get("text", ""),
                language="zh",  # 根据persona配置调整
                retry_count=0,
                enable_direct_retry=True,
                tts_endpoint="http://ultrongw.woa.com/v2/tts/cyber-human/api/get_tts/sound.wav"
            )
            
            quality_check_results.append(quality_check)
            
            if not quality_check["passed"]:
                if DEBUG:
                    print(f"[TTS质量检查] {sid}: 未通过 - {quality_check.get('error', '未知错误')}")
                    if quality_check.get("retry_suggestion"):
                        print(f"[TTS质量检查] 重试建议: {quality_check['retry_suggestion']}")
                
                # 如果质量检查失败，尝试直接TTS重试
                if quality_check.get("direct_retry_available", False):
                    retry_result = _perform_direct_tts_retry(
                        segment_id=sid,
                        expected_text=seg.get("text", ""),
                        language="zh",
                        tts_endpoint="http://ultrongw.woa.com/v2/tts/cyber-human/api/get_tts/sound.wav"
                    )
                    
                    if retry_result["retry_success"]:
                        # 更新音频URL为重新生成的音频
                        audio_map[sid] = retry_result["new_audio_url"]
                        quality_check["retry_success"] = True
                        quality_check["new_audio_url"] = retry_result["new_audio_url"]
                        
                        if DEBUG:
                            print(f"[TTS直接重试] {sid}: 重试成功，使用新音频URL")
                    else:
                        if DEBUG:
                            print(f"[TTS直接重试] {sid}: 重试失败 - {retry_result.get('errors', [])}")
                
        except Exception as e:
            quality_check_results.append({
                "segment_id": sid,
                "passed": False,
                "error": f"质量检查异常: {str(e)}",
                "audio_duration": 0.0
            })
    
    # 统计质量检查结果
    passed_checks = sum(1 for result in quality_check_results if result["passed"])
    total_checks = len(quality_check_results)
    overall_quality_score = passed_checks / total_checks if total_checks > 0 else 0.0
    
    if DEBUG:
        print(f"[TTS质量检查] 总体分数: {overall_quality_score:.2f} ({passed_checks}/{total_checks} 通过)")
    
    # ── 4. Download, normalise, and strip silence from every clip ───────────
    # Results: list of (file_path, stripped_duration_seconds)
    stripped_clips: List[Tuple[str, float]] = []

    for i, seg in enumerate(ordered):
        sid  = _get_seg_id(seg)
        raw  = f"/tmp/{merge_id}_{sid}.bin"
        norm = f"/tmp/{merge_id}_{sid}_norm.wav"
        tmp_files.extend([raw, norm])

        download_file(audio_map[sid], raw)
        ensure_wav_16k_mono(raw, norm)
        norm_dur = probe_duration(norm)

        # Do not strip silence — silenceremove with start+stop periods in a
        # single pass can remove inter-word pauses from the middle of clips,
        # producing the "half a word then cut" symptom. TTS from professional
        # APIs has minimal padding so stripping is not needed.
        stripped, sdur = norm, norm_dur

        nat_slot = slot_nat_end[i] - slot_start[i]
        avail    = slot_avail_end[i] - slot_start[i]
        if DEBUG:
            print(
                f"[AUDIO] {sid}: norm={norm_dur:.3f}s  stripped={sdur:.3f}s  "
                f"nat_slot={nat_slot:.3f}s  avail={avail:.3f}s"
            )

        stripped_clips.append((stripped, sdur))

    # ── 4. Fit each clip to its slot (atempo stretch if needed) ─────────────
    fitted_clips: List[Tuple[str, float]] = []

    for i, ((clip_path, clip_dur), seg) in enumerate(zip(stripped_clips, ordered)):
        sid      = _get_seg_id(seg)
        nat_slot = slot_nat_end[i]   - slot_start[i]  # placement's own window
        avail    = slot_avail_end[i] - slot_start[i]  # hard ceiling

        # Case A: fits inside natural slot — no processing needed
        if clip_dur <= nat_slot + 0.05:
            if DEBUG:
                print(f"[FIT] {sid}: natural fit  clip={clip_dur:.3f}s  nat={nat_slot:.3f}s")
            fitted_clips.append((clip_path, clip_dur))
            continue

        # Case B: overruns natural slot but fits within available gap —
        #         let it bleed into trailing silence (no speech overlap)
        if clip_dur <= avail:
            if DEBUG:
                print(
                    f"[FIT] {sid}: trailing-gap bleed  "
                    f"clip={clip_dur:.3f}s  nat={nat_slot:.3f}s  avail={avail:.3f}s"
                )
            fitted_clips.append((clip_path, clip_dur))
            continue

        # Case C: overruns even the available gap — must compress with atempo
        # Target: fit within natural slot if possible, else fit within avail gap
        if nat_slot > 0.05:
            ratio = clip_dur / nat_slot
        else:
            ratio = clip_dur / max(avail, 0.1)

        ratio = max(ATEMPO_MIN, min(ATEMPO_MAX, ratio))

        stretched = f"/tmp/{merge_id}_{sid}_stretched.wav"
        tmp_files.append(stretched)
        af = _build_atempo_filter(ratio)
        run([
            FFMPEG_BIN, "-y", "-i", clip_path,
            "-af", af,
            "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1", stretched,
        ])
        stretched_dur = probe_duration(stretched)

        if DEBUG:
            print(
                f"[FIT] {sid}: atempo  ratio={ratio:.3f}  "
                f"clip={clip_dur:.3f}s → {stretched_dur:.3f}s  "
                f"nat={nat_slot:.3f}s  avail={avail:.3f}s"
            )

        fitted_clips.append((stretched, stretched_dur))

    # ── 5. Build the final segment list: silence → clip → silence → clip … ──
    # Build a map of segment_id → actual fitted clip duration.
    # This is the ground truth for how long each TTS clip plays in the final
    # audio track — used by run_subtitle_job to cap subtitle end times so
    # subtitles disappear exactly when the audio clip finishes, not when the
    # slot window ends.
    clip_durations: Dict[str, float] = {}
    for i, ((clip_path, clip_dur), seg) in enumerate(zip(fitted_clips, ordered)):
        sid = _get_seg_id(seg)
        if sid:
            clip_durations[sid] = clip_dur

    segment_wavs: List[str] = []
    cursor = 0.0  # current write position in the output timeline (seconds)

    for i, ((clip_path, clip_dur), seg) in enumerate(zip(fitted_clips, ordered)):
        sid    = _get_seg_id(seg)
        target = slot_start[i]

        gap = target - cursor
        if gap > 1e-4:
            # Fill the gap before this clip with silence
            sil_path = f"/tmp/{merge_id}_gap_{i}.wav"
            segment_wavs.append(make_silence(sil_path, gap))
            cursor += gap
        elif gap < -0.5:
            # Previous clip significantly overran into this slot.
            # This should only happen when atempo was clamped at ATEMPO_MAX and
            # the clip was still too long.  Log and continue — the clip is
            # placed at the cursor position (slightly late) rather than skipped.
            if DEBUG:
                print(
                    f"[WARN] {sid}: cursor={cursor:.3f}s overshot target={target:.3f}s "
                    f"by {cursor - target:.3f}s — placing immediately"
                )

        segment_wavs.append(clip_path)
        cursor += clip_dur

    # Pad tail silence so the track matches the video duration exactly
    tail = total_duration - cursor
    if tail > 1e-4:
        tail_path = f"/tmp/{merge_id}_tail.wav"
        segment_wavs.append(make_silence(tail_path, tail))
    elif tail < -0.5 and DEBUG:
        print(
            f"[INFO] audio track ({cursor:.3f}s) exceeds video ({total_duration:.3f}s) "
            f"by {cursor - total_duration:.3f}s — muxer will truncate"
        )

    # ── 6. Concatenate all segments into a single master WAV ────────────────
    concat_list = f"/tmp/{merge_id}_timed_list.txt"
    tmp_files.append(concat_list)
    with open(concat_list, "w", encoding="utf-8") as fh:
        for wav in segment_wavs:
            fh.write(f"file '{concat_quote_path(wav)}'\n")

    master_wav = f"/tmp/{merge_id}_timed_master.wav"
    tmp_files.append(master_wav)
    run([
        FFMPEG_BIN, "-y",
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        master_wav,
    ])
    return master_wav, clip_durations


# --- TTS Quality Check Functions ---

def validate_tts_quality(
    tts_files: List[Dict], 
    expected_texts: str, 
    retry_count: int = 0,
    language: str = "zh",
    tts_duration: float = 0.0
) -> Dict[str, Any]:
    """
    TTS质量检查节点
    验证TTS音频的发音质量，支持重试机制
    
    Args:
        tts_files: TTS生成的音频文件列表
        expected_texts: 期望的文本内容（字符串）
        retry_count: 当前重试次数
        language: 语言设置
        tts_duration: 音频时长信息（秒）
    
    Returns:
        Dict包含质量检查结果和重试状态
    """
    
    # 默认配置
    DEFAULT_CONFIG = {
        "quality_threshold": 0.8,
        "max_retries": 3,
        "min_audio_duration": 0.5,  # 最小音频时长(秒)
        "max_audio_duration": 10.0, # 最大音频时长(秒)
        "asr_similarity_threshold": 0.7,  # ASR相似度阈值
        "enable_asr_check": True,  # 启用ASR检查
    }
    
    # 使用默认配置
    config = DEFAULT_CONFIG
    
    # 处理expected_texts：如果是字符串，转换为列表
    if isinstance(expected_texts, str):
        # 假设每个音频文件对应相同的文本
        expected_texts_list = [expected_texts] * len(tts_files)
    else:
        expected_texts_list = expected_texts
    
    # 初始化结果变量
    validation_results = []
    passed_checks = 0
    total_checks = len(tts_files)
    
    # 检查音频文件
    for i, (audio_file, expected_text) in enumerate(zip(tts_files, expected_texts_list)):
        check_result = _check_single_audio(audio_file, expected_text, config, language)
        validation_results.append(check_result)
        
        if check_result["passed"]:
            passed_checks += 1
    
    # 计算总体质量分数
    overall_quality_score = 0.0
    if total_checks > 0:
        overall_quality_score = passed_checks / total_checks
    
    # 判断是否需要重试
    needs_retry = False
    retry_reason = ""
    workflow_status = "active"
    
    if overall_quality_score < config["quality_threshold"]:
        if retry_count < config["max_retries"]:
            needs_retry = True
            retry_reason = f"质量分数 {overall_quality_score:.2f} 低于阈值 {config['quality_threshold']}"
            workflow_status = "retry_needed"
        else:
            needs_retry = False
            retry_reason = "已达到最大重试次数"
            workflow_status = "fallback_needed"
    else:
        needs_retry = False
        retry_reason = "质量检查通过"
        workflow_status = "completed"
    
    # 更新重试计数
    next_retry_count = retry_count + 1 if needs_retry else retry_count
    
    # 判断是否全部可接受
    all_acceptable = "yes" if overall_quality_score >= config["quality_threshold"] else "no"
    
    # 生成建议
    recommendation = _generate_recommendation(overall_quality_score, needs_retry, retry_count, config)
    
    return {
        # ========== 验证结果 (Array[Object]) ==========
        "validation_results": validation_results,
        
        # ========== 质量状态 (String) ==========
        "all_acceptable": all_acceptable,
        "workflow_status": workflow_status,
        
        # ========== 重试计数 (Number) ==========
        "retry_count": retry_count,
        "next_retry_count": next_retry_count,
        "max_retries": config["max_retries"],
        
        # ========== 质量分数 (Number) ==========
        "overall_quality_score": overall_quality_score,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "quality_threshold": config["quality_threshold"],
        
        # ========== 重试状态 (String/Number) ==========
        "needs_retry": "yes" if needs_retry else "no",
        "needs_retry_flag": 1 if needs_retry else 0,
        "retry_reason": retry_reason,
        
        # ========== 建议信息 (String) ==========
        "recommendation": recommendation
    }


def _check_single_audio(audio_file: Dict, expected_text: str, config: Dict, language: str) -> Dict[str, Any]:
    """检查单个音频文件的质量"""
    
    result = {
        "audio_index": audio_file.get("index", 0),
        "expected_text": expected_text,
        "audio_url": audio_file.get("url", ""),
        "audio_size": audio_file.get("size", 0),
        "passed": False,
        "quality_score": 0.0,
        "checks": {},
        "errors": [],
        "asr_result": None,
        "pronunciation_similarity": 0.0
    }
    
    try:
        # 检查1: 音频文件可访问性
        accessibility_check = _check_audio_accessibility(audio_file)
        result["checks"]["accessibility"] = accessibility_check
        
        if not accessibility_check["passed"]:
            result["errors"].append(f"音频文件不可访问: {accessibility_check['error']}")
            return result
        
        # 检查2: 音频时长
        duration_check = _check_audio_duration(audio_file, config)
        result["checks"]["duration"] = duration_check
        
        if not duration_check["passed"]:
            result["errors"].append(f"音频时长异常: {duration_check['error']}")
            return result
        
        # 检查3: 音频文件大小
        size_check = _check_audio_size(audio_file)
        result["checks"]["size"] = size_check
        
        if not size_check["passed"]:
            result["errors"].append(f"音频文件大小异常: {size_check['error']}")
            return result
        
        # 检查4: 音频格式
        format_check = _check_audio_format(audio_file)
        result["checks"]["format"] = format_check
        
        if not format_check["passed"]:
            result["errors"].append(f"音频格式异常: {format_check['error']}")
            return result
        
        # 检查5: ASR发音准确性检查（核心功能）
        if config.get("enable_asr_check", True):
            asr_check = _check_audio_pronunciation(audio_file, expected_text, language, config)
            result["checks"]["asr"] = asr_check
            result["asr_result"] = asr_check.get("asr_text", "")
            result["pronunciation_similarity"] = asr_check.get("similarity", 0.0)
        else:
            # 如果禁用ASR检查，使用基础检查结果
            asr_check = {"passed": True, "similarity": 1.0, "asr_text": "ASR检查已禁用"}
            result["checks"]["asr"] = asr_check
            result["asr_result"] = "ASR检查已禁用"
            result["pronunciation_similarity"] = 1.0
        
        # 计算综合质量分数
        base_score = 1.0  # 基础分数
        penalty = 0.0     # 扣分项
        
        # 根据基础检查错误类型扣分
        if duration_check.get("warning", False):
            penalty += 0.1
        if size_check.get("warning", False):
            penalty += 0.1
        
        # 根据ASR相似度调整分数
        asr_similarity = result["pronunciation_similarity"]
        if asr_similarity < config.get("asr_similarity_threshold", 0.7):
            penalty += (config.get("asr_similarity_threshold", 0.7) - asr_similarity)
        
        result["quality_score"] = max(0.0, base_score - penalty)
        result["passed"] = result["quality_score"] >= config["quality_threshold"]
        
    except Exception as e:
        result["errors"].append(f"质量检查异常: {str(e)}")
        result["passed"] = False
    
    return result


def _check_audio_accessibility(audio_file: Dict) -> Dict[str, Any]:
    """检查音频文件可访问性"""
    try:
        url = audio_file.get("url", "")
        if not url:
            return {"passed": False, "error": "音频URL为空"}
        
        # 发送HEAD请求检查文件可访问性
        response = requests.head(url, timeout=10)
        if response.status_code != 200:
            return {"passed": False, "error": f"HTTP状态码: {response.status_code}"}
        
        return {"passed": True, "status_code": response.status_code}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _check_audio_duration(audio_file: Dict, config: Dict) -> Dict[str, Any]:
    """检查音频时长"""
    try:
        duration = audio_file.get("duration", 0)
        
        if duration <= 0:
            return {"passed": False, "error": "音频时长为0"}
        
        if duration < config["min_audio_duration"]:
            return {"passed": False, "error": f"音频时长过短: {duration:.2f}s"}
        
        if duration > config["max_audio_duration"]:
            return {"passed": True, "warning": f"音频时长过长: {duration:.2f}s"}
        
        return {"passed": True, "duration": duration}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _check_audio_size(audio_file: Dict) -> Dict[str, Any]:
    """检查音频文件大小"""
    try:
        size = audio_file.get("size", 0)
        
        if size <= 0:
            return {"passed": False, "error": "音频文件大小为0"}
        
        if size < 1024:
            return {"passed": False, "error": f"文件大小过小: {size} bytes"}
        
        if size > 1024 * 1024:
            return {"passed": True, "warning": f"文件大小过大: {size} bytes"}
        
        return {"passed": True, "size": size}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _check_audio_format(audio_file: Dict) -> Dict[str, Any]:
    """检查音频格式"""
    try:
        mime_type = audio_file.get("mime_type", "")
        extension = audio_file.get("extension", "")
        
        # 检查是否为支持的音频格式
        supported_formats = ["audio/wav", "audio/mpeg", "audio/ogg"]
        supported_extensions = [".wav", ".mp3", ".ogg"]
        
        if mime_type and mime_type not in supported_formats:
            return {"passed": False, "error": f"不支持的MIME类型: {mime_type}"}
        
        if extension and extension.lower() not in supported_extensions:
            return {"passed": False, "error": f"不支持的扩展名: {extension}"}
        
        return {"passed": True, "mime_type": mime_type, "extension": extension}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _check_audio_pronunciation(audio_file: Dict, expected_text: str, language: str, config: Dict) -> Dict[str, Any]:
    """使用ASR检查音频发音准确性"""
    
    result = {"passed": False, "similarity": 0.0, "asr_text": "", "error": ""}
    
    try:
        # 下载音频文件
        audio_url = audio_file.get("url", "")
        if not audio_url:
            result["error"] = "音频URL为空"
            return result
        
        response = requests.get(audio_url, timeout=30)
        if response.status_code != 200:
            result["error"] = f"下载音频失败: HTTP {response.status_code}"
            return result
        
        audio_content = response.content
        
        # 使用WhisperX进行语音识别
        if WHISPERX_AVAILABLE:
            asr_result = _whisperx_asr_service(audio_content, language)
        else:
            # 如果WhisperX不可用，使用模拟服务
            asr_result = _mock_asr_service(audio_content, language)
        
        if not asr_result["success"]:
            result["error"] = f"ASR识别失败: {asr_result.get('error', '未知错误')}"
            return result
        
        recognized_text = asr_result["text"]
        confidence = asr_result.get("confidence", 0.0)
        
        # 计算文本相似度
        similarity = _calculate_text_similarity(expected_text, recognized_text, language)
        
        result["asr_text"] = recognized_text
        result["similarity"] = similarity
        result["confidence"] = confidence
        result["passed"] = similarity >= config.get("asr_similarity_threshold", 0.7)
        
    except Exception as e:
        result["error"] = f"ASR检查异常: {str(e)}"
    
    return result


def _whisperx_asr_service(audio_content: bytes, language: str) -> Dict[str, Any]:
    """使用WhisperX进行语音识别"""
    
    result = {"success": False, "text": "", "confidence": 0.0}
    
    try:
        if not WHISPERX_AVAILABLE:
            result["error"] = "WhisperX未安装"
            return result
        
        # 创建临时文件保存音频内容
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_content)
            temp_file_path = temp_file.name
        
        try:
            # 加载WhisperX模型
            device = "cpu"
            batch_size = 16
            model_size = "base"
            
            model = whisperx.load_model(model_size, device, compute_type="int8")
            
            # 音频识别
            audio = whisperx.load_audio(temp_file_path)
            result_whisper = model.transcribe(audio, batch_size=batch_size)
            
            # 获取识别文本
            if result_whisper["segments"]:
                recognized_text = " ".join([segment["text"].strip() for segment in result_whisper["segments"]])
                
                # 计算平均置信度
                confidences = [segment.get("avg_logprob", 0.5) for segment in result_whisper["segments"]]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
                confidence = min(1.0, max(0.0, (avg_confidence + 1.0) / 2.0))
                
                result["success"] = True
                result["text"] = recognized_text
                result["confidence"] = confidence
            else:
                result["error"] = "WhisperX未识别到任何文本"
                
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file_path)
            except:
                pass
                
    except Exception as e:
        result["error"] = f"WhisperX识别失败: {str(e)}"
    
    return result


def _mock_asr_service(audio_content: bytes, language: str) -> Dict[str, Any]:
    """模拟ASR服务，用于测试和演示"""
    
    # 模拟处理时间
    import time
    time.sleep(0.1)
    
    # 返回模拟结果
    return {
        "success": True,
        "text": "模拟识别结果",
        "confidence": 0.85
    }


def _calculate_text_similarity(text1: str, text2: str, language: str) -> float:
    """计算两个文本的相似度"""
    
    if not text1 or not text2:
        return 0.0
    
    # 转换为小写并去除标点符号
    import re
    text1_clean = re.sub(r'[^\w\s]', '', text1.lower())
    text2_clean = re.sub(r'[^\w\s]', '', text2.lower())
    
    # 分词（针对中文）
    if language == "zh":
        # 简单的中文分词（按字符分割）
        words1 = list(text1_clean)
        words2 = list(text2_clean)
    else:
        # 英文按空格分词
        words1 = text1_clean.split()
        words2 = text2_clean.split()
    
    # 计算Jaccard相似度
    set1 = set(words1)
    set2 = set(words2)
    
    if not set1 and not set2:
        return 1.0
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    similarity = intersection / union if union > 0 else 0.0
    
    return similarity


def _generate_recommendation(quality_score: float, needs_retry: bool, retry_count: int, config: Dict) -> str:
    """根据质量检查结果生成建议"""
    
    if quality_score >= config["quality_threshold"]:
        return "TTS音频质量良好，可以继续后续处理"
    
    if not needs_retry:
        return "已达到最大重试次数，建议使用备用TTS服务或调整文本内容"
    
    # 根据重试次数给出具体建议
    if retry_count == 0:
        return "首次质量检查未通过，建议调整TTS参数或检查文本内容"
    elif retry_count == 1:
        return "第二次重试未通过，建议简化文本或调整语音参数"
    elif retry_count == 2:
        return "第三次重试未通过，建议使用更简单的表达方式"
    else:
        return f"第{retry_count + 1}次重试未通过，建议检查TTS服务状态"


def validate_tts_audio_batch(
    placements: List[Dict[str, Any]],
    audio_map: Dict[str, str],
    language: str = "zh",
    tts_endpoint: str = "http://ultrongw.woa.com/v2/tts/cyber-human/api/get_tts/sound.wav",
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    批量验证TTS音频质量，返回验证结果和更新后的音频映射
    专为Dify工作流设计，验证通过后返回音频URL给工作流
    
    Args:
        placements: 音频放置配置列表
        audio_map: 音频URL映射
        language: 语言设置
        tts_endpoint: TTS服务端点
        max_retries: 最大重试次数
    
    Returns:
        包含验证结果和更新音频映射的字典
    """
    
    result = {
        "all_passed": False,
        "validated_placements": [],
        "updated_audio_map": {},
        "quality_results": [],
        "retry_summary": {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0
        },
        "recommendation": ""
    }
    
    updated_audio_map = audio_map.copy()
    validated_placements = []
    quality_results = []
    
    for placement in placements:
        segment_id = _get_seg_id(placement)
        audio_url = audio_map.get(segment_id, "")
        expected_text = placement.get("text", "")
        
        if not audio_url:
            # 记录错误但继续处理其他片段
            quality_results.append({
                "segment_id": segment_id,
                "passed": False,
                "error": "音频URL为空",
                "audio_duration": 0.0
            })
            continue
        
        # 执行质量检查
        quality_check = _perform_tts_quality_check(
            audio_url=audio_url,
            segment_id=segment_id,
            expected_text=expected_text,
            language=language,
            retry_count=0,
            enable_direct_retry=True,
            tts_endpoint=tts_endpoint
        )
        
        quality_results.append(quality_check)
        
        if quality_check["passed"]:
            # 质量检查通过，保留原音频URL
            validated_placements.append(placement)
            updated_audio_map[segment_id] = audio_url
        else:
            # 质量检查失败，尝试直接重试
            if quality_check.get("direct_retry_available", False):
                retry_result = _perform_direct_tts_retry(
                    segment_id=segment_id,
                    expected_text=expected_text,
                    language=language,
                    tts_endpoint=tts_endpoint,
                    max_retries=max_retries
                )
                
                result["retry_summary"]["total_retries"] += retry_result["retry_count"]
                
                if retry_result["retry_success"]:
                    result["retry_summary"]["successful_retries"] += 1
                    # 使用重新生成的音频
                    updated_audio_map[segment_id] = retry_result["new_audio_url"]
                    validated_placements.append(placement)
                    
                    if DEBUG:
                        print(f"[TTS验证] {segment_id}: 重试成功，使用新音频")
                else:
                    result["retry_summary"]["failed_retries"] += 1
                    if DEBUG:
                        print(f"[TTS验证] {segment_id}: 重试失败")
            else:
                # 无法重试，记录失败
                if DEBUG:
                    print(f"[TTS验证] {segment_id}: 质量检查失败且无法重试")
    
    # 统计结果
    passed_count = sum(1 for q in quality_results if q["passed"])
    total_count = len(quality_results)
    
    result["all_passed"] = (passed_count == total_count and total_count > 0)
    result["validated_placements"] = validated_placements
    result["updated_audio_map"] = updated_audio_map
    result["quality_results"] = quality_results
    result["passed_count"] = passed_count
    result["total_count"] = total_count
    
    # 生成建议
    if result["all_passed"]:
        result["recommendation"] = "所有音频质量检查通过，可以继续合并处理"
    elif passed_count > 0:
        result["recommendation"] = f"{passed_count}/{total_count} 个音频通过检查，建议继续处理"
    else:
        result["recommendation"] = "所有音频质量检查失败，建议检查TTS服务配置"
    
    if DEBUG:
        print(f"[TTS验证] 批量验证完成: {passed_count}/{total_count} 通过")
        print(f"[TTS验证] 重试统计: {result['retry_summary']}")
    
    return result


def merge_validated_audio_track(
    placements: List[Dict[str, Any]],
    audio_map: Dict[str, str],
    total_duration: float,
    merge_id: str = None
) -> Dict[str, Any]:
    """
    合并已验证的音频轨道，专为Dify工作流设计
    假设所有音频已经通过质量验证
    
    Args:
        placements: 已验证的音频放置配置
        audio_map: 已验证的音频URL映射
        total_duration: 视频总时长
        merge_id: 合并ID
    
    Returns:
        合并结果，包含音频文件路径和字幕信息
    """
    
    if not merge_id:
        merge_id = str(uuid.uuid4())
    
    # 直接调用现有的合并逻辑
    try:
        result = build_timed_audio_track(
            placements=placements,
            audio_map=audio_map,
            total_duration=total_duration,
            merge_id=merge_id
        )
        
        # 添加验证标记
        result["validation_status"] = "pre_validated"
        result["validated_segments"] = len(placements)
        
        if DEBUG:
            print(f"[音频合并] 已验证音频合并完成: {len(placements)} 个片段")
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"音频合并失败: {str(e)}",
            "validation_status": "pre_validated",
            "validated_segments": len(placements)
        }


# --- Subtitle worker ---

def run_subtitle_job(job_id: str, video_url: str, texts: List[str], base_url: str, persona_id: Optional[str] = None, subtitle_lang: Optional[str] = None, placement: Optional[List[Dict[str, Any]]] = None, clip_durations: Optional[Dict[str, float]] = None):
    with SUBTITLE_SEM:
        with _LOCK: SUBTITLE_JOBS[job_id]["status"] = JobStatus.running
        video      = f"/tmp/{job_id}.mp4"
        audio      = f"/tmp/{job_id}.wav"
        ass        = os.path.join(MERGED_DIR, f"{job_id}.ass")
        out        = os.path.join(MERGED_DIR, f"{job_id}_sub.mp4")
        norm_video = f"/tmp/{job_id}_norm.mp4"
        try:
            profile    = get_subtitle_profile(persona_id, subtitle_lang)
            lang, font_name = profile["lang"], profile["font_name"]
            pid        = normalize_persona_id(persona_id) or DEFAULT_PERSONA_ID
            align_lang  = ALIGN_LANG_ZH if is_zh_lang(lang) else ALIGN_LANG_EN
            allow_align = ENABLE_ALIGN_ZH if is_zh_lang(lang) else ENABLE_ALIGN_EN

            download_file(video_url, video)
            w_disp, h_disp, rot = probe_wh_rotate(video)
            burn_source = video
            if rot in (90, 180, 270):
                vf_rot = {"90": "transpose=1", "180": "hflip,vflip", "270": "transpose=2"}[str(rot)]
                run([FFMPEG_BIN, "-y", "-i", video, "-vf", vf_rot, "-metadata:s:v:0", "rotate=0", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "copy", norm_video])
                burn_source = norm_video
                w_disp, h_disp, _ = probe_wh_rotate(burn_source)

            # Extract audio from the merged video — this already contains the
            # correctly placed TTS track built by build_timed_audio_track, so
            # WhisperX timestamps will reflect real playback positions.
            run([FFMPEG_BIN, "-y", "-i", burn_source, "-vn", "-ac", "1", "-ar", "16000", audio])
            audio_dur        = probe_duration(audio)
            visual_video_dur = probe_video_duration(burn_source)

            # Build coarse segments using actual placement time windows when
            # available.  This is critical: the audio track is silence-padded
            # so each clip lives at its start_time offset.  Distributing texts
            # proportionally across the full duration would misalign WhisperX
            # and produce phantom subtitles over silent sections.
            if placement and len(placement) == len(texts):
                if DEBUG: print(f"[SUB] using placement-aware coarse segments: {len(placement)} slots")
                coarse = make_coarse_segments_from_placements(texts, placement)
            elif placement and len(placement) != len(texts):
                # Count mismatch — zip to shortest to avoid index errors,
                # still better than full proportional distribution.
                if DEBUG:
                    print(f"[WARN] placement count ({len(placement)}) != texts count ({len(texts)}) "
                          f"— zipping to shortest, some segments may be skipped")
                coarse = make_coarse_segments_from_placements(
                    texts[:len(placement)], placement[:len(texts)]
                )
            elif is_zh_lang(lang):
                if DEBUG: print("[WARN] no placement data — falling back to linewise distribution")
                coarse = make_coarse_segments_linewise(texts, audio_dur, lang=lang)
            else:
                if DEBUG: print("[WARN] no placement data — falling back to proportional distribution")
                coarse = make_coarse_segments(texts, audio_dur, lang=lang)
            if not coarse: raise RuntimeError("Empty texts -> no coarse segments")

            segments, word_segments = coarse, None
            if allow_align:
                ensure_align_model(align_lang)
                with _WHISPERX_LOCK: align_model, align_meta = _WHISPERX["align_model"], _WHISPERX["metadata"]
                audio_data = whisperx.load_audio(audio)
                aligned    = whisperx.align(coarse, align_model, align_meta, audio_data, device="cpu", return_char_alignments=False)
                aligned_segments, word_segments = aligned.get("segments") or [], aligned.get("word_segments")
                try: del audio_data, aligned
                except Exception: pass
                if aligned_segments: segments = aligned_segments

            if not segments: raise RuntimeError("Alignment produced no segments")
            _attach_words_if_missing(word_segments, segments)

            # Cap each segment's end time so subtitles disappear when audio stops.
            # seg["end"] after WhisperX may still equal the slot window end (e.g. 15s)
            # if alignment confidence was low. We derive the true end from:
            #   1. Last word with a valid 'end' timestamp (most accurate)
            #   2. Placement end_time as hard ceiling (always applied)
            #   3. Text-length estimate as fallback when no valid word timestamps
            # ── Build placement lookups ───────────────────────────────────────
            # placement_start_map: segment_id → start_time in video timeline.
            # clip_end_map:        seg_idx    → exact moment audio goes silent
            #                                   (placement_start + real WAV dur).
            # These are built first so seg["end"] can be set correctly before
            # render_limit is computed — render_limit must reflect real speech
            # end times, not WhisperX slot boundaries.
            zh_mode_lang = is_zh_lang(lang)
            SUB_END_PAD  = 0.15  # hold after last word for EN

            placement_start_map: Dict[str, float] = {}
            if placement:
                for p in placement:
                    sid = _get_seg_id(p)
                    if sid:
                        try: placement_start_map[sid] = float(p.get("start_time") or 0)
                        except Exception: pass

            # Build a timeline map: for each placement slot that has audio,
            # record (start_time, end_time) where end_time = start + real WAV dur.
            # Keyed by start_time so we can match against WhisperX seg["start"]
            # regardless of how WhisperX merges/splits segments.
            # Structure: sorted list of (slot_start, slot_end, actual_clip_end)
            placement_slots: List[Tuple[float, float, float]] = []
            if clip_durations and placement:
                for p_idx, p in enumerate(placement):
                    if not (texts[p_idx] if p_idx < len(texts) else "").strip():
                        continue
                    sid = _get_seg_id(p)
                    if sid and sid in clip_durations:
                        slot_start = placement_start_map.get(sid, 0.0)
                        slot_end   = float(p.get("end_time") or slot_start)
                        clip_end   = slot_start + clip_durations[sid]
                        placement_slots.append((slot_start, slot_end, clip_end))
            placement_slots.sort(key=lambda x: x[0])

            def find_actual_clip_end(seg_start: float, seg_end: float) -> Optional[float]:
                """
                Find actual_clip_end for a WhisperX segment via time-overlap.
                WhisperX may merge/split segments so index-based lookup fails.
                Strategy:
                  1. Exact: slot window contains seg_start
                  2. Overlap: any slot overlaps [seg_start, seg_end]
                  3. Nearest: closest slot by distance to seg_start
                Returns the clip_end of the best matching slot.
                """
                if not placement_slots:
                    return None
                # 1. Exact: slot contains seg_start
                for slot_start, slot_end, clip_end in placement_slots:
                    if slot_start <= seg_start < slot_end:
                        return clip_end
                # 2. Overlap: slot overlaps [seg_start, seg_end]
                for slot_start, slot_end, clip_end in placement_slots:
                    if slot_start < seg_end and slot_end > seg_start:
                        return clip_end
                # 3. Nearest by distance to seg_start
                best_clip_end: Optional[float] = None
                best_dist = float("inf")
                for slot_start, slot_end, clip_end in placement_slots:
                    dist = min(abs(seg_start - slot_start), abs(seg_start - slot_end))
                    if dist < best_dist:
                        best_dist = dist
                        best_clip_end = clip_end
                return best_clip_end

            # ── Set seg["end"] = authoritative subtitle end for each segment ──
            # Hard rule for ALL personas:
            #   The last subtitle word/char MUST have visual effect and the
            #   subtitle MUST disappear immediately after.
            #
            #   actual_clip_end = placement_start + real WAV duration = exact
            #   moment audio goes silent. This is always the hard ceiling.
            #
            #   ZH: use actual_clip_end directly (WhisperX ends too early).
            #   EN: use actual_clip_end directly too — this IS when audio ends.
            #       WhisperX last_we is used only as a floor (subtitle shows
            #       at least until last spoken word), never as the ceiling.
            for seg_idx, seg in enumerate(segments):
                seg_start = float(seg.get("start") or 0)
                seg_end_raw = float(seg.get("end") or seg_start)
                actual_clip_end = find_actual_clip_end(seg_start, seg_end_raw)

                # Find last valid WhisperX word end timestamp (floor for EN)
                last_we = None
                for w in reversed(seg.get("words") or []):
                    if not isinstance(w, dict): continue
                    try:
                        v = float(w.get("end") or w.get("we") or 0)
                        if v > 0: last_we = v; break
                    except Exception: pass

                if actual_clip_end is not None:
                    if zh_mode_lang:
                        # ZH: actual_clip_end is authoritative — WhisperX ends
                        # too early so we hold until the WAV file goes silent.
                        seg["end"] = actual_clip_end
                    else:
                        # EN: WhisperX word timestamps are reliable. Use last
                        # word end + pad as the subtitle end, but cap at
                        # actual_clip_end so we never bleed into TTS silence.
                        whisperx_end = (last_we + SUB_END_PAD) if last_we else actual_clip_end
                        seg["end"] = min(whisperx_end, actual_clip_end)
                elif last_we:
                    seg["end"] = last_we + SUB_END_PAD
                else:
                    raw_text = (seg.get("text") or "").strip()
                    zh = is_cjk(raw_text)
                    n = len([c for c in raw_text if not c.isspace()]) if zh else len(raw_text.split())
                    seg["end"] = seg_start + (n / (4.5 if zh else 3.0)) + 0.3

            # ── Compute render_limit from finalised seg["end"] values ─────────
            word_pop_ready = has_word_level_timings(segments)
            render_limit   = compute_subtitle_render_limit(segments, audio_dur)
            caption_end    = compute_last_caption_end(segments, render_limit=render_limit, lang=lang) if word_pop_ready else None

            # ── sub_render_until: latest point any subtitle Dialogue line ends ─
            if placement_slots:
                if zh_mode_lang:
                    # ZH: render until last clip ends (actual WAV end).
                    sub_render_until = max(s[2] for s in placement_slots) + 0.05
                else:
                    # EN: use corrected seg ends (word-derived, capped to clip end)
                    # not raw clip end which includes TTS trailing silence.
                    seg_ends = [float(s.get("end", 0)) for s in segments if s.get("end")]
                    sub_render_until = (max(seg_ends) + 0.05) if seg_ends else render_limit
            elif caption_end is not None and word_pop_ready:
                sub_render_until = caption_end
            else:
                sub_render_until = render_limit

            if DEBUG:
                print(f"[SUB] zh={zh_mode_lang} word_pop={word_pop_ready} "
                      f"render_limit={render_limit:.3f} sub_render_until={sub_render_until:.3f} "
                      f"audio_dur={audio_dur:.3f}")
                for i, s in enumerate(segments):
                    wds = s.get("words") or []
                    lwe = None
                    for w in reversed(wds):
                        if isinstance(w, dict):
                            try:
                                v = float(w.get("end") or 0)
                                if v > 0: lwe = v; break
                            except Exception: pass
                    ace = find_actual_clip_end(
                        float(s.get("start") or 0), float(s.get("end") or 0))
                    print(f"[SUB]   seg[{i}] start={s.get('start'):.2f} "
                          f"end={s.get('end'):.2f} actual_clip_end={ace} "
                          f"words={len(wds)} last_we={lwe}")

            with open(ass, "w", encoding="utf-8") as f:
                f.write(build_line_ass_pop(segments=segments, render_until=sub_render_until, play_w=w_disp, play_h=h_disp, persona_id=pid, lang=lang)
                        if word_pop_ready else
                        build_line_ass_linewise(segments=segments, timeline_duration=sub_render_until, font_name=font_name, play_w=w_disp, play_h=h_disp, lang=lang))

            vf = build_subtitles_filter(ass, font_name=font_name)
            run([FFMPEG_BIN, "-y", "-i", burn_source, "-vf", vf, "-af", "aresample=async=1",
                 "-map", "0:v:0", "-map", "0:a:0", "-muxpreload", "0", "-muxdelay", "0",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out])

            with _LOCK:
                SUBTITLE_JOBS[job_id].update({
                    "status": JobStatus.done, "output_url": f"{base_url}/merged/{job_id}_sub.mp4",
                    "ass_url": f"{base_url}/merged/{job_id}.ass",
                    "sub_effect": SUB_EFFECT if word_pop_ready else "line_fallback",
                    "render_limit": round(render_limit, 3), "subtitle_timeline": round(render_limit, 3),
                    "sub_render_until": round(sub_render_until, 3),
                    "visual_video_duration": round(visual_video_dur, 3), "audio_duration": round(audio_dur, 3),
                    "caption_end": round(caption_end, 3) if caption_end is not None else None,
                    "persona_id": pid, "subtitle_lang": lang, "font_name": font_name,
                    "fonts_dir": FONTS_DIR, "align_lang": align_lang, "aligned": bool(allow_align), "word_pop_ready": bool(word_pop_ready),
                })
        except Exception as e:
            with _LOCK: SUBTITLE_JOBS[job_id]["status"] = JobStatus.error; SUBTITLE_JOBS[job_id]["error"] = str(e)
        finally:
            safe_remove(video); safe_remove(audio); safe_remove(norm_video)
            if os.environ.get("KEEP_ASS", "1").strip().lower() not in ("1", "true", "yes", "y"): safe_remove(ass)


# --- Merge endpoint ---

@app.post("/merge")
def merge(
    video_url: str = Form(...), placement_map_json: str = Form(...), segment_audios_json: str = Form(...),
    texts_json: Optional[str] = Form(None), choice: Optional[str] = Form(None),
    persona_id: Optional[str] = Form(None), subtitle_lang: Optional[str] = Form(None), request: Request = None,
):
    merge_id = str(uuid.uuid4())
    video    = f"/tmp/{merge_id}.mp4"
    final    = os.path.join(MERGED_DIR, f"{merge_id}.mp4")
    tmp_files: List[str] = [video]
    try:
        cleanup_old_jobs()
        download_file(video_url, video)
        try: placement = json.loads(placement_map_json); audios = json.loads(segment_audios_json)
        except Exception: raise HTTPException(400, "placement_map_json / segment_audios_json not valid JSON")
        if not isinstance(placement, list) or not isinstance(audios, list):
            raise HTTPException(400, "placement_map_json and segment_audios_json must be JSON arrays")

        # Normalise placement elements — llm_output_to_text.py emits each element
        # as a JSON-encoded string (json.dumps per item) rather than a plain dict.
        # Parse any string elements so we always work with List[Dict].
        normalised = []
        for item in placement:
            if isinstance(item, str):
                try: item = json.loads(item)
                except Exception: pass
            if isinstance(item, dict):
                normalised.append(item)
        placement = normalised
        for i, seg in enumerate(placement):
            if not isinstance(seg, dict): raise HTTPException(400, f"placement_map_json[{i}] is not an object")
            if _get_seg_id(seg) is None: raise HTTPException(400, f"placement_map_json[{i}] missing segment_id")

        audio_map: Dict[str, str] = {
            _get_seg_id(a): _get_audio_url(a)
            for a in audios
            if isinstance(a, dict) and _get_seg_id(a) and _get_audio_url(a)
        }
        placement_ids = [_get_seg_id(s) for s in placement if isinstance(s, dict) and _get_seg_id(s)]
        off_by_one = _detect_off_by_one(placement_ids, list(audio_map.keys()))
        if off_by_one: raise HTTPException(status_code=400, detail=off_by_one)
        missing = [sid for sid in placement_ids if sid not in audio_map]
        if missing: raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_audio_for_segments",
                "missing_segment_ids": missing,
                "hint": "segment_audios_json must contain {segment_id, audio_url} for every segment_id in placement_map_json",
            },
        )

        video_dur  = probe_video_duration(video)
        master_wav, clip_durations = build_timed_audio_track(
            placements=placement,
            audio_map=audio_map,
            merge_id=merge_id,
            total_duration=video_dur,
            tmp_files=tmp_files,
        )
        run([
            FFMPEG_BIN, "-y",
            "-i", video, "-i", master_wav,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-af", "aresample=async=1",
            "-c:a", "aac", "-b:a", "192k",
            "-muxdelay", "0", "-muxpreload", "0",
            "-movflags", "+faststart",
            final,
        ])

        base = str(request.base_url).rstrip("/") if request else ""
        merged_output_url = f"{base}/merged/{merge_id}.mp4"
        subtitle_job_id = subtitles_status_url = subtitles_wait_url = ""
        effective_persona_id = persona_id or choice
        if texts_json is not None:
            texts = parse_texts_payload(texts_json, persona_id=effective_persona_id, lang=subtitle_lang)
            subtitle_job_id = str(uuid.uuid4())
            with _LOCK:
                SUBTITLE_JOBS[subtitle_job_id] = {
                    "status": JobStatus.pending,
                    "output_url": None,
                    "ass_url": None,
                    "error": None,
                    "created_at": time.time(),
                }
            threading.Thread(
                target=run_subtitle_job,
                args=(subtitle_job_id, merged_output_url, texts, base, effective_persona_id, subtitle_lang),
                kwargs={"placement": placement, "clip_durations": clip_durations},
                daemon=True,
            ).start()
            subtitles_status_url = f"{base}/subtitles/{subtitle_job_id}"
            subtitles_wait_url   = f"{base}/subtitles/{subtitle_job_id}/wait"
        return {
            "output_url": merged_output_url,
            "subtitle_job_id": subtitle_job_id,
            "subtitles_status_url": subtitles_status_url,
            "subtitles_wait_url": subtitles_wait_url,
        }
    finally:
        for p in tmp_files: safe_remove(p)


# --- Subtitle endpoints ---

@app.post("/subtitles")
def create_subtitles(
    video_url: str = Form(...), texts_json: str = Form(...), choice: Optional[str] = Form(None),
    persona_id: Optional[str] = Form(None), subtitle_lang: Optional[str] = Form(None), request: Request = None,
):
    cleanup_old_jobs()
    job_id = str(uuid.uuid4())
    base   = str(request.base_url).rstrip("/") if request else ""
    texts  = parse_texts_payload(texts_json, persona_id=persona_id or choice, lang=subtitle_lang)
    with _LOCK: SUBTITLE_JOBS[job_id] = {"status": JobStatus.pending, "output_url": None, "ass_url": None, "error": None, "created_at": time.time()}
    threading.Thread(target=run_subtitle_job, args=(job_id, video_url, texts, base, persona_id or choice, subtitle_lang), daemon=True).start()
    return {"job_id": job_id, "status": JobStatus.pending, "status_url": f"{base}/subtitles/{job_id}", "wait_url": f"{base}/subtitles/{job_id}/wait"}

@app.get("/subtitles/{job_id}/ass")
def subtitle_ass(job_id: str):
    """Return the raw ASS subtitle file for debugging subtitle timing."""
    ass_path = os.path.join(MERGED_DIR, f"{job_id}.ass")
    if not os.path.exists(ass_path):
        raise HTTPException(404, "ASS file not found — job may still be running or KEEP_ASS=0")
    with open(ass_path, encoding="utf-8") as f:
        content = f.read()
    return {"job_id": job_id, "ass_content": content}

@app.get("/subtitles/{job_id}")
def subtitle_status(job_id: str):
    cleanup_old_jobs()
    with _LOCK: job = SUBTITLE_JOBS.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    return job

@app.get("/subtitles/{job_id}/wait")
def subtitle_wait(job_id: str, timeout: float = 290.0, interval: float = 0.8):
    timeout = max(1.0, min(float(timeout), 600.0)); interval = max(0.2, min(float(interval), 10.0))
    cleanup_old_jobs()
    with _LOCK: job = SUBTITLE_JOBS.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    deadline = time.monotonic() + timeout
    while True:
        with _LOCK: job = SUBTITLE_JOBS.get(job_id)
        if not job: raise HTTPException(404, "Job not found")
        if job.get("status") in (JobStatus.done, JobStatus.error, "done", "error"): return job
        if time.monotonic() >= deadline: return {**job, "timed_out": True, "wait_timeout": timeout}
        time.sleep(interval)


def _perform_tts_quality_check(
    audio_url: str,
    segment_id: str,
    expected_text: str,
    language: str = "zh",
    retry_count: int = 0,
    enable_direct_retry: bool = True,
    tts_endpoint: str = "http://ultrongw.woa.com/v2/tts/cyber-human/api/get_tts/sound.wav"
) -> Dict[str, Any]:
    """
    执行TTS质量检查，验证音频文件的发音质量
    支持直接HTTP重试机制，不依赖Dify工作流
    
    Args:
        audio_url: 音频文件URL
        segment_id: 片段ID
        expected_text: 预期文本内容
        language: 语言设置
        retry_count: 当前重试次数
        enable_direct_retry: 是否启用直接HTTP重试
        tts_endpoint: TTS服务端点URL
    
    Returns:
        质量检查结果字典，包含重试建议
    """
    
    # 默认质量阈值配置
    QUALITY_CONFIG = {
        "quality_threshold": 0.8,
        "asr_similarity_threshold": 0.7,
        "min_audio_duration": 0.5,
        "max_audio_duration": 10.0,
        "max_retries": 3,
        "tts_endpoint": tts_endpoint
    }
    
    result = {
        "segment_id": segment_id,
        "passed": False,
        "audio_url": audio_url,
        "expected_text": expected_text,
        "language": language,
        "retry_count": retry_count,
        "audio_duration": 0.0,
        "similarity_score": 0.0,
        "asr_text": "",
        "error": "",
        "checks": {},
        "direct_retry_available": enable_direct_retry,
        "tts_endpoint": tts_endpoint,
        "retry_suggestion": ""
    }
    
    try:
        # 检查1: 音频文件可访问性
        accessibility_check = _check_audio_accessibility(audio_url)
        result["checks"]["accessibility"] = accessibility_check
        
        if not accessibility_check["passed"]:
            result["error"] = f"音频文件不可访问: {accessibility_check['error']}"
            return result
        
        # 检查2: 下载音频文件并计算时长
        audio_data = download_file(audio_url, return_content=True)
        if not audio_data:
            result["error"] = "音频文件下载失败"
            return result
        
        # 保存到临时文件进行时长计算
        temp_file = f"/tmp/quality_check_{segment_id}_{uuid.uuid4().hex[:8]}.wav"
        with open(temp_file, "wb") as f:
            f.write(audio_data)
        
        # 计算音频时长
        audio_duration = probe_duration(temp_file)
        result["audio_duration"] = audio_duration
        
        # 检查3: 音频时长验证
        duration_check = _check_audio_duration(audio_duration, QUALITY_CONFIG)
        result["checks"]["duration"] = duration_check
        
        if not duration_check["passed"]:
            result["error"] = f"音频时长异常: {duration_check['error']}"
            os.unlink(temp_file)
            return result
        
        # 检查4: 音频格式验证
        format_check = _check_audio_format(temp_file)
        result["checks"]["format"] = format_check
        
        if not format_check["passed"]:
            result["error"] = f"音频格式异常: {format_check['error']}"
            os.unlink(temp_file)
            return result
        
        # 检查5: ASR发音准确性检查（核心功能）
        if expected_text and expected_text.strip():
            asr_check = _check_audio_pronunciation(temp_file, expected_text, language, QUALITY_CONFIG)
            result["checks"]["asr"] = asr_check
            result["asr_text"] = asr_check.get("asr_text", "")
            result["similarity_score"] = asr_check.get("similarity", 0.0)
        else:
            # 如果没有预期文本，跳过ASR检查
            asr_check = {"passed": True, "similarity": 1.0, "asr_text": "无预期文本，跳过ASR检查"}
            result["checks"]["asr"] = asr_check
            result["similarity_score"] = 1.0
        
        # 计算综合质量分数
        base_score = 1.0
        penalty = 0.0
        
        # 根据基础检查错误类型扣分
        if duration_check.get("warning", False):
            penalty += 0.1
        
        # 根据ASR相似度调整分数
        if expected_text and expected_text.strip():
            asr_similarity = result["similarity_score"]
            if asr_similarity < QUALITY_CONFIG["asr_similarity_threshold"]:
                penalty += (QUALITY_CONFIG["asr_similarity_threshold"] - asr_similarity)
        
        quality_score = max(0.0, base_score - penalty)
        result["quality_score"] = quality_score
        result["passed"] = quality_score >= QUALITY_CONFIG["quality_threshold"]
        
        # 清理临时文件
        os.unlink(temp_file)
        
        # 如果质量检查失败且启用了直接重试，生成重试建议
        if not result["passed"] and enable_direct_retry and retry_count < QUALITY_CONFIG["max_retries"]:
            result["retry_suggestion"] = _generate_retry_suggestion(result, QUALITY_CONFIG)
        
    except Exception as e:
        result["error"] = f"质量检查异常: {str(e)}"
        result["passed"] = False
        
        # 即使异常也生成重试建议
        if enable_direct_retry and retry_count < QUALITY_CONFIG["max_retries"]:
            result["retry_suggestion"] = _generate_retry_suggestion(result, QUALITY_CONFIG)
    
    return result


def _check_audio_accessibility(audio_url: str) -> Dict[str, Any]:
    """检查音频文件可访问性"""
    try:
        if not audio_url:
            return {"passed": False, "error": "音频URL为空"}
        
        # 发送HEAD请求检查文件可访问性
        response = requests.head(audio_url, timeout=10)
        if response.status_code != 200:
            return {"passed": False, "error": f"HTTP状态码: {response.status_code}"}
        
        return {"passed": True, "status_code": response.status_code}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _generate_retry_suggestion(quality_result: Dict[str, Any], config: Dict) -> str:
    """生成TTS重试建议"""
    if not quality_result.get("direct_retry_available", False):
        return "直接重试功能未启用"
    
    retry_count = quality_result.get("retry_count", 0)
    max_retries = config.get("max_retries", 3)
    
    if retry_count >= max_retries:
        return f"已达到最大重试次数 ({max_retries})"
    
    error_type = ""
    if "duration" in quality_result.get("checks", {}) and not quality_result["checks"]["duration"]["passed"]:
        error_type = "duration"
    elif "asr" in quality_result.get("checks", {}) and not quality_result["checks"]["asr"]["passed"]:
        error_type = "pronunciation"
    else:
        error_type = "general"
    
    suggestions = {
        "duration": "音频时长异常，建议调整TTS参数重新生成",
        "pronunciation": "发音准确性不足，建议重新生成TTS音频",
        "general": "音频质量检查失败，建议重新生成TTS"
    }
    
    return f"建议直接重试: {suggestions.get(error_type, '重新生成TTS音频')}"


def _request_tts_directly(text: str, endpoint: str, language: str = "zh") -> Dict[str, Any]:
    """
    直接向TTS端点发送HTTP请求，不依赖Dify工作流
    
    Args:
        text: 要转换为语音的文本
        endpoint: TTS服务端点URL
        language: 语言设置
    
    Returns:
        包含音频URL和状态信息的字典
    """
    try:
        # 构建请求参数
        params = {
            "text": text,
            "language": language,
            "format": "wav"
        }
        
        # 发送HTTP POST请求
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TTS-Quality-Check/1.0"
        }
        
        if DEBUG:
            print(f"[TTS直接请求] 发送请求到: {endpoint}")
            print(f"[TTS直接请求] 参数: {params}")
        
        response = requests.post(
            endpoint,
            json=params,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            # 解析响应，获取音频URL
            response_data = response.json()
            
            if DEBUG:
                print(f"[TTS直接请求] 响应: {response_data}")
            
            # 根据实际API响应结构调整
            audio_url = response_data.get("audio_url") or response_data.get("url") or response_data.get("file_url")
            
            if audio_url:
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "response_data": response_data,
                    "message": "TTS生成成功"
                }
            else:
                return {
                    "success": False,
                    "error": "响应中未找到音频URL",
                    "response_data": response_data
                }
        else:
            return {
                "success": False,
                "error": f"HTTP错误: {response.status_code}",
                "status_code": response.status_code,
                "response_text": response.text[:500]  # 限制错误信息长度
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"TTS请求异常: {str(e)}"
        }


def _perform_direct_tts_retry(
    segment_id: str,
    expected_text: str,
    language: str = "zh",
    tts_endpoint: str = "http://ultrongw.woa.com/v2/tts/cyber-human/api/get_tts/sound.wav",
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    执行直接TTS重试，不依赖Dify工作流
    
    Args:
        segment_id: 片段ID
        expected_text: 预期文本
        language: 语言设置
        tts_endpoint: TTS服务端点
        max_retries: 最大重试次数
    
    Returns:
        重试结果字典
    """
    
    result = {
        "segment_id": segment_id,
        "retry_success": False,
        "new_audio_url": "",
        "retry_count": 0,
        "errors": [],
        "quality_check_result": None
    }
    
    # 尝试多次重试
    for attempt in range(max_retries):
        result["retry_count"] = attempt + 1
        
        if DEBUG:
            print(f"[TTS直接重试] 第{attempt + 1}次重试 - 文本: {expected_text}")
        
        # 直接请求TTS服务
        tts_response = _request_tts_directly(expected_text, tts_endpoint, language)
        
        if not tts_response["success"]:
            result["errors"].append(f"重试{attempt + 1}: {tts_response.get('error', '未知错误')}")
            continue
        
        # 获取新的音频URL
        new_audio_url = tts_response["audio_url"]
        result["new_audio_url"] = new_audio_url
        
        # 对新生成的音频进行质量检查
        quality_check = _perform_tts_quality_check(
            audio_url=new_audio_url,
            segment_id=segment_id,
            expected_text=expected_text,
            language=language,
            retry_count=attempt + 1,
            enable_direct_retry=False,  # 避免无限递归
            tts_endpoint=tts_endpoint
        )
        
        result["quality_check_result"] = quality_check
        
        if quality_check["passed"]:
            result["retry_success"] = True
            if DEBUG:
                print(f"[TTS直接重试] 第{attempt + 1}次重试成功")
            break
        else:
            result["errors"].append(f"重试{attempt + 1}: 质量检查失败 - {quality_check.get('error', '未知错误')}")
    
    return result


def _check_audio_duration(audio_duration: float, config: Dict) -> Dict[str, Any]:
    """检查音频时长"""
    try:
        if audio_duration <= 0:
            return {"passed": False, "error": "音频时长为0"}
        
        if audio_duration < config["min_audio_duration"]:
            return {"passed": False, "error": f"音频时长过短: {audio_duration:.2f}s"}
        
        if audio_duration > config["max_audio_duration"]:
            return {"passed": True, "warning": f"音频时长过长: {audio_duration:.2f}s"}
        
        return {"passed": True, "duration": audio_duration}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _check_audio_format(audio_file_path: str) -> Dict[str, Any]:
    """检查音频格式"""
    try:
        # 使用ffprobe检查音频格式
        result = subprocess.run([
            FFPROBE_BIN, "-v", "quiet",
            "-show_format", "-show_streams",
            audio_file_path
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"passed": False, "error": "无法解析音频文件格式"}
        
        # 检查是否为支持的音频格式
        output = result.stdout
        if "codec_name=pcm_s16le" not in output:
            return {"passed": False, "error": "不支持的音频编码格式"}
        
        if "sample_rate=16000" not in output:
            return {"passed": False, "error": "不支持的采样率"}
        
        return {"passed": True, "format": "WAV 16kHz mono"}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _check_audio_pronunciation(audio_file_path: str, expected_text: str, language: str, config: Dict) -> Dict[str, Any]:
    """使用ASR检查音频发音准确性"""
    
    result = {"passed": False, "similarity": 0.0, "asr_text": "", "error": ""}
    
    try:
        # 使用WhisperX进行语音识别
        if WHISPERX_AVAILABLE:
            asr_result = _whisperx_asr_service(audio_file_path, language)
        else:
            # 如果WhisperX不可用，使用模拟服务
            asr_result = _mock_asr_service(audio_file_path, language)
        
        if not asr_result["success"]:
            result["error"] = f"ASR识别失败: {asr_result.get('error', '未知错误')}"
            return result
        
        recognized_text = asr_result["text"]
        confidence = asr_result.get("confidence", 0.0)
        
        # 计算文本相似度
        similarity = _calculate_text_similarity(expected_text, recognized_text, language)
        
        result["asr_text"] = recognized_text
        result["similarity"] = similarity
        result["confidence"] = confidence
        result["passed"] = similarity >= config.get("asr_similarity_threshold", 0.7)
        
    except Exception as e:
        result["error"] = f"ASR检查异常: {str(e)}"
    
    return result


def _whisperx_asr_service(audio_file_path: str, language: str) -> Dict[str, Any]:
    """使用WhisperX进行语音识别"""
    
    result = {"success": False, "text": "", "confidence": 0.0}
    
    try:
        if not WHISPERX_AVAILABLE:
            result["error"] = "WhisperX未安装"
            return result
        
        # 加载WhisperX模型
        device = "cpu"
        batch_size = 16
        model_size = "base"
        
        model = whisperx.load_model(model_size, device, compute_type="int8")
        
        # 音频识别
        audio = whisperx.load_audio(audio_file_path)
        result_whisper = model.transcribe(audio, batch_size=batch_size)
        
        # 获取识别文本
        if result_whisper["segments"]:
            recognized_text = " ".join([segment["text"].strip() for segment in result_whisper["segments"]])
            
            # 计算平均置信度
            confidences = [segment.get("avg_logprob", 0.5) for segment in result_whisper["segments"]]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
            confidence = min(1.0, max(0.0, (avg_confidence + 1.0) / 2.0))
            
            result["success"] = True
            result["text"] = recognized_text
            result["confidence"] = confidence
        else:
            result["error"] = "WhisperX未识别到任何文本"
                
    except Exception as e:
        result["error"] = f"WhisperX识别失败: {str(e)}"
    
    return result


def _mock_asr_service(audio_file_path: str, language: str) -> Dict[str, Any]:
    """模拟ASR服务，用于测试和演示"""
    
    # 模拟处理时间
    import time
    time.sleep(0.1)
    
    # 返回模拟结果
    return {
        "success": True,
        "text": "模拟识别结果",
        "confidence": 0.85
    }


def _calculate_text_similarity(text1: str, text2: str, language: str) -> float:
    """计算两个文本的相似度"""
    
    if not text1 or not text2:
        return 0.0
    
    # 转换为小写并去除标点符号
    import re
    text1_clean = re.sub(r'[^\w\s]', '', text1.lower())
    text2_clean = re.sub(r'[^\w\s]', '', text2.lower())
    
    # 分词（针对中文）
    if language == "zh":
        # 简单的中文分词（按字符分割）
        words1 = list(text1_clean)
        words2 = list(text2_clean)
    else:
        # 英文按空格分词
        words1 = text1_clean.split()
        words2 = text2_clean.split()
    
    # 计算Jaccard相似度
    set1 = set(words1)
    set2 = set(words2)
    
    if not set1 and not set2:
        return 1.0
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    similarity = intersection / union if union > 0 else 0.0
    
    return similarity
