#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
融合调度器
多模态认知负荷融合的核心模块

职责：
1. 协调各评分器的评分计算
2. 管理模态可用性
3. 执行多模态融合
4. 返回标准化响应
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .schemas.cognitive_load import (
    CognitiveLoadRequest,
    CognitiveLoadResponse,
    CognitiveLevel,
    TaskSource,
    BehaviorEvent,
    BehaviorFeatures,
    NASATLXAnswers,
    NASATLXFeatures,
    EEGFeatures,
)
from .modalities import BehaviorScorer, NASATLXScorer, EEGScorer


class FusionOrchestrator:
    """
    融合调度器

    协调行为评分器、问卷评分器、EEG评分器的工作，
    实现多模态认知负荷的加权融合
    """

    DEFAULT_WEIGHTS = {
        "behavior": 0.4,
        "questionnaire": 0.6,
        "eeg": 0.0
    }

    DEFAULT_THRESHOLDS = {
        "low": 0.4,
        "high": 0.7
    }

    def __init__(
        self,
        behavior_scorer: Optional[BehaviorScorer] = None,
        nasa_scorer: Optional[NASATLXScorer] = None,
        eeg_scorer: Optional[EEGScorer] = None,
        modality_weights: Optional[Dict[str, float]] = None,
        user_baseline: Optional[float] = None
    ):
        """
        初始化融合调度器

        Args:
            behavior_scorer: 行为评分器
            nasa_scorer: NASA-TLX评分器
            eeg_scorer: EEG评分器
            modality_weights: 各模态权重
            user_baseline: 用户认知负荷基线（用于个性化阈值）
        """
        self.behavior_scorer = behavior_scorer or BehaviorScorer()
        self.nasa_scorer = nasa_scorer or NASATLXScorer()
        self.eeg_scorer = eeg_scorer or EEGScorer()
        self.modality_weights = modality_weights or self.DEFAULT_WEIGHTS.copy()
        self._user_baseline = user_baseline
        self._thresholds = self.DEFAULT_THRESHOLDS.copy()

    @property
    def available_modalities(self) -> List[str]:
        """
        获取当前可用的评估模态

        Returns:
            可用模态列表
        """
        modalities = []
        if self._has_behavior_data():
            modalities.append("behavior")
        if self._has_questionnaire_data():
            modalities.append("questionnaire")
        if self.eeg_scorer.is_available():
            modalities.append("eeg")
        return modalities

    def assess(self, request: CognitiveLoadRequest) -> CognitiveLoadResponse:
        """
        执行认知负荷评估

        Args:
            request: 评估请求

        Returns:
            CognitiveLoadResponse: 评估响应
        """
        behavior_score = None
        behavior_features = None
        questionnaire_score = None
        questionnaire_features = None
        eeg_score = None
        eeg_features = None

        available_modalities = []

        if request.behavior_events or request.behavior_features:
            if request.behavior_events and not request.behavior_features:
                behavior_features = self.behavior_scorer.compute_features(request.behavior_events)
            else:
                behavior_features = request.behavior_features

            if behavior_features:
                behavior_score = self.behavior_scorer.score(behavior_features)
                available_modalities.append("behavior")

        if request.nasa_tlx_answers:
            features = self.nasa_scorer.compute_features(request.nasa_tlx_answers)
            questionnaire_features = features
            questionnaire_score = self.nasa_scorer.score(features)
            available_modalities.append("questionnaire")

        if request.eeg_features and self.eeg_scorer.is_available():
            eeg_score = self.eeg_scorer.score(request.eeg_features)
            eeg_features = request.eeg_features
            if eeg_score is not None:
                available_modalities.append("eeg")

        final_score, fusion_method = self._fuse_scores(
            behavior_score,
            questionnaire_score,
            eeg_score,
            available_modalities
        )

        level = self._get_level(final_score)

        duration_ms = None
        if request.task_start_ts and request.task_end_ts:
            duration_ms = request.task_end_ts - request.task_start_ts

        response = CognitiveLoadResponse(
            user_id=request.user_id,
            task_id=request.task_id,
            source=request.source,
            final_score=round(final_score, 4),
            level=CognitiveLevel(level),
            behavior_score=round(behavior_score, 4) if behavior_score is not None else None,
            questionnaire_score=round(questionnaire_score, 4) if questionnaire_score is not None else None,
            eeg_score=round(eeg_score, 4) if eeg_score is not None else None,
            behavior_features=behavior_features,
            questionnaire_features=questionnaire_features,
            eeg_features=eeg_features,
            fusion_method=fusion_method,
            available_modalities=available_modalities,
            modality_weights=self._get_adjusted_weights(available_modalities),
            created_at=datetime.now().isoformat()
        )

        if duration_ms:
            response_dict = response.model_dump()
            response_dict['duration_ms'] = duration_ms
            response = CognitiveLoadResponse(**response_dict)

        return response

    def _has_behavior_data(self) -> bool:
        """检查是否有行为数据"""
        return True

    def _has_questionnaire_data(self) -> bool:
        """检查是否有问卷数据"""
        return True

    def _fuse_scores(
        self,
        behavior_score: Optional[float],
        questionnaire_score: Optional[float],
        eeg_score: Optional[float],
        available_modalities: List[str]
    ) -> Tuple[float, str]:
        """
        融合各模态评分

        Args:
            behavior_score: 行为评分
            questionnaire_score: 问卷评分
            eeg_score: EEG评分
            available_modalities: 可用模态列表

        Returns:
            (融合评分, 融合方法)
        """
        if not available_modalities:
            return 0.5, "default"

        weights = self._get_adjusted_weights(available_modalities)

        total_score = 0.0
        total_weight = 0.0

        if "behavior" in available_modalities and behavior_score is not None:
            weight = weights.get("behavior", 0)
            total_score += behavior_score * weight
            total_weight += weight

        if "questionnaire" in available_modalities and questionnaire_score is not None:
            weight = weights.get("questionnaire", 0)
            total_score += questionnaire_score * weight
            total_weight += weight

        if "eeg" in available_modalities and eeg_score is not None:
            weight = weights.get("eeg", 0)
            total_score += eeg_score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.5, "weighted"

        final_score = total_score / total_weight
        return final_score, "weighted"

    def _get_adjusted_weights(self, available_modalities: List[str]) -> Dict[str, float]:
        """
        根据可用模态调整权重

        如果只有部分模态可用，等比例放大可用模态的权重

        Args:
            available_modalities: 可用模态列表

        Returns:
            调整后的权重字典
        """
        if not available_modalities:
            return self.modality_weights.copy()

        total_weight = sum(
            self.modality_weights.get(m, 0)
            for m in available_modalities
        )

        if total_weight == 0:
            return self.modality_weights.copy()

        adjusted = {}
        for m in available_modalities:
            original = self.modality_weights.get(m, 0)
            adjusted[m] = original / total_weight

        return adjusted

    def _get_level(self, score: float) -> str:
        """
        根据评分获取负荷等级

        Args:
            score: 综合评分(0-1)

        Returns:
            负荷等级: low/medium/high
        """
        thresholds = self._get_personalized_thresholds()
        if score < thresholds["low"]:
            return "low"
        elif score < thresholds["high"]:
            return "medium"
        else:
            return "high"

    def _get_personalized_thresholds(self) -> Dict[str, float]:
        """
        获取个性化阈值（基于用户基线）

        Returns:
            阈值字典
        """
        if self._user_baseline is not None:
            low_threshold = max(0.1, self._user_baseline * 0.7)
            high_threshold = min(0.9, self._user_baseline * 1.3)
            return {"low": low_threshold, "high": high_threshold}
        return self._thresholds

    def set_user_baseline(self, user_id: str, baseline_score: float) -> None:
        """
        设置用户认知负荷基线

        Args:
            user_id: 用户ID
            baseline_score: 基线评分(0-1)
        """
        self._user_baseline = baseline_score
        self._thresholds = self._get_personalized_thresholds()

    def get_user_baseline(self) -> Optional[float]:
        """获取当前用户基线"""
        return self._user_baseline

    def update_weights(self, weights: Dict[str, float]) -> None:
        """
        更新模态权重

        Args:
            weights: 新的权重字典
        """
        self.modality_weights.update(weights)

    def get_modality_status(self) -> Dict:
        """
        获取各模态状态

        Returns:
            模态状态字典
        """
        return {
            "behavior": {
                "available": True,
                "weight": self.modality_weights.get("behavior", 0)
            },
            "questionnaire": {
                "available": True,
                "weight": self.modality_weights.get("questionnaire", 0)
            },
            "eeg": {
                "available": self.eeg_scorer.is_available(),
                "weight": self.modality_weights.get("eeg", 0),
                "device_type": getattr(self.eeg_scorer, '_device_type', None)
            }
        }


Orchestrator_instance = FusionOrchestrator()
