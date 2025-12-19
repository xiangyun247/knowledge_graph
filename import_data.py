import requests
import json

BASE_URL = "http://localhost:5001"


def import_sample_data():
    """导入示例数据"""
    print("开始导入示例数据...")

    # 示例医疗数据
    sample_data = {
        "entities": [
            {
                "name": "急性胰腺炎",
                "type": "Disease",
                "properties": {
                    "description": "胰腺组织的急性炎症反应",
                    "severity": "严重"
                }
            },
            {
                "name": "腹痛",
                "type": "Symptom",
                "properties": {
                    "description": "腹部疼痛，常为持续性剧烈疼痛"
                }
            },
            {
                "name": "恶心呕吐",
                "type": "Symptom",
                "properties": {
                    "description": "恶心和呕吐症状"
                }
            },
            {
                "name": "发热",
                "type": "Symptom",
                "properties": {
                    "description": "体温升高"
                }
            }
        ],
        "relationships": [
            {
                "source": "急性胰腺炎",
                "target": "腹痛",
                "type": "HAS_SYMPTOM"
            },
            {
                "source": "急性胰腺炎",
                "target": "恶心呕吐",
                "type": "HAS_SYMPTOM"
            },
            {
                "source": "急性胰腺炎",
                "target": "发热",
                "type": "HAS_SYMPTOM"
            }
        ]
    }

    # 检查是否有导入接口
    response = requests.post(
        f"{BASE_URL}/api/import",
        json=sample_data
    )

    if response.status_code == 200:
        print("✅ 数据导入成功！")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ 数据导入失败: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    import_sample_data()
