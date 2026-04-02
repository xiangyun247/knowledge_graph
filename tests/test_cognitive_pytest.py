#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认知负荷评估模块pytest测试
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.cognitive.modalities.nasa_tlx_scorer import NASATLXScorer
from backend.cognitive.modalities.behavior_scorer import BehaviorScorer
from backend.cognitive.fusion_orchestrator import FusionOrchestrator
from backend.cognitive.schemas.cognitive_load import (
    NASATLXAnswers,
    BehaviorEvent,
    EventType,
    CognitiveLoadRequest,
    TaskSource
)


class TestNASATLXScorer:
    """NASA-TLX评分器测试"""

    def setup_method(self):
        self.scorer = NASATLXScorer()

    def test_compute_features_normalization(self):
        """测试特征计算与归一化"""
        answers = NASATLXAnswers(**{k: 4 for k in self.scorer.DIMENSION_NAMES})
        features = self.scorer.compute_features(answers)

        assert hasattr(features, "mental_demand")
        assert hasattr(features, "physical_demand")
        assert 0 <= features.mental_demand <= 1
        assert 0 <= features.physical_demand <= 1

    def test_score_returns_0_1_range(self):
        """测试评分在0-1范围内"""
        answers = NASATLXAnswers(**{k: 4 for k in self.scorer.DIMENSION_NAMES})
        features = self.scorer.compute_features(answers)
        score = self.scorer.score(features)

        assert 0 <= score <= 1, f"Score {score} out of range [0,1]"

    def test_get_level_returns_valid_value(self):
        """测试等级返回有效值"""
        answers = NASATLXAnswers(**{k: 4 for k in self.scorer.DIMENSION_NAMES})
        features = self.scorer.compute_features(answers)
        score = self.scorer.score(features)
        level = self.scorer.get_level(score)

        assert level in ["low", "medium", "high"], f"Invalid level: {level}"

    def test_get_radar_chart_data_returns_dimensions(self):
        """测试雷达图数据"""
        answers = NASATLXAnswers(**{k: 4 for k in self.scorer.DIMENSION_NAMES})
        features = self.scorer.compute_features(answers)
        radar_data = self.scorer.get_radar_chart_data(features)

        assert "dimensions" in radar_data
        assert "norm_values" in radar_data
        assert len(radar_data["dimensions"]) == 6

    def test_generate_suggestions_returns_list(self):
        """测试建议生成返回列表"""
        answers = NASATLXAnswers(**{k: 4 for k in self.scorer.DIMENSION_NAMES})
        features = self.scorer.compute_features(answers)
        suggestions = self.scorer.generate_suggestions(features)

        assert isinstance(suggestions, list)

    def test_minimum_score_boundary(self):
        """测试最低分边界"""
        answers = NASATLXAnswers(**{k: 1 for k in self.scorer.DIMENSION_NAMES})
        features = self.scorer.compute_features(answers)
        score = self.scorer.score(features)

        assert 0 <= score <= 1

    def test_maximum_score_boundary(self):
        """测试最高分边界"""
        answers = NASATLXAnswers(**{k: 7 for k in self.scorer.DIMENSION_NAMES})
        features = self.scorer.compute_features(answers)
        score = self.scorer.score(features)

        assert 0 <= score <= 1


class TestBehaviorScorer:
    """行为评分器测试"""

    def setup_method(self):
        self.scorer = BehaviorScorer()

    def test_compute_features_click_count(self):
        """测试点击次数计算"""
        events = [
            BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            BehaviorEvent(event_type=EventType.CLICK, ts=2000, params={}),
            BehaviorEvent(event_type=EventType.CLICK, ts=3000, params={}),
        ]
        features = self.scorer.compute_features(events)

        assert features.click_count == 3, f"Expected 3 clicks, got {features.click_count}"

    def test_compute_features_back_count(self):
        """测试回退次数计算"""
        events = [
            BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            BehaviorEvent(event_type=EventType.BACK, ts=2000, params={}),
            BehaviorEvent(event_type=EventType.CLICK, ts=3000, params={}),
            BehaviorEvent(event_type=EventType.BACK, ts=4000, params={}),
        ]
        features = self.scorer.compute_features(events)

        assert features.back_count == 2, f"Expected 2 back actions, got {features.back_count}"

    def test_score_returns_0_1_range(self):
        """测试评分在0-1范围内"""
        events = [
            BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            BehaviorEvent(event_type=EventType.BACK, ts=2000, params={}),
        ]
        features = self.scorer.compute_features(events)
        score = self.scorer.score(features)

        assert 0 <= score <= 1, f"Score {score} out of range [0,1]"

    def test_get_level_returns_valid_value(self):
        """测试等级返回有效值"""
        events = [
            BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
        ]
        features = self.scorer.compute_features(events)
        score = self.scorer.score(features)
        level = self.scorer.get_level(score)

        assert level in ["low", "medium", "high"], f"Invalid level: {level}"


class TestFusionOrchestrator:
    """融合编排器测试"""

    def setup_method(self):
        self.orchestrator = FusionOrchestrator()

    def test_assess_returns_valid_response(self):
        """测试评估返回有效响应"""
        request = CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=TaskSource.PATIENT_EDUCATION,
            behavior_events=[
                BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            ],
            nasa_tlx_answers=NASATLXAnswers(**{k: 4 for k in ["mental_demand", "physical_demand", "temporal_demand", "performance", "effort", "frustration"]})
        )

        response = self.orchestrator.assess(request)

        assert response is not None
        assert hasattr(response, "final_score")
        assert hasattr(response, "level")
        assert hasattr(response, "available_modalities")

    def test_final_score_in_0_1_range(self):
        """测试最终评分在0-1范围内"""
        request = CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=TaskSource.PATIENT_EDUCATION,
            behavior_events=[
                BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            ],
            nasa_tlx_answers=NASATLXAnswers(**{k: 4 for k in ["mental_demand", "physical_demand", "temporal_demand", "performance", "effort", "frustration"]})
        )

        response = self.orchestrator.assess(request)

        assert 0 <= response.final_score <= 1, f"Final score {response.final_score} out of range [0,1]"

    def test_level_is_valid_value(self):
        """测试等级是有效值"""
        request = CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=TaskSource.PATIENT_EDUCATION,
            behavior_events=[
                BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            ],
            nasa_tlx_answers=NASATLXAnswers(**{k: 4 for k in ["mental_demand", "physical_demand", "temporal_demand", "performance", "effort", "frustration"]})
        )

        response = self.orchestrator.assess(request)

        assert response.level in ["low", "medium", "high"], f"Invalid level: {response.level}"

    def test_available_modalities_includes_behavior_and_questionnaire(self):
        """测试可用模态包含行为和问卷"""
        request = CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=TaskSource.PATIENT_EDUCATION,
            behavior_events=[
                BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            ],
            nasa_tlx_answers=NASATLXAnswers(**{k: 4 for k in ["mental_demand", "physical_demand", "temporal_demand", "performance", "effort", "frustration"]})
        )

        response = self.orchestrator.assess(request)

        assert "behavior" in response.available_modalities
        assert "questionnaire" in response.available_modalities

    def test_questionnaire_score_calculated(self):
        """测试问卷评分已计算"""
        request = CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=TaskSource.PATIENT_EDUCATION,
            behavior_events=[
                BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            ],
            nasa_tlx_answers=NASATLXAnswers(**{k: 4 for k in ["mental_demand", "physical_demand", "temporal_demand", "performance", "effort", "frustration"]})
        )

        response = self.orchestrator.assess(request)

        assert response.questionnaire_score is not None
        assert 0 <= response.questionnaire_score <= 1

    def test_behavior_score_calculated(self):
        """测试行为评分已计算"""
        request = CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=TaskSource.PATIENT_EDUCATION,
            behavior_events=[
                BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            ],
            nasa_tlx_answers=NASATLXAnswers(**{k: 4 for k in ["mental_demand", "physical_demand", "temporal_demand", "performance", "effort", "frustration"]})
        )

        response = self.orchestrator.assess(request)

        assert response.behavior_score is not None
        assert 0 <= response.behavior_score <= 1

    def test_get_modality_status_returns_status_dict(self):
        """测试获取模态状态返回状态字典"""
        status = self.orchestrator.get_modality_status()

        assert isinstance(status, dict)
        assert "behavior" in status
        assert "questionnaire" in status
        assert "eeg" in status


class TestEdgeCases:
    """边界情况测试"""

    def test_without_behavior_data_questionnaire_only(self):
        """测试无行为数据时只用问卷"""
        orchestrator = FusionOrchestrator()
        request = CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=TaskSource.PATIENT_EDUCATION,
            behavior_events=[],
            nasa_tlx_answers=NASATLXAnswers(**{k: 4 for k in ["mental_demand", "physical_demand", "temporal_demand", "performance", "effort", "frustration"]})
        )

        response = orchestrator.assess(request)

        assert response.final_score is not None
        assert "questionnaire" in response.available_modalities

    def test_without_questionnaire_valid_response(self):
        """测试无问卷时返回有效响应"""
        orchestrator = FusionOrchestrator()
        request = CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=TaskSource.PATIENT_EDUCATION,
            behavior_events=[
                BehaviorEvent(event_type=EventType.CLICK, ts=1000, params={}),
            ],
            nasa_tlx_answers=None
        )

        response = orchestrator.assess(request)

        assert response.final_score is not None
        assert "behavior" in response.available_modalities


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
