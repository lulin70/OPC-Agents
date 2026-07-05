# Skill 生态借鉴分析：design.md / Anthropic-Cybersecurity-Skills / Ponytail

> **研究日期**: 2026-07-01 | **研究者**: DevSquad | **版本**: v1.0
> **目的**: 研究 GitHub 上三个 Skill 生态项目的规范格式、结构化 Skills 库设计、行为约束降低平台风险等，评估对 OPC-Agents / DevSquad 的借鉴意义

---

## 1. 研究对象概览

| 项目 | 仓库 | 规模 | 核心价值 |
|------|------|------|----------|
| **Anthropic-Cybersecurity-Skills** | `mukul975/Anthropic-Cybersecurity-Skills` | 817 技能 / 29 领域 | 结构化 Skills 库 + 6 大框架映射 |
| **Ponytail** | `DietrichGebert/ponytail` | v4.8.3 / ~1000 行 AGENTS.md | 行为约束决策模型 + 硬约束边界 |
| **design.md** | `google-labs-code/design.md` | Apache-2.0 / CLI 工具 | 机器可读 + 人类可读设计规范 |

---

## 2. agentskills.io 开放标准（三个项目共同遵循）

### 2.1 SKILL.md 格式规范

```markdown
---
name: skill-name                    # 必需, kebab-case, ≤64 chars, 必须与目录名一致
description: What it does and when  # 必需, ≤1024 chars, 含触发关键词
license: Apache-2.0                 # 可选
compatibility: Requires Python 3.10+ # 可选, ≤500 chars
metadata:                           # 可选, 任意 key-value
  author: example-org
  version: "1.0"
allowed-tools: Bash(git:*) Read     # 可选, 预批准工具列表
---

# Skill Title

## Step-by-step instructions
...
```

### 2.2 标准目录结构

```
skill-name/
├── SKILL.md          # 必需: 元数据 + 指令
├── scripts/          # 可选: 可执行代码
├── references/       # 可选: 详细参考文档
└── assets/           # 可选: 模板、资源文件
```

### 2.3 关键设计原则

1. **Progressive Disclosure（渐进式披露）**: Level 1 Quick Start (~2K tokens) → Level 2 Implementation (~30min) → Level 3 Deep Dive，按需加载，减少 91-99.6% token 消耗
2. **触发关键词驱动**: description 中包含具体动词和场景关键词，AI Agent 据此自动激活技能
3. **跨平台兼容**: 同一 SKILL.md 可在 Claude Code / Copilot / Codex CLI / Cursor / Gemini CLI 等 26+ 平台使用

---

## 3. Anthropic-Cybersecurity-Skills 借鉴分析

### 3.1 结构化 Skills 库设计

**分类体系**: 29 个安全领域，817 个技能
- 云安全（66）/ 威胁猎捕（58）/ 威胁情报（52）/ 网络安全（43）
- Web 应用安全（42）/ 数字取证（41）/ 恶意软件分析（39）
- IAM（37）/ SOC 运营（35）/ 红队（33）

**框架映射**: 每个技能映射到 6 大框架
- MITRE ATT&CK v19.1（15 战术 / 286 技术）
- NIST CSF 2.0（6 功能 / 22 类别）
- MITRE ATLAS（AI/ML 对抗性威胁）
- MITRE D3FEND（防御性对抗措施）
- NIST AI RMF（AI 风险管理）
- MITRE F3（ Fight Fraud Framework）

**安装方式**: `npx skills add mukul975/Anthropic-Cybersecurity-Skills` 一键安装

### 3.2 对 OPC-Agents 的借鉴

| 借鉴点 | 当前 OPC-Agents 状态 | 改进方向 |
|--------|---------------------|----------|
| 技能分类体系 | DevSquad 7 角色无领域分类 | 按业务领域分类（架构/安全/测试/性能/DevOps/UI/产品） |
| 框架映射 | 无映射 | 将技能映射到 OWASP / NIST / CIS 等框架 |
| 一键安装 | 无安装机制 | 提供 `npx skills add` 或 `pip install` 安装方式 |
| Progressive Disclosure | SKILL.md 全量加载 | 实现 3 级渐进式加载 |

---

## 4. Ponytail 借鉴分析

### 4.1 七层"懒惰阶梯"决策模型

```
Before writing any code, stop at the first rung that holds:
1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse it.
3. Does the standard library already do this? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Make it one line.
7. Only then: write the minimum code that works.
```

### 4.2 硬约束边界（永不削减）

> "Not lazy about: understanding the problem, input validation at trust boundaries, error handling that prevents data loss, security, accessibility, the calibration real hardware needs."

| 硬约束 | 说明 | OPC-Agents 对应 |
|--------|------|-----------------|
| 信任边界输入校验 | 用户输入/API 入口必须校验 | InputValidator（21+ 模式 prompt injection 检测） |
| 防数据丢失错误处理 | 关键操作异常不静默吞没 | encrypt_field fail-closed / audit_log 链式哈希 |
| 安全性 | 永不妥协 | PBKDF2 / hmac.compare_digest / CORS |
| 硬件校准参数 | 真实环境参数不可省略 | 性能基线测试 / zombie scan timeout |

### 4.3 Bug 修复 = 治根不治标

> "Bug fix = root cause, not symptom. grep 出你改动函数的所有调用者，在共享函数里一次性修。"

实测结果：**根因修复率从 1/6 提升到 6/6**（Sonnet 4.6 和 Opus 4.8 验证）

### 4.4 对 OPC-Agents 的借鉴

| 借鉴点 | 当前状态 | 改进方向 |
|--------|----------|----------|
| 7 层决策模型 | 无决策模型 | DevSquad Worker 在编码前执行 YAGNI → 复用 → 标准库 → 最小实现检查 |
| 硬约束边界 | 部分实现 | 显式声明"永不削减"清单，CI 检查 |
| 根因修复 | 修复时有记录但不强制 grep 调用者 | 强制修复前 grep 所有 caller，共享函数一次性修 |
| ponytail: 标记 | 无标记机制 | 技术债标记用 `# ponytail: 简化原因` 注释 |

---

## 5. design.md 借鉴分析

### 5.1 双层格式设计

```yaml
---
version: alpha
name: Heritage
colors:
  primary: "#1A1C1E"
  tertiary: "#B8422E"
typography:
  h1:
    fontFamily: Public Sans
    fontSize: 3rem
---

## Overview
Architectural Minimalism meets Journalistic Gravitas...

## Colors
- **Primary (#1A1C1E):** Deep ink for headlines and core text.
- **Tertiary (#B8422E):** "Boston Clay" — the sole driver for interaction.
```

**设计哲学**: Tokens give exact values. Prose tells agents *why* those values exist and how to apply them.

### 5.2 CLI 验证工具

```bash
# 验证结构 + token 引用 + WCAG 对比度
npx -y @google/design.md lint DESIGN.md

# 版本 diff，检测回归
npx -y @google/design.md diff old.md new.md

# 导出 Tailwind / W3C DTCG JSON
npx -y @google/design.md export DESIGN.md --format tailwind
```

### 5.3 规范化节顺序

```
1. Overview → 2. Colors → 3. Typography → 4. Layout
→ 5. Elevation → 6. Shapes → 7. Components → 8. Do's and Don'ts
```

### 5.4 对 OPC-Agents 的借鉴

| 借鉴点 | 当前状态 | 改进方向 |
|--------|----------|----------|
| 双层格式（YAML + Markdown） | SKILL.md 纯 Markdown | 关键配置用 YAML frontmatter，说明用 Markdown body |
| CLI 验证工具 | 无验证工具 | 添加 `python -m opc_manager.skill_validator` 检查格式合规 |
| 规范化节顺序 | 无固定顺序 | 定义标准节顺序：Overview → When to Use → Process → Constraints → Verification |
| 版本 diff | 无版本管理 | 技能变更时检测行为回归 |

---

## 6. 综合改进建议（按优先级排序）

### P0: 立即可借鉴（低成本高价值）

1. **agentskills.io 标准对齐**: DevSquad 的 SKILL.md 已接近标准，补充 `license` / `compatibility` / `metadata` 可选字段
2. **Ponytail 硬约束清单**: 显式声明 OPC-Agents 的"永不削减"清单（已有硬约束，需文档化）
3. **根因修复规则**: DevSquad Worker 修复 bug 前强制 grep 所有 caller

### P1: 中期改进（中成本中价值）

4. **技能分类体系**: DevSquad 7 角色按领域细分（架构→微服务/数据库/安全架构；安全→OWASP/合规/加密）
5. **Progressive Disclosure**: SKILL.md 实现 3 级加载（Quick Start / Implementation / Deep Dive）
6. **CLI 验证工具**: `python -m opc_manager.skill_validator lint` 检查格式 + 合规

### P2: 长期演进（高成本高价值）

7. **框架映射**: 将 DevSquad 技能映射到 OWASP / NIST / CIS 等行业标准
8. **技能市场**: 参考 Anthropic-Cybersecurity-Skills 的 `npx skills add` 安装机制
9. **版本 diff 工具**: 检测技能变更的行为回归

---

## 7. 与 OPC-Agents 硬约束的对齐

| OPC-Agents 硬约束 | Ponytail 对应 | agentskills.io 对应 |
|-------------------|---------------|---------------------|
| 密码存储必须用 PBKDF2 | 硬约束：安全性 | allowed-tools 限制 |
| prompt injection 必须阻断 | 硬约束：信任边界输入校验 | compatibility 声明 |
| 哈希比较必须用 hmac.compare_digest | 硬约束：安全性 | — |
| ConsensusEngine 前置介入 | — | Progressive Disclosure 决策 |
| 发布前必须完成 E2E 测试 | 硬约束：硬件校准 | 验收标准 |

**结论**: OPC-Agents 的硬约束体系已与 Ponytail 的"永不削减"理念高度一致，需做的是**文档化显式声明**，而非新增约束。

---

## 8. 参考资料

- [agentskills.io 规范](https://raw.githubusercontent.com/agentskills/agentskills/main/docs/specification.mdx)
- [Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills)
- [Ponytail 深度拆解](https://juejin.cn/post/7654760228148330531)
- [design.md 官方仓库](https://github.com/google-labs-code/design.md)
- [DESIGN.md 框架解析](https://www.mejba.me/blog/design-md-ai-design-framework)
- [SkillX: 自动构建技能知识库](https://arxiv.org/pdf/2604.04804v2)
