# TTS质量检查节点 - 更新版输出变量指南

## 概述

质量检查节点现已优化，输出变量更加清晰分开，便于在Dify工作流中使用。

## 新的输出变量结构

### 主要输出变量

#### 1. `validation_results` (Array[Object])
**描述**: 详细的验证结果数组，包含每个音频文件的检查详情

**结构**:
```json
[
  {
    "audio_index": 0,
    "expected_text": "测试文本",
    "audio_url": "http://example.com/audio.wav",
    "audio_size": 102400,
    "passed": true,
    "quality_score": 0.9,
    "checks": {
      "accessibility": {"passed": true, "status_code": 200},
      "duration": {"passed": true, "duration": 2.5},
      "size": {"passed": true, "size": 102400},
      "format": {"passed": true, "mime_type": "audio/wav"}
    },
    "errors": []
  }
]
```

#### 2. `all_acceptable` (String)
**描述**: 是否全部音频文件都通过质量检查

**取值**:
- `"yes"`: 全部通过
- `"no"`: 有文件未通过

#### 3. `retry_count` (Number)
**描述**: 当前的重试次数

#### 4. `next_retry_count` (Number)
**描述**: 下一次的重试计数（如果需要重试）

#### 5. `overall_quality_score` (Number)
**描述**: 总体质量分数（0.0-1.0）

#### 6. `passed_checks` (Number)
**描述**: 通过的检查数量

#### 7. `total_checks` (Number)
**描述**: 总检查数量

#### 8. `needs_retry` (Boolean)
**描述**: 是否需要重试

#### 9. `retry_reason` (String)
**描述**: 重试原因说明

#### 10. `workflow_status` (String)
**描述**: 工作流状态

**取值**:
- `"active"`: 活跃状态
- `"retry_needed"`: 需要重试
- `"fallback_needed"`: 需要备用方案
- `"completed"`: 已完成

#### 11. `recommendation` (String)
**描述**: 处理建议

#### 12. `max_retries` (Number)
**描述**: 最大重试次数配置

#### 13. `quality_threshold` (Number)
**描述**: 质量阈值配置

## Dify工作流配置示例

### 条件判断配置

#### 判断是否需要重试
```
条件: needs_retry == true
真分支: 重试管理节点
假分支: 后续处理节点
```

#### 判断是否全部可接受
```
条件: all_acceptable == "yes"
真分支: 时间轴对齐节点
假分支: 错误处理节点
```

### 变量映射示例

#### 质量检查节点 → 重试管理节点
```
quality_check_result ← 质量检查节点输出
retry_count ← 质量检查节点的retry_count
```

#### 质量检查节点 → 条件判断
```
needs_retry ← 质量检查节点的needs_retry
all_acceptable ← 质量检查节点的all_acceptable
```

#### 质量检查节点 → 日志记录
```
overall_quality_score ← 质量检查节点的overall_quality_score
recommendation ← 质量检查节点的recommendation
validation_results ← 质量检查节点的validation_results
```

## 工作流集成示例

### 完整工作流配置

```
开始
  ↓
Persona配置
  ↓
TTS参数初始化
  ↓
AudioSpring TTS
  ↓
质量检查节点
  ↓
条件判断: needs_retry?
  ├─ 真 → 重试管理 → AudioSpring TTS (更新参数)
  └─ 假 → 条件判断: all_acceptable?
         ├─ 真 → 时间轴对齐
         └─ 假 → 备用TTS处理
```

### 详细变量传递

```
质量检查节点输出:
├─ validation_results (用于详细分析)
├─ all_acceptable (用于快速判断)
├─ needs_retry (用于重试决策)
├─ retry_count (用于状态跟踪)
├─ overall_quality_score (用于质量监控)
├─ recommendation (用于问题诊断)
└─ workflow_status (用于流程控制)
```

## 使用场景示例

### 场景1: 质量检查通过
```json
{
  "validation_results": [...],
  "all_acceptable": "yes",
  "retry_count": 0,
  "next_retry_count": 0,
  "overall_quality_score": 0.95,
  "passed_checks": 4,
  "total_checks": 4,
  "needs_retry": false,
  "retry_reason": "质量检查通过",
  "workflow_status": "completed",
  "recommendation": "TTS音频质量良好，可以继续后续处理"
}
```

### 场景2: 需要重试
```json
{
  "validation_results": [...],
  "all_acceptable": "no",
  "retry_count": 1,
  "next_retry_count": 2,
  "overall_quality_score": 0.6,
  "passed_checks": 2,
  "total_checks": 4,
  "needs_retry": true,
  "retry_reason": "质量分数 0.60 低于阈值 0.8",
  "workflow_status": "retry_needed",
  "recommendation": "第二次重试未通过，建议简化文本或调整语音参数"
}
```

### 场景3: 需要备用方案
```json
{
  "validation_results": [...],
  "all_acceptable": "no",
  "retry_count": 3,
  "next_retry_count": 3,
  "overall_quality_score": 0.4,
  "passed_checks": 1,
  "total_checks": 4,
  "needs_retry": false,
  "retry_reason": "已达到最大重试次数",
  "workflow_status": "fallback_needed",
  "recommendation": "已达到最大重试次数，建议使用备用TTS服务或调整文本内容"
}
```

## 最佳实践

### 1. 条件判断优化
- 优先使用 `all_acceptable` 进行快速判断
- 使用 `needs_retry` 控制重试流程
- 使用 `workflow_status` 进行状态管理

### 2. 监控和日志
- 记录 `overall_quality_score` 进行质量监控
- 使用 `recommendation` 进行问题诊断
- 保存 `validation_results` 用于详细分析

### 3. 错误处理
- 根据 `workflow_status` 执行不同的错误处理策略
- 使用 `retry_reason` 了解失败原因
- 结合 `retry_count` 进行重试控制

## 故障排除

### 常见问题

1. **变量映射错误**: 确保输出变量名称正确
2. **条件判断失效**: 检查布尔值和字符串比较
3. **重试循环**: 监控 `retry_count` 避免无限循环

### 调试技巧

1. 启用详细日志输出
2. 检查 `validation_results` 中的详细错误信息
3. 使用测试数据验证条件判断逻辑

## 总结

新的输出变量结构提供了：

- ✅ **清晰的变量分离**: 每个变量有明确的用途
- ✅ **灵活的流程控制**: 支持多种条件判断
- ✅ **详细的监控信息**: 便于问题诊断和优化
- ✅ **易于集成**: 与Dify工作流完美兼容

现在你可以更灵活地控制TTS质量检查流程了！