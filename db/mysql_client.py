import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MySQLClient:
    def __init__(self, host=None, port=None, user=None, password=None, database=None):
        # 从参数获取MySQL连接信息，如果参数为空则从环境变量获取
        self.host = host or os.getenv("MYSQL_HOST", "localhost")
        self.port = port or int(os.getenv("MYSQL_PORT", 3306))
        self.user = user or os.getenv("MYSQL_USER", "root")
        self.password = password or os.getenv("MYSQL_PASSWORD", "")
        self.database = database or os.getenv("MYSQL_DATABASE", "knowledge_graph")
        self.engine = None
        
    def connect(self):
        """建立数据库连接"""
        try:
            # 使用pymysql创建SQLAlchemy引擎
            self.engine = create_engine(
                f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
            )
            # 测试连接
            with self.engine.connect():
                logger.info(f"成功连接到MySQL数据库: {self.database}")
            return True
        except Exception as e:
            logger.error(f"连接MySQL数据库失败: {e}")
            return False
    
    def disconnect(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            logger.info("MySQL数据库连接已关闭")
    
    def execute_query(self, query, params=None):
        """执行查询（SELECT）"""
        try:
            if not self.engine:
                self.connect()
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                return result.mappings().all()  # 返回字典形式的结果
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            raise e
    
    def execute_update(self, query, params=None):
        """执行更新（INSERT, UPDATE, DELETE）"""
        try:
            if not self.engine:
                self.connect()
            
            with self.engine.begin() as conn:  # 自动管理事务
                result = conn.execute(text(query), params or {})
                return result.rowcount
        except Exception as e:
            logger.error(f"执行更新失败: {e}")
            raise e
    
    def execute_sql_file(self, file_path):
        """执行SQL文件"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"SQL文件不存在: {file_path}")
            
            if not self.engine:
                self.connect()
            
            with open(file_path, 'r', encoding='utf-8') as file:
                sql_script = file.read()
            
            # 分割SQL脚本为多个语句
            sql_statements = sql_script.split(';')
            
            with self.engine.begin() as conn:  # 自动管理事务
                for statement in sql_statements:
                    statement = statement.strip()
                    if statement and not statement.startswith('--'):
                        conn.execute(text(statement))
            
            logger.info(f"成功执行SQL文件: {file_path}")
            return True
        except Exception as e:
            logger.error(f"执行SQL文件失败: {e}")
            raise e
    
    # 知识图谱相关方法
    def create_graph(self, graph_name, description="", data_source="", file_path="", user_id=""):
        """创建新的知识图谱记录"""
        graph_id = str(uuid.uuid4())
        query = """
        INSERT INTO knowledge_graphs (graph_id, graph_name, description, data_source, file_path, user_id)
        VALUES (:graph_id, :graph_name, :description, :data_source, :file_path, :user_id)
        """
        params = {
            "graph_id": graph_id,
            "graph_name": graph_name,
            "description": description,
            "data_source": data_source,
            "file_path": file_path,
            "user_id": user_id
        }
        self.execute_update(query, params)
        return graph_id
    
    def get_graphs(self, status=None, user_id=None, limit=100, offset=0):
        """获取知识图谱列表"""
        query = "SELECT * FROM knowledge_graphs WHERE 1=1"
        params = {}
        
        if status:
            query += " AND status = :status"
            params["status"] = status
        
        if user_id:
            query += " AND user_id = :user_id"
            params["user_id"] = user_id
        
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        return self.execute_query(query, params)
    
    def get_graph_by_id(self, graph_id):
        """根据ID获取知识图谱详情"""
        query = "SELECT * FROM knowledge_graphs WHERE graph_id = :graph_id"
        params = {"graph_id": graph_id}
        result = self.execute_query(query, params)
        return result[0] if result else None
    
    def update_graph_status(self, graph_id, status, entity_count=None, relation_count=None):
        """更新知识图谱状态"""
        query = "UPDATE knowledge_graphs SET status = :status"
        params = {
            "status": status,
            "graph_id": graph_id
        }
        
        if entity_count is not None:
            query += ", entity_count = :entity_count"
            params["entity_count"] = entity_count
        
        if relation_count is not None:
            query += ", relation_count = :relation_count"
            params["relation_count"] = relation_count
        
        query += " WHERE graph_id = :graph_id"
        
        return self.execute_update(query, params)
    
    def delete_graph(self, graph_id):
        """删除知识图谱"""
        query = "DELETE FROM knowledge_graphs WHERE graph_id = :graph_id"
        params = {"graph_id": graph_id}
        return self.execute_update(query, params)
    
    # 历史记录相关方法
    def create_history(self, graph_id, user_id, operation_type, operation_content=""):
        """创建历史记录"""
        history_id = str(uuid.uuid4())
        query = """
        INSERT INTO history_records (history_id, graph_id, user_id, operation_type, operation_content)
        VALUES (:history_id, :graph_id, :user_id, :operation_type, :operation_content)
        """
        params = {
            "history_id": history_id,
            "graph_id": graph_id,
            "user_id": user_id,
            "operation_type": operation_type,
            "operation_content": operation_content
        }
        self.execute_update(query, params)
        return history_id
    
    def get_histories(self, graph_id=None, user_id=None, limit=100, offset=0):
        """获取历史记录"""
        query = "SELECT * FROM history_records WHERE 1=1"
        params = {}
        
        if graph_id:
            query += " AND graph_id = :graph_id"
            params["graph_id"] = graph_id
        
        if user_id:
            query += " AND user_id = :user_id"
            params["user_id"] = user_id
        
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        # 获取原始数据库结果
        records = self.execute_query(query, params)
        
        # 转换为前端期望的数据结构
        frontend_records = []
        for record in records:
            # 尝试解析 operation_content 为 JSON
            content = {}
            try:
                if record.get('operation_content'):
                    import json
                    content = json.loads(record['operation_content'])
            except Exception:
                content = record.get('operation_content', '') or {}

            # 如果 content 为空，但表里有 query_text / answer_text 信息，则用它们补全聊天内容
            query_text = record.get('query_text') or ''
            answer_text = record.get('answer_text') or ''
            if (not content or not isinstance(content, dict)) and (query_text or answer_text):
                if answer_text:
                    content = {
                        'question': query_text or '未知查询',
                        'answer': answer_text
                    }
                else:
                    content = {
                        'question': query_text or '未知查询'
                    }

            # 转换记录类型
            record_type = ''
            op_type = record.get('operation_type')
            if op_type == 'query':
                if isinstance(content, dict) and 'entity' in content:
                    record_type = 'graph'
                elif isinstance(content, dict) and 'question' in content:
                    record_type = 'chat'
            elif op_type == 'create' and isinstance(content, dict) and 'filename' in content:
                record_type = 'upload'
            
            # 构建前端期望的记录结构
            frontend_record = {
                'id': record.get('history_id', ''),
                'type': record_type,
                'title': '',  # 标题将在下面生成
                'content': content,
                'status': 'completed',  # 默认状态
                'entities': [],  # 默认空数组
                'createTime': record.get('created_at', ''),
                'updateTime': record.get('created_at', '')  # 使用相同的时间
            }
            
            # 生成标题
            if record_type == 'chat':
                frontend_record['title'] = f"聊天: {content.get('question', '新对话')}"
            elif record_type == 'graph':
                frontend_record['title'] = f"图谱查询: {content.get('entity', '知识图谱')}"
            elif record_type == 'upload':
                frontend_record['title'] = f"数据上传: {content.get('filename', '未知文件')}"
            else:
                frontend_record['title'] = '未知记录'
            
            frontend_records.append(frontend_record)
        
        return frontend_records
    
    def save_history_record(self, data):
        """保存历史记录"""
        try:
            history_id = str(uuid.uuid4())
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 数据已经直接传递，无需再从请求中获取
            
            # 兼容前端数据结构，确保content是字典类型
            content = data.get('content', {})
            if not isinstance(content, dict):
                content = {}
            
            # 从前端数据结构中提取所需参数
            # 对于CHAT类型，query_text应该是question，answer_text应该是answer
            # 对于GRAPH类型，query_text应该是entity
            # 对于UPLOAD类型，query_text应该是filename
            graph_id = data.get('graph_id') or content.get('graphId') or None
            user_id = data.get('user_id') or content.get('userId') or 'default_user'
            
            # 设置operation_type，默认值为'query'
            record_type = data.get('type', '')
            if record_type == 'chat' or record_type == 'graph':
                operation_type = 'query'
            elif record_type == 'upload':
                operation_type = 'create'
            else:
                operation_type = 'query'  # 默认值
            
            # 根据记录类型提取query_text和answer_text
            if record_type == 'chat':
                query_text = content.get('question', '') or data.get('title', '') or '未知查询'
                answer_text = content.get('answer', '')
            elif record_type == 'graph':
                query_text = content.get('entity', '') or data.get('title', '') or '未知查询'
                answer_text = ''  # 图谱查询可能没有直接的answer
            elif record_type == 'upload':
                query_text = content.get('filename', '') or data.get('title', '') or '未知文件'
                answer_text = ''  # 文件上传可能没有直接的answer
            else:
                query_text = data.get('title', '') or content.get('query', '') or '未知查询'
                answer_text = data.get('answer_text') or content.get('answer') or ''
            
            # 处理实体和关系数量，确保安全访问
            entity_count = data.get('entity_count', 0)
            if entity_count == 0:
                entities = data.get('entities', [])
                entity_count = len(entities) if isinstance(entities, list) else 0
                # 检查content中是否有实体信息
                if entity_count == 0:
                    content_entities = content.get('entities', [])
                    entity_count = len(content_entities) if isinstance(content_entities, list) else 0
            
            relation_count = data.get('relation_count', 0)
            if relation_count == 0:
                relationships = data.get('relationships', [])
                relation_count = len(relationships) if isinstance(relationships, list) else 0
                # 检查content中是否有关系信息
                if relation_count == 0:
                    content_relationships = content.get('relationships', [])
                    relation_count = len(content_relationships) if isinstance(content_relationships, list) else 0
                # 对于图谱查询，检查是否有links或edges
                if relation_count == 0 and record_type == 'graph':
                    links = content.get('links', [])
                    edges = content.get('edges', [])
                    relation_count = len(links) if isinstance(links, list) else len(edges) if isinstance(edges, list) else 0
            
            query = """
            INSERT INTO history_records (history_id, graph_id, user_id, query_text, answer_text, entity_count, relation_count, status, operation_type)
            VALUES (:history_id, :graph_id, :user_id, :query_text, :answer_text, :entity_count, :relation_count, 'pending', :operation_type)
            """
            params = {
                "history_id": history_id,
                "graph_id": graph_id,
                "user_id": user_id,
                "query_text": query_text,
                "answer_text": answer_text,
                "entity_count": entity_count,
                "relation_count": relation_count,
                "operation_type": operation_type
            }
            self.execute_update(query, params)
            return history_id
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")
            raise
    
    def update_history_record_status(self, history_id, status):
        """更新历史记录状态"""
        try:
            query = "UPDATE history_records SET status = :status WHERE history_id = :history_id"
            params = {
                "status": status,
                "history_id": history_id
            }
            self.execute_update(query, params)
            return True
        except Exception as e:
            logger.error(f"更新历史记录状态失败: {e}")
            raise

# 单例模式
mysql_client = None

def get_mysql_client(host=None, port=None, user=None, password=None, database=None):
    global mysql_client
    if mysql_client is None:
        mysql_client = MySQLClient(host, port, user, password, database)
        mysql_client.connect()
    return mysql_client

# 测试代码
if __name__ == "__main__":
    client = MySQLClient()
    if client.connect():
        try:
            # 测试执行SQL文件
            client.execute_sql_file("init_mysql.sql")
            
            # 测试创建图谱
            graph_id = client.create_graph(
                graph_name="测试图谱",
                description="这是一个测试图谱",
                data_source="test.csv",
                user_id="user_001"
            )
            logger.info(f"创建的图谱ID: {graph_id}")
            
            # 测试获取图谱列表
            graphs = client.get_graphs()
            logger.info(f"图谱列表: {graphs}")
            
            # 测试更新图谱状态
            client.update_graph_status(graph_id, "completed", 100, 200)
            
            # 测试创建历史记录
            client.create_history(
                graph_id=graph_id,
                user_id="user_001",
                operation_type="create",
                operation_content="创建测试图谱"
            )
            
            # 测试获取历史记录
            histories = client.get_histories(graph_id=graph_id)
            logger.info(f"历史记录: {histories}")
            
        finally:
            client.disconnect()