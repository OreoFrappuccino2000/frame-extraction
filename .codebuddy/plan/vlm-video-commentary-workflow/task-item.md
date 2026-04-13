# 实施计划

- [ ] 1. ffmpeg 抽帧模块（注入 ground truth 时间戳）
   - 实现 ffmpeg 抽帧脚本，使用 `ffprobe` 获取精确帧率，为每帧生成 `frame_timestamp_sec`（浮点秒数）
   - 输出格式：`[{ "k": 0, "frame_timestamp_sec": 0.0, "frame_path": "..." }, ...]`
   - 禁止使用"帧序号 × 固定帧率"推算时间戳
   - _需求：8.1、8.6、8.7_

- [ ] 2. VLM Prompt 构建模块（V2 结构 + 时间戳锚定）
   - 基于 V2 prompt 结构，在 system prompt 中加入 `TIMESTAMP ANCHORING — CRITICAL` 规则段落
   - 构建 user message 时将 `frame_timestamp_sec` 列表作为 ground truth 注入
   - 要求 VLM 输出的每条 events/views/metrics/squads 记录包含 `frame_timestamp_sec` 字段（原样复读）
   - _需求：8.2、8.3、8.4、8.8_

- [ ] 3. `skills.md` 规则文件编写
   - 编写事件校验规则文件，定义以下规则：UI 信号优先、knock 必须有 killfeed 证据、时间一致性约束、短时重复事件去重阈值（< 1.0s）、置信度过滤阈值（< 0.55）
   - 规则文件支持热更新，格式为结构化 Markdown + YAML front matter
   - _需求：1.1、1.2、1.4、1.6、1.8_

- [ ] 4. `validate_event()` 校验层代码实现
   - 实现 `validate_event(event, ground_truth_timestamps)` 函数，执行以下校验：
     - UI 信号优先验证（killfeed / knock / HP）
     - knock 事件缺少 `ui_killfeed` 时返回 `False`
     - `frame_timestamp_sec` 与 ground truth 偏差 > 0.5s 时强制覆盖并记录漂移日志
     - 置信度 < 0.55 时标记为低置信度并跳过
   - 实现时间一致性校验：检测时间倒退，执行短时重复事件 merge/去重
   - _需求：1.1、1.2、1.3、1.4、1.5、1.7、1.8_

- [ ] 5. 事件时间轴构建模块
   - 实现 `build_event_timeline(validated_events)` 函数
   - 输出标准事件对象：`{ event_id, start_time, end_time, event_type, priority }`
   - 按 `start_time` 升序排列，缺失 priority 时按默认规则赋值（`kill=1 > knock=2 > damage=3 > movement=4`）
   - 将 V2 的 30+ 种事件类型映射到内部优先级体系
   - _需求：2.1、2.2、2.3、2.4、8.8_

- [ ] 6. LLM 解说生成模块（时长约束）
   - 实现 LLM prompt 构建函数，注入事件 `duration` 字段和对应文本长度约束：
     - `duration ≤ 1.0s`：中文 ≤ 5 字 / 英文 ≤ 5 words
     - `1.0s < duration ≤ 3.0s`：中文 ≤ 15 字 / 英文 ≤ 15 words
     - `duration > 3.0s`：中文 ≤ 30 字 / 英文 ≤ 30 words
   - 实现输出长度校验，超长时截断或触发重新生成
   - 支持 RAG 知识库模板风格注入（reaction style）
   - _需求：3.1、3.2、3.3、3.4、3.5、3.6_

- [ ] 7. TTS 音频生成 + 真实时长获取模块
   - 实现 TTS 调用封装，完成后使用 `ffprobe` 解析音频文件获取真实 `audio_duration`
   - 输出结构：`{ segment_id, audio_url, audio_duration }`
   - 实现空音频/白噪音检测（`audio_duration < 0.1s`），触发重新生成
   - 实现单片段重试机制（最多 3 次），超限后标记为缺失并跳过
   - _需求：4.1、4.2、4.3、4.4、4.5_

- [ ] 8. `rules.md` 冲突规则文件编写
   - 编写冲突处理规则文件，定义：优先级覆盖策略（kill > knock > damage > movement）、同优先级 merge 策略、延迟策略
   - 规则文件支持热更新
   - _需求：6.2、6.3、6.4、6.5_

- [ ] 9. Alignment Controller + 冲突处理模块
   - 实现 `alignment_controller(event_timeline, tts_results)` 函数，在 TTS 全部完成后统一计算
   - 使用公式：`audio_start = event_start + reaction_delay`，`audio_end = audio_start + audio_duration`
   - `reaction_delay` 默认 `0.6s ~ 1.2s`，支持按事件类型配置
   - 实现冲突检测（`audio_end > next_event_start`）并调用冲突处理：优先级覆盖 / merge / 延迟
   - 输出无重叠的 `placement_map`：`[{ segment_id, start, end }, ...]`
   - _需求：5.1、5.2、5.3、5.4、5.5、5.6、6.1、6.2、6.3、6.4、6.6_

- [ ] 10. 视频合成模块 + 端到端验证
   - 实现视频合成脚本，按 `placement_map` 中的 `start` 时间点将音频插入视频轨道
   - 缺失片段对应时间段保持静音
   - 实现合成结果验证：检查每段音频实际播放时间与 `placement_map` 误差 ≤ 0.1s
   - 执行端到端测试：验证无提前解说、无音频重叠、`reaction_delay` 在合理范围内
   - _需求：7.1、7.2、7.3、7.4、7.5_
