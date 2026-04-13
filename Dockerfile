# 使用官方Python运行时作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（包括ffmpeg）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements-service.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements-service.txt

# 复制应用代码
COPY frame_extraction_service.py .

# 创建上传目录
RUN mkdir -p /tmp/uploads

# 设置环境变量
ENV HOST=0.0.0.0
ENV PORT=10000
ENV FFMPEG_BIN=ffmpeg
ENV FFPROBE_BIN=ffprobe
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 10000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:10000/health || exit 1

# 启动命令
CMD ["python", "frame_extraction_service.py"]