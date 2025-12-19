# data/examples/README.md

# 示例数据说明

本目录包含用于测试和演示的医学知识样本数据。

## 文件列表

### 1. `sample_pancreatitis.txt`
- **内容**: 重症急性胰腺炎的完整临床知识
- **包含信息**:
  - 疾病概述和定义
  - 病因与危险因素
  - 临床表现和体征
  - 实验室检查指标
  - 影像学检查方法
  - 严重程度评估
  - 并发症
  - 治疗原则和方案
  - 预后和预防
  - 特殊类型
  - 护理要点
  - 健康教育
  - 最新进展

- **用途**: 
  - 知识图谱构建测试
  - RAG 系统功能演示
  - API 接口测试

- **数据来源**: 基于临床指南和医学文献编写

## 使用方法

### 1. 通过 API 导入

```bash
# 上传文件构建知识图谱
curl -X POST "http://localhost:8000/kg/build/file" \
  -F "file=@data/examples/sample_pancreatitis.txt"
  
 
### 2. 通过脚本导入
# 使用初始化脚本
python scripts/init_database.py --data data/examples/sample_pancreatitis.txt


### 3.通过编程导入
from kg import KGBuilder
from db import Neo4jClient
from llm import LLMClient

# 初始化
neo4j = Neo4jClient(...)
llm = LLMClient(...)
builder = KGBuilder(neo4j, llm)

# 读取文件
with open('data/examples/sample_pancreatitis.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# 构建知识图谱
result = await builder.build_from_text(text, source="sample_data")
print(f"已创建 {result['entities_count']} 个实体")
