#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认知负荷模块测试用例
"""
import os
import pytest
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-min-32chars")


class TestNASATLXScorer:
    """NASA-TLX 评分器测试"""

    def setup_method(self):
        """每个测试方法前设置"""
        import os
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-min-32chars"
        from backend.cognitive.modalities.nasa_tlx_scorer import NASATLXScorer
        from backend.cognitive.schemas.cognitive_load import NASATLXAnswers
        self.scorer = NASATLXScorer()
        self.NASATLXAnswers = NASATLXAnswers

    def test_compute_features_low_workload(self):
        """测试低负荷答案的特征计算"""
        answers = self.NASATLXAnswers(
            mental_demand=2,
            physical_demand=1,
            temporal_demand=2,
            performance=6,
            effort=2,
            frustration=1
        )
        features = self.scorer.compute_features(answers)

        assert features.mental_demand == pytest.approx(1/6, rel=0.01)
        assert features.performance == pytest.approx(5/6, rel=0.01)
        assert features.frustration == pytest.approx(0.0)

    def test_compute_features_high_workload(self):
        """测试高负荷答案的特征计算"""
        answers = self.NASATLXAnswers(
            mental_demand=7,
            physical_demand=6,
            temporal_demand=7,
            performance=2,
            effort=7,
            frustration=7
        )
        features = self.scorer.compute_features(answers)

        assert features.mental_demand == pytest.approx(1.0, rel=0.01)
        assert features.frustration == pytest.approx(1.0, rel=0.01)

    def test_score_low_workload(self):
        """测试低负荷评分（应返回较低分数）"""
        answers = self.NASATLXAnswers(
            mental_demand=1,
            physical_demand=1,
            temporal_demand=1,
            performance=7,
            effort=1,
            frustration=1
        )
        score = self.scorer.score_from_answers(answers)
        assert score < 0.3

    def test_score_high_workload(self):
        """测试高负荷评分（应返回较高分数）"""
        answers = self.NASATLXAnswers(
            mental_demand=7,
            physical_demand=7,
            temporal_demand=7,
            performance=1,
            effort=7,
            frustration=7
        )
        score = self.scorer.score_from_answers(answers)
        assert score > 0.7

    def test_score_medium_workload(self):
        """测试中等负荷评分"""
        answers = self.NASATLXAnswers(
            mental_demand=4,
            physical_demand=3,
            temporal_demand=4,
            performance=4,
            effort=4,
            frustration=3
        )
        score = self.scorer.score_from_answers(answers)
        assert 0.3 <= score <= 0.7

    def test_performance_dimension_inverted(self):
        """测试绩效维度是反向的（高分=低负荷）"""
        answers_high_perf = self.NASATLXAnswers(
            mental_demand=1,
            physical_demand=1,
            temporal_demand=1,
            performance=7,
            effort=1,
            frustration=1
        )
        answers_low_perf = self.NASATLXAnswers(
            mental_demand=1,
            physical_demand=1,
            temporal_demand=1,
            performance=1,
            effort=1,
            frustration=1
        )

        score_high_perf = self.scorer.score_from_answers(answers_high_perf)
        score_low_perf = self.scorer.score_from_answers(answers_low_perf)

        assert score_low_perf > score_high_perf

    def test_normalize_formula(self):
        """测试归一化公式 (value-1)/6"""
        assert self.scorer._normalize(1) == pytest.approx(0.0)
        assert self.scorer._normalize(4) == pytest.approx(0.5, rel=0.01)
        assert self.scorer._normalize(7) == pytest.approx(1.0)

    def test_get_radar_chart_data(self):
        """测试雷达图数据生成"""
        from backend.cognitive.schemas.cognitive_load import NASATLXFeatures
        features = NASATLXFeatures(
            mental_demand=0.5,
            physical_demand=0.3,
            temporal_demand=0.5,
            performance=0.5,
            effort=0.7,
            frustration=0.2
        )
        data = self.scorer.get_radar_chart_data(features)

        assert "dimensions" in data
        assert "scores" in data
        assert len(data["dimensions"]) == 6
        assert len(data["scores"]) == 6

    def test_custom_weights(self):
        """测试自定义权重"""
        from backend.cognitive.modalities.nasa_tlx_scorer import NASATLXScorer
        weights = {"mental_demand": 2.0, "physical_demand": 0.0, "temporal_demand": 0.0,
                   "performance": 0.0, "effort": 0.0, "frustration": 0.0}
        scorer = NASATLXScorer(weights=weights)

        answers_low = self.NASATLXAnswers(mental_demand=1, physical_demand=7, temporal_demand=7,
                                          performance=1, effort=7, frustration=7)
        answers_high = self.NASATLXAnswers(mental_demand=7, physical_demand=1, temporal_demand=1,
                                           performance=7, effort=1, frustration=1)

        score_low = scorer.score_from_answers(answers_low)
        score_high = scorer.score_from_answers(answers_high)

        assert score_low < score_high


class TestBehaviorScorer:
    """行为评分器测试"""

    def setup_method(self):
        import os
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-min-32chars"
        from backend.cognitive.modalities.behavior_scorer import BehaviorScorer
        from backend.cognitive.schemas.cognitive_load import BehaviorEvent
        self.scorer = BehaviorScorer()
        self.BehaviorEvent = BehaviorEvent

    def test_compute_features_empty_events(self):
        """测试空事件列表"""
        features = self.scorer.compute_features([])
        assert features.click_count == 0
        assert features.back_count == 0
        assert features.error_count == 0

    def test_compute_features_with_clicks(self):
        """测试有点击事件的特征计算"""
        events = [
            self.BehaviorEvent(event_type="task_start", ts=1000),
            self.BehaviorEvent(event_type="click", ts=1100),
            self.BehaviorEvent(event_type="click", ts=1200),
            self.BehaviorEvent(event_type="click", ts=1300),
            self.BehaviorEvent(event_type="task_end", ts=2000),
        ]
        features = self.scorer.compute_features(events)
        assert features.click_count == 3
        assert features.total_duration_ms == 1000

    def test_compute_features_with_back(self):
        """测试有回退事件的特征计算"""
        events = [
            self.BehaviorEvent(event_type="task_start", ts=1000),
            self.BehaviorEvent(event_type="click", ts=1100),
            self.BehaviorEvent(event_type="back", ts=1200),
            self.BehaviorEvent(event_type="click", ts=1300),
            self.BehaviorEvent(event_type="task_end", ts=2000),
        ]
        features = self.scorer.compute_features(events)
        assert features.click_count == 2
        assert features.back_count == 1
        assert features.back_rate == pytest.approx(0.333, rel=0.1)

    def test_score_low_cognitive_load(self):
        """测试低认知负荷行为（少量点击，无回退）"""
        events = [
            self.BehaviorEvent(event_type="task_start", ts=1000),
            self.BehaviorEvent(event_type="click", ts=1100),
            self.BehaviorEvent(event_type="click", ts=1200),
            self.BehaviorEvent(event_type="task_end", ts=3000),
        ]
        features = self.scorer.compute_features(events)
        score = self.scorer.score(features)
        assert score < 0.4

    def test_score_high_cognitive_load(self):
        """测试高认知负荷行为（多次回退，错误）"""
        events = [
            self.BehaviorEvent(event_type="task_start", ts=1000),
            self.BehaviorEvent(event_type="click", ts=1100),
            self.BehaviorEvent(event_type="back", ts=1200),
            self.BehaviorEvent(event_type="error_or_repeat", ts=1300),
            self.BehaviorEvent(event_type="back", ts=1400),
            self.BehaviorEvent(event_type="click", ts=1500),
            self.BehaviorEvent(event_type="error_or_repeat", ts=1600),
            self.BehaviorEvent(event_type="task_end", ts=10000),
        ]
        features = self.scorer.compute_features(events)
        score = self.scorer.score(features)
        assert score > 0.5

    def test_score_empty_features(self):
        """测试空特征返回较低分数（默认行为）"""
        from backend.cognitive.schemas.cognitive_load import BehaviorFeatures
        features = BehaviorFeatures()
        score = self.scorer.score(features)
        assert 0 <= score <= 0.2


class TestEEGSimulator:
    """EEG模拟器测试"""

    def setup_method(self):
        import os
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-min-32chars"
        from backend.cognitive.modalities.eeg_simulator import EEGSimulator, SimulatorConfig, CognitiveLoadLevel
        self.EEGSimulator = EEGSimulator
        self.SimulatorConfig = SimulatorConfig
        self.CognitiveLoadLevel = CognitiveLoadLevel

    def test_simulator_initialization(self):
        """测试模拟器初始化"""
        sim = self.EEGSimulator()
        assert sim is not None
        assert sim.config is not None

    def test_generate_features_low_level(self):
        """测试生成低负荷EEG特征"""
        config = self.SimulatorConfig(cognitive_level=self.CognitiveLoadLevel.LOW)
        sim = self.EEGSimulator(config)
        features = sim.generate_features(add_noise=False)

        assert features.theta_power < features.alpha_power

    def test_generate_features_high_level(self):
        """测试生成高负荷EEG特征"""
        config = self.SimulatorConfig(cognitive_level=self.CognitiveLoadLevel.HIGH)
        sim = self.EEGSimulator(config)
        features = sim.generate_features(add_noise=False)

        assert features.theta_beta_ratio > 1.5

    def test_theta_beta_ratio_calculation(self):
        """测试Theta/Beta比率计算"""
        config = self.SimulatorConfig(cognitive_level=self.CognitiveLoadLevel.HIGH)
        sim = self.EEGSimulator(config)
        features = sim.generate_features(add_noise=False)

        expected_ratio = features.theta_power / features.beta_power
        assert features.theta_beta_ratio == pytest.approx(expected_ratio, rel=0.1)

    def test_noise_affects_features(self):
        """测试噪声影响特征"""
        config = self.SimulatorConfig(cognitive_level=self.CognitiveLoadLevel.MEDIUM)
        sim = self.EEGSimulator(config)

        features1 = sim.generate_features(add_noise=True)
        features2 = sim.generate_features(add_noise=True)

        assert features1.theta_power != features2.theta_power


class TestEEGScorer:
    """EEG评分器测试（模拟模式）"""

    def setup_method(self):
        import os
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-min-32chars"
        from backend.cognitive.modalities.eeg_scorer import EEGScorer
        from backend.cognitive.schemas.cognitive_load import EEGFeatures
        self.scorer = EEGScorer(simulation_mode=True)
        self.EEGFeatures = EEGFeatures

    def test_score_with_valid_features(self):
        """测试有效特征的评分"""
        features = self.EEGFeatures(
            delta_power=15.0,
            theta_power=10.0,
            alpha_power=8.0,
            beta_power=5.0,
            gamma_power=3.0,
            theta_beta_ratio=2.0,
            theta_alpha_ratio=1.25,
            alpha_beta_ratio=1.6
        )
        score = self.scorer.score(features)
        assert 0 <= score <= 1

    def test_score_none_features_raises_error(self):
        """测试None特征抛出TypeError"""
        with pytest.raises((TypeError, AttributeError)):
            self.scorer.score(None)

    def test_simulation_mode_enabled(self):
        """测试模拟模式已启用"""
        assert self.scorer.is_simulation_mode() is True

    def test_generate_simulated_features(self):
        """测试生成模拟特征"""
        features = self.scorer.generate_simulated_features()
        assert features is not None
        assert features.delta_power is not None


class TestFusionOrchestrator:
    """融合编排器测试"""

    def setup_method(self):
        import os
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-min-32chars"
        from backend.cognitive.fusion_orchestrator import FusionOrchestrator
        from backend.cognitive.schemas.cognitive_load import CognitiveLoadRequest, TaskSource
        self.orchestrator = FusionOrchestrator()
        self.CognitiveLoadRequest = CognitiveLoadRequest
        self.TaskSource = TaskSource

    def test_assess_with_all_modalities(self):
        """测试三模态融合评估"""
        request = self.CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=self.TaskSource.PATIENT_EDUCATION,
            behavior_features={
                "click_count": 5,
                "back_count": 1,
                "error_count": 0,
                "step_count": 3,
                "back_rate": 0.167,
                "error_rate": 0.0,
                "click_density": 0.5,
                "completion_rate": 1.0,
                "avg_time_per_step": 1000.0,
                "total_duration_ms": 3000
            },
            nasa_tlx_answers={
                "mental_demand": 3,
                "physical_demand": 2,
                "temporal_demand": 3,
                "performance": 5,
                "effort": 3,
                "frustration": 2
            }
        )
        result = self.orchestrator.assess(request)
        assert result.final_score is not None
        assert 0 <= result.final_score <= 1
        assert result.level in ["low", "medium", "high"]

    def test_assess_with_questionnaire_only(self):
        """测试仅问卷模态评估"""
        request = self.CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=self.TaskSource.CHAT,
            nasa_tlx_answers={
                "mental_demand": 5,
                "physical_demand": 4,
                "temporal_demand": 5,
                "performance": 3,
                "effort": 5,
                "frustration": 5
            }
        )
        result = self.orchestrator.assess(request)
        assert result.final_score is not None
        assert result.questionnaire_score is not None

    def test_assess_no_modalities(self):
        """测试无模态返回默认分数"""
        request = self.CognitiveLoadRequest(
            user_id="test_user",
            task_id="test_task",
            source=self.TaskSource.MEDICATION
        )
        result = self.orchestrator.assess(request)
        assert result.final_score == 0.5
        assert result.level == "medium"

    def test_get_level_classification(self):
        """测试负荷等级分类"""
        assert self.orchestrator._get_level(0.2) == "low"
        assert self.orchestrator._get_level(0.5) == "medium"
        assert self.orchestrator._get_level(0.8) == "high"

    def test_available_modalities(self):
        """测试可用模态检测"""
        modalities = self.orchestrator.available_modalities
        assert isinstance(modalities, list)


class TestCognitiveModes:
    """EEG模式配置测试"""

    def test_default_mode_is_simulation(self):
        """测试默认模式是模拟器"""
        import os
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-min-32chars"
        from backend.cognitive.modes import get_current_mode, EEGMode
        assert get_current_mode() == EEGMode.SIMULATION

    def test_mode_switching(self):
        """测试模式切换"""
        import os
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-min-32chars"
        from backend.cognitive.modes import set_mode, get_current_mode, EEGMode

        set_mode(EEGMode.HARDWARE)
        assert get_current_mode() == EEGMode.HARDWARE

        set_mode(EEGMode.SIMULATION)
        assert get_current_mode() == EEGMode.SIMULATION


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
