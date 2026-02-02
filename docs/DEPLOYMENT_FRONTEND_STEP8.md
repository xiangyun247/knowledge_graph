# 前端上云（步骤 8）— 简明指南

在**后端已上云**（`http://公网IP:5001/docs` 可访问）的前提下，将 Vue 前端构建为静态资源，用 Nginx 在云主机上提供页面访问；API 请求通过 Nginx 反向代理到后端，无需在前端写死公网 IP。

---

## 一、前提与结果

- **前提**：云主机上已按 `docs/DEPLOYMENT_CLOUD_STEP4.md` 完成后端部署（backend 在 5001 端口运行）。
- **结果**：用户通过 `http://公网IP`（或 `http://公网IP:80`）打开前端页面，前端请求 `/api/*` 由 Nginx 转发到本机 5001，同一域名、无跨域问题。

---

## 二、流程概览

| 步骤 | 做什么 | 预计时间 |
|------|--------|----------|
| 1 | 在云主机上克隆前端仓库并安装依赖 | 约 5 分钟 |
| 2 | 构建前端（`npm run build`，生成 `dist/`） | 约 3～5 分钟 |
| 3 | 安装 Nginx，配置静态站点 + `/api` 反向代理 | 约 5 分钟 |
| 4 | 开放防火墙 80 端口，浏览器访问 `http://公网IP` 验证 | 约 2 分钟 |

---

## 三、详细步骤（在云主机上执行）

### 步骤 1：克隆前端仓库并安装依赖

SSH 登录云主机后执行（将 `你的GitHub用户名` 换成实际用户名，若已克隆可跳过 clone）：

```bash
cd /root
apt install -y git nodejs npm
git clone https://github.com/xiangyun247/knowledge_gragh_frontend.git
cd knowledge_gragh_frontend
npm install
```

若 `nodejs` 版本过旧导致构建失败，可改用 Node 18+：

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs
```

### 步骤 2：构建前端

**无需**在构建时写死后端地址：Nginx 会把同源下的 `/api` 代理到本机 5001，前端使用默认的 `baseURL: '/api'` 即可。

```bash
cd /root/knowledge_gragh_frontend
npm run build
```

成功后当前目录下会生成 **`dist/`** 目录（静态文件）。

### 步骤 3：安装 Nginx 并配置

```bash
apt install -y nginx
```

新建站点配置（例如 `/etc/nginx/sites-available/kg-frontend`）：

```bash
cat > /etc/nginx/sites-available/kg-frontend << 'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    root /root/knowledge_gragh_frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5001/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
    }
}
EOF
```

启用配置并重载 Nginx：

```bash
ln -sf /etc/nginx/sites-available/kg-frontend /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

### 步骤 4：开放 80 端口并验证

1. 在云厂商控制台「防火墙 / 安全组」中放行 **80**（TCP）。
2. 在笔记本浏览器访问：**`http://你的公网IP`**  
   - 能打开前端首页且登录、搜索、图谱等请求正常，即表示前端上云完成。

---

## 四、常用命令

| 操作 | 命令 |
|------|------|
| 重新构建并刷新页面 | `cd /root/knowledge_gragh_frontend && npm run build`，无需重启 Nginx |
| 查看 Nginx 错误日志 | `tail -f /var/log/nginx/error.log` |
| 重启 Nginx | `systemctl restart nginx` |
| 检查 Nginx 配置 | `nginx -t` |

---

## 五、可选：本机构建再上传

若云主机内存不足或不想在云上装 Node，可在**本机**构建后上传 `dist/`：

1. 在本机前端项目根目录执行：
   ```bash
   npm run build
   ```
2. 将生成的 `dist/` 目录打包上传到云主机（如 `/root/kg-frontend-dist`）。
3. 将 Nginx 配置中的 `root` 改为该目录，例如：
   ```nginx
   root /root/kg-frontend-dist;
   ```
4. 执行 `nginx -t && systemctl reload nginx`。

前端请求仍使用相对路径 `/api`，由 Nginx 代理到 5001，无需改环境变量。

---

## 六、相关文档

- 后端上云与云主机环境：`docs/DEPLOYMENT_CLOUD_STEP4.md`
- 本地部署与端口说明：`docs/DEPLOYMENT.md`
- 阶段规划：`docs/TODO_PHASES.md`（步骤 8 = 前端上云，步骤 9 = HTTPS/域名）
