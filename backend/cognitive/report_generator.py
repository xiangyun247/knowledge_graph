#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评估报告生成器
生成结构化认知负荷评估报告

报告类型：
- single: 单次评估报告
- task: 任务分析报告
- trend: 趋势分析报告
- period: 周期汇总报告
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from .schemas.cognitive_load import (
    CognitiveLevel,
    ReportSummary,
    RadarChartData,
    Suggestion,
    CognitiveReport,
)
from .repository import get_cognitive_repository
from .modalities import NASATLXScorer, BehaviorScorer


class ReportType(Enum):
    """报告类型枚举"""
    SINGLE = "single"
    TASK = "task"
    TREND = "trend"
    PERIOD = "period"


@dataclass
class ReportConfig:
    """报告生成配置"""
    report_type: ReportType
    user_id: str
    assessment_id: Optional[int] = None
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    period_days: int = 7
    source: Optional[str] = None
    include_ai: bool = False


class CognitiveReportGenerator:
    """
    认知负荷评估报告生成器

    职责：
    1. 根据报告类型聚合数据
    2. 计算评分、趋势、对比基准
    3. 生成结构化报告
    4. 可选：调用LLM生成个性化建议
    """

    DIMENSION_LABELS = {
        "mental_demand": "脑力需求",
        "physical_demand": "体力需求",
        "temporal_demand": "时间需求",
        "performance": "绩效感知",
        "effort": "努力程度",
        "frustration": "挫败感"
    }

    ELDERLY_NORM_VALUES = {
        "mental_demand": 0.60,
        "physical_demand": 0.18,
        "temporal_demand": 0.32,
        "performance": 0.50,
        "effort": 0.70,
        "frustration": 0.30
    }

    def __init__(self):
        self.repository = get_cognitive_repository()
        self.nasa_scorer = NASATLXScorer()
        self.behavior_scorer = BehaviorScorer()

    async def generate(self, config: ReportConfig) -> Dict:
        """
        生成评估报告

        Args:
            config: 报告配置

        Returns:
            结构化报告字典
        """
        if config.report_type == ReportType.SINGLE:
            return await self._generate_single_report(config)
        elif config.report_type == ReportType.TASK:
            return await self._generate_task_report(config)
        elif config.report_type == ReportType.TREND:
            return await self._generate_trend_report(config)
        elif config.report_type == ReportType.PERIOD:
            return await self._generate_period_report(config)
        else:
            raise ValueError(f"不支持的报告类型: {config.report_type}")

    async def _generate_single_report(self, config: ReportConfig) -> Dict:
        """
        生成单次评估报告
        """
        assessment = self.repository.get_assessment(config.assessment_id)
        if not assessment:
            return {"error": f"评估记录不存在: {config.assessment_id}"}

        nasa_answers = self.repository.get_nasa_tlx_answers(config.assessment_id)

        radar_data = self._compute_radar_chart(nasa_answers)
        key_findings = self._extract_key_findings(assessment, nasa_answers)
        suggestions = self._generate_suggestions(assessment, nasa_answers)
        risk_alerts = self._generate_risk_alerts(assessment, nasa_answers)
        positive_aspects = self._extract_positive_aspects(assessment, nasa_answers)
        benchmarks = self._compute_benchmarks(config.user_id, assessment)

        final_score = float(assessment.get("final_score", 0.5))
        duration_ms = assessment.get("duration_ms")

        report = {
            "report_type": "single",
            "user_id": config.user_id,
            "assessment_id": config.assessment_id,
            "task_id": assessment.get("task_id"),
            "source": assessment.get("source"),

            "summary": {
                "overall_score": final_score,
                "overall_level": assessment.get("level", "medium"),
                "behavior_score": float(assessment.get("behavior_score", 0)) if assessment.get("behavior_score") else None,
                "questionnaire_score": float(assessment.get("questionnaire_score", 0)) if assessment.get("questionnaire_score") else None,
                "duration_ms": duration_ms,
                "task_time": self._format_duration(duration_ms) if duration_ms else None
            },

            "radar_chart": radar_data,
            "key_findings": key_findings,
            "risk_alerts": risk_alerts,
            "positive_aspects": positive_aspects,
            "suggestions": suggestions,
            "benchmarks": benchmarks,

            "generated_at": datetime.now().isoformat()
        }

        return report

    async def _generate_task_report(self, config: ReportConfig) -> Dict:
        """生成任务分析报告"""
        assessments = self.repository.get_user_assessments(
            user_id=config.user_id,
            source=config.source,
            limit=100
        )

        task_assessments = [a for a in assessments if a.get("task_id") == config.task_id]

        if not task_assessments:
            return {"error": f"未找到任务记录: {config.task_id}"}

        avg_score = sum(float(a.get("final_score", 0.5)) for a in task_assessments) / len(task_assessments)

        report = {
            "report_type": "task",
            "user_id": config.user_id,
            "task_id": config.task_id,
            "assessment_count": len(task_assessments),

            "summary": {
                "overall_score": round(avg_score, 4),
                "overall_level": self._get_level(avg_score),
                "avg_behavior_score": sum(float(a.get("behavior_score", 0)) for a in task_assessments) / len(task_assessments),
                "avg_questionnaire_score": sum(float(a.get("questionnaire_score", 0)) for a in task_assessments) / len(task_assessments)
            },

            "generated_at": datetime.now().isoformat()
        }

        return report

    async def _generate_trend_report(self, config: ReportConfig) -> Dict:
        """生成趋势分析报告"""
        assessments = self.repository.get_user_assessments(
            user_id=config.user_id,
            source=config.source,
            days=config.period_days
        )

        if len(assessments) < 2:
            return {
                "error": "数据不足，无法生成趋势报告",
                "required": "至少需要2次评估",
                "current_count": len(assessments)
            }

        trend_data = self.repository.get_trend_analysis(
            user_id=config.user_id,
            days=config.period_days,
            source=config.source
        )

        dates = trend_data.get("dates", [])
        scores = trend_data.get("scores", [])

        timeline = {
            "dates": dates,
            "scores": scores,
            "levels": trend_data.get("levels", [])
        }

        trend_summary = trend_data.get("summary", {})
        trend_direction = trend_summary.get("trend", "stable")
        change_rate = self._compute_change_rate(scores)

        peak_times = self._analyze_peak_times(assessments)

        report = {
            "report_type": "trend",
            "user_id": config.user_id,
            "period_days": config.period_days,
            "assessment_count": len(assessments),

            "timeline": timeline,
            "nasa_tlx_trends": trend_data.get("nasa_tlx_trends", {}),

            "trend_summary": {
                "trend_direction": trend_direction,
                "change_rate": change_rate,
                "avg_score": trend_summary.get("avg_score", 0),
                "min_score": trend_summary.get("min_score", 0),
                "max_score": trend_summary.get("max_score", 0),
                "peak_times": peak_times
            },

            "risk_alerts": self._generate_trend_risk_alerts(trend_summary),
            "suggestions": self._generate_trend_suggestions(trend_summary, trend_direction),

            "generated_at": datetime.now().isoformat()
        }

        return report

    async def _generate_period_report(self, config: ReportConfig) -> Dict:
        """生成周期汇总报告"""
        assessments = self.repository.get_user_assessments(
            user_id=config.user_id,
            days=config.period_days,
            limit=1000
        )

        if not assessments:
            return {"error": "周期内无评估数据"}

        final_scores = [float(a.get("final_score", 0.5)) for a in assessments]
        avg_score = sum(final_scores) / len(final_scores)

        level_counts = {}
        for a in assessments:
            level = a.get("level", "medium")
            level_counts[level] = level_counts.get(level, 0) + 1

        report = {
            "report_type": "period",
            "user_id": config.user_id,
            "period_days": config.period_days,
            "assessment_count": len(assessments),

            "summary": {
                "overall_score": round(avg_score, 4),
                "overall_level": self._get_level(avg_score),
                "level_distribution": level_counts
            },

            "generated_at": datetime.now().isoformat()
        }

        return report

    def _compute_radar_chart(self, nasa_answers: Optional[Dict]) -> Dict:
        """计算NASA-TLX雷达图数据"""
        dimensions = list(self.DIMENSION_LABELS.values())
        raw_scores = []
        scores = []
        norm_values = []

        for dim_key in self.DIMENSION_LABELS.keys():
            if nasa_answers and dim_key in nasa_answers:
                raw_val = nasa_answers[dim_key]
            else:
                raw_val = 4
            raw_scores.append(raw_val)
            normalized = (raw_val - 1) / 6.0
            scores.append(round(normalized, 3))
            norm_values.append(self.ELDERLY_NORM_VALUES.get(dim_key, 0.5))

        return {
            "dimensions": dimensions,
            "scores": scores,
            "raw_scores": raw_scores,
            "norm_values": norm_values
        }

    def _extract_key_findings(self, assessment: Dict, nasa_answers: Optional[Dict]) -> List[str]:
        """提取关键发现"""
        findings = []

        behavior_features = assessment.get("behavior_features", {})
        if behavior_features:
            back_rate = behavior_features.get("back_rate", 0)
            if back_rate > 0.2:
                findings.append(f"回退率为{back_rate*100:.0f}%，高于正常水平，可能遇到理解困难")
            elif back_rate > 0.1:
                findings.append(f"回退率为{back_rate*100:.0f}%，处于正常范围")

            error_rate = behavior_features.get("error_rate", 0)
            if error_rate > 0.1:
                findings.append(f"错误操作率为{error_rate*100:.0f}%，建议简化操作流程")

        if nasa_answers:
            max_dim = max(nasa_answers.keys(), key=lambda k: nasa_answers.get(k, 0))
            max_val = nasa_answers.get(max_dim, 0)
            if max_val >= 5:
                dim_name = self.DIMENSION_LABELS.get(max_dim, max_dim)
                findings.append(f"NASA-TLX中{dim_name}维度得分最高({max_val}/7)，是主要负荷来源")

        duration_ms = assessment.get("duration_ms", 0)
        duration_sec = duration_ms / 1000
        if duration_sec > 180:
            findings.append(f"任务完成耗时{duration_sec/60:.1f}分钟较长，可能内容偏多或难度偏高")
        elif duration_sec < 15 and duration_sec > 0:
            findings.append(f"任务完成较快({duration_sec:.0f}秒)，内容相对简单")

        return findings

    def _generate_risk_alerts(self, assessment: Dict, nasa_answers: Optional[Dict]) -> List[str]:
        """生成风险预警"""
        alerts = []

        final_score = float(assessment.get("final_score", 0))
        if final_score > 0.7:
            alerts.append("⚠️ 高认知负荷预警：当前任务对用户造成较高认知负荷")

        if nasa_answers:
            frustration = nasa_answers.get("frustration", 0)
            if frustration >= 5:
                alerts.append("⚠️ 高挫败感预警：用户在任务中感到明显烦躁")

        behavior = assessment.get("behavior_features", {})
        if behavior.get("back_rate", 0) > 0.3:
            alerts.append("⚠️ 操作困难预警：频繁回退表明内容可能较难理解")

        if behavior.get("error_rate", 0) > 0.15:
            alerts.append("⚠️ 错误率高预警：操作错误频繁，需检查界面设计")

        if assessment.get("duration_ms", 0) > 300000:
            alerts.append("⚠️ 内容过载预警：任务时间过长，建议拆分内容")

        return alerts

    def _extract_positive_aspects(self, assessment: Dict, nasa_answers: Optional[Dict]) -> List[str]:
        """提取积极方面"""
        aspects = []

        final_score = float(assessment.get("final_score", 1))
        if final_score < 0.4:
            aspects.append("✅ 认知负荷处于低水平，任务对用户友好")

        behavior = assessment.get("behavior_features", {})
        if behavior.get("completion_rate", 0) >= 0.9:
            aspects.append("✅ 任务完成率高，操作流畅")

        if behavior.get("error_rate", 1) < 0.05:
            aspects.append("✅ 操作错误少，界面易于理解")

        if nasa_answers:
            performance = nasa_answers.get("performance", 0)
            if performance >= 5:
                aspects.append("✅ 用户对自身表现满意")

            frustration = nasa_answers.get("frustration", 0)
            if frustration <= 2:
                aspects.append("✅ 任务过程顺利，用户无明显挫败感")

        return aspects

    def _generate_suggestions(self, assessment: Dict, nasa_answers: Optional[Dict]) -> List[Dict]:
        """生成个性化建议"""
        suggestions = []

        if nasa_answers:
            mental = nasa_answers.get("mental_demand", 0)
            if mental >= 5:
                suggestions.append({
                    "category": "内容优化",
                    "priority": "high",
                    "suggestion": "建议将长段落内容拆分为更小的步骤，每步聚焦一个要点",
                    "expected_impact": "可降低20-30%脑力负荷",
                    "source": "NASA-TLX脑力需求维度分析"
                })

            frustration = nasa_answers.get("frustration", 0)
            if frustration >= 4:
                suggestions.append({
                    "category": "用户体验",
                    "priority": "high",
                    "suggestion": "增加进度指示器，让用户知道当前进度和剩余时间",
                    "expected_impact": "可降低焦虑感和挫败感",
                    "source": "NASA-TLX挫败感维度分析"
                })

        behavior = assessment.get("behavior_features", {})
        if behavior.get("back_rate", 0) > 0.2:
            suggestions.append({
                "category": "导航优化",
                "priority": "medium",
                "suggestion": "增加'上一步'确认提示，减少用户回退需求",
                "expected_impact": "可减少30-40%回退操作",
                "source": "回退率行为分析"
            })

        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda x: priority_order.get(x["priority"], 2))

        return suggestions[:5]

    def _compute_benchmarks(self, user_id: str, assessment: Dict) -> Dict:
        """计算对比基准"""
        historical = self.repository.get_user_historical_stats(user_id)

        current_score = float(assessment.get("final_score", 0.5))
        avg_score = historical.get("avg_score", 0.5)

        percentile = 50
        if historical.get("count", 0) > 0 and avg_score > 0:
            percentile = min(100, max(0, int((1 - (current_score - avg_score)) * 50 + 50)))

        return {
            "user_historical_avg": historical.get("avg_score", 0.5),
            "user_historical_best": historical.get("min_score", 0),
            "user_historical_worst": historical.get("max_score", 1),
            "elderly_norm": 0.55,
            "percentile": percentile
        }

    def _generate_trend_risk_alerts(self, trend_summary: Dict) -> List[str]:
        """生成趋势风险预警"""
        alerts = []

        trend = trend_summary.get("trend", "stable")
        if trend == "increasing":
            alerts.append("⚠️ 认知负荷呈上升趋势，需关注用户状态变化")

        avg_score = trend_summary.get("avg_score", 0)
        if avg_score > 0.7:
            alerts.append("⚠️ 整体认知负荷偏高，建议优化任务设计")

        return alerts

    def _generate_trend_suggestions(self, trend_summary: Dict, trend_direction: str) -> List[Dict]:
        """生成趋势建议"""
        suggestions = []

        if trend_direction == "increasing":
            suggestions.append({
                "category": "干预建议",
                "priority": "high",
                "suggestion": "认知负荷呈上升趋势，建议增加休息间隔或拆分任务",
                "expected_impact": "可稳定或降低认知负荷水平",
                "source": "趋势分析"
            })

        peak_times = trend_summary.get("peak_times", [])
        if peak_times:
            suggestions.append({
                "category": "时间安排",
                "priority": "medium",
                "suggestion": f"高峰期({', '.join(peak_times)})避免安排复杂任务",
                "expected_impact": "可减少高峰时段的认知压力",
                "source": "时段分析"
            })

        return suggestions

    def _analyze_peak_times(self, assessments: List[Dict]) -> List[str]:
        """分析高峰时段"""
        hour_counts = {}
        for a in assessments:
            created_at = a.get("created_at", "")
            if created_at:
                try:
                    hour = datetime.fromisoformat(created_at.replace("Z", "+00:00")).hour
                    if 6 <= hour <= 22:
                        period = f"{hour}:00-{hour+1}:00"
                        hour_counts[period] = hour_counts.get(period, 0) + 1
                except:
                    pass

        if not hour_counts:
            return []

        sorted_periods = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
        return [p[0] for p in sorted_periods[:2] if p[1] >= 2]

    def _compute_change_rate(self, scores: List[float]) -> float:
        """计算变化率"""
        if len(scores) < 2:
            return 0.0

        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        if avg_first == 0:
            return 0.0

        return round((avg_second - avg_first) / avg_first, 3)

    def _get_level(self, score: float) -> str:
        """获取负荷等级"""
        if score < 0.4:
            return "low"
        elif score < 0.7:
            return "medium"
        else:
            return "high"

    def _format_duration(self, duration_ms: int) -> str:
        """格式化时长"""
        if duration_ms < 60000:
            return f"{duration_ms/1000:.0f}秒"
        else:
            return f"{duration_ms/60000:.1f}分钟"


def get_report_generator() -> CognitiveReportGenerator:
    """获取报告生成器实例"""
    return CognitiveReportGenerator()
