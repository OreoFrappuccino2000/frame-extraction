# 实施计划：视频智能配音生成流水线

- [ ] 1. 实现帧提取 Code Node（Python）
   - 接收 Dify `array[file]` 中的视频对象，优先使用 `out_url` 下载视频，回退使用 `url`
   - 使用 `ffmpeg` 均匀提取最多 20 帧（JPEG 格式），计算每帧时间戳
   - 输出 `frames`（含 `frame_index`、`timestamp_seconds`、`timestamp_formatted`、`image_base64`）、`video_duration`、`total_frames_extracted`
   - 校验视频格式（mp4/mov/avi/webm），不支持时返回结构化错误
   - _需求：1.1、1.2、1.3、2.1、2.2、2.3、2.4、2.5_

- [ ] 2. 配置 VLM 节点与 Prompt
   - 在 Dify 工作流中配置 VLM（视觉语言模型）节点，将帧图像数组作为 `vision` 输入
   - 编写 System Prompt，要求 VLM 输出结构化 JSON：`scene_descriptions`、`overall_context`、`video_intent`
   - 处理 VLM 无法识别帧的情况，在对应帧描述中标注 `"unclear"`
   - _需求：3.1、3.2、3.3、3.4_

- [ ] 3. 实现配音脚本生成 LLM 节点与 Prompt
   - 配置 LLM 节点，将 VLM 输出的 `overall_context`、`video_intent`、`video_duration` 作为输入
   - 编写 Prompt，要求 LLM 按视频意图（宣传/教程/记录）调整文案风格，生成分段脚本
   - 输出 `script_text`（纯文本）和 `script_segments`（含 `start_time`、`end_time`、`text` 的数组）
   - 在 Prompt 中约束字数，使脚本朗读时长与 `video_duration` 误差在 ±10% 以内
   - _需求：4.1、4.2、4.3、4.4、4.5_

- [ ] 4. 实现 TTS 参数初始化与调用 Code Node
   - 编写 Code Node，根据 `video_duration` 和 `script_text` 字数估算初始语速参数
   - 调用 TTS HTTP API，传入 `script_text`、语言、音色、语速，获取音频文件 URL 及 `audio_duration`
   - IF `audio_duration` 与 `video_duration` 差异超过 20%，自动调整语速重新调用 TTS（最多重试 2 次）
   - IF TTS 失败，返回 `error_stage: "tts"`、`error_code`、`error_message`，终止流程
   - _需求：5.1、5.2、5.3、5.4、5.5_

- [ ] 5. 实现音视频合成 Code Node（ffmpeg）
   - 接收原始视频 URL 和 TTS 音频 URL，下载到临时目录
   - 使用 `ffmpeg` 将音频轨道合并到视频中，保留原始画质和分辨率
   - 处理时长差异：音频短则补静音，音频长则截断至视频时长
   - 输出合成后视频文件的 URL，返回元数据 `output_video_url`、`video_duration`、`audio_duration`
   - _需求：6.1、6.2、6.3、6.4、6.5_

- [ ] 6. 实现全局错误处理与 VLM Fallback 逻辑
   - 在帧提取、TTS、音视频合成节点中统一捕获异常，输出 `error_stage`、`error_code`、`error_message`
   - 编写 VLM Fallback Code Node：当 VLM 返回空结果或超时时，使用通用脚本模板并标注 `vlm_fallback: true`
   - _需求：7.1、7.2、7.3、7.4、7.5_

- [ ] 7. 组装 Dify 工作流并验证端到端输出
   - 按流水线顺序连接所有节点：帧提取 → VLM → 脚本生成 → TTS → 音视频合成
   - 配置工作流末端节点，输出标准 JSON：`output_video_url`、`script_text`、`script_segments`、`video_duration`、`audio_duration`、`frames_extracted`、`vlm_fallback`
   - 使用示例视频（15–20 秒 mp4）端到端测试，验证所有节点输入输出格式符合 Dify 规范
   - _需求：8.1、8.2、8.3、8.4_
