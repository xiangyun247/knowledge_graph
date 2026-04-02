#!/usr/bin/env python3
import os, sys
os.environ['JWT_SECRET'] = 'test-secret-key-for-testing-only-min-32chars'
sys.path.insert(0, '.')

# 测试 numpy 导入
from backend.cognitive.modalities.eeg_scorer import EEGScorer, EEGScorer_instance
print('EEGScorer 导入成功')

# 测试模拟器模式
scorer = EEGScorer(simulation_mode=True)
from backend.cognitive.schemas.cognitive_load import EEGFeatures
features = EEGFeatures(delta_power=15, theta_power=10, alpha_power=8, beta_power=5, gamma_power=3, theta_beta_ratio=2.0, theta_alpha_ratio=1.25, alpha_beta_ratio=1.6)
score = scorer.score(features)
print('评分:', score)

# 测试模式切换方法存在
print('enable_simulation 方法存在:', hasattr(scorer, 'enable_simulation'))
print('disable_simulation 方法存在:', hasattr(scorer, 'disable_simulation'))
