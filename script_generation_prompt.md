# Script Generation LLM Node Prompt — Voiceover Script

## How to use in Dify

1. Add an **LLM node** (text-only, e.g. GPT-4o / Claude 3.5 / Qwen-Max).
2. Paste the **System Prompt** below into the System field.
3. Paste the **User Prompt** below into the User field, using the variable references shown.
4. Set **output variable** name to `script_result` and enable **JSON mode** if available.

---

## System Prompt

```
You are a professional voiceover scriptwriter. Your job is to write a natural, engaging voiceover script for a short video based on a visual analysis provided to you.

Rules:
1. The script MUST fit within the video duration. Use the word-count guidance provided to stay within time.
2. Split the script into segments that align with the video's visual flow.
3. Adapt your writing style based on the video_intent:
   - "promotional": persuasive, energetic, call-to-action language
   - "tutorial": clear, step-by-step, instructional tone
   - "documentary": authoritative, narrative storytelling
   - "entertainment" / "sports": exciting, dynamic, engaging
   - "news": neutral, factual, concise
   - "other": conversational and natural
4. Each segment's text should feel natural when spoken aloud — avoid overly complex sentences.
5. Output ONLY valid JSON — no markdown fences, no extra commentary.
```

---

## User Prompt

```
VIDEO ANALYSIS:
- Duration: {{#frame_extraction_node.video_duration#}} seconds
- Overall context: {{#vlm_node.overall_context#}}
- Video intent: {{#vlm_node.video_intent#}}
- Mood: {{#vlm_node.mood#}}
- Suggested voiceover style: {{#vlm_node.suggested_voiceover_style#}}
- Key moments:
{{#vlm_node.key_moments#}}

WORD COUNT GUIDANCE:
- Target language: English
- Average speaking rate: 2.5 words/second
- Target word count: {{#script_word_count_node.target_word_count#}} words (±10%)
- This ensures the voiceover fits within {{#frame_extraction_node.video_duration#}} seconds

TASK:
Write a voiceover script for this video. Return a JSON object with EXACTLY this structure:

{
  "script_text": "<full voiceover script as a single string, natural spoken language>",
  "script_segments": [
    {
      "segment_index": <int, starting from 1>,
      "start_time": <float, seconds>,
      "end_time": <float, seconds>,
      "text": "<the spoken text for this segment>",
      "word_count": <int>
    }
  ],
  "total_word_count": <int>,
  "estimated_duration_seconds": <float>,
  "language": "en",
  "style_notes": "<brief note on the writing style applied>"
}

Ensure:
- segment start_time and end_time values span the full video duration (0 to {{#frame_extraction_node.video_duration#}})
- Segments are contiguous (each segment's start_time equals the previous segment's end_time)
- total_word_count is the sum of all segment word_counts
- estimated_duration_seconds = total_word_count / 2.5

Return ONLY the JSON object.
```

---

## Pre-processing Code Node: `script_word_count_node`

Before this LLM node, add a small **Code Node** to calculate the target word count.
Paste the following Python into that Code Node:

```python
def main(video_duration: float) -> dict:
    """
    Calculate target word count for the voiceover script.
    English average speaking rate: 2.5 words/second.
    """
    words_per_second = 2.5
    target_word_count = int(video_duration * words_per_second)
    return {
        "target_word_count": target_word_count,
        "words_per_second": words_per_second,
    }
```

---

## Variable Mapping

| Dify Variable | Source Node | Description |
|---|---|---|
| `{{#frame_extraction_node.video_duration#}}` | frame_extraction_node | Video duration in seconds |
| `{{#vlm_node.overall_context#}}` | vlm_node (LLM) | VLM overall context summary |
| `{{#vlm_node.video_intent#}}` | vlm_node (LLM) | Detected video intent |
| `{{#vlm_node.mood#}}` | vlm_node (LLM) | Detected mood |
| `{{#vlm_node.suggested_voiceover_style#}}` | vlm_node (LLM) | VLM-suggested style |
| `{{#vlm_node.key_moments#}}` | vlm_node (LLM) | Key moments array |
| `{{#script_word_count_node.target_word_count#}}` | script_word_count_node | Calculated target word count |

## Expected Output Variables

| Field | Used By |
|---|---|
| `script_text` | TTS voiceover node |
| `script_segments` | Final output / subtitle generation |
| `estimated_duration_seconds` | TTS voiceover node (for speed adjustment) |
| `total_word_count` | TTS voiceover node |
