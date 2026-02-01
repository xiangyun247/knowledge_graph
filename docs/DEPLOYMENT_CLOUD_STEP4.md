# 云主机选型与基础环境（步骤 4）— 学生向简明指南

本文直接回答你的三个问题，并给出**从零到能访问 API** 的详细操作步骤。面向：学生、尽量少花钱、只有一台笔记本、无服务器部署经验。

---

## 一、先回答你的三个问题

### 1. 「从简且少花钱」怎么做到？

- **选学生机/轻量服务器**：腾讯云、阿里云都有「学生专享」或「轻量应用服务器」，约 **10 元/月** 左右（1 核 2G），新用户常有首年优惠。
- **精简部署**：你当前项目包含 Hadoop（NameNode、DataNode、ResourceManager、NodeManager 等），**整栈很吃内存**。在 1 核 2G 上全开容易卡死或 OOM。
  - **建议**：先做「**精简版上云**」——只跑 **backend + MySQL + Redis + Neo4j**（不跑 Hadoop、不跑 Celery 也可先省略），这样 1 核 2G 能跑、成本最低；等需要演示 Hadoop 再考虑 2 核 4G 或本地/实验室机器。
- **不买域名、不用 HTTPS**：直接用云主机**公网 IP + 端口**访问（例如 `http://你的IP:5001/docs`），省下域名和证书的钱与配置。

### 2. 更推荐哪个厂商？（针对你当前项目 + 只有笔记本）

- **更推荐：腾讯云 或 阿里云**（二选一即可）。
  - **原因**：国内访问快、中文控制台、学生优惠明确、文档多；你项目是 Docker Compose，任意一家都能跑。
- **具体建议**：
  - **腾讯云**：进入「云+校园」或「轻量应用服务器」→ 学生价约 10 元/月（1 核 2G），新用户有时送券；控制台清晰，适合第一次部署。
  - **阿里云**：「学生机」或「ECS 经济型」学生价类似；若你学校有阿里云校企合作，可能有免费额度。
- **不优先选**：国外云（AWS/GCP/Azure）除非你有特殊需求——国内直连可能慢，且学生认证流程相对麻烦。

**结论**：**腾讯云 或 阿里云 任选一家**，选「学生/轻量」最便宜档（1 核 2G），用下面的「精简部署」即可。

### 3. 会给你「每一步」的详细操作吗？

- **会。** 下面从「注册 → 买机器 → 开放端口 → 装 Docker → 上传代码 → 配置 .env → 启动 → 浏览器访问」按顺序写，你按步骤做即可。若某一步的界面和文档描述不一致，以你当前控制台为准（厂商会改版），思路相同。

---

## 二、整体流程概览（你要做的事）

| 步骤 | 做什么 | 预计时间 |
|------|--------|----------|
| 1 | 注册云厂商账号，完成学生认证（可选但推荐，享学生价） | 约 10 分钟 |
| 2 | 购买/领取 1 台「轻量应用服务器」或「学生机」（1 核 2G，系统选 Ubuntu 22.04） | 约 5 分钟 |
| 3 | 在控制台「防火墙/安全组」里开放端口：22（SSH）、5001（API） | 约 2 分钟 |
| 4 | 用 SSH 登录云主机，安装 Docker 与 Docker Compose | 约 10 分钟 |
| 5 | 把本机项目上传到云主机（或 Git clone） | 约 5 分钟 |
| 6 | 在云主机上配置 `.env`（密码、API Key） | 约 3 分钟 |
| 7 | 使用「精简版」Compose 只启动 backend + MySQL + Redis + Neo4j | 约 5 分钟 |
| 8 | 浏览器访问 `http://云主机公网IP:5001/docs` 做验证 | 约 1 分钟 |

---

## 三、详细操作步骤（以腾讯云轻量为例）

> 若你选的是**阿里云**，步骤类似：控制台名称可能不同（如「轻量应用服务器」→「云服务器 ECS」），但逻辑一致：买机器 → 开放端口 → SSH 登录 → 装 Docker → 上传代码 → 配 .env → 启动服务。

### 步骤 1：注册与学生认证（腾讯云）

1. 打开 [腾讯云官网](https://cloud.tencent.com/)，点击「免费注册」。
2. 用手机号或微信注册账号并登录。
3. 在控制台搜索「**学生**」或进入「**云+校园**」：
   - 若有「学生认证」入口，按提示完成（学生证/学信网等），通过后可买学生机。
   - 若无学生认证，可直接买「**轻量应用服务器**」新用户也有优惠。

### 步骤 2：购买一台轻量服务器（1 核 2G，Ubuntu）

1. 控制台里进入「**轻量应用服务器**」→「**新建**」。
2. 选择：
   - **地域**：选离你较近的（如「广州」或「上海」）。
   - **镜像**：**Ubuntu 22.04 LTS**（或 20.04 也可）。
   - **套餐**：选**最低档**（通常 1 核 2G、约 50～60 元/月；若有 10 元/月学生机则选学生机）。
   - **时长**：可按月买，先买 1 个月试跑。
3. 设置**登录方式**：
   - **密码**：自定义一个 root 密码（务必记住），后面 SSH 登录用。
   - 或选「密钥」，若你还不熟可先用密码。
4. 付费完成后，在「服务器列表」里看到一台机器，记下：
   - **公网 IP**（例如 `43.xxx.xxx.xxx`）
   - **root 密码**（你刚设的）

### 步骤 3：开放端口（防火墙 / 安全组）

1. 在轻量应用服务器列表里，点进你这台机器。
2. 打开「**防火墙**」或「**安全组**」页签。
3. 添加规则，放行：
   - **22**（TCP）— SSH 登录用。
   - **5001**（TCP）— 后端 API 用，浏览器访问 `http://IP:5001/docs` 要靠它。
4. 若你暂时不对外暴露 MySQL/Neo4j，只开放 22 和 5001 即可；其它端口（3307、6379、7474 等）可不开，仅本机访问。

### 步骤 4：SSH 登录并安装 Docker、Docker Compose

1. **在笔记本上**打开 PowerShell 或 CMD，用 SSH 登录（把 `你的公网IP` 换成实际 IP）：
   ```bash
   ssh root@你的公网IP
   ```
   提示输入密码时，输入步骤 2 里设的 root 密码。

2. 登录成功后，在**云主机**上依次执行下面命令（直接复制整段执行也可）：

   ```bash
   # 更新软件源（可选但推荐）
   apt update && apt install -y ca-certificates curl

   # 安装 Docker 官方脚本
   curl -fsSL https://get.docker.com | sh

   # 把 root 加入 docker 组，这样不用每次 sudo
   usermod -aG docker root

   # 安装 Docker Compose 插件（Docker 2.x 自带 compose 插件）
   apt install -y docker-compose-plugin

   # 验证
   docker --version
   docker compose version
   ```

3. 若 `docker compose version` 能输出版本号，说明安装成功。**退出 SSH 再重新登录一次**（这样 `docker` 组生效），再执行一次 `docker run hello-world` 试跑。

### 步骤 5：把项目放到云主机上

任选一种方式即可。**若 SCP 一直报 Permission denied**，可直接用下面的**方式 B（Git clone）**，或把代码推到 GitHub/Gitee 后在云主机上 clone，无需再折腾密码。

**方式 A：本机用 SCP 上传（适合你当前只有笔记本）**

1. 在**笔记本**上，进入项目根目录（例如 `C:\Users\23035\PycharmProjects\knowledge_gragh`）。
2. 打包当前项目（排除大文件、虚拟环境等），例如 PowerShell：
   ```powershell
   # 在项目根目录执行，生成 knowledge_gragh.zip（可根据需要排除 node_modules、.git、data 等）
   Compress-Archive -Path * -DestinationPath knowledge_gragh.zip -Force
   ```
   若你有 Git，也可以不打包，直接在云主机上 `git clone`（方式 B）。

3. 用 SCP 传到云主机（把 `你的公网IP` 换成实际 IP）：
   ```powershell
   scp knowledge_gragh.zip root@你的公网IP:/root/
   ```

4. 在**云主机**上解压：
   ```bash
   cd /root
   apt install -y unzip
   unzip knowledge_gragh.zip -d knowledge_gragh
   cd knowledge_gragh
   ```

**方式 B：云主机上 Git clone（若代码在 GitHub/Gitee）**

在云主机上：

```bash
cd /root
apt install -y git
git clone https://github.com/你的用户名/knowledge_gragh.git
cd knowledge_gragh
```

### 步骤 6：在云主机上配置 .env

1. 在云主机上进入项目目录：
   ```bash
   cd /root/knowledge_gragh
   ```

2. 复制示例环境变量并编辑：
   ```bash
   cp .env.example .env
   nano .env
   ```
   或用 `vi .env`。把下面几项改成**你自己设的密码/Key**（不要用示例里的占位符）：
   - `NEO4J_PASSWORD=你的Neo4j密码`
   - `MYSQL_ROOT_PASSWORD=你的MySQL根密码`
   - `MYSQL_PASSWORD=你的MySQL业务账号密码`
   - `DEEPSEEK_API_KEY=你的DeepSeek的Key`（没有可先留空，Agent 会不可用但其它接口能跑）

3. 保存退出（nano：Ctrl+O 回车，Ctrl+X；vi：按 Esc 后输入 `:wq` 回车）。

### 步骤 7：用「精简版」启动（不跑 Hadoop，省内存）

当前你项目是「全栈」：Hadoop + MySQL + Redis + Neo4j + Backend + Celery。在 1 核 2G 上全开会很吃紧。项目里已提供**精简版 compose 文件**，只起 MySQL、Redis、Neo4j、backend（不启动 Hadoop、Celery）。

在云主机上，仍在项目目录 `/root/knowledge_gragh` 下执行：

```bash
# 使用精简版 compose（仅 backend + MySQL + Redis + Neo4j）
docker compose -f docker-compose.cloud-minimal.yml up -d
```

首次会构建 backend 镜像，可能需几分钟。等待 1～2 分钟后执行：

```bash
docker compose -f docker-compose.cloud-minimal.yml ps
```

期望：`mysql`、`redis`、`neo4j` 为 **healthy**，`backend` 为 **Up**。若 backend 一直 Restarting，可执行 `docker compose -f docker-compose.cloud-minimal.yml logs backend` 看报错（常见是 MySQL/Neo4j 还没 healthy，多等一会再试）。

### 步骤 8：在笔记本浏览器里验证

1. 打开浏览器，访问：**`http://你的云主机公网IP:5001/docs`**（把「你的云主机公网IP」换成步骤 2 里记下的 IP）。
2. 若能看到 Swagger 文档页，说明 API 已对外可访问，**步骤 4 的「云主机选型与基础环境」即算完成**。

---

## 四、若你以后换成 2 核 4G 或想跑全栈

- 先停掉精简版（可选）：
  ```bash
  cd /root/knowledge_gragh
  docker compose -f docker-compose.cloud-minimal.yml down
  ```
- 再按**全栈**启动：
  ```bash
  docker compose up -d
  ```
  会按 `docker-compose.yml` 启动全部服务（含 Hadoop、Celery）。建议内存 ≥4G 再跑全栈。
- 端口若需对外访问（如 7474、8088），再到控制台「防火墙」里放行对应端口。

---

## 五、常见问题（FAQ）

- **问：学生认证失败怎么办？**  
  答：可先不用学生机，直接买「轻量应用服务器」最低档，新用户常有首单优惠，价格也不会很高。

- **问：SSH 连不上（超时/拒绝）？**  
  答：检查是否在控制台开放了 **22** 端口；确认用的是**公网 IP**；云厂商有些默认只允许「密钥」登录，若你选的是密码，需在控制台确认已开启「密码登录」。

- **问：SCP 上传时提示 Permission denied (publickey, password)？**  
  答：按下面顺序排查：  
  1. **先测 SSH**：在笔记本执行 `ssh root@你的公网IP`，用同一密码登录。若 SSH 都登不上，问题在密码或服务器配置，不是 SCP 本身。  
  2. **确认密码**：无多余空格、区分大小写；若在控制台刚重置过密码，等 1～2 分钟再试，并确认复制/输入的是新密码。  
  3. **控制台是否允许密码登录**：腾讯云轻量 → 该实例 →「登录」或「更多」里查看是否已开启「密码登录」；若只开了「密钥」，需添加密码或改用密钥。  
  4. **绕过 SCP**：若仍不行，可直接用**方式 B**：在云主机网页终端里执行 `git clone` 拉取代码（先把项目推到 GitHub/Gitee），无需本机 SCP。

- **问：5001 打不开网页？**  
  答：确认防火墙已开放 **5001**；在云主机上执行 `docker compose ps` 看 backend 是否 Up；再执行 `docker compose logs backend` 看是否有报错（如连不上 MySQL/Neo4j）。

- **问：想用域名 + HTTPS 可以吗？**  
  答：可以，那是 TODO_PHASES 里的「步骤 9」；需要先有域名，再在云主机装 Nginx、申请证书（如 Let’s Encrypt），把 80/443 反代到 5001。当前步骤 4 只做到「用 IP:5001 能访问」即可。

---

## 六、小结（对应你的三个问题）

1. **从简少花钱**：选学生机/轻量 1 核 2G；先做「精简部署」（只起 MySQL + Redis + Neo4j + backend），不跑 Hadoop；不买域名、不配 HTTPS。
2. **推荐厂商**：**腾讯云** 或 **阿里云** 二选一，学生/轻量最便宜档即可。
3. **详细步骤**：上面第三节已按「注册 → 买机器 → 开放端口 → SSH → 装 Docker → 上传项目 → 配 .env → 精简启动 → 浏览器验证」给出逐步操作；若你选阿里云，把「轻量应用服务器」换成对应产品名，其余思路一致。

如果你在某一步卡住（例如控制台界面和文档不一致、或报错信息看不懂），可以把**当前执行到哪一步、报错原文或截图**发出来，再按你的实际情况往下细化。
