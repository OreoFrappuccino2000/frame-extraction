# 需求文档：视频智能配音生成流水线

## 引言

本功能旨在为 Dify 工作流提供一套完整的**视频智能配音生成**能力。用户在 Dify 工作流中上传一个视频文件，系统将自动完成以下端到端流程：

1. **帧提取**：从视频中均匀提取最多 20 帧（含时间戳），输出为 `array[file]` 格式
2. **VLM 视觉理解**：将帧图像批量送入视觉语言模型（VLM），提取场景信息、理解视频上下文与意图
3. **配音脚本生成**：基于 VLM 分析结果，生成与视频节奏匹配的旁白/配音脚本
4. **TTS 语音合成**：将脚本文本转换为语音音频
5. **音视频合成**：将生成的音频与原始视频合并，输出最终配音视频

---

## 需求

### 需求 1：视频输入接收与解析

**用户故事：** 作为一名 Dify 工作流设计者，我希望工作流能接收用户上传的视频文件（Dify file 对象格式），以便后续节点可以对视频内容进行处理。

#### 验收标准

1. WHEN 用户在 Dify 工作流中上传视频文件 THEN 系统 SHALL 接收 Dify file 对象（包含 `url`、`filename`、`mime_type`、`size` 等字段），并将其传递给帧提取节点。
2. WHEN 系统接收到 Dify file 对象 THEN 系统 SHALL 优先使用 `out_url`（COS 直链）下载视频，若不可用则回退使用 `url`（内网预览链接）。
3. IF 输入的视频文件格式不受支持（非 mp4/mov/avi/webm 等常见格式）THEN 系统 SHALL 返回明确的错误信息，终止流程。
4. IF 视频时长超出预期范围（例如超过 60 秒）THEN 系统 SHALL 仍然正常处理，但仅从视频中均匀采样最多 20 帧。

---

### 需求 2：均匀帧提取（输出 array[file]）

**用户故事：** 作为一名 Dify 工作流设计者，我希望系统能从视频中均匀提取最多 20 帧并以 `array[file]` 格式输出，以便 Dify 后续的 VLM 节点可以直接消费这些帧图像。

#### 验收标准

1. WHEN 视频时长在 15–20 秒之间 THEN 系统 SHALL 均匀提取恰好 20 帧（每帧间隔约 0.75–1 秒）。
2. WHEN 视频时长少于 20 帧对应的最小间隔 THEN 系统 SHALL 提取实际可用的最大帧数（不超过 20 帧）。
3. WHEN 执行帧提取 THEN 系统 SHALL 使用 `ffmpeg` 实现均匀采样，确保帧在时间轴上均匀分布。
4. WHEN 帧提取完成 THEN 系统 SHALL 以 JPEG 格式保存每一帧图像，并以 `array[file]`（Dify file 对象数组）格式输出，每个元素包含 `frame_index`、`timestamp_seconds`、`timestamp_formatted`、`image_url`。
5. WHEN 返回帧数组 THEN 系统 SHALL 同时输出 `video_duration`（视频总时长）和 `total_frames_extracted`（实际提取帧数）作为元数据。

---

### 需求 3：VLM 视觉理解与上下文分析

**用户故事：** 作为一名 Dify 工作流设计者，我希望系统能将提取的帧批量送入 VLM 进行分析，以便理解视频的场景内容、叙事上下文和整体意图。

#### 验收标准

1. WHEN 帧提取完成 THEN 系统 SHALL 将 `array[file]` 中的帧图像连同时间戳信息一起发送给 VLM 节点。
2. WHEN VLM 节点接收到帧图像 THEN 系统 SHALL 提示 VLM 分析以下维度：场景描述（每帧）、人物/主体识别、动作与事件、整体叙事弧线、视频意图（如宣传、教程、记录等）。
3. WHEN VLM 分析完成 THEN 系统 SHALL 输出结构化的分析结果，包含：`scene_descriptions`（按帧的场景描述数组）、`overall_context`（整体上下文摘要）、`video_intent`（视频意图标签）。
4. IF VLM 无法识别某帧内容 THEN 系统 SHALL 在该帧的描述中标注 `"unclear"` 并继续处理其余帧，不中断流程。

---

### 需求 4：配音脚本生成

**用户故事：** 作为一名 Dify 工作流设计者，我希望系统能基于 VLM 分析结果自动生成与视频节奏匹配的配音脚本，以便直接用于 TTS 合成。

#### 验收标准

1. WHEN VLM 分析结果可用 THEN 系统 SHALL 将分析结果送入 LLM 节点，生成配音脚本。
2. WHEN 生成配音脚本 THEN 系统 SHALL 确保脚本总时长（按平均语速估算）与视频时长匹配（误差在 ±10% 以内）。
3. WHEN 生成配音脚本 THEN 系统 SHALL 将脚本分段，每段对应一个或多个视频帧的时间区间，输出格式为：`[{ "start_time": 0.0, "end_time": 3.5, "text": "..." }]`。
4. IF 视频意图为宣传/广告类 THEN 系统 SHALL 生成具有感召力的文案风格；IF 视频意图为教程/说明类 THEN 系统 SHALL 生成清晰、步骤化的解说风格。
5. WHEN 脚本生成完成 THEN 系统 SHALL 同时输出纯文本版本（`script_text`）和分段版本（`script_segments`），供后续节点选择使用。

---

### 需求 5：TTS 语音合成

**用户故事：** 作为一名 Dify 工作流设计者，我希望系统能将配音脚本转换为自然流畅的语音音频，以便与视频合并。

#### 验收标准

1. WHEN 配音脚本生成完成 THEN 系统 SHALL 调用 TTS 服务将 `script_text` 转换为音频文件（MP3 或 WAV 格式）。
2. WHEN 调用 TTS 服务 THEN 系统 SHALL 支持配置语音参数：语言（中文/英文）、音色（male/female）、语速（0.5x–2.0x）。
3. WHEN TTS 合成完成 THEN 系统 SHALL 输出音频文件的 URL 或 base64 编码，以及音频时长（`audio_duration`）。
4. IF TTS 合成的音频时长与视频时长差异超过 20% THEN 系统 SHALL 自动调整语速参数重新合成，使音频时长尽量接近视频时长。
5. IF TTS 服务调用失败 THEN 系统 SHALL 返回错误信息并终止后续音视频合成步骤。

---

### 需求 6：音视频合成

**用户故事：** 作为一名 Dify 工作流设计者，我希望系统能将生成的配音音频与原始视频合并，输出带配音的最终视频，以便直接交付给用户。

#### 验收标准

1. WHEN TTS 音频和原始视频均可用 THEN 系统 SHALL 使用 `ffmpeg` 将音频轨道替换或混合到原始视频中，生成最终配音视频。
2. WHEN 合成配音视频 THEN 系统 SHALL 保留原始视频的画质和分辨率不变，仅替换/添加音频轨道。
3. IF 音频时长短于视频时长 THEN 系统 SHALL 在音频末尾补充静音，使音频与视频等长。
4. IF 音频时长长于视频时长 THEN 系统 SHALL 截断音频至视频时长。
5. WHEN 合成完成 THEN 系统 SHALL 输出最终视频文件的 URL，并返回元数据：`output_video_url`、`video_duration`、`audio_duration`。

---

### 需求 7：错误处理与流程容错

**用户故事：** 作为一名 Dify 工作流设计者，我希望流水线在任意环节出现异常时能返回清晰的错误信息，以便工作流能够优雅地处理失败场景。

#### 验收标准

1. IF 视频文件无法下载或损坏 THEN 系统 SHALL 返回错误码和描述性错误消息，终止流程。
2. IF `ffmpeg` 执行失败 THEN 系统 SHALL 捕获 stderr 输出并将其包含在错误响应中。
3. IF VLM 分析超时或返回空结果 THEN 系统 SHALL 使用默认的通用配音脚本模板继续流程，并在输出中标注 `"vlm_fallback": true`。
4. IF TTS 合成失败 THEN 系统 SHALL 返回已生成的脚本文本，允许用户手动处理。
5. WHEN 任意节点发生错误 THEN 系统 SHALL 在错误响应中包含：`error_stage`（出错阶段）、`error_code`、`error_message`，方便定位问题。

---

### 需求 8：Dify 工作流集成与输出格式

**用户故事：** 作为一名 Dify 工作流设计者，我希望流水线各节点的输入输出格式符合 Dify 规范，以便无缝集成到 Dify 工作流中。

#### 验收标准

1. WHEN 帧提取节点输出 THEN 系统 SHALL 输出符合 Dify `array[file]` 规范的帧图像数组，可直接作为 VLM 节点的 `vision` 输入。
2. WHEN 使用 HTTP Request 节点调用后端服务 THEN 系统 SHALL 确保所有 API 响应的 `Content-Type` 为 `application/json`。
3. WHEN 最终流水线完成 THEN 系统 SHALL 输出以下最终结果供 Dify 工作流末端节点使用：
   ```json
   {
     "output_video_url": "https://...",
     "script_text": "...",
     "script_segments": [...],
     "video_duration": 18.5,
     "audio_duration": 18.2,
     "frames_extracted": 20,
     "vlm_fallback": false
   }
   ```
4. WHEN 在 Dify Code Node 中执行帧提取 THEN 系统 SHALL 通过 `return` 语句输出结果，使其可被后续节点的变量引用。
