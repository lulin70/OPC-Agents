# OPC-Agents 推进计划：v0.3.35（T7 第 1 批 Mock 替换 — 校准后范围）

> **创建日期**: 2026-07-18 | **当前版本**: v0.3.34 → v0.3.35 | **依据**: [ROADMAP v0.3.34](ROADMAP_v0.3.34.md) + 5 文件实际 Mock 分布深度调查
>
> **工作流**: 文档先行 → 7-role 共识 → 按生命周期推进 → 充分验证 → 推送 Git
>
> **版本约束**: T7 为测试质量提升，无新功能。按用户约束"功能没有更新则版本不变前两位"，采用 PATCH 升级（v0.3.35），不递增 MINOR。

---

## 0. 前提校准（2026-07-18）

> **关键发现**: 原 ROADMAP_v0.3.34.md 描述的"5 文件 266 处 Mock 替换"严重过期。深度调查发现 5 文件中已有 2 文件（test_timeline_view / test_live_log_panel）部分重构为 Fake 类，实际可替换 Mock 远少于 266 处。遵循 project_memory 教训"基于过期描述的任务需先校验前提"，本节诚实校准范围。

### 0.1 原 ROADMAP 描述 vs 实际 Mock 分布

| # | 文件 | 原 ROADMAP 描述 | 实际 Grep 数 | 实际可替换 | 必要保留 |
|---|------|----------------|-------------|-----------|---------|
| T7.1 | tests/unit/test_mcp_transport.py | 61 处 | 71 行匹配 | ~0-7 处 | 16 @patch.dict(os.environ) + 3 uvicorn + 2 StdioTransport + 1 SSE_AVAILABLE + 3 start_sse_server/create_sse_app |
| T7.2 | tests/unit/test_simple_llm_service.py | 60 处 | 65 行匹配 | ~7-15 处 | 7 requests.post（可改 responses 库）+ 8 _discover_all_providers + 8 llm_cache + 8 _llm_thread_semaphore + 8 sanitize_for_llm + 2 time.sleep |
| T7.3 | tests/integration/test_email_skill_coverage.py | 51 处 | 51 行匹配 | ~10-20 处 | ~20 smtplib.SMTP_SSL/SMTP（无真实 SMTP 服务器）+ 5 crm_skill.get_customer + 2 _count_today_sends/_check_rate_limit + 2 time.sleep + 1 MAX_RETRIES |
| T7.4 | tests/integration/test_timeline_view.py | 52 处 | 52 行匹配 | ~5 处 | 9 timeline_data.st + 12 timeline_view.st（streamlit ScriptRunContext 必需） |
| T7.5 | tests/integration/test_live_log_panel.py | 42 处 | 42 行匹配 | ~5 处 | 3 _WORKSPACE_DIR + 3 psutil + 1 builtins.__import__ + 5 collect_*_logs + 多处模块常量 |
| **合计** | 5 文件 | **266 处** | **281 行** | **~27-52 处** | **大部分为必要 Mock** |

### 0.2 已有 Fake 类重构（v0.3.33 之前完成）

**test_timeline_view.py** 已有：
- `FakeUndoManager(UndoManager)` — 真实子类添加 `list_records()` 别名
- `FakeAuditLog` — 提供 `get_recent_entries()` 返回真实 dict 条目
- `FakeProgressEmitter` — 提供 `get_history()` 返回真实 dict 条目

**test_live_log_panel.py** 已有：
- `FakeAuditLog` — 提供 `query()` 返回真实 dict 条目列表
- `reset_cache_singleton` fixture — 重置 LogCache 单例

### 0.3 校准结论

**T7 第 1 批的真实价值不在于"减少 Mock 数量"，而在于**：
1. 提升 Mock 透明度（用 fake 类替代 MagicMock 桩，提升可读性）
2. 减少 MagicMock 反模式（Mock 装真实类）
3. 用真实组件替代不必要的 Mock（如 _get_smtp_config → tmp_path fixture）
4. 引入 responses 库提升 HTTP 测试真实性

**不强行替换必要 Mock**（streamlit/外部服务/分支控制/环境变量），避免为凑数而破坏测试隔离。

---

## 1. v0.3.35 任务清单（校准后范围）

### T7.1: test_mcp_transport.py（P2，评估后跳过）

> **决策说明**: T7.1.1 评估后跳过。stdin/stdout patch 替换为 io.StringIO 的价值低：
> 1. Mock 数量不减（仍需 patch sys.stdin/sys.stdout 全局对象）
> 2. 需修改断言模式（`call_args_list` → `getvalue()`），有破坏测试意图风险
> 3. 已有 MagicMock 是合理的 file-like mock，符合测试隔离原则
>
> 遵循 ROADMAP 第 0.3 节"不强行替换必要 Mock，避免为凑数而破坏测试隔离"。

| # | 子任务 | 优先级 | 复杂度 | 状态 |
|---|--------|--------|--------|------|
| T7.1.1 | 7 处 stdin/stdout patch 改用 io.StringIO | P2 | 低 | ⏸ 评估后跳过（价值低 + 风险中） |
| T7.1.2 | 文档化保留的 16 @patch.dict + 9 @patch 必要性 | P2 | 低 | ✅ 已在 ROADMAP 第 0.1 节文档化 |

**保留必要 Mock**：
- 16 `@patch.dict(os.environ, ...)` — 环境变量隔离
- 3 `@patch("uvicorn.run")` — 避免启动真实 uvicorn
- 2 `StdioTransport` patch — 测试 main 函数
- 1 `SSE_AVAILABLE` patch — 分支控制
- 3 `start_sse_server/create_sse_app` patch — 避免真实 SSE 服务器
- 7 `sys.stdin/sys.stdout` patch — 全局对象必须 patch（file-like MagicMock 是合理 mock）

### T7.2: test_simple_llm_service.py（P1，8 处已替换）

| # | 子任务 | 优先级 | 复杂度 | 状态 |
|---|--------|--------|--------|------|
| T7.2.1 | 7 处 `requests.post` → responses 库（真实 HTTP mock） | P1 | 中 | ✅ 完成 |
| T7.2.2 | 1 处 `settings.get_settings` MagicMock → FakeSettings 类（其余 7 处为 ImportError side_effect，必要保留） | P1 | 中 | ✅ 完成 |
| T7.2.3 | requirements-dev.txt 添加 responses 依赖 | P1 | 低 | ✅ 完成 |

**保留必要 Mock**：
- 8 `_discover_all_providers` patch — 测试隔离
- 8 `llm_cache.get_llm_cache` patch — 避免 DB 副作用
- 8 `_llm_thread_semaphore` patch — 并发控制
- 8 `sanitize_for_llm` patch — 避免依赖
- 2 `time.sleep` patch — 跳过等待

### T7.3: test_email_skill_coverage.py（P1，18 处已替换）

| # | 子任务 | 优先级 | 复杂度 | 状态 |
|---|--------|--------|--------|------|
| T7.3.1 | 18 处 `_get_smtp_config` patch → tmp_path fixture + 真实 save_smtp_config | P1 | 中 | ✅ 完成 |
| T7.3.2 | 文档化保留的 smtplib/crm_skill/time.sleep 必要性 | P2 | 低 | ✅ 完成 |

**保留必要 Mock**：
- ~20 `smtplib.SMTP_SSL` / `smtplib.SMTP` — 无真实 SMTP 服务器
- 5 `crm_skill.get_customer` — 避免 DB 副作用
- 2 `_count_today_sends` / `_check_rate_limit` — 测试隔离
- 2 `time.sleep` — 跳过等待
- 1 `MAX_RETRIES` — 配置覆盖

### T7.4: test_timeline_view.py（P2，4 处已替换）

| # | 子任务 | 优先级 | 复杂度 | 状态 |
|---|--------|--------|--------|------|
| T7.4.1 | 1 处 `undo_manager.get_undo_manager` patch → 直接模块属性赋值 FakeUndoManager()（1 处 return_value=None 保留） | P2 | 低 | ✅ 完成 |
| T7.4.2 | 1 处 `audit_log.AuditLog` patch → 直接模块属性赋值 FakeAuditLog() | P2 | 低 | ✅ 完成 |
| T7.4.3 | 2 处 `progress_emitter.get_progress_emitter` patch → 直接模块属性赋值 FakeProgressEmitter() | P2 | 低 | ✅ 完成 |

**保留必要 Mock**：
- 9 `frontend.components.timeline_data.st` — streamlit ScriptRunContext 必需
- 12 `frontend.components.timeline_view.st` — streamlit ScriptRunContext 必需

### T7.5: test_live_log_panel.py（P2，6 处已替换）

| # | 子任务 | 优先级 | 复杂度 | 状态 |
|---|--------|--------|--------|------|
| T7.5.1 | 2 处 `audit_log.AuditLog` patch → monkeypatch + FakeAuditLog() | P2 | 低 | ✅ 完成 |
| T7.5.2 | 2 处 `progress_emitter.ProgressEmitter` patch → monkeypatch + FakeProgressEmitter() | P2 | 低 | ✅ 完成 |
| T7.5.3 | 2 处 `Path` patch → tmp_path fixture + `_WORKSPACE_DIR` patch | P2 | 低 | ✅ 完成 |

**保留必要 Mock**：
- 3 `_WORKSPACE_DIR` patch — 模块常量
- 3 `psutil.cpu_percent/virtual_memory/disk_usage` — 外部库
- 1 `builtins.__import__` — 分支控制
- 5 `collect_*_logs` patch — 避免文件系统访问

### 总体范围校准与执行结果

| 维度 | 原 ROADMAP | 校准后预期 | 实际执行 | 差异 |
|------|-----------|-----------|---------|------|
| 可替换 Mock 数量 | 266 处 | ~27-52 处 | **36 处**（T7.2:8 + T7.3:18 + T7.4:4 + T7.5:6 + T7.1:0） | -86% vs 原 ROADMAP |
| 真实价值 | 数量减少 | 透明度提升 + 反模式消除 | ✅ 达成（responses 库 + FakeSettings + 真实 save_smtp_config + Fake 类替换） | 价值重定义 |
| 工作量 | 高 | 中-低 | 低（4 并行子代理完成） | 大幅降低 |
| 测试通过 | — | — | 222 passed（28+61+59+74）+ 0 failed | ✅ |

---

## 2. 生命周期阶段映射

### P1 需求分析（PM 主导）

**T7 第 1 批校准后范围**：5 文件 ~27-52 处 Mock 改进，聚焦：
1. **真实性提升**：requests.post → responses 库（真实 HTTP mock）
2. **透明度提升**：MagicMock 桩 → Fake 类（已有 FakeAuditLog 等）
3. **依赖简化**：_get_smtp_config patch → tmp_path fixture

**验收标准**：
- 5 文件中可替换 Mock 全部替换（~27-52 处）
- 全量回归 0 failed
- E2E 0 failed
- ruff/black/mypy/radon cc 全绿
- 版本同步 18+ 文件 0.3.34→0.3.35

### P3 技术设计（Architect + Coder）

**替换原则**（遵循 project_memory 教训）：
1. 保留 streamlit Mock（ScriptRunContext 运行时必需）
2. 保留外部服务 Mock（uvicorn/smtplib/psutil/requests 无真实服务时必需）
3. 保留分支控制 Mock（SSE_AVAILABLE/__import__ 必需）
4. 保留环境变量 Mock（@patch.dict os.environ 必需）
5. 保留测试隔离 Mock（_discover_all_providers/llm_cache 必需）
6. **替换为真实组件**（优先）：_get_smtp_config → tmp_path + save_smtp_config
7. **替换为 fake 类**（当真实组件有副作用时）：MagicMock → FakeSettings/FakeAuditLog
8. **替换为库**（当 mock 模式复杂时）：requests.post → responses 库

**fake 类设计规范**：
- 必须实现与真实组件相同的协议/方法签名
- 返回真实数据结构（dict/list/object），不返回 MagicMock
- 记录调用历史供断言
- 无外部副作用（网络/DB/文件系统）

### P7 测试规划（Tester）

| 任务 | 测试策略 |
|------|----------|
| T7.1 | 7 处 stdin/stdout 改用 io.StringIO 后，运行 test_mcp_transport.py 全部测试 |
| T7.2 | 7 处 requests.post → responses 后，运行 test_simple_llm_service.py 全部测试 |
| T7.3 | _get_smtp_config → tmp_path fixture 后，运行 test_email_skill_coverage.py 全部测试 |
| T7.4 | @patch 类 → Fake 类后，运行 test_timeline_view.py 全部测试 |
| T7.5 | @patch 类 → Fake 类后，运行 test_live_log_panel.py 全部测试 |
| 全量回归 | `pytest --ignore=tests/e2e --timeout=30 -q` 0 failed |
| E2E | `pytest tests/e2e/test_e2e_real.py -v` 28 passed + 0 failed |

### P8 实现（Coder）

按 T7.2 → T7.3 → T7.4 → T7.5 → T7.1 顺序实现（按 ROI 排序：高价值优先）。

### P9 测试执行（Tester）

```bash
# 单文件验证
PYTHONPATH=. venv/bin/python -m pytest tests/unit/test_mcp_transport.py -v --timeout=30
PYTHONPATH=. venv/bin/python -m pytest tests/unit/test_simple_llm_service.py -v --timeout=30
PYTHONPATH=. venv/bin/python -m pytest tests/integration/test_email_skill_coverage.py -v --timeout=30
PYTHONPATH=. venv/bin/python -m pytest tests/integration/test_timeline_view.py -v --timeout=30
PYTHONPATH=. venv/bin/python -m pytest tests/integration/test_live_log_panel.py -v --timeout=30
# 全量回归
PYTHONPATH=. venv/bin/python -m pytest --ignore=tests/e2e --timeout=30 -q
# E2E
PYTHONPATH=. venv/bin/python -m pytest tests/e2e/test_e2e_real.py -v --timeout=120
# ruff + black + mypy + radon cc
venv/bin/ruff check opc_manager/ frontend/ tests/
venv/bin/black --check --target-version py310 opc_manager/ frontend/ tests/
venv/bin/mypy opc_manager/ --ignore-missing-imports --follow-imports=silent
venv/bin/radon cc opc_manager/ -s -n D
# 版本一致性
PYTHONPATH=. venv/bin/python -m pytest tests/unit/test_version.py -v
```

### P10 部署发布（DevOps）

- VERSION → 0.3.35
- 版本号同步（18+ 文件）
- CHANGELOG 新增 v0.3.35 条目
- Git commit + push

---

## 3. 7-Role 职责分配

| 角色 | v0.3.35 职责 |
|------|-------------|
| Architect | 校准后范围审查 + Fake 类设计规范 + responses 库选型 |
| PM | 范围校准确认 + 优先级调整 + 版本约束（PATCH）审查 |
| Security | Mock 替换不引入安全盲区 + responses 库安全审查 |
| Tester | 每文件替换后单文件测试 + 全量回归 + E2E 验证 |
| Coder | T7.1-T7.5 实现（按 ROI 排序） |
| DevOps | P10 发布流程 + requirements-dev.txt 更新 |
| UI | T7.4/T7.5 UI 组件 Mock 替换审查（streamlit Mock 保留） |

---

## 4. 验证门禁

| 门禁 | 阈值 | 验证方法 |
|------|------|----------|
| ruff | 0 error | `ruff check opc_manager/ frontend/ tests/` |
| black | 0 reformat | `black --check --target-version py310 opc_manager/ frontend/ tests/` |
| mypy | 0 error | `mypy opc_manager/ --ignore-missing-imports --follow-imports=silent` |
| radon cc | 无 D+ | `radon cc opc_manager/ -s -n D` |
| 全量回归 | 0 fail | `pytest --ignore=tests/e2e --timeout=30 -q` |
| E2E test_e2e_real | 28/28 pass | `pytest tests/e2e/test_e2e_real.py -v` |
| 版本一致性 | 18+ 文件 0.3.35 | `pytest tests/unit/test_version.py` |
| Mock 改进 | ~27-52 处替换 | 5 文件单文件测试通过 + Grep 验证减少量 |

---

## 5. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| responses 库版本不兼容 | 低 | 中 | 锁定版本到 requirements-dev.txt |
| Fake 类与真实组件签名漂移 | 中 | 中 | 替换前 grep 真实组件方法签名 |
| _get_smtp_config 替换破坏测试意图 | 中 | 中 | 每文件替换后运行单文件测试 |
| stdin/stdout patch 改用 io.StringIO 行为变化 | 低 | 低 | io.StringIO 与 file-like 行为一致 |
| 范围校准导致工作量低于预期 | 高 | 低 | 诚实记录，不强行扩大范围 |

---

## 6. 共识审查记录

> 7-role 审查结果记录在此节，审查通过后进入实现阶段。

### 审查日期: 2026-07-18

### 7-Role 审查结论

| 角色 | 立场 | 关键意见 | 是否阻塞 |
|------|------|----------|----------|
| **Architect** | ✅ 同意 | 范围校准合理（基于实际 Grep 数据）；Fake 类设计规范清晰；responses 库选型正确（HTTP mock 业界标准）；保留必要 Mock 清单完整 | 否 |
| **PM** | ✅ 同意 | T7 为测试质量提升非功能更新，PATCH 升级正确；范围校准确认了"不强行替换必要 Mock"原则；ROI 排序合理（T7.2/T7.3 高价值优先） | 否 |
| **Security** | ✅ 同意 | responses 库安全（本地拦截 HTTP 请求，无外部网络）；Fake 类不访问外部资源；保留 smtplib Mock 避免真实 SMTP 连接 | 否 |
| **Tester** | ✅ 同意 | 每文件单文件测试 + 全量回归 + E2E 验证策略完善；校准后范围测试意图保持明确 | 否 |
| **Coder** | ✅ 同意 | 校准后工作量大幅降低（~27-52 处 vs 原 266 处）；T7.4/T7.5 已有 Fake 类可复用；T7.2 responses 库 API 简单 | 否 |
| **DevOps** | ✅ 同意 | responses 加入 requirements-dev.txt；v0.3.35 发布流程标准；版本同步 18+ 文件 | 否 |
| **UI** | ✅ 同意 | streamlit Mock 保留（ScriptRunContext 必需）；T7.4/T7.5 UI 组件 Fake 类审查通过 | 否 |

### 共识结论

**7/7 一致通过**。v0.3.35 范围校准为 5 文件 ~27-52 处 Mock 改进，聚焦真实性/透明度/依赖简化。可进入 P8 实现阶段。

---

## 7. 活文档维护规则

1. 每个任务完成后更新本文档任务清单状态（⏳→✅）
2. 共识审查结果实时记录到第 6 节
3. 验证结果实时记录到第 4 节
4. 如计划变更，更新任务清单并标注变更原因
5. 版本发布后，本文档归入 docs/internal/archive/

---

## 8. 变更日志

| 日期 | 变更内容 | 变更原因 |
|------|----------|----------|
| 2026-07-18 | 创建文档，T7 第 1 批校准后范围（~27-52 处 vs 原 266 处） | 深度调查发现 5 文件中 2 文件已有 Fake 类重构，原 ROADMAP 描述过期 |
| 2026-07-18 | T7.2/T7.3/T7.4/T7.5 全部完成（36 处替换）；T7.1 评估后跳过（stdin/stdout patch 价值低） | 4 并行子代理实施 + 222 passed + 0 failed；T7.1 遵循"不强行替换必要 Mock"原则 |
