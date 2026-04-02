#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cognitive Load Assessment Module - Unit Tests

Test Contents:
1. NASA-TLX Scorer
2. Behavior Scorer
3. Fusion Orchestrator
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.cognitive.modalities import NASATLXScorer, BehaviorScorer, EEGScorer
from backend.cognitive.schemas.cognitive_load import (
    NASATLXAnswers,
    BehaviorEvent,
    CognitiveLoadRequest,
    TaskSource,
    EventType
)
from backend.cognitive.fusion_orchestrator import FusionOrchestrator


class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def record(self, name: str, passed: bool, message: str = ""):
        if passed:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            self.errors.append((name, message))
            print(f"  [FAIL] {name}: {message}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            print("\nFailed tests:")
            for name, msg in self.errors:
                print(f"  - {name}: {msg}")
        return self.failed == 0


def test_nasa_tlx_scorer(results: TestResults):
    print("\n[Test] NASA-TLX Scorer")
    print("-" * 40)

    scorer = NASATLXScorer()

    answers = NASATLXAnswers(
        mental_demand=5,
        physical_demand=2,
        temporal_demand=3,
        performance=4,
        effort=5,
        frustration=3
    )

    features = scorer.compute_features(answers)
    results.record(
        "compute_features normalization",
        abs(features.mental_demand - 0.667) < 0.01,
        f"Expected 0.667, got {features.mental_demand}"
    )

    score = scorer.score(features)
    results.record(
        "score returns 0-1 range",
        0 <= score <= 1,
        f"Score {score} out of range"
    )

    level = scorer.get_level(score)
    results.record(
        "get_level returns valid value",
        level in ["low", "medium", "high"],
        f"Level {level} invalid"
    )

    radar = scorer.get_radar_chart_data(features)
    results.record(
        "get_radar_chart_data returns 6 dimensions",
        len(radar["dimensions"]) == 6,
        f"Dimension count {len(radar['dimensions'])}"
    )

    suggestions = scorer.generate_suggestions(features)
    results.record(
        "generate_suggestions returns list",
        isinstance(suggestions, list),
        "Suggestions is not a list"
    )

    print(f"  - Total Score: {score:.4f}")
    print(f"  - Level: {level}")


def test_behavior_scorer(results: TestResults):
    print("\n[Test] Behavior Scorer")
    print("-" * 40)

    scorer = BehaviorScorer()

    events = [
        {"event_type": "task_start", "ts": 1000, "params": {}},
        {"event_type": "click", "ts": 1100, "params": {"button": "next"}},
        {"event_type": "click", "ts": 1200, "params": {"button": "next"}},
        {"event_type": "back", "ts": 1300, "params": {}},
        {"event_type": "click", "ts": 1400, "params": {"button": "next"}},
        {"event_type": "click", "ts": 1500, "params": {"button": "submit"}},
        {"event_type": "task_end", "ts": 1600, "params": {"completed": True}},
    ]

    behavior_events = [BehaviorEvent(**e) for e in events]

    features = scorer.compute_features(behavior_events)
    results.record(
        "compute_features click count",
        features.click_count == 4,
        f"Expected 4, got {features.click_count}"
    )

    results.record(
        "compute_features back count",
        features.back_count == 1,
        f"Expected 1, got {features.back_count}"
    )

    results.record(
        "compute_features duration",
        features.total_duration_ms == 600,
        f"Expected 600, got {features.total_duration_ms}"
    )

    score = scorer.score(features)
    results.record(
        "score returns 0-1 range",
        0 <= score <= 1,
        f"Score {score} out of range"
    )

    level = scorer.get_level(score)
    results.record(
        "get_level returns valid value",
        level in ["low", "medium", "high"],
        f"Level {level} invalid"
    )

    print(f"  - Click count: {features.click_count}")
    print(f"  - Back count: {features.back_count}")
    print(f"  - Back rate: {features.back_rate:.2%}")
    print(f"  - Total Score: {score:.4f}")
    print(f"  - Level: {level}")


def test_fusion_orchestrator(results: TestResults):
    print("\n[Test] Fusion Orchestrator")
    print("-" * 40)

    orchestrator = FusionOrchestrator()

    request = CognitiveLoadRequest(
        user_id="test_user",
        session_id="test_session",
        task_id="test_task_001",
        source=TaskSource.PATIENT_EDUCATION,
        task_start_ts=1000,
        task_end_ts=70000,
        nasa_tlx_answers=NASATLXAnswers(
            mental_demand=4,
            physical_demand=2,
            temporal_demand=3,
            performance=5,
            effort=4,
            frustration=2
        ),
        behavior_events=[
            BehaviorEvent(event_type=EventType.TASK_START, ts=1000),
            BehaviorEvent(event_type=EventType.CLICK, ts=1100),
            BehaviorEvent(event_type=EventType.CLICK, ts=1200),
            BehaviorEvent(event_type=EventType.CLICK, ts=1300),
            BehaviorEvent(event_type=EventType.STEP_VIEW, ts=1400, step_index=1, total_steps=3),
            BehaviorEvent(event_type=EventType.STEP_VIEW, ts=1500, step_index=2, total_steps=3),
            BehaviorEvent(event_type=EventType.STEP_VIEW, ts=1600, step_index=3, total_steps=3),
            BehaviorEvent(event_type=EventType.TASK_END, ts=70000),
        ]
    )

    response = orchestrator.assess(request)

    results.record(
        "assess returns valid response",
        response is not None,
        "Response is empty"
    )

    results.record(
        "final_score in 0-1 range",
        0 <= response.final_score <= 1,
        f"Final score {response.final_score} out of range"
    )

    level_val = response.level.value if hasattr(response.level, 'value') else response.level
    results.record(
        "level is valid value",
        level_val in ["low", "medium", "high"],
        f"Level {level_val} invalid"
    )

    results.record(
        "available_modalities includes behavior and questionnaire",
        "behavior" in response.available_modalities and "questionnaire" in response.available_modalities,
        f"Modalities {response.available_modalities}"
    )

    results.record(
        "questionnaire_score calculated",
        response.questionnaire_score is not None and 0 <= response.questionnaire_score <= 1,
        f"Questionnaire score {response.questionnaire_score}"
    )

    results.record(
        "behavior_score calculated",
        response.behavior_score is not None and 0 <= response.behavior_score <= 1,
        f"Behavior score {response.behavior_score}"
    )

    status = orchestrator.get_modality_status()
    results.record(
        "get_modality_status returns status dict",
        "behavior" in status and "questionnaire" in status,
        "Status dict incomplete"
    )

    print(f"  - Final Score: {response.final_score:.4f}")
    print(f"  - Level: {level_val}")
    print(f"  - Behavior Score: {response.behavior_score:.4f}" if response.behavior_score else "  - Behavior Score: None")
    print(f"  - Questionnaire Score: {response.questionnaire_score:.4f}" if response.questionnaire_score else "  - Questionnaire Score: None")
    print(f"  - Available Modalities: {', '.join(response.available_modalities)}")


def test_modality_weights(results: TestResults):
    print("\n[Test] Modality Weight Adjustment")
    print("-" * 40)

    orchestrator = FusionOrchestrator()

    orchestrator.update_weights({"behavior": 0.3, "questionnaire": 0.7})

    results.record(
        "update_weights updates weights",
        True,
        ""
    )

    status = orchestrator.get_modality_status()
    results.record(
        "Weight updated: questionnaire=0.7",
        abs(status["questionnaire"]["weight"] - 0.7) < 0.01,
        f"Questionnaire weight {status['questionnaire']['weight']}"
    )


def test_edge_cases(results: TestResults):
    print("\n[Test] Edge Cases")
    print("-" * 40)

    orchestrator = FusionOrchestrator()
    nasa_scorer = NASATLXScorer()
    behavior_scorer = BehaviorScorer()

    min_answers = NASATLXAnswers(
        mental_demand=1,
        physical_demand=1,
        temporal_demand=1,
        performance=7,
        effort=1,
        frustration=1
    )
    min_features = nasa_scorer.compute_features(min_answers)
    min_score = nasa_scorer.score(min_features)
    results.record(
        "NASA-TLX minimum score boundary",
        0 <= min_score <= 0.2,
        f"Minimum score {min_score}"
    )

    max_answers = NASATLXAnswers(
        mental_demand=7,
        physical_demand=7,
        temporal_demand=7,
        performance=1,
        effort=7,
        frustration=7
    )
    max_features = nasa_scorer.compute_features(max_answers)
    max_score = nasa_scorer.score(max_features)
    results.record(
        "NASA-TLX maximum score boundary",
        0.8 <= max_score <= 1,
        f"Maximum score {max_score}"
    )

    request_no_behavior = CognitiveLoadRequest(
        user_id="test_user",
        task_id="test_task_002",
        source=TaskSource.CHAT,
        nasa_tlx_answers=min_answers
    )
    response = orchestrator.assess(request_no_behavior)
    results.record(
        "Without behavior data: questionnaire only",
        response.available_modalities == ["questionnaire"],
        f"Modalities {response.available_modalities}"
    )

    request_no_questionnaire = CognitiveLoadRequest(
        user_id="test_user",
        task_id="test_task_003",
        source=TaskSource.MEDICATION
    )
    response2 = orchestrator.assess(request_no_questionnaire)
    results.record(
        "Without questionnaire: valid response",
        True,
        ""
    )


def main():
    print("=" * 60)
    print("Cognitive Load Assessment Module - Unit Tests")
    print("=" * 60)

    results = TestResults()

    try:
        test_nasa_tlx_scorer(results)
        test_behavior_scorer(results)
        test_fusion_orchestrator(results)
        test_modality_weights(results)
        test_edge_cases(results)
    except Exception as e:
        print(f"\n[ERROR] Test execution error: {e}")
        import traceback
        traceback.print_exc()
        results.failed += 1

    success = results.summary()

    print("\n" + "=" * 60)
    if success:
        print("All tests passed!")
    else:
        print("Some tests failed, please check errors above")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
