# WhisperX在Dify代码节点中的使用指南

## 概述
WhisperX是一个基于OpenAI Whisper的增强版本，提供更好的时间戳对齐和语言检测功能。它是免费开源的，非常适合在Dify代码节点中使用。

## 安装依赖

在Dify代码节点中，您需要在代码开头添加以下依赖安装命令：

```python
# 在代码开头添加这些安装命令
import subprocess
import sys

def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    import whisperx
except ImportError:
    print("正在安装WhisperX...")
    install_package("whisperx")
    import whisperx
```

## 配置说明

### 模型选择
WhisperX支持多种模型大小，根据Dify环境选择合适的模型：

- **tiny**: 最快，但准确率较低（约75MB）
- **base**: 平衡速度和准确率（约145MB）
- **small**: 较好的准确率（约460MB）
- **medium**: 高准确率（约1.5GB）
- **large**: 最高准确率（约3.1GB）

**推荐在Dify中使用base模型**，它在准确率和资源消耗之间取得良好平衡。

### 语言支持
WhisperX支持多种语言，包括：
- 中文（普通话）
- 英文
- 日语
- 韩语
- 法语
- 德语
- 西班牙语
- 等99种语言

## 使用示例

### 基本用法
```python
import whisperx

# 加载模型
device = "cpu"  # 使用CPU，适合Dify环境
model = whisperx.load_model("base", device)

# 识别音频
audio = whisperx.load_audio("audio.wav")
result = model.transcribe(audio)

# 获取识别结果
recognized_text = " ".join([segment["text"] for segment in result["segments"]])
print(f"识别结果: {recognized_text}")
```

### 在TTS质量检查中的集成
代码已自动集成WhisperX，优先级高于其他ASR服务。系统会：

1. 检查WhisperX是否可用
2. 如果可用，优先使用WhisperX进行语音识别
3. 计算识别文本与预期文本的相似度
4. 返回质量评分

## 性能优化

### 内存优化
```python
# 使用较小的模型和int8量化
model = whisperx.load_model("base", "cpu", compute_type="int8")

# 减少batch size
result = model.transcribe(audio, batch_size=16)
```

### 处理长音频
对于长音频，可以分段处理：
```python
# 分段处理长音频
chunk_length_s = 30  # 30秒一段
result = model.transcribe(audio, chunk_length_s=chunk_length_s)
```

## 故障排除

### 常见问题

1. **内存不足**
   - 使用更小的模型（tiny或base）
   - 启用int8量化
   - 减少batch size

2. **下载模型失败**
   - 检查网络连接
   - 尝试手动下载模型

3. **音频格式不支持**
   - 确保音频为WAV格式
   - 采样率建议16kHz或更高

### 错误处理
代码已包含完善的错误处理机制：
- WhisperX失败时自动降级到其他ASR服务
- 提供详细的错误信息
- 支持重试机制

## 模型下载

WhisperX首次使用时会自动下载模型。模型存储在：
- Linux/Mac: `~/.cache/whisperx/`
- Windows: `%USERPROFILE%\.cache\whisperx\`

## 性能基准

在Dify代码节点环境中（CPU）：
- **tiny模型**: 实时因子 ~0.1x（10倍实时）
- **base模型**: 实时因子 ~0.3x（3倍实时）
- **small模型**: 实时因子 ~1x（实时）

## 注意事项

1. **首次运行较慢**：需要下载模型文件
2. **内存使用**：base模型约需要500MB内存
3. **音频质量**：建议使用16kHz以上采样率的WAV文件
4. **语言检测**：WhisperX支持自动语言检测，但指定语言可以提高准确率

## 替代方案

如果WhisperX无法满足需求，可以考虑：
1. **OpenAI Whisper API**：付费但更准确
2. **Google Speech-to-Text**：需要API密钥
3. **本地Vosk模型**：完全离线但准确率较低

## 技术支持

如遇问题，请检查：
1. 依赖是否正确安装
2. 音频文件是否可访问
3. 内存是否充足
4. 网络连接是否正常