import sys
import os

# 添加项目根目录到系统路径
sys.path.append('C:/Users/23035/PycharmProjects/knowledge_gragh')

# 导入MySQL客户端
from db.mysql_client import get_mysql_client

def main():
    try:
        # 获取MySQL客户端实例
        client = get_mysql_client()
        
        # 查询表结构
        result = client.execute_query('DESCRIBE history_records')
        
        # 打印表结构
        print('history_records表结构:')
        for row in result:
            print(row)
            
    except Exception as e:
        print(f'查询表结构时出错: {str(e)}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
