import json
import urllib.request
import struct

def main(persona_profile_json: str, tts_response: dict = None, files: list = None) -> dict:
    """
    TTS参数初始化节点
    接收persona配置和TTS响应，输出TTS技术参数、重试配置和音频时长
    
    Args:
        persona_profile_json: Persona配置JSON字符串
        tts_response: TTS HTTP响应，包含files数组和状态信息
        files: 音频文件列表（直接传入）
    """
    
    # 解析persona配置
    persona = json.loads(persona_profile_json)
    
    # 获取语言信息
    language = persona.get("language", "zh")  # 默认中文
    
    # 提取文件信息
    tts_duration = 0.0
    
    # 优先使用直接传入的files参数，其次从tts_response中提取
    audio_files = []
    if files and isinstance(files, list):
        audio_files = files
    elif tts_response and isinstance(tts_response, dict):
        # 从TTS响应中提取files数组
        audio_files = tts_response.get("files", [])
    
    if audio_files and len(audio_files) > 0:
        tts_duration = _calculate_audio_duration(audio_files[0])
    
    # 返回核心TTS参数和音频时长
    return {
        "retry_count": 0,                    # 当前重试次数
        "max_retries": 3,                    # 最大重试次数
        "language": language,                # 使用persona的语言设置
        "quality_threshold": 0.8,            # 质量阈值
        "tts_voice_id": persona.get("tts_voice_id", ""),  # TTS语音ID
        "tts_duration": tts_duration         # 音频时长(秒)
    }

def _calculate_audio_duration(file) -> float:
    """计算音频文件的时长"""
    
    # Get URL
    try:
        url = file.url
    except Exception:
        try:
            url = file["url"]
        except Exception:
            url = None
    
    if not url:
        return 0.0
    
    try:
        # Only download first 44 bytes (WAV header)
        req = urllib.request.Request(url)
        req.add_header("Range", "bytes=0-43")
        with urllib.request.urlopen(req, timeout=5) as resp:
            header = resp.read(44)
        
        if len(header) < 44:
            return 0.0
        
        # Parse WAV header
        # Bytes 24-27: sample rate
        # Bytes 22-23: num channels
        # Bytes 34-35: bits per sample
        # Bytes 40-43: data chunk size
        num_channels = struct.unpack_from("<H", header, 22)[0]
        sample_rate = struct.unpack_from("<I", header, 24)[0]
        bits_per_sample = struct.unpack_from("<H", header, 34)[0]
        data_size = struct.unpack_from("<I", header, 40)[0]
        
        bytes_per_second = sample_rate * num_channels * (bits_per_sample // 8)
        
        if bytes_per_second == 0:
            return 0.0
        
        duration = round(data_size / bytes_per_second, 3)
        return duration
    
    except Exception:
        # Fallback: estimate from size
        try:
            size_bytes = int(file.size)
        except Exception:
            size_bytes = int(file["size"])
        
        audio_bytes = size_bytes - 44
        bytes_per_second = 16000 * 1 * 2  # fallback assumption
        if audio_bytes <= 0:
            return 0.0
        return round(audio_bytes / bytes_per_second, 3)

