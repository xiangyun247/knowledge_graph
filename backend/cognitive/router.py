#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认知负荷评估 API 路由
提供认知负荷评估的RESTful API接口
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import get_current_user_id as get_auth_user_id
from .schemas.cognitive_load import (
    CognitiveLoadRequest,
    CognitiveLoadResponse,
    TrendReportRequest,
    PeriodReportRequest,
)
from .fusion_orchestrator import FusionOrchestrator
from .report_generator import CognitiveReportGenerator, ReportType, ReportConfig
from .repository import get_cognitive_repository

router = APIRouter(prefix="/api/cognitive-load", tags=["认知负荷评估"])


def get_current_user_id(request: Request) -> str:
    """获取当前用户ID（对接认证系统）"""
    return get_auth_user_id(request)


def get_orchestrator() -> FusionOrchestrator:
    """获取融合调度器实例"""
    return FusionOrchestrator()


def get_repository():
    """获取仓储实例"""
    return get_cognitive_repository()


@router.post("/assess", response_model=CognitiveLoadResponse)
async def assess_cognitive_load(
    request: Request,
    cognitive_request: CognitiveLoadRequest,
    save: bool = Query(True, description="是否保存评估记录")
) -> CognitiveLoadResponse:
    """
    多模态认知负荷评估

    当前支持：行为 + 问卷
    预留接口：EEG（设备就绪后自动启用）

    Args:
        request: FastAPI请求对象（用于获取用户认证信息）
        cognitive_request: 评估请求数据
        save: 是否保存评估记录

    Returns:
        CognitiveLoadResponse: 评估响应
    """
    user_id = get_current_user_id(request)
    orchestrator = get_orchestrator()
    response = orchestrator.assess(cognitive_request)

    if save:
        try:
            repository = get_repository()
            assessment_data = {
                "user_id": user_id,
                "session_id": cognitive_request.session_id,
                "task_id": cognitive_request.task_id,
                "source": cognitive_request.source.value if hasattr(cognitive_request.source, 'value') else cognitive_request.source,
                "task_start_ts": cognitive_request.task_start_ts,
                "task_end_ts": cognitive_request.task_end_ts,
                "duration_ms": cognitive_request.task_end_ts - cognitive_request.task_start_ts if cognitive_request.task_start_ts and cognitive_request.task_end_ts else None,
                "final_score": response.final_score,
                "level": response.level.value if hasattr(response.level, 'value') else response.level,
                "behavior_score": response.behavior_score,
                "questionnaire_score": response.questionnaire_score,
                "eeg_score": response.eeg_score,
                "behavior_features": response.behavior_features.model_dump() if response.behavior_features else None,
                "questionnaire_features": response.questionnaire_features.model_dump() if response.questionnaire_features else None,
                "eeg_features": response.eeg_features.model_dump() if response.eeg_features else None,
                "fusion_method": response.fusion_method,
                "available_modalities": response.available_modalities,
                "modality_weights": response.modality_weights,
            }

            if cognitive_request.behavior_events:
                assessment_data["behavior_events"] = [
                    e.model_dump() if hasattr(e, 'model_dump') else e
                    for e in cognitive_request.behavior_events
                ]

            if cognitive_request.nasa_tlx_answers:
                assessment_data["nasa_tlx_answers"] = cognitive_request.nasa_tlx_answers.model_dump() if hasattr(cognitive_request.nasa_tlx_answers, 'model_dump') else cognitive_request.nasa_tlx_answers

            assessment_id = repository.save_assessment(assessment_data)
            response.assessment_id = assessment_id

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"保存评估记录失败: {str(e)}")

    return response


@router.get("/modalities")
async def get_available_modalities():
    """
    查询当前可用的评估模态

    Returns:
        各模态可用性和权重配置
    """
    orchestrator = get_orchestrator()
    return orchestrator.get_modality_status()


@router.get("/assessment/{assessment_id}")
async def get_assessment(assessment_id: int):
    """
    获取单条评估记录

    Args:
        assessment_id: 评估记录ID

    Returns:
        评估记录详情
    """
    repository = get_repository()
    assessment = repository.get_assessment(assessment_id)

    if not assessment:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    return assessment


@router.get("/history")
async def get_assessment_history(
    request: Request,
    user_id: Optional[str] = None,
    source: Optional[str] = None,
    days: Optional[int] = Query(None, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    获取用户评估历史

    Args:
        user_id: 用户ID
        source: 任务来源筛选
        days: 最近天数筛选
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        评估记录列表
    """
    if not user_id:
        user_id = get_current_user_id(request)

    repository = get_repository()
    assessments = repository.get_user_assessments(
        user_id=user_id,
        source=source,
        days=days,
        limit=limit,
        offset=offset
    )

    return {
        "total": len(assessments),
        "assessments": assessments
    }


@router.get("/report/single/{assessment_id}")
async def get_single_report(
    request: Request,
    assessment_id: int,
    include_ai: bool = Query(False, description="是否包含AI增强建议")
):
    """
    获取单次评估报告

    Args:
        assessment_id: 评估记录ID
        include_ai: 是否包含AI增强建议

    Returns:
        结构化评估报告
    """
    user_id = get_current_user_id(request)
    config = ReportConfig(
        report_type=ReportType.SINGLE,
        user_id=user_id,
        assessment_id=assessment_id,
        include_ai=include_ai
    )

    generator = CognitiveReportGenerator()
    report = await generator.generate(config)

    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])

    return report


@router.get("/report/trend")
async def get_trend_report(
    request: Request,
    user_id: Optional[str] = None,
    days: int = Query(7, ge=3, le=90, description="统计天数"),
    source: Optional[str] = None,
    include_ai: bool = Query(False)
):
    """
    获取认知负荷趋势报告

    Args:
        user_id: 用户ID
        days: 统计天数(3-90)
        source: 任务来源筛选
        include_ai: 是否包含AI增强建议

    Returns:
        趋势分析报告
    """
    if not user_id:
        user_id = get_current_user_id(request)

    config = ReportConfig(
        report_type=ReportType.TREND,
        user_id=user_id,
        period_days=days,
        source=source,
        include_ai=include_ai
    )

    generator = CognitiveReportGenerator()
    report = await generator.generate(config)

    if "error" in report:
        raise HTTPException(status_code=400, detail=report)

    return report


@router.get("/report/period")
async def get_period_report(
    request: Request,
    user_id: Optional[str] = None,
    days: int = Query(30, ge=7, le=365),
    include_ai: bool = Query(False)
):
    """
    获取周期汇总报告

    Args:
        user_id: 用户ID
        days: 周期天数
        include_ai: 是否包含AI增强建议

    Returns:
        周期汇总报告
    """
    if not user_id:
        user_id = get_current_user_id(request)

    config = ReportConfig(
        report_type=ReportType.PERIOD,
        user_id=user_id,
        period_days=days,
        include_ai=include_ai
    )

    generator = CognitiveReportGenerator()
    report = await generator.generate(config)

    if "error" in report:
        raise HTTPException(status_code=400, detail=report)

    return report


@router.get("/trend/analysis")
async def get_trend_analysis(
    request: Request,
    user_id: Optional[str] = None,
    days: int = Query(7, ge=3, le=90),
    source: Optional[str] = None
):
    """
    获取认知负荷趋势数据

    Args:
        user_id: 用户ID
        days: 统计天数
        source: 任务来源筛选

    Returns:
        趋势分析数据
    """
    if not user_id:
        user_id = get_current_user_id(request)

    repository = get_repository()
    return repository.get_trend_analysis(user_id, days, source)


@router.get("/stats/user")
async def get_user_stats(
    request: Request,
    user_id: Optional[str] = None
):
    """
    获取用户认知负荷统计

    Args:
        user_id: 用户ID

    Returns:
        用户统计信息
    """
    if not user_id:
        user_id = get_current_user_id(request)

    repository = get_repository()
    return repository.get_user_stats(user_id)


@router.get("/export")
async def export_cognitive_history(
    request: Request,
    format: str = Query("csv", enum=["csv", "json"]),
    days: int = Query(30, ge=1, le=365, description="导出最近N天的数据"),
    source: Optional[str] = Query(None, description="按来源筛选")
):
    """
    导出用户认知评估历史数据

    Args:
        format: 导出格式 (csv/json)
        days: 导出天数 (1-365)
        source: 来源筛选

    Returns:
        CSV或JSON格式的历史数据
    """
    user_id = get_current_user_id(request)
    repository = get_repository()

    history = repository.get_user_assessments(user_id, source, days, 1000)

    if format == "csv":
        import csv
        from io import StringIO
        from fastapi.responses import Response

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "id", "task_id", "source", "final_score", "level",
            "behavior_score", "questionnaire_score", "eeg_score",
            "duration_ms", "created_at"
        ])
        writer.writeheader()
        for item in history:
            writer.writerow({
                "id": item.get("id"),
                "task_id": item.get("task_id"),
                "source": item.get("source"),
                "final_score": item.get("final_score"),
                "level": item.get("level"),
                "behavior_score": item.get("behavior_score"),
                "questionnaire_score": item.get("questionnaire_score"),
                "eeg_score": item.get("eeg_score"),
                "duration_ms": item.get("duration_ms"),
                "created_at": item.get("created_at")
            })

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=cognitive_history_{user_id}_{days}d.csv"
            }
        )
    else:
        return {"data": history, "count": len(history), "format": "json"}


@router.get("/eeg/status")
async def get_eeg_status():
    """
    获取EEG设备/模拟器状态

    Returns:
        EEG设备状态信息
    """
    from .modalities.eeg_scorer import EEGScorer_instance
    return EEGScorer_instance.get_status()


@router.post("/eeg/simulate/enable")
async def enable_eeg_simulation(
    cognitive_level: str = Query("medium", enum=["low", "medium", "high"], description="模拟的认知负荷等级"),
    signal_quality: str = Query("good", enum=["excellent", "good", "fair", "poor"], description="信号质量")
):
    """
    启用EEG模拟器模式（用于开发测试）

    Args:
        cognitive_level: 模拟的认知负荷等级
        signal_quality: 模拟的信号质量

    Returns:
        启用结果
    """
    from .modalities.eeg_scorer import EEGScorer_instance

    EEGScorer_instance.enable_simulation()
    EEGScorer_instance.set_cognitive_level(cognitive_level)
    EEGScorer_instance.set_signal_quality(signal_quality)

    return {
        "success": True,
        "message": "EEG模拟器已启用",
        "status": EEGScorer_instance.get_status()
    }


@router.post("/eeg/simulate/disable")
async def disable_eeg_simulation():
    """
    禁用EEG模拟器模式

    Returns:
        禁用结果
    """
    from .modalities.eeg_scorer import EEGScorer_instance

    EEGScorer_instance.disable_simulation()

    return {
        "success": True,
        "message": "EEG模拟器已禁用",
        "status": EEGScorer_instance.get_status()
    }


@router.post("/eeg/simulate/features")
async def generate_eeg_features(
    cognitive_level: str = Query("medium", enum=["low", "medium", "high"], description="认知负荷等级")
):
    """
    生成模拟EEG特征（用于测试）

    Args:
        cognitive_level: 认知负荷等级

    Returns:
        模拟的EEG特征数据
    """
    from .modalities.eeg_scorer import EEGScorer_instance

    if not EEGScorer_instance.is_simulation_mode():
        raise HTTPException(
            status_code=400,
            detail="模拟器模式未启用，请先调用 /eeg/simulate/enable"
        )

    features = EEGScorer_instance.generate_simulated_features(cognitive_level)
    score = EEGScorer_instance.score(features)

    return {
        "features": features.model_dump(),
        "simulated_score": score,
        "cognitive_level": cognitive_level
    }


@router.post("/eeg/simulate/baseline")
async def create_eeg_baseline():
    """
    创建模拟EEG个体基线

    用于相对基线评估模式

    Returns:
        基线特征数据
    """
    from .modalities.eeg_scorer import EEGScorer_instance

    if not EEGScorer_instance.is_simulation_mode():
        raise HTTPException(
            status_code=400,
            detail="模拟器模式未启用，请先调用 /eeg/simulate/enable"
        )

    baseline = EEGScorer_instance.create_simulated_baseline()

    return {
        "baseline": baseline.model_dump(),
        "message": "个体基线已创建"
    }


@router.post("/eeg/simulate/assess")
async def simulate_eeg_assessment(
    cognitive_level: str = Query("medium", enum=["low", "medium", "high"], description="模拟的认知负荷等级"),
    with_baseline: bool = Query(False, description="是否使用个体基线")
):
    """
    完整模拟一次EEG认知负荷评估（用于测试融合流程）

    Args:
        cognitive_level: 模拟的认知负荷等级
        with_baseline: 是否使用个体基线

    Returns:
        模拟评估结果
    """
    from .modalities.eeg_scorer import EEGScorer_instance

    if not EEGScorer_instance.is_simulation_mode():
        raise HTTPException(
            status_code=400,
            detail="模拟器模式未启用，请先调用 /eeg/simulate/enable"
        )

    if with_baseline:
        baseline = EEGScorer_instance.create_simulated_baseline()

    features = EEGScorer_instance.generate_simulated_features(cognitive_level)
    score = EEGScorer_instance.score(features)

    return {
        "features": features.model_dump(),
        "score": score,
        "level": "high" if score > 0.7 else "medium" if score > 0.4 else "low",
        "cognitive_level": cognitive_level,
        "baseline_used": with_baseline
    }


@router.post("/eeg/hardware/connect")
async def connect_muse_hardware(timeout: float = Query(10.0, description="连接超时时间")):
    """
    连接真实 Muse S 硬件设备

    Args:
        timeout: 连接超时时间（秒）

    Returns:
        连接结果
    """
    from .modalities.eeg_hardware_scorer import muse_scorer
    from .modes import set_mode, EEGMode

    try:
        success = await muse_scorer.connect(timeout)

        if success:
            set_mode(EEGMode.HARDWARE)
            return {
                "success": True,
                "message": "Muse S 设备已连接",
                "status": muse_scorer.get_status()
            }
        else:
            return {
                "success": False,
                "message": "连接失败，请检查设备是否开启且 LSL Streamer 已启动"
            }

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"缺少依赖库: {e}。请运行: pip install pylsl numpy scipy"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/eeg/hardware/disconnect")
async def disconnect_muse_hardware():
    """
    断开 Muse S 硬件设备
    """
    from .modalities.eeg_hardware_scorer import muse_scorer
    from .modes import set_mode, EEGMode

    muse_scorer.disconnect()
    set_mode(EEGMode.SIMULATION)

    return {
        "success": True,
        "message": "已断开 Muse S 设备，已切换到模拟器模式"
    }


@router.post("/eeg/hardware/collect")
async def collect_eeg_data(duration: float = Query(30.0, ge=5.0, le=120.0)):
    """
    采集真实 EEG 数据并评分

    Args:
        duration: 采集时长（秒），范围 5-120

    Returns:
        EEG 特征和认知负荷评分
    """
    from .modalities.eeg_hardware_scorer import muse_scorer

    if not muse_scorer.is_available():
        raise HTTPException(status_code=400, detail="Muse 设备未连接，请先调用 /eeg/hardware/connect")

    try:
        data_result = await muse_scorer.collect_data(duration)

        if data_result is None:
            raise HTTPException(status_code=500, detail="EEG 数据采集失败")

        features = data_result["features"]
        quality = data_result.get("quality", {})

        scorer = muse_scorer
        features_obj = EEGFeatures(
            delta_power=features.get("delta_power"),
            theta_power=features.get("theta_power"),
            alpha_power=features.get("alpha_power"),
            beta_power=features.get("beta_power"),
            gamma_power=features.get("gamma_power"),
            theta_beta_ratio=features.get("theta_beta_ratio"),
            theta_alpha_ratio=features.get("theta_alpha_ratio"),
            alpha_beta_ratio=features.get("alpha_beta_ratio")
        )
        score = scorer.score(features_obj)

        return {
            "success": True,
            "features": features,
            "score": round(score, 3),
            "level": "high" if score > 0.7 else "medium" if score > 0.4 else "low",
            "quality": quality,
            "duration_sec": duration,
            "n_samples": data_result.get("n_samples", 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"采集失败: {str(e)}")


@router.post("/eeg/hardware/baseline")
async def create_muse_baseline(duration: float = Query(60.0, ge=30.0, le=180.0)):
    """
    创建个体基线（安静闭眼状态）

    建议采集 60-120 秒的安静、闭眼数据作为个体基线

    Args:
        duration: 采集时长（秒），范围 30-180

    Returns:
        基线特征
    """
    from .modalities.eeg_hardware_scorer import muse_scorer

    if not muse_scorer.is_available():
        raise HTTPException(status_code=400, detail="Muse 设备未连接，请先调用 /eeg/hardware/connect")

    try:
        baseline_features = await muse_scorer.create_baseline(duration)

        if baseline_features is None:
            raise HTTPException(status_code=500, detail="基线采集失败")

        return {
            "success": True,
            "baseline": baseline_features.model_dump(),
            "message": f"基线采集完成（{duration}秒），建议用于后续相对评估",
            "duration_sec": duration
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"基线采集失败: {str(e)}")


@router.get("/eeg/hardware/status")
async def get_hardware_status():
    """
    获取 Muse 硬件状态

    Returns:
        硬件状态信息
    """
    from .modalities.eeg_hardware_scorer import muse_scorer
    from .modes import get_current_mode

    status = muse_scorer.get_status()
    status["current_mode"] = get_current_mode().value

    return status


@router.post("/eeg/switch-mode")
async def switch_eeg_mode(mode: str = Query(..., enum=["simulation", "hardware"])):
    """
    切换 EEG 运行模式

    Args:
        mode: "simulation" 或 "hardware"

    Returns:
        切换结果
    """
    from .modalities.eeg_scorer import EEGScorer_instance
    from .modalities.eeg_hardware_scorer import muse_scorer
    from .modes import set_mode, EEGMode

    if mode == "hardware":
        if not muse_scorer.is_available():
            raise HTTPException(
                status_code=400,
                detail="Muse 设备未连接，无法切换到硬件模式。请先调用 /eeg/hardware/connect"
            )
        set_mode(EEGMode.HARDWARE)
        EEGScorer_instance.disable_simulation()
        message = "已切换到硬件模式"
    else:
        muse_scorer.disconnect()
        set_mode(EEGMode.SIMULATION)
        EEGScorer_instance.enable_simulation()
        message = "已切换到模拟器模式"

    return {
        "success": True,
        "mode": mode,
        "message": message
    }
