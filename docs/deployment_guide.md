# OPC-Agents Docker 部署指南

**版本**: 1.0.0  
**创建日期**: 2026-04-03  
**适用系统**: macOS, Linux, Windows (with Docker Desktop)

---

## 一、快速开始

### 1.1 前提条件

确保系统已安装：
- Docker (版本 20.10+)
- Docker Compose (版本 2.0+)

### 1.2 一键部署

```bash
# 1. 克隆项目
git clone <repository-url>
cd OPC-Agents

# 2. 配置环境变量
cp .env.sample .env
vim .env  # 编辑 API 密钥

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 访问系统
# http://localhost:5000
```

---

## 二、配置文件

### 2.1 环境变量 (.env)

```bash
# API 密钥
GLM_API_KEY=your_glm_api_key_here

# 数据库配置
POSTGRES_USER=opc
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=opc_agents

# Redis 配置
REDIS_PASSWORD=your_redis_password

# 邮件通知配置（可选）
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_password

# 微信通知配置（可选）
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx

# 钉钉通知配置（可选）
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

### 2.2 Docker Compose (docker-compose.yml)

```yaml
version: '3.8'

services:
  # OPC-Agents 主应用
  opc-agents:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: opc-agents-app
    ports:
      - "5000:5000"
    environment:
      - GLM_API_KEY=${GLM_API_KEY}
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - SMTP_SERVER=${SMTP_SERVER}
      - SMTP_PORT=${SMTP_PORT}
      - SMTP_USERNAME=${SMTP_USERNAME}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
      - WECHAT_WEBHOOK_URL=${WECHAT_WEBHOOK_URL}
      - DINGTALK_WEBHOOK_URL=${DINGTALK_WEBHOOK_URL}
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped
    networks:
      - opc-network

  # PostgreSQL 数据库
  postgres:
    image: postgres:13-alpine
    container_name: opc-agents-db
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - opc-network

  # Redis 缓存
  redis:
    image: redis:6-alpine
    container_name: opc-agents-redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - opc-network

  # Nginx 反向代理（可选）
  nginx:
    image: nginx:alpine
    container_name: opc-agents-nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - opc-agents
    restart: unless-stopped
    networks:
      - opc-network

volumes:
  postgres_data:
  redis_data:

networks:
  opc-network:
    driver: bridge
```

---

## 三、Dockerfile

```dockerfile
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/config

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')"

# 启动命令
CMD ["python", "web_interface/app.py", "--host", "0.0.0.0"]
```

---

## 四、Nginx 配置 (nginx.conf)

```nginx
events {
    worker_connections 1024;
}

http {
    upstream opc_agents {
        server opc-agents:5000;
    }

    server {
        listen 80;
        server_name localhost;

        location / {
            proxy_pass http://opc_agents;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # WebSocket 支持
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            
            # 超时设置
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # 静态文件缓存
        location /static {
            proxy_pass http://opc_agents;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

---

## 五、常用命令

### 5.1 服务管理

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 重启服务
docker-compose restart

# 重启单个服务
docker-compose restart opc-agents

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f opc-agents
```

### 5.2 进入容器

```bash
# 进入应用容器
docker-compose exec opc-agents bash

# 进入数据库容器
docker-compose exec postgres bash

# 进入 Redis 容器
docker-compose exec redis redis-cli -a ${REDIS_PASSWORD}
```

### 5.3 数据库操作

```bash
# 备份数据库
docker-compose exec postgres pg_dump -U opc opc_agents > backup.sql

# 恢复数据库
docker-compose exec -T postgres psql -U opc opc_agents < backup.sql

# 查看数据库大小
docker-compose exec postgres psql -U opc -d opc_agents -c "SELECT pg_size_pretty(pg_database_size('opc_agents'));"
```

### 5.4 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build

# 清理未使用的镜像
docker image prune -f
```

---

## 六、故障排查

### 6.1 容器无法启动

```bash
# 查看日志
docker-compose logs opc-agents

# 检查配置文件
docker-compose exec opc-agents cat config.toml

# 检查环境变量
docker-compose exec opc-agents env | grep GLM
```

### 6.2 数据库连接失败

```bash
# 检查数据库是否运行
docker-compose ps postgres

# 测试数据库连接
docker-compose exec opc-agents python -c "import psycopg2; psycopg2.connect('postgresql://opc:password@postgres:5432/opc_agents')"

# 查看数据库日志
docker-compose logs postgres
```

### 6.3 内存不足

```bash
# 查看资源使用
docker stats

# 限制容器内存
# 在 docker-compose.yml 中添加：
services:
  opc-agents:
    deploy:
      resources:
        limits:
          memory: 2G
```

---

## 七、生产环境建议

### 7.1 安全加固

1. **修改默认密码**
   - 使用强密码
   - 定期更换密码

2. **启用 HTTPS**
   ```nginx
   server {
       listen 443 ssl;
       ssl_certificate /etc/nginx/ssl/cert.pem;
       ssl_certificate_key /etc/nginx/ssl/key.pem;
       ...
   }
   ```

3. **限制访问 IP**
   ```nginx
   allow 192.168.1.0/24;
   deny all;
   ```

### 7.2 性能优化

1. **增加 Worker 进程**
   ```dockerfile
   CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "web_interface.app:app"]
   ```

2. **启用 Redis 缓存**
   ```python
   from flask_caching import Cache
   cache = Cache(config={'CACHE_TYPE': 'redis'})
   ```

3. **数据库连接池**
   ```python
   from sqlalchemy import create_engine
   engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=40)
   ```

### 7.3 监控告警

1. **Prometheus 监控**
   ```yaml
   services:
     prometheus:
       image: prom/prometheus
       volumes:
         - ./prometheus.yml:/etc/prometheus/prometheus.yml
   ```

2. **Grafana 仪表板**
   ```yaml
   services:
     grafana:
       image: grafana/grafana
       ports:
         - "3000:3000"
   ```

---

## 八、备份与恢复

### 8.1 数据备份

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份数据库
docker-compose exec -T postgres pg_dump -U opc opc_agents > $BACKUP_DIR/db_$DATE.sql

# 备份配置文件
tar -czf $BACKUP_DIR/config_$DATE.tar.gz config/

# 备份数据文件
tar -czf $BACKUP_DIR/data_$DATE.tar.gz data/

echo "备份完成：$BACKUP_DIR"
```

### 8.2 数据恢复

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "用法：./restore.sh <备份文件>"
    exit 1
fi

# 恢复数据库
docker-compose exec -T postgres psql -U opc opc_agents < $BACKUP_FILE

echo "恢复完成"
```

---

## 九、总结

### 优势
- ✅ 一键部署，无需复杂配置
- ✅ 容器隔离，环境一致
- ✅ 易于扩展和维护
- ✅ 自动故障恢复

### 资源需求
- **最低配置**: 2GB RAM, 1 CPU, 20GB Disk
- **推荐配置**: 4GB RAM, 2 CPU, 50GB Disk

### 支持
- 文档：`docs/` 目录
- 问题：提交 Issue
- 社区：Discord/微信群

---

**文档维护**: OPC-Agents Team  
**最后更新**: 2026-04-03
