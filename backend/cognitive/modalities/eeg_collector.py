#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Muse S EEG 数据采集器

通过 LSL (Lab Streaming Layer) 协议连接 Muse 设备
采集原始 EEG 数据并进行预处理和特征提取

依赖:
    pip install pylsl numpy scipy

Muse S 规格:
    - 4个干电极 (TP9, AF7, AF8, TP10)
    - 采样率: 256 Hz
    - 数据传输: Bluetooth Low Energy
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BandPowers:
    """频段功率数据"""
    delta: float
    theta: float
    alpha: float
    beta: float
    gamma: float


class MuseCollector:
    """
    Muse S 数据采集器

    通过 LSL 连接 Muse 设备，采集原始 EEG 数据并进行预处理

    使用流程:
        collector = MuseCollector()
        await collector.connect()
        raw_data = await collector.collect_raw_data(duration_sec=30.0)
        features = collector.preprocess(raw_data)
        collector.disconnect()
    """

    CHANNEL_NAMES = ["TP9", "AF7", "AF8", "TP10"]
    SAMPLING_RATE = 256

    FREQUENCY_BANDS = {
        "delta": (0.5, 4),
        "theta": (4, 8),
        "alpha": (8, 13),
        "beta": (13, 30),
        "gamma": (30, 50)
    }

    def __init__(self):
        self._connected = False
        self._inlet = None
        self._device_id: Optional[str] = None
        self._sampling_rate = self.SAMPLING_RATE
        self._channel_count = 4

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        连接 Muse 设备

        Args:
            timeout: 搜索设备的超时时间（秒）

        Returns:
            bool: 连接是否成功
        """
        logger.info("正在搜索 Muse 设备...")

        try:
            from pylsl import StreamInlet, resolve_byprop

            streams = resolve_byprop("type", "EEG", timeout=timeout)

            if not streams:
                logger.warning("未找到 EEG 流，尝试搜索 Muse 流...")
                streams = resolve_byprop("name", "Muse", timeout=timeout)

            if not streams:
                logger.error("=" * 50)
                logger.error("未找到 Muse 设备，请确保：")
                logger.error("1. Muse 设备已开启")
                logger.error("2. Muse Direct 应用已连接设备")
                logger.error("3. 在应用设置中启用了 LSL Streaming")
                logger.error("=" * 50)
                return False

            self._inlet = StreamInlet(streams[0])
            self._connected = True

            info = self._inlet.info()
            self._device_id = info.name()
            self._sampling_rate = int(info.nominal_srate())
            self._channel_count = info.channel_count()

            logger.info(f"已连接到 Muse 设备: {self._device_id}")
            logger.info(f"  采样率: {self._sampling_rate} Hz")
            logger.info(f"  通道数: {self._channel_count}")
            logger.info(f"  通道名称: {self.CHANNEL_NAMES}")

            return True

        except ImportError:
            logger.error("缺少 pylsl 库，请运行: pip install pylsl")
            return False
        except Exception as e:
            logger.error(f"连接 Muse 设备失败: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """断开设备连接"""
        if self._inlet:
            try:
                self._inlet.close_stream()
            except Exception:
                pass
        self._connected = False
        self._inlet = None
        self._device_id = None
        logger.info("已断开 Muse 设备连接")

    async def collect_raw_data(self, duration_sec: float = 30.0) -> Optional[np.ndarray]:
        """
        采集指定时长的原始 EEG 数据

        使用线程池执行器避免阻塞事件循环

        Args:
            duration_sec: 采集时长（秒）

        Returns:
            np.ndarray: 形状为 (samples, channels) 的原始数据，失败返回 None
        """
        if not self._connected or not self._inlet:
            logger.error("Muse 设备未连接")
            return None

        n_samples = int(duration_sec * self._sampling_rate)
        raw_buffer: List[List[float]] = []

        logger.info(f"开始采集 {duration_sec} 秒的 EEG 数据...")
        logger.info(f"预计采集 {n_samples} 个样本")

        try:
            from pylsl import local_clock

            self._inlet.open_stream()

            start_time = local_clock()
            samples_collected = 0
            loop = asyncio.get_event_loop()

            while samples_collected < n_samples:
                sample, timestamp = await loop.run_in_executor(
                    None, self._inlet.pull_sample, 1.0
                )

                if sample:
                    raw_buffer.append(list(sample))
                    samples_collected += 1

                    if samples_collected % 500 == 0:
                        elapsed = local_clock() - start_time
                        progress = (samples_collected / n_samples) * 100
                        logger.info(f"  进度: {progress:.1f}% ({samples_collected}/{n_samples})")

                if local_clock() - start_time > duration_sec + 5:
                    logger.warning("采集超时，提前结束")
                    break

            elapsed = local_clock() - start_time
            logger.info(f"采集完成，共 {len(raw_buffer)} 个样本，耗时 {elapsed:.2f} 秒")

            if len(raw_buffer) < 100:
                logger.error("采集样本过少，数据可能不可靠")
                return None

            return np.array(raw_buffer)

        except Exception as e:
            logger.error(f"采集数据时出错: {e}")
            return None

    def preprocess(self, raw_data: np.ndarray) -> Optional[Dict[str, float]]:
        """
        预处理原始数据并提取特征

        流程：
            1.  Validation 检查
            2.  带通滤波 (1-50 Hz)
            3.  伪迹剔除（幅度阈值）
            4.  FFT 功率谱分析 (Welch 方法)
            5.  频段功率计算
            6.  认知负荷比率计算

        Args:
            raw_data: 形状为 (samples, channels) 的原始数据

        Returns:
            Dict containing band powers and ratios, or None on failure
        """
        if raw_data is None or len(raw_data) < 256:
            logger.warning("数据样本过少，无法进行可靠的频谱分析")
            return None

        try:
            from scipy.signal import butter, filtfilt, welch

            data = self._remove_artifacts(raw_data)

            if len(data) < 256:
                logger.warning("伪迹剔除后数据过少")
                return None

            data = self._bandpass_filter(data, 1, 50, self._sampling_rate)

            band_powers = self._compute_band_powers(data)

            powers = band_powers

            theta_beta_ratio = self._safe_divide(powers.theta, powers.beta)
            theta_alpha_ratio = self._safe_divide(powers.theta, powers.alpha)
            alpha_beta_ratio = self._safe_divide(powers.alpha, powers.beta)

            features = {
                "delta_power": round(powers.delta, 3),
                "theta_power": round(powers.theta, 3),
                "alpha_power": round(powers.alpha, 3),
                "beta_power": round(powers.beta, 3),
                "gamma_power": round(powers.gamma, 3),
                "theta_beta_ratio": round(theta_beta_ratio, 3),
                "theta_alpha_ratio": round(theta_alpha_ratio, 3),
                "alpha_beta_ratio": round(alpha_beta_ratio, 3)
            }

            logger.info("特征提取完成:")
            logger.info(f"  Theta/Beta = {theta_beta_ratio:.3f}")
            logger.info(f"  Theta/Alpha = {theta_alpha_ratio:.3f}")
            logger.info(f"  Alpha/Beta = {alpha_beta_ratio:.3f}")

            return features

        except ImportError:
            logger.error("缺少 scipy 库，请运行: pip install scipy")
            return None
        except Exception as e:
            logger.error(f"预处理失败: {e}")
            return None

    def _remove_artifacts(self, data: np.ndarray, threshold: float = 100.0) -> np.ndarray:
        """
        简单的伪迹剔除

        使用固定幅度阈值 ±100μV，符合 EEG 领域标准

        Args:
            data: 原始数据 (samples, channels)
            threshold: 固定幅度阈值 (μV)，默认 100μV

        Returns:
            处理后的数据
        """
        valid_mask = np.ones(len(data), dtype=bool)

        for ch in range(data.shape[1]):
            channel_data = data[:, ch]
            channel_valid = np.abs(channel_data) < threshold
            valid_mask &= channel_valid

        clean_data = data[valid_mask]

        n_removed = len(data) - len(clean_data)
        if n_removed > 0:
            logger.info(f"伪迹剔除: 移除 {n_removed} 个样本 ({n_removed/len(data)*100:.1f}%)")

        return clean_data

    def _bandpass_filter(self, data: np.ndarray, low: float, high: float, fs: float) -> np.ndarray:
        """
        带通滤波

        Args:
            data: 输入数据
            low: 低频 cutoff (Hz)
            high: 高频 cutoff (Hz)
            fs: 采样率 (Hz)

        Returns:
            滤波后的数据
        """
        from scipy.signal import butter, filtfilt

        nyq = fs / 2
        low_cut = max(0.01, min(low / nyq, 0.99))
        high_cut = max(0.01, min(high / nyq, 0.99))

        if low_cut >= high_cut:
            logger.warning(f"无效的滤波参数: low={low}, high={high}")
            return data

        b, a = butter(4, [low_cut, high_cut], btype='band')

        if data.ndim == 1:
            return filtfilt(b, a, data)
        else:
            filtered = np.zeros_like(data)
            for ch in range(data.shape[1]):
                try:
                    filtered[:, ch] = filtfilt(b, a, data[:, ch])
                except Exception:
                    filtered[:, ch] = data[:, ch]
            return filtered

    def _compute_band_powers(self, data: np.ndarray) -> BandPowers:
        """
        计算各频段功率

        使用 Welch 方法估计功率谱密度，然后计算各频段积分功率

        Args:
            data: 预处理后的数据 (samples, channels)

        Returns:
            BandPowers 对象
        """
        from scipy.signal import welch

        powers = {}

        for band_name, (low, high) in self.FREQUENCY_BANDS.items():
            band_powers = []

            for ch in range(data.shape[1]):
                try:
                    channel_data = data[:, ch]

                    nperseg = min(256, len(channel_data))
                    freqs, psd = welch(channel_data, fs=self._sampling_rate, nperseg=nperseg)

                    idx = np.logical_and(freqs >= low, freqs <= high)

                    if np.any(idx):
                        band_power = np.trapz(psd[idx], freqs[idx])
                    else:
                        band_power = 0.0

                    band_powers.append(band_power)

                except Exception as e:
                    logger.warning(f"通道 {ch} {band_name} 频段计算失败: {e}")
                    band_powers.append(0.0)

            powers[band_name] = float(np.mean(band_powers))

        return BandPowers(
            delta=powers.get("delta", 15.0),
            theta=powers.get("theta", 8.0),
            alpha=powers.get("alpha", 12.0),
            beta=powers.get("beta", 6.0),
            gamma=powers.get("gamma", 3.0)
        )

    def _safe_divide(self, numerator: float, denominator: float) -> float:
        """安全除法，避免除零"""
        if denominator == 0 or denominator is None:
            return 0.0
        if numerator is None:
            return 0.0
        return numerator / denominator

    def get_device_info(self) -> Dict[str, Any]:
        """获取设备信息"""
        if not self._connected:
            return {
                "connected": False,
                "message": "设备未连接"
            }

        return {
            "connected": self._connected,
            "device_id": self._device_id,
            "sampling_rate": self._sampling_rate,
            "channel_count": self._channel_count,
            "channel_names": self.CHANNEL_NAMES,
            "frequency_bands": list(self.FREQUENCY_BANDS.keys())
        }

    def get_signal_quality(self, raw_data: np.ndarray) -> Dict[str, Any]:
        """
        评估信号质量

        Args:
            raw_data: 原始 EEG 数据

        Returns:
            信号质量评估结果
        """
        if raw_data is None or len(raw_data) < 256:
            return {"quality": "unknown", "score": 0.0}

        try:
            channel_qualities = []

            for ch in range(raw_data.shape[1]):
                channel_data = raw_data[:, ch]

                std = np.std(channel_data)
                max_val = np.max(np.abs(channel_data))

                if max_val > 200:
                    quality = "poor"
                elif max_val > 100:
                    quality = "fair"
                elif std > 20:
                    quality = "fair"
                else:
                    quality = "good"

                channel_qualities.append({
                    "channel": self.CHANNEL_NAMES[ch] if ch < len(self.CHANNEL_NAMES) else f"Ch{ch+1}",
                    "quality": quality,
                    "std": round(std, 2),
                    "max_amplitude": round(max_val, 2)
                })

            overall_quality = "good"
            poor_count = sum(1 for c in channel_qualities if c["quality"] == "poor")
            fair_count = sum(1 for c in channel_qualities if c["quality"] == "fair")

            if poor_count >= 2:
                overall_quality = "poor"
            elif poor_count >= 1 or fair_count >= 3:
                overall_quality = "fair"

            return {
                "overall": overall_quality,
                "channels": channel_qualities,
                "recommendation": self._get_quality_recommendation(overall_quality)
            }

        except Exception as e:
            return {"quality": "unknown", "error": str(e)}

    def _get_quality_recommendation(self, quality: str) -> str:
        """根据质量返回建议"""
        recommendations = {
            "good": "信号质量良好，可以进行评估",
            "fair": "信号质量一般，建议检查电极接触",
            "poor": "信号质量差，请重新调整电极位置",
            "unknown": "无法评估信号质量"
        }
        return recommendations.get(quality, "")


muse_collector = MuseCollector()
