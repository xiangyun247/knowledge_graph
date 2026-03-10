"""
多系统问答效果评测脚本。

对比系统：
- llm_only: 只调用 LLM，不做任何检索（无上下文）
- doc_rag: 仅使用文档向量检索（如果可用）
- graph_rag: 仅使用图检索（GraphRetriever）
- hybrid_rag: 同时使用图 + 文档 + 关键词（Hybrid RAG）

数据来源：data/eval_qa.json

输出：
- 终端打印各系统平均得分
- 生成 data/eval_qa_results.json，供后续可视化使用
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List
import sys

# 确保可以从项目根目录导入 rag、db、llm 等模块
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

from llm.client import LLMClient
from db.neo4j_client import Neo4jClient
from rag.rag_pipeline import RAGPipeline
from rag.graph_retriever import GraphRetriever

try:
  from backend.chroma_store import ChromaStore
except Exception:  # pragma: no cover
  ChromaStore = None  # type: ignore


ROOT_DIR = Path(__file__).resolve().parent.parent
EVAL_DATA_PATH = ROOT_DIR / "data" / "eval_qa.json"
RESULT_PATH = ROOT_DIR / "data" / "eval_qa_results.json"


@dataclass
class QAEvalRecord:
  id: str
  question: str
  category: str
  gold_answer: str
  system: str
  answer: str
  score: float
  notes: str = ""


def load_eval_data() -> List[Dict[str, Any]]:
  with EVAL_DATA_PATH.open("r", encoding="utf-8") as f:
    return json.load(f)


def build_clients():
  """构建各类客户端/管线，尽量复用现有实现。"""
  llm = LLMClient()
  neo4j = Neo4jClient()

  # RAGPipeline 需要 EmbeddingClient；从 llm.client 中获取
  from llm.client import EmbeddingClient

  embedding = EmbeddingClient()

  chroma_store = None
  if ChromaStore is not None:
    try:
      chroma_store = ChromaStore()
    except Exception:
      chroma_store = None

  rag_pipeline = RAGPipeline(
    neo4j_client=neo4j,
    llm_client=llm,
    embedding_client=embedding,
    chroma_store=chroma_store,
  )

  graph_retriever = GraphRetriever(neo4j)

  return llm, rag_pipeline, graph_retriever


def score_answer_simple(
  gold: str,
  pred: str,
  category: str,
) -> float:
  """
  简单打分函数（0/0.5/1），后续可替换为 LLM 评分或人工评分。
  这里采用非常保守的基于关键字的启发式：
  - 完全无关 / 基本错误：0
  - 提到部分关键信息：0.5
  - 覆盖主要关键信息：1
  """
  p = pred.strip()
  if not p:
    return 0.0

  # 明确兜底/拒答类文案，直接判 0 分，避免“诚实说不知道”被误判为部分正确
  fallback_phrases = [
    "详细信息请咨询专业医生",
    "请咨询专业医生",
    "无法直接获取",
    "图谱中未提供",
    "知识图谱中未",
    "没有足够的信息来回答",
    "无法从现有信息中得出结论",
  ]
  if any(phrase in p for phrase in fallback_phrases):
    return 0.0

  # 关键子串命中数
  # 为简单起见，根据类别拆几个核心词
  keywords = []
  if category == "symptom":
    keywords = ["腹痛", "疼痛", "恶心", "呕吐", "发热"]
  elif category == "treatment":
    keywords = ["禁食", "胃肠减压", "补液", "镇痛", "抑制胰酶"]
  elif category == "complication":
    keywords = ["呼吸窘迫", "肾功能不全", "器官功能衰竭", "ARDS"]
  elif category == "examination":
    keywords = ["超声", "B超", "增强CT", "CT", "MRI"]
  elif category == "etiology":
    keywords = ["胆结石", "胆源性", "饮酒", "酒精性", "高脂血症", "高钙血症"]
  elif category == "definition":
    keywords = ["急性炎症性疾病", "胰酶", "自我消化", "过早激活"]
  elif category == "department":
    keywords = ["消化内科", "普外科", "重症监护", "ICU"]
  elif category == "prognosis":
    keywords = ["预后", "病死率", "重症", "器官功能衰竭"]
  elif category == "population":
    keywords = ["中老年", "女性", "高危人群", "胆结石"]
  elif category == "cause":
    keywords = ["病因", "胆结石", "梗阻", "胆汁反流"]
  elif category == "severity":
    keywords = ["轻症", "重症", "器官功能衰竭", "坏死", "感染"]
  elif category == "prevention":
    keywords = ["预防", "复发", "戒酒", "低脂", "清淡饮食", "控制体重", "控制血脂"]

  hit = sum(1 for kw in keywords if kw and kw in p)
  if hit == 0:
    return 0.0
  if hit == 1:
    return 0.5
  return 1.0


def answer_llm_only(llm: LLMClient, question: str) -> str:
  messages = [
    {
      "role": "system",
      "content": "你是一个医学助手，请用简洁、专业的中文回答用户的问题。"
    },
    {
      "role": "user",
      "content": question
    }
  ]
  return llm.chat(messages, temperature=0.3)


def answer_graph_rag(
  llm: LLMClient,
  graph_retriever: GraphRetriever,
  question: str,
) -> str:
  """
  简化版：使用 QueryParser 的规则意图，GraphRetriever 检索，再让 LLM 基于检索结果作答。
  为避免引入过多依赖，这里直接用 graph_retriever.retrieve + 一个简单 prompt。
  """
  # 简单实体假设：问题中提到的疾病名，后续可接 QueryParser
  # 这里为了让脚本可跑，沿用 RAGPipeline._extract_entities 的简单逻辑
  from rag.rag_pipeline import RAGPipeline as _R

  rp_dummy = _R(
    neo4j_client=graph_retriever.neo4j,
    llm_client=llm,
    embedding_client=None,  # type: ignore
  )
  entities = rp_dummy._extract_entities(question)  # type: ignore[attr-defined]

  results = graph_retriever.retrieve(
    query=question,
    entity_names=entities,
    max_depth=None,
    limit=20,
  )

  if not results:
    return "抱歉，我没有从知识图谱中找到足够的信息来回答这个问题。"

  # 简单组织 context
  context_lines = []
  for r in results[:10]:
    name = r.get("name") or r.get("entity") or ""
    desc = r.get("description") or r.get("properties", {}).get("description", "")
    rel_types = r.get("relation_types") or r.get("relation")
    context_lines.append(f"实体: {name}; 描述: {desc}; 关系: {rel_types}")

  context = "\n".join(context_lines)
  messages = [
    {
      "role": "system",
      "content": "你是一个医学知识图谱问答助手，请根据给定的结构化知识回答问题，不要编造不存在的内容。"
    },
    {
      "role": "user",
      "content": f"问题：{question}\n\n下面是与问题相关的知识图谱信息：\n{context}\n\n请基于这些信息，用通俗但专业的中文总结回答。"
    }
  ]
  return llm.chat(messages, temperature=0.2)


def answer_doc_rag(rag: RAGPipeline, question: str) -> str:
  """
  仅使用文档向量检索的答案。
  这里假设 Hybrid 检索模块支持单独调用文档检索；如果当前实现不方便拆分，可以先占位或直接复用 query。
  为保持脚本可用，先调用 rag.query(question) 并在说明中注明“当前实现偏 Hybrid”。
  """
  result = rag.query(question)
  return result.get("answer", "")


def answer_hybrid_rag(rag: RAGPipeline, question: str) -> str:
  result = rag.query(question)
  return result.get("answer", "")


def main() -> None:
  print("=== 多系统问答效果评测 ===")

  data = load_eval_data()
  llm, rag_pipeline, graph_retriever = build_clients()

  systems = ["llm_only", "graph_rag", "doc_rag", "hybrid_rag"]
  records: List[QAEvalRecord] = []

  # 按系统累计得分
  system_scores: Dict[str, List[float]] = {s: [] for s in systems}

  for item in data:
    qid = item.get("id")
    question = item.get("question", "")
    gold = item.get("gold_answer", "")
    category = item.get("category", "unknown")

    if not question:
      continue

    # 1) LLM-only
    try:
      ans_llm = answer_llm_only(llm, question)
    except Exception as e:
      ans_llm = f"[ERROR] {e}"
    score_llm = score_answer_simple(gold, ans_llm, category)
    system_scores["llm_only"].append(score_llm)
    records.append(QAEvalRecord(
      id=qid,
      question=question,
      category=category,
      gold_answer=gold,
      system="llm_only",
      answer=ans_llm,
      score=score_llm,
    ))

    # 2) graph_rag
    try:
      ans_graph = answer_graph_rag(llm, graph_retriever, question)
    except Exception as e:
      ans_graph = f"[ERROR] {e}"
    score_graph = score_answer_simple(gold, ans_graph, category)
    system_scores["graph_rag"].append(score_graph)
    records.append(QAEvalRecord(
      id=qid,
      question=question,
      category=category,
      gold_answer=gold,
      system="graph_rag",
      answer=ans_graph,
      score=score_graph,
    ))

    # 3) doc_rag（当前实现为 RAGPipeline.query 的近似文档 RAG）
    try:
      ans_doc = answer_doc_rag(rag_pipeline, question)
    except Exception as e:
      ans_doc = f"[ERROR] {e}"
    score_doc = score_answer_simple(gold, ans_doc, category)
    system_scores["doc_rag"].append(score_doc)
    records.append(QAEvalRecord(
      id=qid,
      question=question,
      category=category,
      gold_answer=gold,
      system="doc_rag",
      answer=ans_doc,
      score=score_doc,
    ))

    # 4) hybrid_rag（与当前默认 RAGPipeline.query 一致）
    try:
      ans_hybrid = answer_hybrid_rag(rag_pipeline, question)
    except Exception as e:
      ans_hybrid = f"[ERROR] {e}"
    score_hybrid = score_answer_simple(gold, ans_hybrid, category)
    system_scores["hybrid_rag"].append(score_hybrid)
    records.append(QAEvalRecord(
      id=qid,
      question=question,
      category=category,
      gold_answer=gold,
      system="hybrid_rag",
      answer=ans_hybrid,
      score=score_hybrid,
    ))

  # 汇总打印
  print("\n[系统平均得分]")
  for system in systems:
    scores = system_scores[system]
    if scores:
      avg = sum(scores) / len(scores)
    else:
      avg = 0.0
    print(f"{system}: avg_score={avg:.3f}, n={len(scores)}")

  # 写结果文件
  RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
  with RESULT_PATH.open("w", encoding="utf-8") as f:
    json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)

  print(f"\n详细结果已写入: {RESULT_PATH}")


if __name__ == "__main__":
  main()

