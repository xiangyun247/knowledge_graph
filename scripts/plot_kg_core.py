"""
对知识图谱构建「主干类型」评测结果做可视化。

核心类型定义与 scripts/analyze_kg_core.py 一致：
- 实体：DISEASE, SYMPTOM, COMPLICATION, TREATMENT, EXAMINATION, LAB_RESULT, PROGNOSIS
- 关系：HAS_SYMPTOM, HAS_COMPLICATION, HAS_TREATMENT, HAS_EXAMINATION,
        HAS_LAB_ABNORMALITY, HAS_PROGNOSIS

脚本会重新调用 KnowledgeGraphBuilder.process_text，对 eval_kg.json 重算一遍
主干类型的实体/关系 TP/FP/FN，然后画两张柱状图：
- 按实体类型的 F1
- 按关系类型的 F1
"""

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple
import sys

import matplotlib.pyplot as plt

# 确保可以从项目根目录导入模块
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

from kg.builder import KnowledgeGraphBuilder, TextPreprocessor  # noqa: E402
from db.neo4j_client import Neo4jClient  # noqa: E402
from llm.client import LLMClient  # noqa: E402


EVAL_DATA_PATH = ROOT_DIR / "data" / "eval_kg.json"

CORE_ENTITY_TYPES = {
  "DISEASE",
  "SYMPTOM",
  "COMPLICATION",
  "TREATMENT",
  "EXAMINATION",
  "LAB_RESULT",
  "PROGNOSIS",
}

CORE_RELATION_TYPES = {
  "HAS_SYMPTOM",
  "HAS_COMPLICATION",
  "HAS_TREATMENT",
  "HAS_EXAMINATION",
  "HAS_LAB_ABNORMALITY",
  "HAS_PROGNOSIS",
}


def load_eval_data() -> List[Dict[str, Any]]:
  with EVAL_DATA_PATH.open("r", encoding="utf-8") as f:
    return json.load(f)


def normalize_text(s: str) -> str:
  if not isinstance(s, str):
    return ""
  s = s.strip()
  out = []
  for c in s:
    if c == "\u3000":
      out.append(" ")
    elif "\uff01" <= c <= "\uff5e":
      out.append(chr(ord(c) - 0xfee0))
    elif "\uff10" <= c <= "\uff19":
      out.append(chr(ord(c) - 0xfee0))
    else:
      out.append(c)
  s = "".join(out)
  return " ".join(s.split())


def build_kg_builder() -> KnowledgeGraphBuilder:
  neo4j_client = Neo4jClient()
  llm_client = LLMClient()
  preprocessor = TextPreprocessor()
  return KnowledgeGraphBuilder(neo4j_client, llm_client, preprocessor=preprocessor)


def collect_gold_sets(sample: Dict[str, Any]) -> Tuple[set[Tuple[str, str]], set[Tuple[str, str, str]]]:
  entity_map: Dict[str, Tuple[str, str]] = {}
  entities: set[Tuple[str, str]] = set()
  relations: set[Tuple[str, str, str]] = set()

  for e in sample.get("entities", []):
    e_id = e.get("id")
    name = normalize_text(e.get("text", ""))
    etype = (e.get("type") or "").upper()
    if not name or not etype or etype not in CORE_ENTITY_TYPES:
      continue
    entity_map[e_id] = (name, etype)
    entities.add((name, etype))

  for r in sample.get("relations", []):
    sid = r.get("subject")
    oid = r.get("object")
    rtype = (r.get("type") or "").upper()
    if rtype not in CORE_RELATION_TYPES:
      continue
    if sid not in entity_map or oid not in entity_map:
      continue
    s_name, _ = entity_map[sid]
    o_name, _ = entity_map[oid]
    relations.add((s_name, rtype, o_name))

  return entities, relations


def collect_pred_sets(result: Dict[str, Any]) -> Tuple[set[Tuple[str, str]], set[Tuple[str, str, str]]]:
  entities: set[Tuple[str, str]] = set()
  relations: set[Tuple[str, str, str]] = set()

  for e in result.get("entities", []):
    name = normalize_text(e.get("name") or e.get("text") or "")
    etype = (e.get("type") or e.get("category") or "").upper()
    if not name or not etype or etype not in CORE_ENTITY_TYPES:
      continue
    entities.add((name, etype))

  for r in result.get("relations", []):
    s = normalize_text(r.get("subject") or r.get("head") or "")
    o = normalize_text(r.get("object") or r.get("tail") or "")
    rtype = (r.get("predicate") or r.get("type") or "").upper()
    if not s or not o or not rtype or rtype not in CORE_RELATION_TYPES:
      continue
    relations.add((s, rtype, o))

  return entities, relations


def compute_prf1(tp: int, fp: int, fn: int) -> Dict[str, float]:
  p = tp / (tp + fp) if tp + fp > 0 else 0.0
  r = tp / (tp + fn) if tp + fn > 0 else 0.0
  if p + r == 0:
    f1 = 0.0
  else:
    f1 = 2 * p * r / (p + r)
  return {"precision": p, "recall": r, "f1": f1}


def main() -> None:
  print("=== KG 主干类型评测可视化（plot_kg_core.py）===")
  data = load_eval_data()
  builder = build_kg_builder()

  per_entity_type: Dict[str, Counter] = defaultdict(lambda: Counter(tp=0, fp=0, fn=0))
  per_relation_type: Dict[str, Counter] = defaultdict(lambda: Counter(tp=0, fp=0, fn=0))

  for sample in data:
    text = sample.get("text", "")
    if not text:
      continue
    gold_e, gold_r = collect_gold_sets(sample)
    result = builder.process_text(text)
    pred_e, pred_r = collect_pred_sets(result)

    # 实体
    tp_e = gold_e & pred_e
    fp_e = pred_e - gold_e
    fn_e = gold_e - pred_e
    for _, etype in tp_e:
      per_entity_type[etype]["tp"] += 1
    for _, etype in fp_e:
      per_entity_type[etype]["fp"] += 1
    for _, etype in fn_e:
      per_entity_type[etype]["fn"] += 1

    # 关系
    tp_r = gold_r & pred_r
    fp_r = pred_r - gold_r
    fn_r = gold_r - pred_r
    for _, rtype, _ in tp_r:
      per_relation_type[rtype]["tp"] += 1
    for _, rtype, _ in fp_r:
      per_relation_type[rtype]["fp"] += 1
    for _, rtype, _ in fn_r:
      per_relation_type[rtype]["fn"] += 1

  # -------- 图 1：按实体类型的 F1 --------
  etypes = sorted(CORE_ENTITY_TYPES)
  e_f1 = []
  for et in etypes:
    c = per_entity_type.get(et, Counter(tp=0, fp=0, fn=0))
    prf = compute_prf1(**c)
    e_f1.append(prf["f1"])

  plt.figure(figsize=(8, 4))
  bars = plt.bar(etypes, e_f1, color="#5B8FF9")
  for bar, val in zip(bars, e_f1):
    plt.text(
      bar.get_x() + bar.get_width() / 2,
      val + 0.01,
      f"{val:.2f}",
      ha="center",
      va="bottom",
      fontsize=9,
    )
  plt.ylim(0, 1.05)
  plt.title("F1 by core entity type")
  plt.ylabel("F1 (0–1)")
  plt.xlabel("Entity type")
  plt.tight_layout()
  plt.show()

  # -------- 图 2：按关系类型的 F1 --------
  rtypes = sorted(CORE_RELATION_TYPES)
  r_f1 = []
  for rt in rtypes:
    c = per_relation_type.get(rt, Counter(tp=0, fp=0, fn=0))
    prf = compute_prf1(**c)
    r_f1.append(prf["f1"])

  plt.figure(figsize=(8, 4))
  bars = plt.bar(rtypes, r_f1, color="#5AD8A6")
  for bar, val in zip(bars, r_f1):
    plt.text(
      bar.get_x() + bar.get_width() / 2,
      val + 0.01,
      f"{val:.2f}",
      ha="center",
      va="bottom",
      fontsize=9,
    )
  plt.ylim(0, 1.05)
  plt.title("F1 by core relation type")
  plt.ylabel("F1 (0–1)")
  plt.xlabel("Relation type")
  plt.xticks(rotation=30, ha="right")
  plt.tight_layout()
  plt.show()


if __name__ == "__main__":
  main()

