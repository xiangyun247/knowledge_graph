import os
from dotenv import load_dotenv
import requests

# 加载环境变量
load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")

print("=" * 50)
print("DeepSeek API Key 诊断")
print("=" * 50)

# 1. 检查 Key 是否存在
if not api_key:
    print("❌ API Key 未设置!")
    exit(1)

# 2. 检查 Key 格式
print(f"✓ API Key 前10位: {api_key[:10]}...")
print(f"✓ API Key 长度: {len(api_key)}")

# 3. 检查是否有多余空格
if api_key != api_key.strip():
    print("⚠️  警告: API Key 有多余空格!")
    api_key = api_key.strip()
    print(f"清理后长度: {len(api_key)}")

# 4. 测试 API 连接
print("\n正在测试 API 连接...")
url = "https://api.deepseek.com/v1/models"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        print("✅ API Key 有效!")
        data = response.json()
        print(f"可用模型数量: {len(data.get('data', []))}")
    else:
        print(f"❌ API Key 无效!")
        print(f"错误: {response.text}")
except requests.exceptions.Timeout:
    print("❌ 请求超时,可能是网络问题")
except requests.exceptions.ConnectionError:
    print("❌ 无法连接到 DeepSeek API,请检查网络")
except Exception as e:
    print(f"❌ 发生错误: {e}")
