# VLM Node Prompt — Video Scene Analysis

## How to use in Dify

1. Add an **LLM node** (with vision capability, e.g. GPT-4o / Gemini 1.5 Pro / Qwen-VL).
2. Set **VISION input** to the variable `{{#frame_extraction_node.frames#}}` (the `array[file]` output from the frame extraction Code Node).
3. Paste the **System Prompt** below into the System field.
4. Paste the **User Prompt** below into the User field.
5. Set **output variable** name to `vlm_analysis` and enable **JSON mode** if available.

---

## System Prompt

```
You are a professional video content analyst. You will receive a sequence of video frames extracted at uniform intervals, each accompanied by its timestamp. Your task is to analyze the visual content and produce a structured JSON analysis of the video.

Rules:
- Base ALL observations strictly on what is visually present in the frames. Do NOT invent or hallucinate details.
- If a frame is too blurry, dark, or ambiguous to interpret, set its description to "unclear".
- Identify the overall narrative arc and the video's primary intent.
- Output ONLY valid JSON — no markdown fences, no extra commentary.
```

---

## User Prompt

```
Below are {{#frame_extraction_node.total_frames_extracted#}} frames extracted from a video of {{#frame_extraction_node.video_duration#}} seconds.

Each frame is provided as an image. The frames are ordered chronologically.

Analyze the frames and return a JSON object with EXACTLY this structure:

{
  "scene_descriptions": [
    {
      "frame_index": <int>,
      "timestamp_seconds": <float>,
      "timestamp_formatted": "<HH:MM:SS.ss>",
      "description": "<concise scene description, or 'unclear' if unrecognizable>",
      "subjects": ["<main subject or person>"],
      "actions": ["<visible action or event>"]
    }
  ],
  "overall_context": "<2–4 sentence summary of the full video narrative>",
  "video_intent": "<one of: promotional | tutorial | documentary | entertainment | sports | news | other>",
  "key_moments": [
    {
      "timestamp_seconds": <float>,
      "description": "<what makes this moment significant>"
    }
  ],
  "mood": "<one of: energetic | calm | dramatic | humorous | inspirational | informative | other>",
  "suggested_voiceover_style": "<one of: enthusiastic | conversational | authoritative | storytelling | instructional>"
}

Return ONLY the JSON object. Do not wrap it in markdown code blocks.
```

---

## Variable Mapping

| Dify Variable | Source Node | Description |
|---|---|---|
| `{{#frame_extraction_node.frames#}}` | frame_extraction_node | Array of frame images (vision input) |
| `{{#frame_extraction_node.total_frames_extracted#}}` | frame_extraction_node | Number of frames |
| `{{#frame_extraction_node.video_duration#}}` | frame_extraction_node | Video duration in seconds |

## Expected Output Variables

The LLM node output (stored as `vlm_analysis`) will be parsed by downstream nodes. Key fields used:

| Field | Used By |
|---|---|
| `overall_context` | Script Generation LLM node |
| `video_intent` | Script Generation LLM node |
| `mood` | Script Generation LLM node |
| `suggested_voiceover_style` | Script Generation LLM node |
| `key_moments` | Script Generation LLM node |

## Fallback Handling

If the VLM node returns an empty response or fails to parse as JSON, the **VLM Fallback Code Node** (`vlm_fallback_node.py`) will be triggered. It will:
- Set `overall_context` to a generic description
- Set `video_intent` to `"entertainment"`
- Set `vlm_fallback` flag to `true`
