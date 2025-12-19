"""
系统测试脚本
测试各个组件的功能
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ⚠️ 关键修复：必须先导入 config
import config

# 然后导入其他模块
import logging
import time
from typing import Dict, Any

from db.neo4j_client import Neo4jClient
from llm.client import LLMClient, EmbeddingClient
from rag.rag_pipeline import RAGPipeline
from rag.query_parser import QueryParser
from rag.graph_retriever import GraphRetriever

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 改为硬编码，避免依赖 config.LOG_LEVEL
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemTester:
    """系统测试器"""

    def __init__(self):
        """初始化测试器"""
        self.neo4j_client = None
        self.llm_client = None
        self.embedding_client = None
        self.test_results = []

    def setup(self) -> bool:
        """
        初始化测试环境

        Returns:
            是否成功
        """
        print("\n" + "=" * 60)
        print("初始化测试环境")
        print("=" * 60)

        try:
            # 创建客户端
            print("正在创建客户端...")
            self.neo4j_client = Neo4jClient()
            self.llm_client = LLMClient()
            self.embedding_client = EmbeddingClient()

            print("✓ 客户端创建成功")
            return True

        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def teardown(self):
        """清理测试环境"""
        print("\n清理测试环境...")

        if self.neo4j_client:
            self.neo4j_client.close()
            print("✓ Neo4j 连接已关闭")

        if self.llm_client:
            self.llm_client.close()
            print("✓ LLM 客户端已关闭")

    def test_neo4j_connection(self) -> Dict[str, Any]:
        """测试 Neo4j 连接"""
        print("\n[测试 1/7] Neo4j 连接测试")
        print("-" * 60)

        start_time = time.time()

        try:
            # 测试连接
            is_connected = self.neo4j_client.verify_connection()

            if is_connected:
                # 获取统计信息
                stats = self.neo4j_client.get_statistics()

                elapsed = time.time() - start_time

                print(f"✓ 连接成功 ({elapsed:.2f}秒)")
                print(f"  节点数: {stats.get('node_count', 0)}")
                print(f"  关系数: {stats.get('relationship_count', 0)}")

                return {"status": "PASS", "time": elapsed, "details": stats}
            else:
                print("❌ 连接失败")
                return {"status": "FAIL", "error": "连接失败"}

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            return {"status": "FAIL", "error": str(e)}

    def test_llm_connection(self) -> Dict[str, Any]:
        """测试 LLM 连接"""
        print("\n[测试 2/7] LLM 连接测试")
        print("-" * 60)

        start_time = time.time()

        try:
            # 测试连接
            is_connected = self.llm_client.verify_connection()

            elapsed = time.time() - start_time

            if is_connected:
                print(f"✓ 连接成功 ({elapsed:.2f}秒)")
                return {"status": "PASS", "time": elapsed}
            else:
                print("❌ 连接失败")
                return {"status": "FAIL", "error": "连接失败"}

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            return {"status": "FAIL", "error": str(e)}

    def test_embedding_client(self) -> Dict[str, Any]:
        """测试 Embedding 客户端"""
        print("\n[测试 3/7] Embedding 客户端测试")
        print("-" * 60)

        start_time = time.time()

        try:
            # 测试编码
            test_text = "这是一个测试文本"
            embedding = self.embedding_client.encode_single(test_text)

            elapsed = time.time() - start_time

            if embedding and len(embedding) > 0:
                print(f"✓ 编码成功 ({elapsed:.2f}秒)")
                print(f"  向量维度: {len(embedding)}")
                return {"status": "PASS", "time": elapsed, "dimension": len(embedding)}
            else:
                print("❌ 编码失败")
                return {"status": "FAIL", "error": "编码结果为空"}

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            return {"status": "FAIL", "error": str(e)}

    def test_query_parser(self) -> Dict[str, Any]:
        """测试查询解析器"""
        print("\n[测试 4/7] 查询解析器测试")
        print("-" * 60)

        start_time = time.time()

        try:
            # 创建解析器
            parser = QueryParser(self.llm_client)

            # 测试查询
            test_query = "什么是重症急性胰腺炎？"
            result = parser.parse(test_query)

            elapsed = time.time() - start_time

            print(f"✓ 解析成功 ({elapsed:.2f}秒)")
            print(f"  意图: {result.get('intent')}")
            print(f"  实体数: {len(result.get('entities', []))}")
            print(f"  关键词: {result.get('keywords')}")

            return {
                "status": "PASS",
                "time": elapsed,
                "intent": result.get("intent"),
                "entity_count": len(result.get("entities", []))
            }

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "FAIL", "error": str(e)}

    def test_graph_retriever(self) -> Dict[str, Any]:
        """测试图检索器"""
        print("\n[测试 5/7] 图检索器测试")
        print("-" * 60)

        start_time = time.time()

        try:
            # 创建检索器
            retriever = GraphRetriever(self.neo4j_client)

            # 测试检索
            test_entities = ["重症急性胰腺炎", "急性胰腺炎"]
            results = retriever.retrieve(
                query="什么是重症急性胰腺炎？",
                entity_names=test_entities,
                max_depth=2,
                limit=5
            )

            elapsed = time.time() - start_time

            print(f"✓ 检索成功 ({elapsed:.2f}秒)")
            print(f"  检索结果数: {len(results)}")

            if results:
                print(f"  首个结果: {results[0].get('name', 'N/A')}")

            return {
                "status": "PASS",
                "time": elapsed,
                "result_count": len(results)
            }

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "FAIL", "error": str(e)}

    def test_rag_pipeline(self) -> Dict[str, Any]:
        """测试 RAG 流水线"""
        print("\n[测试 6/7] RAG 流水线测试")
        print("-" * 60)

        start_time = time.time()

        try:
            # 创建流水线
            pipeline = RAGPipeline(
                neo4j_client=self.neo4j_client,
                llm_client=self.llm_client,
                embedding_client=self.embedding_client
            )

            # 测试问答
            test_query = "什么是重症急性胰腺炎？"
            result = pipeline.answer(test_query)

            elapsed = time.time() - start_time

            print(f"✓ 问答成功 ({elapsed:.2f}秒)")
            print(f"  答案长度: {len(result.get('answer', ''))}")
            print(f"  信息来源数: {len(result.get('sources', []))}")
            print(f"  置信度: {result.get('confidence', 0):.2f}")
            print(f"\n  答案摘要: {result.get('answer', '')[:100]}...")

            return {
                "status": "PASS",
                "time": elapsed,
                "answer_length": len(result.get("answer", "")),
                "confidence": result.get("confidence", 0)
            }

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "FAIL", "error": str(e)}

    def test_end_to_end(self) -> Dict[str, Any]:
        """端到端测试"""
        print("\n[测试 7/7] 端到端测试")
        print("-" * 60)

        start_time = time.time()

        try:
            # 创建流水线
            pipeline = RAGPipeline(
                neo4j_client=self.neo4j_client,
                llm_client=self.llm_client,
                embedding_client=self.embedding_client
            )

            # 测试多个查询
            test_queries = [
                "胰腺炎有哪些症状？",
                "如何治疗急性胰腺炎？",
                "胰腺炎的常见病因是什么？"
            ]

            success_count = 0

            for query in test_queries:
                try:
                    result = pipeline.answer(query, use_graph=True, use_vector=False)
                    if result.get("answer"):
                        success_count += 1
                        print(f"  ✓ {query[:20]}... ({len(result['answer'])} 字)")
                except Exception as e:
                    print(f"  ❌ {query[:20]}... ({e})")

            elapsed = time.time() - start_time

            print(f"\n✓ 测试完成 ({elapsed:.2f}秒)")
            print(f"  成功率: {success_count}/{len(test_queries)}")

            return {
                "status": "PASS" if success_count == len(test_queries) else "PARTIAL",
                "time": elapsed,
                "success_rate": f"{success_count}/{len(test_queries)}"
            }

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "FAIL", "error": str(e)}

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("胰腺炎知识图谱 RAG 系统 - 功能测试")
        print("=" * 60)

        # 初始化
        if not self.setup():
            print("\n❌ 初始化失败，测试终止")
            return

        try:
            # 运行测试
            tests = [
                ("Neo4j 连接", self.test_neo4j_connection),
                ("LLM 连接", self.test_llm_connection),
                ("Embedding 客户端", self.test_embedding_client),
                ("查询解析器", self.test_query_parser),
                ("图检索器", self.test_graph_retriever),
                ("RAG 流水线", self.test_rag_pipeline),
                ("端到端测试", self.test_end_to_end)
            ]

            results = []

            for test_name, test_func in tests:
                result = test_func()
                results.append((test_name, result))
                self.test_results.append(result)

            # 显示测试摘要
            self._print_summary(results)

        finally:
            # 清理
            self.teardown()

    def _print_summary(self, results):
        """打印测试摘要"""
        print("\n" + "=" * 60)
        print("测试摘要")
        print("=" * 60)

        pass_count = sum(1 for _, r in results if r.get("status") == "PASS")
        fail_count = sum(1 for _, r in results if r.get("status") == "FAIL")
        partial_count = sum(1 for _, r in results if r.get("status") == "PARTIAL")

        print(f"\n总测试数: {len(results)}")
        print(f"通过: {pass_count} ✓")
        print(f"部分通过: {partial_count} ~")
        print(f"失败: {fail_count} ✗")

        print("\n详细结果:")
        for test_name, result in results:
            status_icon = {
                "PASS": "✓",
                "FAIL": "✗",
                "PARTIAL": "~"
            }.get(result.get("status"), "?")

            time_info = f" ({result.get('time', 0):.2f}s)" if "time" in result else ""
            print(f"  {status_icon} {test_name}{time_info}")

            if result.get("error"):
                print(f"    错误: {result['error']}")

        print("\n" + "=" * 60)

        if fail_count == 0:
            print("🎉 所有测试通过！")
        else:
            print(f"⚠️  有 {fail_count} 个测试失败")

        print("=" * 60 + "\n")


def main():
    """主函数"""
    tester = SystemTester()

    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⏹️  测试已取消")
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
