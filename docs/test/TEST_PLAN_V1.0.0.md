# OPC-Agents v1.0.0 测试计划

> **状态**: Draft — 测试设计阶段
> **日期**: 2026-08-01 | **版本**: v1.0.0
> **关联 PRD**: [PRD_V5.md](../product-manager/PRD_V5.md)
> **关联 TDD**: [TDD_V1.0.0.md](../architecture/TDD_V1.0.0.md)
> **负责人**: Tester Lead

---

## 1. 测试目标

验证 v1.0.0 的完整用户价值闭环：

```text
会议/聊天输入 → 客户实体 → 关系推进卡 → 承诺识别
→ 跟进队列 → 草稿 → 用户确认 → 安全执行
```

同时验证：

- Scheduler 可持久化、恢复、重试和停止
- PromiseLink 当前真实路由可用
- PromiseLink 不可用时本地降级可用
- 三贤者保护不可绕过
- Token/PII 不泄露
- 真实用户通过浏览器可完成核心旅程

**原则**：测试用来发现问题，不修改测试去迁就缺陷；真实组件优先；不使用 skip 掩盖失败。

---

## 2. 测试分层

| 层级 | 目标 | 计划 |
|------|------|------|
| 静态/类型 | 风格、类型、危险模式 | ruff + mypy + Bandit |
| Unit | parser、repository、DTO、状态机 | 新增 ≥40 |
| Integration | PromiseLinkClient 与服务边界 | 新增 ≥30 |
| E2E API | 真实 PromiseLink 路由和本地回退 | 新增 ≥30 |
| E2E UI | Streamlit/浏览器用户旅程 | 新增 ≥20 |
| Security | 注入、越权、Token/PII、fail-close | 新增 ≥15 |
| Deployment | Docker、重启、迁移、恢复 | 新增 ≥10 |
| **合计** | — | **新增 ≥145，发布前全通过** |

---

## 3. API 合同测试

### 3.1 真实路由清单

必须针对 PromiseLink v0.9.0 实例验证：

- `GET /api/v1/health`
- `POST /api/v1/events` + `GET /api/v1/events/{id}`
- `GET /api/v1/entities`
- `GET /api/v1/entities/dormant?min_days=N`
- `GET /api/v1/entities/{id}`
- `GET /api/v1/entities/{id}/stage-info`
- `GET /api/v1/persons/{id}/relationship-brief/aggregated`
- `GET /api/v1/todos`
- `GET /api/v1/promises`
- `GET /api/v1/promises/stats`
- `GET /api/v1/promises/{todo_id}/nudge-draft`
- `GET/PATCH /api/v1/reminders/preferences`
- `GET /api/v1/reminders/daily`
- `POST/GET /api/v1/scheduled-events`
- `GET /api/v1/dashboard/morning-brief`
- `GET /api/v1/dashboard/care-reminders`

### 3.2 防止错误路由回归

以下调用必须在测试中确认不存在并确保客户端不使用：

- `GET /api/v1/entities?dormant_days=N`
- `POST /api/v1/todos/analyze-bidirectional`
- `POST /api/v1/nudges/generate`

### 3.3 事件异步管线

- POST `/events` 返回事件标识
- 客户端轮询详情，不假设同步完成
- 处理完成后能获取实体/Todo/承诺结果
- 超时进入 DEGRADED，不无限轮询
- 事件失败不产生虚假客户或承诺

---

## 4. CRM E2E 测试

| 编号 | 场景 | 预期 |
|------|------|------|
| CRM-E01 | 会议文本创建事件 | 产生事件 ID并可查询 |
| CRM-E02 | 事件完成后提取实体 | 客户字段正确 |
| CRM-E03 | 重复实体 | 提示合并/确认，不覆盖 |
| CRM-E04 | 沉默客户 | `min_days` 参数和评分正确 |
| CRM-E05 | 关系阶段 | stage-info 可展示 |
| CRM-E06 | 关系推进卡 | 12 模块聚合可展示 |
| CRM-E07 | 外部服务停止 | 本地 CRM 仍可用 |
| CRM-E08 | 外部响应 schema 错误 | 切换本地降级并记录原因 |
| CRM-E09 | 客户搜索注入 | 不执行 SQL/不越权 |
| CRM-E10 | 多用户数据隔离 | A 看不到 B 的实体 |

---

## 5. 客户跟进 E2E 测试

| 编号 | 场景 | 预期 |
|------|------|------|
| F-E01 | my/their 双视角 | 列表不混淆方向 |
| F-E02 | 更新履约状态 | 状态合法、审计完整 |
| F-E03 | 承诺统计 | total/履约率与源数据一致 |
| F-E04 | 逾期承诺催促草稿 | 只生成草稿 |
| F-E05 | 非 their_promise 请求催促 | 返回业务错误，不生成消息 |
| F-E06 | nudge API 失败 | 本地模板回退 |
| F-E07 | 每日提醒 | fatigue_remaining 正确 |
| F-E08 | 静默时段 | 不执行提醒发送 |
| F-E09 | Day 3/7/14 跟进 | 不重复创建任务 |
| F-E10 | 人工忽略后定时任务 | 不重新激活 |

---

## 6. Scheduler E2E 测试

| 编号 | 场景 | 预期 |
|------|------|------|
| S-E01 | 创建每日任务 | 任务持久化 |
| S-E02 | 创建每周任务 | 下次时间正确 |
| S-E03 | 进程重启 | 任务恢复 |
| S-E04 | 手动触发 | 产生执行记录 |
| S-E05 | 任务暂停/恢复 | 状态正确 |
| S-E06 | 任务失败 | 最多重试 3 次 |
| S-E07 | LLM 不可用 | 走缓存/降级 |
| S-E08 | 关键 email 任务 | 进入三贤者 |
| S-E09 | 共识超时 | BLOCKED，不发送 |
| S-E10 | 共识否决 | BLOCKED，不发送 |
| S-E11 | Scheduler 直接调用 SMTP | 架构测试阻断绕过路径 |
| S-E12 | 静默时段 | 不执行外部动作 |
| S-E13 | 任务参数注入 | 拒绝 shell/Python 表达式 |
| S-E14 | 执行历史审计 | trace/status/error 完整 |
| S-E15 | 并发触发同一任务 | 互斥，不重复执行 |

---

## 7. UI 真实用户旅程 E2E

### Journey A：首次使用

1. 打开 Streamlit
2. 配置 PromiseLink（可跳过）
3. 粘贴会议纪要
4. 等待事件管线完成
5. 确认客户实体
6. 打开 CRM 详情
7. 查看关系推进卡
8. 查看待跟进承诺
9. 生成催促草稿
10. 人工确认后进入邮件技能

### Journey B：每日主动运营

1. Scheduler 触发每日早报
2. 用户查看沉默客户
3. 用户查看到期承诺
4. 用户延后一条提醒
5. 用户完成一条跟进
6. 用户打开执行历史

### Journey C：降级与恢复

1. 停止 PromiseLink
2. CRM 页面仍可打开
3. UI 显示 local_fallback
4. 恢复 PromiseLink
5. 重新测试连接
6. 只读能力恢复
7. 任务状态没有丢失

### Journey D：关键操作保护

1. 创建定时发邮件任务
2. 触发时间到达
3. 三贤者超时或否决
4. 页面显示阻断原因
5. SMTP 未调用
6. 审计记录可追溯

---

## 8. 安全测试

- PromiseLink Token 不出现在日志、异常、导出、截图
- API URL SSRF 边界策略符合安全设计
- entity_id 越权访问返回 404/403
- 客户搜索、任务参数、事件文本防注入
- Scheduler 不执行任意 shell/代码
- 关键任务 fail-close
- circuit breaker 不因伪造响应无限重试
- Webhook/回调（如未来启用）验证签名
- 导出和删除需要用户确认
- 多用户数据隔离

---

## 9. 性能与可靠性

| 指标 | 门槛 |
|------|------|
| 本地 CRM 查询 | p95 < 500ms |
| PromiseLink 只读接口 | p95 < 2s（不含事件管线）|
| 连接健康检查 | < 2s |
| 事件轮询总时长 | ≤ 30s，超时可恢复 |
| Scheduler 触发误差 | 单机环境 ≤ 60s |
| 连续 100 次调度 | 无任务重复、无内存异常增长 |
| PromiseLink 连续失败 | 熔断且不阻塞本地核心流程 |

---

## 10. 发布门禁与真实 E2E

发布前必须提供真实命令输出：

```bash
pytest -m e2e tests/e2e/ -q
pytest tests/integration/ -q
ruff check .
mypy opc_manager
bandit -r opc_manager
pip-audit
```

发布前额外条件：

- PromiseLink v0.9.0 真实实例启动
- 真实 HTTP API smoke 全通过
- 真实 Streamlit + Playwright 用户旅程全通过
- Docker 构建、重启、卷恢复验证
- 不允许用 `skip`、`xfail` 或修改断言隐藏失败
- 测试报告保存实际命令输出和环境信息

---

## 11. 缺陷处理规则

- 阻塞发布：关键操作绕过 fail-close、数据越权、Token 泄露、真实路由错误、数据丢失
- 高优先级：核心 CRM/跟进旅程失败、降级失败、Scheduler 重复执行
- 中优先级：非核心 UI、边界文案、低频导出问题
- 所有修复先更新缺陷记录，再修改代码，修复后重跑对应测试和全量回归

---

*文档状态：测试计划草案，不代表测试已执行。*