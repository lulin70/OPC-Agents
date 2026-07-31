# OPC-Agents 技术债追踪

> **活文档原则**：本文件必须随版本演进持续更新，禁止停留在过期状态。
> **来源**：[ASSESSMENT_v0.5.6.md](assessments/ASSESSMENT_v0.5.6.md) 7 维度评估
> **最后更新**：v0.5.8（2026-07-30）

---

## 一、状态总览

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 已解决 | 4 | v0.5.7 修复 |
| 🔄 进行中 | 3 | v0.5.8 推进 |
| ⏳ 待处理 | 5 | v0.6.0+ 规划 |
| **合计** | **12** | |

---

## 二、技术债清单

### ✅ 已解决（v0.5.7）

#### TD-001: MCPClient ghost feature（P0）

- **状态**：✅ 已解决（v0.5.7）
- **来源**：ASSESSMENT_v0.5.6 P0-1/P0-2
- **问题**：`opc_manager/skill_marketplace_external.py:410` 引用 `mcp_protocol.py` 中不存在的 `MCPClient` 类，通过 `# type: ignore[attr-defined]` + `except ImportError` 双重掩盖，功能从未工作过
- **修复**：删除 dead code 块，`discovered_tools` 初始化为空列表，保留外部接口可用，添加 TODO 注释指向本文件
- **依据**：project_memory 教训"name-defined/F821 的 type:ignore 绝不能保留必须修复"，[attr-defined] 同样隐藏运行时 bug
- **验证**：ruff 0 errors + mypy 0 errors + 相关测试通过

#### TD-002: 依赖版本漂移（P0）

- **状态**：✅ 已解决（v0.5.7）
- **来源**：ASSESSMENT_v0.5.6 P0-3/P0-4/P0-5
- **问题**：
  - ruff: pre-commit `v0.15.21` vs requirements-dev `>=0.15.22`
  - black: pre-commit `26.5.1` / requirements-dev `>=26.3.1` / pyproject.toml `>=25.0.0`（三处不一致）
  - pytest-asyncio: 注释 `<1.4.0` vs 代码 `<1.5.0`，pyproject.toml 无上界
  - mypy: pyproject.toml `>=1.8.0` vs requirements-dev `>=1.11.2,<1.12`
- **修复**：
  - ruff: pre-commit `v0.15.21` → `v0.15.22`
  - black: pyproject.toml `>=25.0.0` → `>=26.5.1`
  - pytest-asyncio: 注释统一为 `<1.5.0`，pyproject.toml 添加 `<1.5.0` 上界
  - mypy: pyproject.toml `>=1.8.0` → `>=1.11.2,<1.12`
- **依据**：project_memory 教训"pre-commit 版本漂移是 CI 失败根因"
- **验证**：三处版本一致（pre-commit / requirements-dev / pyproject.toml）

#### TD-003: Dockerfile 无阿里云镜像源（P1，硬约束违规）

- **状态**：✅ 已解决（v0.5.7）
- **来源**：ASSESSMENT_v0.5.6 P1-2
- **问题**：Dockerfile `apt-get update` 前未配置阿里云镜像源，服务器无法访问 `deb.debian.org`（Fastly CDN 被墙）会导致卡死
- **修复**：在 `apt-get update` 前添加 `sed` 替换 `deb.debian.org` → `mirrors.aliyun.com`，兼容 debian.sources 和 sources.list 两种格式
- **依据**：project_memory 硬约束"服务器无法访问 deb.debian.org 需阿里云镜像源"
- **验证**：Dockerfile 包含 sed 命令

#### TD-004: 无活跃 TECH_DEBT.md（P1）

- **状态**：✅ 已解决（v0.5.7）
- **来源**：ASSESSMENT_v0.5.6 P1-9
- **问题**：v0.3.1 到 v0.5.6 跨越 3 版本无活跃技术债追踪，仅 archive 中有过期版本
- **修复**：创建本文件，登记所有评估发现的技术债
- **依据**：project_memory 教训"文档滞后根因：将文档视为一次性交付物而非活文档"
- **验证**：本文件存在且内容完整

---

### 🔄 进行中（v0.5.8）

#### TD-005: E2E 13 个失败（P1）

- **状态**：🔄 进行中（v0.5.8）
- **来源**：ASSESSMENT_v0.5.6 P1-1
- **问题**：E2E 测试 13 个真实失败
  - 7 asyncio 事件循环冲突（`asyncio.run()` in worker threads）
  - 3 morandi 主题缺陷
  - 1 过期断言（主题数 5→7）
  - 2 a11y 对比度不达标（Demo 横幅白底白字）
- **修复计划**：
  - asyncio 冲突：重构 `asyncio.run()` → `new_event_loop() + run_until_complete()`
  - morandi 主题：修复主题应用逻辑
  - 过期断言：更新主题数断言
  - a11y 对比度：修复 Demo 横幅配色
- **依据**：project_memory 教训"后端 API 测试通过不等于用户能用"

#### TD-006: 文档过期（P1）

- **状态**：🔄 进行中（v0.5.8）
- **来源**：ASSESSMENT_v0.5.6 P1-3/P1-4/P1-5/P1-6
- **问题**：
  - 模块数 99 过期（实际顶层 119 / 总计 136）
  - 测试数 scope 不一致（README 4596 vs PROJECT_STATUS 4390）
  - HARD_CONSTRAINTS.md 仍停留 v0.3.4（落后 6 版本）
  - DIRECTORY_STRUCTURE.md 滞后 24.8%（109→136 文件）
- **修复计划**：v0.5.7 同步更新所有过期文档
- **依据**：project_memory 教训"文档滞后根因：活文档原则"

#### TD-007: venv 工具版本漂移（P1）

- **状态**：🔄 进行中（v0.5.8）
- **来源**：ASSESSMENT_v0.5.6 P1-10
- **问题**：本地 venv 工具版本均不符合 requirements-dev.txt
  - black 24.8.0（应 >=26.3.1）
  - ruff 0.15.21（应 >=0.15.22）
  - mypy 2.2.0（应 >=1.11.2,<1.12）
- **修复计划**：v0.5.7 升级 venv 工具版本
- **依据**：本地测试结果可能无法复现 CI 行为

---

### ⏳ 待处理（v0.6.0+ 规划）

#### TD-008: metrics_collector.py 拆分（P2）

- **状态**：⏳ 待处理（v0.6.0+）
- **来源**：ASSESSMENT_v0.5.6 P2-6
- **问题**：`opc_manager/metrics_collector.py` 1251 行，体量较大
- **建议**：拆分 DB 层与业务层
- **依据**：SRP 原则（非行数阈值，但单文件超 1000 行建议评估拆分必要性）

#### TD-009: test_version.py 守护不全（P2）

- **状态**：⏳ 待处理（v0.6.0+）
- **来源**：ASSESSMENT_v0.5.6 P2-2
- **问题**：test_version.py 仅覆盖 3 处版本号，不覆盖 README/Dockerfile 等 14 处
- **建议**：扩展测试覆盖所有版本号位置

#### TD-010: 过期 TODO(v0.3.0)（P2）

- **状态**：⏳ 待处理（v0.6.0+）
- **来源**：ASSESSMENT_v0.5.6 P2-3
- **问题**：`frontend/page_modules/_marketplace_page.py:235` 过期 TODO(v0.3.0)
- **建议**：处理或删除

#### TD-011: 裸 type:ignore（P2）

- **状态**：⏳ 待处理（v0.6.0+）
- **来源**：ASSESSMENT_v0.5.6 P2-4
- **问题**：`opc_manager/memory_bridge.py:35` 裸 `type: ignore`（无错误码）
- **建议**：添加具体错误码或移除

#### TD-012: agent_loop.py 返回类型不一致（P2）

- **状态**：⏳ 待处理（v0.6.0+）
- **来源**：ASSESSMENT_v0.5.6 P2-5
- **问题**：`opc_manager/agent_loop.py:457-461` 3 处返回类型不一致
- **建议**：统一返回类型

---

## 三、版本演进记录

| 版本 | 新增 TD | 解决 TD | 说明 |
|------|---------|---------|------|
| v0.5.7 | TD-001~012 | TD-001~004 | 7 维度评估发现 12 项，v0.5.7 解决 4 项 P0/P1 |
| v0.6.0+ | — | TD-005~012 | 计划解决剩余 8 项 |

---

**维护原则**：
1. 每次版本发布必须更新本文件
2. 新发现技术债必须立即登记
3. 已解决技术债保留记录，标记解决版本
4. 优先级：P0 阻塞 > P1 重要 > P2 次要
