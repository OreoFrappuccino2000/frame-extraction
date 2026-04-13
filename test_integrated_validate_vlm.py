#!/usr/bin/env python3
"""
集成后的 validate-vlm 端点测试脚本
测试 Skills 校验层与现有 validate-vlm 功能的集成
"""

import json
import requests
import sys
import os

# 添加当前目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 测试数据 - 基于用户提供的 VLM 输出样本
test_payload = {
    "vlm_output": {
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
    },
    "frames": [
        {"frame_index": 0, "video_time": 0.0, "image_data": "..."},
        {"frame_index": 1, "video_time": 1.3, "image_data": "..."},
        {"frame_index": 2, "video_time": 2.6, "image_data": "..."},
        {"frame_index": 3, "video_time": 3.9, "image_data": "..."},
        {"frame_index": 4, "video_time": 5.2, "image_data": "..."},
        {"frame_index": 5, "video_time": 6.5, "image_data": "..."},
        {"frame_index": 13, "video_time": 16.901, "image_data": "..."},
        {"frame_index": 14, "video_time": 18.201, "image_data": "..."}
    ]
}

def test_local_validation():
    """测试本地 Skills 校验功能"""
    print("=== 本地 Skills 校验测试 ===\n")
    
    try:
        from app import validate_vlm, ValidateVlmRequest
        
        # 创建请求对象
        request = ValidateVlmRequest(**test_payload)
        
        # 执行校验
        result = validate_vlm(request)
        
        # 输出结果
        print("1. 基础统计:")
        stats = result.get("stats", {})
        print(f"   输入事件数: {stats.get('input_events', 0)}")
        print(f"   输出事件数: {stats.get('output_events', 0)}")
        print(f"   丢弃事件数: {stats.get('dropped_events', 0)}")
        print(f"   意图检测数: {stats.get('intent_detections', 0)}")
        
        print("\n2. 意图分析:")
        intent_analysis = result.get("intent_analysis", {})
        for intent_type, intents in intent_analysis.items():
            print(f"   {intent_type}: {len(intents)} 个检测")
            for intent in intents[:2]:  # 显示前2个
                print(f"     - {intent.get('intent_type', 'unknown')}")
        
        print("\n3. 玩家名称模糊化示例:")
        events = result.get("events", [])
        if events:
            for i, event in enumerate(events[:3]):
                print(f"   事件 {i+1}:")
                print(f"     类型: {event.get('type')}")
                print(f"     演员: {event.get('actor')}")
                print(f"     目标: {event.get('target')}")
        
        print("\n4. 校验日志:")
        validation_log = result.get("validation_log", {})
        print(json.dumps(validation_log, indent=2, ensure_ascii=False))
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_http_endpoint():
    """测试 HTTP 端点（如果应用正在运行）"""
    print("\n=== HTTP 端点测试 ===\n")
    
    try:
        # 假设应用运行在本地 8000 端口
        response = requests.post(
            "http://localhost:8000/validate-vlm",
            json=test_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("HTTP 端点测试成功!")
            print(f"意图检测数: {result.get('stats', {}).get('intent_detections', 0)}")
            return True
        else:
            print(f"HTTP 端点测试失败: {response.status_code}")
            print(response.text)
            return False
            
    except requests.exceptions.ConnectionError:
        print("应用未运行在 localhost:8000，跳过 HTTP 测试")
        return None
    except Exception as e:
        print(f"HTTP 测试异常: {e}")
        return False

if __name__ == "__main__":
    print("集成后的 validate-vlm 端点测试\n")
    
    # 测试本地功能
    local_success = test_local_validation()
    
    # 测试 HTTP 端点
    http_result = test_http_endpoint()
    
    print("\n=== 测试总结 ===")
    print(f"本地校验: {'通过' if local_success else '失败'}")
    if http_result is not None:
        print(f"HTTP 端点: {'通过' if http_result else '失败'}")
    else:
        print("HTTP 端点: 跳过（应用未运行）")