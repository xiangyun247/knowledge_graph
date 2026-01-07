# Hadoop MapReduce 任务模块

## 📁 目录结构

```
hadoop/
├── mapreduce/              # MapReduce 任务
│   ├── pdf_extract/        # PDF 文本提取任务
│   │   ├── mapper.py       # Mapper 脚本
│   │   └── reducer.py      # Reducer 脚本
│   ├── text_clean/         # 文本清洗任务
│   │   └── mapper.py       # Mapper 脚本
│   └── text_chunk/         # 文本分块任务
│       └── mapper.py       # Mapper 脚本
├── utils/                  # 工具函数
│   ├── hdfs_client.py      # HDFS 客户端封装
│   └── hadoop_utils.py     # Hadoop 工具函数
└── config/                 # 配置文件目录
```

## 🚀 任务说明

### 1. PDF 文本提取任务（pdf_extract）

**功能**：从 PDF 文件中提取文本内容

**输入**：HDFS 中的 PDF 文件路径列表

**输出**：文件路径 \t 提取的文本内容

**使用方法**：
```bash
# 使用 Hadoop Streaming 运行
hadoop jar hadoop-streaming.jar \
  -input /input/pdfs \
  -output /output/extracted \
  -mapper mapper.py \
  -reducer reducer.py \
  -file mapper.py \
  -file reducer.py
```

### 2. 文本清洗任务（text_clean）

**功能**：清洗医学文本，去除噪音和无关内容

**输入**：PDF 提取任务的输出（文件路径 \t 文本内容）

**输出**：文件路径 \t 清洗后的文本内容

**清洗规则**：
- 截断参考文献/致谢之后的内容
- 去除图表标题、页眉页脚
- 去除引用标记、URL、邮箱
- 保留医学相关内容

**使用方法**：
```bash
hadoop jar hadoop-streaming.jar \
  -input /output/extracted \
  -output /output/cleaned \
  -mapper mapper.py \
  -file mapper.py
```

### 3. 文本分块任务（text_chunk）

**功能**：将清洗后的文本分块，便于后续处理

**输入**：文本清洗任务的输出（文件路径 \t 文本内容）

**输出**：文件路径_块编号 \t 文本块内容

**分块规则**：
- 每块约 1000 字符
- 按词分割，保持完整性

**使用方法**：
```bash
hadoop jar hadoop-streaming.jar \
  -input /output/cleaned \
  -output /output/chunks \
  -mapper mapper.py \
  -file mapper.py
```

## 📝 使用流程

### 完整处理流程

```
1. 上传 PDF 文件到 HDFS
   hdfs dfs -put /local/pdfs/* /input/pdfs/

2. PDF 提取
   hadoop jar ... -input /input/pdfs -output /output/extracted ...

3. 文本清洗
   hadoop jar ... -input /output/extracted -output /output/cleaned ...

4. 文本分块
   hadoop jar ... -input /output/cleaned -output /output/chunks ...

5. 从 HDFS 下载处理结果
   hdfs dfs -get /output/chunks/* /local/chunks/
```

## 🔧 工具函数

### HDFSClient

用于与 HDFS 交互的客户端封装：

```python
from hadoop.utils.hdfs_client import HDFSClient

# 创建客户端
hdfs = HDFSClient(host="localhost", port=8020)  # Hadoop 3.x 使用 8020 端口

# 上传文件
hdfs.upload_file("/local/file.pdf", "/hdfs/file.pdf")

# 下载文件
hdfs.download_file("/hdfs/file.pdf", "/local/file.pdf")

# 列出文件
files = hdfs.list_files("/hdfs/directory")
```

### HadoopJobManager

用于管理 Hadoop 作业：

```python
from hadoop.utils.hadoop_utils import HadoopJobManager

# 创建管理器
manager = HadoopJobManager()

# 运行 MapReduce 任务
result = manager.run_mapreduce_job(
    input_path="/input",
    output_path="/output",
    mapper="mapper.py",
    reducer="reducer.py",
    files=["mapper.py", "reducer.py"],
    job_name="pdf_extract"
)
```

## ⚠️ 注意事项

1. **依赖安装**
   - PDF 提取需要 `pdfplumber` 库
   - 确保在所有 Hadoop 节点上安装依赖

2. **文件路径**
   - Mapper 和 Reducer 脚本需要上传到 HDFS 或使用 `-file` 参数

3. **输入输出格式**
   - 输入和输出使用制表符（\t）分隔
   - 文件路径和内容之间用 \t 分隔

4. **错误处理**
   - 所有任务都包含错误处理和日志记录
   - 错误信息会输出到 stderr

## 📚 参考资源

- Hadoop Streaming 文档：https://hadoop.apache.org/docs/stable/hadoop-streaming/HadoopStreaming.html
- Python MapReduce 编程：https://www.michael-noll.com/tutorials/writing-an-hadoop-mapreduce-program-in-python/

---

**创建时间**：2024年  
**版本**：v1.0


