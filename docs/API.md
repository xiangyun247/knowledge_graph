# API 接口说明

本文档描述前后端对接的主要 REST 接口。更多路由可查看后端启动后的 `/docs`（Swagger）。

## 历史记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/history/list` | 获取历史记录列表（支持 type、status、limit、offset） |
| GET | `/api/history/stats` | 获取历史统计 |
| GET | `/api/history/search` | 搜索历史（keyword、type、status） |
| POST | `/api/history/save` | 保存一条历史记录 |
| PUT | `/api/history/{history_id}/status` | 更新历史记录状态 |
| **DELETE** | **`/api/history/{history_id}`** | **删除单条历史记录** |
| **POST** | **`/api/history/batch-delete`** | **批量删除历史记录，请求体：`{ "history_ids": ["id1", "id2"] }` 或 `{ "ids": [...] }`** |
| **DELETE** | **`/api/history/clear`** | **清空全部历史记录** |

## 知识图谱

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/graph/list` | 获取图谱列表（当前用户） |
| GET | `/api/graph/data` | 获取图谱数据（可选 `graph_id`、`limit`） |
| GET | `/api/graph/entity/{entity_id}` | 获取实体详情 |
| GET | `/api/graph/relation/{relation_id}` | 获取关系详情 |
| **DELETE** | **`/api/graph/clear`** | **清空所有图谱（Neo4j + MySQL）** |
| **DELETE** | **`/api/graph/{graph_id}`** | **按 graph_id 删除单个图谱（仅 MySQL 元数据；需当前用户有权）** |

其他接口（Agent 问答、上传、KG 构建、知识库、Hadoop 等）见后端 `/docs`。
