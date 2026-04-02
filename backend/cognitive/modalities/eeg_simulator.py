#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EEG模拟器 - 用于开发测试

功能：
1. 生成模拟EEG频段功率数据
2. 支持不同认知负荷水平的模拟
3. 可调节噪声水平和信号质量
4. 提供实时模拟数据流接口

使用场景：
- 前端开发调试
- 后端API测试
- 认知负荷融合算法验证
"""

import time
import random
import math
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from ..schemas.cognitive_load import EEGFeatures


class CognitiveLoadLevel(str, Enum):
    """模拟的认知负荷等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SignalQuality(str, Enum):
    """信号质量等级"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class SimulatorConfig:
    """模拟器配置"""
    cognitive_level: CognitiveLoadLevel = CognitiveLoadLevel.MEDIUM
    signal_quality: SignalQuality = SignalQuality.GOOD
    noise_level: float = 0.1
    use_baseline: bool = True
    individual_variation: float = 0.15


class EEGSimulator:
    """
    EEG模拟器

    基于认知负荷研究的典型EEG频段功率分布生成模拟数据。
    参考值来源于文献：
    - Gevins et al. (1998) - 高认知负荷时Theta增加、Alpha减少
    - Smith et al. (2001) - Theta/Beta比率与注意力负相关
    """

    BASE_POWER = {
        "delta": 15.0,
        "theta": 8.0,
        "alpha": 12.0,
        "beta": 6.0,
        "gamma": 3.0
    }

    COGNITIVE_EFFECTS = {
        CognitiveLoadLevel.LOW: {
            "delta_mult": 1.2,
            "theta_mult": 0.7,
            "alpha_mult": 1.3,
            "beta_mult": 0.9,
            "gamma_mult": 0.8,
            "theta_beta_ratio": 1.0,
            "theta_alpha_ratio": 0.5,
            "alpha_beta_ratio": 2.0
        },
        CognitiveLoadLevel.MEDIUM: {
            "delta_mult": 1.0,
            "theta_mult": 1.2,
            "alpha_mult": 1.0,
            "beta_mult": 1.0,
            "gamma_mult": 1.0,
            "theta_beta_ratio": 1.5,
            "theta_alpha_ratio": 1.0,
            "alpha_beta_ratio": 1.5
        },
        CognitiveLoadLevel.HIGH: {
            "delta_mult": 0.9,
            "theta_mult": 1.8,
            "alpha_mult": 0.6,
            "beta_mult": 1.2,
            "gamma_mult": 1.4,
            "theta_beta_ratio": 2.5,
            "theta_alpha_ratio": 2.0,
            "alpha_beta_ratio": 0.8
        }
    }

    def __init__(self, config: Optional[SimulatorConfig] = None):
        self.config = config or SimulatorConfig()
        self._baseline: Optional[EEGFeatures] = None
        self._session_start: Optional[float] = None
        self._is_recording = False
        self._data_buffer: List[Dict[str, Any]] = []

    def set_cognitive_level(self, level: CognitiveLoadLevel) -> None:
        """设置模拟的认知负荷等级"""
        self.config.cognitive_level = level

    def set_signal_quality(self, quality: SignalQuality) -> None:
        """设置信号质量"""
        self.config.signal_quality = quality

    def set_baseline(self, baseline: EEGFeatures) -> None:
        """设置个体基线"""
        self._baseline = baseline

    def generate_features(self, add_noise: bool = True) -> EEGFeatures:
        """
        生成模拟EEG特征

        Args:
            add_noise: 是否添加随机噪声

        Returns:
            EEGFeatures: 模拟的EEG特征
        """
        effect = self.COGNITIVE_EFFECTS[self.config.cognitive_level]

        if add_noise:
            noise_scale = self._get_noise_scale()
            variation = self.config.individual_variation * noise_scale
        else:
            variation = 0.0

        delta_power = self._scale_value(
            self.BASE_POWER["delta"] * effect["delta_mult"], variation
        )
        theta_power = self._scale_value(
            self.BASE_POWER["theta"] * effect["theta_mult"], variation
        )
        alpha_power = self._scale_value(
            self.BASE_POWER["alpha"] * effect["alpha_mult"], variation
        )
        beta_power = self._scale_value(
            self.BASE_POWER["beta"] * effect["beta_mult"], variation
        )
        gamma_power = self._scale_value(
            self.BASE_POWER["gamma"] * effect["gamma_mult"], variation
        )

        theta_beta_ratio = self._safe_divide(theta_power, beta_power)
        theta_alpha_ratio = self._safe_divide(theta_power, alpha_power)
        alpha_beta_ratio = self._safe_divide(alpha_power, beta_power)

        features = EEGFeatures(
            delta_power=round(delta_power, 3),
            theta_power=round(theta_power, 3),
            alpha_power=round(alpha_power, 3),
            beta_power=round(beta_power, 3),
            gamma_power=round(gamma_power, 3),
            theta_beta_ratio=round(theta_beta_ratio, 3),
            theta_alpha_ratio=round(theta_alpha_ratio, 3),
            alpha_beta_ratio=round(alpha_beta_ratio, 3)
        )

        if self.config.use_baseline and self._baseline:
            features = self._apply_relative_changes(features)

        return features

    def _apply_relative_changes(self, features: EEGFeatures) -> EEGFeatures:
        """计算相对基线的变化"""
        if not self._baseline:
            return features

        baseline = self._baseline

        if baseline.delta_power:
            features.delta_power = features.delta_power / baseline.delta_power
        if baseline.theta_power:
            features.theta_power = features.theta_power / baseline.theta_power
        if baseline.alpha_power:
            features.alpha_power = features.alpha_power / baseline.alpha_power
        if baseline.beta_power:
            features.beta_power = features.beta_power / baseline.beta_power
        if baseline.gamma_power:
            features.gamma_power = features.gamma_power / baseline.gamma_power

        return features

    def _get_noise_scale(self) -> float:
        """根据信号质量获取噪声系数"""
        noise_map = {
            SignalQuality.EXCELLENT: 0.05,
            SignalQuality.GOOD: 0.1,
            SignalQuality.FAIR: 0.2,
            SignalQuality.POOR: 0.35
        }
        return noise_map.get(self.config.signal_quality, 0.1)

    def _scale_value(self, base: float, variation: float) -> float:
        """添加随机变化"""
        scale = 1.0 + random.uniform(-variation, variation)
        return base * scale

    def _safe_divide(self, numerator: float, denominator: float) -> float:
        """安全除法"""
        if denominator == 0:
            return 0.0
        return numerator / denominator

    def start_session(self) -> Dict[str, Any]:
        """开始模拟采集会话"""
        self._session_start = time.time()
        self._is_recording = True
        self._data_buffer = []

        return {
            "session_id": f"sim_{int(self._session_start)}",
            "device_type": "simulator",
            "sampling_rate": 256,
            "channels": 4,
            "start_time": int(self._session_start * 1000)
        }

    def collect_segment(self, duration_sec: float = 5.0) -> EEGFeatures:
        """
        采集一段时间的模拟数据并返回特征

        Args:
            duration_sec: 采集时长（秒）

        Returns:
            EEGFeatures: 模拟的EEG特征
        """
        if not self._is_recording:
            self.start_session()

        time.sleep(min(duration_sec, 0.1))

        features = self.generate_features()

        self._data_buffer.append({
            "timestamp": time.time(),
            "features": features.model_dump()
        })

        return features

    def stop_session(self) -> Dict[str, Any]:
        """停止模拟采集会话"""
        self._is_recording = False

        if not self._data_buffer:
            return {"segments": 0}

        avg_features = self._average_features()
        duration = time.time() - self._session_start if self._session_start else 0

        result = {
            "segments": len(self._data_buffer),
            "duration_sec": round(duration, 2),
            "average_features": avg_features
        }

        self._data_buffer = []
        self._session_start = None

        return result

    def _average_features(self) -> Dict[str, float]:
        """计算缓冲区中所有特征的平均值"""
        if not self._data_buffer:
            return {}

        sums = {
            "delta_power": 0.0,
            "theta_power": 0.0,
            "alpha_power": 0.0,
            "beta_power": 0.0,
            "gamma_power": 0.0
        }

        for entry in self._data_buffer:
            f = entry["features"]
            for key in sums:
                if f.get(key) is not None:
                    sums[key] += f[key]

        count = len(self._data_buffer)
        avg = {k: round(v / count, 3) for k, v in sums.items()}

        avg["theta_beta_ratio"] = round(
            self._safe_divide(avg["theta_power"], avg["beta_power"]), 3
        )
        avg["theta_alpha_ratio"] = round(
            self._safe_divide(avg["theta_power"], avg["alpha_power"]), 3
        )
        avg["alpha_beta_ratio"] = round(
            self._safe_divide(avg["alpha_power"], avg["beta_power"]), 3
        )

        return avg

    def generate_baseline(self) -> EEGFeatures:
        """
        生成模拟个体基线（安静闭眼状态）

        Returns:
            EEGFeatures: 基线特征
        """
        original_level = self.config.cognitive_level
        self.config.cognitive_level = CognitiveLoadLevel.LOW

        baseline = self.generate_features(add_noise=False)

        self.config.cognitive_level = original_level

        self._baseline = baseline
        return baseline

    def get_status(self) -> Dict[str, Any]:
        """获取模拟器状态"""
        return {
            "available": True,
            "device_type": "eeg_simulator",
            "simulation_mode": True,
            "cognitive_level": self.config.cognitive_level.value,
            "signal_quality": self.config.signal_quality.value,
            "has_baseline": self._baseline is not None,
            "is_recording": self._is_recording,
            "buffer_size": len(self._data_buffer)
        }


class EEGSimulatorManager:
    """
    EEG模拟器管理器

    单例模式管理全局模拟器实例
    """

    _instance: Optional["EEGSimulatorManager"] = None
    _simulator: Optional[EEGSimulator] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._simulator = EEGSimulator()
        return cls._instance

    @classmethod
    def get_simulator(cls) -> EEGSimulator:
        """获取模拟器实例"""
        if cls._simulator is None:
            cls._simulator = EEGSimulator()
        return cls._simulator

    @classmethod
    def reset(cls):
        """重置模拟器"""
        if cls._simulator:
            cls._simulator._baseline = None
            cls._simulator._is_recording = False
            cls._simulator._data_buffer = []


eeg_simulator = EEGSimulatorManager.get_simulator()
