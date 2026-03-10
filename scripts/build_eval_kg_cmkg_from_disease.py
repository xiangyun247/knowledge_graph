"""
从 CM3KG 的 Disease.csv 中构造 eval_kg_cmkg.json，用于 KG 抽取评测。

思路：
1）读取 Disease.csv，每行按逗号拆成三列：col0, col1, col2
2）解析实体：
    - "百日咳[疾病]" -> name="百日咳", type="DISEASE"
    - "干咳[症状]"   -> name="干咳", type="SYMPTOM"
3）聚合两类三元组：
    - 疾病 -> 症状：col1 == "症状" 且 col0 带 [疾病]
    - 症状 -> 可能疾病：col1 == "可能疾病" 且 col0 带 [症状] 且 col2 带 [疾病]
4）优先使用 symptom_diseases（症状 -> 疾病）构造评测样本：
    - 文本模板："XXX这一症状常见相关疾病包括d1、d2、...等。"
    - 实体：SYMPTOM + 多个 DISEASE
    - 关系：DISEASE --HAS_SYMPTOM--> SYMPTOM

输出：
    data/eval_kg_cmkg.json
"""

import csv
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_CSV = ROOT_DIR / "data" / "CM3KG" / "Disease.csv"
OUT_JSON = ROOT_DIR / "data" / "eval_kg_cmkg.json"


def parse_entity(raw: str):
  """
  从类似 "百日咳[疾病]" / "干咳[症状]" 中解析出 (name, etype)。
  仅关心 疾病/症状，其他类型返回 etype=None。
  """
  raw = (raw or "").strip()
  if "[" in raw and "]" in raw:
    name, typ = raw.split("[", 1)
    name = name.strip()
    typ = typ.split("]", 1)[0]
    if typ == "疾病":
      etype = "DISEASE"
    elif typ == "症状":
      etype = "SYMPTOM"
    else:
      etype = None
    return name, etype
  else:
    return raw.strip(), None


def build_maps():
  """
  遍历 Disease.csv，构建：
  - disease_symptoms[disease_name] = {symptom1, symptom2, ...}
  - symptom_diseases[symptom_name] = {disease1, disease2, ...}
  """
  disease_symptoms = {}
  symptom_diseases = {}

  with SRC_CSV.open("r", encoding="utf-8") as f:
    reader = csv.reader(f)
    for row in reader:
      if len(row) < 3:
        continue
      c0, c1, c2 = row[0].strip(), row[1].strip(), row[2].strip()

      # 1) 疾病 -> 症状
      if c1 == "症状":
        dis_name, dis_type = parse_entity(c0)
        sym_name, sym_type = parse_entity(c2)
        # 这里 c2 通常是纯文本症状（不带 [症状]），因此 sym_type 可能为 None，我们只用 name 即可
        if dis_type == "DISEASE" and sym_name:
          disease_symptoms.setdefault(dis_name, set()).add(sym_name)

      # 2) 症状 -> 可能疾病
      if c1 == "可能疾病":
        sym_name, sym_type = parse_entity(c0)
        dis_name, dis_type = parse_entity(c2)
        if sym_type == "SYMPTOM" and dis_type == "DISEASE":
          symptom_diseases.setdefault(sym_name, set()).add(dis_name)

  return disease_symptoms, symptom_diseases


def main():
  print("=== 从 Disease.csv 构造 eval_kg_cmkg.json ===")
  if not SRC_CSV.exists():
    raise FileNotFoundError(f"找不到数据文件: {SRC_CSV}")

  disease_symptoms, symptom_diseases = build_maps()
  print(f"聚合得到 symptom_diseases 条目数: {len(symptom_diseases)}")

  samples = []
  sid = 1

  # 只从 symptom_diseases 中抽取前若干个症状构造评测样本
  MAX_SAMPLES = 100

  for symptom, diseases in symptom_diseases.items():
    if not diseases:
      continue

    ents = []
    rels = []

    ents.append({"id": "e1", "text": symptom, "type": "SYMPTOM"})
    eid = 2

    dids = sorted(diseases)
    for d in dids:
      ed = f"e{eid}"; eid += 1
      ents.append({"id": ed, "text": d, "type": "DISEASE"})
      # 统一视为 DISEASE --HAS_SYMPTOM--> SYMPTOM
      rels.append({"subject": ed, "object": "e1", "type": "HAS_SYMPTOM"})

    # 简单文本模板
    disease_str = "、".join(dids[:5])  # 太多的话截断一下
    text = f"{symptom}这一症状常见相关疾病包括{disease_str}等。"

    samples.append({
      "id": f"cmkg_{sid:03d}",
      "text": text,
      "entities": ents,
      "relations": rels
    })
    sid += 1

    if len(samples) >= MAX_SAMPLES:
      break

  OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
  with OUT_JSON.open("w", encoding="utf-8") as f:
    json.dump(samples, f, ensure_ascii=False, indent=2)

  print(f"已生成 {len(samples)} 条评测样本 -> {OUT_JSON}")


if __name__ == "__main__":
  main()

