# test_patient_education.py
import json
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.agent.patient_education import generate_patient_education
from backend.agent.context import set_agent_user_id


def main():
    # 模拟一个用户 id（用于文档/图谱权限过滤）
    set_agent_user_id("test-user")

    topic = "急性胰腺炎出院后注意事项"
    result = generate_patient_education(topic=topic)

    print("=== 原始结构化结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("error"):
        print("\n[失败] 患者教育生成出错：", result["error"])
        return

    print("\n=== 简要检查 ===")
    print("标题:", result.get("title"))
    print("小节数:", len(result.get("sections") or []))
    print("是否有 summary:", bool(result.get("summary")))


if __name__ == "__main__":
    main()