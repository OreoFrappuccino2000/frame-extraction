import json


def main(validated_vlm_output, total_duration, rate_type=None, target_rate=None, language=None, persona=None):
    import math
    import re as _re
    from collections import Counter

    # ------------------------------------------------------------------
    # STEP 1 — Extract validated data from VLM output
    # ------------------------------------------------------------------
    def extract_validated_data(vlm_output):
        """提取验证后的VLM数据"""
        try:
            if isinstance(vlm_output, str):
                vlm_output = json.loads(vlm_output)
            
            # 提取验证后的事件列表
            events = vlm_output.get("events", [])
            
            # 提取意图分析结果
            intent_analysis = vlm_output.get("intent_analysis", {})
            
            # 提取验证日志
            validation_log = vlm_output.get("validation_log", {})
            
            # 提取时间戳校正信息
            drift_log = vlm_output.get("drift_log", [])
            
            return {
                "events": events,
                "intent_analysis": intent_analysis,
                "validation_log": validation_log,
                "drift_log": drift_log
            }
        except Exception as e:
            print(f"Warning: Failed to extract validated data: {e}")
            # 回退到原始事件提取
            return {
                "events": extract_event_list_fallback(vlm_output),
                "intent_analysis": {},
                "validation_log": {},
                "drift_log": []
            }

    def extract_event_list_fallback(obj):
        """回退的事件提取方法"""
        try:
            parsed = json.loads(obj) if isinstance(obj, str) else obj
        except Exception:
            return []
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "events" in parsed:
            return parsed["events"]
        return []

    # ------------------------------------------------------------------
    # STEP 2 — Normalise persona
    # ------------------------------------------------------------------
    _raw = str(persona or "").strip().upper()
    _match = _re.search(r'[_\s-]([ABCD])$', _raw) or _re.match(r'^([ABCD])$', _raw)
    if _match:
        persona = _match.group(1)
    elif _raw.endswith("A"):
        persona = "A"
    elif _raw.endswith("B"):
        persona = "B"
    elif _raw.endswith("C"):
        persona = "C"
    elif _raw.endswith("D"):
        persona = "D"
    else:
        persona = None

    # ------------------------------------------------------------------
    # STEP 3 — Infer persona from language / rate_type
    # ------------------------------------------------------------------
    if persona is None:
        _lang = (language or "").strip().lower()
        _rate = (rate_type or "").strip().lower()
        # Language takes priority over rate_type — rate_type alone is ambiguous
        # because persona node outputs "wps"/"cps" which is a consequence of
        # persona, not a reliable signal to infer it from when persona is missing.
        _is_chinese = _lang in ("zh", "zh-cn", "zh_cn", "chinese", "mandarin", "cn") or _rate == "cps"
        _is_english = _lang in ("en", "english", "en-us", "en-gb", "en_us", "en_gb") or _rate == "wps"
        if _is_chinese:
            persona = "C"
        elif _is_english:
            persona = "A"
        else:
            persona = "C"  # default fallback

    # ------------------------------------------------------------------
    # RATE CONFIG
    # ------------------------------------------------------------------
    WPS_PERSONA_A = 2.5
    WPS_PERSONA_B = 2.5
    CPS_CHINESE   = 3.8

    SAFETY_MARGIN = 0.80

    REAL_TTS_RATE_EN = 3.0
    REAL_TTS_RATE_ZH = 4.5
    FILL_TARGET      = 0.80
    ABS_MAX_UNITS    = 30

    MIN_EVENT_UNITS = 3
    MIN_UNITS_SLOT_THRESH = 0.8

    if persona in ["A", "B"]:
        budget_unit_type  = "words"
        rate_type_used    = "wps"
        conservative_rate = WPS_PERSONA_A if persona == "A" else WPS_PERSONA_B
        tts_real_rate     = REAL_TTS_RATE_EN
    else:
        budget_unit_type  = "chars"
        rate_type_used    = "cps"
        conservative_rate = CPS_CHINESE
        tts_real_rate     = REAL_TTS_RATE_ZH

    target_rate_used = float(target_rate) if target_rate else conservative_rate

    # ------------------------------------------------------------------
    # CONSTANTS
    # ------------------------------------------------------------------
    MIN_DURATION_TO_SPEAK = 0.35

    MIN_ZH_FILLER_DUR = 3.0
    MIN_EN_FILLER_DUR = MIN_DURATION_TO_SPEAK

    is_zh_persona = persona in ("C", "D")
    min_filler_dur = MIN_ZH_FILLER_DUR if is_zh_persona else MIN_EN_FILLER_DUR

    # FIX 1: Raised intro cap from 2.0 → 3.0s and ratio from 0.15 → 0.20
    # so the LLM has enough budget to write a meaningful hook line
    # (e.g. "FNC scOutOP going for the triple — watch this!" instead of just "Watch out!")
    RAW_INTRO_RATIO = 0.20   # was 0.15
    RAW_INTRO_CAP   = 3.0   # was 2.0

    # FIX 2: Forced outro — always carve out the last OUTRO_MIN_DUR seconds
    # as an outro_punchlines slot, regardless of whether a filler exists.
    # This guarantees the LLM always has a closing line slot.
    OUTRO_MIN_DUR = 2.5   # minimum outro slot duration in seconds
    OUTRO_MAX_DUR = 4.0   # cap outro so it doesn't eat too much of short videos

    total_dur = max(0.0, float(total_duration or 0))

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _dynamic_cap(dur: float) -> int:
        return min(int(math.floor(dur * tts_real_rate * FILL_TARGET)), ABS_MAX_UNITS)

    def units_for_duration(dur: float) -> int:
        if dur < min_filler_dur:
            return 0
        raw = int(math.floor(dur * conservative_rate * SAFETY_MARGIN))
        return max(0, min(raw, _dynamic_cap(dur)))

    def units_for_event_slot(dur: float) -> int:
        if dur < MIN_DURATION_TO_SPEAK:
            return 0
        raw = int(math.floor(dur * conservative_rate * SAFETY_MARGIN))
        cap = _dynamic_cap(dur)
        if dur >= MIN_UNITS_SLOT_THRESH:
            return max(MIN_EVENT_UNITS, min(raw, cap))
        return max(0, min(raw, cap))

    def estimated_tts_duration(max_units: int) -> float:
        if max_units <= 0:
            return 0.0
        return round(max_units / tts_real_rate, 3)

    # ------------------------------------------------------------------
    # STEP 4 — Extract and process validated VLM data
    # ------------------------------------------------------------------
    validated_data = extract_validated_data(validated_vlm_output)
    event_list = sorted(validated_data["events"], key=lambda x: x.get("video_time", 0))
    intent_analysis = validated_data["intent_analysis"]
    validation_log = validated_data["validation_log"]
    drift_log = validated_data["drift_log"]

    # ------------------------------------------------------------------
    # PASS 1 — build raw slots
    # ------------------------------------------------------------------
    raw_slots = []

    intro_end_raw = min(RAW_INTRO_CAP, total_dur * RAW_INTRO_RATIO) if total_dur else RAW_INTRO_CAP
    raw_slots.append({
        "_type": "intro_hooks", "start": 0.0, "end": intro_end_raw,
        "event_type": "intro_hooks", "vocal_mode": "intro",
    })
    prev_end = intro_end_raw

    # FIX 2: Pre-compute where the forced outro must start.
    # All event slots must end before this boundary.
    outro_dur_target = min(OUTRO_MAX_DUR, max(OUTRO_MIN_DUR, total_dur * 0.15))
    outro_boundary   = max(intro_end_raw + 1.0, total_dur - outro_dur_target)

    for e in event_list:
        # Use validated video_time from VLM output
        video_time = float(e.get("video_time", 0))
        etype  = e.get("type", "event")
        conf   = float(e.get("confidence", 1.0))
        k_clamped = max(prev_end, min(video_time, outro_boundary))  # clamp to outro_boundary

        if k_clamped > prev_end + 1e-9:
            raw_slots.append({
                "_type": "global_filler", "start": prev_end, "end": k_clamped,
                "event_type": "global_filler", "vocal_mode": "colour",
            })
            prev_end = k_clamped

        # Event slot also clamped so it never crosses outro_boundary
        event_end_raw = min(max(k_clamped + 0.2, k_clamped + 1.0), outro_boundary)
        if event_end_raw <= prev_end:
            continue

        raw_slots.append({
            "_type": "event", "start": prev_end, "end": event_end_raw,
            "event_type": etype, "confidence": conf, "vocal_mode": "call",
        })
        prev_end = event_end_raw

    # FIX 2: Insert filler between last event and outro_boundary (if any gap),
    # then always append a forced outro_punchlines slot.
    if prev_end < outro_boundary - 1e-9:
        raw_slots.append({
            "_type": "global_filler", "start": prev_end, "end": outro_boundary,
            "event_type": "global_filler", "vocal_mode": "colour",
        })

    # Always append outro — guaranteed slot regardless of what came before
    raw_slots.append({
        "_type": "outro_punchlines", "start": outro_boundary, "end": total_dur,
        "event_type": "outro_punchlines", "vocal_mode": "outro",
    })

    # ------------------------------------------------------------------
    # PASS 2 — snap boundaries to be perfectly contiguous
    # ------------------------------------------------------------------
    if not raw_slots:
        raw_slots.append({
            "_type": "intro_hooks", "start": 0.0, "end": total_dur,
            "event_type": "intro_hooks", "vocal_mode": "intro",
        })

    raw_slots[0]["start"] = 0.0
    for i in range(1, len(raw_slots)):
        raw_slots[i]["start"] = raw_slots[i - 1]["end"]
    raw_slots[-1]["end"] = total_dur

    raw_slots = [s for s in raw_slots if s["end"] - s["start"] > 1e-9]

    if raw_slots:
        raw_slots[0]["start"] = 0.0
        for i in range(1, len(raw_slots)):
            raw_slots[i]["start"] = raw_slots[i - 1]["end"]
        raw_slots[-1]["end"] = total_dur

    # Ensure last slot is always outro (safety net after snap/filter)
    if raw_slots and raw_slots[-1]["_type"] != "outro_punchlines":
        raw_slots[-1]["_type"]      = "outro_punchlines"
        raw_slots[-1]["event_type"] = "outro_punchlines"
        raw_slots[-1]["vocal_mode"] = "outro"

    # ------------------------------------------------------------------
    # PASS 3 — merge consecutive adjacent event slots
    # ------------------------------------------------------------------
    MAX_MERGE_EVENTS = 2

    for slot in raw_slots:
        stype = slot["_type"]
        dur   = slot["end"] - slot["start"]
        if stype in ("event", "intro_hooks", "outro_punchlines"):
            slot["_pre_units"] = units_for_event_slot(dur)
        else:
            slot["_pre_units"] = units_for_duration(dur)

    merged_slots = []
    i = 0
    while i < len(raw_slots):
        slot = raw_slots[i]
        if slot["_type"] != "event":
            merged_slots.append(slot)
            i += 1
            continue

        chain = [slot]
        j = i + 1
        while (
            j < len(raw_slots)
            and raw_slots[j]["_type"] == "event"
            and abs(raw_slots[j]["start"] - chain[-1]["end"]) < 1e-6
            and len(chain) < MAX_MERGE_EVENTS
        ):
            chain.append(raw_slots[j])
            j += 1

        if len(chain) == 1:
            merged_slots.append(slot)
        else:
            merged = {
                "_type":              "event",
                "start":              chain[0]["start"],
                "end":                chain[-1]["end"],
                "event_type":         chain[-1]["event_type"],
                "vocal_mode":         "call",
                "merged_event_types": [s["event_type"] for s in chain],
                "merged_count":       len(chain),
                "_pre_units":         sum(s["_pre_units"] for s in chain),
            }
            if "confidence" in chain[-1]:
                merged["confidence"] = chain[-1]["confidence"]
            merged_slots.append(merged)
        i = j

    raw_slots = merged_slots

    # Re-snap boundaries after merge
    if raw_slots:
        raw_slots[0]["start"] = 0.0
        for k in range(1, len(raw_slots)):
            raw_slots[k]["start"] = raw_slots[k - 1]["end"]
        raw_slots[-1]["end"] = total_dur

    # ------------------------------------------------------------------
    # PASS 4 — emit final segments
    # ------------------------------------------------------------------
    total_slots = len(raw_slots)
    pad_width   = max(2, len(str(total_slots - 1)))

    enhanced_segments = []
    rag_lines         = []

    for idx, slot in enumerate(raw_slots):
        stype = slot["_type"]
        start = round(slot["start"], 6)
        end   = round(slot["end"],   6)
        dur   = round(end - start,   6)

        # event/intro/outro: _pre_units already has MIN_EVENT_UNITS guarantee baked in
        # via units_for_event_slot — do NOT re-apply dynamic cap here or it will
        # silently truncate the minimum (e.g. 1s slot: cap=2 < MIN_EVENT_UNITS=3).
        # filler slots: _pre_units was calculated without a minimum, safe to re-cap.
        if stype in ("event", "intro_hooks", "outro_punchlines"):
            max_units = slot.get("_pre_units", 0)
        else:
            max_units = min(slot.get("_pre_units", 0), _dynamic_cap(dur))

        requires_audio = max_units > 0

        est_tts = estimated_tts_duration(max_units)

        overflow_risk = requires_audio and (est_tts > dur * 0.90)

        if idx + 1 < total_slots:
            next_start = round(raw_slots[idx + 1]["start"], 6)
        else:
            next_start = round(total_dur, 6)
        available_gap = round(max(0.0, next_start - end), 6)

        seg: dict = {
            "segment_id":            f"seg_{str(idx).zfill(pad_width)}",
            "segment_type":          stype,
            "start_time":            start,
            "end_time":              end,
            "duration":              dur,
            "event_type":            slot["event_type"],
            "max_units":             max_units,
            "vocal_mode":            slot["vocal_mode"],
            "requires_audio":        requires_audio,
            "estimated_tts_duration": est_tts,
            "tts_overflow_risk":      overflow_risk,
            "available_gap":          available_gap,
        }

        if "confidence" in slot:
            seg["confidence"] = slot["confidence"]

        if slot.get("merged_count", 1) > 1:
            seg["merged_event_types"] = slot["merged_event_types"]
            seg["merged_count"]       = slot["merged_count"]

        if not requires_audio and stype == "global_filler":
            seg["vocal_mode"] = "silence"
        if not requires_audio and stype == "outro_punchlines":
            seg["vocal_mode"] = "silence"
        # If outro immediately follows an event segment, silence it —
        # a near-end event is its own punchline; forced outro sounds awkward.
        if stype == "outro_punchlines" and idx > 0:
            prev_slot = raw_slots[idx - 1]
            if prev_slot["_type"] == "event":
                seg["vocal_mode"] = "silence"
                seg["requires_audio"] = False
                seg["max_units"] = 0

        enhanced_segments.append(seg)

        if stype == "intro_hooks":
            rag_lines.append("intro_hooks")
        elif stype == "outro_punchlines":
            rag_lines.append("outro_punchlines")
        elif slot["event_type"] == "player_elimination":
            rag_lines.append("kill finish")
        elif slot["event_type"] == "player_knock":
            rag_lines.append("knock down")
        else:
            rag_lines.append(slot["event_type"])

    # ------------------------------------------------------------------
    # FIX 3: Enhanced RAG query — add multi-kill context from intent analysis
    # ------------------------------------------------------------------
    # Use intent analysis from validated VLM output for better context
    multi_kill_count = 0
    if "multi_kill" in intent_analysis:
        multi_kill_events = intent_analysis["multi_kill"]
        if multi_kill_events:
            multi_kill_count = max(event.get("kill_count", 0) for event in multi_kill_events)
    
    # Fallback to counting eliminations if intent analysis is not available
    if multi_kill_count == 0:
        elim_events  = [e for e in event_list if e.get("type") == "player_elimination"]
        actor_kills  = Counter(e.get("actor") for e in elim_events if e.get("actor"))
        multi_kill_count = max(actor_kills.values()) if actor_kills else 0

    if multi_kill_count >= 4:
        multi_tag = "quad kill multi kill"
    elif multi_kill_count == 3:
        multi_tag = "triple kill"
    elif multi_kill_count == 2:
        multi_tag = "double kill"
    else:
        multi_tag = ""

    rag_parts = list(dict.fromkeys(rag_lines))
    if multi_tag:
        # Insert after intro_hooks so the retriever sees: intro → multi-kill → events → outro
        insert_pos = 1 if len(rag_parts) > 1 else len(rag_parts)
        rag_parts.insert(insert_pos, multi_tag)

    # ------------------------------------------------------------------
    # INTEGRITY CHECK
    # ------------------------------------------------------------------
    if enhanced_segments:
        actual_start  = enhanced_segments[0]["start_time"]
        actual_end    = enhanced_segments[-1]["end_time"]
        total_covered = sum(s["duration"] for s in enhanced_segments)
        assert abs(actual_start) < 1e-6,              f"First segment does not start at 0: {actual_start}"
        assert abs(actual_end - total_dur) < 1e-4,    f"Last segment end {actual_end} != total_duration {total_dur}"
        assert abs(total_covered - total_dur) < 1e-4, f"Summed durations {total_covered} != total_duration {total_dur}"

    segments_text = "\n".join(json.dumps(seg, ensure_ascii=False) for seg in enhanced_segments)

    return {
        "budget_unit_type":    budget_unit_type,
        "rag_query":           ". ".join(rag_parts),
        "rate_type_used":      rate_type_used,
        "segments":            enhanced_segments,
        "segments_text":       segments_text,
        "target_rate_used":    target_rate_used,
        "effective_rate_used": conservative_rate,
        "multi_kill_count":    multi_kill_count,
        "intent_analysis":     json.dumps(intent_analysis, ensure_ascii=False),      # Convert to JSON string
        "validation_log":      json.dumps(validation_log, ensure_ascii=False),       # Convert to JSON string
        "drift_corrections":   len(drift_log)        # Include drift correction count
    }
