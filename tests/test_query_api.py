"""
测试智能问答接口
"""
import sys
import requests
from pathlib import Path

BACKEND_URL = "http://localhost:5001"

def test_query_api():
    """测试智能问答接口"""
    print("=" * 60)
    print("测试智能问答接口")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        {
            "name": "症状查询",
            "question": "急性胰腺炎有什么症状？",
            "use_graph": True,
            "top_k": 5
        },
        {
            "name": "治疗查询",
            "question": "急性胰腺炎如何治疗？",
            "use_graph": True,
            "top_k": 5
        },
        {
            "name": "科室查询",
            "question": "急性胰腺炎看什么科？",
            "use_graph": True,
            "top_k": 5
        },
        {
            "name": "病因查询",
            "question": "上腹部疼痛可能是什么病？",
            "use_graph": True,
            "top_k": 5
        }
    ]
    
    results = {"passed": 0, "failed": 0, "total": len(test_cases)}
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}] 测试: {test_case['name']}")
        print(f"   问题: {test_case['question']}")
        
        try:
            response = requests.post(
                f"{BACKEND_URL}/api/query",
                json=test_case,
                timeout=30  # 问答可能需要更长时间
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                sources = data.get('sources', [])
                confidence = data.get('confidence', 0)
                
                print(f"   [OK] 回答成功")
                print(f"   答案长度: {len(answer)} 字符")
                print(f"   来源数: {len(sources)}")
                print(f"   置信度: {confidence}")
                if answer:
                    print(f"   答案预览: {answer[:100]}...")
                results["passed"] += 1
            else:
                print(f"   [FAIL] 状态码: {response.status_code}")
                print(f"   响应: {response.text[:200]}")
                results["failed"] += 1
                
        except Exception as e:
            print(f"   [ERROR] {e}")
            results["failed"] += 1
    
    print("\n" + "=" * 60)
    print(f"测试完成: {results['passed']}/{results['total']} 通过")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    test_query_api()

