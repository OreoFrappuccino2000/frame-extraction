# Dify工作流中WhisperX ASR配置指南

## 问题描述
当前TTS质量检查节点输出显示："WhisperX不可用，跳过ASR检查"，需要正确配置环境以启用WhisperX。

## 解决方案

### 1. Dify工作流环境变量配置

在Dify工作流的**环境变量**设置中，添加以下配置：

```bash
# Python包安装配置
PIP_INDEX_URL=https://pypi.org/simple/
PIP_TRUSTED_HOST=pypi.org

# WhisperX相关配置
WHISPERX_MODEL_SIZE=tiny  # 或 base，根据内存选择
WHISPERX_DEVICE=cpu
WHISPERX_COMPUTE_TYPE=int8

# 网络配置（如果需要代理）
HTTP_PROXY=http://your-proxy:port
HTTPS_PROXY=https://your-proxy:port

# 内存优化
PYTHONUNBUFFERED=1
PYTHONIOENCODING=utf-8
```

### 2. 代码节点依赖管理

当前代码已包含自动安装逻辑，但需要确保Dify环境允许安装第三方包。

#### 检查Dify配置：
1. 进入Dify控制台
2. 找到你的工作流
3. 检查代码节点的"允许安装依赖"选项是否启用
4. 确保网络连接正常（用于下载WhisperX和模型）

### 3. 手动安装方案（如果自动安装失败）

如果自动安装失败，可以在Dify代码节点的**依赖管理**部分手动添加：

```txt
whisperx>=3.1.1
torch>=2.0.0
torchaudio>=2.0.0
numpy>=1.21.0
ffmpeg-python>=0.2.0
```

### 4. 验证配置

修改后的代码包含详细的调试信息，运行时会显示：

```
检查WhisperX依赖...
WhisperX未安装，正在自动安装...
成功安装: whisperx
WhisperX安装成功
加载WhisperX模型: tiny
加载音频文件...
开始语音识别...
WhisperX识别成功: 没毛病...
```

### 5. 故障排除

#### 常见问题及解决方案：

**问题1: 网络连接失败**
```bash
# 解决方案：检查网络配置或使用代理
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=https://proxy.example.com:8080
```

**问题2: 内存不足**
```bash
# 解决方案：使用更小的模型
WHISPERX_MODEL_SIZE=tiny
```

**问题3: 下载模型失败**
```bash
# 解决方案：设置模型下载路径
WHISPER_CACHE_DIR=./models
```

**问题4: 权限问题**
```bash
# 解决方案：确保有写入权限
chmod 755 /path/to/dify/cache
```

### 6. 性能优化建议

#### 内存优化：
- 使用`tiny`模型（约75MB）
- 启用`int8`量化
- 设置较小的`batch_size`

#### 速度优化：
- 确保网络连接稳定
- 使用本地缓存模型
- 避免重复下载模型

### 7. 测试验证

运行测试用例验证配置：

```python
# 测试WhisperX是否正常工作
def test_whisperx():
    try:
        import whisperx
        model = whisperx.load_model("tiny", "cpu")
        print("✅ WhisperX配置成功")
        return True
    except Exception as e:
        print(f"❌ WhisperX配置失败: {e}")
        return False

test_whisperx()
```

### 8. 监控和日志

代码已添加详细的日志输出，可以在Dify日志中查看：
- 依赖安装状态
- 模型加载进度
- 识别过程
- 错误信息

### 9. 备用方案

如果WhisperX仍然无法使用，可以考虑：

1. **使用其他ASR服务**：修改代码使用腾讯云、百度AI等
2. **简化质量检查**：禁用ASR检查，只进行基础质量验证
3. **手动上传模型**：将预训练模型上传到Dify文件系统

## 总结

按照以上步骤配置后，WhisperX应该能够正常工作。关键点：

1. ✅ 确保Dify环境允许安装第三方包
2. ✅ 配置正确的环境变量
3. ✅ 检查网络连接
4. ✅ 监控日志输出排查问题

配置成功后，TTS质量检查将包含准确的发音相似度评估！