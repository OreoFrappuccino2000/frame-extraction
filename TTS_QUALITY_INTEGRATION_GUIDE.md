# TTS质量检查集成指南

## 概述

本指南介绍如何在VLM视频解说工作流中集成TTS（文本转语音）质量检查功能。该功能使用WhisperX进行语音识别，验证TTS音频的发音准确性，确保音频质量符合要求后再进行视频合并。

## 功能特性

- ✅ **实时质量检查**: 在音频插入视频前进行质量验证
- ✅ **发音准确性验证**: 使用WhisperX对比预期文本和实际发音
- ✅ **多维度检查**: 音频可访问性、时长、格式、发音准确性
- ✅ **智能重试机制**: 质量不合格时自动重试
- ✅ **详细日志记录**: 完整的质量检查报告
- ✅ **配置灵活**: 支持自定义质量阈值和检查参数

## 集成架构

```
TTS生成 → 质量检查 → 音频对齐 → 视频合并
     ↓          ↓          ↓          ↓
  音频文件 → 质量验证 → 时间轴对齐 → 最终视频
```

## 快速开始

### 1. 环境准备

确保已安装必要的依赖：

```bash
# 安装WhisperX和相关依赖
pip install whisperx torch torchaudio

# 安装音频处理库
pip install pydub librosa

# 安装HTTP请求库
pip install requests
```

### 2. 配置参数

在Dify工作流中设置以下环境变量：

```python
# TTS质量检查配置
TTS_QUALITY_THRESHOLD = 0.8        # 质量阈值 (0.0-1.0)
ENABLE_TTS_VALIDATION = True       # 启用质量检查
TTS_MAX_RETRIES = 3                # 最大重试次数
ASR_SIMILARITY_THRESHOLD = 0.7     # ASR相似度阈值
```

### 3. 工作流集成

#### 方法1: 在音频对齐阶段集成

```python
# 在build_timed_audio_track函数中添加质量检查
def build_timed_audio_track(placements, audio_map, merge_id, total_duration, tmp_files):
    # ... 现有代码 ...
    
    # 步骤3: 下载和处理音频片段
    for sid, seg in enumerate(placements):
        # 下载音频文件
        audio_url = audio_map.get(seg["segment_id"])
        if not audio_url:
            continue
            
        # TTS质量检查
        if ENABLE_TTS_VALIDATION:
            expected_text = seg.get("text", "")
            language = seg.get("language", "zh")
            
            quality_result = _perform_tts_quality_check(
                audio_url=audio_url,
                segment_id=seg["segment_id"],
                expected_text=expected_text,
                language=language
            )
            
            if not quality_result["passed"]:
                print(f"[TTS_QUALITY] {seg['segment_id']}: 质量检查失败")
                print(f"  错误: {quality_result.get('error', '无')}")
                print(f"  分数: {quality_result.get('quality_score', 0.0):.3f}")
                
                # 触发重试或使用备用方案
                if quality_result["retry_count"] < TTS_MAX_RETRIES:
                    # 重新生成TTS音频
                    return _trigger_tts_retry(seg, quality_result)
                else:
                    # 使用静音或跳过此片段
                    return _handle_tts_failure(seg, quality_result)
    
    # ... 继续处理 ...
```

#### 方法2: 在TTS生成后立即检查

```python
# 在TTS生成节点后添加质量检查节点
def tts_quality_check_node(tts_files, expected_texts, language="zh"):
    """
    TTS质量检查节点
    验证TTS音频质量，返回质量报告和重试建议
    """
    
    quality_results = []
    needs_retry = False
    retry_reason = ""
    
    for i, audio_file in enumerate(tts_files):
        expected_text = expected_texts[i] if i < len(expected_texts) else expected_texts[0]
        
        result = _perform_tts_quality_check(
            audio_url=audio_file["url"],
            segment_id=audio_file.get("id", f"seg_{i}"),
            expected_text=expected_text,
            language=language
        )
        
        quality_results.append(result)
        
        if not result["passed"]:
            needs_retry = True
            retry_reason = f"片段 {i} 质量不合格"
    
    return {
        "quality_results": quality_results,
        "all_passed": all(r["passed"] for r in quality_results),
        "needs_retry": needs_retry,
        "retry_reason": retry_reason,
        "average_score": sum(r.get("quality_score", 0) for r in quality_results) / len(quality_results)
    }
```

## 配置详解

### 质量阈值配置

```python
QUALITY_CONFIG = {
    # 基础质量阈值
    "quality_threshold": 0.8,           # 总体质量阈值
    "asr_similarity_threshold": 0.7,    # ASR相似度阈值
    
    # 音频时长限制
    "min_audio_duration": 0.5,          # 最小音频时长(秒)
    "max_audio_duration": 10.0,         # 最大音频时长(秒)
    
    # 重试配置
    "max_retries": 3,                   # 最大重试次数
    "retry_delay": 1.0,                 # 重试延迟(秒)
    
    # 性能配置
    "timeout": 30.0,                    # 超时时间(秒)
    "max_concurrent": 5                 # 最大并发检查数
}
```

### 事件类型优先级

```python
EVENT_PRIORITY = {
    "kill": 1,      # 击杀事件 - 最高优先级
    "knock": 2,     # 击倒事件 - 高优先级
    "damage": 3,    # 伤害事件 - 中等优先级
    "movement": 4,  # 移动事件 - 低优先级
    "filler": 5     # 填充事件 - 最低优先级
}
```

## 使用示例

### 基本使用

```python
# 导入质量检查函数
from app import _perform_tts_quality_check

# 执行质量检查
result = _perform_tts_quality_check(
    audio_url="https://example.com/audio/tts_001.wav",
    segment_id="seg_001",
    expected_text="Player A eliminates Player B",
    language="en"
)

# 检查结果
if result["passed"]:
    print("✓ TTS音频质量合格")
    print(f"  相似度分数: {result['similarity_score']:.3f}")
    print(f"  识别文本: {result['asr_text']}")
else:
    print("✗ TTS音频质量不合格")
    print(f"  错误: {result.get('error', '无')}")
    print(f"  建议: {'重试' if result['retry_count'] < 3 else '使用备用方案'}")
```

### 批量检查

```python
# 批量检查多个音频文件
def batch_quality_check(audio_segments, expected_texts, language="zh"):
    """批量执行TTS质量检查"""
    
    results = []
    for i, segment in enumerate(audio_segments):
        result = _perform_tts_quality_check(
            audio_url=segment["url"],
            segment_id=segment["id"],
            expected_text=expected_texts[i],
            language=language,
            retry_count=segment.get("retry_count", 0)
        )
        results.append(result)
    
    # 统计结果
    passed_count = sum(1 for r in results if r["passed"])
    avg_score = sum(r.get("quality_score", 0) for r in results) / len(results)
    
    return {
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "success_rate": passed_count / len(results),
            "average_score": avg_score
        }
    }
```

## 错误处理

### 常见错误及解决方案

| 错误类型 | 原因 | 解决方案 |
|---------|------|----------|
| 音频不可访问 | URL无效或网络问题 | 检查URL有效性，重试下载 |
| 音频时长异常 | 文件损坏或格式问题 | 重新生成TTS音频 |
| ASR识别失败 | WhisperX服务异常 | 检查WhisperX安装，使用备用ASR |
| 相似度过低 | 发音不准确或文本不匹配 | 调整TTS参数，重新生成 |
| 超时错误 | 处理时间过长 | 增加超时时间或优化性能 |

### 重试机制

```python
def handle_tts_quality_failure(result, max_retries=3):
    """处理TTS质量检查失败"""
    
    if result["retry_count"] >= max_retries:
        # 达到最大重试次数，使用备用方案
        return {
            "action": "use_fallback",
            "reason": "达到最大重试次数",
            "fallback_options": ["silence", "short_beep", "previous_audio"]
        }
    else:
        # 触发重试
        return {
            "action": "retry",
            "retry_count": result["retry_count"] + 1,
            "delay": 1.0 * (result["retry_count"] + 1)  # 指数退避
        }
```

## 性能优化

### 缓存策略

```python
# 使用缓存避免重复检查
from cachetools import TTLCache

# 创建缓存（最大100个项目，有效期300秒）
quality_cache = TTLCache(maxsize=100, ttl=300)

def cached_quality_check(audio_url, expected_text, language):
    """带缓存的TTS质量检查"""
    
    cache_key = f"{audio_url}:{expected_text}:{language}"
    
    if cache_key in quality_cache:
        return quality_cache[cache_key]
    
    # 执行质量检查
    result = _perform_tts_quality_check(audio_url, "cache_segment", expected_text, language)
    
    # 缓存结果
    quality_cache[cache_key] = result
    
    return result
```

### 异步处理

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def async_batch_quality_check(audio_segments, expected_texts, language="zh"):
    """异步批量质量检查"""
    
    async def check_single(segment, expected_text):
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                _perform_tts_quality_check,
                segment["url"], segment["id"], expected_text, language
            )
        return result
    
    # 并发执行所有检查
    tasks = [
        check_single(segment, expected_texts[i])
        for i, segment in enumerate(audio_segments)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

## 监控和日志

### 日志配置

```python
import logging

# 配置质量检查日志
quality_logger = logging.getLogger("tts_quality")
quality_logger.setLevel(logging.INFO)

# 文件处理器
file_handler = logging.FileHandler("tts_quality.log")
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
quality_logger.addHandler(file_handler)

def log_quality_result(result):
    """记录质量检查结果"""
    if result["passed"]:
        quality_logger.info(
            f"质量检查通过 - 片段: {result['segment_id']} "
            f"分数: {result.get('quality_score', 0.0):.3f}"
        )
    else:
        quality_logger.warning(
            f"质量检查失败 - 片段: {result['segment_id']} "
            f"错误: {result.get('error', '无')}"
        )
```

### 性能监控

```python
import time
from datetime import datetime

class QualityCheckMonitor:
    """质量检查性能监控"""
    
    def __init__(self):
        self.metrics = {
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": 0,
            "total_duration": 0.0,
            "avg_duration": 0.0
        }
    
    def record_check(self, result, duration):
        """记录检查结果"""
        self.metrics["total_checks"] += 1
        self.metrics["total_duration"] += duration
        
        if result["passed"]:
            self.metrics["passed_checks"] += 1
        else:
            self.metrics["failed_checks"] += 1
        
        self.metrics["avg_duration"] = (
            self.metrics["total_duration"] / self.metrics["total_checks"]
        )
    
    def get_report(self):
        """获取监控报告"""
        success_rate = (
            self.metrics["passed_checks"] / self.metrics["total_checks"] * 100
            if self.metrics["total_checks"] > 0 else 0
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics,
            "success_rate": success_rate,
            "status": "healthy" if success_rate >= 80 else "degraded"
        }
```

## 故障排除

### 常见问题

**Q: WhisperX无法导入**
A: 确保已正确安装WhisperX: `pip install whisperx`

**Q: 音频时长计算不准确**
A: 检查音频文件格式，确保是标准WAV格式

**Q: ASR识别结果为空**
A: 检查音频质量，确保音量足够且无明显噪音

**Q: 性能过慢**
A: 启用缓存，使用异步处理，或调整批处理大小

### 调试模式

启用调试模式获取详细日志：

```python
# 设置调试模式
import os
os.environ["TTS_QUALITY_DEBUG"] = "1"

# 在代码中检查调试模式
debug_mode = os.getenv("TTS_QUALITY_DEBUG", "0") == "1"
if debug_mode:
    print(f"[DEBUG] 质量检查详细日志...")
```

## 总结

通过集成TTS质量检查功能，您可以：

1. **提高视频质量**: 确保TTS音频发音准确
2. **减少重试次数**: 提前发现质量问题
3. **优化用户体验**: 提供更自然的语音解说
4. **降低资源浪费**: 避免处理低质量音频

按照本指南的步骤，您可以轻松地在现有工作流中集成TTS质量检查功能。