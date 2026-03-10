# 项目优化建议（可落地）

结合当前代码与业界常见做法，从「文本提取与数据清洗」「实体-关系提取」「其他」三方面给出可落地的优化建议。

---

## 一、文本提取与数据清洗

### 现状

- **PDF**：`pdfplumber` 按页 `extract_text()` 后直接拼接，无统一清洗。
- **入库/构建**：`_extract_text_for_ingest`、单文件上传、Hadoop 批量路径均未复用同一套清洗逻辑。
- **Hadoop**：`hadoop/mapreduce/text_clean/mapper.py` 中已有较完整的 `clean_medical_text`（参考文献截断、页眉页脚、引用标记、URL 等），但仅用于 MapReduce，单文件上传与知识库入库未使用。
- **KG 构建**：`kg/builder.py` 的 `TextPreprocessor.clean_text` 仅做空白合并和字符过滤，与 Hadoop 的医学清洗未统一。

### 建议 1：统一「提取后」清洗管道（优先）【已实现】

**目标**：所有来源的正文（PDF/TXT/JSON、单文件/批量）在进入分块或 KG 构建前，都走同一套清洗。

**落地步骤**：

1. **抽成公共模块**  
   在 `backend/` 或 `utils/` 下新增 `text_clean.py`，把 Hadoop 里 `clean_medical_text` 的逻辑迁入（或从 hadoop 里 import 再封装一层），提供：
   - `clean_medical_text(raw: str) -> str`  
   - 可选：`normalize_for_kg(text: str) -> str`（仅做空白/控制字符等轻度清洗，供 KG 用）。

2. **在提取入口统一调用**  
   - 在 `backend/app.py` 的 `_extract_text_for_ingest` 中，对 PDF/TXT 提取结果在返回前调用 `clean_medical_text`（或对知识库入库单独用 `normalize_for_kg`，视是否要保留更多原文）。  
   - 单文件上传写入 `pdf_text` 前、以及批量构建从 `pdf_text` 读入后，对文本做一次同一套清洗。  
   - 这样：**单文件上传、知识库入库、KG 构建** 用的都是「提取 + 同一套清洗」后的文本。

3. **清洗内容建议保留/增强**（与现有 hadoop 逻辑对齐并略作扩展）  
   - 统一换行符 `\r\n` / `\r` → `\n`。  
   - 按「参考文献」「References」「致谢」等截断，去掉文末无关内容。  
   - 过滤：页眉页脚、图/表标题行、纯数字/符号行、过短且无医学关键词的行。  
   - 行内：去掉引用标记 `[1]`、`[2-5]`，简单文献引用 `(Author 2020)`，URL、邮箱，多空格压成单空格。  
   - 可选：控制字符、不可见字符、乱码替换（如 `\x00`、部分 `\ufffd` 替换为空格或删掉）。

**收益**：构建与检索的文本质量一致，减少噪声实体和无关关系，便于后续实体-关系提取更稳。

---

### 建议 2：PDF 提取增强（按需）

- **扫描版 PDF**：当前仅 pdfplumber，对扫描件几乎无文字。可考虑：  
  - 集成 **pytesseract + pdf2image** 或 **OCR 能力**（如 PaddleOCR、EasyOCR）做版面分析 + 文字识别，再对识别结果做同一套 `clean_medical_text`。  
  - 先在小批量上验证效果和性能，再决定是否作为可选开关（如按文件或按任务开启 OCR）。  
- **表格**：pdfplumber 支持 `page.extract_tables()`，若医学文献中表格含「疾病-症状-药物」等，可对表格单元做简单规则或小模型抽取，再转为段落文本进入现有管道（或单独存为结构化字段，供后续利用）。  

这两项可作为二期，在「统一清洗」完成后再做。

---

## 二、实体-关系提取算法更精确

### 现状

- 单段约 1000 字、单次 LLM 调用、一个通用 prompt，实体类型与关系类型来自 `config.ENTITY_TYPES` / `RELATION_TYPES`。
- 无 few-shot、无结构化输出约束、无实体/关系校验与规范化，subject/object 是否在实体列表中也未强制校验。

### 建议 3：Prompt 工程（低成本、先做）

1. **Few-shot 示例**  
   在 `_extract_entities_and_relations` 的 prompt 中增加 1～2 个「输入段落 + 标准 JSON 输出」示例（医学场景，含多实体、多关系类型）。  
   - 示例中严格遵循：关系里的 subject/object 都来自上面 entities 的 name。  
   - 可显著减少格式错误和「编造实体名」问题。

2. **输出格式与约束写清**  
   - 明确写出：  
     - “relations 中的 subject 和 object 必须是 entities 中某一项的 name，不得新增未列出的实体。”  
     - “若某句无实体或关系，对应列表可为空，但必须保留 entities/relations 两个 key。”  
   - 继续使用现有的 `extract_json` 鲁棒解析；若模型支持 JSON mode / structured output，可后续改为强制 JSON 输出，减少截断与格式错误。

3. **温度与长度**  
   - 抽取任务建议 `temperature=0` 或 `0.1`，提高可复现性和一致性。  
   - 若单段 1000 字导致遗漏，可适当增大 `max_tokens`，或先做「段落内句子级」粗筛（如含医学关键词的句子再送 LLM），在保证成本可控的前提下提高召回。

### 建议 4：后处理校验与规范化（中成本、推荐）

1. **关系与实体一致性**  
   - 在写入 Neo4j 前，对每条 relation 检查：subject 和 object 是否都出现在当前 batch 的 entities（或已写入图中的实体）中。  
   - 若不匹配：  
     - 自动在 entities 中补一条（name=subject 或 object，type=Unknown 或由 LLM 再填一次），或  
     - 丢弃该 relation，并打日志，便于统计与调 prompt。

2. **实体名规范化**  
   - 对 LLM 输出的实体名做简单归一化：strip、全角转半角、多余空格合并。  
   - 可选：同义合并（如「急性胰腺炎」与「急性 胰腺炎」视为同一实体），可用简单规则或小词表，避免同一实体多节点。

3. **类型与关系类型校验**  
   - 若 entity.type 不在 `ENTITY_TYPES`，映射到默认类型（如 Disease）并打日志。  
   - 若 relation.predicate 不在 `RELATION_TYPES`，映射到 `BELONGS_TO` 并打日志。  
   - 实体/关系类型见 config.py（表2 实体描述框架、表3 实体关系描述框架）。

### 建议 5：两阶段抽取（可选、进阶）

- **阶段一**：只做实体识别（NER）。  
  - Prompt 或小模型只输出 entities，减少单次输出长度，提高实体召回与边界准确率。  
- **阶段二**：在已识别实体基础上做关系分类（RE）。  
  - 输入：段落 + 本段实体列表；输出：仅 relations，且 subject/object 必须来自该列表。  
- 实现上可先在同一 `process_text` 里用两次 LLM 调用（先 NER，再 RE），再考虑是否拆成两个函数、或对超长段落先分句再 RE。  
- 成本约为原来的约 2 倍，适合对准确率要求高、且能接受延迟与 API 成本的场景。

### 建议 6：医学领域增强（可选）

- **专用模型**：若有条件，可尝试医学预训练或微调模型（如中文医学 NER/RE 或 LLaMA 系医学微调）做抽取，再与当前 LLM 结果融合（例如用规则或小模型做初筛，LLM 做精修）。  
- **术语表/实体库**：维护一个「疾病/药物/检查」等核心词表，在写入前做实体名与词表匹配，匹配到的强制类型或打标签，便于后续查询与展示。  
- **负样本提示**：在 prompt 中加 1～2 句「不应被抽成实体/关系的例子」，减少误抽（如“患者主诉……”中的“患者”一般不单独成实体）。

---

## 三、其他可优化点

### 建议 7：分块与 KG 段落策略一致

- 知识库分块（`doc_chunking.chunk_text`）与 KG 构建的「段落」目前是两套逻辑。  
- 若希望「同一段文本在检索与图谱中语义一致」，可考虑：  
  - 对同一份清洗后文本，先按同一套规则分块（如按段或按句界 + 长度），  
  - 一块用于 Chroma 入库，一块用于 KG 的 `process_text` 输入。  
- 这样检索到的 chunk 与图谱来源更对齐，便于 Hybrid RAG 或后续多源融合。

### 建议 8：抽取质量监控

- 对每次构建（或每批）统计：  
  - 实体数/关系数、被丢弃的关系数（因 subject/object 不在实体列表）、类型映射次数。  
- 打日志或写入简单指标表，便于对比「改 prompt / 改清洗」前后的效果，指导下一步优化。

### 建议 9：配置外置

- 将「实体类型」「关系类型」的说明或示例从代码中移到配置文件或单独 markdown，便于非开发同学维护领域词表与类型定义，并与 prompt 中的描述保持一致。

---

## 四、建议落地优先级

| 优先级 | 建议 | 成本 | 预期收益 |
|--------|------|------|----------|
| 高 | 1. 统一提取后清洗管道 | 低 | 全链路文本质量一致，减少噪声 |
| 高 | 3. Prompt 工程（few-shot + 约束） | 低 | 抽取格式更稳、实体关系更一致 |
| 高 | 4. 后处理校验与规范化 | 中 | 数据一致性与图谱质量提升 |
| 中 | 2. PDF 增强（OCR/表格） | 中高 | 支持扫描件与表格内容 |
| 中 | 5. 两阶段 NER+RE | 中 | 抽取准确率提升 |
| 中 | 7. 分块与 KG 段落一致 | 中 | 检索与图谱语义对齐 |
| 低 | 6. 医学专用模型/词表 | 高 | 领域准确率进一步提升 |
| 低 | 8. 质量监控 / 9. 配置外置 | 低 | 可观测性与可维护性 |

建议实施顺序：**1 → 3 → 4**，再视效果决定是否做 2、5、7。

**实现说明**：建议 1 已落地。`backend/text_clean.py` 提供 `clean_medical_text`，并在 `_extract_text_for_ingest`、单文件上传、批量上传（hadoop_api）的提取后统一调用。

---

## 五、可直接复用的代码位置

- **文本提取**：`backend/app.py` 中 `_extract_text_for_ingest`、单文件上传写 `pdf_text` 处。  
- **医学清洗逻辑**：`hadoop/mapreduce/text_clean/mapper.py` 中 `clean_medical_text`。  
- **实体关系提取**：`kg/builder.py` 中 `_extract_entities_and_relations`、`process_text` 中段落循环与 `_create_entity` / `_create_relation` 前。  
- **实体/关系类型**：`config.py` 中 `ENTITY_TYPES`、`RELATION_TYPES`。

在以上位置接入「统一清洗」与「校验/规范化」即可快速落地前述高优先级建议。

---

## 六、批量构建与 Hadoop MapReduce

### 现状

- **批量构建**（`POST /api/hadoop/build/batch`）**没有使用 Hadoop MapReduce**。
- 流程实际为：
  1. 批量上传时：文件写入本地并上传到 HDFS，**文本在 API 进程内**用 `backend.pdf_extract.extract_pdf_text()`（pdfplumber + 表格 + 可选 OCR）提取，结果存入 `uploaded_files[file_id]["pdf_text"]`。
  2. 批量构建时：后台线程直接从 `uploaded_files` 读取各文件的 `pdf_text`，用 **ThreadPoolExecutor** 并行为每个文件调用 `build_single_file_kg()` 构建图谱。
- 请求体里的 **`use_hadoop`** 参数目前**未参与分支**，传 `true`/`false` 行为一致。
- **Hadoop 侧**：`hadoop_service.process_files_with_hadoop(file_ids)` 已实现（PDF 提取 → 文本清洗 → 文本分块 三阶段 MapReduce），但**没有任何调用方**；MapReduce 脚本（`pdf_extract` / `text_clean` / `text_chunk`）处于「预留未接入」状态。

### 建议（按需选做）

1. **文档与接口诚实化（低成本）**  
   - 在 README 或 API 文档中写明：当前批量构建为「上传时本地提取 + 多线程并行构建」，**不经过 Hadoop MapReduce**；Hadoop 仅用于批量上传到 HDFS 及未来可选的分布式预处理。  
   - 将 `use_hadoop` 设为可选，或注明「保留参数，暂未启用；为后续接入 MapReduce 预留」。

2. **真正接入 MapReduce（中高成本）**  
   - 当 `use_hadoop=True` 且 Hadoop 可用时：先调 `process_files_with_hadoop(file_ids)`，从 HDFS 读取 MapReduce 的**最终分块结果**（text_chunk 阶段输出），按 file_id 或路径聚合为「每文件一段或若干块」的文本，再交给现有线程池对每个文件/块调用 `build_single_file_kg` 或按块构建。  
   - **“中高成本”主要指**：**开发与对接成本**——需要改后端逻辑、约定 MapReduce 输出格式、实现从 HDFS 拉取并解析结果的代码、处理 Hadoop 不可用/任务失败等情况；不是指“跑一次很贵”。  
   - **笔记本能不能用？** 能。当前项目用 `docker-compose` 已配置好 Hadoop（NameNode、DataNode、ResourceManager、NodeManager 等），在笔记本上 `docker-compose up` 即可在本地起一套 Hadoop，MapReduce 任务可以正常提交和运行。但需注意：  
     - 多个 Hadoop 容器 + JVM 会占用较多内存（建议本机 8GB+，16GB 更稳）；  
     - 对**少量文件**（例如几十个 PDF），MapReduce 的启动与调度开销可能比「本机多线程提取+构建」还大，真正优势在**文件量很大、单机成为瓶颈**时才明显。

3. **折中（可选）**【已实现】  
   - 保留「上传时本地提取」作为默认路径（无 Hadoop 依赖、行为与现有一致）。  
   - 仅对「仅上传到 HDFS、未在本地做提取」的文件（即 `pdf_text` 为空或以 `ERROR:` 开头），在批量构建时若 `use_hadoop=True` 则走 MapReduce 提取→清洗→分块，从 HDFS 读取 text_clean 阶段输出并拉回，写入 `uploaded_files[file_id]["pdf_text"]`，再用同一套并行构建逻辑。  
   - **如何区分小规模/大规模？** 系统不会按文件数量或数据量自动区分。实际逻辑是：  
     - **有本地提取结果**（`uploaded_files[file_id]["pdf_text"]` 有内容且非 `ERROR:`）→ 一律用这份文本构建，不调 MapReduce。  
     - **没有本地提取结果**（空或 `ERROR:`）且请求里 **`use_hadoop=True`** → 对这些 file_id 调 MapReduce，拉回后再构建。  
     因此「小规模」= 你一直用当前上传流程（上传即做本地提取），不传或传 `use_hadoop=false` 也能正常构建；「大规模」= 你主动选择：部分文件只上 HDFS 不做本地提取，并在批量构建时传 **`use_hadoop=true`**，由后端对缺文本的文件跑 MapReduce。  
   - 实现位置：`backend/hadoop_api.py` 中 `_run_hadoop_and_celery_in_background`；`backend/hadoop_service.py` 中 `read_extracted_text_from_hdfs`。
