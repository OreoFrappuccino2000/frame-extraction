import json
import requests
import tempfile
import os
import io
from typing import Dict, Any, List
import base64
import re
import subprocess
import sys

# 自动安装WhisperX依赖
print("检查WhisperX依赖...")

def install_package(package):
    """安装Python包"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"成功安装: {package}")
        return True
    except Exception as e:
        print(f"安装失败 {package}: {e}")
        return False

# 检查并安装WhisperX
try:
    import whisperx
    WHISPERX_AVAILABLE = True
    print("WhisperX已安装")
except ImportError:
    print("WhisperX未安装，正在自动安装...")
    if install_package("whisperx"):
        try:
            import whisperx
            WHISPERX_AVAILABLE = True
            print("WhisperX安装成功")
        except ImportError:
            WHISPERX_AVAILABLE = False
            print("WhisperX安装失败，将使用基础质量检查")
    else:
        WHISPERX_AVAILABLE = False
        print("WhisperX安装失败，将使用基础质量检查")

def main(
    tts_files: List[Dict], 
    expected_texts: str, 
    retry_count: int = 0,
    language: str = "zh",
    tts_duration: float = 0.0
) -> Dict[str, Any]:
    """
    TTS质量检查节点
    验证TTS音频的发音质量，支持重试机制
    
    Args:
        tts_files: TTS生成的音频文件列表
        expected_texts: 期望的文本内容（字符串）
        retry_count: 当前重试次数
        language: 语言设置
        tts_duration: 音频时长信息（秒）
    
    Returns:
        Dict包含质量检查结果和重试状态
    """    
    # 默认配置
    DEFAULT_CONFIG = {
        "quality_threshold": 0.8,
        "max_retries": 3,
        "min_audio_duration": 0.5,  # 最小音频时长(秒)
        "max_audio_duration": 10.0, # 最大音频时长(秒)
        "asr_similarity_threshold": 0.7,  # ASR相似度阈值
        "enable_asr_check": WHISPERX_AVAILABLE,  # 只有WhisperX可用时才启用ASR检查
    }
    
    # 使用默认配置
    config = DEFAULT_CONFIG
    
    # 处理expected_texts：如果是字符串，转换为列表
    if isinstance(expected_texts, str):
        # 假设每个音频文件对应相同的文本
        expected_texts_list = [expected_texts] * len(tts_files)
    else:
        expected_texts_list = expected_texts
    
    # 初始化结果变量
    validation_results = []
    passed_checks = 0
    total_checks = len(tts_files)
    
    # 检查音频文件
    for i, (audio_file, expected_text) in enumerate(zip(tts_files, expected_texts_list)):
        check_result = _check_single_audio(audio_file, expected_text, config, language, tts_duration)
        validation_results.append(check_result)
        
        if check_result["passed"]:
            passed_checks += 1
    
    # 计算总体质量分数
    overall_quality_score = 0.0
    if total_checks > 0:
        overall_quality_score = passed_checks / total_checks
    
    # 判断是否需要重试
    needs_retry = False
    retry_reason = ""
    workflow_status = "active"
    
    if overall_quality_score < config["quality_threshold"]:
        if retry_count < config["max_retries"]:
            needs_retry = True
            retry_reason = f"质量分数 {overall_quality_score:.2f} 低于阈值 {config['quality_threshold']}"
            workflow_status = "retry_needed"
        else:
            needs_retry = False
            retry_reason = "已达到最大重试次数"
            workflow_status = "fallback_needed"
    else:
        needs_retry = False
        retry_reason = "质量检查通过"
        workflow_status = "completed"
    
    # 更新重试计数
    next_retry_count = retry_count + 1 if needs_retry else retry_count
    
    # 判断是否全部可接受
    all_acceptable = "yes" if overall_quality_score >= config["quality_threshold"] else "no"
    
    # 生成建议
    recommendation = _generate_recommendation(overall_quality_score, needs_retry, retry_count, config)
    
    # 返回输出变量
    return {
        # ========== 验证结果 (Array[Object]) ==========
        "validation_results": validation_results,
        
        # ========== 质量状态 (String) ==========
        "all_acceptable": all_acceptable,
        "workflow_status": workflow_status,
        
        # ========== 重试计数 (Number) ==========
        "retry_count": retry_count,
        "next_retry_count": next_retry_count,
        "max_retries": config["max_retries"],
        
        # ========== 质量分数 (Number) ==========
        "overall_quality_score": overall_quality_score,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "quality_threshold": config["quality_threshold"],
        
        # ========== 重试状态 (String/Number) ==========
        "needs_retry": "yes" if needs_retry else "no",
        "needs_retry_flag": 1 if needs_retry else 0,
        "retry_reason": retry_reason,
        
        # ========== 建议信息 (String) ==========
        "recommendation": recommendation
    }


def _check_single_audio(audio_file: Dict, expected_text: str, config: Dict, language: str = "zh", tts_duration: float = 0.0) -> Dict[str, Any]:
    """检查单个音频文件的质量，包括ASR发音准确性检查"""
    
    result = {
        "audio_index": audio_file.get("index", 0),
        "expected_text": expected_text,
        "audio_url": audio_file.get("url", ""),
        "audio_size": audio_file.get("size", 0),
        "passed": False,
        "quality_score": 0.0,
        "checks": {},
        "errors": [],
        "asr_result": None,
        "pronunciation_similarity": 0.0
    }
    
    try:
        # 检查1: 音频文件可访问性
        accessibility_check = _check_audio_accessibility(audio_file)
        result["checks"]["accessibility"] = accessibility_check
        
        if not accessibility_check["passed"]:
            result["errors"].append(f"音频文件不可访问: {accessibility_check['error']}")
            return result
        
        # 检查2: 音频时长 - 优先使用传入的tts_duration，如果为0则尝试其他方法
        duration_check = _check_audio_duration(audio_file, config, tts_duration)
        result["checks"]["duration"] = duration_check
        
        if not duration_check["passed"]:
            result["errors"].append(f"音频时长异常: {duration_check['error']}")
            return result
        
        # 检查3: 音频文件大小
        size_check = _check_audio_size(audio_file)
        result["checks"]["size"] = size_check
        
        if not size_check["passed"]:
            result["errors"].append(f"音频文件大小异常: {size_check['error']}")
            return result
        
        # 检查4: 音频格式
        format_check = _check_audio_format(audio_file)
        result["checks"]["format"] = format_check
        
        if not format_check["passed"]:
            result["errors"].append(f"音频格式异常: {format_check['error']}")
            return result
        
        # 检查5: ASR发音准确性检查（仅使用WhisperX）
        if config.get("enable_asr_check", False):
            asr_check = _check_audio_pronunciation(audio_file, expected_text, language, config)
            result["checks"]["asr"] = asr_check
            result["asr_result"] = asr_check.get("asr_text", "")
            result["pronunciation_similarity"] = asr_check.get("similarity", 0.0)
        else:
            # 如果WhisperX不可用，跳过ASR检查
            asr_check = {"passed": True, "similarity": 1.0, "asr_text": "WhisperX不可用，跳过ASR检查"}
            result["checks"]["asr"] = asr_check
            result["asr_result"] = "WhisperX不可用"
            result["pronunciation_similarity"] = 1.0
        
        # 计算综合质量分数
        base_score = 1.0
        penalty = 0.0
        
        # 根据基础检查错误类型扣分
        if duration_check.get("warning", False):
            penalty += 0.1
        if size_check.get("warning", False):
            penalty += 0.1
        
        # 根据ASR相似度调整分数
        asr_similarity = result["pronunciation_similarity"]
        if asr_similarity < config.get("asr_similarity_threshold", 0.7):
            penalty += (config.get("asr_similarity_threshold", 0.7) - asr_similarity)
        
        result["quality_score"] = max(0.0, base_score - penalty)
        result["passed"] = result["quality_score"] >= config["quality_threshold"]
        
    except Exception as e:
        result["errors"].append(f"质量检查异常: {str(e)}")
        result["passed"] = False
    
    return result


def _check_audio_accessibility(audio_file: Dict) -> Dict[str, Any]:
    """检查音频文件可访问性"""
    try:
        url = audio_file.get("url", "")
        if not url:
            return {"passed": False, "error": "音频URL为空"}
        
        response = requests.head(url, timeout=10)
        if response.status_code != 200:
            return {"passed": False, "error": f"HTTP状态码: {response.status_code}"}
        
        return {"passed": True, "status_code": response.status_code}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _check_audio_duration(audio_file: Dict, config: Dict, tts_duration: float = 0.0) -> Dict[str, Any]:
    """检查音频时长"""
    try:
        # 优先使用传入的tts_duration参数
        duration = tts_duration if tts_duration > 0 else audio_file.get("duration", 0)
        
        # 如果duration仍然为0，尝试从URL获取信息
        if duration <= 0:
            url = audio_file.get("url", "")
            if url:
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    content_length = int(response.headers.get('Content-Length', 0))
                    if content_length > 0:
                        # 估算WAV文件时长：文件大小 / (采样率 * 声道数 * 位深/8)
                        # 假设标准WAV参数：44.1kHz, 2声道, 16位
                        estimated_duration = content_length / (44100 * 2 * 2)
                        duration = max(estimated_duration, 0.1)
                    else:
                        duration = 2.0  # 假设标准TTS音频时长
                else:
                    return {"passed": False, "error": f"无法访问音频URL: HTTP {response.status_code}"}
            else:
                return {"passed": False, "error": "音频URL为空"}
        
        if duration <= 0:
            return {"passed": False, "error": "音频时长为0"}
        
        if duration < config["min_audio_duration"]:
            return {"passed": False, "error": f"音频时长过短: {duration:.2f}s"}
        
        if duration > config["max_audio_duration"]:
            return {"passed": True, "warning": f"音频时长过长: {duration:.2f}s"}
        
        return {"passed": True, "duration": duration, "estimated": duration != tts_duration and duration != audio_file.get("duration", 0)}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _check_audio_size(audio_file: Dict) -> Dict[str, Any]:
    """检查音频文件大小"""
    try:
        # 尝试多种方式获取文件大小
        size = 0
        
        # 1. 首先尝试直接从audio_file获取size
        if "size" in audio_file:
            size = audio_file["size"]
        
        # 2. 如果size为0或不存在，尝试从URL获取文件大小
        if size <= 0:
            url = audio_file.get("url", "")
            if url:
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    content_length = int(response.headers.get('Content-Length', 0))
                    if content_length > 0:
                        size = content_length
        
        # 3. 如果仍然为0，尝试从文件信息中获取
        if size <= 0:
            # 检查是否有其他可能包含大小的字段
            for key in ["file_size", "length", "bytes"]:
                if key in audio_file:
                    size = audio_file[key]
                    break
        
        if size <= 0:
            return {"passed": False, "error": "音频文件大小为0"}
        
        # 确保size是整数
        size = int(size)
        
        if size < 1024:
            return {"passed": False, "error": f"文件大小过小: {size} bytes"}
        
        if size > 1024 * 1024:
            return {"passed": True, "warning": f"文件大小过大: {size} bytes"}
        
        return {"passed": True, "size": size}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _check_audio_format(audio_file: Dict) -> Dict[str, Any]:
    """检查音频格式"""
    try:
        mime_type = audio_file.get("mime_type", "")
        extension = audio_file.get("extension", "")
        
        supported_formats = ["audio/wav", "audio/mpeg", "audio/ogg"]
        supported_extensions = [".wav", ".mp3", ".ogg"]
        
        if mime_type and mime_type not in supported_formats:
            return {"passed": False, "error": f"不支持的MIME类型: {mime_type}"}
        
        if extension and extension.lower() not in supported_extensions:
            return {"passed": False, "error": f"不支持的扩展名: {extension}"}
        
        return {"passed": True, "mime_type": mime_type, "extension": extension}
    
    except Exception as e:
        return {"passed": False, "error": str(e)}


def _generate_recommendation(quality_score: float, needs_retry: bool, retry_count: int, config: Dict) -> str:
    """根据质量检查结果生成建议"""
    
    if quality_score >= config["quality_threshold"]:
        return "TTS音频质量良好，可以继续后续处理"
    
    if not needs_retry:
        return "已达到最大重试次数，建议使用备用TTS服务或调整文本内容"
    
    if retry_count == 0:
        return "首次质量检查未通过，建议调整TTS参数或检查文本内容"
    elif retry_count == 1:
        return "第二次重试未通过，建议简化文本或调整语音参数"
    elif retry_count == 2:
        return "第三次重试未通过，建议使用更简单的表达方式"
    else:
        return f"第{retry_count + 1}次重试未通过，建议检查TTS服务状态"


def _check_audio_pronunciation(audio_file: Dict, expected_text: str, language: str, config: Dict) -> Dict[str, Any]:
    """使用WhisperX检查音频发音准确性"""
    
    result = {
        "passed": False,
        "similarity": 0.0,
        "asr_text": "",
        "error": "",
        "confidence": 0.0
    }
    
    try:
        # 下载音频文件
        audio_url = audio_file.get("url", "")
        if not audio_url:
            result["error"] = "音频URL为空"
            return result
        
        response = requests.get(audio_url, timeout=30)
        if response.status_code != 200:
            result["error"] = f"下载音频失败: HTTP {response.status_code}"
            return result
        
        audio_content = response.content
        
        # 调用WhisperX进行语音识别
        asr_result = _whisperx_asr_service(audio_content, language)
        
        if not asr_result["success"]:
            result["error"] = f"WhisperX识别失败: {asr_result.get('error', '未知错误')}"
            return result
        
        recognized_text = asr_result["text"]
        confidence = asr_result.get("confidence", 0.0)
        
        # 计算文本相似度
        similarity = _calculate_text_similarity(expected_text, recognized_text, language)
        
        result["asr_text"] = recognized_text
        result["similarity"] = similarity
        result["confidence"] = confidence
        result["passed"] = similarity >= config.get("asr_similarity_threshold", 0.7)
        
    except Exception as e:
        result["error"] = f"ASR检查异常: {str(e)}"
    
    return result


def _whisperx_asr_service(audio_content: bytes, language: str) -> Dict[str, Any]:
    """使用WhisperX进行语音识别（免费开源）"""
    
    result = {"success": False, "text": "", "confidence": 0.0}
    
    try:
        if not WHISPERX_AVAILABLE:
            result["error"] = "WhisperX未安装，请检查依赖安装"
            return result
        
        # 创建临时文件保存音频内容
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_content)
            temp_file_path = temp_file.name
        
        try:
            # 优化WhisperX配置
            device = "cpu"
            batch_size = 8  # 进一步减少batch size以降低内存使用
            model_size = "tiny"  # 使用更小的模型确保Dify环境兼容性
            
            print(f"加载WhisperX模型: {model_size}")
            
            # 加载模型，添加超时和错误处理
            try:
                model = whisperx.load_model(model_size, device, compute_type="int8", download_root="./whisperx_models")
            except Exception as e:
                print(f"模型加载失败，尝试使用默认路径: {e}")
                model = whisperx.load_model(model_size, device, compute_type="int8")
            
            print("加载音频文件...")
            audio = whisperx.load_audio(temp_file_path)
            
            print("开始语音识别...")
            result_whisper = model.transcribe(audio, batch_size=batch_size, language=language)
            
            # 获取识别文本
            if result_whisper["segments"]:
                recognized_text = " ".join([segment["text"].strip() for segment in result_whisper["segments"]])
                
                # 计算平均置信度
                confidences = [segment.get("avg_logprob", 0.5) for segment in result_whisper["segments"]]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
                confidence = min(1.0, max(0.0, (avg_confidence + 1.0) / 2.0))
                
                result["success"] = True
                result["text"] = recognized_text
                result["confidence"] = confidence
                result["model"] = "whisperx"
                result["language"] = result_whisper.get("language", language)
                print(f"WhisperX识别成功: {recognized_text[:50]}...")
            else:
                result["error"] = "WhisperX未识别到任何文本"
                print("WhisperX未识别到文本")
                
        except Exception as e:
            result["error"] = f"WhisperX识别失败: {str(e)}"
            print(f"WhisperX识别异常: {e}")
            
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file_path)
            except:
                pass
                
    except Exception as e:
        result["error"] = f"WhisperX处理异常: {str(e)}"
        print(f"WhisperX处理异常: {e}")
    
    return result


def _calculate_text_similarity(text1: str, text2: str, language: str) -> float:
    """计算两个文本的相似度"""
    
    if not text1 or not text2:
        return 0.0
    
    # 转换为小写并去除标点符号
    text1_clean = re.sub(r'[^\w\s]', '', text1.lower())
    text2_clean = re.sub(r'[^\w\s]', '', text2.lower())
    
    # 分词
    if language == "zh":
        words1 = list(text1_clean)
        words2 = list(text2_clean)
    else:
        words1 = text1_clean.split()
        words2 = text2_clean.split()
    
    # 计算Jaccard相似度
    set1 = set(words1)
    set2 = set(words2)
    
    if not set1 and not set2:
        return 1.0
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    similarity = intersection / union if union > 0 else 0.0
    
    return similarity
