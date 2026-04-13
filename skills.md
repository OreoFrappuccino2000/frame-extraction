# PUBG Mobile VLM 输出校验规则

## 基础校验规则

### 1. 时间一致性校验
- 事件时间戳必须单调递增
- 证据帧必须在有效范围内
- 事件时间不能超过视频总时长

### 2. 置信度过滤
- 置信度低于 0.55 的事件需要额外验证
- 高置信度事件（>0.9）直接通过
- 中等置信度事件（0.55-0.9）需要上下文验证

### 3. 防幻觉规则
- 禁止推断超出最后一帧的事件
- 必须基于可见 UI 证据
- 禁止编造玩家/战队名称

### 4. 玩家名称模糊化
- 替换具体玩家名称为模糊指代
- 使用：这边这个人 / 对面 / 这波人 / 这一队 / 刚刚那个 / 有人 / 一个人 / 另一边

## 意图识别模式

### 连杀意图 (Multi-Kill Intent)
- 模式：短时间内连续击杀同一团队的多个玩家
- 触发条件：3个以上 elimination 事件，目标团队相同，时间间隔 < 5秒
- 意图标签："team_wipe"

### 救援意图 (Rescue Intent)  
- 模式：knock 后立即开始 revival
- 触发条件：player_knock 后 3秒内出现 player_revival_started
- 意图标签："rescue_attempt"

### 团队对抗意图 (Team Fight Intent)
- 模式：两个团队之间的连续战斗事件
- 触发条件：不同团队间的 knock/elimination 事件交替出现
- 意图标签："team_fight"

## 事件逻辑校验

### 1. 击杀链验证
- knock 必须在 elimination 之前
- 同一目标的 knock 和 elimination 不能同时发生
- 救援必须在 knock 之后

### 2. 状态一致性
- 玩家状态必须合理过渡（alive → knocked → eliminated）
- 不能出现状态跳跃
- 复活后状态应重置为 alive

### 3. 位置合理性
- 事件位置应与玩家状态匹配
- 室内/室外战斗的逻辑一致性
- 移动路径的合理性

## 特殊场景处理

### 团队歼灭 (Team Wipe)
- 识别条件：一个团队的所有玩家都被 eliminated
- 需要验证：团队人数一致性，时间窗口合理性

### 毒圈压力 (Zone Pressure)
- 识别条件：zone_timer_s 减少，玩家向安全区移动
- 需要验证：时间戳一致性，移动方向合理性

## 输出格式要求

### 校验后事件格式
```json
{
  "validated": true/false,
  "event": {原事件},
  "intent_tags": ["tag1", "tag2"],
  "validation_notes": "校验说明",
  "confidence_adjusted": 调整后的置信度
}
```

### 校验日志格式
```json
{
  "timestamp": "校验时间",
  "event_count": 事件总数,
  "validated_count": 通过校验数,
  "rejected_count": 拒绝数,
  "intent_analysis": 意图分析结果
}
```