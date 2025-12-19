"""
PDF 医疗文档导入脚本（优化版）
场景：医学论文 / 疾病指南 / 健康指南等 PDF

流程：
1. 从 PDF 提取原始文本
2. 针对医学场景进行文本清洗：
   - 切掉参考文献/致谢之后的内容
   - 去掉图表标题、表格、页眉页脚等噪音
   - 删除文献引用标记、URL、邮箱等
3. 将清洗后的纯文本按段切分
4. 交给 KnowledgeGraphBuilder.process_text 构建知识图谱
"""

import sys
import time
import re
from pathlib import Path
from typing import Dict, Any, List

# 把项目根目录加入 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
import config
from db.neo4j_client import Neo4jClient
from llm.client import LLMClient, EmbeddingClient
from kg.builder import KnowledgeGraphBuilder

# 日志配置
logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    从 PDF 文件中提取全部原始文本（未清洗）

    Args:
        pdf_path: PDF 文件路径

    Returns:
        提取到的全部文本（字符串）
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error(
            "未安装 pdfplumber 库，无法解析 PDF。\n"
            "请先运行: pip install pdfplumber"
        )
        raise

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    logger.info(f"开始从 PDF 提取文本: {pdf_file}")

    texts: List[str] = []
    with pdfplumber.open(pdf_file) as pdf:
        logger.info(f"PDF 共 {len(pdf.pages)} 页")
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            # 粗暴去掉多余空白
            page_text = page_text.replace("\u00a0", " ")
            logger.info(f"第 {i + 1}/{len(pdf.pages)} 页，提取 {len(page_text)} 字符")
            texts.append(page_text)

    full_text = "\n\n".join(texts)
    logger.info(f"PDF 文本提取完成，总长度 {len(full_text)} 字符")
    return full_text


def clean_medical_text(raw_text: str) -> str:
    """
    针对医学论文 / 指南的文本进行清洗，只保留相对有用的医学正文内容

    主要操作：
    1. 截断参考文献/致谢之后的内容
    2. 过滤掉图表标题、页眉页脚、纯数字/符号行
    3. 删除行内的参考文献标记、URL、邮箱等

    Args:
        raw_text: 原始 PDF 文本

    Returns:
        清洗后的文本
    """
    if not raw_text:
        return ""

    # 统一换行符
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # 1) 按参考文献/致谢截断
    cutoff_patterns = [
        r"^\s*参考文献\s*$",
        r"^\s*参考资料\s*$",
        r"^\s*致谢\s*$",
        r"^\s*Acknowledg?ement[s]?\s*$",
        r"^\s*References\s*$",
        r"^\s*BIBLIOGRAPHY\s*$",
        r"^\s*Bibliography\s*$",
    ]
    cutoff_regex = re.compile("|".join(cutoff_patterns), re.IGNORECASE)

    lines = text.split("\n")
    filtered_lines: List[str] = []

    medical_keywords = [
        "炎", "癌", "综合征", "综合症", "症", "疾病", "病因", "病程", "病理", "病变",
        "诊断", "治疗", "用药", "药物", "方案", "疗法", "干预", "预后", "预防",
        "风险", "危险因素", "并发症", "感染", "出血", "坏死",
        "患者", "病人", "临床", "指南", "推荐", "随访", "复发",
        "胰腺", "胰腺炎", "胰腺癌", "肝", "肾", "心功能",
        # 英文
        "pancreatitis", "pancreas", "acute", "chronic",
        "disease", "syndrome", "disorder",
        "treatment", "therapy", "management",
        "diagnosis", "diagnostic",
        "clinical", "patient", "patients",
        "risk", "factor", "complication", "outcome", "prognosis"
    ]

    def looks_like_figure_or_table(line: str) -> bool:
        line_strip = line.strip()
        # 图表标题
        if re.match(r"^(图|表)\s*\d+", line_strip):
            return True
        if re.match(r"^(Figure|Fig\.?|Table|TAB\.)\s*\d+", line_strip, re.IGNORECASE):
            return True
        return False

    def is_mostly_numeric_or_garbage(line: str) -> bool:
        # 太短的行另一套逻辑处理，这里只针对有些长度但内容是数字/符号的
        if len(line) < 6:
            return True
        chars = [c for c in line if not c.isspace()]
        if not chars:
            return True
        digits = sum(c.isdigit() for c in chars)
        punct = sum(c in ".,;:[]()%+-=<>/\\|~" for c in chars)
        ratio = (digits + punct) / max(len(chars), 1)
        return ratio > 0.6

    def contains_medical_keyword(line: str) -> bool:
        lower = line.lower()
        return any(k in line or k in lower for k in medical_keywords)

    # 2) 逐行处理 + 截断参考文献
    for line in lines:
        # 截断逻辑：遇到参考文献 / 致谢等直接结束
        if cutoff_regex.match(line):
            logger.info(f"检测到参考文献/致谢标记行: {line.strip()}，后续内容将被忽略")
            break

        line_strip = line.strip()
        if not line_strip:
            continue

        # 页眉页脚粗略过滤：带 Page / 页 / 期刊号等且几乎没医学词
        if re.search(r"Page\s+\d+\s+of\s+\d+", line_strip, re.IGNORECASE):
            continue
        if re.search(r"第\s*\d+\s*页", line_strip):
            continue

        # 图表标题
        if looks_like_figure_or_table(line_strip):
            continue

        # 纯数字/符号
        if is_mostly_numeric_or_garbage(line_strip):
            continue

        # 很短且不含医学关键词 → 丢掉（大概率是栏目标题/垃圾排版）
        if len(line_strip) < 15 and not contains_medical_keyword(line_strip):
            continue

        # 加入后续清洗流程
        filtered_lines.append(line_strip)

    # 3) 行内轻量清洗
    cleaned_lines: List[str] = []
    for line in filtered_lines:
        # 删掉 [1] [2-5] 这类引用标记
        line = re.sub(r"\[[0-9,\-\s]+\]", "", line)

        # 删除简单括号内文献引用，例如 (Smith 2020), (Wang et al., 2019)
        line = re.sub(r"\([A-Z][A-Za-z].{0,40}?\d{4}\)", "", line)

        # 去掉 URL
        line = re.sub(r"http[s]?://\S+", "", line)

        # 去掉邮箱
        line = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "", line)

        # 多空格压缩
        line = re.sub(r"\s{2,}", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines)
    logger.info(f"清洗后文本长度: {len(cleaned_text)} 字符（原始 {len(raw_text)}）")
    return cleaned_text


def import_pdf_to_kg(
    pdf_path: str,
    kg_builder: KnowledgeGraphBuilder,
    chunk_size: int = 1000,
    sleep_sec: float = 1.0
) -> Dict[str, Any]:
    """
    从 PDF 导入知识到图谱（带医疗场景清洗）

    Args:
        pdf_path: PDF 文件路径
        kg_builder: 知识图谱构建器实例
        chunk_size: 每个分段的字符数
        sleep_sec: 每段之间的休眠时间（秒）

    Returns:
        导入统计信息字典
    """
    # 1. 提取 PDF 原始文本
    raw_text = extract_text_from_pdf(pdf_path)

    # 2. 医学场景清洗
    clean_text = clean_medical_text(raw_text)

    if not clean_text.strip():
        logger.warning("清洗后文本内容为空，跳过导入")
        return {
            "total_chunks": 0,
            "processed_chunks": 0,
            "entities_created": 0,
            "relations_created": 0,
            "errors": 0,
        }

    # 3. 分段
    chunks = [
        clean_text[i:i + chunk_size]
        for i in range(0, len(clean_text), chunk_size)
    ]
    logger.info(f"清洗文本分为 {len(chunks)} 段（chunk_size={chunk_size}）")

    stats = {
        "total_chunks": len(chunks),
        "processed_chunks": 0,
        "entities_created": 0,
        "relations_created": 0,
        "errors": 0,
    }

    # 4. 对每个文本段调用 KnowledgeGraphBuilder
    for idx, chunk in enumerate(chunks, start=1):
        logger.info(f"处理第 {idx}/{len(chunks)} 段...")
        try:
            result = kg_builder.process_text(chunk)

            stats["processed_chunks"] += 1

            # 根据你的实际返回结构做兜底
            entities = (
                result.get("entities_created")
                or result.get("entity_count")
                or 0
            )
            relations = (
                result.get("relations_created")
                or result.get("relation_count")
                or 0
            )

            stats["entities_created"] += entities
            stats["relations_created"] += relations

            logger.info(
                f"✓ 第 {idx} 段处理完成: "
                f"新增实体={entities}, 新增关系={relations}"
            )

            if sleep_sec > 0:
                time.sleep(sleep_sec)

        except Exception as e:
            logger.error(f"处理第 {idx} 段失败: {e}")
            stats["errors"] += 1

    logger.info(f"PDF 导入完成: {stats}")
    return stats


def main():
    print("=" * 70)
    print("📄 PDF 医学文献导入工具（带清洗）")
    print("=" * 70)

    # 1. 获取 PDF 路径
    if len(sys.argv) >= 2:
        pdf_path = sys.argv[1]
    else:
        pdf_path = input("请输入 PDF 文件路径: ").strip()

    if not pdf_path:
        print("❌ 未提供 PDF 路径，退出")
        return

    # 2. 创建客户端
    logger.info("正在初始化服务...")

    neo4j_client = None
    llm_client = None
    embedding_client = None

    try:
        neo4j_client = Neo4jClient()
        if not neo4j_client.verify_connection():
            logger.error("❌ Neo4j 连接失败")
            return

        llm_client = LLMClient()
        if not llm_client.verify_connection():
            logger.error("❌ LLM 连接失败")
            return

        embedding_client = EmbeddingClient()

        # 3. 创建知识图谱构建器
        kg_builder = KnowledgeGraphBuilder(
            neo4j_client=neo4j_client,
            llm_client=llm_client,
        )

        # 4. 导入 PDF
        stats = import_pdf_to_kg(pdf_path, kg_builder)

        print("\n✅ PDF 导入完成!")
        print(f"   文本分段: {stats['processed_chunks']}/{stats['total_chunks']}")
        print(f"   新增实体: {stats['entities_created']}")
        print(f"   新增关系: {stats['relations_created']}")
        print(f"   出错段数: {stats['errors']}")

    except KeyboardInterrupt:
        print("\n⏹️  导入已取消")
    except Exception as e:
        logger.error(f"导入过程发生异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 5. 关闭连接
        if neo4j_client:
            neo4j_client.close()
        if llm_client:
            # 你已经给 DeepSeekClient 实现了 close()
            llm_client.close()
        logger.info("连接已关闭")

        print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
