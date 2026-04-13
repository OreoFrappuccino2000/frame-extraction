# TTS质量检查节点 - ASR集成使用指南

## 概述

本指南介绍如何在TTS质量检查节点中集成ASR（自动语音识别）服务，实现真正的发音准确性检查。

## 功能特性

### ✅ 基础质量检查
- 音频文件可访问性验证
- 音频时长检查
- 文件大小验证
- 音频格式支持性检查

### 🎯 ASR发音准确性检查（新增）
- 下载并分析音频内容
- 使用ASR服务识别音频文本
- 计算识别文本与预期文本的相似度
- 支持多种ASR服务提供商

## 支持的ASR服务

### 1. 腾讯云ASR
- **优势**: 中文识别准确率高，响应速度快
- **配置**: 需要Secret ID和Secret Key
- **语言支持**: 中文优先

### 2. Google Speech-to-Text
- **优势**: 多语言支持，识别准确率高
- **配置**: 需要服务账号JSON文件
- **语言支持**: 多语言

### 3. 百度AI ASR
- **优势**: 中文识别优秀，免费额度较高
- **配置**: 需要App ID、API Key、Secret Key
- **语言支持**: 中文优先

### 4. 阿里云ASR
- **优势**: 稳定性好，企业级服务
- **配置**: 需要Access Key ID和Secret
- **语言支持**: 中文优先

### 5. 模拟服务（默认）
- **优势**: 无需配置，用于测试
- **配置**: 无需配置
- **语言支持**: 所有语言（模拟结果）

## 配置步骤

### 步骤1: 配置环境变量

在系统环境变量或`.env`文件中设置相应的API密钥：

```bash
# 腾讯云ASR配置
export TENCENT_SECRET_ID="your_secret_id"
export TENCENT_SECRET_KEY="your_secret_key"

# Google Speech-to-Text配置
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# 百度AI ASR配置
export BAIDU_ASR_APP_ID="your_app_id"
export BAIDU_ASR_API_KEY="your_api_key"
export BAIDU_ASR_SECRET_KEY="your_secret_key"

# 阿里云ASR配置
export ALIYUN_ACCESS_KEY_ID="your_access_key_id"
export ALIYUN_ACCESS_KEY_SECRET="your_access_key_secret"
export ALIYUN_ASR_APP_KEY="your_app_key"
```

### 步骤2: 启用ASR服务

在`asr_config.py`中启用所需的服务：

```python
# 启用腾讯云ASR
TENCENT_CONFIG = {
    "enabled": True,  # 改为True启用
    "secret_id": os.getenv("TENCENT_SECRET_ID", ""),
    "secret_key": os.getenv("TENCENT_SECRET_KEY", ""),
    # ... 其他配置
}
```

### 步骤3: 验证配置

运行配置验证脚本：

```bash
python asr_config.py
```

输出示例：
```
配置验证结果:
有效: True
可用服务: ['tencent', 'google']
错误: []
警告: []
```

## 使用示例

### 基本使用

```python
from tts_quality_check_node import main

# 输入数据
tts_files = [
    {
        "url": "http://example.com/audio.wav",
        "size": 181484,
        "mime_type": "audio/wav",
        "extension": ".wav"
    }
]

expected_texts = "哎哟，秒躺俩 那肯定吃鸡！"
retry_count = 0
language = "zh"

# 执行质量检查
result = main(tts_files, expected_texts, retry_count, language)

print(f"质量分数: {result['overall_quality_score']:.2f}")
print(f"ASR相似度: {result['validation_results'][0]['pronunciation_similarity']:.2f}")
print(f"是否需要重试: {result['needs_retry']}")
```

### 输出结果说明

质量检查节点返回丰富的输出信息：

```json
{
  "validation_results": [
    {
      "audio_index": 0,
      "expected_text": "哎哟，秒躺俩 那肯定吃鸡！",
      "audio_url": "http://...",
      "passed": true,
      "quality_score": 0.85,
      "asr_result": "哎哟秒躺俩那肯定吃鸡",
      "pronunciation_similarity": 0.92,
      "checks": {
        "accessibility": {"passed": true, "status_code": 200},
        "duration": {"passed": true, "duration": 2.5},
        "asr": {"passed": true, "similarity": 0.92}
      }
    }
  ],
  "all_acceptable": "yes",
  "workflow_status": "completed",
  "overall_quality_score": 0.85,
  "needs_retry": "no",
  "asr_config_status": {
    "valid": true,
    "available_services": ["tencent"],
    "errors": [],
    "warnings": []
  }
}
```

## 高级配置

### 调整相似度阈值

在质量检查节点中调整ASR相似度阈值：

```python
# 在DEFAULT_CONFIG中修改
DEFAULT_CONFIG = {
    "quality_threshold": 0.8,
    "asr_similarity_threshold": 0.7,  # 调整此值
    "enable_asr_check": True
}
```

### 禁用ASR检查

如果只需要基础质量检查，可以禁用ASR：

```python
DEFAULT_CONFIG = {
    "quality_threshold": 0.8,
    "enable_asr_check": False  # 禁用ASR检查
}
```

## 故障排除

### 常见问题

1. **ASR服务调用失败**
   - 检查API密钥配置
   - 验证网络连接
   - 查看错误日志

2. **相似度过低**
   - 调整相似度阈值
   - 检查音频质量
   - 验证预期文本格式

3. **配置验证失败**
   - 检查环境变量设置
   - 验证配置文件格式
   - 查看验证错误信息

### 调试模式

启用详细日志输出：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 性能优化

### 批量处理

对于大量音频文件，建议：
- 使用异步处理
- 设置合理的超时时间
- 分批处理避免API限制

### 缓存策略

- 缓存ASR识别结果
- 避免重复识别相同音频
- 设置合理的缓存过期时间

## 安全考虑

### API密钥安全
- 不要将API密钥硬编码在代码中
- 使用环境变量或密钥管理服务
- 定期轮换API密钥

### 数据传输安全
- 使用HTTPS传输音频数据
- 加密敏感信息
- 验证服务端证书

## 扩展开发

### 添加新的ASR服务

1. 在`asr_config.py`中添加服务配置
2. 在`tts_quality_check_node.py`中实现服务函数
3. 更新服务选择逻辑

### 自定义相似度算法

修改`_calculate_text_similarity`函数，实现自定义的文本相似度算法。

## 支持与反馈

如有问题或建议，请联系开发团队或提交Issue。