# 【已归档】PromiseLink 云端部署架构设计（v0.5.0-draft，不适用于 OPC-Agents）

> **归档说明**（2026-07-27）：
> 本文档描述的是 **PromiseLink 项目**的云端部署架构（nginx + 47.116.219.15 服务器 +
> promiselink-pro 容器 + 官网静态文件），**不适用于 OPC-Agents**。
>
> OPC-Agents 是 PyPI 开源包，**本地运行**（localhost:8000），无云端部署。
> 用户通过 `pip install opc-agents` 安装，启动后访问 `http://localhost:8000`。
>
> 文档保留于此仅作历史参考，描述 PromiseLink Pro 网关（`gateway.promiselink.cn`）
> 的架构决策来源。OPC-Agents 复用该网关作为 Moka LLM 代理（见 ADR-005），
> 但 OPC-Agents 本身不部署任何云端组件。
>
> 相关硬约束已更新：见 `docs/HARD_CONSTRAINTS.md` P2/P3（已废弃）。

| 元数据     | 内容                                      |
| ---------- | ----------------------------------------- |
| 版本       | v0.5.0-draft（已归档）                    |
| 日期       | 2026-07-19                                |
| 状态       | 7-Role 共识（仅适用于 PromiseLink）       |
| 决策者     | DevOps Lead                               |
| 关联路线图 | ROADMAP_v0.5.0.md §OKR-4 运营基础设施     |
| 关联约束   | HARD_CONSTRAINTS.md                       |

---

## 1. 背景（Context）

### 1.1 v0.4.0 评估结论

`ASSESSMENT_INITIAL_VISION_v0.4.0.md` §5.4 明确指出当前运营基础设施存在三类缺失：

- 产品官网未部署（promiselink.cn 未上线）
- 真实生产环境未部署（仅本地 beta 验证）
- 用户反馈渠道未建立（无官网入口、无支持邮箱、无问题反馈链路）

上述缺失使 v0.4.0 仅完成"产品功能闭环"，未完成"产品对外可达闭环"，阻碍 v0.5.0 种子用户扩展与商业化验证。

### 1.2 v0.5.0 必须达成

`ROADMAP_v0.5.0.md` §OKR-4 要求：

1. 部署 promiselink.cn 官网（含产品介绍、下载、文档、快速入门）
2. 部署真实生产环境（专业版网关 + 支撑服务）
3. 建立用户反馈渠道（官网入口 + 企业微信告警链路）

### 1.3 必须遵守的硬约束

本架构设计严格遵循 `HARD_CONSTRAINTS.md`，下述约束为不可协商项：

- **硬约束 H1**：基础版必须在用户本地运行（localhost:8000），禁止云端部署基础版容器、源码或前端
- **硬约束 H2**：专业版 LLM 调用路径为 用户本地/小程序 → 网关 `/api/v1/pro/relay/llm` → Moka AI，用户不持有 LLM API Key
- **硬约束 H3**：基础版通过 relay_client 连接专业版网关
- **硬约束 H4**：基础版不包含语音功能和图片扫描功能
- **硬约束 H5**：专业版网关地址统一为 `gateway.promiselink.cn`，备案前临时使用 `47.116.219.15:8001`
- **硬约束 H6**：47.116.219.15 服务器仅部署专业版网关（promiselink-pro:8001）+ 官网静态文件（nginx）+ 支撑服务（PostgreSQL/Redis/Certbot）。禁止部署基础版容器/源码/前端
- **硬约束 H7**：nginx 默认 server 策略——默认 server 块（捕获直接 IP 访问和未匹配 Host）必须服务官网静态文件，禁止代理到任何应用容器
- **硬约束 H8**：API keys 与 credentials 不得以明文形式写入文档、代码或注释

任何违反上述约束的部署变更必须先更新 `HARD_CONSTRAINTS.md` 并经 7-Role 共识评审通过后方可执行。

---

## 2. 部署架构总览

### 2.1 三层架构图

```
┌─────────────────────────────────────────────────────────────┐
│  云端 (47.116.219.15) — 仅专业版网关 + 官网 + 支撑服务      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  nginx (80/443)                                      │   │
│  │  ├── promiselink.cn → 官网静态文件 (/var/www/html)   │   │
│  │  ├── gateway.promiselink.cn → 网关 :8001             │   │
│  │  └── 默认 server → 官网静态文件（禁止代理应用）       │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ promiselink-pro  │  │ PostgreSQL       │                │
│  │ :8001 (网关)     │  │ :5432            │                │
│  └──────────────────┘  └──────────────────┘                │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Redis            │  │ Certbot          │                │
│  │ :6379            │  │ (Let's Encrypt)  │                │
│  └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
                                   ▲
                                   │ WSS 长连接 / HTTPS API
                                   │
┌─────────────────────────────────────────────────────────────┐
│  用户本地（基础版 localhost:8000）                            │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Streamlit UI     │  │ relay_client     │                │
│  │ :8000            │──│ WSS → 云端网关    │                │
│  └──────────────────┘  └──────────────────┘                │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ opc_manager      │  │ SQLite (本地)    │                │
│  │ (核心引擎)       │  │ (用户数据)       │                │
│  └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
                                   ▲
                                   │ 微信小程序
                                   │
┌─────────────────────────────────────────────────────────────┐
│  微信小程序（专业版前端）                                     │
│  └─ 通过网关 WSS 中继与用户电脑对接，不直接访问              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 架构层次说明

| 层次       | 部署位置             | 主要组件                                     | 数据存储位置         |
| ---------- | -------------------- | -------------------------------------------- | -------------------- |
| 云端层     | 47.116.219.15        | nginx / promiselink-pro / PostgreSQL / Redis | PostgreSQL（网关元数据）|
| 用户本地层 | 用户电脑 localhost   | Streamlit UI / opc_manager / relay_client    | SQLite（用户业务数据）|
| 移动端层   | 微信小程序运行环境   | 小程序前端                                   | 无本地持久化         |

### 2.3 数据流路径

- **基础版 LLM 调用**：用户本地 Streamlit UI → opc_manager → relay_client → WSS → 云端网关 `/api/v1/pro/relay/llm` → Moka AI
- **小程序 LLM 调用**：微信小程序 → HTTPS → 云端网关 `/api/v1/pro/relay/llm` → Moka AI
- **官网访问**：浏览器 → `https://promiselink.cn` → nginx → `/var/www/html` 静态文件
- **直接 IP 访问**：浏览器 → `http://47.116.219.15` → nginx 默认 server → `/var/www/html` 静态文件（不进入网关）

---

## 3. 云端部署（47.116.219.15）

### 3.1 nginx 配置

nginx 监听 80/443 端口，配置三个 server 块。所有 HTTP 请求强制 301 跳转到 HTTPS。

#### 3.1.1 promiselink.cn（官网静态文件）

```nginx
server {
    listen 443 ssl http2;
    server_name promiselink.cn;
    ssl_certificate     /etc/letsencrypt/live/promiselink.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/promiselink.cn/privkey.pem;
    root /var/www/html;
    index index.html;

    location / { try_files $uri $uri/ =404; }
    location /install.sh {
        alias /var/www/scripts/install.sh;
        default_type application/x-sh;
    }

    # 安全头
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    # 限流：单 IP 100 req/min
    limit_req zone=website_zone burst=20 nodelay;
}
```

#### 3.1.2 gateway.promiselink.cn（专业版网关反向代理）

```nginx
server {
    listen 443 ssl http2;
    server_name gateway.promiselink.cn;
    ssl_certificate     /etc/letsencrypt/live/gateway.promiselink.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gateway.promiselink.cn/privkey.pem;

    # 健康检查
    location = /health {
        access_log off;
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
    # 网关反向代理
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # WSS 升级支持
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    limit_req zone=gateway_zone burst=50 nodelay;
}
```

#### 3.1.3 默认 server（捕获直接 IP 访问与未匹配 Host）

> **硬约束 H7 强制项**：默认 server 必须服务官网静态文件，禁止代理到任何应用容器。

```nginx
server {
    listen 80 default_server;
    listen 443 ssl default_server;
    server_name _;
    ssl_certificate     /etc/letsencrypt/live/promiselink.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/promiselink.cn/privkey.pem;
    root /var/www/html;
    index index.html;
    location / { try_files $uri $uri/ =404; }
}
```

默认 server 的存在保证：

- 直接访问 `http://47.116.219.15` 显示官网首页，不暴露任何应用容器
- 未匹配的 Host 头（含恶意扫描）回落到官网静态文件
- 即使攻击者通过 IP 直连也无法触达 promiselink-pro:8001

#### 3.1.4 限流区域定义（nginx http 块）

```nginx
limit_req_zone $binary_remote_addr zone=website_zone:10m rate=100r/m;
limit_req_zone $binary_remote_addr zone=gateway_zone:10m rate=300r/m;
```

### 3.2 专业版网关（promiselink-pro:8001）

#### 3.2.1 容器职责

promiselink-pro 为基于 FastAPI 的专业版网关容器，监听容器内 8001 端口，由 docker-compose 编排。对外仅通过 nginx 反向代理暴露，不直接监听公网端口。

#### 3.2.2 核心 API 路由

| 路由                          | 方法 | 鉴权方式          | 说明                       |
| ----------------------------- | ---- | ----------------- | -------------------------- |
| `/api/v1/health`              | GET  | 无                | 健康检查                   |
| `/api/v1/pro/relay/llm`       | POST | API Key + JWT     | LLM 中继（核心路径）       |
| `/api/v1/pro/relay/asr`       | POST | API Key + JWT     | 语音识别                   |
| `/api/v1/pro/relay/tts`       | POST | API Key + JWT     | 语音合成                   |
| `/api/v1/pro/relay/ocr`       | POST | API Key + JWT     | 图片文字识别               |
| `/api/v1/pro/license/activate`| POST | License Key       | 激活专业版                 |
| `/api/v1/pro/usage`           | GET  | API Key + JWT     | 查询使用量                 |

> **硬约束 H4**：基础版不包含语音（ASR/TTS）和图片扫描（OCR）功能。基础版 relay_client 不调用上述 ASR/TTS/OCR 路由，仅小程序专业版前端会使用。

#### 3.2.3 鉴权机制

- **API Key 验证**：所有 `/api/v1/pro/*` 路由强制校验 `X-API-Key` 标头
- **JWT token**：基础版 relay_client 通过 License 激活后获取 JWT，用于 WSS 长连接认证
- **CORS**：仅允许 `https://promiselink.cn` 与 `http://localhost:8000`

#### 3.2.4 与 Moka AI 对接

- 网关持有 Moka AI API Key（环境变量 `MOKA_API_KEY`，禁止明文写入任何文件）
- 用户请求经网关鉴权后转发至 Moka AI，响应原样返回
- 网关记录调用次数、token 消耗、调用延迟，不记录请求体与响应体

### 3.3 支撑服务

| 服务         | 端口/监听          | 用途                                            | 备份/持久化                            |
| ------------ | ------------------ | ----------------------------------------------- | -------------------------------------- |
| PostgreSQL   | 127.0.0.1:5432     | 网关元数据：users / licenses / api_keys(哈希) / call_logs(不含业务数据) | 每日 02:00 pg_dump，保留 14 天         |
| Redis        | 127.0.0.1:6379     | JWT 黑名单 / API 调用计数限流 / 热点配置缓存    | RDB 每小时 + AOF everysec              |
| Certbot      | -                  | Let's Encrypt 证书自动续签（nginx 插件）        | 证书路径 `/etc/letsencrypt/live/<domain>/` |

- 数据库：`promiselink_gateway`
- 自动续签：每 12 周通过 cron 触发 `certbot renew --nginx && docker exec nginx nginx -s reload`
- 备案前临时方案：`gateway.promiselink.cn` 使用自签证书，浏览器告警由基础版 relay_client 在客户端忽略（仅信任第一次）

### 3.4 健康检查

| 端点                             | 期望响应          | 检查频率 | 告警阈值          |
| -------------------------------- | ----------------- | -------- | ----------------- |
| `https://promiselink.cn/`        | HTTP 200          | 60s      | 连续 3 次失败     |
| `https://gateway.promiselink.cn/health` | HTTP 200    | 30s      | 连续 3 次失败     |
| `https://gateway.promiselink.cn/api/v1/health` | HTTP 200 | 60s | 连续 3 次失败    |
| `tcp://127.0.0.1:5432`           | TCP 连通          | 60s      | 连续 3 次失败     |
| `tcp://127.0.0.1:6379`           | TCP 连通          | 60s      | 连续 3 次失败     |

健康检查脚本部署于 `/opt/healthcheck/healthcheck.sh`，由 cron 每 1 分钟执行一次。失败连续 3 次通过企业微信 webhook 发送告警。

---

## 4. 用户本地部署（基础版）

> **硬约束 H1 / H6**：基础版仅在用户本地运行，禁止任何形式的云端部署。云端 47.116.219.15 不得包含基础版容器、源码或前端。

### 4.1 安装方式

#### 4.1.1 PyPI 安装（推荐）

```bash
pip install opc-agents
```

适用于已具备 Python 3.10+ 环境的用户。安装后 `opc-agents` 命令可用。

#### 4.1.2 一键脚本安装

```bash
curl -fsSL https://promiselink.cn/install.sh | bash
```

脚本来源：`/var/www/scripts/install.sh`，由 nginx 通过 `promiselink.cn/install.sh` 暴露。脚本逻辑：检测 OS（macOS/Linux/WSL2）→ 检测 Python 3.10+ → 创建虚拟环境 `~/.opc-agents/venv` → `pip install opc-agents` → 写入 `~/.opc-agents/config.yaml` 默认配置 → 提示运行 `opc-agents start`。

#### 4.1.3 Docker 安装

```bash
docker run -d \
  --name opc-agents \
  -p 8000:8000 \
  -v ~/.opc-agents:/root/.opc-agents \
  ghcr.io/<org>/opc-agents:latest
```

> 注意：Docker 安装方式仍属于"用户本地部署"，容器运行在用户自己的机器上，监听 localhost:8000。禁止将基础版镜像部署到 47.116.219.15 或任何云端服务器。

### 4.2 启动与激活

#### 4.2.1 启动基础版

```bash
opc-agents start
```

执行后：

- Streamlit UI 监听 `http://localhost:8000`
- opc_manager 核心引擎在后台运行
- relay_client 处于待激活状态，未激活时不发起 WSS 连接

#### 4.2.2 激活专业版

```bash
opc-agents pro activate PL-PRO-xxxx-xxxx-xxxx
```

激活流程：relay_client 向 `https://gateway.promiselink.cn/api/v1/pro/license/activate` POST License Key → 网关校验返回 JWT + API Key → 基础版用用户主机派生密钥加密存入 `~/.opc-agents/credentials.enc` → 建立 WSS 长连接到 `wss://gateway.promiselink.cn/api/v1/pro/ws` → 激活成功后可用专业版 LLM 中继能力。

> **硬约束 H2**：用户不持有 LLM API Key。用户持有的仅为 License Key 与派生的 JWT/API Key（用于网关鉴权），Moka AI API Key 永远只存在于云端网关环境变量中。

### 4.3 数据存储

| 路径                              | 类型     | 内容                                   | 是否加密 |
| --------------------------------- | -------- | -------------------------------------- | -------- |
| `~/.opc-agents/data/opc.db`       | SQLite   | 用户业务数据（任务、技能、知识库等）   | 否       |
| `~/.opc-agents/config.yaml`       | YAML     | 用户配置（语言、主题、网关地址等）     | 否       |
| `~/.opc-agents/credentials.enc`   | 二进制   | JWT token + API Key（激活后）          | 是       |
| `~/.opc-agents/logs/opc-agents.log` | 文本   | 运行日志（按日轮转，保留 7 天）        | 否       |

用户业务数据仅存储在本地 SQLite，云端网关不接收也不存储用户业务数据。

### 4.4 与云端网关通信

#### 4.4.1 通信协议

- 传输：WSS（WebSocket over TLS）
- 端点：`wss://gateway.promiselink.cn/api/v1/pro/ws`
- 心跳：客户端每 30s 发送 `ping`，服务端响应 `pong`，60s 无响应触发重连
- 重连：指数退避，最大间隔 60s，连续 10 次失败提示用户检查网络

#### 4.4.2 数据转发策略

| 数据类型     | 是否转发到网关 | 说明                                       |
| ------------ | -------------- | ------------------------------------------ |
| LLM 请求     | 是             | `/api/v1/pro/relay/llm`                    |
| ASR 请求     | 是             | `/api/v1/pro/relay/asr`（基础版禁用）      |
| TTS 请求     | 是             | `/api/v1/pro/relay/tts`（基础版禁用）      |
| OCR 请求     | 是             | `/api/v1/pro/relay/ocr`（基础版禁用）      |
| 用户任务数据 | 否             | 仅本地 SQLite                              |
| 用户技能配置 | 否             | 仅本地 YAML                                |
| 知识库向量   | 否             | 仅本地 SQLite + 本地嵌入模型               |

> **硬约束 H4 落地**：基础版 relay_client 在代码层禁止调用 ASR/TTS/OCR 路由，即使激活专业版也不可用。

---

## 5. CI/CD 流程

### 5.1 GitHub Actions release.yml

继承现有 `.github/workflows/release.yml`，触发条件为 tag `v*.*.*` 推送。

| 步骤 | 说明                                                       |
| ---- | ---------------------------------------------------------- |
| 1    | 运行单元测试 + 集成测试（pytest）                          |
| 2    | 构建 Python wheel 与 sdist                                 |
| 3    | 发布到 PyPI（使用 `PYPI_API_TOKEN` 密钥，禁止明文）        |
| 4    | 创建 GitHub Release（自动生成 changelog）                  |
| 5    | 构建 Docker 镜像 `ghcr.io/<org>/opc-agents:<tag>`          |
| 6    | 推送 GHCR（使用 `GITHUB_TOKEN`）                           |
| 7    | 同步推送 `latest` tag                                      |

### 5.2 官网部署

新建 `.github/workflows/website-deploy.yml`：

- 触发：`main` 分支 push 到 `docs/` 或 `frontend/website/`
- 步骤：
  1. 构建静态文件（Hugo / MkDocs / 纯 HTML，待官网技术栈定稿）
  2. 通过 `rsync -avz --delete` 同步到 `root@47.116.219.15:/var/www/html/`
  3. 远程执行 `docker exec nginx nginx -s reload`
  4. 健康检查 `https://promiselink.cn/` 期望 200

### 5.3 网关部署

新建 `.github/workflows/gateway-deploy.yml`：

- 触发：手动 dispatch（`workflow_dispatch`，需选择环境 `production`）
- 步骤：
  1. 构建网关镜像 `ghcr.io/<org>/promiselink-pro:<tag>`
  2. 推送 GHCR
  3. SSH 到 47.116.219.15，`docker compose pull promiselink-pro`
  4. `docker compose up -d promiselink-pro`
  5. 健康检查 `https://gateway.promiselink.cn/api/v1/health` 期望 200
  6. 失败自动回滚到上一版本镜像

### 5.4 灰度发布策略

- 官网：先部署到 `staging.promiselink.cn`（内部测试），通过后切换 `main` 部署
- 网关：通过 `X-Canary-User: true` 标头灰度，10% 用户先体验新版本，观察 24h 无异常后全量

---

## 6. 域名与证书

| 域名                        | 用途         | 备案状态 | 证书来源           | 临时方案                         |
| --------------------------- | ------------ | -------- | ------------------ | -------------------------------- |
| promiselink.cn              | 官网         | 已备案   | Let's Encrypt      | -                                |
| gateway.promiselink.cn      | 专业版网关   | 备案中   | Let's Encrypt      | `47.116.219.15:8001`（自签证书） |
| staging.promiselink.cn      | 预发环境     | 已备案   | Let's Encrypt      | -                                |

证书续签由 Certbot 自动执行，详见 §3.3.3。

> **硬约束 H5**：备案完成后，所有客户端配置（基础版 relay_client、小程序）切换到 `gateway.promiselink.cn`，临时地址 `47.116.219.15:8001` 仅在备案完成前使用。

---

## 7. 监控与告警

### 7.1 监控指标

#### 7.1.1 官网指标

- 响应时间 P50 / P95 / P99
- HTTP 5xx 错误率
- 入口流量（带宽 / QPS）
- 静态资源缓存命中率

#### 7.1.2 网关指标

- API 调用成功率（按路由细分）
- 平均延迟 / P95 延迟
- LLM 调用量（按用户 / 按小时）
- WSS 长连接数
- 限流触发次数

#### 7.1.3 服务器指标

- CPU 使用率
- 内存使用率
- 磁盘使用率
- 网络出入流量
- Docker 容器资源占用

### 7.2 告警规则

| 告警项                          | 阈值                     | 触发条件          | 通知渠道 |
| ------------------------------- | ------------------------ | ----------------- | -------- |
| 官网不可用                      | 健康检查失败             | 连续 3 次         | 企业微信 |
| 网关 5xx 错误率                 | > 5%                     | 5min 滑动窗口     | 企业微信 |
| 服务器磁盘使用率                | > 80%                    | 持续 5min         | 企业微信 |
| 服务器 CPU 使用率               | > 90%                    | 持续 10min        | 企业微信 |
| PostgreSQL 连接数               | > 80                     | 持续 5min         | 企业微信 |
| Redis 内存使用率                | > 80%                    | 持续 5min         | 企业微信 |
| SSL 证书剩余天数                | < 14                     | -                 | 企业微信 |
| 网关 LLM 调用失败率             | > 10%                    | 5min 滑动窗口     | 企业微信 |

告警 webhook 地址通过环境变量 `WECOM_WEBHOOK_URL` 注入，禁止明文写入配置文件。

### 7.3 监控技术栈

指标采集 Prometheus（node/nginx/postgres/redis exporter）+ 存储 30 天；可视化 Grafana（仅 127.0.0.1:3000，SSH 隧道访问）；告警 Alertmanager → 企业微信 webhook。

---

## 8. 安全策略

### 8.1 nginx 安全

- **强制 HTTPS**：HTTP 80 端口全部 301 跳转到 HTTPS；TLS 仅启用 1.2 / 1.3
- **密码套件**：优先 ECDHE-ECDSA-AES256-GCM-SHA384 等强加密套件
- **安全头**：HSTS / X-Frame-Options:SAMEORIGIN / X-Content-Type-Options:nosniff / X-XSS-Protection
- **限流**：官网单 IP 100 req/min，网关单 IP 300 req/min
- **默认 server 隔离**：默认 server 仅服务静态文件，禁止 proxy_pass 到任何容器

### 8.2 网关安全

- **API Key 验证**：所有 `/api/v1/pro/*` 路由强制校验 `X-API-Key`，数据库存储 bcrypt 哈希
- **JWT token**：HS256 签名，有效期 24h，通过 refresh token 刷新
- **CORS 白名单**：仅允许 `https://promiselink.cn` 与 `http://localhost:8000`，其他来源一律拒绝
- **请求体大小限制**：LLM 请求 1MB，ASR/OCR 请求 10MB
- **SQL 注入防护**：FastAPI + SQLAlchemy ORM 参数化查询
- **速率限制**：单 License 100 次/分钟 LLM 调用，超出返回 429

### 8.3 数据安全

- **用户业务数据**：仅存储在用户本地 SQLite，云端不接收不存储
- **网关日志**：仅记录调用元数据（路由、用户 ID、时间、token 数、延迟），禁止记录请求体与响应体
- **API Key 存储**：云端 PostgreSQL 存 bcrypt 哈希 + 环境变量 `MOKA_API_KEY` 仅在 `.env`（gitignore）；本地用户主机派生密钥加密存入 `~/.opc-agents/credentials.enc`
- **传输加密**：所有云端通信强制 HTTPS / WSS
- **备份加密**：PostgreSQL 备份使用 GPG 对称加密，密钥仅 DevOps Lead 持有

> **硬约束 H8**：本文档不包含任何 API Key、密码、token 明文。所有敏感信息通过环境变量或加密文件注入。

### 8.4 服务器访问控制

- SSH 非默认端口（记录在内部运维文档）+ 密钥登录 + 禁用 root 远程登录
- 防火墙仅放行 22（SSH）/ 80 / 443，其余端口仅内网访问
- 操作审计：SSH 登录记录到 `/var/log/auth.log`，异常登录告警

---

## 9. 部署清单（Pre-deployment Checklist）

部署前必须逐项确认：

- [ ] 硬约束检查：基础版禁止云端部署（H1 / H6）
- [ ] nginx 默认 server 仅服务静态文件，未配置任何 proxy_pass（H7）
- [ ] 域名 promiselink.cn 备案完成
- [ ] 域名 gateway.promiselink.cn 备案完成（或临时使用 47.116.219.15:8001）
- [ ] SSL 证书申请完成（promiselink.cn / gateway.promiselink.cn）
- [ ] nginx 配置经 7-Role 安全审查
- [ ] 网关 API Key 与 JWT 密钥通过环境变量注入，未明文写入任何文件
- [ ] MOKA_API_KEY 配置到 `/etc/promiselink-pro/.env`（权限 600，owner root）
- [ ] PostgreSQL 初始化脚本执行（建库、建表、索引）
- [ ] Redis 持久化配置生效
- [ ] 健康检查脚本部署到 `/opt/healthcheck/healthcheck.sh`
- [ ] 监控告警（Prometheus + Alertmanager + 企业微信 webhook）配置完成
- [ ] 灰度发布计划评审通过
- [ ] 回滚预案就绪（上一版本镜像 tag 保留）
- [ ] 备份脚本部署并验证可恢复
- [ ] 防火墙规则生效（仅 22 / 80 / 443 对外）
- [ ] SSH 安全配置生效（密钥登录、禁用 root）
- [ ] 日志轮转配置生效（避免磁盘被日志写满）
- [ ] 灾难恢复演练通过（模拟网关容器崩溃 → 自动重启 → 健康检查恢复）

---

## 10. 验证标准

部署完成后必须全部通过：

| 编号 | 验证项                                                | 期望结果                          |
| ---- | ----------------------------------------------------- | --------------------------------- |
| V1   | 访问 `https://promiselink.cn`                         | HTTP 200，显示官网首页            |
| V2   | 访问 `https://gateway.promiselink.cn/health`          | HTTP 200，返回 `ok`               |
| V3   | 访问 `https://gateway.promiselink.cn/api/v1/health`   | HTTP 200，返回网关健康信息        |
| V4   | 访问 `http://47.116.219.15`                           | 301 跳转到 HTTPS，显示官网首页    |
| V5   | 访问 `https://47.116.219.15`                          | 显示官网首页，不暴露任何应用容器  |
| V6   | 访问 `http://47.116.219.15:8001`                      | 连接被拒绝（网关不直接对外）      |
| V7   | 基础版本地启动 `opc-agents start`                     | `http://localhost:8000` 可访问    |
| V8   | 基础版激活专业版 `opc-agents pro activate`            | WSS 连接建立，JWT 获取成功        |
| V9   | 基础版发起 LLM 调用                                   | 请求经网关中继到 Moka AI，返回正常|
| V10  | 基础版发起 ASR / TTS / OCR 调用                       | 被基础版 relay_client 拒绝（H4）  |
| V11  | SSL Labs 测试 `promiselink.cn`                        | A+ 等级                           |
| V12  | SSL Labs 测试 `gateway.promiselink.cn`                | A 等级或以上                      |
| V13  | 健康检查脚本 `/opt/healthcheck/healthcheck.sh`        | 全部端点返回 200 / TCP 连通       |
| V14  | 模拟网关容器崩溃                                      | docker-compose 自动重启，60s 内恢复 |
| V15  | 模拟官网健康检查连续失败 3 次                         | 企业微信收到告警                  |
| V16  | 模拟网关 5xx 错误率 > 5%                              | 5min 内企业微信收到告警           |
| V17  | 模拟服务器磁盘 > 80%                                  | 企业微信收到告警                  |
| V18  | 直接访问 nginx 默认 server 的随机 Host                | 显示官网首页，无应用泄漏          |

### 10.1 E2E 用户视角测试

发布前必须执行端到端用户视角测试，模拟真实用户使用流程：

1. **新用户首次安装**：清除环境 → `curl -fsSL https://promiselink.cn/install.sh | bash` → 启动 → 看到欢迎页
2. **新用户激活专业版**：测试 License 激活 → 发起对话 → 收到 LLM 响应
3. **老用户升级**：`pip install --upgrade opc-agents` → 数据迁移正常 → 启动正常
4. **网络异常场景**：断网 → UI 提示网关不可达 → 恢复网络 → 自动重连
5. **License 失效场景**：过期 License → 提示重新激活 → 不崩溃
6. **小程序对接场景**：小程序扫码 → 网关 WSS 中继与用户电脑对接 → 数据双向流通
7. **官网导航**：首页 → 下载 → 文档 → 快速入门 → 反馈表单，全链路无死链
8. **多语言切换**：官网与基础版在中/英/日文之间切换正常

E2E 测试脚本位于 `tests/e2e/test_e2e_real.py`，发布前必须全部通过。灾难恢复 RTO 目标：网关容器崩溃 < 60s（docker-compose 自动重启）、PostgreSQL 损坏 < 30min（每日 02:00 自动备份，保留 14 天）、SSL 证书过期 < 5min（Certbot 提前 30 天自动续签）。

---

## 11. 相关文档

| 文档                                                      | 关联章节                                |
| --------------------------------------------------------- | --------------------------------------- |
| [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md)                 | §OKR-4 运营基础设施                     |
| [ASSESSMENT_INITIAL_VISION_v0.4.0.md](../assessments/ASSESSMENT_INITIAL_VISION_v0.4.0.md) | §5.4 运营基础设施缺失 |
| [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md)             | 基础版本地部署 + 专业版云端网关         |
| [QUICK_START_BETA.md](../guides/QUICK_START_BETA.md)       | 安装引导                                |
| [SECURITY_DESIGN.md](../internal/SECURITY_DESIGN.md)      | 安全设计总览                            |
| [Dockerfile](../../Dockerfile)                            | 基础版容器化                            |
| [docker-compose.yml](../../docker-compose.yml)            | 容器编排                                |
| [scripts/start.sh](../../scripts/start.sh)                | 本地启动脚本                            |
| [scripts/install.sh](../../scripts/install.sh)            | 一键安装脚本                            |
| [.github/workflows/release.yml](../../.github/workflows/release.yml) | PyPI 发布流程                |

---

## 12. 变更记录

| 版本         | 日期       | 变更内容                | 作者        |
| ------------ | ---------- | ----------------------- | ----------- |
| v0.5.0-draft | 2026-07-19 | 初始版本，7-Role 共识   | DevOps Lead |

> 硬约束 H1-H8 的落地章节已在 §1.3 列出，任何对本文档的变更必须经 7-Role 共识评审通过，并同步更新 `HARD_CONSTRAINTS.md`。
