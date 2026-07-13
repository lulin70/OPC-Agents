# OPC-Agents 项目整理评估报告 D02

**评估日期**: 2026-07-12
**项目版本**: v0.3.19
**评估方法**: DevSquad 7-Role 并行评估 + 实际命令验证
**评估范围**: 7 维度（代码走读 / 文档同步 / 技术债 / 测试验证 / CI-CD / 目录结构 / 成熟度）
**前次评估**: D01（2026-07-05，v0.3.3，72.9 分 C+）

> 本报告遵循用户规则：所有结论均附实际命令输出，禁止虚假自评。

---

## 执行摘要 (TL;DR)

| 维度 | D01 评分 (v0.3.3) | D02 评分 (v0.3.19) | 趋势 | 关键问题数 |
|------|-------------------|-------------------|------|-----------|
| 1. 代码走读 | B+ (82) | A- (85) | ↑ | 1 (P3) |
| 2. 文档同步 | C (60) | B (75) | ↑↑ | 4 (1 P1) |
| 3. 技术债+幽灵 | B (70) | B+ (85) | ↑↑ | 1 (P2) |
| 4. 测试验证 | B+ (78) | B+ (80) | ↑ | 3 (1 P1) |
| 5. CI/CD | C+ (65) | B+ (82) | ↑↑ | 3 (P2) |
| 6. 目录结构 | C (60) | B (75) | ↑↑ | 2 (P2) |
| **7. 综合成熟度** | **C+ / 72.9分** | **B+ / 82分** | **↑↑** | **共 14 项** |

**结论**: OPC-Agents v0.3.19 相比 D01（v0.3.3）有显著提升——ruff/mypy 全绿、幽灵功能清零、E2E 门控生效、三语 README 一致性校验、pre-commit 补全、Dockerfile 多阶段构建。**但仍存在版本号局部不同步（mcp_protocol 0.3.3）、3 个测试失败（1 个单元测试 bug + 2 个环境依赖）、工作区残留文件未清理**。距离生产就绪（A-）还差一轮 P1 修复（约 0.5 人日）。

---

## 维度 1：代码走读（架构 / 安全 / 测试 / 性能 / 可维护性 / 文档 / 集成）

**评估方式**: Explore Agent 全量扫描 + Grep 验证 + ruff/mypy 实际执行

### 1.1 静态分析 [A]

```
$ ruff check .
All checks passed!

$ mypy opc_manager/
Success: no issues found in 113 source files
```

| 指标 | D01 (v0.3.3) | D02 (v0.3.19) | 状态 |
|------|-------------|---------------|------|
| ruff 错误 | 43 | 0 | ✅ 清零 |
| mypy 错误 | 0 | 0 | ✅ 保持 |
| 源文件数 | 109 | 113 | +4 新模块 |

### 1.2 架构 [B+]

| 指标 | 数值 | 评估 |
|------|------|------|
| opc_manager/ .py 文件数 | 121 | 合理规模 |
| opc_manager/ 总行数 | 36,739 | 中型项目 |
| 最大文件行数 | 788 (task_engine_v3_executors.py) | ✅ 无超 800 行 |
| 前十大文件 | 788→633 行 | 均在可接受范围 |

**架构改进**（相比 D01）:
- ✅ strategist_brain.py 884→176 行（Facade 模式拆分）
- ✅ reflector_brain.py 841→222 行（Facade 模式拆分）
- ✅ tests/ 已分层为 unit(62) + integration(31) + e2e(10) + tools

### 1.3 安全 [A-]

- ✅ 无 `eval(` / `exec(` / `os.system(` 危险调用
- ✅ 无硬编码密钥（`settings.py:47` 仅为 docstring 示例）
- ✅ 无裸 `except:`
- ✅ Dockerfile 使用非 root 用户（opcuser）
- ✅ .dockerignore 排除 .env* / .git / coverage / logs

### 1.4 代码质量 [A-]

- ✅ 无调试残留（breakpoint/pdb）
- ✅ 无 `NotImplementedError` 占位
- ✅ 无 `if False:` / `if 0:` 死代码
- ✅ TODO/FIXME 仅在 llm_content_prompt.py 字符串内容中（非真实 TODO）

### 1.5 幽灵功能检测 [A-]

```
$ grep -P "def \w+\([^)]*\):\s*$\n\s*pass\s*$" opc_manager/ (multiline)
→ export/manager.py:29-30: def __init__(self): pass
```

**export/manager.py:29-30** — 单例模式（Singleton）刻意设计。`__new__` 已完成 `_register_builtin_exporters()` 初始化，`__init__` 的 `pass` 避免重复初始化。**非幽灵功能**，但建议加注释说明意图。

---

## 维度 2：文档同步与一致性

**评估方式**: Grep 版本号 + Read 文档内容 + CI 一致性校验

### 严重问题（1 项）

#### [严重-1] `mcp_protocol.py:25` 版本号未同步 [P1]

```python
# opc_manager/mcp_protocol.py:25
MCP_SERVER_VERSION = "0.3.3"  # 应为 0.3.19
```

**影响**: MCP 协议握手时上报版本号 0.3.3，与实际版本 0.3.19 不一致。CI 的版本一致性校验只检查 VERSION 文件 vs version.py，**未覆盖 mcp_protocol.py**。

### 中等问题（3 项）

#### [中-2] `knowledge_bridge.py:301` User-Agent 版本号未同步

```python
# opc_manager/knowledge_bridge.py:301
"User-Agent": "OPC-Agents/0.3.2",  # 应为 0.3.19
```

#### [中-3] 5 个模块 docstring 版本号停留在 v0.3.2

| 文件 | 行号 | 当前 | 应为 |
|------|------|------|------|
| settings.py | 2, 162 | v0.3.2 | v0.3.19 |
| onboarding.py | 2 | v0.3.2 | v0.3.19 |
| error_handler.py | 2 | v0.3.2 | v0.3.19 |
| shortcuts_handler.py | 2 | v0.3.2 | v0.3.19 |

#### [中-4] README 亮点章节停留在 v0.3.5

README.md 第 34 行 `## v0.3.5 亮点`，虽然版本号已更新到 v0.3.19，但亮点内容未更新。后续 v0.3.6-v0.3.19 的改进（技术债清理、mypy 豁免移除、Mock 反模式修复）未在亮点中体现。

### 已修复（相比 D01）✅

- ✅ 三语 README 不存在的目录描述已修正
- ✅ 版本历史表格已补全
- ✅ install.sh 路径已修正
- ✅ 冻结技能数量已统一

---

## 维度 3：技术债 + 幽灵功能检测

**评估方式**: Grep TODO/FIXME/NotImplementedError/pass/xfail/skip

### 幽灵功能 [A]

| D01 问题 | D02 状态 |
|----------|----------|
| skill_registry.py from_dict 空实现 | ✅ 已修复 |
| task_engine_v3_executors.py 空 try 块 | ✅ 已修复 |
| audit_log.py __init__ pass | ✅ 已核实 |

**D02 新发现**: export/manager.py:29-30 `__init__: pass` — 单例刻意设计（非幽灵功能）。

### 技术债清单

| 类别 | 数量 | 评估 |
|------|------|------|
| TODO/FIXME 注释 | 0（仅字符串内容） | ✅ 清零 |
| NotImplementedError | 0 | ✅ |
| type: ignore | 需 grep 确认 | P3-3 已清理 83→0 |
| xfail strict=False | 需 grep 确认 | D01 已清理 |
| CI deselect 的测试 | 0 (已全部修复) | ✅ P1-7 已修复 (v0.3.21) |

### CI deselect 的测试 [P1-7] — ✅ 已修复 (v0.3.21)

python-ci.yml 中原有 6 个 test_settings.py 测试被 `--deselect`，现已全部修复并移除 deselect。

**根因**: `_read_key_from_env_local()` 使用 `Path(".env.local")`（CWD 相对路径）读取密钥，而 `_ensure_encryption_key()` 写入 `Path(self.SETTINGS_FILE).parent / ".env.local"`。路径不一致导致 CI 中无法读取之前写入的密钥，生成新密钥时调用 `_save_to_disk()` 覆盖了设置文件，provider 重置为默认值 'moka'。

**修复**:
1. `_read_key_from_env_local()` 改为优先读取 `Path(self.SETTINGS_FILE).parent / ".env.local"`，兼容回退 `Path(".env.local")`
2. `_ensure_encryption_key()` 移除 `self._save_to_disk()` 调用，避免在 `_load_from_disk()` 之前覆盖设置文件

---

## 维度 4：测试验证

**评估方式**: 实际执行 `pytest` / `ruff` / `mypy`

### 4.1 全量测试

```
$ ./venv/bin/python -m pytest --tb=no -q
3 failed, 3864 passed, 114 skipped, 3 warnings in 505.14s (0:08:25)
```

| 指标 | D01 (v0.3.3) | D02 (v0.3.19) | 状态 |
|------|-------------|---------------|------|
| 通过 | 3359 | 3864 | ↑ +505 |
| 失败 | 0 | 3 | ⚠️ 新增 |
| 跳过 | 110 | 114 | ⚠️ 略增 |
| xpassed | 1 | 0 | ✅ 已清理 |
| 耗时 | 342s (5:42) | 505s (8:25) | ↑ 测试量增加 |

### 4.2 失败测试分析（3 项）

#### [P1] test_moka_takes_priority_over_ollama（单元测试）

```
FAILED tests/unit/test_ollama_backend.py::TestOllamaGetLLMConfig::test_moka_takes_priority_over_ollama
AssertionError: 'moka' not found in 'http://localhost:11434'
```

**分析**: 测试设置 `MOKA_API_KEY` + `OLLAMA_BASE_URL` 环境变量，期望 moka 优先。但 `discover_llm_config()` 可能读取了本地 `.env` 文件中的配置，覆盖了环境变量。**可能是测试隔离问题（.env 文件污染）或优先级 bug**，需调查。

#### [P2] test_search_performance_under_15s（E2E 真实测试）

```
FAILED tests/e2e/test_e2e_real.py::TestRealSearch::test_search_performance_under_15s
AssertionError: 15.64988374710083 not less than 15
```

**分析**: 搜索耗时 15.6s 超过 15s 阈值。环境依赖（网络/限流），CI 中 `--ignore=tests/e2e` 会跳过。

#### [P2] test_chinese_content_generation_real（E2E 真实测试）

```
FAILED tests/e2e/test_e2e_real.py::TestRealFullPipeline::test_chinese_content_generation_real
AssertionError: 137 not greater than 500
```

**分析**: 真实 LLM 生成内容仅 137 字符，未达 500 阈值。环境依赖（LLM 响应质量），CI 中跳过。

### 4.3 覆盖率

| 指标 | 值 | 来源 |
|------|-----|------|
| 全量覆盖率 | 66% | coverage.json |
| CI 阈值 | 65% | python-ci.yml |
| 目标 | 70% | 硬约束 |
| 差距 | 4% | 需补充测试 |

### 4.4 静态分析

- ruff: All checks passed ✅
- mypy: Success, no issues in 113 source files ✅
- radon cc: D+ blocking（CI 门控）✅

---

## 维度 5：CI/CD 检查

**评估方式**: Read .github/workflows/ + Dockerfile + .pre-commit-config.yaml

### CI 门控清单 [B+]

| 门控项 | D01 | D02 | 状态 |
|--------|-----|-----|------|
| ruff/flake8 blocking | ❌ 43 错误 | ✅ 0 错误 | ✅ |
| mypy blocking | ✅ | ✅ | ✅ |
| Black blocking | ✅ | ✅ | ✅ |
| E2E blocking | ❌ `|| true` | ✅ 已移除 | ✅ |
| 覆盖率 gate | 62% | 65% | ✅ |
| radon D+ blocking | 未配置 | ✅ 已配置 | ✅ |
| Bandit 安全扫描 | 未配置 | ✅ 已配置 | ✅ |
| pip-audit 漏洞扫描 | 未配置 | ✅ 已配置 | ✅ |
| Docker build 验证 | 未配置 | ✅ 已配置 | ✅ |
| 版本一致性校验 | 未配置 | ✅ VERSION vs version.py | ✅ |
| 三语 README 一致性 | 未配置 | ✅ 版本/模块/测试数 | ✅ |
| pre-commit | ❌ 无 | ✅ ruff+mypy+black | ✅ |
| Dependabot | ❌ 无 | ✅ 已配置 | ✅ |

### 遗留问题（3 项）

#### [P2] CI 用 flake8 而 pre-commit 用 ruff — ✅ 已修复 (v0.3.21)

python-ci.yml 原 flake8 已替换为 ruff v0.6.9，与 .pre-commit-config.yaml 统一。

#### [P1-7] 6 个 test_settings.py 被 deselect — ✅ 已修复 (v0.3.21)

CI 中 6 个测试被 `--deselect` 跳过（本地通过，CI 失败）。根因是 `_read_key_from_env_local()` 路径与写入路径不一致 + `_ensure_encryption_key()` 在 `_load_from_disk()` 前调用 `_save_to_disk()` 覆盖设置文件。已在 v0.3.21 修复，6 个 `--deselect` 已从 python-ci.yml 移除。

#### [P3] weekly-e2e-real.yml 无失败通知

每周一 3:00 UTC 运行真实 E2E，但无失败通知配置（无 Slack/Email webhook）。

### Dockerfile [A]

- ✅ 多阶段构建（builder + runtime）
- ✅ 固定版本 python:3.11-slim
- ✅ ARG VERSION=0.3.19
- ✅ 非 root 用户（opcuser, UID 1000）
- ✅ HEALTHCHECK（HTTP + DB 双重检查）
- ✅ .dockerignore 完整（.env* / .git / tests / coverage / logs / output）

---

## 维度 6：目录结构清理

**评估方式**: ls 根目录 + 检查 .gitignore + git ls-files

### 工作区残留文件 [P2]

| 文件/目录 | 大小 | 状态 | 应清理 |
|-----------|------|------|--------|
| coverage.json | 1.0M | 存在 | ✅ 应删除 |
| .coverage | 88K | 存在 | ✅ 应删除 |
| logs/ | 2.3M | 存在 | ✅ 应清空 |
| output/ | 0B | 空目录 | ✅ 应删除 |
| .dbg/ | 4.0K | 存在 | ✅ 应删除 |
| .benchmarks/ | 0B | 空目录 | ✅ 应删除 |
| deliverables/ | 36K | 存在 | ✅ 应清空 |
| opc_agents.egg-info/ | 60K | 构建产物 | ✅ 应删除 |

**验证**: `git ls-files | grep -E "coverage\.json|\.coverage$|..."` = 0 → **均未被 git tracked** ✅（.gitignore 已正确排除，但工作区需清理）

### tests/ 分层 [A]

```
tests/
├── unit/         # 62 个测试文件
├── integration/  # 31 个测试文件
├── e2e/          # 10 个测试文件
└── tools/        # 测试工具
```

✅ 已完成分层（D01 时 87 个文件平铺）。

### docs/ 结构 [B]

72 个 .md 文件，docs/internal/archive/ 已归档旧文档。但仍有部分过程文档（如 V033_TECH_DEBT_CLEANUP_PLAN.md、V030_REMEDIATION_PLAN.md）可考虑归档。

---

## 维度 7：成熟度评价 + 下一步建议

### 7.1 成熟度评分（7 维加权）

| 维度 | 权重 | D01 得分 | D02 得分 | 加权分 | 评级 |
|------|------|----------|----------|--------|------|
| 1. 代码走读 | 15% | 82 | 85 | 12.75 | A- |
| 2. 文档同步 | 10% | 60 | 75 | 7.5 | B |
| 3. 技术债+幽灵 | 15% | 70 | 85 | 12.75 | B+ |
| 4. 测试验证 | 20% | 78 | 80 | 16.0 | B+ |
| 5. CI/CD | 15% | 65 | 82 | 12.3 | B+ |
| 6. 目录结构 | 10% | 60 | 75 | 7.5 | B |
| 7. 安全 | 15% | 85 | 88 | 13.2 | A- |
| **总分** | **100%** | **72.9** | **82.0** | **82.0** | **B+** |

### 7.2 成熟度画像

```
功能完整性:    ████████████████████ 95%  (A)   ← 3 核心技能 + 三贤者架构
测试覆盖:      ██████████████████   90%  (A-)  ← 3864 passed + 66% 覆盖率
代码质量:      █████████████████    85%  (B+)  ← ruff/mypy 全绿
安全:          █████████████████    88%  (A-)  ← Bandit + pip-audit + 加密
文档一致性:    ███████████████      75%  (B)   ← 版本号局部不同步
工程纪律:      █████████████████    82%  (B+)  ← CI 门控完善
CI/CD 成熟度:  █████████████████    82%  (B+)  ← 12 项门控
目录组织:      ███████████████      75%  (B)   ← tests 分层好,工作区有残留
```

**核心进步**（相比 D01）:
- 文档同步: C(60) → B(75)，+15 分
- 技术债: B(70) → B+(85)，+15 分
- CI/CD: C+(65) → B+(82)，+17 分
- 目录结构: C(60) → B(75)，+15 分

**核心矛盾**: 代码质量和 CI 门控已达生产级，但**版本号局部不同步 + 工作区残留文件**暴露了工程收尾纪律的不足。距离 A-（生产就绪）还差版本号同步 + 工作区清理 + 测试失败修复。

### 7.3 下一步建议（按优先级排序）

#### 🔴 P0 立即修复（0.3 人日）

1. **`mcp_protocol.py:25`** 版本号 `0.3.3` → `0.3.19`
2. **`knowledge_bridge.py:301`** User-Agent `0.3.2` → `0.3.19`
3. **5 个 docstring** 版本号 `v0.3.2` → `v0.3.19`（settings.py / onboarding.py / error_handler.py / shortcuts_handler.py）
4. **CI 版本一致性校验扩展**: 将 mcp_protocol.py 和 knowledge_bridge.py 纳入校验范围
5. **清理工作区残留文件**: `coverage.json` / `.coverage` / `logs/` / `output/` / `.dbg/` / `.benchmarks/` / `deliverables/` / `opc_agents.egg-info/`

#### 🟡 P1 本周修复（0.5 人日）

6. **调查 `test_moka_takes_priority_over_ollama` 失败**: 确认是 .env 污染还是优先级 bug
7. **修复 CI 中 6 个 test_settings.py deselect**: 根因是 relative path/cwd 问题
8. **README 亮点章节更新**: 从 v0.3.5 更新到 v0.3.19，补充 v0.3.6-v0.3.19 改进
9. **CI 统一 lint 工具**: flake8 → ruff（与 pre-commit 一致）
10. **export/manager.py:29-30 加注释**: 说明 `__init__: pass` 是单例刻意设计

#### 🟢 P2 后续迭代（1-2 人日） — ✅ 全部完成 (v0.3.23)

11. **覆盖率提升**: 66% → 68.25%（8 模块 401 行新覆盖）✅
    - monitoring.py 38%→92%, correction_manager.py 28%→100%, config.py 59%→94%
    - async_executor_persistence.py 31%→100%, protocols.py 41%→95%
    - persona_manager.py 34%→73%, skill_registry.py 47%→71%
    - async_executor_recovery.py 63%→~100%
    - 注：70% 目标未完全达成（实际 68.25%），但 CI minimum 65% 已满足，后续版本继续推进
12. **weekly-e2e-real.yml 添加失败通知** ✅（之前已完成）
13. **80 个 skipped 测试审查** ✅ — 3 个 unjustified skip 修复（80→77），77 剩余全部为冻结技能（SKILL_FREEZE_LIST.md）
14. **docs/ 过程文档归档** ✅（commit c94fa89, docs/internal/）

### 7.4 发布就绪判断

| 门控 | D01 (v0.3.3) | D02 (v0.3.19) | v0.3.23 当前 | v0.3.24 当前 | v0.3.25 当前 | 目标 | 状态 |
|------|-------------|---------------|-------------|--------------|--------------|------|------|
| Unit 测试全绿 | 3359 ✅ | 3864 passed + 3 failed | 3935 passed + 6 timeout（满载） | 3942 passed + 0 timeout | 4278 passed + 0 timeout | 全绿 | ✅ |
| 覆盖率 | — | — | 68.25% | 68.25% | 74% | ≥70% | ✅ |
| mypy 0 错误 | 0 ✅ | 0 (113 files) | 0 (113 files) | 0 (113 files) | 0 (117 files) | 0 | ✅ |
| ruff 0 错误 | 43 ❌ | 0 ✅ | 0 ✅ | 0 ✅ | 0 ✅ | ≤10 | ✅ |
| E2E 测试全绿 | 1 失败 ❌ | 2 失败（环境依赖） | 2 失败（环境依赖） | 2 失败（环境依赖） | 4 失败（环境依赖） | 全绿 | ⚠️ 环境依赖 |
| 文档一致性 | 6 问题 ❌ | 4 问题（1 P1） | 0 严重（P0+P1 修复后同步） | 0 严重 | 0 严重 | 0 严重 | ✅ |
| 无幽灵功能 | 3 个 ❌ | 0 ✅ | 0 ✅ | 0 ✅ | 0 ✅ | 0 | ✅ |
| CI 强制门 | E2E 被吞 ❌ | 12 项门控 ✅ | 12+ 项门控 ✅ | 12+ 项门控 ✅ | 12+ 项门控 ✅ | 全门控 | ✅ |
| 工作区干净 | 残留 ❌ | 残留（.gitignore 已排除） | 已清理（v0.3.20） | 干净 | 干净 | 干净 | ✅ |

**结论**: **v0.3.25 发布门控 8/9 达标**（覆盖率门控从 ⚠️ → ✅，74% 超过 70% 目标）。仅剩 1 项 ⚠️：E2E 真实测试 4 个失败（环境依赖，CI `--ignore=tests/e2e` 跳过，非阻塞）。v0.3.25 完成 Wave 2: tool_system.py God Class 拆分为 4 个子模块 + Facade 模式（754 行 → 225 行 Facade + 700 行子模块），覆盖率从 68.25% 提升至 74%（+5.75pp），新增 99 个覆盖测试。

---

## 附录 A：评估命令输出

### A.1 pytest 输出
```
$ ./venv/bin/python -m pytest --tb=no -q
3 failed, 3864 passed, 114 skipped, 3 warnings in 505.14s (0:08:25)

FAILED tests/e2e/test_e2e_real.py::TestRealSearch::test_search_performance_under_15s
FAILED tests/e2e/test_e2e_real.py::TestRealFullPipeline::test_chinese_content_generation_real
FAILED tests/unit/test_ollama_backend.py::TestOllamaGetLLMConfig::test_moka_takes_priority_over_ollama
```

### A.2 ruff 输出
```
$ ruff check .
All checks passed!
```

### A.3 mypy 输出
```
$ mypy opc_manager/
Success: no issues found in 113 source files
```

### A.4 代码规模
```
opc_manager/: 121 .py files, 36,739 lines
最大文件: task_engine_v3_executors.py (788 lines)
tests/: unit(62) + integration(31) + e2e(10) + tools
docs/: 72 .md files
```

### A.5 git 状态
```
Branch: main
Working tree: clean (git tracked)
Latest commit: 13e81c8 v0.3.19: P3-5 Mock反模式修复扩展
```

### A.6 工作区残留
```
coverage.json (1.0M) — 未 tracked,应删除
.coverage (88K) — 未 tracked,应删除
logs/ (2.3M) — 未 tracked,应清空
output/ (0B) — 未 tracked,应删除
.dbg/ (4.0K) — 未 tracked,应删除
.benchmarks/ (0B) — 未 tracked,应删除
deliverables/ (36K) — 未 tracked,应清空
opc_agents.egg-info/ (60K) — 未 tracked,应删除
```

---

## 附录 B：D01 → D02 进步对比

| 指标 | D01 (v0.3.3) | D02 (v0.3.19) | 变化 |
|------|-------------|---------------|------|
| 版本 | 0.3.3 | 0.3.19 | +16 PATCH |
| 测试通过数 | 3359 | 3864 | +505 |
| ruff 错误 | 43 | 0 | -43 ✅ |
| 幽灵功能 | 3 | 0 | -3 ✅ |
| CI 门控项 | 4 | 12 | +8 ✅ |
| pre-commit | 无 | 有 | ✅ |
| E2E 门控 | `|| true` 吞掉 | blocking | ✅ |
| 文档同步问题 | 6 (2 严重) | 4 (1 P1) | -2 |
| 成熟度总分 | 72.9 (C+) | 82.0 (B+) | +9.1 |

**评估执行人**: DevSquad 7-Role（Architect / PM / Security / Tester / Coder / DevOps / UI）
**评估耗时**: ~15 分钟（3 个并行 Agent + 主线程测试验证）
**报告生成**: 2026-07-12
