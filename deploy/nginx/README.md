# nginx 配置目录

> 关联设计文档：[`docs/architecture/DEPLOYMENT_ARCHITECTURE.md`](../../docs/architecture/DEPLOYMENT_ARCHITECTURE.md) §3.1
> 适用服务器：`47.116.219.15`（云端）
> 部署目标：`/etc/nginx/`

## 目录结构

```
deploy/nginx/
├── nginx.conf                          # 主配置（http 块全局配置 + 限流区域 + WSS 映射 + SSL 优化）
├── README.md                           # 本文件
└── sites-available/
    ├── default.conf                    # 默认 server（硬约束 H7 强制，仅服务静态文件）
    ├── promiselink.cn.conf             # 官网（443 静态文件 + /install.sh 别名 + 80→443 跳转）
    └── gateway.promiselink.cn.conf     # 网关反向代理（443→8001 + WSS 升级 + /health 直答）
```

## 三类 server 块说明

| 文件                              | 监听                                  | server_name              | 行为                                                                  |
| --------------------------------- | ------------------------------------- | ----------------------- | --------------------------------------------------------------------- |
| `default.conf`                    | 80 + 443（均为 default_server）       | `_`（兜底）             | 仅服务 `/var/www/html` 静态文件，禁止 proxy_pass（H7 硬约束）         |
| `promiselink.cn.conf`             | 80 + 443                              | `promiselink.cn`        | 官网首页 + `/install.sh` 别名 + 静态资源缓存 + 安全头 + 限流 100r/m   |
| `gateway.promiselink.cn.conf`     | 80 + 443                              | `gateway.promiselink.cn` | 反向代理到 `127.0.0.1:8001` + WSS 升级 + `/health` 直答 + 限流 300r/m |

## 启用方式（软链接 sites-enabled）

nginx 主配置通过 `include /etc/nginx/sites-enabled/*` 加载已启用的站点。`sites-available/` 是配置文件库，需要通过软链接启用：

```bash
# 在 47.116.219.15 服务器上执行（root 用户）
cd /etc/nginx/sites-enabled

# 启用所有站点（如软链接不存在）
ln -sf /etc/nginx/sites-available/default.conf                /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/promiselink.cn.conf         /etc/nginx/sites-enabled/promiselink.cn
ln -sf /etc/nginx/sites-available/gateway.promiselink.cn.conf /etc/nginx/sites-enabled/gateway.promiselink.cn

# 禁用某站点（删除软链接，不影响 sites-available/ 中的源文件）
# rm /etc/nginx/sites-enabled/<name>
```

## 部署步骤

### 1. 上传配置文件

```bash
# 从本地仓库根目录执行
scp deploy/nginx/nginx.conf root@47.116.219.15:/etc/nginx/nginx.conf
scp deploy/nginx/sites-available/*.conf root@47.116.219.15:/etc/nginx/sites-available/
```

### 2. 启用站点（创建软链接）

```bash
ssh root@47.116.219.15 << 'EOF'
cd /etc/nginx/sites-enabled
ln -sf /etc/nginx/sites-available/default.conf                default
ln -sf /etc/nginx/sites-available/promiselink.cn.conf         promiselink.cn
ln -sf /etc/nginx/sites-available/gateway.promiselink.cn.conf gateway.promiselink.cn
EOF
```

### 3. 测试与重载

```bash
ssh root@47.116.219.15 'nginx -t && nginx -s reload'
```

- `nginx -t` 校验配置语法 + 引用文件路径正确性
- `nginx -s reload` 平滑重载（不中断现有连接）

## SSL 证书路径

| 域名                       | 证书路径                                                                      |
| -------------------------- | ----------------------------------------------------------------------------- |
| `promiselink.cn`           | `/etc/letsencrypt/live/promiselink.cn/fullchain.pem` + `privkey.pem`          |
| `gateway.promiselink.cn`   | `/etc/letsencrypt/live/gateway.promiselink.cn/fullchain.pem` + `privkey.pem`  |

证书由 Certbot（Let's Encrypt）签发并自动续签。续签命令：

```bash
certbot renew --nginx && nginx -s reload
```

## 常见问题

| 现象                                | 排查思路                                                                                       |
| ----------------------------------- | ---------------------------------------------------------------------------------------------- |
| `nginx -t` 报 `unknown directive`   | 检查 nginx 版本是否支持 `http2`（≥1.9.5）与 `limit_req_zone`                                   |
| `nginx -t` 报 SSL 证书找不到        | 确认 `/etc/letsencrypt/live/<domain>/` 下文件存在；先执行 `certbot --nginx -d <domain>`         |
| `gateway.promiselink.cn` 502        | 检查 `promiselink-pro:8001` 容器是否启动：`docker ps | grep promiselink-pro`                    |
| 直接访问 IP 显示网关错误页          | 检查 `default.conf` 是否被启用（必须 `default_server`）；H7 硬约束禁止默认 server 代理到容器   |
| `/install.sh` 404                   | 确认 `/var/www/scripts/install.sh` 文件存在且有读权限                                           |

## 硬约束检查清单

部署前必须逐项确认（任何一项不满足即阻塞发布）：

- [ ] `default.conf` 中不存在任何 `proxy_pass` 指令（H7）
- [ ] `default.conf` 同时监听 80 与 443 端口的 `default_server`（捕获所有未匹配 Host）
- [ ] `promiselink.cn.conf` 与 `gateway.promiselink.cn.conf` 的 80 端口仅 301 跳转 HTTPS
- [ ] 所有 server 块均配置 HSTS / X-Frame-Options / X-Content-Type-Options 安全头
- [ ] 配置文件中不包含任何明文 API Key / 密码 / Token（H8）
