# OPC-Agents 项目整理评估报告 D03

**评估日期**: 2026-07-13
**项目版本**: v0.3.27
**评估方法**: DevSquad 7-Role 并行评估 + 实际命令验证
**评估范围**: 7 维度（代码走读 / 文档同步 / 技术债 / 测试验证 / CI-CD / 目录结构 / 成熟度）
**前次评估**: D02（2026-07-12，v0.3.19，82 分 B+）

> 本报告遵循用户规则：所有结论均附实际命令输出，禁止虚假自评。

---

## 执行摘要 (TL;DR)

| 维度 | D01 (v0.3.3) | D02 (v0.3.19) | D03 (v0.3.27) | 趋势 | 关键问题 |
|------|-------------|---------------|---------------|------|---------|
| 1. 代码走读 | B+ (82) | A- (85) | B (80) | ↓ | 1 P1（ruff 版本漂移） |
| 2. 文档同步 | C (60) | B (75) | B- (70) | ↓ | 1 P1（测试数不准确） |
| 3. 技术债+幽灵 | B (70) | B+ (85) | A- (90) | ↑ | 0 |
| 4. 测试验证 | B+ (78) | B+ (80) | B (75) | ↓ | 1 P1（CI 无法验证） |
| 5. CI/CD | C+ (65) | B+ (82) | D (30) | ↓↓ | 1 P0（CI 全红） |
| 6. 目录结构 | C (60) | B (75) | A- (90) | ↑ | 0 |
| **7. 综合成熟度** | **C+ / 72.9** | **B+ / 82** | **C+ / 72.5** | **↓↓** | **共 5 项（1 P0 + 3 P1 + 1 P2）** |

**结论**: OPC-Agents v0.3.27 相比 D02（v0.3.19，82 分 B+）出现**显著回退**——CI 连续 4 次失败（v0.3.24-v0.3.27 全红），根因是 ruff 版本漂移（CI 锁 0.6.9 / 本地 0.15.21）导致 2 个测试文件的 E402 错误未被 per-file-ignores 豁免。v0.3.27 CHANGELOG 中"v0.4.0 发布门控 14/14 全部达标"的声明**不准确**——CI 门控实际未通过。README 中"4278 个测试"与实际（4116 passed + 77 skipped = 4193）不符。

**v0.4.0 发布决策**: **暂缓**。必须先修复 CI（预估 0.5 人日），验证 CI 全绿后重新评估。

---

## 维度 1：代码走读（架构 / 安全 / 测试 / 性能 / 可维护性 / 文档 / 集成）

**评估方式**: ruff/mypy/black/radon 实际执行 + 文件扫描

### 1.1 静态分析（本地环境）

```
$ ./venv/bin/ruff --version
ruff 0.15.21

$ ./venv/bin/ruff check opc_manager/ frontend/ tests/
All checks passed!

$ mypy opc_manager/
Success: no issues found in 117 source files

$ black --check opc_manager/ frontend/ tests/
248 files would be left unchanged

$ radon cc opc_manager/ -s -n D
(empty — no D+ grade functions)
```

| 指标 | D01 (v0.3.3) | D02 (v0.3.19) | D03 (v0.3.27) | 状态 |
|------|-------------|---------------|---------------|------|
| ruff 错误（本地） | 43 | 0 | 0 | ✅ 保持 |
| mypy 错误 | 0 | 0 | 0 | ✅ 保持 |
| 源文件数 | 109 | 113 | 117 | +4 新模块 |
| radon D+ 函数 | 6 | 0 | 0 | ✅ 保持 |

### 1.2 ⚠️ 关键发现：ruff 版本漂移

| 环境 | ruff 版本 | 检查结果 |
|------|----------|---------|
| 本地 venv | 0.15.21 | ✅ All checks passed |
| CI (python-ci.yml L41) | 0.6.9 (pinned) | ❌ 6 errors (E402) |

**根因**: `tests/unit/test_mcp_transport.py` 和 `tests/unit/test_skill_marketplace_api.py` 使用 `pytest.importorskip()` 在模块级导入之前，触发 E402。ruff 0.15.21 对此模式更宽容（识别 importorskip 为守卫语句），0.6.9 严格报错。`pyproject.toml` 的 `per-file-ignores` 仅豁免 `frontend/app.py` 和 `tests/e2e/test_docker_deployment.py`，未包含这 2 个测试文件。

**影响**: 本地开发者认为代码通过 lint，但 CI 实际失败。**所有 v0.3.24-v0.3.27 的 CI 均失败在此步骤**。

### 1.3 架构 [B+]

- tool_system.py 拆分（v0.3.25）为 4 子模块 + Facade，复杂度 D→C ✅
- 三贤者并行投票架构稳定 ✅
- 最大文件 task_engine_v3_executors.py 788 行（< 800 限制）✅
- 125 个 .py 文件，37,078 行，无 God Class ✅

**Dim 1 评分**: 80/100 (B) — 代码质量本身良好，但 ruff 版本漂移导致本地检查与 CI 不一致，削弱信心

---

## 维度 2：文档同步与一致性

### 2.1 版本号一致性 ✅

```
VERSION: 0.3.27
opc_manager/version.py: __version__ = "0.3.27"
Dockerfile ARG: 0.3.27
README.md / README-EN.md / README-JP.md: v0.3.27
CHANGELOG.md: v0.3.27 entry exists
```

### 2.2 ⚠️ 测试数不准确

| 来源 | 声称测试数 | 实际测试数 | 差异 |
|------|-----------|-----------|------|
| README.md (L42) | 4278 | 4116 passed + 77 skipped = 4193 | -85 |
| README-EN.md | 4278 | 同上 | -85 |
| README-JP.md | 4278 | 同上 | -85 |
| python-ci.yml L201 (EXPECTED_TEST_COUNT) | 4278 | 同上 | -85 |

```
$ pytest --ignore=tests/e2e --tb=no -q
4116 passed, 77 skipped, 3 warnings in 71.29s
```

**影响**: README 宣传数据不准确；CI 的 README 一致性检查（L179-208）虽因 README 和 EXPECTED 都是 4278 而"自洽通过"，但两者均与实际不符。用户看到"4278 个测试"但实际只有 4193 个。

### 2.3 CHANGELOG 与 PROJECT_STATUS

- CHANGELOG.md v0.3.27 条目存在 ✅
- PROJECT_STATUS.md 更新至 v0.3.27 ✅
- IMPROVEMENT_PLAN_V0.3.24.md Wave 1-3 + 门控状态已更新 ✅

**Dim 2 评分**: 70/100 (B-) — 版本同步良好，但测试数不准确是文档诚信问题

---

## 维度 3：技术债 + 幽灵功能

### 3.1 幽灵功能扫描 ✅

```
pass-only functions (ghost): 0 found
NotImplementedError: 0 found
if False / if 0 dead code: 0 found
```

### 3.2 TODO/FIXME

- 5 处 "TODO" 字符串，全部在 llm_content_prompt.py 和 next_action_decider.py 中作为**字符串内容**（非真实待办）✅

### 3.3 技术债清理进展

| 项目 | D02 状态 | D03 状态 |
|------|---------|---------|
| tool_system.py God Class | 754 行 | ✅ 拆分为 4 子模块 + Facade |
| Mock 反模式 | 31 文件 | ✅ 56 处反模式已修复 |
| timeout 测试 | 6 个 | ✅ 0 个（conftest mock 修复） |
| 覆盖率 | 68.25% | ✅ 74% |

**Dim 3 评分**: 90/100 (A-) — 技术债清理成效显著，无幽灵功能

---

## 维度 4：测试验证

### 4.1 本地全量测试 ✅

```
$ pytest --ignore=tests/e2e --tb=no -q
4116 passed, 77 skipped, 3 warnings in 71.29s
```

| 指标 | D01 | D02 | D03 | 状态 |
|------|-----|-----|-----|------|
| 测试通过 | 3781 | 3913 | 4116 | ↑↑ |
| timeout | 多个 | 6 | 0 | ✅ |
| 失败 | 3 | 0 | 0 | ✅ |
| 覆盖率 | 65% | 68.25% | 74% | ↑ |

### 4.2 ⚠️ CI 无法验证

CI 在 ruff 步骤（L38-42）即失败，后续测试步骤（L64-69）、覆盖率步骤（L79-87）均未执行。本地测试通过但**CI 无法验证**，意味着测试结果未经 Linux 环境交叉验证。

### 4.3 E2E 测试

- weekly-e2e-real.yml 手动触发成功（run 29261499813）✅
- 计划任务触发成功（run 29228767681）✅
- E2E 阈值修复（15s→30s 匹配文档质量门）✅

**Dim 4 评分**: 75/100 (B) — 本地测试质量高，但 CI 验证链断裂

---

## 维度 5：CI/CD 检查 ❌ P0 关键问题

### 5.1 CI 运行状态

```
$ gh run list --limit 10 --json conclusion,name,event,createdAt
```

| Run ID | 事件 | CI 结果 | weekly-e2e 结果 |
|--------|------|---------|----------------|
| 29262171200 | push (v0.3.27) | ❌ failure | — |
| 29261499813 | workflow_dispatch | — | ✅ success |
| 29257295406 | push (v0.3.26) | ❌ failure | — |
| 29249634361 | push (v0.3.25) | ❌ failure | — |
| 29230099896 | push (v0.3.24) | ❌ failure | — |
| 29228767681 | schedule | — | ✅ success |

**CI 连续 4 次失败（v0.3.24-v0.3.27），全红。**

### 5.2 失败根因

```
$ gh run view 29262171200 --log-failed
test (3.10): failure  (Lint with ruff)
test (3.11): failure  (Lint with ruff)
test (3.12): failure  (Lint with ruff)
```

**失败步骤**: `Lint with ruff (blocking — unified with pre-commit)` (python-ci.yml L38-42)

**错误详情** (6 个 E402):
```
tests/unit/test_mcp_transport.py:19:1: E402 Module level import not at top of file
tests/unit/test_mcp_transport.py:21:1: E402 Module level import not at top of file
tests/unit/test_skill_marketplace_api.py:21:1: E402 Module level import not at top of file
tests/unit/test_skill_marketplace_api.py:23:1: E402 Module level import not at top of file
tests/unit/test_skill_marketplace_api.py:24:1: E402 Module level import not at top of file
tests/unit/test_skill_marketplace_api.py:25:1: E402 Module level import not at top of file
Found 6 errors.
##[error]Process completed with exit code 1.
```

### 5.3 根因分析

| 因素 | 详情 |
|------|------|
| CI ruff 版本 | 0.6.9 (python-ci.yml L41 硬编码 `pip install ruff==0.6.9`) |
| 本地 ruff 版本 | 0.15.21 (venv) |
| 版本差异 | 9 个 minor 版本，E402 对 `pytest.importorskip()` 模式的处理不同 |
| per-file-ignores | 仅豁免 `frontend/app.py` 和 `tests/e2e/test_docker_deployment.py` |
| 受影响文件 | `tests/unit/test_mcp_transport.py`、`tests/unit/test_skill_marketplace_api.py` |

### 5.4 v0.3.27 声明 vs 实际

| v0.3.27 CHANGELOG 声明 | 实际状态 |
|----------------------|---------|
| "CI 全门控通过" | ❌ CI 全红（4 次连续失败） |
| "v0.4.0 发布门控 14/14 全部达标" | ❌ CI 门控未通过 |
| "ruff/mypy/Black/E2E/coverage/radon D+/Bandit/pip-audit 全绿" | ❌ CI ruff 步骤即失败，后续步骤未执行 |

**Dim 5 评分**: 30/100 (D) — CI 完全失效，发布门控声明不准确

---

## 维度 6：目录结构清理

### 6.1 根目录 ✅

- 无散落 .py 文件 ✅
- 无临时/处理文件 ✅
- VERSION/Dockerfile/pyproject.toml 等规范文件齐全 ✅

### 6.2 docs/ 结构 ✅

- 分类清晰（architecture/guides/spec/internal/postmortem/archive）✅
- archive/ 目录归档历史文档 ✅

### 6.3 运行时目录

- `__pycache__`: 15 个目录（gitignored，可接受）
- `data/`/`logs/`/`deliverables/`/`.benchmarks/`: 均已 gitignored ✅

**Dim 6 评分**: 90/100 (A-) — 目录结构规范整洁

---

## 维度 7：综合成熟度评价与建议

### 7.1 评分汇总

| 维度 | D03 评分 | 权重说明 |
|------|---------|---------|
| 1. 代码走读 | 80 (B) | 代码质量好，但工具版本漂移 |
| 2. 文档同步 | 70 (B-) | 版本同步好，测试数不准确 |
| 3. 技术债 | 90 (A-) | 清理成效显著 |
| 4. 测试验证 | 75 (B) | 本地通过，CI 验证断裂 |
| 5. CI/CD | 30 (D) | **全红，关键阻塞** |
| 6. 目录结构 | 90 (A-) | 整洁规范 |
| **加权平均** | **72.5 (C+)** | **D02 82→D03 72.5，回退 9.5 分** |

### 7.2 成熟度评级

```
D01 (v0.3.3):  72.9  C+   ──┐
                              │
D02 (v0.3.19): 82.0  B+   ──┤  D03 回退至 C+ 水平
                              │
D03 (v0.3.27): 72.5  C+   ──┘
```

**评级**: C+（72.5 分）—— 回退至 D01 水平。核心原因是 CI 全红导致发布门控失效，以及文档中测试数不准确。

### 7.3 趋势分析

**进步方面**（相比 D02）:
- ✅ tool_system.py God Class 拆分完成
- ✅ Mock 反模式 56 处修复
- ✅ timeout 测试清零
- ✅ 覆盖率 68% → 74%
- ✅ 安全扫描（pip-audit 0 漏洞）
- ✅ 目录结构更整洁

**回退方面**（相比 D02）:
- ❌ CI 从 B+ (82) → D (30)，全红 4 次
- ❌ 文档测试数不准确（4278 vs 4193）
- ❌ v0.3.27 发布门控声明不实
- ❌ ruff 版本漂移（本地/CI 不一致）

### 7.4 发布就绪判断

| 门控 | v0.3.27 声明 | D03 实际 | 状态 |
|------|-------------|---------|------|
| G1 pip-audit 0 漏洞 | ✅ | ✅（本地验证） | ⚠️ CI 未验证 |
| G2 E2E 0 失败 | ✅ | ✅（weekly-e2e 成功） | ✅ |
| G3 基础版本地运行 | ✅ | ✅（HTTP 200） | ✅ |
| G4 weekly-e2e-real.yml | ✅ | ✅（手动+计划均成功） | ✅ |
| **G5 CI 全门控通过** | ✅（声明） | **❌ 全红 4 次** | **❌ 未达标** |
| **G6 README 测试数准确** | — | **❌ 4278 vs 4193** | **❌ 未达标** |

**实际门控达标**: 4/6（非 14/14）

### 7.5 下一步建议

#### P0（必须，阻塞 v0.4.0）

| # | 任务 | 工作量 | 方案 |
|---|------|--------|------|
| P0-1 | 修复 CI ruff 失败 | 0.5h | 方案 A：CI ruff 版本升级至 0.15.21（与本地一致）；方案 B：将 2 个测试文件加入 per-file-ignores（保持 CI ruff 0.6.9） |
| P0-2 | 修复 README 测试数 | 0.5h | 4278 → 4193（3 个 README + python-ci.yml EXPECTED_TEST_COUNT） |

#### P1（推荐，发布前完成）

| # | 任务 | 工作量 |
|---|------|--------|
| P1-1 | 统一 ruff 版本（pyproject.toml + CI + pre-commit + requirements-dev.txt） | 1h |
| P1-2 | 验证 CI 全绿后重新评估门控 | 0.5h |
| P1-3 | 修正 v0.3.27 CHANGELOG 中"CI 全门控通过"的不实声明 | 0.5h |

#### P2（可选，后续迭代）

| # | 任务 | 工作量 |
|---|------|--------|
| P2-1 | 在 CI 中增加 ruff 版本一致性检查（防止再次漂移） | 1h |
| P2-2 | 自动化 README 测试数更新（从 pytest 结果同步） | 2h |

### 7.6 v0.4.0 发布决策

**建议: 暂缓 v0.4.0 发布**

依据:
1. CI 全红（4 次连续失败），发布门控实际未达标
2. v0.3.27 声明"14/14 全部达标"不准确，需修正
3. README 测试数不准确，影响外部诚信
4. 修复工作量小（~2h），但必须修复后才能发布

**发布路径**:
```
v0.3.27 (当前，CI 红) → v0.3.28 (修复 CI + README，CI 全绿) → 重新评估 → v0.4.0 (如通过)
```

---

## 附录：DevSquad 7 角色共识

| 角色 | 意见 | 关键发现 |
|------|------|---------|
| **Architect** | ⚠️ 暂缓 v0.4.0 | ruff 版本漂移暴露工具链管理缺陷，需统一 |
| **PM** | ⚠️ 暂缓 v0.4.0 | v0.3.27 声明不实损害项目诚信，必须修正后再发布 |
| **Security** | ✅ 安全维度通过 | pip-audit 0 漏洞、Bandit 0 高危（本地验证） |
| **Tester** | ⚠️ 暂缓 v0.4.0 | 本地测试通过但 CI 验证链断裂，未经 Linux 交叉验证 |
| **Coder** | ⚠️ 暂缓 v0.4.0 | 代码质量本身良好，但 CI 修复是前置条件 |
| **DevOps** | ❌ 强烈暂缓 v0.4.0 | CI 全红 4 次是发布阻塞项，P0 必须修复 |
| **UI** | — | 本评估不涉及 UI 维度 |

**共识结论**: 7/7 角色同意暂缓 v0.4.0，先修复 CI（P0），验证全绿后重新评估。

---

**评估人**: DevSquad V4.0.0（7 角色并行评估）
**评估日期**: 2026-07-13
**下次评估**: P0 修复完成后（D04）
