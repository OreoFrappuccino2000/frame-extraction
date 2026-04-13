# 视频帧提取服务

一个高性能的视频帧提取服务，提供RESTful API接口，支持从视频文件中提取关键帧。支持多种输入方式（文件上传和URL）和灵活的帧提取配置，可无缝集成到Dify工作流中。

## 功能特性

- 🎯 **多输入源支持**：支持文件上传和URL输入两种方式
- 🔄 **Dify集成**：原生支持Dify HTTP Request节点集成
- ⚡ **高性能**：优化的帧提取算法，支持并发处理
- 🛡️ **可靠性**：重试机制、优雅降级和错误恢复
- 📊 **监控**：健康检查、性能指标和请求统计
- 🚀 **多部署**：支持本地、Docker、云函数等多种部署方式

## 快速开始

### 环境要求

- Python 3.7+
- FFmpeg (已包含在Docker镜像中)
- 至少1GB可用内存

### 安装依赖

```bash
pip install -r requirements-service.txt
```

### 本地运行

```bash
python frame_extraction_service.py
```

服务将在 `http://localhost:5000` 启动

### 使用Docker运行

```bash
# 构建镜像
docker build -t frame-extraction-service .

# 运行容器
docker run -p 5000:5000 frame-extraction-service

# 使用docker-compose
docker-compose up
```

## API使用指南

### 健康检查

```bash
curl http://localhost:5000/health
```

响应：
```json
{
  "status": "ok",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0"
}
```

### 帧提取接口

#### 方式1：文件上传 (multipart/form-data)

```bash
curl -X POST http://localhost:5000/extract \
  -F "file=@/path/to/video.mp4" \
  -F "max_frames=10"
```

#### 方式2：URL输入 (application/json)

```bash
curl -X POST http://localhost:5000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "http://example.com/video.mp4",
    "max_frames": 10,
    "filename": "video.mp4",
    "mime_type": "video/mp4"
  }'
```

### 成功响应格式

```json
{
  "success": true,
  "frames": [
    {
      "frame_index": 0,
      "timestamp_seconds": 0.0,
      "timestamp_formatted": "00:00:00.00",
      "image_base64": "base64_encoded_image_data",
      "image_mime": "image/jpeg"
    }
  ],
  "video_duration": 120.5,
  "total_frames_extracted": 10,
  "error": null
}
```

### 错误响应格式

```json
{
  "success": false,
  "frames": [],
  "video_duration": 0.0,
  "total_frames_extracted": 0,
  "error": {
    "error_code": "UNSUPPORTED_FORMAT",
    "message": "Video format not supported",
    "details": "Supported formats: mp4, avi, mov, mkv, webm"
  }
}
```

## Dify集成指南

### 在Dify工作流中使用

1. 在Dify中添加HTTP Request节点
2. 配置节点参数：
   - **URL**: `http://your-service-url/extract_frames`
   - **Method**: `POST`
   - **Headers**: `Content-Type: multipart/form-data`
   - **Body**: 选择 `form-data` 格式

3. 添加文件变量绑定：
   - **Key**: `file`
   - **Value**: `{{#files.#0}}` (绑定第一个文件)

4. 可选参数：
   - **max_frames**: 提取的帧数（默认10）

### Dify节点代码

也可以直接使用提供的Dify节点代码：

```python
# 将 frame_extraction_node.py 内容复制到Dify自定义节点中
```

## 部署指南

### 1. 本地部署

```bash
# 克隆项目
git clone <repository-url>
cd frame-extraction-service

# 安装依赖
pip install -r requirements-service.txt

# 运行服务
python frame_extraction_service.py
```

### 2. Docker部署

```bash
# 使用预构建镜像
docker run -p 5000:5000 oreofrappuccino2000/frame-extraction:latest

# 或自定义构建
docker build -t your-registry/frame-extraction .
docker push your-registry/frame-extraction
```

### 3. Render.com部署

1. 将代码推送到GitHub仓库
2. 在Render.com连接GitHub仓库
3. 选择Web Service类型
4. 使用以下配置：
   - **Build Command**: `pip install -r requirements-service.txt`
   - **Start Command**: `python frame_extraction_service.py`

### 4. 腾讯云SCF部署

```bash
# 安装Serverless Framework
npm install -g serverless

# 配置腾讯云凭证
sls deploy
```

### 5. 其他云平台

服务支持任何支持Python的云平台：
- AWS Lambda
- Google Cloud Functions
- Azure Functions
- Heroku

## 配置参数

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PORT` | `5000` | 服务端口 |
| `MAX_FRAMES` | `10` | 默认提取帧数 |
| `MAX_FILE_SIZE` | `100MB` | 最大文件大小 |
| `MAX_PROCESSING_TIME` | `60` | 最大处理时间(秒) |
| `LOG_LEVEL` | `INFO` | 日志级别 |

### 性能配置

```python
# 在 frame_extraction_service.py 中修改
MAX_CONCURRENT_REQUESTS = 5    # 最大并发请求数
MEMORY_THRESHOLD_MB = 500      # 内存使用阈值
MAX_RETRY_ATTEMPTS = 3         # 最大重试次数
```

## 监控和日志

### 监控端点

- `/health` - 健康检查
- `/metrics` - Prometheus指标
- `/stats` - 服务统计信息

### 日志配置

日志输出到标准输出，支持结构化日志格式：

```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "INFO",
  "message": "Frame extraction completed",
  "request_id": "uuid",
  "processing_time": 2.5
}
```

## 故障排除

### 常见问题

**Q: 服务启动失败，提示FFmpeg未找到**
A: 确保FFmpeg已安装或在Docker环境中运行

**Q: 文件上传失败，提示文件过大**
A: 检查`MAX_FILE_SIZE`配置，或使用URL输入方式

**Q: Dify集成失败**
A: 确保使用`/extract_frames`端点，并正确配置form-data格式

**Q: 处理超时**
A: 增大`MAX_PROCESSING_TIME`或减少`max_frames`参数

### 调试模式

设置环境变量启用详细日志：

```bash
export LOG_LEVEL=DEBUG
python frame_extraction_service.py
```

## 开发指南

### 项目结构

```
frame-extraction-service/
├── frame_extraction_service.py  # 主服务文件
├── frame_extraction_node.py     # Dify节点代码
├── scf_handler.py              # 腾讯云SCF入口
├── Dockerfile                  # Docker配置
├── docker-compose.yml          # Docker Compose配置
├── render.yaml                 # Render.com配置
├── scf.yaml                    # 腾讯云SCF配置
├── requirements-service.txt    # 服务依赖
├── requirements-test.txt       # 测试依赖
├── test_frame_extraction.py    # 测试文件
├── pytest.ini                 # 测试配置
└── README.md                  # 本文档
```

### 运行测试

```bash
# 安装测试依赖
pip install -r requirements-test.txt

# 运行所有测试
pytest

# 运行特定测试
pytest test_frame_extraction.py::TestFrameExtractionService

# 生成覆盖率报告
pytest --cov=.
```

### 代码规范

项目使用以下工具确保代码质量：

```bash
# 代码格式化
black .

# 代码检查
flake8 .

# 类型检查
mypy .
```

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 支持

如有问题，请提交GitHub Issue或联系开发团队。