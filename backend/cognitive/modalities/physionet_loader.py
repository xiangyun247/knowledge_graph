#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PhysioNet EEGMAT 数据集适配器

用于将 PhysioNet 的 EEG During Mental Arithmetic Tasks 数据集
接入认知负荷评估 pipeline

数据集信息:
- 36 名被试执行心算任务
- 19 导联 EEG (标准 10-20 系统)
- 采样率: 500 Hz
- 每个被试 2 个文件 (_1 和 _2)
"""
import os
from typing import List, Dict, Optional, Tuple
import numpy as np

try:
    import mne
    MNE_AVAILABLE = True
except ImportError:
    MNE_AVAILABLE = False

from ..schemas.cognitive_load import EEGFeatures
from .eeg_scorer import EEGScorer


MUSE_CHANNEL_MAP = {
    "TP9": "T3",
    "AF7": "F7",
    "AF8": "F8",
    "TP10": "T4"
}

MUSE_SAMPLE_RATE = 256


class PhysioNetLoader:
    """
    PhysioNet EEGMAT 数据集加载器

    功能:
    1. 读取 EDF 格式文件
    2. 选择与 Muse S 对应的 4 通道
    3. 重采样到 256 Hz
    4. 分段提取 EEG epochs
    5. 计算频段功率特征
    """

    TARGET_CHANNELS = ["T3", "T4", "F7", "F8"]
    FREQ_BANDS = {
        "delta": (0.5, 4),
        "theta": (4, 8),
        "alpha": (8, 13),
        "beta": (13, 30),
        "gamma": (30, 100)
    }

    def __init__(self, data_dir: str):
        """
        初始化加载器

        Args:
            data_dir: 数据集根目录 (包含 Subject*.edf 文件)
        """
        self.data_dir = data_dir
        self.sfreq = MUSE_SAMPLE_RATE

    def list_subjects(self) -> List[str]:
        """列出所有被试文件"""
        import glob
        pattern = os.path.join(self.data_dir, "Subject*.edf")
        files = glob.glob(pattern)
        subjects = sorted(set(
            os.path.basename(f).replace(".edf", "")[:8]
            for f in files
        ))
        return subjects

    def load_edf(self, filepath: str) -> Optional["mne.io.Raw"]:
        """
        加载 EDF 文件

        Args:
            filepath: EDF 文件路径

        Returns:
            MNE Raw 对象，失败返回 None
        """
        if not MNE_AVAILABLE:
            print("错误: 需要安装 mne 库 pip install mne")
            return None

        try:
            raw = mne.io.read_raw_edf(filepath, verbose=False)
            return raw
        except Exception as e:
            print(f"加载失败 {filepath}: {e}")
            return None

    def select_muse_channels(self, raw: "mne.io.Raw") -> "mne.io.Raw":
        """
        选择与 Muse S 对应的通道

        Args:
            raw: 原始 Raw 对象

        Returns:
            只包含对应通道的 Raw 对象
        """
        available = raw.info["ch_names"]
        muse_channels = []

        for muse_ch, std_ch in MUSE_CHANNEL_MAP.items():
            eeg_ch = f"EEG {std_ch}"
            if eeg_ch in available:
                muse_channels.append(eeg_ch)

        if not muse_channels:
            raise ValueError(f"找不到 Muse 通道。可用通道: {available}")

        return raw.pick_channels(muse_channels)

    def resample(self, raw: "mne.io.Raw", target_sfreq: int = None) -> "mne.io.Raw":
        """
        重采样到目标频率

        Args:
            raw: 原始 Raw 对象
            target_sfreq: 目标采样率，默认 256 Hz (Muse S)

        Returns:
            重采样后的 Raw 对象
        """
        target_sfreq = target_sfreq or self.sfreq
        current_sfreq = raw.info["sfreq"]

        if abs(current_sfreq - target_sfreq) < 1:
            return raw

        return raw.resample(target_sfreq)

    def compute_band_power(self, data: np.ndarray, sfreq: float,
                           band: Tuple[float, float],
                           method: str = "welch") -> float:
        """
        计算单个频段的功率

        Args:
            data: EEG 数据 (1D)
            sfreq: 采样率
            band: 频段范围 (low, high)
            method: 计算方法，目前只用简单积分

        Returns:
            频段功率 (μV²)
        """
        low, high = band

        from scipy import signal
        from scipy.integrate import simpson

        nperseg = min(256, len(data))
        freqs, psd = signal.welch(data, fs=sfreq, nperseg=nperseg)

        idx = np.logical_and(freqs >= low, freqs <= high)
        power = simpson(psd[idx], freqs[idx])
        return power

    def compute_features_from_raw(self, raw: "mne.io.Raw",
                                   epoch_len: float = 30.0) -> List[EEGFeatures]:
        """
        从 Raw 数据计算 EEG 特征

        Args:
            raw: MNE Raw 对象
            epoch_len: 每个 epoch 的时长（秒）

        Returns:
            EEGFeatures 列表
        """
        data = raw.get_data()
        sfreq = raw.info["sfreq"]
        n_channels = len(raw.info["ch_names"])

        features_list = []
        samples_per_epoch = int(epoch_len * sfreq)

        for start in range(0, data.shape[1] - samples_per_epoch, samples_per_epoch):
            epoch_data = data[:, start:start + samples_per_epoch]

            band_powers = {}
            for band_name, band_range in self.FREQ_BANDS.items():
                powers = []
                for ch_idx in range(n_channels):
                    power = self.compute_band_power(
                        epoch_data[ch_idx], sfreq, band_range
                    )
                    powers.append(power)
                band_powers[band_name] = float(np.mean(powers))

            delta = band_powers["delta"]
            theta = band_powers["theta"]
            alpha = band_powers["alpha"]
            beta = band_powers["beta"]
            gamma = band_powers["gamma"]

            theta_beta = theta / beta if beta > 0 else 0
            theta_alpha = theta / alpha if alpha > 0 else 0
            alpha_beta = alpha / beta if beta > 0 else 0

            features = EEGFeatures(
                delta_power=delta,
                theta_power=theta,
                alpha_power=alpha,
                beta_power=beta,
                gamma_power=gamma,
                theta_beta_ratio=theta_beta,
                theta_alpha_ratio=theta_alpha,
                alpha_beta_ratio=alpha_beta
            )
            features_list.append(features)

        return features_list

    def load_and_process(self, subject_id: int,
                         file_suffix: str = "_1",
                         epoch_len: float = 30.0) -> Optional[Dict]:
        """
        加载并处理单个被试数据

        Args:
            subject_id: 被试编号 (0-35)
            file_suffix: 文件后缀 "_1" 或 "_2"
            epoch_len: 每个 epoch 时长（秒）

        Returns:
            包含元数据和特征列表的字典
        """
        filename = f"Subject{subject_id:02d}{file_suffix}.edf"
        filepath = os.path.join(self.data_dir, filename)

        if not os.path.exists(filepath):
            print(f"文件不存在: {filepath}")
            return None

        raw = self.load_edf(filepath)
        if raw is None:
            return None

        raw = self.select_muse_channels(raw)
        raw = self.resample(raw)

        features_list = self.compute_features_from_raw(raw, epoch_len)

        return {
            "subject_id": subject_id,
            "file": filename,
            "n_epochs": len(features_list),
            "sfreq": raw.info["sfreq"],
            "channels": raw.info["ch_names"],
            "features": features_list
        }


class PhysioNetPipeline:
    """
    PhysioNet 数据集 + 认知负荷评分 pipeline
    """

    def __init__(self, data_dir: str):
        self.loader = PhysioNetLoader(data_dir)
        self.scorer = EEGScorer(simulation_mode=True)

    def process_subject(self, subject_id: int,
                        file_suffix: str = "_1") -> Optional[Dict]:
        """
        处理单个被试数据并计算认知负荷评分

        Args:
            subject_id: 被试编号
            file_suffix: "_1" 或 "_2"

        Returns:
            处理结果字典
        """
        result = self.loader.load_and_process(subject_id, file_suffix)
        if result is None:
            return None

        scores = []
        for features in result["features"]:
            score = self.scorer.score(features)
            scores.append(score)

        result["scores"] = scores
        result["mean_score"] = float(np.mean(scores))
        result["std_score"] = float(np.std(scores))

        return result

    def process_all_subjects(self, max_subjects: int = None) -> List[Dict]:
        """
        处理所有可用被试

        Args:
            max_subjects: 最大处理数量，None 表示全部

        Returns:
            所有被试的处理结果
        """
        subjects = self.loader.list_subjects()
        if max_subjects:
            subjects = subjects[:max_subjects]

        results = []
        for subject in subjects:
            try:
                subject_id = int(subject[7:9])
                result = self.process_subject(subject_id, "_1")
                if result:
                    results.append(result)
                    print(f"被试 {subject_id}: 平均负荷={result['mean_score']:.3f}")
            except Exception as e:
                print(f"处理被试 {subject} 失败: {e}")

        return results


if __name__ == "__main__":
    import sys

    data_dir = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "data", "eeg-during-mental-arithmetic-tasks-1.0.0"
    )
    data_dir = os.path.abspath(data_dir)

    if not os.path.exists(data_dir):
        print(f"数据目录不存在: {data_dir}")
        sys.exit(1)

    print(f"数据目录: {data_dir}")
    print("=" * 50)

    pipeline = PhysioNetPipeline(data_dir)

    print("处理前 3 个被试...")
    print("=" * 50)
    results = pipeline.process_all_subjects(max_subjects=3)

    print("=" * 50)
    print("汇总:")
    for r in results:
        print(f"  Subject {r['subject_id']:02d}: "
              f"平均={r['mean_score']:.3f}, "
              f"标准差={r['std_score']:.3f}, "
              f"epochs={r['n_epochs']}")
