# OPC-Agents v1.0.0 安全评审

> **状态**: Draft — 安全评审阶段
> **日期**: 2026-08-01 | **版本**: v1.0.0
> **关联 PRD**: [PRD_V5.md](../product-manager/PRD_V5.md)
> **关联 TDD**: [TDD_V1.0.0.md](../architecture/TDD_V1.0.0.md)
> **负责人**: Security Lead

---

## 1. 评审范围

v1.0.0 新增能力：

- PromiseLink HTTP API 集成
- L3 定时主动执行（Scheduler）
- CRM 完全解冻
- 客户跟进/承诺/提醒能力

评估内容：

- 关键决策点保护能否覆盖自动任务
- Token、PII、关系数据的保密性
- 路由误用和接口混淆
- 多用户数据隔离
- 审计可追溯性

---

## 2. 威胁建模（STRIDE）

### S 假冒（来源可信）

- 通过构造实体 ID 访问他人数据：OPC-Agents 只存 ID，请求 PromiseLink 验证所有权
- Token 滥用：Bearer Token Fernet 加密存储；URL 明确，不进入日志

### T 篡改（数据被改）

- 事件管线完成后客户端写入虚假承诺：客户端只能读取任务结果并写入本地视图，不直接修改 PromiseLink
- scheduler 修改任务参数：参数必须从有限枚举选择，禁止 shell/Python 表达式

### R 否认（不承认做过）

- 自动任务执行必须写入审计：trace_id、status、参数哈希、调用时长
- 邮件/财务/报告自动执行必须经过三贤者，记录每个脑的输入与决策

### I 泄露（信息被偷）

- Token/PII 不进入日志、报告、错误信息、截图
- 导出文件必须脱敏，禁止包含 Token
- API URL SSRF 防护：禁止内网/回环地址（配置白名单或默认值限定）

### D 拒绝服务

- circuit breaker 限制连续失败
- 健康检查频繁失败时降级而非雪崩
- scheduler 任务重试上限

### E 提权（绕过保护）

- 架构层：scheduler 不允许直接调用 SMTP/finance 写入等底层接口
- 测试层：架构测试必须阻断绕过路径
- 关键决策点：超时或否决必须 fail-close

---

## 3. 关键决策点扩展

| 任务类型 | 是否经过关键决策点 | 否决行为 |
|---------|------------------|---------|
| 一次性报告 | ❌ | — |
| 草稿邮件 | ❌（生成阶段）| — |
| 自动发送邮件 | ✅ 三贤者 | fail-close |
| 自动财务记账 | ✅ 三贤者 | fail-close |
| 自动生成并发送报告 | ✅ 三贤者 | fail-close |
| PromiseLink 实体/Todo/承诺写入 | ✅ 三贤者 | fail-close |

---

## 4. 凭据与 Token 管理

- `PROMISELINK_API_TOKEN` 通过 Fernet 加密后存储
- 不在配置页面明文回显
- 写入日志时只打印前缀哈希，不打印完整 Token
- 用户撤销 Token 后，旧请求的 trace_id 仍保留但不展示可识别信息
- 提供「断开并清除配置」操作

---

## 5. 数据隔离

```text
OPC-Agents 数据库        PromiseLink 数据库
        │                       │
        ├─ customer_refs        ├─ entities
        ├─ followup_refs        ├─ relationships
        ├─ task_executions      ├─ events
        ├─ audit_logs           ├─ todos
        └─ ...                  └─ reminders
```

- 仅通过 `entity_id` 等标识关联
- OPC-Agents 不缓存 PromiseLink 原始 PII（如电话、邮箱）
- 用户的 OPC-Agents 删除不会自动同步删除 PromiseLink 数据
- 删除/导出操作明确分两套确认流程

---

## 6. 自动化任务的安全要求

- 任务参数只能从白名单字段选择，禁止任意 JSON
- 任务创建必须二次确认（执行前显示任务名、频率、动作类型）
- 自动发送邮件必须显式开关 + 单任务级保护 + 三贤者
- scheduler 不允许加载任意 Python 模块或插件
- 关键任务参数变更必须保留历史快照
- 执行历史包含 `task_id`、时间、trace_id、状态、错误码
- 自动任务不绕过 Settings 中的用户偏好（提醒、疲劳、时区）

---

## 7. 注入与越权

- CRM 客户搜索防 SQL 注入
- 实体 ID 必须经过 UUID 校验，不允许字符串拼接 URL
- 任务名称、备注、客户标签防 XSS（Markdown/HTML 转义）
- 客户端不直接展示 PromiseLink 原始 HTML
- Webhook（未来启用）必须做签名校验

---

## 8. 错误信息与日志

禁止在错误信息、日志和 UI 中暴露：

- API Token
- 完整 Bearer 头
- SMTP 账号/密码
- LLM API Key
- 客户电话/邮箱（除授权查看页面）

允许记录：

- trace_id
- 路由模板
- 状态码
- 耗时
- 错误类别
- 用户可见原因（去敏感）

---

## 9. 缓解措施汇总

| 风险 | 缓解 |
|------|------|
| 自动任务绕过保护 | 架构测试 + 三贤者 |
| Token 泄露 | Fernet 加密 + 日志脱敏 + 撤销流程 |
| 路由错误集成 | 校准文档 + 合同测试 + schema 校验 |
| 客户数据越权 | 不缓存 PII + 每次请求校验所有权 |
| 导出文件泄露 | 脱敏 + 不含 Token + 二次确认 |
| 重复打扰用户 | 提醒疲劳控制 + 人工暂停优先级最高 |
| 用户误启自动发送 | 单任务级开关 + 三贤者 + 二次确认 |
| 数据删除不可恢复 | 删除前必须导出快照（可选）|

---

## 10. 安全测试

按 [TEST_PLAN_V1.0.0.md §8](../test/TEST_PLAN_V1.0.0.md) 执行：

- Token 出现在日志/导出即 fail
- 关键任务绕过保护即 fail
- schema mismatch 路由调用即 fail
- 多用户越权即 fail
- 自动任务失败重试上限失控即 fail
- 注入测试（CRM 搜索、任务参数、事件文本）
- 自动任务并发执行（同一任务不重复）

---

## 11. 风险与未决事项

| 事项 | 负责人 | 阻塞版本 |
|------|--------|---------|
| PromiseLink API schema 演化版本号 | 双方 | v1.0.0 |
| PromiseLink 多用户隔离保证 | PromiseLink 项目组 | v1.0.0 |
| 自动邮件/财务灰度开关 | Coder + PM | v1.0.0 |
| Scheduler 重试上限与雪崩控制 | Coder + DevOps | v1.0.0 |

---

## 12. 评审结论（草案）

> 待 Security Lead + 7-Role 共识签名。

预计结论：v1.0.0 在以下条件满足后可发布：

- 所有威胁缓解措施落地并通过安全测试
- 关键任务不绕过三贤者
- Token/PII 不泄露
- PromiseLink 不可用时本地能力完整
- 多用户隔离测试通过

---

*文档状态：安全评审草案，不代表代码已实现。*