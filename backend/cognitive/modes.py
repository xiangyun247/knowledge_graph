# -*- coding: utf-8 -*-
"""
EEG 运行模式配置

用于管理模拟器模式和真实硬件模式之间的切换
"""

from enum import Enum


class EEGMode(str, Enum):
    """EEG 运行模式"""
    SIMULATION = "simulation"
    HARDWARE = "hardware"


CURRENT_MODE: EEGMode = EEGMode.SIMULATION


MUSE_CONFIG = {
    "collect_duration_sec": 30.0,
    "baseline_duration_sec": 60.0,
    "sampling_rate": 256,
    "connection_timeout": 10.0,
    "channels": ["TP9", "AF7", "AF8", "TP10"]
}


def get_current_mode() -> EEGMode:
    """获取当前 EEG 运行模式"""
    return CURRENT_MODE


def set_mode(mode: EEGMode) -> None:
    """设置 EEG 运行模式"""
    global CURRENT_MODE
    CURRENT_MODE = mode


def is_hardware_mode() -> bool:
    """检查是否处于硬件模式"""
    return CURRENT_MODE == EEGMode.HARDWARE


def is_simulation_mode() -> bool:
    """检查是否处于模拟器模式"""
    return CURRENT_MODE == EEGMode.SIMULATION
