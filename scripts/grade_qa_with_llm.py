"""
使用 LLM 对问答结果进行自动打分（0 / 0.5 / 1）。

数据来源：
- data/eval_qa_results.json （由 eval_qa_systems.py 生成）

作用：
- 对每条 (question, gold_answer, system_answer) 调用 DeepSeek LLM
- 按 0 / 0.5 / 1 三档给出评分，并写入字段：
  - llm_score
  - llm_reason（简要评分理由，便于人工抽查）

注意：
- 本脚本会覆盖写回 data/eval_qa_results.json，给每个记录新增字段；
- 运行前请确保 .env 中的 DEEPSEEK_API_KEY 已配置。
"""

import json
from pathlib import Path
from typing import Dict, Any
import sys
import re

# 保证可以导入项目根目录模块
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: F401  # 触发 .env 加载与日志配置
from llm.client import LLMClient  # noqa: E402


RESULT_PATH = ROOT_DIR / "data" / "eval_qa_results.json"


def load_results() -> list[Dict[str, Any]]:
  with RESULT_PATH.open("r", encoding="utf-8") as f:
    return json.load(f)


def build_grading_prompt(item: Dict[str, Any]) -> str:
  """构造给 LLM 的评分提示词。"""
  q = item["question"]
  gold = item["gold_answer"]
  ans = item["answer"]
  system = item["system"]

  return f"""
你是一名医学教育评阅老师，现在需要对一个问答系统的回答进行打分。

请根据下面的信息，给出 0 / 0.5 / 1 三档评分：
- 0 分：回答明显错误、严重偏离医学共识，或者基本没有提供有效信息。
- 0.5 分：回答部分正确，包含了部分关键医学要点，但不完整或有一定表述问题。
- 1 分：回答整体正确、覆盖了题目中的关键要点，表述清晰、专业，允许有一定措辞差异。

请务必从“医学内容是否符合 gold answer 提供的要点”来判断，而不是只看文字相似度。

【题目】
{q}

【参考标准答案（gold answer）】
{gold}

【系统类型】
{system}

【系统实际回答】
{ans}

请你返回一个 JSON，格式严格如下（不要添加多余字段）：
{{
  "score": 0 或 0.5 或 1,
  "reason": "简要说明打这个分数的原因"
}}
"""


def parse_llm_json(text: str) -> Dict[str, Any]:
  """
  从 LLM 返回的文本中提取 JSON。
  尽量鲁棒地匹配第一个 {...} 段落。
  """
  match = re.search(r"\{.*\}", text, re.DOTALL)
  if not match:
    raise ValueError("未找到 JSON 片段")
  obj = json.loads(match.group())

  score_raw = obj.get("score")
  if isinstance(score_raw, str):
    # 支持 "0.5" / "1" / "0"
    score = float(score_raw)
  else:
    score = float(score_raw)

  # 归一化为 0 / 0.5 / 1
  if score <= 0.25:
    score = 0.0
  elif score <= 0.75:
    score = 0.5
  else:
    score = 1.0

  reason = obj.get("reason") or ""
  return {"score": score, "reason": reason}


def main() -> None:
  print("=== 使用 LLM 对问答结果打分（0 / 0.5 / 1） ===")

  data = load_results()
  llm = LLMClient()

  updated = 0
  skipped = 0

  for i, item in enumerate(data):
    # 如果已经有 llm_score，并且你不想覆盖，可以在此跳过
    # 这里选择“若存在则跳过”，避免重复计费；如需重评，可以手动删字段或改逻辑
    if "llm_score" in item:
      skipped += 1
      continue

    prompt = build_grading_prompt(item)
    messages = [
      {
        "role": "system",
        "content": "你是严格但公平的医学教育评阅老师，请根据 gold answer 评价系统回答质量。"
      },
      {
        "role": "user",
        "content": prompt
      },
    ]

    try:
      resp = llm.chat(messages, temperature=0.0)
      parsed = parse_llm_json(resp)
      item["llm_score"] = parsed["score"]
      item["llm_reason"] = parsed["reason"]
      updated += 1
      print(f"[{i+1}/{len(data)}] 打分成功: id={item['id']}, system={item['system']}, llm_score={parsed['score']}")
    except Exception as e:
      print(f"[{i+1}/{len(data)}] 打分失败: id={item['id']}, system={item['system']}, error={e}")
      # 打分失败时，不设置 llm_score，后续分析时会自动跳过
      continue

  # 写回结果
  with RESULT_PATH.open("w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

  print(f"\nLLM 评分完成，共更新 {updated} 条记录，跳过已有评分 {skipped} 条。")
  print(f"结果已写回: {RESULT_PATH}")


if __name__ == "__main__":
  main()

