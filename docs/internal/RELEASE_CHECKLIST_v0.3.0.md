# OPC-Agents v0.3.0-beta 发布检查清单

**检查日期**: 2026-06-25  
**目标版本**: v0.3.0-beta → v0.3.0  
**关联文档**: [REMEDIATION_PLAN_20260625.md](REMEDIATION_PLAN_20260625.md) | [TECH_DEBT_20260625.md](TECH_DEBT_20260625.md) | [PROJECT_ASSESSMENT_20260623.md](PROJECT_ASSESSMENT_20260623.md)

---

## 一、代码质量门

| 检查项 | 命令/方法 | 通过标准 | 实际结果 | 状态 |
|--------|-----------|----------|----------|------|
| 语法检查 | `python -m py_compile` 关键文件 | 无语法错误 | 已通过 | ✅ |
| 全量测试 | `PYTHONPATH=. pytest tests/ --timeout=120 -q` | 0 failure | 3223 passed, 117 skipped, 1 xpassed, 2 warnings in 204.29s | ✅ |
| 测试收集 | `PYTHONPATH=. pytest --collect-only -q` | 3341 | 3341 collected | ✅ |
| 安全扫描 | `bandit -r opc_manager/ -ll -ii` | 0 High/Medium | No issues identified | ✅ |
| 版本一致性 | `cat VERSION` vs `python -c "from opc_manager.version import __version__; print(__version__)"` | 一致 | 0.2.5 = 0.2.5 | ✅ |
| UI E2E | `pytest tests/test_ui_e2e_apptest.py -q` | 25 passed | 25 passed | ✅ |

---

## 二、P0-P1 阻塞项清零

| 级别 | 数量 | 已完成 | 剩余 |
|------|------|--------|------|
| P0 | 1 | 1 | 0 |
| P1 | 7 | 7 | 0 |
| P2（本次处理） | 4 | 4 | 0 |

**关键修复**：
- P0-1: AuditLog 后台 writer 跨测试未清理导致 SQLite 写锁竞争 hang → 已修复
- P1-1: `_serial_consensus_fallback` Decision 构造参数错误 → 已修复
- P1-2: `CRITICAL_DECISION_SKILLS` 缺少 `finance` → 已修复
- P1-3/P1-4/P1-5: 文档版本号与架构描述同步 → 已修复
- 新增修复：`frontend/app.py` atexit 访问 `st.session_state` 导致测试收尾日志错误 → 已修复

---

## 三、UI/UX 真实运行验证

**验证环境**: `streamlit run frontend/app.py`, 浏览器视口 632px × 652px  
**验证方法**: 浏览器截图 + DOM 检查 + 真实点击/输入操作

| 页面/操作 | 结果 | 证据/说明 |
|-----------|------|-----------|
| 应用启动 | ✅ | 页面标题 "一人公司助手"，无控制台 JS 错误 |
| 跳过引导 | ✅ | 点击后 onboarding overlay 关闭 |
| 首页/对话页 | ✅ | 侧边栏导航、场景按钮、快捷入口、输入框均渲染 |
| Dashboard 页 | ✅ | 导航切换正常，显示时间线图表 |
| 设置页 | ✅ | 显示“安全设置/个人信息/数据备份”标签页与输入框 |
| 聊天输入提交 | ⚠️ | 输入“帮我写一份周报”并点击 Send，触发任务执行；因后端配置/LLM 问题执行失败并显示“任务执行遇到问题”，但 UI 提交流程本身正常 |

**发现的 UI/UX 问题**：

| 编号 | 问题 | 严重程度 | 说明/建议 |
|------|------|----------|-----------|
| UI-01 | 界面大量使用 emoji | P1 | 首页可见文本中检测到 69 处 emoji；与“优先使用莫兰迪色系/PNG/SVG 图标”的 UX 偏好冲突；建议逐步替换为图标组件或色块 |
| UI-02 | `st.radio` 空 label 触发可访问性警告 | P2 | 已修复为 `label="Navigation"` + `label_visibility="collapsed"` |
| UI-03 | 启动时出现 `transformers` 库 `__path__` 警告 | P2 | 某依赖链间接引入 transformers，拖慢冷启动；建议排查并延迟/条件导入 |
| UI-04 | 浏览器视图宽度偏窄 | P2 | 当前验证窗口约 632px；建议在 ≥1024px 视口下重新验证响应式布局 |
| UI-05 | 聊天任务执行报错 | P2 | 输入提交后后端返回错误；本地开发环境需配置 LLM/API 才能完整验证端到端 |

**UI/UX 结论**: 核心导航、页面切换、表单输入均已验证可用；**尚未达到“真实用户逐按钮验证功能”的完全覆盖**，主要阻塞点为 emoji 替换和宽屏布局验证。

---

## 四、文档同步

| 文档 | 检查项 | 状态 |
|------|--------|------|
| README.md | 版本号、测试数、架构描述 | ✅ 已同步 |
| README-EN.md | 版本号、测试数、架构描述 | ✅ 已同步 |
| README-JP.md | 版本号、测试数、架构描述 | ✅ 已同步 |
| CHANGELOG.md | 版本条目、测试数 | ✅ 已同步 |
| docs/API.md | v0.3.0 架构章节、版本号 | ✅ 已更新 |
| QUICK_START.md | 并行投票架构流程 | ✅ 已重写 |
| docs/internal/V030_ROADMAP.md | 标题、测试数、状态 | ✅ 已更新 |
| docs/internal/REMEDIATION_PLAN_20260625.md | P0-P1 状态、验证结果 | ✅ 已更新 |
| docs/internal/TECH_DEBT_20260625.md | P1/P2/P3 延后项 | ✅ 已新建 |

---

## 五、Git 状态

**当前分支**: 未指定功能分支（工作区在 main 上直接修改）  
**未提交更改**: 25 个已修改文件 + 2 个新增文件（REMEDIATION_PLAN_20260625.md、TECH_DEBT_20260625.md）

**已修改文件清单**：
- CHANGELOG.md, QUICK_START.md, README-EN.md, README-JP.md, README.md
- docs/API.md, docs/internal/V030_ROADMAP.md
- frontend/app.py
- opc_manager/async_executor.py, opc_manager/audit_log.py, opc_manager/constants.py, opc_manager/data_manager.py, opc_manager/onboarding.py, opc_manager/task_orchestrator.py
- tests/conftest.py, tests/test_async_executor.py, tests/test_async_frontend_integration.py, tests/test_audit_log.py, tests/test_data_manager.py, tests/test_e2e_user_journeys.py, tests/test_integration_e2e.py, tests/test_integration_modules.py, tests/test_no_circular_import.py, tests/test_onboarding.py, tests/test_parallel_sages.py, tests/test_start_script.py, tests/test_ui_e2e_apptest.py, tests/test_user_journey.py

**新增文件**：
- docs/internal/REMEDIATION_PLAN_20260625.md
- docs/internal/TECH_DEBT_20260625.md

---

## 六、发布决策

| 维度 | 评估 | 说明 |
|------|------|------|
| 功能完整性 | ✅ 满足 v0.3.0-beta 目标 | P0/P1 阻塞项全部修复 |
| 测试质量 | ✅ 通过 | 3223 passed，覆盖率 62.87% |
| 安全扫描 | ✅ 通过 | bandit 无 High/Medium |
| 文档同步 | ✅ 通过 | 关键文档已更新 |
| UI/UX | ⚠️ 部分满足 | 核心流程可用，但 emoji 替换和宽屏验证未完成 |
| Git 流程 | ❌ 未满足 | 修改直接在 main 工作区，未通过 PR → Review → Merge |

**发布建议**: 
- **暂不建议直接发布到 v0.3.0**。
- 必须先完成：1) 将当前变更整理为 PR 并按 Git 工作流合并；2) 处理 UI-01 emoji 替换（P1）；3) 在 ≥1024px 视口下补充响应式布局验证。
- 完成后可重新评估为 RC 状态。

---

## 七、PR 建议

**建议分支名**: `feat/v0.3.0-beta-remediation` 或 `release/v0.3.0-beta`  
**建议 PR 标题**: `fix(v0.3.0-beta): 修复 P0/P1 阻塞项、同步文档、优化 UI 可访问性`  
**建议 PR 描述要点**：
1. 修复 AuditLog 后台 writer 与 SQLite 写锁竞争（P0-1）
2. 修复 `_serial_consensus_fallback` Decision 构造参数（P1-1）
3. 将 `finance` 纳入关键决策技能集合（P1-2）
4. 更新 API/QUICK_START/CHANGELOG/README 文档版本与架构描述（P1-3/P1-4/P1-5）
5. 修复 `frontend/app.py` atexit 访问 `st.session_state` 的测试收尾问题
6. 修复 Streamlit `st.radio` 可访问性警告
7. 全量测试 3223 passed / 117 skipped / 1 xpassed / 2 warnings

**Review 重点**：
- `opc_manager/task_orchestrator.py` 的 `_serial_consensus_fallback` fail-close 语义
- `opc_manager/constants.py` 的 `CRITICAL_DECISION_SKILLS` 变更影响
- `opc_manager/data_manager.py` 的 SQLite busy_timeout 与 WAL 配置
- `tests/conftest.py` 的全局 singleton 清理 fixture
- `frontend/app.py` 的 atexit 闭包捕获修改
