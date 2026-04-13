# 音频视频对齐冲突解决规则

## 优先级体系

### 事件优先级定义
事件按重要性从高到低排序：

| 优先级 | 事件类型 | 权重 | 描述 |
|--------|----------|------|------|
| 1 | kill/elimination | 1 | 击杀/淘汰事件，最高优先级 |
| 2 | knock/down | 2 | 击倒事件，高优先级 |
| 3 | damage/combat | 3 | 伤害/战斗事件，中等优先级 |
| 4 | movement/positioning | 4 | 移动/位置事件，低优先级 |
| 5 | filler/color | 5 | 填充/色彩事件，最低优先级 |

### 优先级覆盖规则
1. **绝对优先级**：高优先级事件总是覆盖低优先级事件
2. **同优先级处理**：相同优先级事件按时间顺序处理，早发生的事件优先
3. **合并阈值**：相邻事件间隔 < 1.0秒且类型相同可合并

## 冲突检测规则

### 冲突定义
音频时间冲突定义为：`audio_end > next_event_start`

### 冲突检测参数
```yaml
conflict_detection:
  overlap_threshold: 0.1  # 重叠阈值（秒）
  min_gap: 0.05          # 最小间隔（秒）
  max_delay: 3.0         # 最大延迟时间（秒）
```

## 冲突解决策略

### 策略1：优先级覆盖（默认）
```python
# 当高优先级事件与低优先级事件冲突时
if current_event.priority < next_event.priority:
    # 保留高优先级事件，丢弃低优先级事件
    discard_lower_priority_event(next_event)
```

### 策略2：事件合并
```python
# 当相邻事件类型相同且间隔小于阈值时
if (event1.type == event2.type and 
    event2.start - event1.end < merge_threshold):
    # 合并事件
    merged_event = merge_events(event1, event2)
```

### 策略3：延迟处理
```python
# 当冲突无法通过覆盖或合并解决时
if can_delay_event(event, max_delay):
    # 延迟低优先级事件
    delayed_event = delay_event_after_conflict(event, conflict_end)
```

### 策略4：文本合并重生成
```python
# 当两个事件优先级相同且无法延迟时
if events_have_same_priority(event1, event2):
    # 合并解说文本，重新生成TTS
    merged_text = merge_commentary_text(event1.text, event2.text)
    new_audio = regenerate_tts(merged_text)
```

## 具体场景处理规则

### 场景1：击杀事件冲突
```yaml
kill_event_conflict:
  description: "多个击杀事件在短时间内发生"
  handling:
    - "如果间隔 < 0.5秒：合并为多杀事件"
    - "如果间隔 0.5-1.0秒：按时间顺序排列"
    - "如果间隔 > 1.0秒：正常处理，可能产生延迟"
  example: "双杀、三杀场景"
```

### 场景2：击倒与伤害事件冲突
```yaml
knock_damage_conflict:
  description: "击倒事件与伤害事件重叠"
  handling:
    - "击倒事件优先级高于伤害事件"
    - "丢弃伤害事件解说"
    - "如果击倒后立即有击杀，可合并解说"
```

### 场景3：移动事件与战斗事件冲突
```yaml
movement_combat_conflict:
  description: "移动解说与战斗解说重叠"
  handling:
    - "战斗事件优先级高于移动事件"
    - "延迟移动事件解说"
    - "如果延迟过大，静音移动事件"
```

### 场景4：填充事件冲突
```yaml
filler_conflict:
  description: "填充解说与事件解说重叠"
  handling:
    - "事件解说优先级高于填充解说"
    - "静音或缩短填充解说"
    - "保持视频节奏流畅"
```

## 反应延迟配置

### 默认延迟范围
```yaml
reaction_delay:
  default_range: [0.6, 1.2]  # 默认反应延迟范围（秒）
  
  # 事件类型特定延迟
  event_specific:
    kill: [0.5, 0.8]     # 击杀事件反应较快
    knock: [0.6, 1.0]    # 击倒事件中等反应
    damage: [0.8, 1.2]   # 伤害事件标准反应
    movement: [1.0, 1.5] # 移动事件反应较慢
    
  # 动态调整因子
  adjustment_factors:
    high_intensity: 0.8   # 高强度场景加速反应
    low_intensity: 1.2    # 低强度场景减缓反应
    multi_kill: 0.7      # 多杀场景特别加速
```

## 错误处理和容错机制

### 音频时长异常处理
```yaml
audio_duration_issues:
  empty_audio: 
    threshold: 0.1  # 空音频阈值（秒）
    action: "regenerate"
    
  excessive_duration:
    threshold: 10.0  # 过长音频阈值（秒）
    action: "truncate_and_log"
    
  tts_failure:
    max_retries: 3
    fallback: "silence"
```

### 时间轴异常处理
```yaml
timeline_issues:
  time_reversal:
    # 检测到时间倒退（当前事件start_time < 上一事件end_time）
    action: "skip_invalid_event"
    
  excessive_drift:
    threshold: 0.5  # 时间漂移阈值（秒）
    action: "use_ground_truth_timestamp"
    
  missing_timestamps:
    action: "estimate_from_frame_rate"
    fallback_fps: 30
```

## 性能优化规则

### 计算优化
```yaml
performance:
  max_concurrent_audio: 5      # 最大并发音频处理数
  cache_duration: 300          # 缓存持续时间（秒）
  batch_processing: true       # 启用批处理
  
  memory_management:
    max_audio_buffer: 100      # 最大音频缓冲区（MB）
    cleanup_interval: 60       # 清理间隔（秒）
```

### 质量保证
```yaml
quality_assurance:
  max_allowed_overlap: 0.05    # 最大允许重叠（秒）
  min_audio_quality: 0.8      # 最低音频质量分数
  max_reaction_delay: 2.0      # 最大反应延迟（秒）
  
  validation:
    check_audio_sync: true
    validate_timestamps: true
    verify_no_gaps: true
```

## 配置热更新支持

规则文件支持热更新，修改后无需重启服务：

```python
# 规则热更新示例
def reload_conflict_rules():
    """重新加载冲突解决规则"""
    global conflict_rules
    try:
        with open('conflict_rules.md', 'r', encoding='utf-8') as f:
            new_rules = parse_rules_from_markdown(f.read())
        conflict_rules.update(new_rules)
        logger.info("冲突规则已更新")
    except Exception as e:
        logger.error(f"规则更新失败: {e}")
```

## 日志和监控

### 冲突解决日志
```yaml
logging:
  conflict_resolution:
    level: "INFO"
    format: "时间冲突解决: 事件{event_id} -> 操作{action}"
    
  performance_metrics:
    track_resolution_time: true
    track_conflict_count: true
    track_audio_quality: true
```

### 监控指标
```yaml
metrics:
  conflicts_per_video: "视频冲突次数"
  resolution_success_rate: "冲突解决成功率"
  average_reaction_delay: "平均反应延迟"
  audio_overlap_percentage: "音频重叠比例"
```

---

**最后更新**: 2024-01-01  
**版本**: 1.0  
**适用场景**: VLM视频解说工作流音频对齐