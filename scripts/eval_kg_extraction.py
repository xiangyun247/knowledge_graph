"""
评估知识图谱构建（实体/关系抽取）的准确率、召回率、F1。

数据来源：data/eval_kg.json
每条样本包含：
- text: 原始句子
- entities: 标注实体（id, text, type）
- relations: 标注关系（subject, object, type）

评测流程：
1）使用 KnowledgeGraphBuilder.process_text(text) 得到抽取结果（不写入 Neo4j）
2）从抽取结果中解析出实体/关系集合
3）与标注结果按 (规范化名称, 类型) / (subject_name, predicate, object_name) 匹配
4）输出 overall & per-type 的 P/R/F1
"""

import json
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set
import sys

# 确保可以从项目根目录导入 kg、db、llm 等模块
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

from kg.builder import KnowledgeGraphBuilder, TextPreprocessor
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient

EVAL_DATA_PATH = ROOT_DIR / "data" / "eval_kg.json"

def load_eval_data() -> List[Dict[str, Any]]:
  with EVAL_DATA_PATH.open("r", encoding="utf-8") as f:
    return json.load(f)


def normalize_text(s: str) -> str:
  """与 builder._normalize_entity_name 保持一致的简化版，用于评测对齐。"""
  if not isinstance(s, str):
    return ""
  s = s.strip()
  # 全角转半角
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
  # 合并多余空格
  return " ".join(s.split())


def build_kg_builder() -> KnowledgeGraphBuilder:
  """
  构建一个“离线评测用”的 KnowledgeGraphBuilder。
  - Neo4jClient: 仍然需要实例化，但评测阶段我们不会关心写入是否成功
  - LLMClient: 复用现有配置，确保抽取逻辑与线上一致
  """
  neo4j_client = Neo4jClient()
  llm_client = LLMClient()
  preprocessor = TextPreprocessor()
  return KnowledgeGraphBuilder(neo4j_client, llm_client, preprocessor=preprocessor)


def collect_gold_sets(sample: Dict[str, Any]) -> Tuple[Set[Tuple[str, str]], Set[Tuple[str, str, str]]]:
  """从标注数据中构造实体/关系集合。"""
  entity_map = {}
  entities = set()
  relations = set()

  for e in sample.get("entities", []):
    e_id = e.get("id")
    name = normalize_text(e.get("text", ""))
    etype = e.get("type", "").upper()
    if not name or not etype:
      continue
    entity_map[e_id] = (name, etype)
    entities.add((name, etype))

  for r in sample.get("relations", []):
    sid = r.get("subject")
    oid = r.get("object")
    rtype = r.get("type", "").upper()
    if sid not in entity_map or oid not in entity_map or not rtype:
      continue
    s_name, _ = entity_map[sid]
    o_name, _ = entity_map[oid]
    relations.add((s_name, rtype, o_name))

  return entities, relations


def collect_pred_sets(result: Dict[str, Any]) -> Tuple[Set[Tuple[str, str]], Set[Tuple[str, str, str]]]:
  """从 KnowledgeGraphBuilder.process_text 的结果中构造实体/关系集合。"""
  entities = set()
  relations = set()

  for e in result.get("entities", []):
    name = normalize_text(e.get("name") or e.get("text") or "")
    etype = (e.get("type") or e.get("category") or "").upper()
    if not name or not etype:
      continue
    entities.add((name, etype))

  for r in result.get("relations", []):
    s = normalize_text(r.get("subject") or r.get("head") or "")
    o = normalize_text(r.get("object") or r.get("tail") or "")
    rtype = (r.get("predicate") or r.get("type") or "").upper()
    if not s or not o or not rtype:
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
  print("=== 知识图谱构建评测（实体/关系抽取） ===")

  data = load_eval_data()
  builder = build_kg_builder()

  # overall 计数
  counts = {
    "entity": Counter(tp=0, fp=0, fn=0),
    "relation": Counter(tp=0, fp=0, fn=0),
  }
  # 按类型统计（实体类型、关系类型）
  per_entity_type: Dict[str, Counter] = defaultdict(lambda: Counter(tp=0, fp=0, fn=0))
  per_relation_type: Dict[str, Counter] = defaultdict(lambda: Counter(tp=0, fp=0, fn=0))

  for sample in data:
    text = sample.get("text", "")
    if not text:
      continue

    gold_entities, gold_relations = collect_gold_sets(sample)
    result = builder.process_text(text)
    pred_entities, pred_relations = collect_pred_sets(result)

    # 实体级别
    gold_e_set = set(gold_entities)
    pred_e_set = set(pred_entities)

    tp_e = gold_e_set & pred_e_set
    fp_e = pred_e_set - gold_e_set
    fn_e = gold_e_set - pred_e_set

    counts["entity"]["tp"] += len(tp_e)
    counts["entity"]["fp"] += len(fp_e)
    counts["entity"]["fn"] += len(fn_e)

    for name, etype in tp_e:
      per_entity_type[etype]["tp"] += 1
    for name, etype in fp_e:
      per_entity_type[etype]["fp"] += 1
    for name, etype in fn_e:
      per_entity_type[etype]["fn"] += 1

    # 关系级别
    gold_r_set = set(gold_relations)
    pred_r_set = set(pred_relations)

    tp_r = gold_r_set & pred_r_set
    fp_r = pred_r_set - gold_r_set
    fn_r = gold_r_set - pred_r_set

    counts["relation"]["tp"] += len(tp_r)
    counts["relation"]["fp"] += len(fp_r)
    counts["relation"]["fn"] += len(fn_r)

    for s, rtype, o in tp_r:
      per_relation_type[rtype]["tp"] += 1
    for s, rtype, o in fp_r:
      per_relation_type[rtype]["fp"] += 1
    for s, rtype, o in fn_r:
      per_relation_type[rtype]["fn"] += 1

  # 输出 overall
  print("\n[整体指标]")
  ent_prf = compute_prf1(**counts["entity"])
  rel_prf = compute_prf1(**counts["relation"])
  print(f"实体抽取: P={ent_prf['precision']:.3f}, R={ent_prf['recall']:.3f}, F1={ent_prf['f1']:.3f}")
  print(f"关系抽取: P={rel_prf['precision']:.3f}, R={rel_prf['recall']:.3f}, F1={rel_prf['f1']:.3f}")

  # 输出 per-entity-type
  print("\n[按实体类型]")
  for etype, c in sorted(per_entity_type.items(), key=lambda x: x[0]):
    prf = compute_prf1(**c)
    print(f"{etype}: P={prf['precision']:.3f}, R={prf['recall']:.3f}, F1={prf['f1']:.3f} (tp={c['tp']}, fp={c['fp']}, fn={c['fn']})")

  # 输出 per-relation-type
  print("\n[按关系类型]")
  for rtype, c in sorted(per_relation_type.items(), key=lambda x: x[0]):
    prf = compute_prf1(**c)
    print(f"{rtype}: P={prf['precision']:.3f}, R={prf['recall']:.3f}, F1={prf['f1']:.3f} (tp={c['tp']}, fp={c['fp']}, fn={c['fn']})")


if __name__ == "__main__":
  main()

