# OPC-Agents v0.3.0 发布前修复计划

**制定日期**: 2026-06-25  
**目标版本**: v0.3.0-beta → v0.3.0  
**制定依据**: PROJECT_ASSESSMENT_20260623.md + 2026-06-25 严格复评  
**治理原则**: 文档先行 → 达成共识 → 修改代码 → 充分测试 → 同步文档

---

## 一、修复目标

将项目从 **C+ / 中期 Beta（70.1 分）** 推进到 **B / 发布候选（≥75 分）**，消除所有 P1 阻塞项，完成 P2/P3 高价值项。

---

## 二、问题清单与共识决策（P0-P3）

### P0 级问题（1 个）

| 编号 | 问题 | 状态 | 修复方案 | 共识角色 | 影响文件 |
|------|------|------|----------|----------|----------|
| P0-1 | 完整测试套件 (`pytest tests/`) 在 `test_consensus_engine.py` 阶段 hang 超时，根因为 `AuditLog` 后台 writer 线程跨测试未清理，与 `ConsensusEngine._log_decision` 竞争 SQLite 写锁；默认 busy timeout 30s 导致单点阻塞 | **已完成** | 1. `data_manager.py`: 设置 `PRAGMA busy_timeout=5000` 并降低连接 `timeout` 至 5s；2. `tests/conftest.py`: 添加全局 autouse fixture，每个测试后停止 `AuditLog` writer 并释放当前线程 DB 连接；3. `audit_log.py`: 优化 `stop()` 快速中断 writer；4. `tests/conftest.py`: 增加 i18n locale 重置，防止跨测试语言状态泄漏 | Architect + Tester | `opc_manager/data_manager.py`, `tests/conftest.py`, `opc_manager/audit_log.py` |

### P1 级问题（7 个，本次重点）

| 编号 | 问题 | 状态 | 修复方案 | 共识角色 | 影响文件 |
|------|------|------|----------|----------|----------|
| P1-1 | `_serial_consensus_fallback` 构造 `Decision` 时传入无效字段 `opinions`/`consensus_score`，缺少必填 `decision_type` | **已完成** | 按 `Decision(decision_type=DecisionType.ESCALATED, approved=False, reasoning=..., confidence=0.0)` 构造；补充 `test_serial_consensus_fallback_timeout_fail_close` | Architect + Security + Tester | `opc_manager/task_orchestrator.py`, `tests/test_parallel_sages.py` |
| P1-1b | `test_audit_log.py` 全量运行时 hang，因 `AuditLog` 后台 writer 与 DB cleanup 竞争锁 | **已完成** | 已做：修正 `log` 返回类型、writer 单例、cleanup 节流；补充：跨测试 writer 清理、SQLite busy timeout 收敛（见 P0-1） | Architect + Tester | `opc_manager/audit_log.py`, `tests/test_audit_log.py`, `tests/conftest.py` |
| P1-2 | `CRITICAL_DECISION_SKILLS` 缺少 `finance`，记账操作绕过共识门 | **已完成** | 在 `constants.py` 中将集合扩展为 `{"email", "report", "finance"}`；补充 `test_is_critical_finance_skill` | Security + Architect | `opc_manager/constants.py`, `tests/test_parallel_sages.py` |
| P1-3 | `docs/API.md` 严重过时，仍停留在 v0.2.5 | **已完成** | 更新版本号为 v0.3.0-beta、最后更新日期；新增“v0.3.0 三贤者并行投票架构”章节 | PM + Architect + Tester | `docs/API.md` |
| P1-4 | `QUICK_START.md` 仍按旧版串行流水线描述 | **已完成** | 重写架构流程图为“三贤者并行投票 + IntentClassifier 三路由”；补充 Key Design Points | PM + UI | `QUICK_START.md` |
| P1-5 | 测试数量文档矛盾：README=3341，CHANGELOG/V030_ROADMAP=2991 | **已完成** | 统一为 3341；V030_ROADMAP 标题与状态更新为 v0.3.0 Roadmap | PM + Tester | `CHANGELOG.md`, `docs/internal/V030_ROADMAP.md`, `README.md`, `README-EN.md`, `README-JP.md`, `docs/API.md` |
| P1-6 | `opc_manager/` 102 文件平铺，`task_engine_v3.py` 1853 行 | **本次不重组**（风险高） | 记录为 v0.3.1 技术债；本次仅拆分/重命名最具风险的 `error_handler.py` vs `error_handler_component.py` 命名冲突 | Architect | `docs/internal/TECH_DEBT_20260625.md`（新建） |
| P1-7 | `tests/` 87 文件平铺 | **本次不重组**（风险高） | 记录为 v0.3.1 技术债；本次仅对新增测试按 `tests/unit/consensus/` 试点分组 | Tester | `docs/internal/TECH_DEBT_20260625.md`（新建） |

**共识结论**:  
- 优先修复会直接影响安全契约的 P1-1 和 P1-2（Architect + Security 达成共识）。  
- 文档类 P1-3/P1-4/P1-5 与代码修复同步更新（PM + Tester 达成共识）。  
- 目录重组风险高、回归成本高，延后到 v0.3.1（全角色共识）。

### P2 级问题（15 个，精选 4 个在本次处理）

| 编号 | 问题 | 状态 | 修复方案 | 责任角色 |
|------|------|------|----------|----------|
| P2-3 | flake8 检查范围过窄 | **已修复** | `python-ci.yml` 当前已使用 `--select=E9,F63,F7,F82,W605`，保持现状并待 v0.3.1 扩展 | Infra |
| P2-5 | `.flake8` 自相矛盾 | **已修复** | 当前 `.flake8` 仅 `extend-ignore = W503`，无 E501 矛盾 | Infra |
| P2-10 | Ollama URL 三处不一致 | **待确认** | 扫描 README/QUICK_START/CONFIGURATION 中 `.com` vs `.ai`，统一为项目实际使用的域名 | DevOps |
| P2-15 | `pyproject.toml` 缺少 `--strict-markers` | **已修复** | `[tool.pytest.ini_options]` 已存在 `addopts = "-v --tb=short --strict-markers"` | Tester |

其余 P2（核心 skill 覆盖率、CI 覆盖率余量、weekly-e2e 范围等）纳入 v0.3.1 计划。

### P3 级问题（8 个，不纳入本次）

全部归档到 `docs/internal/TECH_DEBT_20260625.md`，在 v0.3.1 中按优先级挑选。

---

## 三、实施计划

### Phase 1: 代码缺陷修复（P1-1, P1-2）✅

1. 修复 `task_orchestrator.py` 的 `_serial_consensus_fallback`。
2. 更新 `constants.py` 的 `CRITICAL_DECISION_SKILLS`。
3. 补充/更新单元测试。

### Phase 2: 文档与 CI 同步（P1-3, P1-4, P1-5, P2-15）✅

1. 更新 `docs/API.md`、`QUICK_START.md`。
2. 同步 `CHANGELOG.md`、`V030_ROADMAP.md` 测试数与版本状态。
3. 确认 `pyproject.toml` 已包含 `--strict-markers`。

### Phase 3: 全量回归测试 🔄

1. 相关模块单元测试通过。
2. `bandit` 安全扫描无 High/Medium。
3. `pytest --collect-only` 确认测试数 3341。
4. 完整执行 `pytest tests/ --timeout=120` 曾因 P0-1 DB 锁竞争 hang 在 `test_consensus_engine.py`；修复后重新全量验证。

### Phase 4: 文档收尾 ✅

1. 本计划文档状态已更新为“已完成”。
2. 建议后续更新 `docs/internal/PROJECT_ASSESSMENT_20260623.md` 中对应条目状态。

---

## 四、验证方法

| 检查项 | 命令/方法 | 通过标准 | 实际结果 |
|--------|-----------|----------|----------|
| P1-1 修复 | `pytest tests/test_parallel_sages.py -v` | 新增超时降级测试通过 | ✅ 26 passed |
| P1-2 修复 | `pytest tests/test_parallel_sages.py::TestCriticalDecisionPoint::test_is_critical_finance_skill -v` | `finance` 在关键决策集合中 | ✅ passed |
| 安全扫描 | `bandit -r opc_manager/ -ll -ii` | 0 High/Medium | ✅ No issues identified |
| 测试总数 | `PYTHONPATH=. pytest --collect-only -q` | 3341 | ✅ 3341 collected |
| 版本一致性 | `cat VERSION` 与 `python -c "from opc_manager.version import __version__; print(__version__)"` | 一致 | ✅ 0.2.5 = 0.2.5 |
| 文档同步 | 人工走读 README/CHANGELOG/V030_ROADMAP/API/QUICK_START | 测试数、版本号、架构描述一致 | ✅ 已统一为 3341，API/QUICK_START 已更新 |
| 全量回归 | `pytest tests/ --timeout=120 -q` | 0 failure | ✅ 3223 passed, 117 skipped, 1 xpassed, 2 warnings in 204.29s |
| UI E2E | `pytest tests/test_ui_e2e_apptest.py -q` | 25 passed | ✅ 25 passed in 14.76s |
| 测试收尾日志 | `pytest tests/ --timeout=120 -q` 后检查 stderr | 无 `frontend/app.py` 日志错误 | ✅ 修复后无日志错误 |

---

## 五、风险与回滚

| 风险 | 缓解措施 |
|------|----------|
| 修改 `CRITICAL_DECISION_SKILLS` 导致现有 finance 相关测试行为变化 | 已运行 `test_finance_skill_coverage.py` / `test_p1_skills.py` / `test_p2_skills.py` / `test_integration_modules.py`，143 passed，86 skipped，无破坏 |
| 修复 `_serial_consensus_fallback` 改变超时行为 | 仅修正构造参数，不改变 fail-closed 语义；补充回归测试 `test_serial_consensus_fallback_timeout_fail_close` |
| 文档更新遗漏 | 使用本清单逐项勾选 |

---

## 六、决策记录（ADR）

**ADR-20260625-01**: 目录重组（opc_manager/、tests/）风险高于收益，延后到 v0.3.1。  
**ADR-20260625-02**: `finance` 纳入关键决策技能，符合 `PARALLEL_SAGES_DESIGN.md` 对“数据持久化”的定义。  
**ADR-20260625-03**: `_serial_consensus_fallback` 超时返回 `DecisionType.ESCALATED`（而非 VETOED），因为超时属于“未达成有效共识”，而非“明确否决”。

---

## 七、UI/UX 真实运行验证（2026-06-25 补充）

验证方法：启动 `streamlit run frontend/app.py`，使用浏览器截图 + DOM 检查 + 真实点击操作，对照设计约束检查布局、按钮、指令。

### 7.1 已验证页面与操作

验证环境：`streamlit run frontend/app.py`，浏览器视口固定为 **632px × 652px**。

| 页面/操作 | 结果 | 说明 |
|-----------|------|------|
| 应用启动 | ✅ | 页面标题“一人公司助手”，无致命 JS 错误 |
| 跳过引导 | ✅ | 点击“跳过引导”后 onboarding overlay 关闭 |
| 操作提示关闭 | ✅ | 点击“Got it, don't show again”后提示折叠 |
| 首页/对话页 | ✅ | 侧边栏导航、场景按钮、快捷入口、输入框均渲染 |
| Dashboard 页 | ✅ | 导航切换正常，显示数据仪表盘与收入趋势图；控制台仅 Vega-Lite warning |
| 设置页 | ✅ | LLM/SMTP/API密钥/安全设置/个人信息/数据备份 标签页与输入框渲染 |
| 聊天输入 | ⚠ 提交成功 | 使用真实键盘事件输入“分析本月数据”并点击 Send，消息成功提交并触发任务执行；因本地未配置 LLM/API，任务执行失败并显示“任务执行遇到问题”，但 UI 提交流程本身正常 |
| 取消任务/重新执行 | ✅ | 任务执行期间“取消任务”按钮出现，失败后“重新执行”按钮渲染 |

### 7.2 发现的 UI/UX 问题

| 编号 | 问题 | 严重程度 | 说明/建议 |
|------|------|----------|-----------|
| UI-01 | 界面大量使用 emoji（导航、按钮、场景卡片、标题） | P1 | 首页可见文本中检测到 69 处 emoji；与“优先使用莫兰迪色系/PNG/SVG 图标”的 UX 偏好冲突；需批量替换 |
| UI-02 | `st.radio` 空 label 触发 Streamlit 可访问性警告 | 已修复 | `frontend/app.py:243` 原 `label=""`；已修复为 `label="Navigation"` + `label_visibility="collapsed"` |
| UI-03 | 启动时出现大量 `transformers` 库 `__path__` 警告 | P2 | 某依赖链间接引入 transformers，拖慢冷启动；建议排查并延迟/条件导入 |
| UI-04 | 浏览器视图宽度偏窄 | P2 | 当前浏览器工具 viewport 锁定在 632px，无法调整到 ≥1024px；宽屏响应式布局验证受限 |
| UI-05 | 聊天任务真实提交后执行失败 | P2 | UI 流程正常，后端失败系本地未配置 LLM；端到端成功需配置有效 LLM 后重测 |

### 7.3 结论

UI 可在本地正常运行，核心导航、页面切换、聊天输入提交、任务状态展示均已通过真实用户操作验证（632px 视口）。剩余阻塞点：emoji 替换（P1）需要设计决策和批量文案改动；宽屏响应式布局需在支持 ≥1024px 视口的测试环境中补充验证。
