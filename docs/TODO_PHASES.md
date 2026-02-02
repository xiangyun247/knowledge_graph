# 项目推进 To-Do 清单（三阶段）

本文档将后续工作拆分为三份清单：**修复问题**、**Docker+上云**、**Hadoop MR**。每份 5～10 条具体步骤，便于按阶段执行与验收。

---

## 一、修复问题（当前缺口与体验优化）

| 序号 | 步骤 | 说明 |
|-----|------|------|
| 1 | **历史记录：单条删除 API** | 在 `backend/app.py` 新增 `DELETE /api/history/{history_id}`，内部调用 MySQL 删除指定 `history_id`；若 `mysql_client` 无 `delete_history(history_id)`，先在 `db/mysql_client.py` 实现再暴露。 |
| 2 | **历史记录：批量删除 API** | 新增 `POST /api/history/batch-delete`，请求体为 `{ "history_ids": ["id1", "id2", ...] }`，在 MySQL 中批量删除；需在 `mysql_client` 增加 `delete_history_batch(history_ids)`（或循环调用单条删除）。 |
| 3 | **历史记录：清空 API** | 新增 `DELETE /api/history/clear`（或 `POST /api/history/clear`），清空当前用户或全部历史；在 `mysql_client` 增加 `clear_history(user_id=None)`，并在 app 中挂载路由。 |
| 4 | **图谱清空 API** | 新增 `DELETE /api/graph/clear`（或按 graph_id 的 `DELETE /api/graph/{graph_id}`）。若为「清空当前图谱」：调用 Neo4j `delete_all()` 并同步清理 MySQL 中对应 `knowledge_graphs`/graph_data；若为「按 graph_id 删除」：使用现有 `mysql_client.delete_graph(graph_id)` 并清理 Neo4j 中该图谱相关数据。 |
| 5 | **前端对接上述新接口** | 在 `vue_test_style` 的 history、graph 相关页面中，将「删除单条」「批量删除」「清空历史」「清空/删除图谱」等操作对接到上述新 API（调用 `src/api/history.js`、`src/api/graph.js` 等）。 |
| 6 | **API 文档与脚本更新** | 在 `docs/API.md` 中补充历史删除/清空、图谱清空/删除的请求/响应说明；在 `scripts/check_frontend_backend_api.py`（若有）中增加对新接口的检查项。 |
| 7 | **错误处理与权限（可选）** | 对删除/清空接口做基本校验：如 history_id 是否存在、当前用户是否有权删除；返回 404/403 与统一错误格式。 |
| 8 | **首页/统计数据源（可选）** | 若首页或统计页仍为 mock 数据，改为调用后端统计接口（如 `get_history_stats`、图谱数量等），保证前后端数据一致。 |

---

## 二、Docker + 上云

| 序号 | 步骤 | 说明 |
|-----|------|------|
| 1 | **完善 docker-compose 与 Dockerfile** | 检查 `docker-compose.yml` 与 `docker/` 下各 Dockerfile（backend、celery、hadoop-*）是否均可一次构建通过；统一基础镜像版本与 Python 依赖（requirements.txt）；确保 backend 能连上 Neo4j、MySQL、Redis、Hadoop。 |
| 2 | **环境变量与密钥管理** | 将敏感信息（DB 密码、Neo4j 密码、DeepSeek API Key）从 compose 中抽到 `.env`，并在 `.env.example` 中列出占位说明；文档中注明生产环境务必修改默认密码。 |
| 3 | **编写 DEPLOYMENT.md** | 在 `docs/DEPLOYMENT.md` 中写清：本地 `docker-compose up` 步骤、端口说明、健康检查、首次初始化（DB 初始化脚本、默认账号等）。 |
| 4 | **云主机选型与基础环境** | 选定云厂商（如阿里云/腾讯云/华为云）及机型；在云主机上安装 Docker 与 Docker Compose，配置安全组（开放 5001、7474、7687、3307 等必要端口，仅允许可信 IP 或通过 LB 暴露）。 |
| 5 | **镜像构建与推送** | 在 CI 或本机使用 `docker build` 构建 backend、celery、hadoop 等镜像；打 tag 并推送到云厂商镜像仓库（或 Docker Hub），供云上 `docker-compose pull` 使用。 |
| 6 | **云上 Compose 部署** | 在云主机上拉取代码或仅拉取 `docker-compose.yml` + `.env`；执行 `docker-compose up -d`，确认所有服务 healthy；通过公网 IP:5001 访问 API 做冒烟测试。 |
| 7 | **持久化与备份** | 确认 MySQL、Neo4j、Redis、HDFS 等数据目录使用 named volume 或挂载云盘；文档中说明备份策略（如 mysqldump、Neo4j dump、Redis RDB）。 |
| 8 | **前端上云（可选）** | 将 Vue 前端构建为静态资源，部署到云上 Nginx 或对象存储+CDN；配置 Nginx 反向代理到后端 `http://backend:5001`，或前端 baseURL 指向云上后端地址。详见 **`docs/DEPLOYMENT_FRONTEND_STEP8.md`**。 |
| 9 | **HTTPS 与域名（可选）** | 为域名申请证书，在 Nginx 或 LB 上配置 HTTPS，将 API 和前端统一通过域名访问。 |

---

## 三、Hadoop MapReduce

| 序号 | 步骤 | 说明 |
|-----|------|------|
| 1 | **明确 MR 在流水线中的位置** | 当前批量构建使用「已提取文本 + 多线程调用 build」而非真实 MR。确定 MR 要替代的环节：例如「PDF 正文提取」「文本分块」「文本清洗」等，选 1～2 个作为 MR 阶段。 |
| 2 | **PDF 提取 MR 可运行性验证** | 在已有 `hadoop/mapreduce/pdf_extract` 下，用 `hadoop jar` 提交 WordCount 或现有 map/reduce 任务，在 Docker Hadoop 集群上跑通；确认 mapper/reducer 能从 HDFS 读输入、写输出，日志无 Python 环境错误。 |
| 3 | **文本清洗/分块 MR 设计** | 若采用「文本清洗」或「文本分块」为 MR：设计 mapper 输入（行或文件路径）、输出 key/value 格式；reducer 是否仅做合并或需二次处理；与现有 `text_clean`、`text_chunk` 的 Python 逻辑对应。 |
| 4 | **实现/调整 Mapper 与 Reducer** | 在 `hadoop/mapreduce/` 下实现或修改 mapper/reducer（可用 Python streaming 或 Jython）；保证在集群节点上可执行、能读 HDFS、写 HDFS；输出格式与下游「实体关系提取」或「build_single_file_kg」所需输入一致。 |
| 5 | **Hadoop Streaming 提交脚本** | 编写脚本（如 `scripts/submit_mr_pdf_extract.sh` 或 Python 调 `hadoop jar`）使用 Hadoop Streaming API 提交 MR 任务；参数化输入路径、输出路径、mapper/reducer 命令。 |
| 6 | **后端调用 MR 并消费结果** | 在 `backend/hadoop_api.py` 或 celery 任务中：先上传文件到 HDFS（已有能力），再提交 MR 任务并轮询完成；MR 完成后从 HDFS 读取输出（如每行一段文本），再调用现有「按文本块/build 单文件」逻辑写 Neo4j+MySQL。 |
| 7 | **MR 与批量构建接口打通** | 将「批量构建」接口改为可选路径：勾选「使用 Hadoop MR」时走「HDFS 上传 → 提交 MR → 读 MR 输出 → 多线程 build」；不勾选时保持当前「本地提取 + 多线程 build」行为。 |
| 8 | **文档与测试** | 在 README 或 `docs/` 中说明 MR 流程、输入输出目录约定、如何查看 YARN/HistoryServer 日志；增加一条端到端测试或脚本：上传样本 PDF → 触发 MR 构建 → 检查图谱是否写入。 |

---

## 使用建议

- **修复问题**：优先做 1～6，7～8 可按时间选做，便于课程答辩与演示。
- **Docker+上云**：1～3 可在本地完成；4～7 为云上部署主线；8～9 为体验增强。
- **Hadoop MR**：1～2 先打通跑通；3～5 实现具体 MR；6～8 与现有系统集成并文档化。

每完成一条可在上表中打勾或更新状态，便于跟踪进度。
