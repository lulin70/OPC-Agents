# OPC-Agents 推进计划：v0.3.32 → v0.4.0

> **创建日期**: 2026-07-15 | **最后更新**: 2026-07-17 | **当前版本**: v0.3.32（已发布）| **依据**: [D06 评估](assessments/ASSESSMENT_D06_TIDY_v0.3.31.md)（88 分 B+）
>
> **工作流**: 文档先行 → 7-role 共识 → 按生命周期推进 → 充分验证 → 推送 Git
>
> **SemVer 约束**: 修复/优化递增 PATCH（v0.3.32），功能完整性提升递增 MINOR（v0.4.0）
>
> **活文档原则**: 文档先行、时刻更新。每个任务完成后更新状态（⏳→✅），共识审查结果实时记录。

---

## 0. 误判修正记录（2026-07-17）

> D06 评估中 T1/T4 经实际代码验证为误判，已修正。详见 [D06 评估报告「误判修正记录」](assessments/ASSESSMENT_D06_TIDY_v0.3.31.md#阻塞-v040-发布的待办)。

| 原任务 | 原定级 | 修正后定级 | 修正依据 |
|--------|--------|-----------|----------|
| T1: async_executor shutdown() 线程 join | P1 | **P3 移除**（保留为讨论项） | [async_executor.py:220-221](file:///Users/lin/trae_projects/OPC-Agents/opc_manager/async_executor.py#L220-L221) 已有 `for t in worker_threads: t.join(timeout=2)`，仅在 `wait=True` 时执行。D06 search agent 仅扫描 L202-209 未读取 L210-221 完整 wait 块 |
| T4: live_log_panel.py SRP 修正 | P3 | **移除** | [live_log_panel.py](file:///Users/lin/trae_projects/OPC-Agents/frontend/components/live_log_panel.py) 无任何 `data_manager` 导入，仅通过 `opc_manager.audit_log.AuditLog`（L390 延迟导入）和 `opc_manager.progress_emitter.ProgressEmitter`（L437 延迟导入）访问后端接口，符合 SRP |

**教训**: 验证了 project_memory 中"基于不完整代码片段的架构改进任务需先校验前提"教训。后续所有基于评估报告的改进任务必须先 grep + 读取完整函数体再启动。

---

## 1. 任务清单

### v0.3.32 — 短期修复（PATCH，无新功能）

| # | 任务 | 优先级 | 来源 | 复杂度 | 生命周期模板 | 状态 |
|---|------|--------|------|--------|-------------|------|
| T1 | ~~async_executor shutdown() 线程 join~~ → 移除（误判） | ~~P1~~ | D06 | — | — | ❌ 移除 |
| T2 | llm_cache.py 温度边界处理注释完善 | P3 | D06 | 低 | minimal | ✅ 已完成 |
| T3 | mypy/black CI 版本锁定 | P3 | D06 | 低 | minimal | ✅ 已完成 |
| T4 | ~~live_log_panel.py SRP 修正~~ → 移除（误判） | ~~P3~~ | D06 | — | — | ❌ 移除 |
| T5 | docs/ 根级别散落文档归档到 docs/assessments/ | P3 | D06 | 低 | minimal | ✅ 已完成 |

**v0.3.32 实际任务范围**: T2 + T3 + T5（3 项 P3 修复，无 P1/P2 阻塞项）

### v0.4.0 — 中期大型任务（MINOR，功能完整性提升）

| # | 任务 | 优先级 | 来源 | 复杂度 | 生命周期模板 |
|---|------|--------|------|--------|-------------|
| T6 | email/finance 全量覆盖率提升（17%/14.5% → ≥50%） | P0 | P0-6 | 高 | full |
| T7 | 715 处 Mock → 真实组件重构 | P1 | P1-8 | 高 | full |

### v0.5.0 — 长期架构演进（远期规划）

| # | 任务 | 优先级 | 来源 |
|---|------|--------|------|
| T8 | tool_system.py 进一步拆分 | P3 | Phase 3 路线图 |

---

## 2. v0.3.32 生命周期阶段映射

> 使用 DevSquad `minimal` 模板（P1 需求 → P3 技术设计 → P7 测试规划 → P8 实现 → P9 测试执行）

### P1 需求分析（PM 主导）

**T2: llm_cache.py 温度边界处理注释完善**
- 现状：[llm_cache.py:122-139](file:///Users/lin/trae_projects/OPC-Agents/opc_manager/llm_cache.py#L122-L139) `put()` 在 `temperature >= CACHE_MAX_TEMPERATURE` 时跳过缓存，逻辑合理
- 需求：补充注释明确缓存策略边界（高温度不缓存、低温度缓存），无需代码逻辑变更
- 验收标准：注释清晰、CI 通过、无测试回归

**T3: mypy/black CI 版本锁定**
- 现状：[python-ci.yml:52,57](file:///Users/lin/trae_projects/OPC-Agents/.github/workflows/python-ci.yml#L52) `pip install mypy/black` 不锁版本，pre-commit 中 mypy v1.11.2 / black 24.8.0
- 需求：CI 中固定 `mypy==1.11.2 black==24.8.0` 与 pre-commit 一致
- 验收标准：CI 和 pre-commit 版本完全一致，CI 通过

**T5: docs/ 散落文档归档**
- 现状：docs/ 根级别有 6+ 散落文档（ASSESSMENT_D01-D04, IMPROVEMENT_PLAN, P2_P3_PLAN, P2_REFACTOR_PLAN, test_plan_ui_e2e）
- 需求：归入 docs/assessments/ 子目录，更新所有引用链接
- 验收标准：docs/ 根级别只保留 PROJECT_STATUS.md 和 HARD_CONSTRAINTS.md 等核心文档；所有内部引用链接更新

### P3 技术设计（Architect + Coder）

| 任务 | 修改文件 | 修改范围 |
|------|----------|----------|
| T2 | opc_manager/llm_cache.py L122-139 | 注释完善 + docstring 边界说明 |
| T3 | .github/workflows/python-ci.yml L52,57 | mypy==1.11.2, black==24.8.0 |
| T5 | docs/ 文件移动 + 引用更新 | 6+ 文件移动到 docs/assessments/ |

### P7 测试规划（Tester）

| 任务 | 测试策略 |
|------|----------|
| T2 | 无新测试（仅注释变更），验证现有 test_llm_cache.py 全通过 |
| T3 | CI 验证：版本锁定后 CI 通过 |
| T5 | 验证文档链接：grep 检查所有引用路径正确 |

### P8 实现（Coder）

按 T2→T3→T5 顺序实现，每个任务独立提交。

### P9 测试执行（Tester）

```bash
# 全量回归
venv/bin/python -m pytest --ignore=tests/e2e --timeout=30 -q
# E2E
venv/bin/python -m pytest tests/e2e/test_ui_playwright.py -v --tb=short
# ruff
venv/bin/python -m ruff check opc_manager/ frontend/ tests/
# 版本一致性
venv/bin/python -m pytest tests/unit/test_version.py -v
```

### P10 部署发布（DevOps）

- VERSION → 0.3.32
- 26+ 文件版本号同步
- CHANGELOG 新增 v0.3.32 条目
- Git tag v0.3.32
- GitHub Release

---

## 3. v0.4.0 方案概述

### T6: email/finance 全量覆盖率提升

**现状**: 专项覆盖率 99%/100%，全量口径仅 17%/14.5%
**目标**: 全量口径 ≥50%（v0.4.0）/ ≥80%（v0.5.0）
**方案**: 分 3 批补充全量测试（每批 ~100 测试），每批独立验证
**生命周期**: full（P1-P11）
**预计测试新增**: ~300

### T7: 715 处 Mock → 真实组件重构

**现状**: v0.3.18-v0.3.22 已修复 4 批 8 文件，剩余 ~700 处
**目标**: 非 streamlit Mock 全部替换为真实组件/fake 类
**方案**: 按模块分批（email/finance/report → tool_system → task_engine → 其他）
**生命周期**: full（P1-P11）
**约束**: 保留 streamlit Mock（ScriptRunContext 运行时上下文所必需）

---

## 4. 7-Role 职责分配

| 角色 | v0.3.32 职责 | v0.4.0 职责 |
|------|-------------|-------------|
| Architect | T2/T3/T5 技术设计审查 | T6/T7 架构影响评估 |
| PM | T2/T3/T5 优先级确认 | T6/T7 用户价值评估 |
| Security | T3 CI 版本锁定安全影响 | T7 Mock 替换安全验证 |
| Tester | T2/T3/T5 测试策略 + P9 执行 | T6/T7 测试计划 |
| Coder | T2/T3/T5 实现 | T6/T7 实现 |
| DevOps | T3 CI 配置 + P10 发布 | v0.4.0 发布流程 |
| UI | —（v0.3.32 无 UI 任务） | — |

---

## 5. 验证计划

### v0.3.32 验证门禁

| 门禁 | 阈值 | 验证方法 |
|------|------|----------|
| ruff | 0 error | `ruff check opc_manager/ frontend/ tests/` |
| mypy | 0 error | `mypy opc_manager/ --ignore-missing-imports` |
| pytest | 0 fail | `pytest --ignore=tests/e2e --timeout=30 -q` |
| E2E | 21/21 pass | `pytest tests/e2e/test_ui_playwright.py -v` |
| Coverage | ≥70% | `pytest --cov-fail-under=70` |
| 版本一致性 | 26+ 文件 0.3.32 | `pytest tests/unit/test_version.py` |
| radon cc | D+ blocking | `radon cc -s -n D opc_manager/` |

### v0.4.0 额外门禁

| 门禁 | 阈值 |
|------|------|
| email 全量覆盖率 | ≥50% |
| finance 全量覆盖率 | ≥50% |
| Mock 数量 | 非 streamlit Mock ≤50 |

---

## 6. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| T6/T7 大型任务耗时过长 | 高 | 中 | 分批推进，每批独立验证 |
| T7 Mock 替换破坏测试 | 中 | 高 | 逐模块替换，每模块回归测试 |
| CI 版本锁定导致兼容性问题 | 低 | 低 | 先在本地验证版本兼容 |
| 文档归档链接更新遗漏 | 中 | 低 | grep 全量检查 + CI 文档一致性检查 |

---

## 7. 共识审查记录

> 7-role 审查结果记录在此节，审查通过后进入实现阶段。

### 审查日期: 2026-07-17

### 7-Role 审查结论

| 角色 | 立场 | 关键意见 | 是否阻塞 |
|------|------|----------|----------|
| **Architect** | ✅ 同意 | T2/T3/T5 均为低风险优化，不影响架构；T1/T4 误判修正合理，避免无效工作 | 否 |
| **PM** | ✅ 同意 | v0.3.32 范围精简为 3 项 P3 修复，符合"修复/优化递增 PATCH"原则；T6/T7 推迟到 v0.4.0 合理 | 否 |
| **Security** | ✅ 同意 | T3 CI 版本锁定有安全价值（防止供应链漂移）；T1 误判修正不影响安全（join 已存在）；密钥策略无变化 | 否 |
| **Tester** | ✅ 同意 | v0.3.32 仅注释+CI 配置+文档归档，无代码逻辑变更，回归测试足够；T6/T7 需详细测试计划 | 否 |
| **Coder** | ✅ 同意 | T2/T3/T5 实现简单；T1/T4 误判修正避免无效代码变更 | 否 |
| **DevOps** | ✅ 同意 | T3 CI 修改与 pre-commit 配置对齐，无运维风险；v0.3.32 发布流程标准 | 否 |
| **UI** | ✅ 同意 | v0.3.32 无 UI 任务，无 UI 风险 | 否 |

### 共识结论

**7/7 一致通过**。v0.3.32 范围精简为 T2+T3+T5（3 项 P3 修复），T1/T4 误判修正避免无效工作。可进入 P8 实现阶段。

### 共识门验证

- ✅ 无角色行使否决权
- ✅ 所有角色确认任务范围与 SemVer 原则一致
- ✅ 所有角色确认误判修正依据充分（基于实际代码 grep + 完整函数体读取）
- ✅ Tester 确认测试策略覆盖所有变更
- ✅ DevOps 确认发布流程无阻塞

---

## 8. 活文档维护规则

1. 每个任务完成后更新本文档任务清单状态（⏳→✅）
2. 共识审查结果实时记录到第 7 节
3. 验证结果实时记录到第 5 节
4. 如计划变更，更新任务清单并标注变更原因（如第 0 节误判修正记录）
5. 版本发布后，本文档归入 docs/internal/archive/

---

## 9. 变更日志

| 日期 | 变更内容 | 变更原因 |
|------|----------|----------|
| 2026-07-15 | 创建文档，初版 T1-T7 任务清单 | D06 评估发现 |
| 2026-07-17 | T1 降级移除（误判）、T4 移除（误判）、新增第 0 节误判修正记录、完成第 7 节 7-role 共识审查 | 实际代码验证发现 D06 评估 T1/T4 为误判 |
| 2026-07-17 | T2/T3/T5 实现完成，版本号同步到 v0.3.32，CHANGELOG 新增条目 | P8 实现阶段完成，进入 P9 测试执行 |
