# OPC-Agents v1.0.0 DevOps 部署计划

> **状态**: Draft — 部署设计阶段
> **日期**: 2026-08-01 | **版本**: v1.0.0
> **关联 PRD**: [PRD_V5.md](../product-manager/PRD_V5.md)
> **关联 TDD**: [TDD_V1.0.0.md](../architecture/TDD_V1.0.0.md)
> **负责人**: DevOps Lead

---

## 1. 部署目标

- OPC-Agents v1.0.0 独立部署，与 PromiseLink 通过 HTTP 通信
- Scheduler 在 OPC-Agents 进程内运行，跨重启保留任务
- 默认零外部依赖；启用 PromiseLink 才需要 PromiseLink 实例
- 三种交付方式：pip、源码、Docker
- 部署变更具备可回滚能力

---

## 2. 运行时拓扑

```text
┌────────────────────────────────────────────────────┐
│ Host                                                │
│                                                     │
│  OPC-Agents process (Streamlit :8501 + API :8900) │
│       │                                             │
│       ├─ SQLite (local, AES-256)                   │
│       ├─ Scheduler (in-process, persistent)        │
│       ├─ CarryMem (local)                          │
│       └─ PromiseLink Client                        │
│              │                                      │
│              │ HTTPS                                │
│              ▼                                      │
│       PromiseLink v0.9.0 (FastAPI :8200)            │
└────────────────────────────────────────────────────┘
```

单机部署；如需多实例，需要引入持久队列（v1.1.0 评估）。

---

## 3. 数据持久化

### 3.1 OPC-Agents 本地

- `data/opc.db`：SQLite，AES-256 加密
- `data/scheduler.db`：Scheduler 表（tasks/executions），独立或合并 SQLite
- `data/backup/`：定期自动备份

### 3.2 数据迁移

v1.0.0 新增表：

```sql
scheduled_tasks (...)
task_executions (...)
customer_refs (entity_id, last_synced_at, source)
followup_refs (todo_id, entity_id, status, last_synced_at)
```

迁移策略：

- Alembic 风格迁移文件
- 启动时自动检查版本
- 不可逆迁移需 PM 批准
- 失败保留备份并回滚

---

## 4. 部署方式

### 4.1 pip 部署

```bash
pip install opc-agents
opc-agents init
opc-agents start
```

- 适合个人开发者
- 自动创建 `~/.opc-agents/` 配置目录
- 通过 systemd/launchd 注册服务（可选）

### 4.2 源码部署

```bash
git clone https://github.com/lulin70/OPC-Agents
cd OPC-Agents
./scripts/start.sh
```

- 适合贡献者和高级用户
- `start.sh` 串联：env check → db init → frontend build → service start

### 4.3 Docker 部署

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8501 8900
CMD ["opc-agents", "start", "--host", "0.0.0.0"]
```

- 数据卷：`-v opc_data:/app/data`
- 配置卷：`-v opc_config:/root/.opc-agents`
- 健康检查：HTTP `/api/v1/health`
- 默认非 root 用户运行

---

## 5. 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `OPC_ENV` | `dev` | `dev`/`staging`/`prod` |
| `OPC_PORT` | `8501` | Streamlit 端口 |
| `OPC_API_PORT` | `8900` | 内部 API 端口 |
| `OPC_DATABASE_URL` | `sqlite:///data/opc.db` | 数据库路径 |
| `OPC_ENCRYPTION_KEY` | （必填）| 加密密钥 |
| `OPC_SCHEDULER_ENABLED` | `true` | 是否启用调度器 |
| `OPC_SCHEDULER_TICK_SECONDS` | `60` | 调度检查间隔 |
| `PROMISELINK_ENABLED` | `false` | 是否启用集成 |
| `PROMISELINK_API_URL` | `http://localhost:8200` | API 地址 |
| `PROMISELINK_API_TOKEN` | （可选）| Bearer Token |
| `PROMISELINK_TIMEOUT_SECONDS` | `5` | HTTP 超时 |
| `PROMISELINK_CIRCUIT_THRESHOLD` | `5` | 熔断失败阈值 |
| `PROMISELINK_CIRCUIT_RECOVERY_SECONDS` | `30` | 熔断恢复时间 |

---

## 6. CI/CD 流水线

### 6.1 静态检查（必过）

- ruff 0 errors
- mypy 0 errors
- Black 一致
- Bandit 高危 0
- pip-audit 0 漏洞

### 6.2 单元/集成测试

```bash
pytest tests/unit -q
pytest tests/integration -q
```

### 6.3 E2E 测试

- 真实 PromiseLink v0.9.0 实例
- 真实 Streamlit + Playwright
- Docker 内完整路径
- 覆盖率 ≥65%

### 6.4 文档与版本一致性

- 三语 README 同步
- CHANGELOG 与代码一致
- API 文档与 openapi.json 一致
- 版本号在 pyproject.toml、__init__.py、README、CHANGELOG 一致

### 6.5 发布脚本

```bash
scripts/release.sh
```

执行顺序：

1. 检查工作目录干净
2. 全量门禁
3. 构建 wheel + sdist
4. tag + push
5. 触发 GitHub Release

---

## 7. 监控与告警

### 7.1 健康检查

- `GET /api/v1/health` 返回 200
- DB 连接、LLM 后端、PromiseLink 状态

### 7.2 Prometheus 指标

- `opc_scheduler_executions_total{task_type,status}`
- `opc_scheduler_consensus_blocked_total{task_type}`
- `opc_promiselink_requests_total{route,status}`
- `opc_promiselink_request_duration_seconds{route}`
- `opc_promiselink_fallback_total{reason}`

### 7.3 日志

- 结构化日志（JSON）
- trace_id 全链路
- Token/PII 脱敏
- 保留 30 天（可配置）

### 7.4 告警

- Scheduler 任务连续失败 ≥3 次告警
- PromiseLink 熔断开启告警
- LLM 调用失败率 > 10% 告警
- 磁盘/数据库 > 80% 容量告警

---

## 8. 备份与恢复

### 8.1 自动备份

- 每 24 小时一次
- 保留最近 7 份
- 备份路径 `data/backup/opc_YYYYMMDD_HHMMSS.db`

### 8.2 手动导出

- 用户主动触发「导出」生成可携带快照
- 包含本地数据库 + 用户偏好
- 不包含 PromiseLink 原始数据
- 不包含 Token

### 8.3 恢复流程

```bash
opc-agents stop
cp data/backup/opc_latest.db data/opc.db
opc-agents start
```

---

## 9. 回滚策略

### 9.1 版本回滚

- 保留 pip 历史版本
- `pip install opc-agents==v0.5.9` 即可回到上一版本
- 数据库迁移可向前，不可向后（迁移脚本必须向前兼容）

### 9.2 配置回滚

- `PROMISELINK_ENABLED=false` 立即停止外部调用
- `OPC_SCHEDULER_ENABLED=false` 暂停调度
- 不需要重启代码即可生效

### 9.3 关键回滚检查

- 回滚后立即验证：核心 CRUD、邮件、报告、本地 CRM
- 回滚不破坏 PromiseLink 数据
- 任务历史保留但不再触发

---

## 10. 真实环境验证

发布前必须运行：

```bash
docker compose up -d
pytest -m e2e --tb=short
opc-agents doctor
```

`opc-agents doctor` 检查项：

- 配置完整性
- 数据库读写
- LLM 后端连通性
- PromiseLink 连通性（若启用）
- SMTP 连通性（若启用）
- Scheduler 调度器状态
- 备份目录可写

---

## 11. 变更与发布流程

1. 分支命名：`feature/v1.0.0-xxx` 或 `fix/v1.0.0-xxx`
2. 提交前运行：`pre-commit run --all-files`
3. PR 必须有对应 PRD/TDD/FREEZE_LIST 引用
4. 7-Role 共识 ≥5 角色批准（PM/架构/安全/测试/DevOps）
5. 合并后自动触发 CI
6. 发布前手动运行真实 E2E 并截图
7. 发布：git tag → GitHub Release → PyPI

---

## 12. 风险与监控点

| 风险 | 监控 | 应对 |
|------|------|------|
| Scheduler 任务雪崩 | 任务执行计数 | 限流 + 熔断 |
| PromiseLink schema 变化 | schema 校验失败率 | 自动切回本地能力 |
| SQLite 写锁竞争 | 写操作 p99 | WAL 模式 + 拆分数据库 |
| 备份目录满 | 备份目录大小 | 自动清理 + 告警 |
| 升级后用户配置失效 | 启动日志 | 提供迁移向导 |

---

## 13. 部署验收

- [ ] 三种部署方式均可成功
- [ ] 数据库迁移可重复且幂等
- [ ] Scheduler 任务重启后恢复
- [ ] PromiseLink 不可用时本地能力完整
- [ ] 自动备份与恢复演练通过
- [ ] 回滚路径演练通过
- [ ] 监控指标与告警正常
- [ ] 真实用户旅程 E2E 全通过

---

*文档状态：部署计划草案，不代表代码已实现。*