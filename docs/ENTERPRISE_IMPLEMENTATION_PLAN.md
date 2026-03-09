# 企业级项目落地实施方案

> 基于对前后端完整代码的审视，针对正式比赛与企业级部署制定的具体实现方案。

---

## 一、项目现状概览

### 1.1 后端架构（knowledge_gragh）

| 模块 | 技术栈 | 现状 |
|------|--------|------|
| API 框架 | FastAPI | ✅ 已用 |
| 认证 | JWT (access + refresh) | ✅ 已实现 |
| 角色 | admin / doctor / patient / guest | ✅ 已实现 |
| 数据库 | MySQL + Neo4j + Chroma | ✅ 已用 |
| 密码存储 | SHA256 | ⚠️ 需升级 |
| CORS | `allow_origins=["*"]` | ⚠️ 生产不安全 |
| 限流 | 无 | ❌ 缺失 |
| 健康检查 | `/api/health` | ✅ 已有 |
| 结构化日志 | log_api_event | ✅ 已有 |
| 错误码 | E_OK, E_DB 等 | ✅ 已有 |
| Docker | docker-compose | ✅ 已有（无前端） |

### 1.2 前端架构（vue_test_style）

| 模块 | 技术栈 | 现状 |
|------|--------|------|
| 框架 | Vue 2 + Element UI | ✅ |
| 路由 | Vue Router (history) | ✅ |
| 状态 | Vuex | ✅ |
| 请求 | Axios + Token 刷新 | ✅ |
| 角色控制 | role.js + 路由守卫 | ✅ |
| 环境变量 | .env.development / .env.production | ✅ |
| 构建 | vue-cli-service | ✅ |
| Docker | 无 | ❌ 缺失 |

### 1.3 测试与文档

| 项目 | 现状 |
|------|------|
| 后端测试 | tests/ 下多为脚本式，非 pytest 规范 |
| 前端测试 | 无 |
| API 文档 | FastAPI Swagger | ✅ |
| 部署文档 | 分散 | ⚠️ 需整合 |
| 架构图 | 无 | ❌ 缺失 |

---

## 二、实施方案（按优先级）

### 阶段一：安全加固（高优先级）

#### 2.1.1 密码哈希升级

**现状**：`backend/app.py` 使用 `hashlib.sha256`，无盐值，易被彩虹表破解。

**方案**：

```python
# 新增依赖：requirements.txt
bcrypt>=4.0.0

# backend/app.py 修改
import bcrypt

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()

def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode())
    except Exception:
        return False
```

**迁移**：已有用户需在首次登录时提示修改密码，或提供一次性迁移脚本将 SHA256 哈希转为 bcrypt。

---

#### 2.1.2 CORS 生产配置

**现状**：`backend/app.py` 中 `allow_origins=["*"]`。

**方案**：

```python
# 从 config 或环境变量读取
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8080").split(",")
# 生产示例：CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```

---

#### 2.1.3 JWT 密钥校验

**现状**：`JWT_SECRET` 默认 `change-me-in-production`，生产易被忽略。

**方案**：在 `backend/auth.py` 或应用启动时增加校验：

```python
if os.getenv("ENVIRONMENT") == "production" and JWT_SECRET == "change-me-in-production":
    raise ValueError("生产环境必须设置 JWT_SECRET，且不能使用默认值")
```

---

#### 2.1.4 接口限流

**现状**：无限流，易被暴力破解或滥用。

**方案**：

```python
# requirements.txt
slowapi>=0.1.9

# backend/app.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/auth/login")
@limiter.limit("5/minute")  # 登录限流
async def login_user(request: Request, body: LoginRequest):
    ...
```

---

### 阶段二：可观测性与稳定性

#### 2.2.1 优雅关闭

**现状**：`run.py` 无 shutdown 逻辑，进程退出时 DB 连接可能未正确关闭。

**方案**：

```python
# run.py 或 backend/app.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # 关闭时
    if mysql_client and hasattr(mysql_client, "disconnect"):
        mysql_client.disconnect()
    if neo4j_client and hasattr(neo4j_client, "close"):
        neo4j_client.close()

app = FastAPI(lifespan=lifespan)
```

---

#### 2.2.2 请求日志脱敏

**现状**：`request.js` 中 `console.log` 可能打印敏感信息。

**方案**：生产环境关闭或脱敏：

```javascript
if (process.env.NODE_ENV !== 'production') {
  console.log('API请求:', config.method.toUpperCase(), config.url);
}
```

---

### 阶段三：测试体系

#### 2.3.1 后端 API 自动化测试

**现状**：`tests/` 多为脚本式，缺少 pytest  fixtures 与断言规范。

**方案**：

```
tests/
├── conftest.py          # pytest fixtures：TestClient、测试用户 token
├── test_auth_api.py     # 登录、注册、刷新
├── test_kg_api.py       # 图谱构建、列表、数据
├── test_kb_api.py       # 知识库、文档、ask
├── test_agent_api.py    # Agent 问答（可 mock LLM）
└── test_health.py       # /api/health
```

**示例**（`tests/conftest.py`）：

```python
import pytest
from fastapi.testclient import TestClient
from backend.app import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers(client):
    r = client.post("/api/auth/login", json={"username": "testuser", "password": "testpass123"})
    assert r.status_code == 200
    token = r.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}
```

---

#### 2.3.2 测试覆盖率

**方案**：

```bash
pip install pytest-cov
pytest tests/ -v --cov=backend --cov-report=html --cov-report=term
```

---

### 阶段四：部署与工程化

#### 2.4.1 前端 Docker 化

**现状**：docker-compose 仅有后端，无前端服务。

**方案**：

```dockerfile
# docker/Dockerfile.frontend
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production=false
COPY . .
ARG VUE_APP_API_BASE_URL=
ENV VUE_APP_API_BASE_URL=$VUE_APP_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```yaml
# docker-compose.yml 新增
frontend:
  build:
    context: ../vue_test_style  # 或将前端放入 monorepo
    dockerfile: ../docker/Dockerfile.frontend
  ports:
    - "80:80"
  depends_on:
    - backend
```

---

#### 2.4.2 Nginx 配置（前后端同域）

**方案**（`docker/nginx.conf`）：

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api {
        proxy_pass http://backend:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

#### 2.4.3 环境变量统一

**现状**：`config.py` 与 `backend/app.py`、`db/mysql_client.py` 存在不一致（如 `MYSQL_DATABASE`）。

**方案**：统一从 `config.py` 或 `.env` 读取，避免硬编码与重复定义。

---

### 阶段五：文档与展示（比赛必备）

#### 2.5.1 架构图

**内容**：系统架构、数据流、技术栈、部署拓扑。

**工具**：Draw.io、Mermaid、或 PPT 导出 PNG。

---

#### 2.5.2 部署文档

**文件**：`docs/DEPLOYMENT.md`

**内容**：

- 环境要求（Python、Node、Docker、MySQL、Neo4j）
- 本地开发启动步骤
- Docker Compose 一键部署
- 环境变量说明（.env.example 补充完整）
- 常见问题与排查

---

#### 2.5.3 演示脚本

**文件**：`docs/DEMO_SCRIPT.md`

**内容**：固定演示流程（如 5–8 分钟），包含：

1. 系统介绍
2. 登录 / 角色
3. 知识图谱构建与可视化
4. 智能问答
5. 患者教育
6. 知识库管理
7. 多模态（语音 / OCR，如有）

---

### 阶段六：配置与规范

#### 2.6.1 .env.example 完善

**补充项**：

```
# CORS（生产必填）
CORS_ORIGINS=https://your-domain.com

# 可选：限流
RATE_LIMIT_LOGIN=5/minute
RATE_LIMIT_API=60/minute
```

---

#### 2.6.2 前端生产构建优化

**vue.config.js** 补充：

```javascript
module.exports = {
  productionSourceMap: false,
  configureWebpack: config => {
    if (process.env.NODE_ENV === 'production') {
      config.optimization.splitChunks = {
        chunks: 'all',
        cacheGroups: {
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors'
          }
        }
      };
    }
  }
};
```

---

## 三、实施优先级与时间估算

| 阶段 | 内容 | 优先级 | 预估工时 |
|------|------|--------|----------|
| 一 | 密码升级、CORS、JWT 校验、限流 | P0 | 1–2 天 |
| 二 | 优雅关闭、日志脱敏 | P1 | 0.5 天 |
| 三 | 后端 pytest 测试、覆盖率 | P1 | 1–2 天 |
| 四 | 前端 Docker、Nginx、环境统一 | P1 | 1 天 |
| 五 | 架构图、部署文档、演示脚本 | P0（比赛） | 1 天 |
| 六 | .env 完善、前端构建优化 | P2 | 0.5 天 |

---

## 四、检查清单（比赛前）

- [ ] 密码使用 bcrypt
- [ ] 生产环境 CORS 已限制
- [ ] JWT_SECRET 非默认值
- [ ] 登录接口已限流
- [ ] `/api/health` 可正常访问
- [ ] Docker Compose 可一键启动
- [ ] 部署文档完整
- [ ] 架构图已准备
- [ ] 演示脚本已演练
- [ ] 核心 API 有自动化测试

---

## 五、附录：关键文件索引

| 功能 | 后端文件 | 前端文件 |
|------|----------|----------|
| 认证 | backend/auth.py | src/utils/request.js, src/store/modules/user.js |
| 角色 | backend/auth.py | src/utils/role.js, src/router/index.js |
| 配置 | config.py, .env | .env.development, .env.production |
| 健康检查 | backend/app.py (GET /api/health) | - |
| 部署 | docker-compose.yml, docker/ | - |
