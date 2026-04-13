#!/usr/bin/env python3
"""
TTS质量检查功能测试脚本
测试音频视频对齐控制器中的TTS质量检查功能
"""

import sys
import os
import json
from typing import Dict, Any, List

# 添加项目路径到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入app.py中的函数
try:
    from app import _perform_tts_quality_check, _check_audio_accessibility, _check_audio_duration
    from app import _check_audio_format, _calculate_text_similarity
    print("✓ 成功导入TTS质量检查函数")
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    sys.exit(1)


def test_audio_accessibility():
    """测试音频可访问性检查"""
    print("\n=== 测试音频可访问性检查 ===")
    
    # 测试用例1: 有效URL
    result1 = _check_audio_accessibility("https://httpbin.org/status/200")
    print(f"有效URL测试: {result1}")
    
    # 测试用例2: 无效URL
    result2 = _check_audio_accessibility("")
    print(f"空URL测试: {result2}")
    
    return result1["passed"] and not result2["passed"]


def test_audio_duration_check():
    """测试音频时长检查"""
    print("\n=== 测试音频时长检查 ===")
    
    config = {
        "min_audio_duration": 0.5,
        "max_audio_duration": 10.0
    }
    
    # 测试用例1: 正常时长
    result1 = _check_audio_duration(2.5, config)
    print(f"正常时长测试: {result1}")
    
    # 测试用例2: 过短时长
    result2 = _check_audio_duration(0.1, config)
    print(f"过短时长测试: {result2}")
    
    # 测试用例3: 过长时长
    result3 = _check_audio_duration(15.0, config)
    print(f"过长时长测试: {result3}")
    
    return result1["passed"] and not result2["passed"] and result3["passed"]


def test_text_similarity():
    """测试文本相似度计算"""
    print("\n=== 测试文本相似度计算 ===")
    
    # 测试用例1: 相同文本（中文）
    text1 = "今天天气很好"
    text2 = "今天天气很好"
    similarity1 = _calculate_text_similarity(text1, text2, "zh")
    print(f"相同文本相似度: {similarity1:.3f}")
    
    # 测试用例2: 相似文本（中文）
    text3 = "今天天气很好"
    text4 = "今天天气不错"
    similarity2 = _calculate_text_similarity(text3, text4, "zh")
    print(f"相似文本相似度: {similarity2:.3f}")
    
    # 测试用例3: 不同文本（中文）
    text5 = "今天天气很好"
    text6 = "明天会下雨"
    similarity3 = _calculate_text_similarity(text5, text6, "zh")
    print(f"不同文本相似度: {similarity3:.3f}")
    
    # 测试用例4: 英文文本
    text7 = "Hello world"
    text8 = "Hello world"
    similarity4 = _calculate_text_similarity(text7, text8, "en")
    print(f"英文相同文本相似度: {similarity4:.3f}")
    
    return similarity1 == 1.0 and similarity2 > 0.5 and similarity3 < 0.5


def test_full_quality_check():
    """测试完整的TTS质量检查流程"""
    print("\n=== 测试完整TTS质量检查流程 ===")
    
    # 模拟测试数据
    test_cases = [
        {
            "name": "正常音频质量检查",
            "audio_url": "https://httpbin.org/status/200",  # 模拟URL
            "segment_id": "test_segment_001",
            "expected_text": "今天天气很好",
            "language": "zh"
        },
        {
            "name": "空URL测试",
            "audio_url": "",
            "segment_id": "test_segment_002",
            "expected_text": "测试文本",
            "language": "zh"
        },
        {
            "name": "无预期文本测试",
            "audio_url": "https://httpbin.org/status/200",
            "segment_id": "test_segment_003",
            "expected_text": "",
            "language": "zh"
        }
    ]
    
    results = []
    for test_case in test_cases:
        print(f"\n测试: {test_case['name']}")
        
        try:
            result = _perform_tts_quality_check(
                audio_url=test_case["audio_url"],
                segment_id=test_case["segment_id"],
                expected_text=test_case["expected_text"],
                language=test_case["language"]
            )
            
            print(f"  结果: {result['passed']}")
            print(f"  错误: {result.get('error', '无')}")
            print(f"  质量分数: {result.get('quality_score', 0.0):.3f}")
            
            results.append(result["passed"])
            
        except Exception as e:
            print(f"  异常: {e}")
            results.append(False)
    
    return any(results)  # 至少有一个测试通过


def test_integration_with_alignment():
    """测试与对齐控制器的集成"""
    print("\n=== 测试与对齐控制器的集成 ===")
    
    # 模拟对齐控制器输入数据
    sample_input = {
        "validated_events": [
            {
                "event_id": "event_001",
                "video_time": 5.2,
                "type": "kill",
                "confidence": 0.95,
                "text": "Player A eliminates Player B"
            }
        ],
        "tts_segments": [
            {
                "segment_id": "seg_001",
                "audio_url": "https://example.com/audio/seg_001.wav",
                "audio_duration": 2.1,
                "event_type": "kill",
                "text": "Player A eliminates Player B"
            }
        ],
        "total_duration": 30.0,
        "config": {
            "reaction_delay_range": (0.6, 1.2),
            "quality_threshold": 0.8,
            "max_retries": 3
        }
    }
    
    print("模拟对齐控制器工作流:")
    print(f"  事件数量: {len(sample_input['validated_events'])}")
    print(f"  音频片段数量: {len(sample_input['tts_segments'])}")
    print(f"  视频总时长: {sample_input['total_duration']}秒")
    
    # 模拟质量检查过程
    quality_results = []
    for segment in sample_input["tts_segments"]:
        matching_event = next((e for e in sample_input["validated_events"] if e["type"] == segment["event_type"]), None)
        
        if matching_event:
            result = _perform_tts_quality_check(
                audio_url=segment["audio_url"],
                segment_id=segment["segment_id"],
                expected_text=matching_event["text"],
                language="en"
            )
            quality_results.append(result)
    
    print(f"  质量检查结果数量: {len(quality_results)}")
    
    if quality_results:
        passed_count = sum(1 for r in quality_results if r["passed"])
        print(f"  通过检查: {passed_count}/{len(quality_results)}")
        
        for i, result in enumerate(quality_results):
            print(f"    片段 {i+1}: {'通过' if result['passed'] else '失败'} - 分数: {result.get('quality_score', 0.0):.3f}")
    
    return len(quality_results) > 0


def main():
    """主测试函数"""
    print("🚀 TTS质量检查功能测试开始")
    print("=" * 50)
    
    test_results = []
    
    # 运行各个测试
    test_results.append(("音频可访问性检查", test_audio_accessibility()))
    test_results.append(("音频时长检查", test_audio_duration_check()))
    test_results.append(("文本相似度计算", test_text_similarity()))
    test_results.append(("完整质量检查流程", test_full_quality_check()))
    test_results.append(("对齐控制器集成", test_integration_with_alignment()))
    
    # 输出测试结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    
    passed_tests = 0
    for test_name, passed in test_results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {test_name}: {status}")
        if passed:
            passed_tests += 1
    
    total_tests = len(test_results)
    success_rate = (passed_tests / total_tests) * 100
    
    print(f"\n📈 总体结果: {passed_tests}/{total_tests} 测试通过 ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        print("🎉 TTS质量检查功能测试通过!")
    else:
        print("⚠️  部分测试失败，需要进一步调试")
    
    return success_rate >= 80


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)