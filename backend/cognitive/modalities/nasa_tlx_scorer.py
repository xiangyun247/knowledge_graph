#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NASA-TLX 评分器
简化版NASA-TLX问卷评分实现

理论基础：
- NASA-TLX是主观工作负荷评估的金标准
- 原始版本包含20步配对比较（确定各维度权重），过于复杂
- 简化版直接使用6个维度等权重评分，适合老年人/快速评估

评分维度（每项1-7分）：
- mental_demand: 脑力需求（需要多少脑力思考？）
- physical_demand: 体力需求（需要多少体力？）
- temporal_demand: 时间需求（时间够用吗？）
- performance: 绩效感知（对自己的表现满意吗？）
- effort: 努力程度（需要多少努力才能完成？）
- frustration: 挫败感（完成过程让你烦躁吗？）
"""

from typing import Dict, List, Optional
from ..schemas.cognitive_load import NASATLXAnswers, NASATLXFeatures


class NASATLXScorer:
    """
    NASA-TLX问卷评分器

    支持功能：
    1. 计算各维度归一化评分(0-1)
    2. 计算综合问卷评分
    3. 获取各维度权重（预留动态调整接口）
    """

    DIMENSION_NAMES = [
        "mental_demand",
        "physical_demand",
        "temporal_demand",
        "performance",
        "effort",
        "frustration"
    ]

    DIMENSION_LABELS = {
        "mental_demand": "脑力需求",
        "physical_demand": "体力需求",
        "temporal_demand": "时间需求",
        "performance": "绩效感知",
        "effort": "努力程度",
        "frustration": "挫败感"
    }

    DEFAULT_WEIGHTS = {
        "mental_demand": 1.0,
        "physical_demand": 1.0,
        "temporal_demand": 1.0,
        "performance": 1.0,
        "effort": 1.0,
        "frustration": 1.0
    }

    ELDERLY_NORM_VALUES = {
        "mental_demand": 0.60,
        "physical_demand": 0.18,
        "temporal_demand": 0.32,
        "performance": 0.50,
        "effort": 0.70,
        "frustration": 0.30
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        初始化评分器

        Args:
            weights: 各维度权重，不传则使用等权重
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def compute_features(self, answers: NASATLXAnswers) -> NASATLXFeatures:
        """
        计算NASA-TLX各维度特征（归一化到0-1）

        Args:
            answers: NASA-TLX原始答案（1-7分）

        Returns:
            NASATLXFeatures: 各维度归一化评分
        """
        return NASATLXFeatures(
            mental_demand=self._normalize(answers.mental_demand),
            physical_demand=self._normalize(answers.physical_demand),
            temporal_demand=self._normalize(answers.temporal_demand),
            performance=self._normalize(answers.performance),
            effort=self._normalize(answers.effort),
            frustration=self._normalize(answers.frustration)
        )

    def score(self, features: NASATLXFeatures) -> float:
        """
        计算NASA-TLX综合评分

        公式：
        1. 将1-7分归一化到0-1: (raw - 1) / 6
        2. 各维度加权平均

        注意：
        - 绩效(performance)是反向的：高分表示表现好=认知负荷低
        - 其他维度高分都表示认知负荷高

        Args:
            features: NASA-TLX各维度特征

        Returns:
            0-1之间的认知负荷分数（越高负荷越高）
        """
        scores = []
        total_weight = 0.0

        for dim in self.DIMENSION_NAMES:
            dim_score = getattr(features, dim)
            dim_weight = self.weights.get(dim, 1.0)

            if dim == "performance":
                dim_score = 1.0 - dim_score

            scores.append(dim_score * dim_weight)
            total_weight += dim_weight

        if total_weight == 0:
            return 0.5

        return sum(scores) / total_weight

    def score_from_answers(self, answers: NASATLXAnswers) -> float:
        """
        从原始答案直接计算评分（便捷方法）

        Args:
            answers: NASA-TLX原始答案

        Returns:
            0-1之间的认知负荷分数
        """
        features = self.compute_features(answers)
        return self.score(features)

    def _normalize(self, value: int) -> float:
        """
        将1-7分归一化到0-1

        Args:
            value: 原始分数(1-7)

        Returns:
            归一化分数(0-1)
        """
        return (value - 1) / 6.0

    def get_radar_chart_data(self, features: NASATLXFeatures) -> Dict:
        """
        获取雷达图数据

        Args:
            features: NASA-TLX各维度特征

        Returns:
            雷达图数据字典
        """
        dimensions = [self.DIMENSION_LABELS[dim] for dim in self.DIMENSION_NAMES]
        raw_scores = []
        scores = []
        norm_values = []

        for dim in self.DIMENSION_NAMES:
            raw_val = int(getattr(features, dim) * 6 + 1)
            raw_scores.append(raw_val)
            scores.append(round(getattr(features, dim), 3))
            norm_values.append(self.ELDERLY_NORM_VALUES.get(dim, 0.5))

        return {
            "dimensions": dimensions,
            "scores": scores,
            "raw_scores": raw_scores,
            "norm_values": norm_values
        }

    def update_weights(self, weights: Dict[str, float]) -> None:
        """
        更新维度权重

        Args:
            weights: 新的权重字典
        """
        for dim in self.DIMENSION_NAMES:
            if dim in weights:
                self.weights[dim] = weights[dim]

    def get_level(self, score: float) -> str:
        """
        根据评分获取负荷等级

        Args:
            score: 认知负荷评分(0-1)

        Returns:
            负荷等级: low/medium/high
        """
        if score < 0.4:
            return "low"
        elif score < 0.7:
            return "medium"
        else:
            return "high"

    def generate_suggestions(self, features: NASATLXFeatures) -> List[Dict]:
        """
        根据评分生成个性化建议

        Args:
            features: NASA-TLX各维度特征

        Returns:
            建议列表
        """
        suggestions = []

        mental = features.mental_demand
        if mental >= 0.67:
            suggestions.append({
                "category": "内容优化",
                "priority": "high",
                "suggestion": "建议将长段落内容拆分为更小的步骤，每步聚焦一个要点",
                "expected_impact": "可降低20-30%脑力负荷",
                "source": "NASA-TLX脑力需求维度分析"
            })
            suggestions.append({
                "category": "呈现方式",
                "priority": "high",
                "suggestion": "使用通俗语言，避免专业术语，必要时提供通俗解释",
                "expected_impact": "可降低15-25%理解难度",
                "source": "NASA-TLX脑力需求维度分析"
            })

        frustration = features.frustration
        if frustration >= 0.5:
            suggestions.append({
                "category": "用户体验",
                "priority": "high",
                "suggestion": "增加进度指示器，让用户知道当前进度和剩余时间",
                "expected_impact": "可降低焦虑感和挫败感",
                "source": "NASA-TLX挫败感维度分析"
            })

        temporal = features.temporal_demand
        if temporal >= 0.67:
            suggestions.append({
                "category": "时间安排",
                "priority": "medium",
                "suggestion": "避免在用户疲劳时段（如下午3点、晚饭后）安排复杂任务",
                "expected_impact": "可减少15-20%时间压力感",
                "source": "NASA-TLX时间需求维度分析"
            })

        effort = features.effort
        if effort >= 0.67:
            suggestions.append({
                "category": "操作简化",
                "priority": "medium",
                "suggestion": "减少操作步骤，提供更多操作引导和示例",
                "expected_impact": "可降低10-20%努力程度",
                "source": "NASA-TLX努力程度维度分析"
            })

        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda x: priority_order.get(x["priority"], 2))

        return suggestions[:5]


NASATLXScorer_instance = NASATLXScorer()
