#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '.')
os.environ['JWT_SECRET'] = 'test-secret-key-for-testing-only-min-32chars'

from backend.cognitive.modalities.physionet_loader import PhysioNetPipeline
import numpy as np

data_dir = r'c:\Users\23035\PycharmProjects\knowledge_gragh\data\eeg-during-mental-arithmetic-tasks-1.0.0'
pipeline = PhysioNetPipeline(data_dir)

print('处理所有 36 个被试...')
print('=' * 60)

all_scores = []
for subject_id in range(36):
    result = pipeline.process_subject(subject_id, '_1')
    if result:
        all_scores.append(result['mean_score'])
        status = 'LOW' if result['mean_score'] < 0.35 else 'MED' if result['mean_score'] < 0.55 else 'HIGH'
        print('Subject {:02d}: score={:.4f} [{}]'.format(
            subject_id, result['mean_score'], status))

print('=' * 60)
print('汇总统计:')
print('  被试数: {}'.format(len(all_scores)))
print('  平均负荷: {:.4f}'.format(np.mean(all_scores)))
print('  标准差: {:.4f}'.format(np.std(all_scores)))
print('  最低: {:.4f} (Subject {:02d})'.format(
    min(all_scores), all_scores.index(min(all_scores))))
print('  最高: {:.4f} (Subject {:02d})'.format(
    max(all_scores), all_scores.index(max(all_scores))))

low_count = sum(1 for s in all_scores if s < 0.35)
med_count = sum(1 for s in all_scores if 0.35 <= s < 0.55)
high_count = sum(1 for s in all_scores if s >= 0.55)
print()
print('负荷分布:')
print('  低 (0-0.35): {} 人 ({:.1f}%)'.format(low_count, low_count/len(all_scores)*100))
print('  中 (0.35-0.55): {} 人 ({:.1f}%)'.format(med_count, med_count/len(all_scores)*100))
print('  高 (0.55+): {} 人 ({:.1f}%)'.format(high_count, high_count/len(all_scores)*100))
