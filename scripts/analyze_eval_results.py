"""
对 eval_qa_results.json 进行统计分析。

功能：
- 计算各系统（llm_only / graph_rag / doc_rag / hybrid_rag）的平均得分
- 按 category 分组计算每个系统的平均得分
- 支持选择使用 "score" 或 "llm_score" 字段（若存在）
- 将分析结果写入 data/eval_qa_summary.json，便于前端或 Notebook 可视化
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any
import sys

# 保证可以导入项目根目录模块（如果后续需要）
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

RESULT_PATH = ROOT_DIR / "data" / "eval_qa_results.json"
SUMMARY_PATH = ROOT_DIR / "data" / "eval_qa_summary.json"


def load_results() -> list[Dict[str, Any]]:
  with RESULT_PATH.open("r", encoding="utf-8") as f:
    return json.load(f)


def analyze(metric_field: str = "score") -> Dict[str, Any]:
  """
  metric_field: "score" 或 "llm_score"
  """
  data = load_results()

  systems = set(r["system"] for r in data)
  categories = set(r["category"] for r in data)

  # overall 按系统
  system_scores: Dict[str, list[float]] = {s: [] for s in systems}

  # 按 category & system
  by_cat: Dict[str, Dict[str, list[float]]] = {
    cat: {s: [] for s in systems} for cat in categories
  }

  for r in data:
    system = r["system"]
    category = r["category"]
    score = r.get(metric_field)
    # 如果没有该字段（比如还没跑 LLM 评分），跳过
    if score is None:
      continue
    try:
      s_val = float(score)
    except (TypeError, ValueError):
      continue

    system_scores[system].append(s_val)
    by_cat[category][system].append(s_val)

  def avg(lst: list[float]) -> float:
    return sum(lst) / len(lst) if lst else 0.0

  summary: Dict[str, Any] = {
    "metric": metric_field,
    "overall": {},
    "by_category": {},
  }

  for s in sorted(systems):
    summary["overall"][s] = {
      "avg": avg(system_scores[s]),
      "n": len(system_scores[s]),
    }

  for cat in sorted(categories):
    summary["by_category"][cat] = {}
    for s in sorted(systems):
      scores = by_cat[cat][s]
      summary["by_category"][cat][s] = {
        "avg": avg(scores),
        "n": len(scores),
      }

  return summary


def main() -> None:
  print("=== 问答评测结果分析 ===")

  # 支持命令行参数：python scripts/analyze_eval_results.py llm_score
  metric = "score"
  if len(sys.argv) >= 2:
    metric = sys.argv[1].strip()
    if metric not in ("score", "llm_score"):
      print(f"未知评分字段 {metric}，仅支持 'score' 或 'llm_score'，将回退为 'score'")
      metric = "score"

  summary = analyze(metric_field=metric)

  label = "rule-based score" if metric == "score" else "LLM score"

  print(f"\n[整体平均得分（{label}）]")
  for system, info in summary["overall"].items():
    print(f"{system}: avg={info['avg']:.3f}, n={info['n']}")

  print(f"\n[按类别分组平均得分（{label}）]")
  for cat, sys_info in summary["by_category"].items():
    print(f"\nCategory = {cat}")
    for system, info in sys_info.items():
      print(f"  {system}: avg={info['avg']:.3f}, n={info['n']}")

  # 写入 summary JSON，供前端 / Notebook 使用
  SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
  with SUMMARY_PATH.open("w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

  print(f"\n分析结果已写入: {SUMMARY_PATH}")


if __name__ == "__main__":
  main()

