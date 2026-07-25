# OPC-Agents 部署目录

> **关联权威设计文档**：[`docs/architecture/DEPLOYMENT_ARCHITECTURE.md`](../docs/architecture/DEPLOYMENT_ARCHITECTURE.md)
> **适用版本**：v0.5.4
> **目标服务器**：`47.116.219.15`（云端）
> **硬约束**：H1 / H6 / H7 / H8（详见 `docs/HARD_CONSTRAINTS.md`）

本目录承载 OPC-Agents 云端部署相关的所有可执行文件：nginx 配置、部署脚本、健康检查脚本。
基础版相关脚本（`scripts/install.sh` / `scripts/start.sh`）位于仓库根目录的 `scripts/`，不在本目录内。

---

## 目录结构

```
deploy/
├── README.md                          # 本文件
├── nginx/
│   ├── nginx.conf                      # 主配置（http 块全局 + 限流 + WSS map + SSL 优化）
│   ├── README.md                       # nginx 配置说明与启用方式
│   └── sites-available/
│       ├── default.conf                # 默认 server（硬约束 H7 强制，仅服务静态文件）
│       ├── promiselink.cn.conf         # 官网（443 静态文件 + /install.sh + 80→443 跳转）
│       └── gateway.promiselink.cn.conf # 网关反向代理（443→8001 + WSS + /health 直答）
└── scripts/
    ├── deploy-website.sh               # 官网部署脚本（rsync + scp + nginx reload + 健康检查）
    └── healthcheck.sh                 # 健康检查脚本（5 端点 + 连续 3 次失败企业微信告警）
```

部署后服务器侧目录对应关系：

| 本地文件                                              | 服务器路径                                                   |
| ----------------------------------------------------- | ------------------------------------------------------------ |
| `website/*`                                           | `/var/www/html/*`                                            |
| `scripts/install.sh`（仓库根，不在本目录）            | `/var/www/scripts/install.sh`                                |
| `deploy/nginx/nginx.conf`                             | `/etc/nginx/nginx.conf`                                      |
| `deploy/nginx/sites-available/*.conf`                 | `/etc/nginx/sites-available/*.conf`                          |
| `deploy/scripts/healthcheck.sh`                       | `/opt/healthcheck/healthcheck.sh`（cron 每 1 分钟执行）      |

---

## 部署流程

### 1. 官网部署（推荐：通过 GitHub Actions 自动触发）

触发条件：push 到 `main` 分支且改动 `website/` / `deploy/nginx/` / `deploy/scripts/deploy-website.sh` / `.github/workflows/website-deploy.yml`。

```bash
git add website/ deploy/nginx/
git commit -m "deploy: 更新官网与 nginx 配置"
git push origin main
```

GitHub Actions 工作流文件：[`.github/workflows/website-deploy.yml`](../.github/workflows/website-deploy.yml)

需要的 GitHub Secrets：

| Secret 名          | 用途                                    |
| ------------------- | --------------------------------------- |
| `DEPLOY_SSH_KEY`    | 部署服务器 SSH 私钥（root 用户）         |
| `DEPLOY_SSH_HOST`   | 服务器 IP（默认 `47.116.219.15`）        |
| `DEPLOY_SSH_PORT`   | SSH 端口（默认 `22`，如改端口须配置）    |
| `WECOM_WEBHOOK_URL` | 企业微信告警 webhook（健康检查使用）     |

### 2. 官网部署（手动：本地执行脚本）

```bash
# 干跑（仅验证文件存在 + rsync dry-run，不写入远端）
./deploy/scripts/deploy-website.sh --staging

# 正式部署到生产
./deploy/scripts/deploy-website.sh --production
```

脚本会按顺序执行：

1. 前置检查（website/ + deploy/nginx/ 完整性、rsync / ssh 命令可用）
2. `rsync -avz --delete website/ root@47.116.219.15:/var/www/html/`
3. `scp deploy/nginx/sites-available/*.conf root@47.116.219.15:/etc/nginx/sites-available/`
4. SSH 远端创建 `sites-enabled` 软链接
5. SSH 远端 `nginx -t` 测试配置
6. SSH 远端 `nginx -s reload` 平滑重载
7. `curl https://promiselink.cn/` 健康检查（连续 10 次重试至 200）

### 3. 网关部署

> 网关部署（`promiselink-pro:8001` 容器镜像）由独立的 `gateway-deploy.yml` 工作流触发，
> 属于 W5-W6 阶段任务 8.7 范畴，本目录暂不包含网关镜像构建产物。
> 网关反向代理 nginx 配置 `deploy/nginx/sites-available/gateway.promiselink.cn.conf` 由本目录的官网部署流程同步到服务器。

### 4. 支撑服务部署

支撑服务（PostgreSQL / Redis / Certbot）部署在 `47.116.219.15` 服务器本地，由 docker-compose 编排。
相关 docker-compose 文件位于服务器 `/etc/promiselink-pro/docker-compose.yml`，不在本仓库中。

### 5. 健康检查（持续运行）

健康检查脚本部署位置：`/opt/healthcheck/healthcheck.sh`

cron 配置（每 1 分钟执行）：

```cron
* * * * * root /opt/healthcheck/healthcheck.sh >> /var/log/healthcheck.log 2>&1
```

环境变量配置（`/etc/environment` 或 systemd timer）：

```bash
# 硬约束 H8：webhook URL 必须通过环境变量注入，禁止明文写入配置文件
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=<your-key>
```

---

## 关联文档

| 文档                                              | 关联章节                                              |
| ------------------------------------------------- | ----------------------------------------------------- |
| [DEPLOYMENT_ARCHITECTURE.md](../docs/architecture/DEPLOYMENT_ARCHITECTURE.md) | 部署架构总览（权威设计）        |
| [HARD_CONSTRAINTS.md](../docs/HARD_CONSTRAINTS.md) | 硬约束清单（H1-H8）                                  |
| [deploy/nginx/README.md](nginx/README.md)          | nginx 配置启用方式与常见问题                          |
| [docs/guides/INSTALL_GUIDE_NON_TECHNICAL.md](../docs/guides/INSTALL_GUIDE_NON_TECHNICAL.md) | 用户本地安装指引 |
| [scripts/install.sh](../scripts/install.sh)        | 用户本地一键安装脚本（基础版，不上云）                |

---

## 常见问题排查

### 1. `nginx -t` 失败

| 错误信息                                                | 原因与解决                                                |
| ------------------------------------------------------- | --------------------------------------------------------- |
| `nginx: [emerg] unknown directive "limit_req_zone"`     | nginx 版本过旧（< 1.7.6）或缺少模块。升级 nginx          |
| `nginx: [emerg] SSL_CTX_use_PrivateKey_file() failed`   | SSL 证书路径错误或文件权限不足。先 `certbot --nginx -d <domain>` |
| `nginx: [emerg] duplicate location "/"`                 | 多个 server 块使用了相同 `listen` 但未通过 `server_name` 区分 |
| `nginx: [emerg] could not build server_names_hash`     | `server_names_hash_bucket_size` 不足。在 nginx.conf 增加 `server_names_hash_bucket_size 64;` |

排查命令：

```bash
# 远端执行
nginx -t
nginx -T | grep -A 20 'server_name promiselink.cn'
tail -50 /var/log/nginx/error.log
```

### 2. SSL 证书问题

```bash
# 查看证书有效期
openssl x509 -in /etc/letsencrypt/live/promiselink.cn/cert.pem -noout -dates

# 手动续签
certbot renew --nginx --dry-run        # dry-run 验证
certbot renew --nginx && nginx -s reload

# 查看续签 cron
crontab -l | grep certbot
```

证书签发前临时方案（自签证书）：参见 `DEPLOYMENT_ARCHITECTURE.md` §6。

### 3. 健康检查失败

```bash
# 手动执行健康检查
/opt/healthcheck/healthcheck.sh

# 查看连续失败计数
cat /var/lib/opc-healthcheck/fail-count.txt

# 清零失败计数
echo 0 > /var/lib/opc-healthcheck/fail-count.txt

# 排查端点
curl -I https://promiselink.cn/
curl -I https://gateway.promiselink.cn/health
curl -I https://gateway.promiselink.cn/api/v1/health
nc -zv 127.0.0.1 5432
nc -zv 127.0.0.1 6379
```

### 4. 部署脚本 SSH 连接失败

```bash
# 本地测试 SSH 连通性
ssh -v root@47.116.219.15 'echo ok'

# 检查 known_hosts
ssh-keygen -F 47.116.219.15

# 接受新主机指纹
ssh -o StrictHostKeyChecking=accept-new root@47.116.219.15 'echo ok'
```

### 5. rsync 同步异常

```bash
# dry-run 预览将要变更的文件
rsync -avzn --delete website/ root@47.116.219.15:/var/www/html/

# 查看远端实际文件
ssh root@47.116.219.15 'ls -la /var/www/html/'
```

---

## 硬约束检查清单（部署前必查）

任何一项不满足即阻塞发布：

- [ ] **H1 / H6**：本目录不包含任何基础版容器 / 源码 / 前端产物
- [ ] **H7**：`deploy/nginx/sites-available/default.conf` 不存在任何 `proxy_pass` 指令
- [ ] **H7**：`default.conf` 同时监听 80 与 443 端口的 `default_server`
- [ ] **H8**：所有脚本与配置不包含明文 API Key / 密码 / Token / Webhook URL
- [ ] **H8**：`WECOM_WEBHOOK_URL` 通过环境变量注入，不写入脚本
- [ ] **H8**：`DEPLOY_SSH_KEY` 通过 GitHub Secrets 注入，不写入仓库
- [ ] nginx 配置通过 `nginx -t` 校验
- [ ] bash 脚本通过 `bash -n` 语法校验
- [ ] 官网静态文件 `index.html` / `styles.css` / `404.html` 齐全

---

## 变更记录

| 版本       | 日期       | 变更内容                              | 作者        |
| ---------- | ---------- | ------------------------------------- | ----------- |
| v0.5.0     | 2026-07-19 | 初始创建：nginx + 脚本 + workflow     | DevOps Lead |
