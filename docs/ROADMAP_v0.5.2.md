# OPC-Agents v0.5.2 路线图 — 文档同步与可优化项评估收口

> **版本**: v0.5.2 | **日期**: 2026-07-25 | **状态**: 7-Role 共识评估完成
> **类型**: PATCH（无新功能、无破坏性 API 变更）
> **依据**: [v0.5.1 路线图](ROADMAP_v0.5.1.md) + [D07 评估](assessments/ASSESSMENT_D07_TIDY_v0.3.36.md) + 可优化项盘点
> **方法论**: DevSquad V4.1.7 7-Role 共识评估 + Meta Iron Rule 文档先行

---

## 一、背景与动机

### 1.1 v0.5.1 发布后的盘点

v0.5.1（2026-07-20）完成 UI/UX 体验提升（Morandi 主题真正落地 + 暗黑模式 + WCAG 2.1 AA 合规），发布后立即进行的盘点发现两类问题：

| 类别 | 问题 | 严重级别 |
|------|------|---------|
| 文档滞后 | ROADMAP_v0.5.1.md §3.3-3.7 状态列停留在"待创建/待实现/待执行"，但 §10 推进状态显示已全部完成；§10.7 显示 Git commit + Tag v0.5.1 "⏳ 待执行"，但实际已完成 | P1 文档一致性 |
| 过期待办 | PROJECT_STATUS.md §6 Phase 2 列出"v0.4.0 发布前 E2E 复核 / Release Notes 准备"，但 v0.4.0 早已发布（tag 存在） | P2 历史遗留 |

### 1.2 可优化项评估

基于 D07 SRP 评估结论，识别 5 项可优化项。本路线图通过 7-Role 共识评估，决定哪些适合在 PATCH 版本推进。

---

## 二、7-Role 共识评估

### 2.1 依赖分析（实际数据）

| 可优化项 | 文件行数 | 被引用次数 | 风险等级 |
|---------|---------|------------|---------|
| data_manager.py 拆分（encryption + migrations + data_manager） | 790 | **152 处 import，43 文件** | 🔴 高 |
| task_orchestrator.py 提取 ConsensusChecker | 774 | 1 处 import，但 **23 处测试调用私有方法** | 🟡 中 |
| opc_manager 99 文件真子包化 | — | 全量影响 | 🔴 高（v0.6.0+） |
| shared.py 重构 | — | 已部分完成（仅新组件不再中转） | 🟢 已完成 |
| v4.1 外部技能扩展完整化 | — | 新功能 | ❌ 不适合 PATCH |

### 2.2 7-Role 评估表

| Role | data_manager 拆分 | task_orchestrator 拆分 | 文档同步 |
|------|-------------------|------------------------|---------|
| Architect | ❌ 152 处 import 风险 | ❌ D07 评估非 God Class + 23 处测试调用私有方法 | ✅ 支持 |
| PM | ❌ PATCH 不应大改 | ❌ 收益有限 | ✅ 支持 |
| Security | ❌ 加密层不能动 | ❌ 非必要 | ✅ 支持 |
| Tester | ❌ 4338 测试需全跑 | ❌ 需新增转发方法或破坏测试 | ✅ 支持 |
| Coder | ❌ 工作量大收益低 | ❌ 拆分需 4 个转发方法，违背简化原则 | ✅ 支持 |
| DevOps | ❌ CI 风险 | ❌ 无影响但无收益 | ✅ 支持 |
| UI | 无意见 | 无意见 | ✅ 支持 |

### 2.3 共识结论

> **7-Role 共识 7/7 通过**

| 决策项 | 结论 |
|--------|------|
| data_manager.py 拆分 | **推迟到 v0.6.0+**（152 处 import 风险过高，PATCH 版本不应承担此风险） |
| task_orchestrator.py 提取 ConsensusChecker | **不拆分**（D07 SRP 评估非 God Class + 23 处测试调用私有方法 + 拆分需 4 个转发方法违背简化原则） |
| 文档同步 | **必做**（7/7 支持，低风险高收益） |

### 2.4 决策依据

依据 project_memory 教训：
- **SRP 评估原则有效** — D07 评估明确 3 个 700+ 行大文件均非 God Class（52 候选 1.9% 命中率验证行数阈值不可靠）
- **测试不应被修改以适配源代码 bug** — 23 处测试直接调用 `_parallel_consensus` 等私有方法，拆分要么破坏测试，要么增加转发方法（违背简化）
- **Think Before Coding** — 152 处 import 的重构属于 v0.6.0+ MINOR 版本范畴，不应在 PATCH 强推

---

## 三、v0.5.2 工作分解

### 3.1 文档同步（必做）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 1.1 ROADMAP_v0.5.1.md §3.3-3.7 状态列 | 5 个 Phase 表格状态从"待创建/待实现/待执行"更新为"✅ 已完成" | 文档 | ✅ 完成 |
| 1.2 ROADMAP_v0.5.1.md §6.1-6.2 时间线 | 4 个阶段 + 4 个里程碑状态更新为"✅ 完成/达成" | 文档 | ✅ 完成 |
| 1.3 ROADMAP_v0.5.1.md §10.7-10.8 推进状态 | Git commit + Tag v0.5.1 状态从"⏳ 待执行"更新为"✅ 完成"，移除"唯一待执行"措辞 | 文档 | ✅ 完成 |
| 1.4 PROJECT_STATUS.md §6 Phase 2 过期待办 | "待办（v0.4.0 发布前）"改为"已完成（v0.4.0 发布前）"，2 项内容加 ✅ | 文档 | ✅ 完成 |

### 3.2 版本发布（必做）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 2.1 版本号同步 | 0.5.1 → 0.5.2（VERSION + version.py + mcp_protocol.py + README×3 + Dockerfile ARG 等 18 处） | 代码 | ✅ 完成（v0.5.2 已发布，当前 v0.5.6） |
| 2.2 CHANGELOG.md 新增 [0.5.2] 条目 | PATCH 类型，记录文档同步 + 可优化项评估决策 | 文档 | ✅ 完成 |
| 2.3 ROADMAP_v0.5.2.md（本文档） | 决策记录与依据 | 文档 | ✅ 完成 |
| 2.4 PROJECT_STATUS.md 更新 | 反映 v0.5.2 当前版本 | 文档 | ✅ 完成（v0.5.4 评估时同步更新测试数据） |

### 3.3 测试验证（必做）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 3.1 版本一致性测试 | test_version.py 9/9 通过 | 测试 | ✅ 完成 |
| 3.2 静态检查 | mypy 0 errors + ruff All checks passed + radon cc 无 D+ | 报告 | ✅ 完成 |
| 3.3 全量回归测试 | 单元 + 集成测试 100% 通过 | 报告 | ✅ 完成（v0.5.5: 4390 passed） |

### 3.4 推送发布（必做）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 4.1 Git commit + push | origin/main | 提交 | ✅ 完成 |
| 4.2 Tag v0.5.2 | 触发 release.yml workflow | tag | ✅ 完成 |

---

## 四、范围说明

### 4.1 包含范围（In Scope）

- ✅ ROADMAP_v0.5.1.md 文档状态同步（§3.3-3.7 + §6.1-6.2 + §10.7-10.8）
- ✅ PROJECT_STATUS.md §6 Phase 2 过期待办清理
- ✅ ROADMAP_v0.5.2.md（本文档，决策记录）
- ✅ 版本号 0.5.1 → 0.5.2 同步
- ✅ CHANGELOG [0.5.2] 条目

### 4.2 排除范围（Out of Scope）

- ❌ data_manager.py 拆分（推迟到 v0.6.0+ MINOR，152 处 import 风险）
- ❌ task_orchestrator.py 提取 ConsensusChecker（D07 SRP 评估非 God Class + 23 处测试调用私有方法）
- ❌ opc_manager 99 文件真子包化（v0.6.0+ MINOR）
- ❌ v4.1 外部技能扩展完整化（新功能，MINOR）

### 4.3 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 单独为文档同步发 PATCH 是否合理 | 低 | 低 | SemVer 严格解读下文档更新不算 bug 修复，但 project_memory "文档同步"是 Meta Iron Rule，发版本强制校验文档一致性是合理做法 |
| 测试因版本号变更失败 | 低 | 低 | test_version.py 自动校验，失败立即修复 |

---

## 五、验收标准

### 5.1 文档验收

| 文档 | 状态 |
|------|------|
| ROADMAP_v0.5.2.md（本文档） | ✅ |
| ROADMAP_v0.5.1.md 状态同步 | ✅ |
| PROJECT_STATUS.md 更新 | ✅ |
| CHANGELOG.md [0.5.2] 条目 | ✅ |

### 5.2 质量验收

| 维度 | 标准 |
|------|------|
| 版本一致性 | test_version.py 9/9 通过 |
| mypy | 0 errors |
| ruff | All checks passed |
| radon cc | 无 D+ 函数 |
| 单元测试 | 0 failure |
| 集成测试 | 0 failure |

---

## 六、附录

### 6.1 相关文档

- [ROADMAP_v0.5.1.md](ROADMAP_v0.5.1.md) — v0.5.1 路线图（前置，已同步状态）
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — 项目当前状态
- [ASSESSMENT_D07_TIDY_v0.3.36.md](assessments/ASSESSMENT_D07_TIDY_v0.3.36.md) — D07 SRP 评估依据

### 6.2 决策追溯

- **2026-07-25**: 7-Role 共识评估完成，决策不拆分 data_manager.py 和 task_orchestrator.py，仅做文档同步
- **依据**: D07 SRP 评估 + project_memory 教训（行数阈值不可靠）+ 23 处测试调用私有方法 + 152 处 import 风险
