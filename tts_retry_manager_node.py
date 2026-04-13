import json
import time
from typing import Dict, Any, List

def main(
    quality_check_result: Dict[str, Any],
    tts_params: Dict[str, Any],
    original_texts: List[str],
    persona_profile: Dict[str, Any]
) -> Dict[str, Any]:
    """
    TTS重试管理节点
    根据质量检查结果决定是否重试，管理重试状态
    
    Args:
        quality_check_result: 质量检查结果
        tts_params: TTS参数配置
        original_texts: 原始文本内容
        persona_profile: Persona配置
    
    Returns:
        Dict包含重试决策和更新后的参数
    """
    
    # 提取关键信息
    needs_retry = quality_check_result.get("needs_retry", False)
    current_retry_count = quality_check_result.get("current_retry_count", 0)
    max_retries = quality_check_result.get("max_retries", 3)
    workflow_status = quality_check_result.get("workflow_status", "active")
    retry_reason = quality_check_result.get("retry_reason", "")
    
    result = {
        "should_retry": needs_retry,
        "current_retry_count": current_retry_count,
        "max_retries": max_retries,
        "workflow_status": workflow_status,
        "retry_reason": retry_reason,
        "retry_timestamp": int(time.time()),
        "updated_tts_params": tts_params.copy(),
        "texts_for_retry": original_texts.copy(),
        "persona_profile": persona_profile.copy()
    }
    
    # 如果需要重试
    if needs_retry and current_retry_count < max_retries:
        result["should_retry"] = True
        result["next_retry_count"] = current_retry_count + 1
        result["workflow_status"] = "retrying"
        
        # 更新TTS参数以优化重试
        result["updated_tts_params"] = _optimize_tts_params_for_retry(
            tts_params, 
            current_retry_count + 1,
            quality_check_result
        )
        
        # 可选：调整文本以改善TTS质量
        result["texts_for_retry"] = _adjust_texts_for_retry(
            original_texts, 
            current_retry_count + 1,
            persona_profile
        )
    
    # 如果达到最大重试次数，需要回退
    elif needs_retry and current_retry_count >= max_retries:
        result["should_retry"] = False
        result["workflow_status"] = "fallback_needed"
        result["fallback_reason"] = "已达到最大重试次数"
    
    # 如果质量检查通过
    else:
        result["should_retry"] = False
        result["workflow_status"] = "completed"
        result["quality_score"] = quality_check_result.get("overall_quality_score", 0.0)
    
    # 添加重试历史记录
    result["retry_history"] = _build_retry_history(
        current_retry_count, 
        quality_check_result,
        result["workflow_status"]
    )
    
    return result


def _optimize_tts_params_for_retry(
    tts_params: Dict[str, Any], 
    next_retry_count: int,
    quality_check_result: Dict[str, Any]
) -> Dict[str, Any]:
    """根据重试次数优化TTS参数"""
    
    optimized_params = tts_params.copy()
    
    # 根据重试次数调整参数
    if next_retry_count == 1:
        # 第一次重试：轻微调整
        optimized_params["speech_rate"] = optimized_params.get("speech_rate", 1.0) * 0.95
        optimized_params["pitch"] = optimized_params.get("pitch", 1.0) * 1.05
    
    elif next_retry_count == 2:
        # 第二次重试：中等调整
        optimized_params["speech_rate"] = optimized_params.get("speech_rate", 1.0) * 0.9
        optimized_params["pitch"] = optimized_params.get("pitch", 1.0) * 1.1
        optimized_params["volume"] = optimized_params.get("volume", 1.0) * 1.05
    
    elif next_retry_count >= 3:
        # 第三次及以后重试：显著调整
        optimized_params["speech_rate"] = optimized_params.get("speech_rate", 1.0) * 0.85
        optimized_params["pitch"] = optimized_params.get("pitch", 1.0) * 1.15
        optimized_params["volume"] = optimized_params.get("volume", 1.0) * 1.1
        optimized_params["emphasis_level"] = "high"
    
    # 根据质量检查结果调整
    quality_score = quality_check_result.get("overall_quality_score", 0.0)
    if quality_score < 0.5:
        # 质量很差，尝试更激进的调整
        optimized_params["speech_rate"] = optimized_params.get("speech_rate", 1.0) * 0.8
        optimized_params["pitch"] = optimized_params.get("pitch", 1.0) * 1.2
    
    # 添加重试标记
    optimized_params["is_retry"] = True
    optimized_params["retry_attempt"] = next_retry_count
    
    return optimized_params


def _adjust_texts_for_retry(
    texts: List[str], 
    next_retry_count: int,
    persona_profile: Dict[str, Any]
) -> List[str]:
    """根据重试次数调整文本以改善TTS质量"""
    
    adjusted_texts = []
    
    for text in texts:
        adjusted_text = text
        
        # 根据重试次数应用不同的调整策略
        if next_retry_count == 1:
            # 第一次重试：简化标点
            adjusted_text = text.replace("！", "。").replace("？", "。")
        
        elif next_retry_count == 2:
            # 第二次重试：拆分长句
            if len(text) > 20:
                # 简单的句子拆分逻辑
                if "，" in text:
                    parts = text.split("，")
                    if len(parts) > 1:
                        adjusted_text = parts[0] + "。"
                elif "." in text:
                    parts = text.split(".")
                    if len(parts) > 1:
                        adjusted_text = parts[0] + "."
        
        elif next_retry_count >= 3:
            # 第三次重试：使用更简单的表达
            # 这里可以添加更复杂的文本简化逻辑
            adjusted_text = text
        
        # 根据persona语言调整
        language = persona_profile.get("language", "zh")
        if language == "zh":
            # 中文特定调整
            adjusted_text = adjusted_text.replace("  ", " ").strip()
        else:
            # 英文特定调整
            adjusted_text = adjusted_text.replace("  ", " ").strip()
        
        adjusted_texts.append(adjusted_text)
    
    return adjusted_texts


def _build_retry_history(
    current_retry_count: int,
    quality_check_result: Dict[str, Any],
    workflow_status: str
) -> List[Dict[str, Any]]:
    """构建重试历史记录"""
    
    history = []
    
    # 添加当前重试记录
    current_record = {
        "retry_count": current_retry_count,
        "timestamp": int(time.time()),
        "quality_score": quality_check_result.get("overall_quality_score", 0.0),
        "passed_checks": quality_check_result.get("passed_checks", 0),
        "total_checks": quality_check_result.get("total_checks", 0),
        "workflow_status": workflow_status,
        "retry_reason": quality_check_result.get("retry_reason", "")
    }
    
    history.append(current_record)
    
    return history


# 测试函数
if __name__ == "__main__":
    # 测试数据
    test_quality_check = {
        "needs_retry": True,
        "current_retry_count": 0,
        "max_retries": 3,
        "workflow_status": "retry_needed",
        "retry_reason": "质量分数 0.6 低于阈值 0.8",
        "overall_quality_score": 0.6,
        "passed_checks": 1,
        "total_checks": 2
    }
    
    test_tts_params = {
        "speech_rate": 1.0,
        "pitch": 1.0,
        "volume": 1.0
    }
    
    test_texts = ["这是一个测试文本", "另一个测试句子"]
    test_persona = {"language": "zh"}
    
    result = main(test_quality_check, test_tts_params, test_texts, test_persona)
    print(json.dumps(result, indent=2, ensure_ascii=False))