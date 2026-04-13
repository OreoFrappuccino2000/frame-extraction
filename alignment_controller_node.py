import json
import math
from typing import Dict, Any, List, Tuple
from collections import defaultdict


def main(
    validated_events: List[Dict],
    tts_segments: List[Dict],
    total_duration: float,
    reaction_delay_range: Tuple[float, float] = (0.6, 1.2),
    conflict_resolution_rules: Dict = None
) -> Dict[str, Any]:
    """
    音频视频对齐控制器
    根据需求文档实现精准的音频插入与视频事件对齐
    
    Args:
        validated_events: 验证后的事件列表（来自skills校验层）
        tts_segments: TTS生成的音频片段列表
        total_duration: 视频总时长
        reaction_delay_range: 反应延迟范围（秒）
        conflict_resolution_rules: 冲突解决规则
    
    Returns:
        Dict包含placement_map和冲突处理结果
    """
    
    # 默认冲突解决规则
    DEFAULT_CONFLICT_RULES = {
        "priority_order": ["kill", "knock", "damage", "movement"],
        "priority_weights": {"kill": 1, "knock": 2, "damage": 3, "movement": 4},
        "merge_threshold": 1.0,  # 合并阈值（秒）
        "max_delay": 3.0,  # 最大延迟时间
        "min_gap": 0.1  # 最小间隔
    }
    
    rules = conflict_resolution_rules or DEFAULT_CONFLICT_RULES
    
    # ------------------------------------------------------------------
    # STEP 1: 构建事件时间轴（唯一可信时间源）
    # ------------------------------------------------------------------
    def build_event_timeline(events: List[Dict]) -> List[Dict]:
        """构建唯一可信事件时间轴"""
        timeline = []
        
        for event in events:
            # 使用video_time作为唯一时间依据
            start_time = event.get("video_time", 0)
            event_type = event.get("type", "unknown")
            confidence = event.get("confidence", 1.0)
            
            # 过滤低置信度事件
            if confidence < 0.55:
                continue
                
            # 计算事件持续时间（基于事件类型）
            duration = _calculate_event_duration(event_type, event)
            end_time = start_time + duration
            
            # 确定优先级
            priority = rules["priority_weights"].get(event_type, 4)
            
            timeline.append({
                "event_id": event.get("event_id", f"event_{len(timeline)}"),
                "start_time": start_time,
                "end_time": end_time,
                "event_type": event_type,
                "priority": priority,
                "original_data": event
            })
        
        # 按开始时间排序
        timeline.sort(key=lambda x: x["start_time"])
        
        # 去重和合并相邻事件
        return _deduplicate_and_merge_timeline(timeline, rules)
    
    # ------------------------------------------------------------------
    # STEP 2: 构建音频片段映射
    # ------------------------------------------------------------------
    def build_audio_segment_map(tts_segments: List[Dict]) -> Dict[str, Dict]:
        """构建音频片段映射"""
        audio_map = {}
        
        for segment in tts_segments:
            segment_id = segment.get("segment_id")
            audio_url = segment.get("audio_url")
            audio_duration = segment.get("audio_duration", 0)
            
            if segment_id and audio_url and audio_duration > 0:
                audio_map[segment_id] = {
                    "audio_url": audio_url,
                    "audio_duration": audio_duration,
                    "segment_data": segment
                }
        
        return audio_map
    
    # ------------------------------------------------------------------
    # STEP 3: 计算音频放置位置
    # ------------------------------------------------------------------
    def calculate_audio_placement(
        timeline: List[Dict], 
        audio_map: Dict[str, Dict],
        reaction_delay_range: Tuple[float, float]
    ) -> List[Dict]:
        """计算音频放置位置"""
        placement_map = []
        
        for event in timeline:
            segment_id = _find_matching_segment(event, audio_map)
            if not segment_id or segment_id not in audio_map:
                continue
                
            audio_duration = audio_map[segment_id]["audio_duration"]
            
            # 计算反应延迟
            reaction_delay = _calculate_reaction_delay(
                event["event_type"], 
                reaction_delay_range
            )
            
            # 计算音频开始和结束时间
            audio_start = event["start_time"] + reaction_delay
            audio_end = audio_start + audio_duration
            
            placement_map.append({
                "segment_id": segment_id,
                "event_id": event["event_id"],
                "start": audio_start,
                "end": audio_end,
                "audio_duration": audio_duration,
                "reaction_delay": reaction_delay,
                "event_type": event["event_type"],
                "priority": event["priority"]
            })
        
        return placement_map
    
    # ------------------------------------------------------------------
    # STEP 4: 冲突检测与解决
    # ------------------------------------------------------------------
    def detect_and_resolve_conflicts(
        placement_map: List[Dict], 
        rules: Dict
    ) -> Tuple[List[Dict], List[Dict]]:
        """检测并解决音频时间冲突"""
        conflicts = []
        resolved_map = []
        
        # 按开始时间排序
        placement_map.sort(key=lambda x: x["start"])
        
        i = 0
        while i < len(placement_map):
            current = placement_map[i]
            
            # 检查与后续事件的冲突
            conflicts_with_current = []
            j = i + 1
            while j < len(placement_map):
                next_event = placement_map[j]
                
                # 检查重叠
                if current["end"] > next_event["start"]:
                    conflicts_with_current.append(next_event)
                    j += 1
                else:
                    break
            
            if conflicts_with_current:
                # 解决冲突
                resolved_events = _resolve_conflict_group(
                    [current] + conflicts_with_current, 
                    rules
                )
                
                # 记录冲突信息
                conflict_info = {
                    "conflicting_events": [current] + conflicts_with_current,
                    "resolution": resolved_events,
                    "timestamp": current["start"]
                }
                conflicts.append(conflict_info)
                
                # 添加解决后的事件
                resolved_map.extend(resolved_events)
                i = j  # 跳过已处理的事件
            else:
                resolved_map.append(current)
                i += 1
        
        return resolved_map, conflicts
    
    # ------------------------------------------------------------------
    # STEP 5: 最终验证和优化
    # ------------------------------------------------------------------
    def finalize_placement_map(
        placement_map: List[Dict], 
        total_duration: float
    ) -> List[Dict]:
        """最终验证和优化placement_map"""
        
        # 确保所有音频都在视频时长范围内
        for placement in placement_map:
            if placement["end"] > total_duration:
                # 调整音频结束时间
                placement["end"] = total_duration
                # 如果音频被截断，记录警告
                if placement["end"] - placement["start"] < placement["audio_duration"]:
                    placement["truncated"] = True
                    placement["original_duration"] = placement["audio_duration"]
                    placement["actual_duration"] = placement["end"] - placement["start"]
        
        # 确保没有重叠
        placement_map.sort(key=lambda x: x["start"])
        for i in range(1, len(placement_map)):
            prev = placement_map[i-1]
            curr = placement_map[i]
            
            if prev["end"] > curr["start"]:
                # 强制调整，保持最小间隔
                curr["start"] = prev["end"] + rules["min_gap"]
                curr["end"] = curr["start"] + curr["audio_duration"]
        
        return placement_map
    
    # ------------------------------------------------------------------
    # 辅助函数
    # ------------------------------------------------------------------
    def _calculate_event_duration(event_type: str, event_data: Dict) -> float:
        """根据事件类型计算持续时间"""
        base_durations = {
            "kill": 2.0,
            "knock": 1.5,
            "damage": 1.0,
            "movement": 0.5
        }
        
        duration = base_durations.get(event_type, 1.0)
        
        # 根据事件特性调整时长
        if event_type == "kill" and event_data.get("multi_kill", False):
            duration += 0.5  # 多杀事件稍长
            
        return duration
    
    def _deduplicate_and_merge_timeline(timeline: List[Dict], rules: Dict) -> List[Dict]:
        """去重和合并相邻事件"""
        if not timeline:
            return []
        
        merged_timeline = []
        current = timeline[0]
        
        for i in range(1, len(timeline)):
            next_event = timeline[i]
            
            # 检查是否应该合并
            time_gap = next_event["start_time"] - current["end_time"]
            same_type = current["event_type"] == next_event["event_type"]
            
            if time_gap < rules["merge_threshold"] and same_type:
                # 合并事件
                current["end_time"] = max(current["end_time"], next_event["end_time"])
            else:
                merged_timeline.append(current)
                current = next_event
        
        merged_timeline.append(current)
        return merged_timeline
    
    def _find_matching_segment(event: Dict, audio_map: Dict[str, Dict]) -> str:
        """为事件找到匹配的音频片段"""
        event_type = event["event_type"]
        
        # 简单的匹配逻辑 - 可以根据需要扩展
        for segment_id, audio_info in audio_map.items():
            segment_data = audio_info["segment_data"]
            segment_type = segment_data.get("event_type", "")
            
            if segment_type == event_type:
                return segment_id
        
        # 如果没有精确匹配，返回第一个可用的片段
        if audio_map:
            return list(audio_map.keys())[0]
        
        return ""
    
    def _calculate_reaction_delay(event_type: str, delay_range: Tuple[float, float]) -> float:
        """根据事件类型计算反应延迟"""
        min_delay, max_delay = delay_range
        
        # 不同类型事件的反应延迟
        delay_factors = {
            "kill": 0.6,    # 击杀事件反应较快
            "knock": 0.8,   # 击倒事件中等反应
            "damage": 1.0,  # 伤害事件标准反应
            "movement": 1.2 # 移动事件反应较慢
        }
        
        factor = delay_factors.get(event_type, 1.0)
        return min_delay + (max_delay - min_delay) * factor
    
    def _resolve_conflict_group(conflicting_events: List[Dict], rules: Dict) -> List[Dict]:
        """解决一组冲突事件"""
        if not conflicting_events:
            return []
        
        # 按优先级排序
        conflicting_events.sort(key=lambda x: x["priority"])
        
        resolved_events = []
        
        # 处理最高优先级事件
        highest_priority = conflicting_events[0]
        resolved_events.append(highest_priority)
        
        # 处理其他事件
        for i in range(1, len(conflicting_events)):
            event = conflicting_events[i]
            
            # 检查是否可以合并
            if _can_merge_events(highest_priority, event, rules):
                # 合并事件
                highest_priority = _merge_events(highest_priority, event)
                resolved_events[0] = highest_priority
            else:
                # 延迟事件
                delayed_event = _delay_event(event, highest_priority, rules)
                if delayed_event:
                    resolved_events.append(delayed_event)
        
        return resolved_events
    
    def _can_merge_events(event1: Dict, event2: Dict, rules: Dict) -> bool:
        """检查两个事件是否可以合并"""
        # 相同类型且优先级相近的事件可以合并
        return (event1["event_type"] == event2["event_type"] and
                abs(event1["priority"] - event2["priority"]) <= 1)
    
    def _merge_events(event1: Dict, event2: Dict) -> Dict:
        """合并两个事件"""
        merged = event1.copy()
        merged["end"] = max(event1["end"], event2["end"])
        merged["merged_count"] = event1.get("merged_count", 1) + 1
        merged["merged_events"] = event1.get("merged_events", [event1["event_id"]])
        merged["merged_events"].append(event2["event_id"])
        return merged
    
    def _delay_event(event: Dict, blocking_event: Dict, rules: Dict) -> Dict:
        """延迟事件以避免冲突"""
        delayed_event = event.copy()
        
        # 计算延迟后的开始时间
        new_start = blocking_event["end"] + rules["min_gap"]
        max_allowed_start = blocking_event["start"] + rules["max_delay"]
        
        if new_start <= max_allowed_start:
            delayed_event["start"] = new_start
            delayed_event["end"] = new_start + delayed_event["audio_duration"]
            delayed_event["delayed_by"] = new_start - event["start"]
            return delayed_event
        
        # 如果延迟过大，丢弃低优先级事件
        return None
    
    # ------------------------------------------------------------------
    # 主执行流程
    # ------------------------------------------------------------------
    
    # 1. 构建事件时间轴
    event_timeline = build_event_timeline(validated_events)
    
    # 2. 构建音频片段映射
    audio_segment_map = build_audio_segment_map(tts_segments)
    
    # 3. 计算初始放置位置
    initial_placement = calculate_audio_placement(
        event_timeline, 
        audio_segment_map, 
        reaction_delay_range
    )
    
    # 4. 检测并解决冲突
    resolved_placement, conflicts = detect_and_resolve_conflicts(initial_placement, rules)
    
    # 5. 最终验证和优化
    final_placement = finalize_placement_map(resolved_placement, total_duration)
    
    # 6. 生成最终输出
    return {
        "placement_map": final_placement,
        "conflicts_resolved": len(conflicts),
        "conflict_details": conflicts,
        "total_events": len(event_timeline),
        "total_audio_segments": len(audio_segment_map),
        "final_placements": len(final_placement),
        "timeline_summary": {
            "total_duration": total_duration,
            "event_count": len(event_timeline),
            "audio_coverage": sum(p["audio_duration"] for p in final_placement),
            "coverage_percentage": (sum(p["audio_duration"] for p in final_placement) / total_duration * 100)
            if total_duration > 0 else 0
        }
    }