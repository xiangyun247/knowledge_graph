#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行为评分器
基于用户行为事件的认知负荷评分

行为指标设计：
- 点击次数、点击密度
- 回退次数、回退率
- 错误次数、错误率
- 步骤数、完成率
- 任务耗时、每步平均耗时

评分逻辑：
- 回退率高 → 认知负荷高
- 错误率高 → 认知负荷高
- 任务耗时长 → 认知负荷高
- 点击密度高 → 认知负荷高
- 完成率低 → 认知负荷高
"""

from typing import Dict, List, Optional
from ..schemas.cognitive_load import BehaviorEvent, BehaviorFeatures, EventType


class BehaviorScorer:
    """
    行为评分器

    支持功能：
    1. 从事件列表计算行为特征
    2. 基于特征计算认知负荷评分
    3. 识别异常行为模式
    """

    DEFAULT_CONFIG = {
        "back_rate_weight": 0.25,
        "error_rate_weight": 0.20,
        "click_density_weight": 0.15,
        "duration_weight": 0.20,
        "completion_rate_weight": 0.20,
    }

    THRESHOLDS = {
        "back_rate": {
            "low": 0.1,
            "medium": 0.2,
            "high": 0.3
        },
        "error_rate": {
            "low": 0.05,
            "medium": 0.1,
            "high": 0.15
        },
        "click_density": {
            "low": 0.3,
            "medium": 0.6,
            "high": 0.8
        },
        "duration_sec": {
            "low": 30,
            "medium": 90,
            "high": 180
        },
        "completion_rate": {
            "low": 0.9,
            "medium": 0.7,
            "high": 0.5
        }
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化评分器

        Args:
            config: 评分配置，包含各指标权重
        """
        self.config = config or self.DEFAULT_CONFIG.copy()

    def compute_features(self, events: List[BehaviorEvent]) -> BehaviorFeatures:
        """
        从事件列表计算行为特征

        Args:
            events: 行为事件列表

        Returns:
            BehaviorFeatures: 行为特征对象
        """
        if not events:
            return BehaviorFeatures()

        event_dicts = [e.model_dump() if hasattr(e, 'model_dump') else e for e in events]
        events = event_dicts if event_dicts else events

        click_count = sum(1 for e in events if e.get("event_type") == EventType.CLICK.value)
        back_count = sum(1 for e in events if e.get("event_type") == EventType.BACK.value)
        error_count = sum(1 for e in events if e.get("event_type") == EventType.ERROR_OR_REPEAT.value)

        task_start = next((e for e in events if e.get("event_type") == EventType.TASK_START.value), None)
        task_end = next((e for e in events if e.get("event_type") == EventType.TASK_END.value), None)

        duration_ms = 0
        if task_start and task_end:
            duration_ms = task_end.get("ts", 0) - task_start.get("ts", 0)
        elif events:
            ts_list = [e.get("ts", 0) for e in events if e.get("ts")]
            if len(ts_list) >= 2:
                duration_ms = max(ts_list) - min(ts_list)

        step_views = [e for e in events if e.get("event_type") == EventType.STEP_VIEW.value]
        step_count = len(step_views)

        total_steps = 1
        if step_views:
            total_steps = max((e.get("total_steps", 1) or 1) for e in step_views)

        total_interactions = click_count + back_count + error_count
        back_rate = back_count / max(total_interactions, 1)
        error_rate = error_count / max(total_interactions, 1)

        click_density = click_count / max(duration_ms / 1000, 1)

        completion_rate = 1.0
        if task_end:
            completion_rate = min(step_count / max(total_steps, 1), 1.0)

        avg_time_per_step = duration_ms / max(step_count, 1)

        return BehaviorFeatures(
            click_count=click_count,
            back_count=back_count,
            error_count=error_count,
            step_count=step_count,
            back_rate=round(back_rate, 4),
            error_rate=round(error_rate, 4),
            click_density=round(click_density, 4),
            completion_rate=round(completion_rate, 4),
            avg_time_per_step=round(avg_time_per_step, 2),
            total_duration_ms=duration_ms
        )

    def score(self, features: BehaviorFeatures) -> float:
        """
        基于行为特征计算认知负荷评分

        评分公式：
        - 回退率评分：回退率高 → 负荷高
        - 错误率评分：错误率高 → 负荷高
        - 点击密度评分：密度高 → 负荷高
        - 耗时评分：耗时长 → 负荷高
        - 完成率评分：完成率低 → 负荷高

        Args:
            features: 行为特征

        Returns:
            0-1之间的认知负荷分数
        """
        back_score = self._normalize_metric(
            features.back_rate,
            self.THRESHOLDS["back_rate"]["low"],
            self.THRESHOLDS["back_rate"]["high"],
            invert=False
        )

        error_score = self._normalize_metric(
            features.error_rate,
            self.THRESHOLDS["error_rate"]["low"],
            self.THRESHOLDS["error_rate"]["high"],
            invert=False
        )

        click_score = self._normalize_metric(
            features.click_density,
            self.THRESHOLDS["click_density"]["low"],
            self.THRESHOLDS["click_density"]["high"],
            invert=False
        )

        duration_sec = features.total_duration_ms / 1000
        duration_score = self._normalize_metric(
            duration_sec,
            self.THRESHOLDS["duration_sec"]["low"],
            self.THRESHOLDS["duration_sec"]["high"],
            invert=False
        )

        completion_score = self._normalize_metric(
            features.completion_rate,
            self.THRESHOLDS["completion_rate"]["low"],
            self.THRESHOLDS["completion_rate"]["high"],
            invert=True
        )

        weighted_score = (
            back_score * self.config["back_rate_weight"] +
            error_score * self.config["error_rate_weight"] +
            click_score * self.config["click_density_weight"] +
            duration_score * self.config["duration_weight"] +
            completion_score * self.config["completion_rate_weight"]
        )

        return round(min(max(weighted_score, 0.0), 1.0), 4)

    def _normalize_metric(
        self,
        value: float,
        low_thresh: float,
        high_thresh: float,
        invert: bool = False
    ) -> float:
        """
        将指标值归一化到0-1

        Args:
            value: 指标值
            low_thresh: 低阈值（正常水平）
            high_thresh: 高阈值（高负荷水平）
            invert: 是否反转（如完成率是越高越好）

        Returns:
            归一化后的分数
        """
        if high_thresh <= low_thresh:
            return 0.5

        normalized = (value - low_thresh) / (high_thresh - low_thresh)
        normalized = min(max(normalized, 0.0), 1.0)

        if invert:
            normalized = 1.0 - normalized

        return normalized

    def get_level(self, score: float) -> str:
        """
        根据评分获取负荷等级

        Args:
            score: 认知负荷评分(0-1)

        Returns:
            负荷等级: low/medium/high
        """
        if score < 0.35:
            return "low"
        elif score < 0.65:
            return "medium"
        else:
            return "high"

    def generate_suggestions(self, features: BehaviorFeatures) -> List[Dict]:
        """
        根据行为特征生成建议

        Args:
            features: 行为特征

        Returns:
            建议列表
        """
        suggestions = []

        if features.back_rate > 0.2:
            suggestions.append({
                "category": "导航优化",
                "priority": "high" if features.back_rate > 0.3 else "medium",
                "suggestion": "增加'上一步'确认提示，减少用户回退需求",
                "expected_impact": "可减少30-40%回退操作",
                "source": "回退率行为分析"
            })

        if features.error_rate > 0.1:
            suggestions.append({
                "category": "界面优化",
                "priority": "high" if features.error_rate > 0.15 else "medium",
                "suggestion": "优化按钮位置和样式，减少误操作",
                "expected_impact": "可减少20-30%错误操作",
                "source": "错误率行为分析"
            })

        if features.click_density > 0.6:
            suggestions.append({
                "category": "界面简化",
                "priority": "medium",
                "suggestion": "减少界面元素数量，聚焦核心操作",
                "expected_impact": "可降低视觉搜索负担",
                "source": "点击密度行为分析"
            })

        if features.total_duration_ms > 180000:
            suggestions.append({
                "category": "内容拆分",
                "priority": "medium",
                "suggestion": "将长内容拆分为多个短任务，分段完成",
                "expected_impact": "可减少单次任务耗时",
                "source": "任务耗时行为分析"
            })

        if features.completion_rate < 0.7:
            suggestions.append({
                "category": "任务简化",
                "priority": "high",
                "suggestion": "减少单次任务的步骤数量，降低完成难度",
                "expected_impact": "可提高15-25%完成率",
                "source": "完成率行为分析"
            })

        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda x: priority_order.get(x["priority"], 2))

        return suggestions[:5]


BehaviorScorer_instance = BehaviorScorer()
