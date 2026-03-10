## 实验与结果分析

本章评估了本系统在「医学知识图谱构建」与「智能问答」两个核心任务上的效果，重点分析不同配置下的性能表现、优势与局限性。

---

## 实验环境与数据集

### 实验环境

本文所有实验均在同一软硬件环境下完成。  

- **硬件环境**：Intel Core i7 处理器，16 GB 内存，Windows 10 操作系统  
- **软件环境**：
  - 后端：Python 3.10，FastAPI 0.104，Uvicorn 0.24  
  - 图数据库：Neo4j 5.x  
  - 关系数据库：MySQL 8.0  
  - 向量库：Chroma 0.5.x  
  - 前端：Vue 2.6 + Vue Router 3 + Vuex 3，UI 框架 Element UI  
  - 任务队列：Celery  
  - 部署：Docker / Docker Compose  
  - 大模型：DeepSeek `deepseek-chat`（OpenAI 兼容 API），本地嵌入模型 `BAAI/bge-large-zh-v1.5`

除特别说明外，所有实验均在 CPU 环境下完成。

### 数据集与场景

系统以「急性胰腺炎」相关医学知识为核心应用场景，构建并使用了两类评测数据集：

- **知识图谱构建评测集（KG Eval）**  
  从教科书、指南和综述中选取 **30 条**与急性胰腺炎相关的典型中文句子，覆盖：
  - 症状（symptom）、并发症（complication）、治疗（treatment）  
  - 检查与影像学（examination）、实验室异常（lab result）  
  - 预后（prognosis）、病因与危险因素（etiology, risk factor）等  
  对每条句子人工标注实体列表 `{id, text, type}` 及关系列表 `{subject_id, object_id, type}`，构成金标准知识图谱，用于评估基于 LLM 的 KG 构建质量。

- **智能问答评测集（QA Eval）**  
  围绕急性胰腺炎构造 **20 道**医学问题，问题类型包括：
  - 定义（definition）、症状（symptom）、治疗（treatment）、并发症（complication）  
  - 检查/影像学（examination）、病因（etiology/cause）  
  - 预后（prognosis）、就诊科室（department）、多发人群（population）  
  - 严重程度分层（severity）、预防与生活方式干预（prevention）  
  每道题均给出参考标准答案（gold answer），并在 `notes` 字段中标注判分时需要关注的关键要点（例如必须提到的症状、治疗措施或病因要素）。

---

## 知识图谱构建质量评测（KG Extraction Evaluation）

### 实验设置

为评估基于 LLM 的知识图谱构建模块（`KnowledgeGraphBuilder`）在实体/关系抽取任务上的效果，我们在胰腺炎场景下人工标注了 30 条句子，构成评测集 `eval_kg.json`。  
每条样本均标注：

- **实体列表**：`{id, text, type}`  
- **关系列表**：`{subject_id, object_id, type}`

实体与关系类型按项目中实际使用的 schema 设计，包括但不限于：

- 实体类型：`DISEASE, SYMPTOM, COMPLICATION, TREATMENT, EXAMINATION, LAB_RESULT, PROGNOSIS` 等  
- 关系类型：`HAS_SYMPTOM, HAS_COMPLICATION, HAS_TREATMENT, HAS_EXAMINATION, HAS_LAB_ABNORMALITY, HAS_PROGNOSIS` 等  

评测时，脚本 `scripts/eval_kg_extraction.py` 调用 `KnowledgeGraphBuilder.process_text(text)`，从输出中抽取实体/关系集合，与 gold 标注按：

- 实体：`(规范化名称, 类型)`  
- 关系：`(subject_name, relation_type, object_name)`  

精确匹配，计算 P/R/F1；脚本 `scripts/analyze_kg_core.py` 进一步只针对上述“核心主干类型”重新统计了一版指标。

### 评价指标

设在给定类型集合上，金标准实体/关系集合为 \(G\)，系统预测集合为 \(P\)，则：

\[
TP = |G \cap P|,\quad FP = |P \setminus G|,\quad FN = |G \setminus P|
\]

定义精度（Precision）、召回率（Recall）和 F1 值为：

\[
P = \frac{TP}{TP + FP},\quad
R = \frac{TP}{TP + FN},\quad
F1 = \frac{2PR}{P + R}
\]

在实现上：

- 实体按 \((\text{规范化名称}, \text{类型})\) 精确匹配；  
- 关系按 \((\text{subject\_name}, \text{relation\_type}, \text{object\_name})\) 匹配。  

除整体汇总外，本文分别计算：

- **整体指标**：所有实体/关系类型合并统计的 P/R/F1；  
- **按类型指标**：对每个实体类型、每个关系类型分别统计 P/R/F1；  
- **主干类型指标**：仅针对核心实体类型 `DISEASE, SYMPTOM, COMPLICATION, TREATMENT, EXAMINATION, LAB_RESULT, PROGNOSIS` 以及核心关系类型 `HAS_SYMPTOM, HAS_COMPLICATION, HAS_TREATMENT, HAS_EXAMINATION, HAS_LAB_ABNORMALITY, HAS_PROGNOSIS` 重新计算 P/R/F1。

### 实验结果

#### 整体指标（全部类型）

在全部实体/关系类型上，知识图谱构建模块在 30 条标注句子上的整体表现为：

- **实体抽取**：P=0.403, R=0.429, F1=0.416  
- **关系抽取**：P=0.271, R=0.280, F1=0.275  

在完全端到端、句子较复杂的前提下，整体 F1 约 0.28–0.42，说明系统在“能够抓住主要信息”的同时，仍存在一定漏检与噪声。

#### 主干类型指标（核心实体/关系）

仅统计核心实体类型：`DISEASE, SYMPTOM, COMPLICATION, TREATMENT, EXAMINATION, LAB_RESULT, PROGNOSIS` 与核心关系类型：`HAS_SYMPTOM, HAS_COMPLICATION, HAS_TREATMENT, HAS_EXAMINATION, HAS_LAB_ABNORMALITY, HAS_PROGNOSIS` 时，结果如下（`scripts/analyze_kg_core.py`）：

- **主干整体（核心类型合并）**
  - 实体（核心类型）：P=0.545, R=0.505, F1=0.525  
  - 关系（核心类型）：P=0.469, R=0.434, F1=0.451

- **按实体类型（核心）**
  - `DISEASE`：P=0.536, R=0.968, **F1=0.690**（tp=30, fp=26, fn=1）  
  - `SYMPTOM`：P=0.615, R=0.762, **F1=0.681**（tp=16, fp=10, fn=5）  
  - `PROGNOSIS`：P=0.333, R=0.500, F1=0.400（tp=2, fp=4, fn=2）  
  - `COMPLICATION / TREATMENT / EXAMINATION / LAB_RESULT`：当前 F1 接近 0，主要由于 LLM 输出 schema 与标注 schema 不完全对齐，导致这几类大量被记为 FN。

- **按关系类型（核心）**
  - `HAS_COMPLICATION`：P=0.550, R=0.917, **F1=0.687**（tp=11, fp=9, fn=1）  
  - `HAS_SYMPTOM`：P=0.478, R=0.524, **F1=0.500**（tp=11, fp=12, fn=10）  
  - `HAS_PROGNOSIS`：P=0.167, R=0.500, F1=0.250（tp=1, fp=5, fn=1）  
  - `HAS_TREATMENT / HAS_EXAMINATION / HAS_LAB_ABNORMALITY`：目前 F1≈0，多数金标准关系未被当前构建器显式抽取到对应类型。

使用 `scripts/plot_kg_core.py` 绘制的按实体/关系类型的 F1 柱状图表明：在疾病 `DISEASE`、症状 `SYMPTOM` 及并发症关系 `HAS_COMPLICATION` 这一主干链路上，系统表现明显优于其他细分类型。

### 结果分析与讨论

从整体结果来看，在复杂医学文本场景下，端到端的 LLM 驱动知识图谱构建尚存在一定提升空间：全部类型合并统计的实体 F1 约 0.42，关系 F1 约 0.28。但在进一步聚焦于核心实体/关系类型后，可以看到系统在主干医学知识上的抽取能力已经达到一个较为可用的水平：

- 在疾病与症状实体上，F1 分别为 0.69 和 0.68，说明大模型能够较稳定地识别出“急性胰腺炎”及其典型症状等关键信息；  
- 在 `HAS_COMPLICATION` 关系上，F1 接近 0.69，表明系统较好地捕获了“急性胰腺炎–并发症”之间的结构化关联；  
- `HAS_SYMPTOM` 的 F1 约 0.50，代表系统对“疾病–症状”关系的抽取已经具备一定质量，但仍存在漏检与误检。

与此相对，治疗（TREATMENT）、检查（EXAMINATION / `HAS_EXAMINATION`）、实验室异常（LAB_RESULT / `HAS_LAB_ABNORMALITY`）等类型以及对应关系的 F1 偏低，主要原因在于：

1. 当前 `KnowledgeGraphBuilder` 的提示词设计更偏向“疾病–症状–并发症”主干，对治疗方案、检查项目和实验室指标的抽取约束不足；  
2. 标注 schema 较为细粒度，而 LLM 实际输出往往倾向于更粗类别或自由文本，导致在评测时大量被统计为 FN 或 FP。

综合来看，本轮评测表明：

- 在主干信息（disease–symptom–complication）上，基于 LLM 的图谱构建已能提供较高质量的结构化抽取；  
- 在更丰富的临床语义维度（treatment/examination/lab_result/prognosis 等）上，仍需通过收紧 schema、优化 prompt 与后处理规则、引入更强的 few-shot 约束来进一步提升抽取效果。

后续工作中，我们计划：

1. 将标注 schema 与构建器内部 schema 进一步统一，减少类型不一致带来的评测惩罚；  
2. 针对治疗/检查等类型设计专门的提示词与后处理逻辑；  
3. 在更大规模标注集上重复上述实验，验证改进后的构建质量。

---

## 智能问答系统效果评测（QA Evaluation）

### 实验设置

本节评估了本系统在医学问答任务中的效果，对比了四种配置：

- **LLM-only**：仅调用大模型（DeepSeek, `deepseek-chat`），不使用任何检索（无 RAG）。  
- **Graph RAG**：仅使用图谱检索（Neo4j）+ LLM 生成答案。  
- **Doc RAG**：仅使用文档向量检索（Chroma）+ LLM 生成答案。  
- **Hybrid RAG**：图谱检索 + 文档向量检索 + 关键词检索的混合检索（Hybrid RAG）+ LLM 生成答案。

我们基于胰腺炎场景构造了 20 道评测题集，题目类型覆盖：

- 定义（definition）、症状（symptom）、治疗（treatment）、并发症（complication）  
- 检查/影像学（examination）、病因（etiology/cause）、预后（prognosis）  
- 就诊科室（department）、多发人群（population）、严重程度分层（severity）  
- 预防与生活方式干预（prevention）  

每道题均给出参考标准答案（gold answer），并在 `notes` 字段中标注出判分时需要关注的关键要点（例如必须提到的症状、治疗措施或病因要素）。

### 评价指标与评分方法（Metrics & Scoring）

为了提高结果的可信度，我们设计了**双重评分机制**：

#### 规则启发式评分（Rule-based score）

对每个问题类别预先定义若干**关键术语集合**（例如）：

- 症状类问题：`{腹痛, 恶心, 呕吐, 发热, 向背部放射}`  
- 治疗类问题：`{禁食, 胃肠减压, 补液, 镇痛, 抑制胰酶}` 等  

评分规则：

- **0 分**：回答为空，或仅为兜底/拒答类文案（如“详细信息请咨询专业医生”“无法从现有信息中得出结论”等）；  
- **0.5 分**：命中 1 个关键术语；  
- **1 分**：命中 ≥2 个关键术语，认为覆盖了大部分核心要点。

#### LLM 自动评分（LLM-based grading）

采用 DeepSeek 模型，对每条 `(question, gold_answer, system_answer)` 进行独立打分。  
提示词中明确给出三档定义：

- **0 分**：明显错误或基本无有效信息；  
- **0.5 分**：部分关键点正确，但不完整或有明显缺陷；  
- **1 分**：总体正确，覆盖主要医学要点，允许表述差异。

模型返回形如：

```json
{ "score": 0/0.5/1, "reason": "简要评分理由" }
```

的 JSON，对应得分记为 `llm_score`，原有规则分记为 `score`，后续分析中分别统计两种评分下的系统表现。

### 实验结果

#### 整体结果（Overall Results）

在 20 道问题上，四种系统配置的平均得分如下：

- **规则评分（score）**
  - LLM-only：0.80  
  - Graph RAG：0.35  
  - Doc RAG：0.05  
  - Hybrid RAG：0.05  

- **LLM 评分（llm_score）**
  - LLM-only：0.98  
  - Graph RAG：0.33  
  - Doc RAG：0.03  
  - Hybrid RAG：0.03  

可以看到：

- 在当前题集中（多为标准教科书型问题），**LLM-only 表现最好**，在 LLM 自评下几乎全部拿到 1 分；  
- **Graph RAG 始终显著优于 Doc RAG / Hybrid RAG**，在两种评分下平均得分均约为 0.3–0.35，属于“部分正确”的水平；  
- 受限于当前文档知识库规模（仅有 2–3 篇文档），**Doc RAG 与 Hybrid RAG 得分接近 0**，说明大多数问题在文档侧缺乏可用上下文。

#### 按类别的结果分析（Per-Category Analysis）

按 `category` 维度统计后，可以看出不同系统在各类问题上的优势与短板。以下以 LLM 评分（`llm_score`）为主进行说明：

- **定义 / 病因 / 预后 / 严重程度**（definition, etiology, prognosis, severity）  
  - LLM-only：大多为 1.0（完全正确或接近 gold answer）；  
  - Graph RAG：在这些结构化信息较多的类别中，平均得分约为 0.25–0.5，表明图谱中确实提供了部分有用信息；  
  - Doc / Hybrid：接近 0，主要因为当前文档库覆盖度有限，经常给出兜底回答。

- **检查与影像学**（examination）  
  - LLM-only：平均 1.0（能完整给出超声 / CT / MRI 等检查手段）；  
  - Graph RAG：在少数问题上达到约 0.25，能指出 CT 及相关评分系统（如 Balthazar CT 评级），但对“超声”“MRI”涉及不足；  
  - Doc / Hybrid：由于文档稀疏，多数回答为拒答或泛泛而谈，得分为 0。

- **治疗 / 并发症 / 预防**（treatment, complication, prevention）  
  - LLM-only：多数类别平均分在 0.8–1.0，能给出较完整的治疗方案、并发症列表以及生活方式建议；  
  - Graph RAG：在这些涉及多种关系类型的类别中平均得分约为 0.3–0.5，可补充部分具体实体（如并发症名词、某些治疗措施），但整体完整性弱于 LLM-only；  
  - Doc / Hybrid：由于缺乏相应文档段落，多数回答停留在“请咨询医生”，得分接近 0。

使用 `scripts/analyze_eval_results.py` 与 `scripts/plot_qa_results.py`，可以分别在规则评分和 LLM 评分下，绘制不同系统整体平均得分以及按类别分组平均得分的柱状图，从而直观对比各系统配置的效果差异。

### 讨论与局限性（Discussion & Limitations）

#### 题集偏向通识，天然有利于 LLM-only

当前 20 道问题多为急性胰腺炎的标准知识点（症状、治疗、并发症、指南推荐检查等），对于大模型而言本身就属于高频训练内容。  
在这种情况下，LLM-only 在两种评分下都取得了最高分，这说明在常见医学问答场景中，大模型本身已经具备较强的“教科书知识”能力。

#### 知识源规模不均衡：图谱多、文档少

实验时，系统已有约 10 个知识图谱实例，而文档知识库中仅录入了 2–3 篇文档。这导致：

- Graph RAG 在多个类别中能提供一定补充信息（平均得分 0.3–0.5）；  
- Doc RAG / Hybrid RAG 经常由于找不到相关文档而退回兜底回答，评分接近 0。  

因此，Doc / Hybrid 低分更多反映的是“当前文档数据不足”而非方法本身无效。

#### Hybrid RAG 未能在当前设定下体现理论优势

按设计，Hybrid RAG 应该在“图谱 + 文档 + 关键词”的综合检索上优于单一路径；  
但在文档端极度稀疏的前提下，Hybrid 实际上退化为“图谱 + 噪声/空文档”的组合，因此没有显著优于 Graph RAG，甚至在部分问题上更倾向于输出泛泛回答。

#### 评分机制仍有改进空间

- 规则评分仅基于关键词命中，尽管已引入拒答模式识别，但仍难以区分“结构合理但略有缺失的回答”和“堆砌关键词的回答”；  
- LLM 评分虽然更接近人类判断，但也可能受到提示词设计、模型偏好的影响，仍需辅以人工抽查以确保公平性。

### 小结（Summary）

综合规则启发式评分与 LLM 自动评分的结果可以得到以下结论：

- 在当前题集和数据规模下，**LLM-only 在通识性医学问答上表现最佳**，验证了大模型在常见医学知识方面的强大先验能力；  
- **Graph RAG 在若干结构化信息密集的类别中能够提供一定补充，但总体尚未超越 LLM-only**；  
- **Doc RAG 与 Hybrid RAG 的表现主要受限于文档知识库规模和质量**，在本轮实验中未能充分体现优势，需要在未来工作中通过扩充高质量临床指南/综述文档、优化索引策略等方式进一步验证其价值。

在后续工作中，我们计划：

1. 扩充知识库，特别是结构化文档与权威指南，以提升 Doc/Hybrid RAG 的上限；  
2. 设计更多“必须依赖本系统图谱/文档细节”才能回答的问题，构造更适合检索增强问答（RAG）的评测集；  
3. 对不同检索策略（仅图谱、仅文档、Hybrid RAG、Agent+Tools）在这些高依赖结构化知识的题目上进行更有针对性的对比实验，以更全面地评估 Hybrid RAG 与 Agent 架构的优势。

