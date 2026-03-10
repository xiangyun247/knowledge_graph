实验设置（Evaluation Setup）
本节评估了本系统在医学问答任务中的效果，对比了四种配置：

LLM-only：仅调用大模型（DeepSeek, deepseek-chat），不使用任何检索（无 RAG）。
Graph RAG：仅使用图谱检索（Neo4j）+ LLM 生成答案。
Doc RAG：仅使用文档向量检索（Chroma）+ LLM 生成答案。
Hybrid RAG：图谱检索 + 文档向量检索 + 关键词检索的混合检索（Hybrid RAG）+ LLM 生成答案。
我们基于胰腺炎场景构造了20 道评测题集，题目类型覆盖：

定义（definition）、症状（symptom）、治疗（treatment）、并发症（complication）、
检查/影像学（examination）、病因（etiology/cause）、预后（prognosis）、就诊科室（department）、
多发人群（population）、严重程度分层（severity）、预防与生活方式干预（prevention）等。
每道题均给出参考标准答案（gold answer），并在 notes 字段中标注出判分时需要关注的关键要点（例如必须提到的症状、治疗措施或病因要素）。

评价指标与评分方法（Metrics & Scoring）
为了提高结果的可信度，我们设计了双重评分机制：

规则启发式评分（Rule-based score）

对每个问题类别预先定义若干关键术语集合（例如：
症状类问题：{腹痛, 恶心, 呕吐, 发热, 向背部放射}
治疗类问题：{禁食, 胃肠减压, 补液, 镇痛, 抑制胰酶} 等）。
评分规则：
0 分：回答为空，或仅为兜底/拒答类文案（如“详细信息请咨询专业医生”“无法从现有信息中得出结论”等）；
0.5 分：命中 1 个关键术语；
1 分：命中 ≥2 个关键术语，认为覆盖了大部分核心要点。
LLM 自动评分（LLM-based grading）

采用 DeepSeek 模型，对每条 (question, gold_answer, system_answer) 进行独立打分。
提示词中明确给出三档定义：
0 分：明显错误或基本无有效信息；
0.5 分：部分关键点正确，但不完整或有明显缺陷；
1 分：总体正确，覆盖主要医学要点，允许表述差异。
模型返回 JSON：
{ "score": 0/0.5/1, "reason": "简要评分理由" }
该得分记为 llm_score，原有规则分记为 score，后续分析中分别统计两种评分下的系统表现。
整体结果（Overall Results）
在 20 道问题上，四种系统配置的平均得分如下：

规则评分（score）

LLM-only：0.80
Graph RAG：0.35
Doc RAG：0.05
Hybrid RAG：0.05
LLM 评分（llm_score）

LLM-only：0.98
Graph RAG：0.33
Doc RAG：0.03
Hybrid RAG：0.03
可以看到：

在当前题集中（多为标准教科书型问题），LLM-only 表现最好，在 LLM 自评下几乎全部拿到 1 分；
Graph RAG 始终显著优于 Doc RAG / Hybrid RAG，在两种评分下平均得分均约为 0.3–0.35，属于“部分正确”的水平；
受限于当前文档知识库规模（仅有 2–3 篇文档），Doc RAG 与 Hybrid RAG 得分接近 0，说明大多数问题在文档侧缺乏可用上下文。
按类别的结果分析（Per-Category Analysis）
按 category 维度统计后，可以看出不同系统在各类问题上的优势与短板。以下以 LLM 评分（llm_score）为主进行说明：

定义 / 病因 / 预后 / 严重程度（definition, etiology, prognosis, severity）

LLM-only：大多为 1.0（完全正确或接近 gold answer）；
Graph RAG：在这些结构化信息较多的类别中，平均得分约为 0.25–0.5，表明图谱中确实提供了部分有用信息；
Doc / Hybrid：接近 0，主要因为当前文档库覆盖度有限，经常给出兜底回答。
检查与影像学（examination）

LLM-only：平均 1.0（能完整给出超声 / CT / MRI 等检查手段）；
Graph RAG：在少数问题上达到 0.25 左右，能指出 CT 及相关评分系统（如 Balthazar CT 评级），但对“超声”“MRI”涉及不足；
Doc / Hybrid：由于文档稀疏，多数回答为拒答或泛泛而谈，得分为 0。
治疗 / 并发症 / 预防（treatment, complication, prevention）

LLM-only：多数类别平均分在 0.8–1.0，能给出较完整的治疗方案、并发症列表以及生活方式建议；
Graph RAG：在这些涉及多种关系类型的类别中平均得分约为 0.3–0.5，可补充部分具体实体（如并发症名词、某些治疗措施），但整体完整性弱于 LLM-only；
Doc / Hybrid：由于缺乏相应文档段落，多数回答停留在“请咨询医生”，得分接近 0。
总体来看，在当前数据规模与题集设置下：

LLM-only 更擅长回答“通识性、教科书式”问题；
Graph RAG 能在若干类别中补充结构化细节（例如具体并发症名称、评分系统、影像学分级），但整体覆盖度仍受限于现有图谱规模；
Doc/Hybrid 的性能主要受限于文档数量与索引质量，尚未体现出理论上的优势。
讨论与局限性（Discussion & Limitations）
题集偏向通识，天然有利于 LLM-only

当前 20 道问题多为急性胰腺炎的标准知识点（症状、治疗、并发症、指南推荐检查等），对于大模型而言本身就属于高频训练内容。
在这种情况下，LLM-only 在两种评分下都取得了最高分，这说明在常见医学问答场景中，大模型本身已经具备较强的“教科书知识”能力。
知识源规模不均衡：图谱多、文档少

实验时，系统已有约 10 个知识图谱实例，而文档知识库中仅录入了 2–3 篇文档。
这导致：
Graph RAG 在多个类别中能提供一定补充信息（平均得分 0.3–0.5）；
Doc RAG / Hybrid RAG 经常由于找不到相关文档而退回兜底回答，评分接近 0。
因此，Doc / Hybrid 低分更多反映的是“当前文档数据不足”而非方法本身无效。
Hybrid RAG 未能在当前设定下体现理论优势

按设计，Hybrid RAG 应该在“图谱 + 文档 + 关键词”的综合检索上优于单一路径；
但在文档端极度稀疏的前提下，Hybrid 实际上退化为“图谱 + 噪声/空文档”的组合，因此没有显著优于 Graph RAG，甚至在部分问题上更倾向于输出泛泛回答。
评分机制仍有改进空间

规则评分仅基于关键词命中，尽管已引入拒答模式识别，但仍难以区分“结构合理但略有缺失的回答”和“堆砌关键词的回答”；
LLM 评分虽然更接近人类判断，但也可能受到提示词设计、模型偏好的影响，仍需辅以人工抽查以确保公平性。
小结（Summary）
综合规则启发式评分与 LLM 自动评分的结果可以得到以下结论：

在当前题集和数据规模下，LLM-only 在通识性医学问答上表现最佳，验证了大模型在常见医学知识方面的强大先验能力。
Graph RAG 在若干结构化信息密集的类别中能够提供一定补充，但总体尚未超越 LLM-only；
Doc RAG 与 Hybrid RAG 的表现主要受限于文档知识库规模和质量，在本轮实验中未能充分体现优势，需要在未来工作中通过扩充高质量临床指南/综述文档、优化索引策略等方式进一步验证其价值。
在后续工作中，我们计划：
1）扩充知识库（特别是结构化文档与权威指南），
2）设计更多“必须依赖本系统图谱/文档细节”的问题，
3）对不同检索策略在这些“高依赖结构化知识”的题目上进行更有针对性的对比实验，以更全面地评估 Hybrid RAG 与 Agent 架构的优势。




知识图谱构建质量评测（KG Extraction Evaluation）
实验设置
为评估基于 LLM 的知识图谱构建模块（KnowledgeGraphBuilder）在实体/关系抽取任务上的效果，我们在胰腺炎场景下人工标注了 30 条句子，构成评测集 eval_kg.json。
每条样本均标注：

实体列表：{id, text, type}
关系列表：{subject_id, object_id, type}
实体与关系类型按项目中实际使用的 schema 设计，包括但不限于：DISEASE, SYMPTOM, COMPLICATION, TREATMENT, EXAMINATION, LAB_RESULT, PROGNOSIS 以及 HAS_SYMPTOM, HAS_COMPLICATION, HAS_TREATMENT, HAS_EXAMINATION, HAS_LAB_ABNORMALITY, HAS_PROGNOSIS 等。

评测时，脚本 scripts/eval_kg_extraction.py 调用 KnowledgeGraphBuilder.process_text(text)，从输出中抽取实体/关系集合，与 gold 标注按 (规范化名称, 类型) / (subject_name, relation_type, object_name) 精确匹配，计算 P/R/F1；脚本 scripts/analyze_kg_core.py 进一步只针对上述“核心主干类型”重新统计了一版指标。

实验结果
整体指标（全部类型）
实体抽取：P=0.403, R=0.429, F1=0.416
关系抽取：P=0.271, R=0.280, F1=0.275
在完全端到端、句子较复杂的前提下，整体 F1 约 0.28–0.42，说明系统在“能够抓住主要信息”的同时，仍存在一定漏检与噪声。

主干类型指标（核心实体/关系）
仅统计核心实体类型：DISEASE, SYMPTOM, COMPLICATION, TREATMENT, EXAMINATION, LAB_RESULT, PROGNOSIS 与核心关系类型：HAS_SYMPTOM, HAS_COMPLICATION, HAS_TREATMENT, HAS_EXAMINATION, HAS_LAB_ABNORMALITY, HAS_PROGNOSIS 时，结果如下：

主干整体

实体（核心类型）：P=0.545, R=0.505, F1=0.525
关系（核心类型）：P=0.469, R=0.434, F1=0.451
按实体类型（核心）

DISEASE：P=0.536, R=0.968, F1=0.690（tp=30, fp=26, fn=1）
SYMPTOM：P=0.615, R=0.762, F1=0.681（tp=16, fp=10, fn=5）
PROGNOSIS：P=0.333, R=0.500, F1=0.400
COMPLICATION / TREATMENT / EXAMINATION / LAB_RESULT：当前 F1 接近 0，主要由于 LLM 输出 schema 与标注 schema 不完全对齐，导致这几类大量被记为 FN。
按关系类型（核心）

HAS_COMPLICATION：P=0.550, R=0.917, F1=0.687（tp=11, fp=9, fn=1）
HAS_SYMPTOM：P=0.478, R=0.524, F1=0.500（tp=11, fp=12, fn=10）
HAS_PROGNOSIS：P=0.167, R=0.500, F1=0.250
HAS_TREATMENT / HAS_EXAMINATION / HAS_LAB_ABNORMALITY：目前 F1≈0，多数金标准关系未被当前构建器显式抽取到对应类型。
结果分析与讨论
在最关心的主干链路上（疾病 DISEASE、症状 SYMPTOM 以及并发症关系 HAS_COMPLICATION），系统已经取得了相对可接受的抽取质量：

疾病与症状实体 F1 约 0.68–0.69；
HAS_COMPLICATION 关系 F1 约 0.69，HAS_SYMPTOM 关系 F1 约 0.50。
说明在“疾病–症状–并发症”这一条医学知识主干上，LLM + 后处理方案具备一定可靠性。
对于预后（PROGNOSIS）等次要类型，系统已能在部分句子中抽取到正确实体和关系（F1≈0.25–0.40），但整体覆盖度和精确度仍有提升空间。

另一方面，治疗（TREATMENT）、检查（EXAMINATION / HAS_EXAMINATION）、实验室异常（LAB_RESULT / HAS_LAB_ABNORMALITY）等细分类型的 F1 偏低，主要原因在于：
1）当前 KnowledgeGraphBuilder 的提示词更聚焦于“疾病–症状–并发症”主干，对治疗/检查等类别的输出约束不足；
2）标注 schema 引入了较多细粒度类型，而 LLM 实际输出往往归到更粗的类别或自由文本，导致在评测时被计为 FN 或 FP。

综合来看，本轮评测表明：

在主干信息（disease–symptom–complication）上，基于 LLM 的图谱构建已能提供较高质量的结构化抽取；
在更丰富的临床语义维度（treatment/examination/lab_result/prognosis 等）上，仍需通过收紧 schema、优化 prompt 与后处理规则、引入更强的 few-shot 约束来进一步提升抽取效果。
在后续工作中，我们计划：
1）将标注 schema 与构建器内部 schema 进一步统一，减少类型不一致带来的评测惩罚；
2）针对治疗/检查等类型设计专门的提示词与后处理逻辑；
3）在更大规模标注集上重复上述实验，验证改进后的构建质量。