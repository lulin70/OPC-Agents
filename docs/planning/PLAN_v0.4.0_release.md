# OPC-Agents v0.4.0 发布前工作计划

> **创建日期**: 2026-07-18 | **目标版本**: v0.4.0 | **状态**: in_progress
>
> **前置评估**: [D07 v0.3.36 项目整理评估](../assessments/ASSESSMENT_D07_TIDY_v0.3.36.md)（88.3 分 B+，Phase 1 100%）

---

## 工作项

### 任务 1: 短期问题修复（P2 短期可选）

#### 1.1 bandit B608 误报 # nosec 注释（5 处）

| # | 文件:行 | 代码模式 | 安全性 |
|---|---------|----------|--------|
| 1 | [crm_skill.py:158](file:///Users/lin/trae_projects/OPC-Agents/opc_manager/crm_skill.py#L158) | `where_parts.append(f"{col} {op} ?")` + `_CRM_WHERE_COLUMNS` 白名单 | ✅ 字段名白名单 + 值参数化 |
| 2 | [knowledge_skill.py:129](file:///Users/lin/trae_projects/OPC-Agents/opc_manager/knowledge_skill.py#L129) | `set_clauses.append(f"{col}=?")` + `_KNOWLEDGE_UPDATEABLE_COLUMNS` 白名单 | ✅ 字段名白名单 + 值参数化 |
| 3 | [knowledge_skill.py:182](file:///Users/lin/trae_projects/OPC-Agents/opc_manager/knowledge_skill.py#L182) | `where_clause = " AND ".join(conditions)` (固定条件) | ✅ 固定 SQL 模板 |
| 4 | [task_skill.py:141](file:///Users/lin/trae_projects/OPC-Agents/opc_manager/task_skill.py#L141) | `where_parts.append(f"{col}{op}?")` + `_TASK_WHERE_COLUMNS` 白名单 | ✅ 字段名白名单 + 值参数化 |
| 5 | [user_profile.py:202](file:///Users/lin/trae_projects/OPC-Agents/opc_manager/user_profile.py#L202) | `updates.append(f"{key}=?")` + `allowed` 白名单 | ✅ 字段名白名单 + 值参数化 |

**已有 nosec 处理**: [skill_reviews.py:277](file:///Users/lin/trae_projects/OPC-Agents/opc_manager/skill_reviews.py#L277) `# nosec B608 — placeholders are "?" only, values parameterized`

**修复方式**: 添加 `# nosec B608 — <reason>` 注释，参照 skill_reviews.py:277 的格式

#### 1.2 Mock 分类文档（监控新增测试遵循"必要 Mock"分类）

新建 `docs/spec/MOCK_CLASSIFICATION_GUIDE.md`，内容：
- 7 类 Mock 判定标准（参照 D07 评估报告）
- 反模式 vs 必要 Mock 对照表
- 新增测试 Mock 自检清单
- T7 系列关闭总结（5 文件 42 处替换 + 56 文件 532 处必要 Mock）

### 任务 2: 架构演进评估（P3 长期）

#### 2.1 tool_system.py 拆分状态确认

**结论**: ✅ 已完成拆分，无需进一步操作

现状（v0.3.36 实测）:
- `tool_system.py` (222 行) — Facade，组合 Registry + 3 Handlers
- `tool_registry.py` (130 行) — 数据模型 + 注册/发现/调用分发 + 输入长度校验（99% coverage）
- `tool_handlers_fs.py` (91 行) — 文件系统工具处理器 + 路径校验（100% coverage）
- `tool_handlers_smtp.py` (70 行) — 邮件工具处理器 + CRLF 注入防护（100% coverage）
- `tool_handlers_cmd.py` (33 行) — 命令执行处理器 + shlex 白名单防护（85% coverage）
- `tool_audit_logger.py` (119 行) — 审计日志（84% coverage）

PROJECT_STATUS.md L173 "tool_system.py 拆为 tool_registry/tool_audit/tool_handlers_fs/tool_handlers_smtp" 已完成，应标记为 ✅。

#### 2.2 其他大文件 SRP 评估

| 文件 | 行数 | SRP 评估 | 建议 |
|------|------|----------|------|
| data_manager.py | 790 | 待评估 | 需 SRP 分析（非行数阈值）|
| task_engine_v3_executors.py | 788 | 待评估 | 需 SRP 分析 |
| scenario_definitions_builtin.py | 775 | 已知（内置场景定义）| 文件大但 SRP 单一，不建议拆 |
| task_orchestrator.py | 774 | 待评估 | 需 SRP 分析 |
| knowledge_bridge.py | 725 | 已有 7 处 nosec B310 | URL fetch 职责单一，不建议拆 |

**判定原则**（参照 project_memory 教训）:
> God Class identification should be based on 'single class with multiple responsibilities' rather than mechanical threshold of 'method count >30' or 'line count >500/800'. 累计 52 候选 → 1 TRUE / 51 FALSE = 1.9% hit rate (98.1% 误判率)

**本任务只做评估，不做拆分**。如评估发现真 God Class，记入 ROADMAP 作为 v0.5.0 任务。

### 任务 3: v0.4.0 发布准备（P0-P1 必做）

#### 3.1 D05 E2E 37/37 用户旅程验证

```bash
# 运行 E2E 测试（独立运行，避免 sync_playwright 事件循环污染）
venv/bin/python -m pytest tests/e2e/test_ui_playwright.py -v --tb=short
# 期望: 21 passed, 0 failed, 0 skipped
```

参考 [D05 E2E 评估](../assessments/ASSESSMENT_E2E_D05.md)（v0.4.0 发布前已完成 37/37 用户旅程）。

#### 3.2 Release Notes 准备

新建 `docs/releases/RELEASE_NOTES_v0.4.0.md`，内容：
- v0.4.0 亮点（Phase 1 100% 完成 + 覆盖率 83% + T7 关闭 + SQLite 锁根治 + mypy 15→0）
- 版本跨度（v0.3.27 → v0.4.0，13 个版本）
- 关键改进列表
- 已知限制
- 升级指南

#### 3.3 版本号升级

- VERSION: 0.3.36 → 0.4.0
- opc_manager/version.py: `__version__ = "0.4.0"`, `__version_info__ = (0, 4, 0)`
- opc_manager/mcp_protocol.py: MCP_SERVER_VERSION = "0.4.0"
- pyproject.toml: version = "0.4.0" (dynamic from version.py)
- Dockerfile: ARG VERSION=0.4.0
- 三语 README: v0.3.36 → v0.4.0 Highlights
- CHANGELOG: 新增 [0.4.0] 条目
- PROJECT_STATUS.md: 版本号 + 状态从 Beta → Stable

---

## 执行顺序

1. **任务 1.1**: bandit B608 nosec 注释（5 处） — 简单，立即执行
2. **任务 1.2**: Mock 分类文档 — 文档级别
3. **任务 2.1**: tool_system.py 拆分状态确认 — 已完成，更新文档
4. **任务 2.2**: 大文件 SRP 评估 — 评估-only，给方案
5. **任务 3.1**: E2E 37/37 验证 — 运行测试
6. **任务 3.2**: Release Notes 准备
7. **任务 3.3**: 版本号升级（v0.3.36 → v0.4.0）
8. **闭环**: 回归测试 + 文档同步 + Git 推送 + tag v0.4.0

---

## 验收标准

- ✅ bandit -ll 输出无 B608 警告（全部 nosec 或修复）
- ✅ Mock 分类文档存在且完整
- ✅ tool_system.py 拆分状态在 PROJECT_STATUS.md 中标记为 ✅
- ✅ E2E 测试 21/21 通过
- ✅ Release Notes 文档存在
- ✅ 版本号在所有位置统一为 0.4.0
- ✅ 全量测试通过（4164+ passed, 0 failed）
- ✅ ruff/mypy/radon D+/black/bandit 全绿
- ✅ Git tag v0.4.0 已打

---

## 风险与回滚

- **风险 1**: 版本号升级遗漏导致 CI 失败
  - 缓解: `grep -r "0.3.36" .` 全量检查
  - 回滚: git revert
- **风险 2**: E2E 测试失败（环境/网络问题）
  - 缓解: 先在本地跑一次，失败则修复后再升版本
  - 回滚: 不打 tag，推迟 v0.4.0
- **风险 3**: 版本升级破坏向后兼容
  - 缓解: v0.3.x → v0.4.0 是 MINOR 升级，应该向后兼容
  - 回滚: git revert
