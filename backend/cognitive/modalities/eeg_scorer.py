#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EEG评分器

支持两种模式：
1. 真实硬件模式：连接Muse/OpenBCI设备
2. 模拟器模式：使用EEGSimulator生成测试数据

当硬件可用时，计算方法：
1. 功率谱分析 (δ, θ, α, β, γ)
2. 关键比率计算 (θ/β, θ/α, α/β)
3. 与个体基线对比
4. 综合评分
"""

import logging
from typing import Optional

import numpy as np

from ..schemas.cognitive_load import EEGFeatures
from .eeg_simulator import (
    EEGSimulator,
    EEGSimulatorManager,
    CognitiveLoadLevel,
    SignalQuality
)

logger = logging.getLogger(__name__)


class EEGScorer:
    """
    EEG评分器

    支持真实设备和模拟器两种模式
    """

    def __init__(self, simulation_mode: bool = True):
        """
        初始化EEG评分器

        Args:
            simulation_mode: 是否使用模拟器模式（默认True，用于开发测试）
        """
        self._simulation_mode = simulation_mode
        self._device_type: Optional[str] = None
        self._baseline: Optional[EEGFeatures] = None
        self._simulator: Optional[EEGSimulator] = None

        if self._simulation_mode:
            self._enable_simulation()
        else:
            self._available = False

    def _enable_simulation(self) -> None:
        """启用模拟器模式"""
        self._simulator = EEGSimulatorManager.get_simulator()
        self._available = True
        self._device_type = "simulator"
        logger.info("EEG评分器已启用模拟器模式")

    def _disable_simulation(self) -> None:
        """禁用模拟器模式"""
        self._simulator = None
        self._available = False
        self._device_type = None
        logger.info("EEG评分器已禁用模拟器模式")

    def is_available(self) -> bool:
        """
        检测EEG设备是否连接

        Returns:
            bool: 设备是否可用
        """
        if self._simulation_mode and self._simulator:
            return True
        return self._available

    def is_simulation_mode(self) -> bool:
        """检查是否处于模拟器模式"""
        return self._simulation_mode

    def set_available(self, available: bool, device_type: Optional[str] = None) -> None:
        """
        设置设备可用性（用于手动控制）

        Args:
            available: 是否可用
            device_type: 设备类型
        """
        if not self._simulation_mode:
            self._available = available
            self._device_type = device_type

    def enable_simulation(self) -> None:
        """启用模拟器模式"""
        self._enable_simulation()

    def disable_simulation(self) -> None:
        """禁用模拟器模式（切换到真实硬件模式）"""
        self._disable_simulation()

    def set_cognitive_level(self, level: str) -> None:
        """
        设置模拟的认知负荷等级

        Args:
            level: "low", "medium", "high"
        """
        if self._simulator:
            level_map = {
                "low": CognitiveLoadLevel.LOW,
                "medium": CognitiveLoadLevel.MEDIUM,
                "high": CognitiveLoadLevel.HIGH
            }
            cognitive_level = level_map.get(level.lower(), CognitiveLoadLevel.MEDIUM)
            self._simulator.set_cognitive_level(cognitive_level)

    def set_signal_quality(self, quality: str) -> None:
        """
        设置模拟信号质量

        Args:
            quality: "excellent", "good", "fair", "poor"
        """
        if self._simulator:
            quality_map = {
                "excellent": SignalQuality.EXCELLENT,
                "good": SignalQuality.GOOD,
                "fair": SignalQuality.FAIR,
                "poor": SignalQuality.POOR
            }
            signal_quality = quality_map.get(quality.lower(), SignalQuality.GOOD)
            self._simulator.set_signal_quality(signal_quality)

    def score(self, features: EEGFeatures) -> Optional[float]:
        """
        基于EEG特征的认知负荷评分

        算法说明：
        - Theta/Beta比率 ↑ → 认知负荷高
        - Theta功率相对基线 ↑ → 负荷高
        - Alpha功率相对基线 ↓ → 负荷高

        Args:
            features: EEG特征

        Returns:
            0-1之间的认知负荷分数，如果不可用返回None
        """
        if not self.is_available():
            return None

        if not self._has_valid_features(features):
            logger.warning("EEG特征不完整，使用默认分数")
            return 0.5

        theta_beta = features.theta_beta_ratio or 1.5
        theta_alpha = features.theta_alpha_ratio or 1.0
        alpha_beta = features.alpha_beta_ratio or 1.5

        if self._baseline:
            score = self._score_with_baseline(features)
        else:
            score = self._score_absolute(theta_beta, theta_alpha, alpha_beta)

        return float(max(0.0, min(1.0, score)))

    def _has_valid_features(self, features: EEGFeatures) -> bool:
        """检查特征是否有效"""
        return any([
            features.delta_power,
            features.theta_power,
            features.alpha_power,
            features.beta_power,
            features.gamma_power
        ])

    def _score_with_baseline(self, features: EEGFeatures) -> float:
        """使用基线计算认知负荷分数"""
        baseline = self._baseline

        theta_ratio = self._safe_divide(
            features.theta_power or baseline.theta_power,
            baseline.theta_power
        )
        alpha_ratio = self._safe_divide(
            features.alpha_power or baseline.alpha_power,
            baseline.alpha_power
        )

        theta_beta_ratio = features.theta_beta_ratio or 1.5
        baseline_tbr = self._safe_divide(baseline.theta_power, baseline.beta_power) if baseline.beta_power else 1.5
        theta_beta_change = self._safe_divide(theta_beta_ratio, baseline_tbr)

        cognitive_index = (
            0.40 * max(0, theta_ratio - 1.0) +
            0.30 * max(0, 1.0 - alpha_ratio) +
            0.30 * max(0, theta_beta_change - 1.0)
        )

        score = 1.0 / (1.0 + np.exp(-3.0 * (cognitive_index - 0.5)))

        return score

    def _score_absolute(
        self,
        theta_beta_ratio: float,
        theta_alpha_ratio: float,
        alpha_beta_ratio: float
    ) -> float:
        """使用绝对值计算认知负荷分数"""
        tbr_score = min(theta_beta_ratio / 3.0, 1.0)

        alpha_beta_norm = max(0, min(alpha_beta_ratio / 2.5, 1.0))
        inverse_abr = 1.0 - alpha_beta_norm

        raw_score = 0.5 * tbr_score + 0.3 * inverse_abr + 0.2 * (theta_alpha_ratio / 2.5)

        return min(raw_score, 1.0)

    def _safe_divide(self, numerator: float, denominator: float) -> float:
        """安全除法"""
        if denominator == 0 or numerator is None or denominator is None:
            return 1.0
        return numerator / denominator

    def generate_simulated_features(
        self,
        cognitive_level: Optional[str] = None
    ) -> EEGFeatures:
        """
        生成模拟EEG特征（仅模拟器模式可用）

        Args:
            cognitive_level: 可选，指定认知负荷等级

        Returns:
            EEGFeatures: 模拟的EEG特征
        """
        if not self._simulator:
            raise RuntimeError("模拟器模式未启用")

        if cognitive_level:
            self.set_cognitive_level(cognitive_level)

        return self._simulator.generate_features()

    def create_simulated_baseline(self) -> EEGFeatures:
        """
        创建模拟个体基线（仅模拟器模式可用）

        Returns:
            EEGFeatures: 基线特征
        """
        if not self._simulator:
            raise RuntimeError("模拟器模式未启用")

        baseline = self._simulator.generate_baseline()
        self.set_baseline(baseline)
        return baseline

    def preprocess(self, raw_data: bytes) -> EEGFeatures:
        """
        预处理 + 特征提取（真实硬件模式）

        实现MNE-Python预处理流水线：
        1. 带通滤波 (0.5-50Hz)
        2. 伪迹剔除 (眨眼/运动)
        3. 独立成分分析 (ICA)
        4. 功率谱密度 (PSD) 估计
        5. 频段功率计算

        Args:
            raw_data: 原始EEG数据

        Returns:
            EEGFeatures: 提取的特征
        """
        if self._simulation_mode:
            return self.generate_simulated_features()

        raise NotImplementedError("真实硬件预处理待设备接入后实现")

    def set_baseline(self, baseline_features: EEGFeatures) -> None:
        """
        设置个体基线

        Args:
            baseline_features: 基线特征
        """
        self._baseline = baseline_features
        if self._simulator:
            self._simulator.set_baseline(baseline_features)

    def get_baseline(self) -> Optional[EEGFeatures]:
        """
        获取个体基线

        Returns:
            基线特征或None
        """
        return self._baseline

    def get_status(self) -> dict:
        """
        获取评分器状态

        Returns:
            dict: 状态信息
        """
        status = {
            "available": self.is_available(),
            "simulation_mode": self._simulation_mode,
            "device_type": self._device_type,
            "has_baseline": self._baseline is not None
        }

        if self._simulation_mode and self._simulator:
            status["simulator"] = self._simulator.get_status()

        return status


EEGScorer_instance = EEGScorer(simulation_mode=True)
