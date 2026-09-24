# OPC-Agents v1.0.0 推进计划（执行基线）

> **状态**: Approved — DevSquad 五角色共识通过
> **日期**: 2026-09-21 | **版本**: v1.0.0
> **主项目铁律**: 当前主项目 = OPC-Agents；PromiseLink/DevSquad 仅为依赖或协作仓库，不主动修改（2026-09-21 用户确认）
> **上游文档**: [PRD_V5](PRD_V5.md) · [TDD_V1.0.0](../architecture/TDD_V1.0.0.md) · [TEST_PLAN_V1.0.0](../test/TEST_PLAN_V1.0.0.md) · [SECURITY_REVIEW_V1.0.0](../security/SECURITY_REVIEW_V1.0.0.md) · [DEPLOYMENT_V1.0.0](../operations/DEPLOYMENT_V1.0.0.md) · [SKILL_FREEZE_LIST_V1.0.0](../spec/SKILL_FREEZE_LIST_V1.0.0.md) · [PROMISELINK_API_CALIBRATION](../research/PROMISELINK_API_CALIBRATION.md)

---

## 1. 目标

完成 OPC-Agents v1.0.0 的全部交付项：CRM 解冻、PromiseLink 集成客户端、Scheduler 主动执行引擎、UI 更新，通过全部门禁后发版。

## 2. 现状事实（2026-09-21 核查）

| 项 | 事实 |
|---|---|
| 代码基座 | v0.5.9 已有代码：`opc_manager/`（数十模块）+ `frontend/app.py` + 144 个测试文件 |
| 规划文档 | 9 份全链完成（PRD/TDD/TEST/SEC/DEP/POS/FREEZE/US48-59/CALIBRATION），**已提交推送** |
| v1.0.0 新模块 | promiselink_client / scheduler / CRM 解冻：**未启动** |
| 外部依赖 | ENH-PL-01~10 已送 PromiseLink 团队，未回；仅阻塞双向承诺分析等少数功能 |
| 协作基座 | DevSquad PR #9 已合并（09-14），无遗留 open 项 |
| 周榜借鉴 | 仅采纳信号 4（Skill 输出结构化+可校验，已写入 SKILL_FREEZE_LIST §九）；信号 5 入 P2 backlog |

## 3. 批次计划

### 批次 0 — 文档留痕闭环（已完成 2026-09-21）
| 项 | 内容 | 校验方法 |
|---|---|---|
| 0.1 | 信号 4 增补 SKILL_FREEZE_LIST §九 | 文档含"结构化+可校验"约束条目 |
| 0.2 | 提交推送 9 份文档 + USER_STORIES | `git status` 干净，CI 绿 |

### 批次 1 前置 — B0 基线修复（进行中 2026-09-21）

> 事实基线（2026-09-21 全量）：4526 passed / 284 failed；失败全部为
> `RuntimeError: asyncio.run()/Runner.run() cannot be called from a running event loop`
> （存量跨测试事件循环污染，与批次 1 新代码无关）。分支 `feature/v1.0.0-batch1` 已创建（基于 main fc4b999）。

| 项 | 内容 | 验收标准 | 校验方法 |
|---|---|---|---|
| B0.1 | **根因已定位并修复（2026-09-23）**：Playwright Sync API 的事件循环以 greenlet 运行在**主线程内**（实测 `loop._thread_id == 主线程 ident`），而 asyncio 的 running-loop 标记存放在 `threading.local`、被同一 OS 线程的所有 greenlet 共享 → `session` 级 `playwright_browser` 一旦进入 `sync_playwright()`，主线程在**整个 session** 内始终被视为"正在 loop 中"，其后任何主线程 `asyncio.run()` 均抛 `RuntimeError: cannot be called from a running event loop`。修复：`tests/e2e/conftest.py` 的 `playwright_browser` 由 session 级收敛为 **module 级**（上下文随模块结束关闭、标记复位） | 全量 pytest **0 failed** | `pytest tests/ -q` 全绿 |
| B0.2 | ~~MPLCONFIGDIR~~ **诊断修正（2026-09-21 复现核实）**：`.uuid` 写入系统字体目录由 e2e Playwright 启动的 Chromium 经 CoreText 枚举字体触发（venv 未安装 matplotlib，原假设证伪）；写入被沙箱拦截但无害——报错出现在 pytest 汇总之后，0 用例因此失败 | e2e 浏览器组本地跑需在沙箱外执行；用例结果不受影响 | e2e 浏览器组沙箱外重跑：无 TRAE Sandbox Error 且结果与沙箱内一致 |

> **B0.1 二分证据链（留痕）**：
> 1. 全量 4526P/284F；`tool_system` 单跑 71 全绿 → 面在 tests/e2e
> 2. 非浏览器 e2e 9 文件（api_server/docker_deployment/docker_run/e2e_real/integration/memory_bridge/p0_skills/start_script/ui_e2e_apptest）+ tool_system = **275P/4S，无泄漏**
> 3. 浏览器组 A 半（a11y_all_themes/a11y_axe/chat_error_recovery/chat_real_mode/injection）+ tool_system = **24F/121P**；B 半（responsive/settings/theme_dark/ui_playwright/visual_regression）+ tool_system = **24F/119P**。两半失败**全部**位于 `tests/unit/test_tool_system.py`，错误均为 `asyncio.run() cannot be called from a running event loop`
> 4. 临时探针插件（用后即删）在 setup/teardown 记录：浏览器模块内每个用例均为 `SETUP-INSIDE`/`TEARDOWN-INSIDE`（主线程处于 running loop），teardown 金丝雀首个变红用例 = 各组**第一个**浏览器用例，模块外无任何记录
> 5. 决定性验证：`with sync_playwright():` 内 `asyncio._get_running_loop()` 非空且 `loop._thread_id == threading.get_ident()`（**主线程**）；退出上下文后恢复 `None`
> 6. 修复后复验：`test_theme_dark` + tool_system = **74 passed**，探针零记录
> 7. **全量复验（2026-09-24）**：`4871 passed, 2 failed`（26:39），`asyncio.run() cannot be called from a running event loop` 出现次数 **0**（修复前 284 failed）→ 泄漏类失败清零
> 8. 剩余 2 个失败已归因：
>    - `tests/test_scheduler.py::TestPersistenceAcrossRestart::test_due_tasks_requires_enabled_and_next_run` —— **T6 新代码引入的定时炸弹测试（真缺陷，已修）**：用例把 `NOW` 硬编码为 `2026-09-21`，而 `enable_task` 用真实当前时间计算首次 `next_run_at`；2026-09-21 编写时通过，日期推进到 2026-09-24 后参照点 `2026-09-22 12:00` 早于真实算出的 `2026-09-25 08:00`，`due_tasks` 返回 0。源码行为正确（首次排期基于真实当前时间），缺陷在测试非确定性。修法：参照点改为 `datetime.now() + timedelta(days=365)`，保留"enabled=0 排除 / enabled=1 且 next_run 非空纳入"两条断言语义 → **33 passed**
>    - `tests/e2e/test_e2e_real.py::TestRealSearch::test_japanese_search_returns_results` —— **外部网络抖动，非代码缺陷（未改动）**：DuckDuckGo 真实搜索，隔离跑 3 次结果 2 通过/1 失败（15.9s / 91s / 82s），同一 query 结果不一致 → 判定为外部服务抖动。该用例属于 `pytest tests/e2e/` 阻塞门禁范围，存在随机阻塞 CI 的风险，待决策是否加固
> 9. 附带确认：CI 早已用 `--ignore=tests/e2e` + 单独跑 e2e 的方式**绕过**本泄漏（`python-ci.yml:76`、`release.yml:36` 注释明确写明"避免 Playwright sync_playwright 创建的独立事件循环线程污染后续单元测试"）。本次修复消除了根因，该 workaround 不再是必需（保留亦可，属冗余保险）

### 批次 1 — 无外部依赖开发（三项独立，client 最优先）
前置动作：B0.1/B0.2 完成（全量 0 failed）；已创建 `feature/v1.0.0-batch1` 分支。

| 项 | 内容 | 验收标准 | 校验方法 |
|---|---|---|---|
| 1.1 | `opc_manager/promiselink_client.py`：TDD §3 的 17 条已确认路由 + 六态失败状态（DISABLED/UNCONFIGURED/AVAILABLE/DEGRADED/CIRCUIT_OPEN/SCHEMA_MISMATCH）+ 指数退避/429 处理 + trace_id | 单测全绿；认证失败 fail-closed；日志无 token | `pytest tests/test_promiselink_client.py -v` |
| 1.2 | `opc_manager/scheduler.py`：cron 触发 + 本地持久化 + 关键决策点保护；`PROMISELINK_ENABLED=false` 默认 | 单测全绿；重启后任务不丢 | `pytest tests/test_scheduler.py -v` |
| 1.3 | CRM 解冻：按 SKILL_FREEZE_LIST §5 清单（移除 FROZEN 标记、解锁 10 方法、lifecycle_tracker、DormantScanner 集成） | 覆盖率 ≥80%；`tests/e2e/test_crm_e2e.py` 40 测试通过；集成可开关，关闭时本地 CRM 完整可用 | `pytest --cov=opc_manager.crm_skill` + E2E |
| 1.4 | 批次回归：全量测试 + CI 门禁不回退（现有 11 项） | 0 regression | 全量 pytest + CI 绿后合并 main |

### 批次 2 — 事件驱动（ENH-PL 反馈到达后）
反馈 → 共识决策（改 TDD 或不改）→ **先更文档再动码** → 实现被阻塞功能（ENH-PL-01 双向承诺分析等）。

### 批次 3 — 集成验证与发布门禁
UI（技能市场 6 技能、CRM 标签页、关系推进卡、Onboarding）→ 真实 PromiseLink 实例 smoke → Streamlit+Playwright 模拟真实用户 E2E（发布硬门禁）→ 对照 SECURITY_REVIEW / DEPLOYMENT 收尾 → 发版。

### 改进项 — 炼刀对标（2026-09-21 用户共识：全部纳入 v1.0.0）

> 对标结论：学"窄场景打穿 / 接管既有工作流 / 稳定即卖点"，不学模拟真人 RPA 与灰区话术。

| 项 | 内容 | 批次映射 | 验收标准 | 校验方法 |
|---|---|---|---|---|
| IMP-1 | 岗位 E2E 链路：早报 → 沉默客户 → 催促草稿，模拟真实用户完整走完一个运营岗的工作闭环 | 批次 3 | Streamlit+Playwright 真实浏览器走完三段链路，不依赖硬编码 mock | `tests/e2e/` 岗位链路用例 + Playwright 证据截图 |
| IMP-2 | PromiseLink 六态状态卡：DISABLED/UNCONFIGURED/AVAILABLE/DEGRADED/CIRCUIT_OPEN/SCHEMA_MISMATCH 在 UI 可视化，降级原因用户可见 | 批次 3 UI | 状态卡渲染六态 + 每态用户可见原因说明 | UI 单测 + E2E 断言状态卡文案 |
| IMP-3 | 早报邮件交付：morning-brief 经 email 技能送出，受三贤者/关键决策点保护 | 批次 3 | 用户可订阅早报邮件；发送前必经关键决策点；fail-close | scheduler/email 集成测试 + 决策点否决用例 |
| IMP-4 | README 价值锚点："对标一个运营岗"定位上首屏 | 立即（T8） | README 首屏出现岗位对标描述，与 v1.0.0 能力一致 | 人工复核 |

## 4. 明确不做（防插队）
- DevSquad backlog（16 大文件拆分、bandit MEDIUM、Prometheus exporter）→ v1.0.0 后
- 周榜信号 2（安全垂直开源）/ 信号 5（跨模型路由，P2 backlog）→ 不进 v1.0.0
- task_manager 解冻 → v1.1.0 评估

## 5. 角色共识记录（DevSquad，2026-09-21）

| 角色 | 结论 | 关键输入 |
|---|---|---|
| PM | ✅ 同意 | 每批次带验收标准对齐 US48-59；文档先行闭环为前置 |
| Architect | ✅ 同意 | client 六态契约按 TDD §3.4 严格执行；不复制 PromiseLink 代码；DTO 最小映射 |
| Tester | ✅ 同意 | 动工前回归基线锁定；真实组件优先于 Mock；E2E 为发布硬门禁 |
| Security | ✅ 同意 | fail-closed + 日志禁泄 token + Fernet 按 SECURITY_REVIEW 前置于批次 1 |
| DevOps | ✅ 同意 | 批次 0 文档直推 main；批次 1 走 feature 分支，CI 绿后合并 |

**共识结论**：全体通过，无阻塞异议。批次 0 立即执行，批次 1 按依赖顺序推进。

## 6. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09-21 | 初版；DevSquad 五角色共识通过；批次 0 完成闭环 |
| 2026-09-21 | 增补 B0 基线修复（B0.1 事件循环泄漏 / B0.2 matplotlib 沙箱）；纳入炼刀对标四改进项 IMP-1~4 及批次映射 |
| 2026-09-23 | B0.1 根因定位并修复：Playwright Sync API 的 greenlet 事件循环占用主线程 running-loop 标记 → `playwright_browser` 由 session 级收敛为 module 级；补二分证据链；临时探针插件用后即删不入库 |

---

*维护者: DevSquad 协作产出，PM 归档*
