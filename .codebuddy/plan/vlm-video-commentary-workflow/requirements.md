# 需求文档：VLM 视频解说工作流（音画精准对齐）

## 引言

本项目旨在构建一个基于 Dify 工作流的视频自动解说系统，核心流程为：

**视频链接 → 抽帧（ffmpeg）→ VLM 理解画面 → LLM + RAG 生成解说 → TTS 生成音频 → 按时间插入视频**

当前核心痛点是**音频与视频事件无法精准对齐（audio start timing mismatch）**，根本原因在于：
1. VLM 存在幻觉问题，输出不可直接作为时间轴依据
2. TTS 时长不可控，不能用文本长度预测音频时长
3. VLM prompt 中时间窗口由模型自行推算，导致时间漂移（如事件实际发生在 14-15s，模型输出为 9-11s）

本需求文档定义了解决上述问题所需的核心模块：**VLM Prompt 时间锚定、Skills/Rules 校验层、事件时间轴构建、LLM 时长约束、TTS 真实时长获取、Alignment Controller、冲突处理机制**。

---

## 需求

### 需求 1：Skills / Rules 校验层（防 VLM 幻觉）

**用户故事：** 作为一名工作流开发者，我希望在 VLM 输出后增加一层规则校验，以便过滤幻觉事件、确保事件识别的可靠性。

#### 验收标准

1. WHEN VLM 输出事件时 THEN 系统 SHALL 优先采用 UI 信号（killfeed / knock / HP / weapon 等）作为高置信度验证依据
2. WHEN 事件类型为 `knock` 且缺少 `ui_killfeed` 字段时 THEN 系统 SHALL 拒绝该事件（返回 `False`）
3. WHEN 检测到时间倒退（当前事件 `start_time` < 上一事件 `end_time`）时 THEN 系统 SHALL 标记该事件为无效并跳过
4. WHEN 同一类型事件在短时间内（< 1.0s）重复出现时 THEN 系统 SHALL 执行 merge 或去重操作
5. WHEN 校验通过时 THEN 系统 SHALL 输出带置信度标记的事件对象
6. IF `skills.md` 规则文件存在 THEN 系统 SHALL 从该文件加载校验规则，支持规则热更新
7. WHEN VLM 输出的 `frame_timestamp_sec` 与注入的 ground truth 时间戳偏差 > 0.5s 时 THEN 系统 SHALL 用 ground truth 时间戳覆盖 VLM 输出，并记录漂移日志
8. WHEN VLM 输出事件的置信度 `confidence < 0.55` 时 THEN 系统 SHALL 标记该事件为低置信度，不纳入事件时间轴，仅记录日志

---

### 需求 2：构建唯一可信事件时间轴

**用户故事：** 作为一名工作流开发者，我希望构建一个统一的事件时间轴，以便后续所有模块都以此为唯一时间依据。

#### 验收标准

1. WHEN 校验层输出有效事件时 THEN 系统 SHALL 生成包含以下字段的事件对象：`event_id`、`start_time`、`end_time`、`event_type`、`priority`
2. WHEN 构建时间轴时 THEN 系统 SHALL 仅使用 `video_time`（抽帧时间戳）+ 校验后的 VLM 输出，禁止使用 VLM 原始输出直接决定时间
3. WHEN 时间轴构建完成时 THEN 系统 SHALL 按 `start_time` 升序排列所有事件
4. IF 事件优先级字段缺失 THEN 系统 SHALL 按默认优先级规则赋值：`kill=1 > knock=2 > damage=3 > movement=4`
5. WHEN 后续模块（LLM / TTS / Alignment）请求时间信息时 THEN 系统 SHALL 强制从该时间轴读取，不允许绕过

---

### 需求 3：LLM 生成解说时加入时长约束

**用户故事：** 作为一名工作流开发者，我希望 LLM 在生成解说文本时受到时长约束，以便降低 TTS 超长风险。

#### 验收标准

1. WHEN LLM 接收事件时 THEN 系统 SHALL 在 prompt 中注入事件的 `duration`（持续时间）字段
2. WHEN 事件 `duration ≤ 1.0s` 时 THEN 系统 SHALL 约束中文解说 ≤ 5 字、英文解说 ≤ 5 words
3. WHEN 事件 `duration > 1.0s` 且 `≤ 3.0s` 时 THEN 系统 SHALL 约束中文解说 ≤ 15 字、英文解说 ≤ 15 words
4. WHEN 事件 `duration > 3.0s` 时 THEN 系统 SHALL 约束中文解说 ≤ 30 字、英文解说 ≤ 30 words
5. WHEN LLM 输出超过约束长度时 THEN 系统 SHALL 截断或重新生成，不允许超长文本进入 TTS
6. IF RAG 知识库存在相关事件解说模板 THEN 系统 SHALL 优先参考模板风格（reaction style）

---

### 需求 4：TTS 后获取真实音频时长

**用户故事：** 作为一名工作流开发者，我希望 TTS 完成后能获取真实音频时长，以便作为后续对齐的唯一依据。

#### 验收标准

1. WHEN TTS 生成音频完成时 THEN 系统 SHALL 输出包含 `segment_id`、`audio_url`、`audio_duration` 的结构化对象
2. WHEN 获取音频时长时 THEN 系统 SHALL 通过实际解析音频文件（如 ffprobe）获取真实时长，禁止使用文本长度估算
3. WHEN 检测到空音频或白噪音（`audio_duration < 0.1s`）时 THEN 系统 SHALL 标记该片段为无效并触发重新生成
4. WHEN TTS 生成异常（发音错误、时长异常）时 THEN 系统 SHALL 记录错误日志并支持单片段重试
5. IF 同一片段重试超过 3 次仍失败 THEN 系统 SHALL 跳过该片段并在最终输出中标记为缺失

---

### 需求 5：Alignment Controller（核心对齐模块）

**用户故事：** 作为一名工作流开发者，我希望在 TTS 全部完成后统一计算音频放置位置，以便生成精准的 placement_map。

#### 验收标准

1. WHEN TTS 全部完成后 THEN 系统 SHALL 统一执行 Alignment Controller，禁止在 segmentation 阶段提前生成 placement_map
2. WHEN 计算音频放置时 THEN 系统 SHALL 使用公式：`audio_start = event_start + reaction_delay`，`audio_end = audio_start + audio_duration`
3. WHEN 设置 `reaction_delay` 时 THEN 系统 SHALL 默认范围为 `0.6s ~ 1.2s`，支持按事件类型配置
4. WHEN 生成 placement_map 时 THEN 系统 SHALL 输出包含 `segment_id`、`start`、`end` 的列表结构
5. WHEN `audio_end > next_event_start` 时 THEN 系统 SHALL 触发冲突处理流程（见需求 6）
6. IF placement_map 中存在重叠区间 THEN 系统 SHALL 拒绝输出并强制执行冲突解决

---

### 需求 6：冲突处理机制（rules.md）

**用户故事：** 作为一名工作流开发者，我希望系统能自动处理音频时间冲突，以便避免解说重叠和音画错位。

#### 验收标准

1. WHEN `audio_end > next_event_start` 时 THEN 系统 SHALL 检测为冲突并触发冲突处理
2. WHEN 发生冲突时 THEN 系统 SHALL 优先按优先级覆盖：`kill(1) > knock(2) > damage(3) > movement(4)`，低优先级事件被丢弃或延迟
3. WHEN 两个相邻事件优先级相同时 THEN 系统 SHALL 尝试合并解说文本，合并后重新走 TTS 流程
4. WHEN 合并文本超过时长约束时 THEN 系统 SHALL 选择保留较早事件，延迟低优先级事件到冲突解除后
5. IF `rules.md` 冲突规则文件存在 THEN 系统 SHALL 从该文件加载冲突处理策略，支持规则热更新
6. WHEN 冲突处理完成时 THEN 系统 SHALL 输出无重叠的最终 placement_map

---

### 需求 7：最终输出与视频合成

**用户故事：** 作为一名工作流开发者，我希望系统输出标准化的 placement_map 并完成视频合成，以便得到音画精准对齐的最终视频。

#### 验收标准

1. WHEN placement_map 生成完成时 THEN 系统 SHALL 输出标准 JSON 格式，每条记录包含 `segment_id`、`start`、`end`
2. WHEN 执行视频合成时 THEN 系统 SHALL 按 placement_map 中的 `start` 时间点将对应音频插入视频轨道
3. WHEN 合成完成时 THEN 系统 SHALL 保证：无提前解说、无音频重叠、解说延迟在合理范围（`reaction_delay` 内）
4. WHEN 合成结果验证时 THEN 系统 SHALL 检查每段音频的实际播放时间与 placement_map 的误差 ≤ 0.1s
5. IF 某片段音频标记为缺失 THEN 系统 SHALL 在该时间段保持静音，不影响其他片段的正常播放

---

### 需求 8：VLM Prompt 设计（时间锚定 + 结构化输出）

**用户故事：** 作为一名工作流开发者，我希望 VLM 的时间输出被强制锚定到 ffmpeg 抽帧的真实时间戳，并采用结构化四维输出格式，以便消除时间漂移并获得更精细的事件分类。

#### 背景：两版 Prompt 对比

当前存在两个版本的 VLM system prompt，各有优劣：

| 维度 | V1（原版） | V2（新版） | 结论 |
|---|---|---|---|
| **时间锚定** | ❌ 依赖 `time_grid` 字符串，模型自行推算 | ⚠️ 用帧序号 `k`，仍需外部映射到秒 | V2 略好，但两者均需补充时间戳注入 |
| **幻觉防控** | ✅ 明确 knock/elimination UI 区分规则 | ✅ Frame boundary 强制约束，k 越界丢弃 | V2 更严格 |
| **事件类型** | ⚠️ 仅 4 种（knock/elimination/combat/uncertain） | ✅ 30+ 种精细类型（stair_hold/revive/grenade 等） | V2 |
| **输出结构** | ⚠️ 简单 timeline 数组 | ✅ views / metrics / events / squads 四维结构 | V2 |
| **置信度** | ❌ 无置信度字段 | ✅ 0.00-1.00 置信度 + 校准规则 | V2 |
| **UI 证据要求** | ✅ 明确要求 `evidence` 字段 | ✅ `evidence_k` 帧列表 | 平手 |
| **去重规则** | ❌ 无 | ✅ killfeed 持久帧去重规则 | V2 |
| **时间漂移风险** | ❌ 高（模型推算 time_window） | ⚠️ 中（k 是帧序号，仍需外部映射） | V2 略好 |

**结论：采用 V2 结构，并补充时间戳锚定规则（见下方验收标准）**

#### 验收标准

1. WHEN ffmpeg 抽帧时 THEN 系统 SHALL 为每帧生成精确时间戳，格式为 `frame_timestamp_sec`（浮点秒数），并随帧数据一起传入 VLM
2. WHEN 构建 VLM 输入时 THEN 系统 SHALL 将每帧的 `frame_timestamp_sec` 作为 ground truth 直接注入 user message，格式示例：
   ```json
   [
     { "k": 0, "frame_timestamp_sec": 0.0 },
     { "k": 1, "frame_timestamp_sec": 3.5 },
     { "k": 2, "frame_timestamp_sec": 7.1 },
     { "k": 3, "frame_timestamp_sec": 14.2 }
   ]
   ```
   禁止由模型自行用"k × 帧率"计算时间戳
3. WHEN VLM system prompt 构建时 THEN 系统 SHALL 在 prompt 中加入以下时间戳锚定规则段落：
   > "TIMESTAMP ANCHORING — CRITICAL: Each frame k has a ground-truth timestamp provided in the user message as frame_timestamp_sec. You MUST copy frame_timestamp_sec exactly from the provided list into every event/view/metric/squad entry. Do NOT calculate timestamps using k × frame_rate. Do NOT infer or extrapolate timestamps beyond the provided list."
4. WHEN VLM 输出 events/views/metrics/squads 时 THEN 系统 SHALL 要求每条记录包含 `frame_timestamp_sec` 字段，值必须原样复读自注入列表
5. WHEN VLM 输出的 `frame_timestamp_sec` 与注入值不一致时 THEN 系统 SHALL 在校验层（需求 1）用注入值强制覆盖，并记录漂移量
6. WHEN 抽帧间隔不均匀（如关键帧抽取）时 THEN 系统 SHALL 仍为每帧单独记录真实时间戳，禁止用"帧序号 × 固定帧率"公式推算
7. IF 视频帧率信息可用 THEN 系统 SHALL 使用 `ffprobe` 获取精确帧率，而非假设固定帧率（如 30fps）
8. WHEN VLM 输出事件类型时 THEN 系统 SHALL 采用 V2 的 30+ 种精细事件类型，并将其映射到内部优先级体系（`kill=1 > knock=2 > damage=3 > movement=4`）
9. WHEN VLM 输出置信度 `confidence` 时 THEN 系统 SHALL 将 `confidence < 0.55` 的事件标记为低置信度，不纳入事件时间轴

---

## 核心约束（禁止事项）

| 禁止行为 | 原因 |
|---|---|
| ❌ 使用 VLM 原始输出直接决定时间 | VLM 存在幻觉，时间不可信 |
| ❌ 使用文本长度估算音频时长 | TTS 时长不稳定，必须用真实时长 |
| ❌ 在 segmentation 阶段生成最终 placement | 必须等 TTS 完成后统一计算 |
| ❌ 让模型自行推算 `time_window` 或 `frame_timestamp_sec` | 帧率误差累积导致时间漂移，必须注入 ground truth |
| ❌ 使用"帧序号 × 固定帧率"估算时间戳 | 帧率可能不均匀，必须用 ffprobe 获取真实时间戳 |
| ❌ 直接使用 V1 prompt（4 种事件类型） | 事件分类过粗，无法支持精细的优先级和冲突处理 |

## 正确执行流程

```
1. 抽帧（ffmpeg，每帧写入真实 frame_timestamp_sec）
2. 构建 VLM 输入（注入 ground truth 时间戳列表 + V2 结构化 prompt）
3. VLM 识别画面事件（原样复读 frame_timestamp_sec，输出 views/metrics/events/squads）
4. Skills 校验（去幻觉、去重、时间一致性、时间戳覆盖、置信度过滤）
5. 构建事件时间轴（唯一可信时间源，基于 frame_timestamp_sec）
6. LLM 生成解说（带时长约束）
7. TTS 生成音频（获取真实 audio_duration）
8. Alignment Controller（生成 placement_map）
9. 冲突处理（优先级覆盖 / merge / 延迟）
10. 视频合成（按 placement_map 插入音频）
```
