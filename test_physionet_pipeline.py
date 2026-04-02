#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '.')
os.environ['JWT_SECRET'] = 'test-secret-key-for-testing-only-min-32chars'

from backend.cognitive.modalities.physionet_loader import PhysioNetPipeline

data_dir = r'c:\Users\23035\PycharmProjects\knowledge_gragh\data\eeg-during-mental-arithmetic-tasks-1.0.0'
pipeline = PhysioNetPipeline(data_dir)

print('处理 Subject01...')
result = pipeline.process_subject(1, '_1')
if result:
    print('  通道:', result['channels'])
    print('  采样率:', result['sfreq'], 'Hz')
    print('  Epochs:', result['n_epochs'])
    print('  平均认知负荷评分: {:.4f}'.format(result['mean_score']))
    print('  评分范围: {:.4f} - {:.4f}'.format(min(result['scores']), max(result['scores'])))
