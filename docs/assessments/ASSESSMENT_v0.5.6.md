# OPC-Agents v0.5.6 7 维度项目整理评估报告

> **评估时间**: 2026-07-27 | **评估版本**: v0.5.6 (commit edb8c8e) | **评估方法**: DevSquad 7-Role 共识 + 实测命令验证
> **评估范围**: 代码走读 / 文档一致性 / 技术债清理 / 全面测试 / CI-CD / 目录清理 / 成熟度评价
> **上一份评估**: [ASSESSMENT_v0.5.4.md](ASSESSMENT_v0.5.4.md)（B+ 85/100）

---

## 一、执行摘要

| 维度 | 评级 | 关键发现 |
|------|------|---------|
| 1. 代码走读 | **A-** (90) | 无 God Class，无硬编码密钥，无 pickle，ruff/radon 全通过 |
| 2. 文档一致性 | **B-** (78) | 版本号同步优秀，但模块数 99 严重过期（实际 119/136） |
| 3. 技术债清理 | **C+** (75) | 🔴 发现 MCPClient ghost feature + 4 处依赖版本漂移 |
| 4. 全面测试 | **B** (82) | 单元/集成 4390 全绿，但 E2E 13 个真实失败 |
| 5. CI/CD 检查 | **B+** (86) | CI 配置全面，但 Dockerfile 无阿里云镜像源（硬约束违规） |
| 6. 目录清理 | **A** (95) | 目录非常干净，无临时文件/过程文件 |
| 7. 成熟度评价 | **B+** (84) | 单元测试层面健康，E2E/工具链一致性存在短板 |
| **综合** | **B+ (84/100)** | 比 v0.5.4 (85) 略降 1 分，主要因 E2E 退步和 ghost feature |

### 与 v0.5.4 评估对比

| 维度 | v0.5.4 | v0.5.6 | 变化 | 说明 |
|------|--------|--------|------|------|
| 代码走读 | A- (90) | A- (90) | 持平 | 质量稳定 |
| 文档一致性 | B+ (85) | B- (78) | ↓7 | 模块数/测试数 scope 问题暴露 |
| 技术债清理 | B+ (85) | C+ (75) | ↓10 | 发现 MCPClient ghost feature |
| 全面测试 | A- (88) | B (82) | ↓6 | E2E 从 184/185 退步到 193/206 |
| CI/CD 检查 | B+ (86) | B+ (86) | 持平 | 配置稳定 |
| 目录清理 | A (95) | A (95) | 持平 | 持续优秀 |
| 综合 | B+ (85) | B+ (84) | ↓1 | 略有退步但仍在 B+ 区间 |

---

## 二、问题清单（按严重程度分级）

### 🔴 P0（阻塞级 — 应立即处理）

| ID | 维度 | 问题 | 位置 | 实测证据 |
|----|------|------|------|---------|
| P0-1 | 3 | **MCPClient ghost feature** | `opc_manager/skill_marketplace_external.py:410` | `mcp_protocol.py` 仅有 MCPTool/MCPResource/MCPPrompt/MCPServer 4 个类，无 MCPClient。代码用 `# type: ignore[attr-defined]` + `except ImportError` 双重掩盖，功能从未工作过 |
| P0-2 | 3 | **type:ignore[attr-defined] 隐藏 ghost feature** | `opc_manager/skill_marketplace_external.py:410` | 违反 project_memory 教训"name-defined/F821 的 type:ignore 绝不能保留" |
| P0-3 | 3 | **pytest-asyncio 上界不一致** | `requirements-dev.txt:9` + `pyproject.toml:64` | 注释说 `<1.4.0` 但代码是 `<1.5.0`；pyproject.toml 无上界，可能触发已知 event loop bug |
| P0-4 | 3+5 | **ruff 版本漂移** | `.pre-commit-config.yaml:8` vs `requirements-dev.txt:22` | pre-commit `v0.15.21` vs requirements-dev `>=0.15.22` |
| P0-5 | 3 | **black 版本三处不一致** | 3 处 | pre-commit `26.5.1` vs requirements-dev `>=26.3.1` vs pyproject.toml `>=25.0.0` |

### 🟠 P1（重要问题 — 影响生产就绪）

| ID | 维度 | 问题 | 位置 | 实测证据 |
|----|------|------|------|---------|
| P1-1 | 4 | **E2E 13 个真实失败** | `tests/e2e/` | 7 asyncio 事件循环冲突 + 3 morandi 主题缺陷 + 1 过期断言 + 2 a11y 对比度不达标 |
| P1-2 | 5 | **Dockerfile 无阿里云镜像源** | `Dockerfile:9-11` | project_memory 硬约束违规："服务器无法访问 deb.debian.org 会导致 apt-get update 卡死" |
| P1-3 | 2 | **模块数过期** | README×3 + PROJECT_STATUS.md | 宣称 99，实际顶层 119 / 总计 136（+20/+37） |
| P1-4 | 2 | **测试数 scope 不一致** | README×3 (4596) vs PROJECT_STATUS (4390) | scope 不同（含/不含 e2e）且未互注，"100%通过"声明仅对 4390 有 CI 验证 |
| P1-5 | 2+3 | **HARD_CONSTRAINTS.md 严重过期** | `docs/HARD_CONSTRAINTS.md:5` | 仍停留 v0.3.4（落后 6 版本）；V3 引用错误文件名（mcp_server.py→mcp_protocol.py）+过期计数 |
| P1-6 | 1 | **DIRECTORY_STRUCTURE.md 滞后** | `docs/internal/DIRECTORY_STRUCTURE.md` | 记录 109 文件，实际 136 文件（+24.8%） |
| P1-7 | 4 | **覆盖率运行 6 个超时失败** | `tests/integration/` + `tests/unit/test_agent_brain.py` | `--timeout=30` 过严，CI runner 性能波动时可能 flaky |
| P1-8 | 5 | **Auto Label PR workflow 持续失败** | `.github/workflows/` | HTTP 403 + 标签缺失（ci/cd、chore 等标签不存在） |
| P1-9 | 3 | **无活跃 TECH_DEBT.md** | 缺失 | v0.3.1 到 v0.5.6 跨越 3 版本无活跃技术债追踪 |
| P1-10 | 4 | **venv 工具版本严重漂移** | 本地 venv | black 24.8.0 / mypy 2.2.0 / ruff 0.15.21 均不符合 requirements-dev.txt |

### 🟡 P2（次要问题 — 建议处理）

| ID | 维度 | 问题 | 位置 |
|----|------|------|------|
| P2-1 | 2 | README-JP 额外宣称"100テストファイル"（实际 123） | `README-JP.md:402` |
| P2-2 | 2 | test_version.py 守护不全（仅 3 处，不覆盖 README/Dockerfile 等 14 处） | `tests/unit/test_version.py` |
| P2-3 | 3 | 过期 TODO(v0.3.0) 未处理 | `frontend/page_modules/_marketplace_page.py:235` |
| P2-4 | 3 | 裸 `type: ignore`（无错误码） | `opc_manager/memory_bridge.py:35` |
| P2-5 | 3 | agent_loop.py 3 处返回类型不一致 | `opc_manager/agent_loop.py:457-461` |
| P2-6 | 1 | metrics_collector.py (1251 行) 体量较大 | `opc_manager/metrics_collector.py` |
| P2-7 | 1 | .streamlit/config.toml 被 .gitignore 误忽略 | `.gitignore:33` |
| P2-8 | 4 | 性能测试命名误导（under_50ms 实际 max<200ms） | `tests/integration/test_async_frontend_integration.py:298` |
| P2-9 | 5 | 3 个 dependabot PR 未合并（ruff 0.16.0 / mypy <2.4 major 跳跃） | PR #23/#24/#25 |

---

## 三、7-Role 共识评估

### 3.1 评估表

| Role | 修复 P0 ghost feature | 修复依赖漂移 | 修复 E2E 回归 | 修复文档过期 | 建立活跃 TECH_DEBT.md |
|------|---------------------|-------------|--------------|-------------|---------------------|
| Architect | ✅ 必须修复 | ✅ 必须统一 | ✅ E2E 是质量门 | ✅ 文档是架构一部分 | ✅ 支持 |
| PM | ✅ 影响用户信任 | ✅ 影响 CI 稳定 | ✅ 影响发布质量 | ✅ 影响用户感知 | ✅ 支持 |
| Security | ✅ ghost feature 是隐患 | ⚠️ 需评估版本风险 | — | — | ✅ 支持 |
| Tester | ✅ 需补测试 | — | ✅ 必须修复 | — | ✅ 支持 |
| Coder | ✅ 删 dead code 或实现 | ✅ 简单修复 | ✅ 修复 asyncio | ✅ 数据校对 | ✅ 支持 |
| DevOps | — | ✅ 影响 CI | ✅ E2E 阻塞 | — | ✅ 支持 |
| UI | — | — | ✅ morandi 主题 + a11y | — | — |

### 3.2 共识结论

> **7-Role 共识 7/7 通过**

| 决策项 | 结论 | 优先级 |
|--------|------|--------|
| MCPClient ghost feature | **必须修复**（删除 dead code 或实现类） | P0 立即 |
| 4 处依赖版本漂移 | **必须统一**（ruff/black/pytest-asyncio/mypy） | P0 立即 |
| E2E 13 个失败 | **必须修复**（asyncio + morandi + a11y） | P1 v0.5.7 |
| Dockerfile 阿里云镜像源 | **必须修复**（硬约束违规） | P1 v0.5.7 |
| 文档过期（模块数/测试数/HARD_CONSTRAINTS） | **必须更新** | P1 v0.5.7 |
| 建立活跃 TECH_DEBT.md | **必做**（活文档原则） | P1 v0.5.7 |
| DIRECTORY_STRUCTURE.md 更新 | **必做** | P1 v0.5.7 |

### 3.3 决策依据

依据 project_memory 教训：
- **"type:ignore[name-defined] + F821 绝不能保留必须修复"** — P0-1/P0-2 验证此教训，[attr-defined] 同样隐藏运行时 bug
- **"pre-commit 版本漂移是 CI 失败根因"** — P0-4/P0-5 是 v0.5.5 black 漂移问题的同类未修复项
- **"服务器无法访问 deb.debian.org 会导致 Dockerfile apt-get update 卡死"** — P1-2 是硬约束违规
- **"文档滞后根因：将文档视为一次性交付物而非活文档"** — P1-3/P1-5/P1-6 是此根因的再次体现
- **"测试不应被跳过，skip 测试数量需保持为 0"** — 维度4 验证 0 skip，符合硬约束

---

## 四、诚实评价

### 4.1 做得好的方面（诚实）

1. **单元/集成测试质量高**：4390 测试全绿、0 skip、0 fail，118s 完成，覆盖率 72.43%。这是项目最稳定的基础。
2. **版本号同步优秀**：v0.5.6 的 0.5.6 在 22 处位置全量同步，无遗漏。吸取了 v4.0.5 教训。
3. **目录极其干净**：无临时文件、无过程文件、archive 规范、.pyc 未泄漏、工作树完全 clean。这是 7 维度中表现最好的。
4. **CI 配置全面**：python-ci.yml 覆盖 11 项检查，concurrency 控制到位，dependabot 配置完全符合硬约束。
5. **安全实践扎实**：无硬编码密钥、无 pickle、密钥从环境变量读取并加密存储、prompt injection 阻断、PBKDF2 密码哈希。
6. **God Class 治理有效**：v0.5.0 评估的三个大文件中 data_manager 790→585、task_orchestrator 774→680，主动瘦身。
7. **CHANGELOG 质量优秀**：[0.5.6] 条目包含根因/修复/依据/验证/教训五要素。
8. **PROJECT_STATUS.md 是当前最准确文档**：所有数据与实测一致，"待重测"标记诚实。

### 4.2 存在的问题（诚实）

1. **🔴 真实 ghost feature**: MCPClient 代码从未工作过，被 `type:ignore` + `except ImportError` 双重掩盖。这正是 project_memory 教训中明确警告的反模式，说明教训未完全落实。
2. **🔴 依赖版本管理失控**: ruff/black/pytest-asyncio 三处版本漂移。v0.5.5 修复了 black 24.8.0→26.5.1，但 ruff 漂移和 black 三处不一致仍未修复。这是"同类问题重复出现"的典型。
3. **🔴 E2E 退步**: v0.4.0 时 E2E 184/185 通过，v0.5.6 退步到 193/206（13 失败）。新增的 morandi 主题引入了回归（3 个主题失败 + 2 个 a11y 对比度不达标），且未被 CI 捕获。这违反了"后端 API 测试通过不等于用户能用"原则。
4. **🟠 硬约束违规**: Dockerfile 未配置阿里云镜像源，project_memory 明确记录此教训但未应用。
5. **🟠 文档系统性滞后**: 模块数 99（实际 119/136）、测试数 scope 混乱、HARD_CONSTRAINTS.md 落后 6 版本、DIRECTORY_STRUCTURE.md 滞后 24.8%。这不是个别疏忽，是"文档无自动校验"的工具链缺口。
6. **🟠 技术债追踪缺失**: v0.3.1 到 v0.5.6 跨越 3 版本无活跃 TECH_DEBT.md，违反"活文档原则"。
7. **🟠 venv 与 requirements 脱节**: 本地 venv 的 black/mypy/ruff 版本均不符合 requirements-dev.txt，本地测试结果可能无法复现 CI 行为。

### 4.3 与 project_memory 教训的对照

| 教训 | v0.5.6 落实情况 | 评估 |
|------|----------------|------|
| "type:ignore[name-defined] + F821 绝不能保留" | ❌ 发现 [attr-defined] 隐藏 ghost feature | 未完全落实 |
| "pre-commit 版本漂移是 CI 失败根因" | ❌ ruff 漂移 + black 三处不一致 | 未完全落实 |
| "服务器无法访问 deb.debian.org 需阿里云镜像源" | ❌ Dockerfile 未配置 | 未落实 |
| "文档滞后根因：活文档原则" | ❌ 多处文档过期 | 未完全落实 |
| "测试 skip 必须为 0" | ✅ 0 skip | 已落实 |
| "版本号必须全量同步" | ✅ 22 处全量同步 | 已落实 |
| "SRP 评估原则（非行数阈值）" | ✅ 无 God Class 误判 | 已落实 |
| "Radon cc D+ blocking" | ✅ 无 D+ 函数 | 已落实 |

---

## 五、下一步建议

### 5.1 v0.5.7 修复计划（PATCH — P0+P1 修复）

**P0 立即修复**（预计 1-2 小时）：

1. **P0-1/P0-2: MCPClient ghost feature**
   - 选项 A（推荐）：删除 `skill_marketplace_external.py:410-418` 的 dead code 块，移除 `# type: ignore[attr-defined]`
   - 选项 B：实现 MCPClient 类（如果功能确实需要）
   - 验证：mypy 0 errors + ruff 0 errors + 相关测试通过

2. **P0-3: pytest-asyncio 上界统一**
   - 修正注释：`<1.4.0` → `<1.5.0`（或代码改为 `<1.4.0`）
   - pyproject.toml 同步：`>=0.21.0` → `>=0.21.0,<1.5.0`

3. **P0-4: ruff 版本统一**
   - `.pre-commit-config.yaml`: `rev: v0.15.21` → `v0.15.22`（或更高）

4. **P0-5: black 版本统一**
   - pyproject.toml: `>=25.0.0` → `>=26.5.1`
   - 确认三处（pre-commit/requirements-dev/pyproject.toml）一致

**P1 v0.5.7 修复**（预计 4-8 小时）：

5. **P1-1: E2E 13 个失败**
   - 7 asyncio 冲突：重构 `asyncio.run()` → `new_event_loop() + run_until_complete()`
   - 3 morandi 主题：修复主题应用逻辑
   - 1 过期断言：更新主题数断言（5→7）
   - 2 a11y 对比度：修复 Demo 横幅白底白字

6. **P1-2: Dockerfile 阿里云镜像源**
   - 在 `apt-get update` 前添加 `sed` 替换为阿里云镜像源

7. **P1-3/P1-4/P1-5/P1-6: 文档更新**
   - 模块数 99 → 实测值（119 顶层 / 136 总计）
   - 测试数 scope 统一（建议都用 4390 不含 e2e）
   - HARD_CONSTRAINTS.md 更新到 v0.5.6
   - DIRECTORY_STRUCTURE.md 更新到 136 文件

8. **P1-9: 建立活跃 TECH_DEBT.md**
   - 在 `docs/` 创建 TECH_DEBT.md，登记本次评估所有 TD

### 5.2 v0.6.0+ 长期规划（MINOR）

- metrics_collector.py (1251 行) 拆分 DB 层与业务层
- llm_backend_manager.py (869 行) 拆分健康检查与 fallback 策略
- 扩展 test_version.py 覆盖 README/Dockerfile/scripts 等 14 处版本号位置
- archive 目录治理（清理 v0.1.x~v0.2.x 过时文件）

### 5.3 不建议在 v0.5.7 做的事

- ❌ data_manager.py 拆分（v0.5.2 7-Role 共识推迟到 v0.6.0+，152 处 import 风险）
- ❌ opc_manager 99 文件真子包化（v0.6.0+ MINOR）
- ❌ ruff 0.16.0 / mypy 2.x major 升级（需独立验证）

---

## 六、评估结论

### 6.1 成熟度评级

**B+ (84/100)** — 接近 A- 但有明确短板

| 维度 | 评级 | 说明 |
|------|------|------|
| 代码质量 | A- | 无 God Class，安全实践扎实，质量门控有效 |
| 测试质量 | B | 单元/集成优秀，E2E 退步是真实短板 |
| 文档质量 | B- | 版本号同步好，但数字数据系统性滞后 |
| 技术债管理 | C+ | 发现 ghost feature + 依赖漂移 + 无活跃追踪 |
| CI/CD | B+ | 配置全面，但有硬约束违规和版本漂移 |
| 目录卫生 | A | 持续优秀 |

### 6.2 核心矛盾

v0.5.6 存在一个核心矛盾：**单元测试层面非常健康（4390 全绿 0 skip），但在 E2E、工具链一致性、project_memory 教训落实三方面存在明显短板**。这反映了"单元测试通过 ≠ 系统可用"的工程现实。

### 6.3 发布建议

- ✅ v0.5.6 已发布且 PyPI/GHCR/GitHub Release 三端齐全，**无需回滚**
- ⚠️ 建议尽快发布 v0.5.7 修复 P0（ghost feature + 依赖漂移）和关键 P1（E2E + Dockerfile）
- ⚠️ v0.5.7 发布前必须修复 P0-1（ghost feature），否则违背"无幽灵功能"原则

---

## 附录：评估证据索引

| 维度 | 关键证据 | 来源 |
|------|---------|------|
| 1 | ruff All checks passed / radon 无 D+ / mypy 4 errors（版本差异） | subagent 实测 |
| 2 | grep 0.5.6 22 处 / 模块数 find 119/136 / 测试数 pytest --co 4390 | subagent 实测 |
| 3 | MCPClient 不存在于 mcp_protocol.py（仅 4 个 class）/ ruff 0.15.21 vs 0.15.22 | 主 agent 验证 |
| 4 | pytest 4390 passed 0 skip 118s / E2E 13 failed 193 passed 494s | subagent 实测 |
| 5 | Dockerfile 无 sed 镜像源 / pre-commit ruff v0.15.21 / Auto Label 403 | subagent + 主 agent 验证 |
| 6 | git status clean / Glob 无 .tmp/.bak/.DS_Store | subagent 实测 |

---

**评估完成**。本报告基于 4 个 subagent 并行评估 + 主 agent 验证关键发现，所有结论均有实测命令输出支撑。
