#!/usr/bin/env python3
"""
Skills 校验层测试脚本
"""

import json
from skills_node import main

# 测试数据 - 基于用户提供的 VLM 输出样本
test_vlm_output = {
    "views": [
        {
            "k": 0,
            "video_time": 0.0,
            "camera_mode": "tpp",
            "pov_confirmed": True,
            "observer_mode": False
        },
        {
            "k": 1,
            "video_time": 1.3,
            "camera_mode": "fpp",
            "pov_confirmed": True,
            "observer_mode": False
        },
        {
            "k": 2,
            "video_time": 2.6,
            "camera_mode": "observer",
            "pov_confirmed": False,
            "observer_mode": True
        }
    ],
    "metrics": [
        {
            "k": 0,
            "video_time": 0.0,
            "alive": 51,
            "teams": 16,
            "phase": None,
            "zone_timer_s": None
        },
        {
            "k": 1,
            "video_time": 1.3,
            "alive": 51,
            "teams": 16,
            "phase": None,
            "zone_timer_s": 30
        },
        {
            "k": 2,
            "video_time": 2.6,
            "alive": 51,
            "teams": 16,
            "phase": None,
            "zone_timer_s": None
        },
        {
            "k": 13,
            "video_time": 16.901,
            "alive": 48,
            "teams": 15,
            "phase": None,
            "zone_timer_s": None
        }
    ],
    "events": [
        {
            "k": 2,
            "video_time": 2.6,
            "type": "player_knock",
            "actor": "GodLKrontenBTC",
            "team": "7",
            "target": "FNC scOutOP",
            "target_team": "14",
            "weapon": "gun",
            "damage_type": "bullet",
            "text": "FNC scOutOP knocked",
            "position_tag": "outside_building",
            "confidence": 0.95,
            "evidence_k": [2, 3, 4, 5]
        },
        {
            "k": 13,
            "video_time": 16.901,
            "type": "player_elimination",
            "actor": "FNC scOutOP",
            "team": "14",
            "target": "GodLSmxkieOP",
            "target_team": "7",
            "weapon": "gun",
            "damage_type": "bullet",
            "text": "FNC scOutOP eliminated GodLSmxkieOP",
            "position_tag": "outside_building",
            "confidence": 0.95,
            "evidence_k": [13]
        },
        {
            "k": 13,
            "video_time": 16.901,
            "type": "player_elimination",
            "actor": "FNC scOutOP",
            "team": "14",
            "target": "GodLKrontenBTC",
            "target_team": "7",
            "weapon": "gun",
            "damage_type": "bullet",
            "text": "FNC scOutOP eliminated GodLKrontenBTC",
            "position_tag": "outside_building",
            "confidence": 0.95,
            "evidence_k": [13]
        },
        {
            "k": 13,
            "video_time": 16.901,
            "type": "player_elimination",
            "actor": "FNC scOutOP",
            "team": "14",
            "target": "GodLKingXzist",
            "target_team": "7",
            "weapon": "gun",
            "damage_type": "bullet",
            "text": "FNC scOutOP eliminated GodLKingXzist",
            "position_tag": "outside_building",
            "confidence": 0.95,
            "evidence_k": [13]
        },
        {
            "k": 13,
            "video_time": 16.901,
            "type": "player_revival_started",
            "actor": "FNC scOutOP",
            "team": "14",
            "target": "FNC RonaK",
            "target_team": "14",
            "weapon": None,
            "damage_type": None,
            "text": "Reviving",
            "position_tag": "outside_building",
            "confidence": 0.95,
            "evidence_k": [14, 15, 16, 17, 18, 19]
        }
    ],
    "squads": [
        {
            "k": 0,
            "video_time": 0.0,
            "player": "GodLSmxkieOP",
            "team": "7",
            "state": "alive",
            "posture": "standing",
            "hp_bucket": "51_75",
            "is_low_hp": False,
            "is_lowest_hp_on_team_est": None,
            "action": "holding",
            "location_tag": "outside_building",
            "confidence": 0.90
        },
        {
            "k": 0,
            "video_time": 0.0,
            "player": "GodLKrontenBTC",
            "team": "7",
            "state": "alive",
            "posture": "standing",
            "hp_bucket": "76_100",
            "is_low_hp": False,
            "is_lowest_hp_on_team_est": None,
            "action": "holding",
            "location_tag": "outside_building",
            "confidence": 0.90
        },
        {
            "k": 5,
            "video_time": 6.5,
            "player": "FNC RonaK",
            "team": "14",
            "state": "knocked",
            "posture": "knocked_pose",
            "hp_bucket": "1_25",
            "is_low_hp": True,
            "is_lowest_hp_on_team_est": True,
            "action": None,
            "location_tag": "inside_building",
            "confidence": 0.90
        },
        {
            "k": 13,
            "video_time": 16.901,
            "player": "GodLSmxkieOP",
            "team": "7",
            "state": "eliminated",
            "posture": "unknown",
            "hp_bucket": "0",
            "is_low_hp": None,
            "is_lowest_hp_on_team_est": None,
            "action": None,
            "location_tag": "outside_building",
            "confidence": 0.95
        },
        {
            "k": 13,
            "video_time": 16.901,
            "player": "GodLKrontenBTC",
            "team": "7",
            "state": "eliminated",
            "posture": "unknown",
            "hp_bucket": "0",
            "is_low_hp": None,
            "is_lowest_hp_on_team_est": None,
            "action": None,
            "location_tag": "outside_building",
            "confidence": 0.95
        },
        {
            "k": 13,
            "video_time": 16.901,
            "player": "GodLKingXzist",
            "team": "7",
            "state": "eliminated",
            "posture": "unknown",
            "hp_bucket": "0",
            "is_low_hp": None,
            "is_lowest_hp_on_team_est": None,
            "action": None,
            "location_tag": "outside_building",
            "confidence": 0.95
        },
        {
            "k": 14,
            "video_time": 18.201,
            "player": "FNC RonaK",
            "team": "14",
            "state": "being_revived",
            "posture": "knocked_pose",
            "hp_bucket": "1_25",
            "is_low_hp": True,
            "is_lowest_hp_on_team_est": True,
            "action": "being_revived",
            "location_tag": "outside_building",
            "confidence": 0.95
        },
        {
            "k": 14,
            "video_time": 18.201,
            "player": "FNC scOutOP",
            "team": "14",
            "state": "reviving",
            "posture": "crouch",
            "hp_bucket": "26_50",
            "is_low_hp": True,
            "is_lowest_hp_on_team_est": None,
            "action": "reviving",
            "location_tag": "outside_building",
            "confidence": 0.95
        }
    ]
}

# 模拟帧时间戳（基于视频时长20秒，25fps）
frame_timestamps = [i * 0.04 for i in range(500)]  # 20秒视频，500帧

def test_skills_node():
    """测试 Skills 校验层"""
    print("=== Skills 校验层测试 ===\n")
    
    # 运行校验
    result = main(test_vlm_output, frame_timestamps)
    
    # 输出结果
    print("1. 校验日志:")
    print(json.dumps(result.get("validation_log", {}), indent=2, ensure_ascii=False))
    
    print("\n2. 意图分析:")
    print(json.dumps(result.get("intent_analysis", {}), indent=2, ensure_ascii=False))
    
    print("\n3. 校验后事件数量:")
    print(f"原始事件数: {len(test_vlm_output['events'])}")
    print(f"校验后事件数: {len(result.get('events', []))}")
    
    print("\n4. 玩家名称模糊化示例:")
    if result.get("events"):
        for i, event in enumerate(result["events"][:3]):  # 显示前3个事件
            print(f"事件 {i+1}:")
            print(f"  原始演员: {test_vlm_output['events'][i].get('actor')}")
            print(f"  模糊化后: {event.get('actor')}")
            print(f"  原始目标: {test_vlm_output['events'][i].get('target')}")
            print(f"  模糊化后: {event.get('target')}")
            print()
    
    print("\n5. 校验详情（前3个事件）:")
    for i, event in enumerate(result.get("events", [])[:3]):
        print(f"事件 {i+1}:")
        print(f"  类型: {event.get('type')}")
        print(f"  时间: {event.get('video_time')}")
        print(f"  置信度: {event.get('confidence')}")
        print(f"  校验状态: {'通过' if event.get('validated', False) else '拒绝'}")
        if "validation_notes" in event:
            print(f"  校验说明: {event.get('validation_notes')}")
        print()

if __name__ == "__main__":
    test_skills_node()