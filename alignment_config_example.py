"""
音频视频对齐控制器配置示例
展示如何使用alignment_controller_node进行精准的音频插入与视频事件对齐
"""

import json
from typing import Dict, Any, List

# 示例配置
ALIGNMENT_CONFIG = {
    "reaction_delay_range": (0.6, 1.2),  # 反应延迟范围（秒）
    "conflict_resolution_rules": {
        "priority_order": ["kill", "knock", "damage", "movement"],
        "priority_weights": {
            "kill": 1,      # 最高优先级：击杀事件
            "knock": 2,     # 高优先级：击倒事件
            "damage": 3,    # 中等优先级：伤害事件
            "movement": 4   # 低优先级：移动事件
        },
        "merge_threshold": 1.0,    # 合并阈值（秒）
        "max_delay": 3.0,          # 最大延迟时间（秒）
        "min_gap": 0.1             # 最小间隔（秒）
    },
    "audio_quality_thresholds": {
        "min_duration": 0.1,       # 最小音频时长（秒）
        "max_duration": 10.0,      # 最大音频时长（秒）
        "quality_score": 0.8       # 最低质量分数
    },
    "performance_settings": {
        "max_concurrent_processing": 5,  # 最大并发处理数
        "cache_enabled": True,           # 启用缓存
        "batch_size": 10                 # 批处理大小
    }
}


def create_sample_input() -> Dict[str, Any]:
    """创建示例输入数据"""
    
    # 示例验证后的事件数据（来自skills校验层）
    validated_events = [
        {
            "event_id": "event_001",
            "video_time": 5.2,           # 事件发生的视频时间（秒）
            "type": "kill",              # 事件类型
            "confidence": 0.95,          # 置信度
            "actor": "player_A",         # 行动者
            "target": "player_B",        # 目标
            "weapon": "AK47",            # 武器
            "multi_kill": False          # 是否多杀
        },
        {
            "event_id": "event_002", 
            "video_time": 8.7,
            "type": "knock",
            "confidence": 0.88,
            "actor": "player_C",
            "target": "player_D",
            "weapon": "M4A1"
        },
        {
            "event_id": "event_003",
            "video_time": 12.3,
            "type": "damage",
            "confidence": 0.75,
            "actor": "player_E",
            "target": "player_F",
            "damage": 45
        },
        {
            "event_id": "event_004",
            "video_time": 15.8,
            "type": "movement",
            "confidence": 0.82,
            "actor": "player_G",
            "action": "reposition"
        }
    ]
    
    # 示例TTS生成的音频片段
    tts_segments = [
        {
            "segment_id": "seg_001",
            "audio_url": "http://example.com/audio/seg_001.wav",
            "audio_duration": 2.1,      # 真实音频时长（秒）
            "event_type": "kill",
            "text": "Player A eliminates Player B with AK47",
            "quality_score": 0.92
        },
        {
            "segment_id": "seg_002",
            "audio_url": "http://example.com/audio/seg_002.wav", 
            "audio_duration": 1.8,
            "event_type": "knock",
            "text": "Player C knocks down Player D",
            "quality_score": 0.89
        },
        {
            "segment_id": "seg_003",
            "audio_url": "http://example.com/audio/seg_003.wav",
            "audio_duration": 1.5,
            "event_type": "damage",
            "text": "Player E deals 45 damage to Player F",
            "quality_score": 0.85
        },
        {
            "segment_id": "seg_004",
            "audio_url": "http://example.com/audio/seg_004.wav",
            "audio_duration": 1.2,
            "event_type": "movement",
            "text": "Player G repositions for better angle",
            "quality_score": 0.88
        }
    ]
    
    return {
        "validated_events": validated_events,
        "tts_segments": tts_segments,
        "total_duration": 30.0,  # 视频总时长（秒）
        "config": ALIGNMENT_CONFIG
    }


def demonstrate_alignment_workflow():
    """演示对齐工作流"""
    
    # 1. 准备输入数据
    sample_input = create_sample_input()
    
    print("=== 音频视频对齐工作流演示 ===")
    print(f"视频总时长: {sample_input['total_duration']}秒")
    print(f"事件数量: {len(sample_input['validated_events'])}")
    print(f"音频片段数量: {len(sample_input['tts_segments'])}")
    
    # 2. 导入对齐控制器
    try:
        from alignment_controller_node import main as alignment_controller
    except ImportError:
        print("错误: 无法导入alignment_controller_node")
        return
    
    # 3. 执行对齐计算
    print("\n--- 执行音频对齐计算 ---")
    
    result = alignment_controller(
        validated_events=sample_input["validated_events"],
        tts_segments=sample_input["tts_segments"], 
        total_duration=sample_input["total_duration"],
        reaction_delay_range=ALIGNMENT_CONFIG["reaction_delay_range"],
        conflict_resolution_rules=ALIGNMENT_CONFIG["conflict_resolution_rules"]
    )
    
    # 4. 显示结果
    print("\n--- 对齐结果 ---")
    print(f"解决的冲突数量: {result['conflicts_resolved']}")
    print(f"最终放置位置数量: {result['final_placements']}")
    print(f"音频覆盖率: {result['timeline_summary']['coverage_percentage']:.1f}%")
    
    # 5. 显示详细的placement_map
    print("\n--- 音频放置位置详情 ---")
    for i, placement in enumerate(result["placement_map"], 1):
        print(f"{i}. 片段: {placement['segment_id']}")
        print(f"   事件: {placement['event_type']} (优先级: {placement['priority']})")
        print(f"   时间: {placement['start']:.1f}s - {placement['end']:.1f}s")
        print(f"   音频时长: {placement['audio_duration']:.1f}s")
        print(f"   反应延迟: {placement['reaction_delay']:.1f}s")
        if placement.get('delayed_by'):
            print(f"   延迟量: {placement['delayed_by']:.1f}s")
        print()
    
    # 6. 显示冲突解决详情
    if result["conflict_details"]:
        print("\n--- 冲突解决详情 ---")
        for i, conflict in enumerate(result["conflict_details"], 1):
            print(f"冲突 {i} (时间: {conflict['timestamp']:.1f}s):")
            print(f"  涉及事件: {len(conflict['conflicting_events'])}个")
            print(f"  解决方案: {len(conflict['resolution'])}个位置")
    
    return result


def validate_placement_map(placement_map: List[Dict], total_duration: float) -> Dict[str, Any]:
    """验证placement_map的完整性"""
    
    validation_result = {
        "valid": True,
        "warnings": [],
        "errors": [],
        "metrics": {}
    }
    
    if not placement_map:
        validation_result["valid"] = False
        validation_result["errors"].append("placement_map为空")
        return validation_result
    
    # 检查时间重叠
    placement_map.sort(key=lambda x: x["start"])
    overlaps = []
    
    for i in range(1, len(placement_map)):
        prev = placement_map[i-1]
        curr = placement_map[i]
        
        if prev["end"] > curr["start"]:
            overlap = prev["end"] - curr["start"]
            overlaps.append({
                "position": i,
                "overlap": overlap,
                "events": [prev["event_id"], curr["event_id"]]
            })
    
    if overlaps:
        validation_result["valid"] = False
        validation_result["errors"].append(f"发现{len(overlaps)}处时间重叠")
        validation_result["overlaps"] = overlaps
    
    # 检查时间范围
    out_of_bounds = []
    for placement in placement_map:
        if placement["start"] < 0:
            out_of_bounds.append({
                "segment": placement["segment_id"],
                "issue": "开始时间小于0"
            })
        if placement["end"] > total_duration:
            out_of_bounds.append({
                "segment": placement["segment_id"],
                "issue": f"结束时间{placement['end']}超出视频时长{total_duration}"
            })
    
    if out_of_bounds:
        validation_result["warnings"].extend([f"{o['segment']}: {o['issue']}" for o in out_of_bounds])
    
    # 计算指标
    total_audio_time = sum(p["audio_duration"] for p in placement_map)
    coverage_percentage = (total_audio_time / total_duration * 100) if total_duration > 0 else 0
    
    validation_result["metrics"] = {
        "total_audio_time": total_audio_time,
        "coverage_percentage": coverage_percentage,
        "average_reaction_delay": sum(p.get("reaction_delay", 0) for p in placement_map) / len(placement_map)
    }
    
    return validation_result


if __name__ == "__main__":
    # 运行演示
    result = demonstrate_alignment_workflow()
    
    # 验证结果
    if result and "placement_map" in result:
        validation = validate_placement_map(result["placement_map"], result["timeline_summary"]["total_duration"])
        
        print("\n=== 验证结果 ===")
        print(f"有效性: {'通过' if validation['valid'] else '失败'}")
        
        if validation["warnings"]:
            print("警告:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")
        
        if validation["errors"]:
            print("错误:")
            for error in validation["errors"]:
                print(f"  - {error}")
        
        print("\n指标:")
        for metric, value in validation["metrics"].items():
            if isinstance(value, float):
                print(f"  {metric}: {value:.2f}")
            else:
                print(f"  {metric}: {value}")