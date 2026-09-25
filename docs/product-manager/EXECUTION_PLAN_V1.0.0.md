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

### 批次 1 追加项 W — web_search 静默降级可观测化（2026-09-24 用户决策）

> **触发**：B0.1 全量回归剩 2 failed，其一为 `test_e2e_real.py::TestRealSearch::test_japanese_search_returns_results`。
> **深挖结论（证据）**：① 直接调用 `ddgs.DDGS().text()` 对同一日语 query 连跑 5 次 **5/5 成功**（16/20/20/10.5/25s），失败与语言无关；② 复现测试的连续 5 查询序列，失败出现在**第 2 条英文 query**（`TimeoutException: ConnectTimeout`），即 DDGS 聚合器**间歇性连接超时**（样本约 1/5），随机命中任一查询；③ `WebSearchMCP.search()` 捕获全部异常后**静默返回 `[]`**，且该契约被单测 `test_search_exception_returns_empty` 锁定；④ 生产调用方 `skill_executors._do_web_search` 再吞一层，同样返回 `[]`，全链路**无重试**。
> **真实用户影响**：一次瞬时超时 → 成果物**零来源**且用户无任何提示、无法诊断（不是"没搜到"，是"搜挂了"）。
> **测试侧缺陷**：断言消息 `"Japanese search should return results"` 把网络超时**误报为语言问题**。

| 项 | 内容 | 验收标准 | 校验方法 |
|---|---|---|---|
| W-1 | `opc_manager/web_search.py`：对**瞬时网络异常**做**有界重试**（有限次数 + 短退避），并把"重试后仍失败"变成**可观测信号**（调用方可区分"零来源"与"搜索失败"），同时保持最终仍返回 `[]` 的既有契约以兼容既有生产调用方 | 单测全绿；重试次数有上界；失败可被调用方区分；既有 `test_search_exception_returns_empty` 契约不被破坏 | `pytest tests/unit/test_web_search_coverage.py -v` + 新增重试/可观测单测 |
| W-2 | 修正 `tests/e2e/test_e2e_real.py` 误导性断言消息（网络失败不再表述为语言问题） | 断言消息如实描述失败原因 | 人工复核 + e2e 复跑 |
| W-3 | 同步生产调用方：`skill_executors._execute_search` 输出新增 `search_failed` 字段、`_do_web_search` 失败留告警；`task_engine_v3_search._search()` 失败时**不写缓存**（避免一次抖动被冻结成 5 分钟"零结果"）并记录原因 | 调用方能区分"零结果/搜索失败"；失败结果不进缓存；既有 `Tuple[List, List]` 与 `fallback_used` 契约不变 | 新增调用方单测（`test_skill_executors.py` / `test_task_engine_v3.py`） |

> **据实校正**：原始表述为"3 个生产调用方"。实测探查后确认真实调用方只有 **2 个**——`skill_executors` 与 `task_engine_v3_search`；`tool_system._execute_web_search` 是**纯占位实现**（返回 `example.com` 假结果、根本不构造 `WebSearchMCP`），不构成调用方，故不改。

#### W 系列实施证据（2026-09-24，实际命令输出）

| 校验 | 命令 | 结果 |
|---|---|---|
| W-1/W-2 单测 | `pytest tests/unit/test_web_search_coverage.py -q` | `23 passed in 0.70s`（含新增重试上界/瞬时判定/last_status 11 项） |
| W-3 调用方单测 | `pytest tests/integration/test_task_engine_v3.py::TestSearchFailureNotCached tests/integration/test_skill_executors.py -q` | `104 passed in 0.82s` |
| W-2 e2e 稳定性 | `pytest tests/e2e/test_e2e_real.py::TestRealSearch -q`（连续 2 次） | 两次均 `5 passed`（84.98s / 104.46s）→ 有界重试消除了间歇超时抖动 |
| 门禁 mypy（CI 同参） | `mypy opc_manager/ --ignore-missing-imports --follow-imports=silent` | `Success: no issues found in 130 source files` |
| 门禁 black（CI 同参） | `black --check --target-version py310 <11 个改动文件>` | `11 files would be left unchanged` |
| 门禁 radon D+ | `radon cc opc_manager/ -s -n D` | 空输出 = PASS |
| W5 全量回归 | `pytest -q`（全量 4894 项） | `4894 passed, 8 warnings in 1649.15s (0:27:29)`，`EXIT=0` |

> **门禁可信度附带发现（2026-09-24）**：本批次提交在 push 后**从未触发 CI**（`gh run list` 无 `feature/v1.0.0-batch1` 记录，主 CI 只在 main/PR 上跑），因此"已 push"不等于"已过门禁"。核验本地四门禁时发现两类**先于本分支存在**的红：
> ① `black --check` 在 main 上即为红（`gh run view 35564847359` → 3 个 job 的 `Check formatting with Black` 全部 failure，可溯源至 `f9f4c50`）；
> ② `Verify README consistency` 同为既有红（同一 run 三处 failure，日志为 `测试数 4814 未找到`，而三语 README 实际写的是 `4744`）。
> ③ `mypy` 检出本批次自身引入的 3 个错误（`scheduler.py` 重复定义 `_iso`/`_from_iso`、`promiselink_client.py` union-attr），已当场修复，不再遗留。

#### 既有红修复（2026-09-24，用户指令"修好了再继续推进"）

**根因**：`f9f4c50`（main 上增补 E2E 测试）之后，测试数与文件数已变，但三语 README 未同步；同时该提交的 2 个 e2e 文件未过 black。两者在 main 上持续为红，与 v1.0.0 批次无关，但会掩盖本分支自身的门禁问题。

| # | 门禁 | 性质 | 修复动作 | 校验证据 |
|---|---|---|---|---|
| ① | black | 既有红（2 文件，非本批次） | `black --target-version py310` 格式化 `test_memory_bridge_e2e.py` / `test_parallel_sages_e2e.py` | `327 files would be left unchanged`（全仓） |
| ② | README 一致性 | 既有红（三语） | 三语 README 测试数 `4744`→`4894`（含 JP 文件数 `100`→`137`）；用 CI 原样 heredoc 脚本复跑 | `✓ 三语 README 一致性校验通过（版本 0.5.9, 模块 99, 测试 4894）` |
| ③ | ruff | 本批次自身引入（blocking） | `promiselink_client.py` 删未用 `List`（F401）、删死代码 `url`（F841，实际请求走 `httpx.Client(base_url=...)` + 相对路径，等价）；测试文件删未用 `ClientResult` | `All checks passed!` / `ruff_exit=0` |
| ④ | mypy | 本批次自身引入 | 见上 ③ | `Success: no issues found in 130 source files` |
| ⑤ | bandit（`-r opc_manager/ -ll -ii`） | 本批次自身引入（3 处 B608 Medium/Medium） | `scheduler.py`：`get_task`/`due_tasks` 插值为内部类常量 `_SELECT_COLUMNS`、值走 `?` 绑定 → 真误报，按 repo 既有约定加 `# nosec B608 — <理由>`；`_update_fields` 插值的是**调用方列名** → 真实薄弱点，**补 `_UPDATABLE_COLUMNS` 白名单 + 校验**（不写"声称有白名单但实际没有"的注释），并新增拒绝/放行两条单测 | `bandit_exit=0`；Medium 由 6 降至 3（余下 3 条未达 `-ll -ii` 阈值） |
| ⑥ | 版本一致性 | — | 无改动，复跑确认 | `VERSION=0.5.9 py=0.5.9 mcp=0.5.9` → OK |
| ⑦ | radon D+ | — | 无新增 | 空输出 = PASS |

> **教训（与 project_memory 门禁可信度条目呼应）**：CI 只在 main/PR 触发，feature 分支 push 不触发 → "已 push"被误当"已过门禁"，导致 ruff/mypy/black/bandit 四类问题被掩盖。**任何"门禁通过"的结论必须先确认该门禁真的执行了、且检查范围没被 flag 削掉。**

### 批次 1.3（T7）CRM 解冻 — 事实校正与设计（2026-09-24）

> **动工前核查（实际命令输出）**，先校正 SSOT（SKILL_FREEZE_LIST §5）中三处与代码事实不符的描述，避免按错误前提施工。

| # | SSOT 描述 | 代码事实 | 处置 |
|---|---|---|---|
| ① | §5.1「移除 `crm_skill.py` 文件顶部 `# [FROZEN v0.3.0]` 标记」「解锁所有方法（移除 `# [FROZEN v0.3.0] add_customer` 等注释）」 | 文件内**不存在**任何 per-method `# [FROZEN]` 注释；只有文件头 `"""[SEMI-FROZEN v0.3.0] ..."""` 模块 docstring | 解冻动作 = 改写模块 docstring；SSOT §5.1 该两条合并为一条 |
| ② | §5.1 方法名：`update_customer` / `list_customers` / `add_interaction` / `list_interactions` / `add_followup_reminder` | 实际实现名：`update_customer_status` / `search_customers` / `add_deal` / `get_follow_ups` / `add_follow_up`（`add_deal` 即"合作记录"） | **不重命名**（`email_skill`/`report_skill` 与 64 项既有单测均按现名引用，重命名属破坏性改动且非本批次目标）；改为在 SSOT 补"SSOT 名义 → 实际实现名"映射表 |
| ③ | §5.2「当前约 40%，需补约 40 个测试」 | 实测 `pytest tests/unit/test_crm_skill.py --cov=opc_manager.crm_skill` = **249 stmts / 24 miss / 90%**，64 passed | 存量覆盖率**已达标**（≥80%）；本批次只需为**新增代码**（PromiseLink 集成 + `lifecycle_tracker`）补测，不虚报补测数量 |

**集成路径校正**：`DormantScanner` 是 **PromiseLink 侧**服务（`services/dormant_scanner.py`），OPC-Agents 侧不存在该类。OPC-Agents 的集成点只能是既有 `PromiseLinkClient`：
- 沉默客户 → `PromiseLinkClient.list_dormant_entities(min_days)`（`GET /api/v1/entities/dormant?min_days=N`，TDD §3.1 已校准）
- 生命周期 → `PromiseLinkClient.get_entity_stage_info(entity_id)`（`GET /api/v1/entities/{id}/stage-info`）

> `PROMISELINK_REUSE_PLAN.md` §3.2 的示例代码基于旧设想的 `PromiseLinkConfig` / `get_promiselink_client()` / `self` 方法，与批次 1.1 落地的实际客户端签名不一致 → **以 `promiselink_client.py` 实际契约为准**，示例代码不作为施工依据。

**设计（最小改动，向后兼容）**：

| 项 | 设计 | 理由 |
|---|---|---|
| 集成开关 | 复用 `PromiseLinkClient()` 读 `PROMISELINK_ENABLED`（默认 `false`），crm_skill 只新增一个模块级 `_get_client()` 工厂，**不新增重复配置项** | 配置单一来源；`PROMISELINK_ENABLED=false` 默认值已在批次 1.1 落地 |
| `get_silent_customers(days)` | 本地查询结果**保持不变**（`success`/`customers`/`count`/`silent_days` 四个键语义不变）；集成可用时**追加** `promiselink`（映射后的实体 + `reactivation_score`/`icebreaker_topic`）与 `source="promiselink"`；不可用或失败时**追加** `promiselink_state`（DISABLED/UNCONFIGURED/DEGRADED…显式给出），本地结果不受影响 | 既有 2 项单测与 `report_skill` 调用方零回归；失败不静默（SKILL_FREEZE_LIST §八） |
| `lifecycle_tracker(customer_id="", name="", entity_id="")` | 本地生命周期视图（status / last_contact / silent_days / deal_count / follow_up_count / stage）**始终可用**；仅当显式传入 `entity_id` 且集成可用时，追加 `promiselink_stage`（stage-info 原始 payload） | 本地 CRM 无 entity_id 字段，不强做隐式映射；关闭集成时能力完整 |

**验收标准（T7）**：
- [x] `crm_skill.py` 不含 `[SEMI-FROZEN v0.3.0]` 标记
- [x] 覆盖率 ≥80%（实测口径：`pytest tests/unit/test_crm_skill.py --cov=opc_manager.crm_skill`）
- [x] `tests/e2e/test_crm_e2e.py` 通过（模拟真实用户走完 录入→查→合作→跟进→沉默→统计 链路）
- [x] 集成关闭（`PROMISELINK_ENABLED` 未设置）时本地 CRM 完整可用；集成开启且 PromiseLink 可用/降级两条路径均有测试
- [x] 既有 64 项 CRM 单测 0 regression；本地五门禁 + 全量回归绿

**实施证据（T7，真实命令输出）**：

| 检查项 | 命令 | 实际输出 |
|---|---|---|
| 存量单测无回归 | `pytest tests/unit/test_crm_skill.py -q` | `64 passed`（改动前基线，改后并入下列 93 项） |
| 单测 + 覆盖率 | `pytest tests/unit/test_crm_skill.py -q --cov=opc_manager.crm_skill` | `93 passed`；`crm_skill.py 317 stmts / 24 miss / 92%` |
| E2E 全链路 | `pytest tests/e2e/test_crm_e2e.py -q` | `43 passed` |
| 收集总数 | `pytest --co -q --no-header` | `4966 tests collected`（原 4894 → +29 单测 +43 E2E） |
| 三语 README 一致性 | CI 原样 heredoc 脚本 | `✓ 三语 README 一致性校验通过（版本 0.5.9, 模块 99, 测试 4966）` |
| ruff | `ruff check opc_manager/ frontend/ tests/` | `All checks passed!`（exit 0） |
| black | `black --check --target-version py310 <3 个改动文件>` | `3 files would be left unchanged.`（exit 0） |
| mypy | `mypy opc_manager/ --ignore-missing-imports --follow-imports=silent` | `Success: no issues found in 130 source files`（exit 0） |
| bandit | `bandit -r opc_manager/ -ll -ii` | 仅 nosec 提示，无告警（exit 0） |
| radon cc ≥D | `radon cc opc_manager/ -s -n D` | 空输出（exit 0） |
| 全量回归 | `pytest -q` | 见下方"实施记录"（W5/T7 全量结果） |

**实施记录（T7）**：
- 代码：`opc_manager/crm_skill.py` — 模块 docstring 改写（移除 `[SEMI-FROZEN v0.3.0]`）；新增 `_get_client()` 工厂 + `_client_state()` / `_map_dormant_entity()` / `_promiselink_dormant()` / `_promiselink_stage()`；`get_silent_customers` 追加集成片段；新增 `lifecycle_tracker()` 与 `_silent_days_since()` / `_STAGE_LABELS`。
- 测试：`tests/unit/test_crm_skill.py` 64 → 93（+29，覆盖 6 态集成分支与 lifecycle 全分支）；新增 `tests/e2e/test_crm_e2e.py`（43 项，真实 SQLite + 真实 `PromiseLinkClient` + `httpx.MockTransport`，不打真实网络）。
- 设计取舍：`stage` 直接取 `_STAGE_LABELS[status]` 而不做 `未知` 兜底——`customers.status` 受 DB `CHECK` 约束为 5 个枚举值，兜底分支不可达（首版写的兜底与对应用例已删除，避免"测试造数据迁就代码"）。
- 文档：三语 README 测试数 4894 → 4966、JP 测试文件数 137 → 138；本文件与 `SKILL_FREEZE_LIST_V1.0.0.md` §5/§6 勾选。
- 未纳入 T7（属批次 3 UI）：`SKILL_FREEZE_LIST` §5.3 文档层中 API.md / README 功能位同步、§5.4 UI 层（技能市场 / Settings / 主导航 / 关系推进卡 / Onboarding）。

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
| 2026-09-24 | 批次 1 追加项 W 完成（W-1 有界重试 + 失败可观测 / W-2 e2e 断言消息如实化 / W-3 两个真实生产调用方同步，第三个经查为占位实现）；补 W 系列实施证据表；记录门禁可信度附带发现（本分支从未触发 CI、main 上 black 与 README 一致性门禁为既有红、本批次 mypy 3 错已修） |
| 2026-09-24 | 按用户指令修复"既有红"：main 上 black（2 个 e2e 文件）与三语 README 一致性（测试数 4744→4894、JP 文件数 100→137）由红转绿；并清除本批次自身引入的 ruff（3 处 F401/F841）与 bandit（3 处 B608，其中 `_update_fields` 补真实列名白名单）问题；本地全门禁复跑全绿 |
| 2026-09-24 | 批次 1.3（T7）CRM 解冻施工完成：docstring 去 `[SEMI-FROZEN]`、新增 `lifecycle_tracker`、`get_silent_customers` 集成增强（六态显式 `promiselink_state`，本地四键语义不变）；单测 64→93、覆盖率 92%、新增 `tests/e2e/test_crm_e2e.py` 43 项（真实 SQLite + 真实 `PromiseLinkClient` + `MockTransport`）；测试数 4894→4966 同步三语 README；补 T7 实施证据表；§5.3/§5.4 与整体解冻验收前三项归属批次 3 |

---

*维护者: DevSquad 协作产出，PM 归档*
