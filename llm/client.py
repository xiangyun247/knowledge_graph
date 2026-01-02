"""
LLM 客户端 - DeepSeek API 封装

提供与 DeepSeek API 交互的统一接口
"""
import os
import logging
from typing import List, Dict, Any, Optional, Generator
from openai import OpenAI

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """DeepSeek LLM 客户端

    基于 OpenAI SDK 封装的 DeepSeek API 客户端
    """

    def __init__(
            self,
            api_key: Optional[str] = None,
            base_url: str = "https://api.deepseek.com",
            model: str = "deepseek-chat",
            timeout: int = 60
    ):
        """
        初始化 DeepSeek 客户端

        Args:
            api_key: DeepSeek API 密钥，默认从环境变量读取
            base_url: API 基础 URL
            model: 使用的模型名称
            timeout: 请求超时时间（秒）

        Raises:
            ValueError: 当 API 密钥未设置时
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

        if not self.api_key:
            raise ValueError(
                "DeepSeek API 密钥未设置。请设置环境变量 DEEPSEEK_API_KEY "
                "或在初始化时传入 api_key 参数"
            )

        # 初始化 OpenAI 客户端（DeepSeek 兼容 OpenAI API）
        try:
            # 手动创建 httpx.Client，避免 openai 库内部传递不支持的参数
            import httpx
            
            # 创建 httpx 客户端，不传递 proxies 参数（避免版本兼容性问题）
            http_client = httpx.Client(
                timeout=self.timeout,
                # 不传递 proxies 参数，即使 httpx 支持，openai 库内部可能处理不当
            )
            
            # 使用自定义的 http_client 初始化 OpenAI 客户端
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=http_client
            )
            logger.info(f"DeepSeek 客户端初始化成功 (模型: {self.model})")
        except Exception as e:
            logger.error(f"DeepSeek 客户端初始化失败: {e}")
            import traceback
            logger.error(f"详细错误信息:\n{traceback.format_exc()}")
            raise

    def chat(
            self,
            messages: List[Dict[str, str]],
            temperature: float = 0.7,
            max_tokens: int = 2000,
            stream: bool = False,
            **kwargs
    ) -> str:
        """
        聊天补全接口

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数 (0-2)，控制随机性
            max_tokens: 最大生成 token 数
            stream: 是否流式输出
            **kwargs: 其他 OpenAI API 参数

        Returns:
            生成的文本内容

        Raises:
            Exception: 当 API 调用失败时

        Examples:
            >>> client = DeepSeekClient()
            >>> messages = [
            ...     {"role": "system", "content": "你是一个医疗助手"},
            ...     {"role": "user", "content": "胰腺炎有什么症状？"}
            ... ]
            >>> response = client.chat(messages)
            >>> print(response)
        """
        try:
            logger.debug(f"发送聊天请求: {len(messages)} 条消息")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )

            if stream:
                # 流式输出暂不支持，返回错误提示
                logger.warning("流式输出暂未实现，使用非流式模式")
                return self.chat(messages, temperature, max_tokens, stream=False, **kwargs)

            content = response.choices[0].message.content
            logger.debug(f"收到响应: {len(content)} 字符")

            return content

        except Exception as e:
            logger.error(f"DeepSeek API 调用失败: {e}")
            raise

    def generate(
            self,
            prompt: str,
            system_prompt: Optional[str] = None,
            temperature: float = 0.7,
            max_tokens: int = 2000,
            **kwargs
    ) -> str:
        """
        简化的生成接口

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            **kwargs: 其他参数

        Returns:
            生成的文本内容

        Examples:
            >>> client = DeepSeekClient()
            >>> response = client.generate(
            ...     prompt="胰腺炎有什么症状？",
            ...     system_prompt="你是一个医疗助手"
            ... )
            >>> print(response)
        """
        messages = []

        # 添加系统提示
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        # 添加用户提示
        messages.append({
            "role": "user",
            "content": prompt
        })

        return self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

    def stream_chat(
            self,
            messages: List[Dict[str, str]],
            temperature: float = 0.7,
            max_tokens: int = 2000,
            **kwargs
    ) -> Generator[str, None, None]:
        """
        流式聊天补全接口

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            **kwargs: 其他参数

        Yields:
            生成的文本片段

        Examples:
            >>> client = DeepSeekClient()
            >>> messages = [{"role": "user", "content": "你好"}]
            >>> for chunk in client.stream_chat(messages):
            ...     print(chunk, end='')
        """
        try:
            logger.debug(f"发送流式聊天请求: {len(messages)} 条消息")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )

            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"DeepSeek 流式 API 调用失败: {e}")
            raise

    def get_embedding(self, text: str, model: str = "text-embedding-ada-002") -> List[float]:
        """
        获取文本嵌入向量

        注意：DeepSeek 目前可能不支持嵌入 API
        这里提供一个占位实现

        Args:
            text: 输入文本
            model: 嵌入模型名称

        Returns:
            嵌入向量（768维零向量作为占位）

        Todo:
            实现真实的嵌入 API 调用
        """
        logger.warning("DeepSeek 嵌入功能暂未实现，返回零向量占位")
        # 返回 768 维零向量作为占位符
        return [0.0] * 768

    def count_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量

        使用简单的启发式方法：中文按字符数，英文按单词数的 1.3 倍

        Args:
            text: 输入文本

        Returns:
            估算的 token 数量
        """
        # 简单估算：中文1字符≈1token，英文1单词≈1.3token
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        english_words = len(text.split()) - chinese_chars

        estimated_tokens = chinese_chars + int(english_words * 1.3)
        logger.debug(f"估算 token 数: {estimated_tokens}")

        return estimated_tokens

    def validate_messages(self, messages: List[Dict[str, str]]) -> bool:
        """
        验证消息格式是否正确

        Args:
            messages: 消息列表

        Returns:
            是否有效

        Raises:
            ValueError: 当消息格式无效时
        """
        if not messages:
            raise ValueError("消息列表不能为空")

        for msg in messages:
            if not isinstance(msg, dict):
                raise ValueError(f"消息必须是字典类型: {msg}")

            if "role" not in msg or "content" not in msg:
                raise ValueError(f"消息必须包含 'role' 和 'content' 字段: {msg}")

            if msg["role"] not in ["system", "user", "assistant"]:
                raise ValueError(f"无效的角色: {msg['role']}")

        return True

    def __repr__(self) -> str:
        """返回客户端的字符串表示"""
        return f"DeepSeekClient(model={self.model}, base_url={self.base_url})"


    def is_available(self) -> bool:
        """
        检查 LLM 是否可用

        通过调用 models.list() API 来验证连接

        Returns:
            bool: 如果 LLM 可用返回 True，否则返回 False
        """
        try:
            # 尝试获取模型列表来验证连接
            response = self.client.models.list()

            # 检查是否返回了模型列表
            if hasattr(response, 'data') and len(response.data) > 0:
                logger.info(f"LLM 健康检查成功，可用模型数: {len(response.data)}")
                return True
            else:
                logger.warning("LLM 返回了空的模型列表")
                return False

        except Exception as e:
            logger.error(f"LLM 健康检查失败: {type(e).__name__}: {e}")
            # 打印详细错误信息用于调试
            import traceback
            logger.debug(f"详细错误:\n{traceback.format_exc()}")
            return False

    def verify_connection(self) -> bool:
        return self.is_available()

    def close(self) -> None:
        """
        关闭客户端，释放资源。

        目前 openai/DeepSeek 官方 client 通常不强制要求显式关闭，
        这里主要是为了兼容脚本中的 llm_client.close() 调用。
        如果内部 client 支持 close()，则尝试调用一次。
        """
        try:
            # 如果底层 client 自己有 close 方法，就顺手调一下
            if hasattr(self.client, "close") and callable(self.client.close):
                self.client.close()
                logger.info("DeepSeek 客户端已关闭底层连接")
        except Exception as e:
            # 失败也不要让整个程序崩，打个日志就行
            logger.warning(f"关闭 DeepSeek 客户端时发生异常: {type(e).__name__}: {e}")
# 向后兼容的别名
LLMClient = DeepSeekClient


# ==================== 工具函数 ====================

def create_client(
        api_key: Optional[str] = None,
        model: str = "deepseek-chat"
) -> DeepSeekClient:
    """
    创建 DeepSeek 客户端的便捷函数

    Args:
        api_key: API 密钥
        model: 模型名称

    Returns:
        DeepSeekClient 实例

    Examples:
        >>> client = create_client()
        >>> response = client.generate("你好")
    """
    return DeepSeekClient(api_key=api_key, model=model)


def format_messages(
        user_message: str,
        system_message: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None
) -> List[Dict[str, str]]:
    """
    格式化消息列表

    Args:
        user_message: 用户消息
        system_message: 系统消息
        history: 历史对话

    Returns:
        格式化的消息列表

    Examples:
        >>> messages = format_messages(
        ...     user_message="你好",
        ...     system_message="你是一个助手"
        ... )
        >>> print(messages)
        [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "你好"}
        ]
    """
    messages = []

    # 添加系统消息
    if system_message:
        messages.append({
            "role": "system",
            "content": system_message
        })

    # 添加历史对话
    if history:
        messages.extend(history)

    # 添加当前用户消息
    messages.append({
        "role": "user",
        "content": user_message
    })

    return messages


# ==================== 模块级别的便捷实例 ====================

# 默认客户端实例（延迟初始化）
_default_client: Optional[DeepSeekClient] = None


def get_default_client() -> DeepSeekClient:
    """
    获取默认的 DeepSeek 客户端实例（单例模式）

    Returns:
        DeepSeekClient 实例
    """
    global _default_client

    if _default_client is None:
        _default_client = DeepSeekClient()

    return _default_client


# ==================== 嵌入客户端 ====================

class EmbeddingClient:
    """
    嵌入向量客户端

    支持两种模式：
    1. 本地模型（sentence-transformers）：使用预训练的中文模型
    2. API 服务（OpenAI 兼容）：使用远程 API
    3. 占位模式：返回零向量（当以上两种都不可用时）
    """

    def __init__(
            self,
            use_local: Optional[bool] = None,
            local_model: Optional[str] = None,
            api_key: Optional[str] = None,
            base_url: str = "https://api.openai.com/v1",
            api_model: str = "text-embedding-ada-002",
            embedding_dim: Optional[int] = None
    ):
        """
        初始化嵌入客户端

        Args:
            use_local: 是否使用本地模型，默认从环境变量读取
            local_model: 本地模型名称，默认从环境变量读取
            api_key: API 密钥（如使用 OpenAI）
            base_url: API 基础 URL
            api_model: API 模型名称
            embedding_dim: 嵌入向量维度，默认根据模型自动检测
        """
        import config
        
        # 从环境变量或参数获取配置
        self.use_local = use_local if use_local is not None else config.USE_LOCAL_EMBEDDING
        self.local_model = local_model or config.LOCAL_EMBEDDING_MODEL
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.api_model = api_model
        
        # 初始化标志
        self.local_encoder = None
        self.api_client = None
        self.embedding_dim = embedding_dim or config.EMBEDDING_DIM
        
        # 优先使用本地模型
        if self.use_local:
            try:
                logger.info(f"Loading local Embedding model: {self.local_model}")
                from sentence_transformers import SentenceTransformer
                
                # 加载模型（首次运行会自动下载）
                self.local_encoder = SentenceTransformer(self.local_model)
                
                # 获取模型的实际维度
                if embedding_dim is None:
                    # 测试编码一个短文本以获取维度
                    test_embedding = self.local_encoder.encode("测试", convert_to_numpy=False)
                    self.embedding_dim = len(test_embedding)
                
                logger.info(f"[OK] Local Embedding model loaded successfully (model: {self.local_model}, dim: {self.embedding_dim})")
            except ImportError:
                logger.error("[ERROR] sentence-transformers not installed, please run: pip install sentence-transformers")
                self.local_encoder = None
            except Exception as e:
                logger.error(f"[ERROR] Local model loading failed: {e}, will try API or placeholder")
                self.local_encoder = None
        
        # 如果本地模型不可用，尝试使用 API
        if not self.local_encoder and self.api_key:
            try:
                self.api_client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                logger.info(f"[OK] Embedding API client initialized successfully (model: {self.api_model})")
            except Exception as e:
                logger.warning(f"⚠️  API 客户端初始化失败: {e}，将使用占位向量")
                self.api_client = None
        
        # 如果都不可用，使用占位模式
        if not self.local_encoder and not self.api_client:
            logger.warning("[WARN] Embedding model not configured, will use placeholder vectors (vector retrieval will be unavailable)")

    def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        # 优先使用本地模型
        if self.local_encoder:
            try:
                # 使用 sentence-transformers 编码
                embedding = self.local_encoder.encode(
                    text,
                    convert_to_numpy=False,  # 返回 Python list
                    normalize_embeddings=True  # 归一化向量，提高相似度计算准确性
                )
                # 确保返回 Python list
                if isinstance(embedding, list):
                    return embedding
                elif hasattr(embedding, 'tolist'):
                    return embedding.tolist()
                else:
                    return list(embedding)
            except Exception as e:
                logger.error(f"本地模型编码失败: {e}，尝试使用 API")
                # 降级到 API
                if self.api_client:
                    return self._get_embedding_from_api(text)
                return self._get_placeholder_embedding()
        
        # 其次使用 API
        if self.api_client:
            return self._get_embedding_from_api(text)
        
        # 最后使用占位向量
        return self._get_placeholder_embedding()
    
    def _get_embedding_from_api(self, text: str) -> List[float]:
        """从 API 获取嵌入向量"""
        try:
            response = self.api_client.embeddings.create(
                input=text,
                model=self.api_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"API 获取嵌入向量失败: {e}，返回占位向量")
            return self._get_placeholder_embedding()

    def encode_single(self, text: str) -> List[float]:
        """
        兼容旧代码使用的接口名。
        内部直接调用 get_embedding。
        """
        return self.get_embedding(text)

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取嵌入向量（批量处理更高效）

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        # 优先使用本地模型（批量处理更高效）
        if self.local_encoder:
            try:
                embeddings = self.local_encoder.encode(
                    texts,
                    convert_to_numpy=False,
                    normalize_embeddings=True,
                    batch_size=32,  # 批量处理，提高效率
                    show_progress_bar=False
                )
                # 转换为列表格式
                if hasattr(embeddings, 'tolist'):
                    return [emb.tolist() for emb in embeddings]
                return [list(emb) for emb in embeddings]
            except Exception as e:
                logger.error(f"本地模型批量编码失败: {e}，尝试使用 API")
                if self.api_client:
                    return self._get_embeddings_from_api(texts)
                return [self._get_placeholder_embedding() for _ in texts]
        
        # 使用 API
        if self.api_client:
            return self._get_embeddings_from_api(texts)
        
        # 占位向量
        return [self._get_placeholder_embedding() for _ in texts]
    
    def _get_embeddings_from_api(self, texts: List[str]) -> List[List[float]]:
        """从 API 批量获取嵌入向量"""
        try:
            response = self.api_client.embeddings.create(
                input=texts,
                model=self.api_model
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"API 批量获取嵌入向量失败: {e}，返回占位向量")
            return [self._get_placeholder_embedding() for _ in texts]

    def _get_placeholder_embedding(self) -> List[float]:
        """
        生成占位嵌入向量（零向量）

        Returns:
            占位嵌入向量
        """
        # 返回零向量作为占位
        # 注意：这只是占位，不具备语义相似性
        return [0.0] * self.embedding_dim
    
    def is_available(self) -> bool:
        """
        检查 Embedding 客户端是否可用

        Returns:
            True 如果本地模型或 API 可用，False 如果只能使用占位向量
        """
        return self.local_encoder is not None or self.api_client is not None
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            包含模型信息的字典
        """
        info = {
            "mode": "placeholder",
            "model": None,
            "dimension": self.embedding_dim,
            "available": False
        }
        
        if self.local_encoder:
            info.update({
                "mode": "local",
                "model": self.local_model,
                "available": True
            })
        elif self.api_client:
            info.update({
                "mode": "api",
                "model": self.api_model,
                "available": True
            })
        
        return info

    def __repr__(self) -> str:
        if self.local_encoder:
            return f"EmbeddingClient(mode=local, model={self.local_model}, dim={self.embedding_dim})"
        elif self.api_client:
            return f"EmbeddingClient(mode=api, model={self.api_model}, dim={self.embedding_dim})"
        else:
            return f"EmbeddingClient(mode=placeholder, dim={self.embedding_dim})"
