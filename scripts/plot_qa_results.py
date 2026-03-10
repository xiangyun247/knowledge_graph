"""
基于 eval_qa_summary.json 做可视化分析（Python 脚本版）。

前置步骤：
1）运行规则评分统计：
    python scripts/analyze_eval_results.py score
2）或运行 LLM 评分统计：
    python scripts/analyze_eval_results.py llm_score

本脚本会读取 data/eval_qa_summary.json，生成：
- 整体平均得分柱状图（按 system）
- 按类别的分组柱状图（category × system）

依赖：
- matplotlib（已在大多数科学环境中预装，如无可 pip install matplotlib）
"""

import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt


ROOT_DIR = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT_DIR / "data" / "eval_qa_summary.json"


def load_summary() -> dict:
  if not SUMMARY_PATH.exists():
    raise FileNotFoundError(
      f"未找到 {SUMMARY_PATH}，请先运行：\n"
      "  python scripts/analyze_eval_results.py score\n"
      "或：\n"
      "  python scripts/analyze_eval_results.py llm_score\n"
    )
  with SUMMARY_PATH.open("r", encoding="utf-8") as f:
    return json.load(f)


def plot_overall(summary: dict) -> None:
  metric = summary.get("metric", "score")
  overall = summary["overall"]

  systems = sorted(overall.keys())
  avgs = [overall[s]["avg"] for s in systems]

  plt.figure(figsize=(6, 4))
  bars = plt.bar(systems, avgs, color=["#5B8FF9", "#5AD8A6", "#5D7092", "#F6BD16"])

  for bar, val in zip(bars, avgs):
    plt.text(
      bar.get_x() + bar.get_width() / 2,
      val + 0.01,
      f"{val:.2f}",
      ha="center",
      va="bottom",
      fontsize=9,
    )

  plt.ylim(0, 1.05)
  label = "rule-based score" if metric == "score" else "LLM score"
  plt.title(f"Overall average score ({label})")
  plt.ylabel("Average score (0–1)")
  plt.xlabel("System")
  plt.tight_layout()
  plt.show()


def plot_by_category(summary: dict) -> None:
  metric = summary.get("metric", "score")
  by_cat = summary["by_category"]

  categories = sorted(by_cat.keys())
  systems = sorted(next(iter(by_cat.values())).keys())

  # 每个类别一组，多系统分组条形
  x = range(len(categories))
  total_width = 0.8
  n_sys = len(systems)
  bar_width = total_width / max(n_sys, 1)

  plt.figure(figsize=(10, 5))

  for idx, system in enumerate(systems):
    offsets = [i - total_width / 2 + idx * bar_width + bar_width / 2 for i in x]
    avgs = [by_cat[cat][system]["avg"] for cat in categories]
    plt.bar(offsets, avgs, width=bar_width, label=system)

  plt.xticks(list(x), categories, rotation=45, ha="right")
  plt.ylim(0, 1.05)
  label = "rule-based score" if metric == "score" else "LLM score"
  plt.title(f"Average score by category ({label})")
  plt.ylabel("Average score (0–1)")
  plt.xlabel("Category")
  plt.legend(title="System")
  plt.tight_layout()
  plt.show()


def main() -> None:
  print("=== 问答评测结果可视化（plot_qa_results.py）===")
  summary = load_summary()
  metric = summary.get("metric", "score")
  print(f"当前使用评分字段: {metric}")

  plot_overall(summary)
  plot_by_category(summary)


if __name__ == "__main__":
  main()

