import requests
import json

url = 'http://localhost:8000/api/cognitive-load/assess?save=false'
data = {
    'user_id': 'test_user',
    'task_id': 'task_001',
    'source': 'patient_education',
    'nasa_tlx_answers': {
        'mental_demand': 5,
        'physical_demand': 2,
        'temporal_demand': 3,
        'performance': 4,
        'effort': 4,
        'frustration': 2
    },
    'behavior_events': [
        {'event_type': 'task_start', 'ts': 1000000},
        {'event_type': 'click', 'ts': 1100000},
        {'event_type': 'back', 'ts': 1200000},
        {'event_type': 'task_end', 'ts': 2000000}
    ]
}

print('Testing /api/cognitive-load/assess endpoint...')
response = requests.post(url, json=data)
print(f'Status: {response.status_code}')

if response.status_code == 200:
    result = response.json()
    print('\n=== Assessment Result ===')
    print(f"综合评分: {result['final_score']:.4f}")
    print(f"负荷等级: {result['level']}")
    print(f"问卷评分: {result['questionnaire_score']:.4f}")
    print(f"行为评分: {result['behavior_score']:.4f}")
    modalities = ', '.join(result['available_modalities'])
    print(f"可用模态: {modalities}")
    print(f"融合方法: {result['fusion_method']}")
else:
    print(f'Error: {response.text}')
