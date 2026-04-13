import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

def main(vlm_output: Dict, frame_timestamps: List[float], skills_rules_path: str = "skills.md") -> Dict:
    """
    Skills 校验层主函数
    
    Args:
        vlm_output: VLM 的原始输出（包含 events/views/metrics/squads）
        frame_timestamps: 每帧的真实时间戳列表
        skills_rules_path: skills.md 规则文件路径
    
    Returns:
        validated_output: 经过校验的输出
    """
    
    # 读取校验规则
    rules = load_skills_rules(skills_rules_path)
    
    # 基础校验
    validated_events = validate_events(vlm_output.get("events", []), frame_timestamps, rules)
    validated_views = validate_views(vlm_output.get("views", []), frame_timestamps, rules)
    validated_metrics = validate_metrics(vlm_output.get("metrics", []), frame_timestamps, rules)
    validated_squads = validate_squads(vlm_output.get("squads", []), frame_timestamps, rules)
    
    # 意图识别
    intent_analysis = analyze_intents(validated_events, rules)
    
    # 玩家名称模糊化
    anonymized_events = anonymize_player_names(validated_events)
    anonymized_squads = anonymize_player_names(validated_squads)
    
    # 生成校验日志
    validation_log = generate_validation_log(
        vlm_output, 
        validated_events, 
        validated_views, 
        validated_metrics, 
        validated_squads,
        intent_analysis
    )
    
    return {
        "events": anonymized_events,
        "views": validated_views,
        "metrics": validated_metrics,
        "squads": anonymized_squads,
        "intent_analysis": intent_analysis,
        "validation_log": validation_log
    }


def load_skills_rules(rules_path: str) -> Dict:
    """读取 skills.md 规则文件"""
    try:
        with open(rules_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析规则文件（简化版本）
        rules = {
            "confidence_threshold": 0.55,
            "max_time_gap": 5.0,
            "player_name_patterns": [
                r"[A-Za-z0-9_]+",  # 玩家名称模式
            ],
            "anonymization_terms": [
                "这边这个人", "对面", "这波人", "这一队", 
                "刚刚那个", "有人", "一个人", "另一边"
            ]
        }
        
        return rules
    except Exception as e:
        print(f"Warning: Failed to load rules from {rules_path}: {e}")
        return {}


def validate_events(events: List[Dict], frame_timestamps: List[float], rules: Dict) -> List[Dict]:
    """校验事件列表"""
    validated = []
    
    for event in events:
        # 基础校验
        if not validate_event_basic(event, frame_timestamps, rules):
            continue
            
        # 置信度过滤
        if event.get("confidence", 0) < rules.get("confidence_threshold", 0.55):
            event["validation_notes"] = "置信度过低"
            event["validated"] = False
        else:
            event["validated"] = True
            
        validated.append(event)
    
    # 时间顺序校验
    validated = validate_temporal_consistency(validated)
    
    return validated


def validate_event_basic(event: Dict, frame_timestamps: List[float], rules: Dict) -> bool:
    """基础事件校验"""
    # 检查 k 值有效性
    k = event.get("k", -1)
    if k < 0 or k >= len(frame_timestamps):
        return False
    
    # 检查 video_time 一致性
    expected_time = frame_timestamps[k]
    actual_time = event.get("video_time")
    if actual_time is not None and abs(actual_time - expected_time) > 0.1:
        return False
    
    # 检查证据帧有效性
    evidence_k = event.get("evidence_k", [])
    for evidence_frame in evidence_k:
        if evidence_frame < 0 or evidence_frame >= len(frame_timestamps):
            return False
    
    return True


def validate_temporal_consistency(events: List[Dict]) -> List[Dict]:
    """时间一致性校验"""
    # 按时间排序
    sorted_events = sorted(events, key=lambda x: x.get("video_time", 0))
    
    # 检查事件逻辑
    for i in range(1, len(sorted_events)):
        prev_event = sorted_events[i-1]
        curr_event = sorted_events[i]
        
        # 检查时间倒退
        if curr_event.get("video_time", 0) < prev_event.get("video_time", 0):
            curr_event["validation_notes"] = "时间顺序异常"
            curr_event["validated"] = False
    
    return sorted_events


def validate_views(views: List[Dict], frame_timestamps: List[float], rules: Dict) -> List[Dict]:
    """校验视图列表"""
    return [view for view in views if validate_view_basic(view, frame_timestamps)]


def validate_view_basic(view: Dict, frame_timestamps: List[float]) -> bool:
    """基础视图校验"""
    k = view.get("k", -1)
    return 0 <= k < len(frame_timestamps)


def validate_metrics(metrics: List[Dict], frame_timestamps: List[float], rules: Dict) -> List[Dict]:
    """校验指标列表"""
    return [metric for metric in metrics if validate_metric_basic(metric, frame_timestamps)]


def validate_metric_basic(metric: Dict, frame_timestamps: List[float]) -> bool:
    """基础指标校验"""
    k = metric.get("k", -1)
    return 0 <= k < len(frame_timestamps)


def validate_squads(squads: List[Dict], frame_timestamps: List[float], rules: Dict) -> List[Dict]:
    """校验小队列表"""
    return [squad for squad in squads if validate_squad_basic(squad, frame_timestamps)]


def validate_squad_basic(squad: Dict, frame_timestamps: List[float]) -> bool:
    """基础小队校验"""
    k = squad.get("k", -1)
    return 0 <= k < len(frame_timestamps)


def analyze_intents(events: List[Dict], rules: Dict) -> Dict:
    """意图识别分析"""
    intents = {
        "multi_kill": detect_multi_kill(events),
        "rescue_attempt": detect_rescue_attempt(events),
        "team_fight": detect_team_fight(events)
    }
    
    return intents


def detect_multi_kill(events: List[Dict]) -> List[Dict]:
    """检测连杀意图"""
    eliminations = [e for e in events if e.get("type") == "player_elimination"]
    
    multi_kills = []
    time_window = 5.0  # 5秒时间窗口
    
    for i, elim in enumerate(eliminations):
        elim_time = elim.get("video_time", 0)
        same_team_kills = []
        
        # 查找同一团队在时间窗口内的击杀
        for other_elim in eliminations:
            if (other_elim.get("actor") == elim.get("actor") and
                abs(other_elim.get("video_time", 0) - elim_time) <= time_window):
                same_team_kills.append(other_elim)
        
        if len(same_team_kills) >= 2:  # 至少2个击杀
            multi_kills.append({
                "intent_type": "multi_kill",
                "actor": elim.get("actor"),
                "kill_count": len(same_team_kills),
                "time_window": time_window,
                "events": same_team_kills
            })
    
    return multi_kills


def detect_rescue_attempt(events: List[Dict]) -> List[Dict]:
    """检测救援意图"""
    rescue_attempts = []
    time_window = 3.0  # 3秒时间窗口
    
    knocks = [e for e in events if e.get("type") == "player_knock"]
    revivals = [e for e in events if e.get("type") == "player_revival_started"]
    
    for knock in knocks:
        knock_time = knock.get("video_time", 0)
        target = knock.get("target")
        
        # 查找同一目标的救援
        for revival in revivals:
            if (revival.get("target") == target and
                revival.get("video_time", 0) - knock_time <= time_window):
                rescue_attempts.append({
                    "intent_type": "rescue_attempt",
                    "knock_event": knock,
                    "revival_event": revival,
                    "time_gap": revival.get("video_time", 0) - knock_time
                })
    
    return rescue_attempts


def detect_team_fight(events: List[Dict]) -> List[Dict]:
    """检测团队对抗意图"""
    combat_events = [e for e in events if e.get("type") in ["player_knock", "player_elimination"]]
    
    team_fights = []
    time_window = 10.0  # 10秒时间窗口
    
    for i, event in enumerate(combat_events):
        event_time = event.get("video_time", 0)
        actor_team = event.get("team")
        target_team = event.get("target_team")
        
        if not actor_team or not target_team:
            continue
        
        # 查找同一团队对抗的事件
        related_events = []
        for other_event in combat_events:
            if (abs(other_event.get("video_time", 0) - event_time) <= time_window and
                (other_event.get("team") == actor_team and other_event.get("target_team") == target_team) or
                (other_event.get("team") == target_team and other_event.get("target_team") == actor_team)):
                related_events.append(other_event)
        
        if len(related_events) >= 2:  # 至少2个相关事件
            team_fights.append({
                "intent_type": "team_fight",
                "teams": [actor_team, target_team],
                "event_count": len(related_events),
                "time_window": time_window,
                "events": related_events
            })
    
    return team_fights


def anonymize_player_names(data: List[Dict]) -> List[Dict]:
    """玩家名称模糊化"""
    anonymized = []
    name_mapping = {}
    anonymization_terms = ["这边这个人", "对面", "这波人", "这一队", "刚刚那个", "有人", "一个人", "另一边"]
    
    for item in data:
        anonymized_item = item.copy()
        
        # 模糊化玩家名称字段
        for field in ["actor", "target", "player"]:
            if field in anonymized_item and anonymized_item[field]:
                original_name = anonymized_item[field]
                
                # 如果还没有映射，创建新的模糊名称
                if original_name not in name_mapping:
                    term_index = len(name_mapping) % len(anonymization_terms)
                    name_mapping[original_name] = anonymization_terms[term_index]
                
                anonymized_item[field] = name_mapping[original_name]
        
        # 模糊化团队名称字段
        for field in ["team", "target_team"]:
            if field in anonymized_item and anonymized_item[field]:
                # 团队名称简化为数字或模糊描述
                team_id = anonymized_item[field]
                if team_id.isdigit():
                    anonymized_item[field] = f"{team_id}队"
                else:
                    anonymized_item[field] = "这一队"
        
        anonymized.append(anonymized_item)
    
    return anonymized


def generate_validation_log(vlm_output: Dict, events: List[Dict], views: List[Dict], 
                           metrics: List[Dict], squads: List[Dict], intent_analysis: Dict) -> Dict:
    """生成校验日志"""
    validated_count = len([e for e in events if e.get("validated", False)])
    rejected_count = len([e for e in events if not e.get("validated", True)])
    
    return {
        "timestamp": datetime.now().isoformat(),
        "input_event_count": len(vlm_output.get("events", [])),
        "validated_event_count": validated_count,
        "rejected_event_count": rejected_count,
        "view_count": len(views),
        "metric_count": len(metrics),
        "squad_count": len(squads),
        "intent_analysis_summary": {
            "multi_kill_count": len(intent_analysis.get("multi_kill", [])),
            "rescue_attempt_count": len(intent_analysis.get("rescue_attempt", [])),
            "team_fight_count": len(intent_analysis.get("team_fight", []))
        }
    }