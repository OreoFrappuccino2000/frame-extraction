#!/usr/bin/env python3
"""
测试直接TTS重试功能
验证app.py是否可以直接进行HTTP请求而不依赖Dify工作流
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import _perform_tts_quality_check, _request_tts_directly, _perform_direct_tts_retry

def test_direct_tts_request():
    """测试直接TTS请求功能"""
    print("=== 测试直接TTS请求功能 ===")
    
    # 测试文本
    test_text = "没毛病"
    tts_endpoint = "http://ultrongw.woa.com/v2/tts/cyber-human/api/get_tts/sound.wav"
    
    print(f"测试文本: {test_text}")
    print(f"TTS端点: {tts_endpoint}")
    
    # 测试直接TTS请求
    print("\n1. 测试直接TTS请求...")
    tts_result = _request_tts_directly(test_text, tts_endpoint)
    
    print(f"请求成功: {tts_result['success']}")
    if tts_result['success']:
        print(f"音频URL: {tts_result.get('audio_url', 'N/A')}")
        
        # 测试质量检查
        print("\n2. 测试TTS质量检查...")
        quality_check = _perform_tts_quality_check(
            audio_url=tts_result['audio_url'],
            segment_id="test_segment_001",
            expected_text=test_text,
            language="zh",
            enable_direct_retry=True,
            tts_endpoint=tts_endpoint
        )
        
        print(f"质量检查通过: {quality_check['passed']}")
        print(f"相似度分数: {quality_check.get('similarity_score', 0):.2f}")
        print(f"ASR识别结果: {quality_check.get('asr_text', 'N/A')}")
        
        if not quality_check['passed'] and quality_check.get('retry_suggestion'):
            print(f"重试建议: {quality_check['retry_suggestion']}")
    else:
        print(f"错误信息: {tts_result.get('error', 'N/A')}")

def test_direct_tts_retry():
    """测试直接TTS重试功能"""
    print("\n=== 测试直接TTS重试功能 ===")
    
    # 使用一个已知质量较差的音频URL进行测试
    poor_quality_audio_url = "http://example.com/poor_quality_audio.wav"  # 替换为实际测试URL
    test_text = "测试文本"
    tts_endpoint = "http://ultrongw.woa.com/v2/tts/cyber-human/api/get_tts/sound.wav"
    
    print("1. 模拟质量检查失败场景...")
    
    # 模拟质量检查失败
    quality_check = _perform_tts_quality_check(
        audio_url=poor_quality_audio_url,
        segment_id="test_retry_segment",
        expected_text=test_text,
        language="zh",
        enable_direct_retry=True,
        tts_endpoint=tts_endpoint
    )
    
    print(f"初始质量检查结果: {'通过' if quality_check['passed'] else '失败'}")
    
    if not quality_check['passed'] and quality_check.get('direct_retry_available'):
        print("\n2. 执行直接TTS重试...")
        
        retry_result = _perform_direct_tts_retry(
            segment_id="test_retry_segment",
            expected_text=test_text,
            language="zh",
            tts_endpoint=tts_endpoint,
            max_retries=2
        )
        
        print(f"重试成功: {retry_result['retry_success']}")
        print(f"重试次数: {retry_result['retry_count']}")
        
        if retry_result['retry_success']:
            print(f"新音频URL: {retry_result['new_audio_url']}")
            print(f"重试后质量: {'通过' if retry_result['quality_check_result']['passed'] else '失败'}")
        else:
            print(f"重试错误: {retry_result.get('errors', [])}")

def test_integration_workflow():
    """测试集成工作流"""
    print("\n=== 测试集成工作流 ===")
    
    # 模拟完整的音频处理流程
    placements = [
        {
            "segment_id": "seg_001",
            "start_time": 0.0,
            "end_time": 2.0,
            "text": "没毛病",
            "audio_url": "http://example.com/audio1.wav"
        },
        {
            "segment_id": "seg_002", 
            "start_time": 3.0,
            "end_time": 5.0,
            "text": "测试文本",
            "audio_url": "http://example.com/audio2.wav"
        }
    ]
    
    audio_map = {
        "seg_001": "http://example.com/audio1.wav",
        "seg_002": "http://example.com/audio2.wav"
    }
    
    print("模拟音频处理流程...")
    print(f"音频片段数量: {len(placements)}")
    
    # 测试每个片段的处理
    for placement in placements:
        print(f"\n处理片段: {placement['segment_id']}")
        
        quality_check = _perform_tts_quality_check(
            audio_url=placement['audio_url'],
            segment_id=placement['segment_id'],
            expected_text=placement['text'],
            language="zh",
            enable_direct_retry=True,
            tts_endpoint="http://ultrongw.woa.com/v2/tts/cyber-human/api/get_tts/sound.wav"
        )
        
        print(f"质量检查: {'通过' if quality_check['passed'] else '失败'}")
        print(f"直接重试可用: {quality_check.get('direct_retry_available', False)}")
        
        if not quality_check['passed'] and quality_check.get('retry_suggestion'):
            print(f"建议: {quality_check['retry_suggestion']}")

if __name__ == "__main__":
    print("直接TTS重试功能测试")
    print("=" * 50)
    
    try:
        # test_direct_tts_request()
        # test_direct_tts_retry()
        test_integration_workflow()
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()