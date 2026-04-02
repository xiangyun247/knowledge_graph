#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认知负荷评估模块 - 数据模式定义
Pydantic模型用于API请求/响应验证
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class CognitiveLevel(str, Enum):
    """认知负荷等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskSource(str, Enum):
    """任务来源"""
    PATIENT_EDUCATION = "patient_education"
    CHAT = "chat"
    MEDICATION = "medication"


class EventType(str, Enum):
    """行为事件类型"""
    TASK_START = "task_start"
    TASK_END = "task_end"
    STEP_VIEW = "step_view"
    BACK = "back"
    CLICK = "click"
    ERROR_OR_REPEAT = "error_or_repeat"
    SUBMIT_QUESTIONNAIRE = "submit_questionnaire"


class BehaviorEvent(BaseModel):
    """单个行为事件"""
    event_type: EventType
    ts: int = Field(..., description="事件时间戳(毫秒)")
    params: Optional[Dict[str, Any]] = Field(default=None, description="事件参数")
    step_index: Optional[int] = Field(default=None, description="步骤索引(分步模式)")
    total_steps: Optional[int] = Field(default=None, description="总步骤数")


class BehaviorFeatures(BaseModel):
    """行为特征"""
    click_count: int = Field(default=0, description="点击次数")
    back_count: int = Field(default=0, description="回退次数")
    error_count: int = Field(default=0, description="错误次数")
    step_count: int = Field(default=0, description="步骤数")
    back_rate: float = Field(default=0.0, description="回退率")
    error_rate: float = Field(default=0.0, description="错误率")
    click_density: float = Field(default=0.0, description="点击密度(点击次数/任务时长)")
    completion_rate: float = Field(default=0.0, description="完成率")
    avg_time_per_step: float = Field(default=0.0, description="每步平均耗时(毫秒)")
    total_duration_ms: int = Field(default=0, description="总耗时(毫秒)")


class NASATLXAnswers(BaseModel):
    """NASA-TLX问卷答案"""
    mental_demand: int = Field(..., ge=1, le=7, description="脑力需求: 1-7分")
    physical_demand: int = Field(..., ge=1, le=7, description="体力需求: 1-7分")
    temporal_demand: int = Field(..., ge=1, le=7, description="时间需求: 1-7分")
    performance: int = Field(..., ge=1, le=7, description="绩效感知: 1-7分")
    effort: int = Field(..., ge=1, le=7, description="努力程度: 1-7分")
    frustration: int = Field(..., ge=1, le=7, description="挫败感: 1-7分")


class NASATLXFeatures(BaseModel):
    """NASA-TLX各维度评分(归一化)"""
    mental_demand: float = Field(default=0.0, ge=0, le=1, description="脑力需求(0-1)")
    physical_demand: float = Field(default=0.0, ge=0, le=1, description="体力需求(0-1)")
    temporal_demand: float = Field(default=0.0, ge=0, le=1, description="时间需求(0-1)")
    performance: float = Field(default=0.0, ge=0, le=1, description="绩效感知(0-1)")
    effort: float = Field(default=0.0, ge=0, le=1, description="努力程度(0-1)")
    frustration: float = Field(default=0.0, ge=0, le=1, description="挫败感(0-1)")


class EEGFeatures(BaseModel):
    """EEG特征(预留)"""
    delta_power: Optional[float] = None
    theta_power: Optional[float] = None
    alpha_power: Optional[float] = None
    beta_power: Optional[float] = None
    gamma_power: Optional[float] = None
    theta_beta_ratio: Optional[float] = None
    theta_alpha_ratio: Optional[float] = None
    alpha_beta_ratio: Optional[float] = None


class CognitiveLoadRequest(BaseModel):
    """认知负荷评估请求"""
    user_id: str = Field(..., description="用户ID")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    agent_session_id: Optional[str] = Field(default=None, description="关联的Agent会话ID")
    task_id: str = Field(..., description="任务ID")
    source: TaskSource = Field(..., description="任务来源")
    task_start_ts: Optional[int] = Field(default=None, description="任务开始时间戳")
    task_end_ts: Optional[int] = Field(default=None, description="任务结束时间戳")
    behavior_events: Optional[List[BehaviorEvent]] = Field(default=None, description="行为事件列表")
    behavior_features: Optional[BehaviorFeatures] = Field(default=None, description="行为特征")
    nasa_tlx_answers: Optional[NASATLXAnswers] = Field(default=None, description="NASA-TLX答案")
    eeg_features: Optional[EEGFeatures] = Field(default=None, description="EEG特征")


class CognitiveLoadResponse(BaseModel):
    """认知负荷评估响应"""
    assessment_id: Optional[int] = Field(default=None, description="评估记录ID")
    user_id: str
    task_id: str
    source: TaskSource

    final_score: float = Field(..., ge=0, le=1, description="综合认知负荷评分(0-1)")
    level: CognitiveLevel = Field(..., description="认知负荷等级")

    behavior_score: Optional[float] = Field(default=None, ge=0, le=1, description="行为评分")
    questionnaire_score: Optional[float] = Field(default=None, ge=0, le=1, description="问卷评分")
    eeg_score: Optional[float] = Field(default=None, ge=0, le=1, description="EEG评分")

    behavior_features: Optional[BehaviorFeatures] = None
    questionnaire_features: Optional[NASATLXFeatures] = None
    eeg_features: Optional[EEGFeatures] = None

    fusion_method: str = Field(default="weighted", description="融合方法")
    available_modalities: List[str] = Field(default_factory=list, description="可用模态列表")
    modality_weights: Optional[Dict[str, float]] = None

    created_at: Optional[str] = None


class AssessmentRecord(BaseModel):
    """评估记录(数据库模型)"""
    id: Optional[int] = None
    user_id: str
    session_id: Optional[str] = None
    task_id: str
    source: TaskSource

    task_start_ts: Optional[int] = None
    task_end_ts: Optional[int] = None
    duration_ms: Optional[int] = None

    final_score: float
    level: CognitiveLevel

    behavior_score: Optional[float] = None
    questionnaire_score: Optional[float] = None
    eeg_score: Optional[float] = None

    behavior_features: Optional[Dict[str, Any]] = None
    questionnaire_features: Optional[Dict[str, Any]] = None
    eeg_features: Optional[Dict[str, Any]] = None

    fusion_method: str = "weighted"
    available_modalities: str = ""
    modality_weights: Optional[Dict[str, float]] = None

    created_at: Optional[str] = None


class ReportSummary(BaseModel):
    """报告摘要"""
    overall_score: float
    overall_level: CognitiveLevel
    behavior_score: Optional[float] = None
    questionnaire_score: Optional[float] = None
    duration_ms: Optional[int] = None
    task_time: Optional[str] = None


class RadarChartData(BaseModel):
    """雷达图数据"""
    dimensions: List[str]
    scores: List[float]
    raw_scores: List[int]
    norm_values: List[float]


class Suggestion(BaseModel):
    """个性化建议"""
    category: str
    priority: str
    suggestion: str
    expected_impact: str
    source: str


class CognitiveReport(BaseModel):
    """认知负荷评估报告"""
    report_type: str
    user_id: str
    assessment_id: Optional[int] = None
    task_id: Optional[str] = None
    source: Optional[str] = None

    summary: Optional[ReportSummary] = None
    radar_chart: Optional[RadarChartData] = None

    key_findings: Optional[List[str]] = None
    risk_alerts: Optional[List[str]] = None
    positive_aspects: Optional[List[str]] = None
    suggestions: Optional[List[Suggestion]] = None

    benchmarks: Optional[Dict[str, Any]] = None
    trend_summary: Optional[Dict[str, Any]] = None

    generated_at: Optional[str] = None


class TrendReportRequest(BaseModel):
    """趋势报告请求"""
    user_id: str
    days: int = Field(default=7, ge=3, le=90)
    source: Optional[TaskSource] = None
    include_ai: bool = Field(default=False)


class PeriodReportRequest(BaseModel):
    """周期报告请求"""
    user_id: str
    start_date: str
    end_date: str
    include_ai: bool = Field(default=False)
