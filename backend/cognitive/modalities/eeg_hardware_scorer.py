#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Muse S EEG 评分器 - 真实硬件模式

使用 Muse S 设备进行真实的 EEG 认知负荷评估

依赖:
    pip install pylsl numpy scipy

功能:
    1. 连接/断开 Muse S 设备
    2. 采集 EEG 数据
    3. 预处理提取特征
    4. 基于特征计算认知负荷分数
    5. 支持个体基线对比
"""

import logging
from typing import Optional, Dict, Any, Tuple

from ..schemas.cognitive_load import EEGFeatures
from .eeg_collector import MuseCollector

logger = logging.getLogger(__name__)


class MuseScorer:
    """
    Muse S 评分器

    使用真实 Muse 设备进行 EEG 认知负荷评估

    评分算法:
        - 基于 Theta/Beta 比率 (θ/β)
        - 基于 Alpha 功率变化
        - 支持个体基线对比

    使用流程:
        scorer = MuseScorer()
        await scorer.connect()
        await scorer.create_baseline(duration=60)
        features, score = await scorer.assess(duration=30)
    """

    DEFAULT_COLLECTION_DURATION = 30.0
    DEFAULT_BASELINE_DURATION = 60.0

    def __init__(self):
        self._collector = MuseCollector()
        self._baseline: Optional[EEGFeatures] = None
        self._is_available = False

    def is_available(self) -> bool:
        """
        检查 Muse 设备是否已连接

        Returns:
            bool: 设备是否可用
        """
        self._is_available = self._collector.is_connected()
        return self._is_available

    def is_simulation_mode(self) -> bool:
        """检查是否处于模拟器模式（始终返回 False）"""
        return False

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        连接 Muse 设备

        Args:
            timeout: 连接超时时间（秒）

        Returns:
            bool: 连接是否成功
        """
        logger.info("正在连接 Muse S 设备...")
        success = await self._collector.connect(timeout)
        self._is_available = success

        if success:
            logger.info("Muse S 设备连接成功")
        else:
            logger.warning("Muse S 设备连接失败")

        return success

    def disconnect(self) -> None:
        """断开 Muse 设备连接"""
        self._collector.disconnect()
        self._is_available = False
        logger.info("Muse S 设备已断开")

    async def collect_data(self, duration_sec: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        采集 EEG 数据并预处理

        Args:
            duration_sec: 采集时长（秒）

        Returns:
            包含原始数据、特征和设备信息的字典，失败返回 None
        """
        if not self.is_available():
            logger.error("Muse 设备未连接")
            return None

        logger.info(f"开始采集 EEG 数据，时长 {duration_sec} 秒...")

        raw_data = await self._collector.collect_raw_data(duration_sec)

        if raw_data is None:
            logger.error("EEG 数据采集失败")
            return None

        quality = self._collector.get_signal_quality(raw_data)
        logger.info(f"信号质量: {quality.get('overall', 'unknown')}")

        if quality.get('overall') == 'poor':
            logger.warning("信号质量较差，评估结果可能不可靠")
            logger.warning(f"建议: {quality.get('recommendation', '')}")

        features = self._collector.preprocess(raw_data)

        if features is None:
            logger.error("特征提取失败")
            return None

        return {
            "raw_data": raw_data,
            "features": features,
            "quality": quality,
            "duration_sec": duration_sec,
            "n_samples": len(raw_data)
        }

    async def assess(self, duration_sec: float = 30.0) -> Tuple[Optional[EEGFeatures], Optional[float]]:
        """
        采集数据并进行认知负荷评估

        Args:
            duration_sec: 采集时长（秒）

        Returns:
            (特征, 分数) 元组，任一失败返回 (None, None)
        """
        data_result = await self.collect_data(duration_sec)

        if data_result is None:
            return None, None

        features_dict = data_result["features"]

        features = EEGFeatures(
            delta_power=features_dict.get("delta_power"),
            theta_power=features_dict.get("theta_power"),
            alpha_power=features_dict.get("alpha_power"),
            beta_power=features_dict.get("beta_power"),
            gamma_power=features_dict.get("gamma_power"),
            theta_beta_ratio=features_dict.get("theta_beta_ratio"),
            theta_alpha_ratio=features_dict.get("theta_alpha_ratio"),
            alpha_beta_ratio=features_dict.get("alpha_beta_ratio")
        )

        score = self.score(features)

        return features, score

    def score(self, features: EEGFeatures) -> float:
        """
        基于 EEG 特征计算认知负荷分数

        算法说明:
            1. 如果有基线：使用相对变化计算
               - Theta 功率相对基线增加 → 负荷高
               - Alpha 功率相对基线减少 → 负荷高
               - Theta/Beta 比率增加 → 负荷高

            2. 如果无基线：使用绝对值估算
               - 高 θ/β 比率通常表示高负荷

        Args:
            features: EEG 特征

        Returns:
            0-1 之间的认知负荷分数
        """
        if not self._has_valid_features(features):
            logger.warning("EEG 特征不完整，无法评分")
            return 0.5

        if self._baseline is not None:
            score = self._score_with_baseline(features)
        else:
            score = self._score_absolute(features)

        score = max(0.0, min(1.0, score))

        logger.info(f"认知负荷评分: {score:.3f}")
        logger.info(f"  负荷等级: {'高' if score > 0.7 else '中' if score > 0.4 else '低'}")

        return score

    def _has_valid_features(self, features: EEGFeatures) -> bool:
        """检查特征是否有效"""
        return any([
            features.delta_power,
            features.theta_power,
            features.alpha_power,
            features.beta_power
        ])

    def _score_with_baseline(self, features: EEGFeatures) -> float:
        """
        使用个体基线计算认知负荷分数

        认知科学依据:
            - 高认知负荷时，Theta 波段功率增加（尤其在额区）
            - 高认知负荷时，Alpha 波段功率降低（alpha 抑制）
            - Theta/Beta 比率是衡量注意力负荷的有效指标
        """
        import math

        baseline = self._baseline

        theta_ratio = self._safe_divide(
            features.theta_power or 8.0,
            baseline.theta_power or 8.0
        )

        alpha_ratio = self._safe_divide(
            features.alpha_power or 12.0,
            baseline.alpha_power or 12.0
        )

        theta_beta_ratio = features.theta_beta_ratio or 1.5
        baseline_tbr = self._safe_divide(
            baseline.theta_power or 8.0,
            baseline.beta_power or 6.0
        )
        theta_beta_change = self._safe_divide(theta_beta_ratio, baseline_tbr)

        cognitive_index = (
            0.40 * max(0, theta_ratio - 1.0) +
            0.30 * max(0, 1.0 - alpha_ratio) +
            0.30 * max(0, theta_beta_change - 1.0)
        )

        score = 1.0 / (1.0 + math.exp(-3.0 * (cognitive_index - 0.5)))

        return score

    def _score_absolute(self, features: EEGFeatures) -> float:
        """
        使用绝对值计算认知负荷分数

        基于典型 EEG 频段功率分布
        """
        tbr = features.theta_beta_ratio or 1.5
        tar = features.theta_alpha_ratio or 1.0
        abr = features.alpha_beta_ratio or 1.5

        tbr_score = min(tbr / 3.0, 1.0)

        alpha_beta_norm = max(0, min(abr / 2.5, 1.0))
        inverse_abr = 1.0 - alpha_beta_norm

        raw_score = 0.5 * tbr_score + 0.3 * inverse_abr + 0.2 * min(tar / 2.5, 1.0)

        return min(raw_score, 1.0)

    def _safe_divide(self, numerator: float, denominator: float) -> float:
        """安全除法"""
        if denominator == 0 or denominator is None:
            return 1.0
        if numerator is None:
            return 1.0
        return numerator / denominator

    async def create_baseline(self, duration_sec: float = 60.0) -> Optional[EEGFeatures]:
        """
        创建个体基线

        基线采集条件：安静、闭眼、放松状态，持续 60-120 秒

        Args:
            duration_sec: 采集时长（秒）

        Returns:
            基线特征，失败返回 None
        """
        if not self.is_available():
            logger.error("Muse 设备未连接，无法创建基线")
            return None

        logger.info("=" * 50)
        logger.info("开始创建个体基线")
        logger.info("请确保：")
        logger.info("  1. 佩戴好 Muse 设备")
        logger.info("  2. 处于安静环境")
        logger.info("  3. 放松、闭眼")
        logger.info(f"  4. 保持 {duration_sec} 秒...")
        logger.info("=" * 50)

        features, _ = await self.assess(duration_sec)

        if features is None:
            logger.error("基线创建失败")
            return None

        self._baseline = features

        logger.info("=" * 50)
        logger.info("个体基线创建成功!")
        logger.info(f"  Theta: {features.theta_power:.3f} μV²")
        logger.info(f"  Alpha: {features.alpha_power:.3f} μV²")
        logger.info(f"  Beta: {features.beta_power:.3f} μV²")
        logger.info(f"  Theta/Beta: {features.theta_beta_ratio:.3f}")
        logger.info("后续评估将使用此基线进行对比")
        logger.info("=" * 50)

        return features

    def set_baseline(self, baseline: EEGFeatures) -> None:
        """
        手动设置个体基线

        Args:
            baseline: 基线特征
        """
        self._baseline = baseline
        logger.info("个体基线已设置")

    def get_baseline(self) -> Optional[EEGFeatures]:
        """获取当前个体基线"""
        return self._baseline

    def clear_baseline(self) -> None:
        """清除个体基线"""
        self._baseline = None
        logger.info("个体基线已清除")

    def get_status(self) -> Dict[str, Any]:
        """
        获取评分器状态

        Returns:
            状态信息字典
        """
        status = {
            "available": self.is_available(),
            "device_type": "muse_s",
            "hardware_mode": True,
            "simulation_mode": False,
            "has_baseline": self._baseline is not None,
            "collector_info": self._collector.get_device_info()
        }

        if self._baseline:
            baseline = self._baseline
            status["baseline_info"] = {
                "theta_power": baseline.theta_power,
                "alpha_power": baseline.alpha_power,
                "beta_power": baseline.beta_power,
                "theta_beta_ratio": baseline.theta_beta_ratio
            }

        return status


muse_scorer = MuseScorer()
