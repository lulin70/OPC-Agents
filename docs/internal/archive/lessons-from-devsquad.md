# OPC-Agents 从 DevSquad 学到的经验

> **版本**: v1.0 | **日期**: 2026-05-02 | **作者**: OPC-Agents 项目组
>
> 本文档从产品经理、架构师、安全专家、测试专家四个视角，系统梳理 DevSquad V3.4.0 的设计精华，以及 OPC-Agents 可以借鉴的具体改进方向。

---

## 一、产品经理视角

### 1.1 工作流生命周期管理

**DevSquad 做法**：定义了 11 阶段生命周期模板（P1需求分析 → P2架构设计 → ... → P11运维保障），每个阶段有明确的角色、依赖、门禁条件和产出物。5种预定义模板（full/backend/frontend/internal_tool/minimal）适配不同场景。

**OPC-Agents 现状**：任务执行是单次请求-响应模式，没有阶段化流程。用户提交需求后直接走"意图分类→搜索→生成→保存"一条线。

**可借鉴**：
- 引入**任务阶段模板**：将"帮我写Q2营销方案"拆分为"需求确认→数据收集→方案生成→审核交付"4阶段
- 每阶段设置**门禁条件**：如数据收集阶段必须至少获得3条有效搜索结果才能进入生成阶段
- 用户可选择**精简模式**（当前行为）或**完整模式**（带阶段反馈和确认点）

### 1.2 需求变更机制

**DevSquad 做法**：`submit_change_request()` 支持运行中的工作流提交需求变更，自动分析受影响阶段并提供回滚点。

**OPC-Agents 现状**：任务一旦提交无法修改，用户只能取消重做。

**可借鉴**：
- 在任务执行过程中允许用户追加指令（如"方案里加上竞品分析"）
- 保留检查点，变更后从受影响阶段重新执行而非从头开始

### 1.3 交付物质量门禁

**DevSquad 做法**：每个工作流阶段都有 `gate_condition`（如"架构通过加权共识>=70%"、"覆盖率>=80%"），不满足则不进入下一阶段。

**OPC-Agents 现状**：生成的内容没有质量门禁，占位符清理后直接交付。

**可借鉴**：
- 设置**交付物质量门禁**：如"零占位符"、"字数>=500"、"包含至少2个数据来源"
- 不满足门禁时自动重试或降级到模板模式，而非交付低质量内容

### 1.4 多角色协作产出结构化报告

**DevSquad 做法**：7个角色并行分析同一任务，通过共识机制合并结论，最终输出包含"发现→决策→建议→警告"的结构化报告。

**OPC-Agents 现状**：单线程生成，输出是单一 LLM 响应。

**可借鉴**：
- 对复杂任务启用**多视角生成**：同时从"市场视角"和"技术视角"生成方案，合并后交付
- 报告结构化：每个交付物包含"核心结论→详细分析→数据来源→风险提示"

---

## 二、架构师视角

### 2.1 Protocol 接口 + Null Provider 降级模式

**DevSquad 做法**：定义了4个 Protocol 接口（CacheProvider/RetryProvider/MonitorProvider/MemoryProvider），每个接口都有 NullProvider 空实现。任何组件不可用时系统优雅降级，不会崩溃。

```python
# DevSquad 的降级模式
class NullCacheProvider(CacheProvider):
    def is_available(self) -> bool: return False
    def get(self, key): return None
    def set(self, key, value, ttl): pass
```

**OPC-Agents 现状**：LLM 不可用时降级到模板模式，但其他组件（如搜索、加密存储、监控）不可用时缺乏统一降级策略。

**可借鉴**：
- 为每个外部依赖定义 Protocol 接口 + NullProvider
- 搜索不可用 → 降级到知识库兜底（已有）
- 加密存储不可用 → 降级到 .env 明文（已有，但需统一模式）
- 监控不可用 → 降级到日志记录
- 统一降级日志格式：`[ComponentName] Not available, falling back to [FallbackName]`

### 2.2 Scratchpad 共享黑板模式

**DevSquad 做法**：Scratchpad 实现了分区的共享黑板，支持 FINDING/DECISION/CONFLICT/QUESTION/SUGGESTION/WARNING 6种条目类型，分区协议（READONLY/WRITE/SHARED/PRIVATE）控制访问权限。

**OPC-Agents 现状**：`SessionContextManager` 只存储对话历史，没有结构化的发现/决策/冲突记录。

**可借鉴**：
- 在 `SessionContextManager` 中引入**结构化上下文**：除了对话历史，还记录"已确认的决策"、"待解决的问题"、"已发现的风险"
- 为多轮对话提供**决策追踪**：用户在对话中做出的选择被记录为 DECISION 条目，后续生成时自动参考

### 2.3 检查点与交接文档

**DevSquad 做法**：CheckpointManager 在工作流执行中定期保存检查点（含 SHA256 完整性校验），支持从检查点恢复。HandoffDocument 定义了 Agent 间交接的标准格式。

**OPC-Agents 现状**：AsyncTaskExecutor 有基本的状态持久化（JSON），但没有完整性校验和交接文档。

**可借鉴**：
- 为检查点文件添加**SHA256 完整性校验**（当前只有 JSON dump）
- 定义**任务交接文档格式**：当任务需要在不同模块间传递时，包含"已完成的工作→当前状态→下一步→待解决问题"
- 支持从检查点恢复后**跳过已完成阶段**

### 2.4 配置层次化与 SSOT

**DevSquad 做法**：
- 版本号 SSOT：`_version.py` 是唯一版本来源，CLI/MCP/pyproject.toml 都引用它
- 配置层次：项目级 YAML → LLM 优化 YAML → 环境变量覆盖
- 敏感信息（API Key）仅通过环境变量传入，无 CLI 参数暴露

**OPC-Agents 现状**：
- 版本号分散在 `version.py`、`pyproject.toml`、README 中，有不一致风险
- 配置只有环境变量一层，没有项目级配置文件
- API Key 通过 .env 文件传入（已支持加密存储）

**可借鉴**：
- 引入 `opc-agents.yaml` 项目级配置文件（类似 `.devsquad.yaml`）
- 版本号严格 SSOT：`version.py` 是唯一来源，其他地方全部引用
- 配置优先级：YAML 配置 < 环境变量 < 加密存储 < CLI 参数

### 2.5 批处理调度器

**DevSquad 做法**：BatchScheduler 管理任务批次，检查批次间依赖，支持并行/串行执行模式。

**OPC-Agents 现状**：AsyncTaskExecutor 支持并发执行，但没有批次概念和依赖管理。

**可借鉴**：
- 引入**任务批次**：用户一次提交多个相关任务时（如"帮我分析3个竞品"），自动拆分为批次
- 批次内任务可并行执行，批次间有依赖关系
- 批次完成后生成**汇总报告**

---

## 三、安全专家视角

### 3.1 四级权限守卫

**DevSquad 做法**：PermissionGuard 实现4级权限（DEFAULT/REVIEW/APPROVE/ADMIN），30条默认规则，5维风险评分（数据敏感性/操作不可逆性/外部影响范围/权限提升风险/合规要求）。

**OPC-Agents 现状**：没有权限控制，任何用户都能执行任何操作（包括删除成果物、修改配置）。

**可借鉴**：
- 为危险操作添加**权限检查**：
  - 删除成果物 → 需确认（REVIEW 级）
  - 修改 API Key → 需二次验证（APPROVE 级）
  - 重置所有数据 → 需管理员确认（ADMIN 级）
- 风险评分用于决定是否自动执行或需要用户确认

### 3.2 输入验证 21+ 攻击模式

**DevSquad 做法**：InputValidator 检测 21+ 种攻击模式（SQL注入/XSS/命令注入/路径遍历/Prompt注入/模板注入等），支持自定义规则扩展。

**OPC-Agents 现状**：InputValidator 覆盖了基本的 Prompt 注入和 XSS 防护，但攻击模式库较小。

**可借鉴**：
- 扩展输入验证的**攻击模式库**：添加模板注入（SSTI）、LDAP注入、XML注入等检测
- 支持**自定义规则扩展**：项目级 YAML 文件定义额外的验证规则
- 验证结果包含**风险等级**：低风险放行、中风险警告、高风险拦截

### 3.3 规则注入安全

**DevSquad 做法**：EnhancedWorker 对注入规则进行 Unicode NFKC 标准化 + 长度限制 + InputValidator 双层防护，防止通过规则注入执行恶意代码。

**OPC-Agents 现状**：persona_manager 从 YAML 加载角色配置，但没有对配置内容做安全校验。

**可借鉴**：
- 对 YAML 配置文件内容做**安全校验**：检测是否包含代码执行指令、敏感路径引用等
- 配置加载后进行**NFKC 标准化**：防止 Unicode 欺骗攻击
- 对配置值设置**长度限制**：防止超长输入导致缓冲区问题

### 3.4 安全否决权

**DevSquad 做法**：安全角色拥有否决权（veto），一票否决触发升级。`.devsquad.yaml` 配置 `veto_allowed_roles: [security, architect]`。

**OPC-Agents 现状**：没有安全否决机制，任何操作只要格式正确就会执行。

**可借鉴**：
- 为高风险操作添加**安全否决点**：
  - 生成内容包含敏感信息（如 API Key、密码）→ 拦截并警告
  - 文件操作涉及系统目录 → 拦截
  - LLM 响应包含可执行代码 → 标记并提示用户确认

### 3.5 审计日志

**DevSquad 做法**：PermissionGuard 维护审计日志，记录所有权限检查结果。

**OPC-Agents 现状**：只有基本的运行日志，没有审计追踪。

**可借鉴**：
- 为关键操作添加**审计日志**：
  - API Key 的设置/读取/删除
  - 成果物的创建/删除/下载
  - 配置的修改
- 审计日志包含：时间戳、操作类型、操作者、结果、风险等级

---

## 四、测试专家视角

### 4.1 契约测试

**DevSquad 做法**：`tests/contract/test_memory_provider_contract.py`（42个测试）验证所有 MemoryProvider 实现都遵守 Protocol 接口契约。

**OPC-Agents 现状**：只有功能测试，没有契约测试。如果新增 LLM 后端，无法自动验证它是否符合接口规范。

**可借鉴**：
- 为所有 Protocol 接口编写**契约测试**：
  - LLMBackend 契约：所有后端必须支持 `generate()` 和 `generate_stream()`
  - CacheProvider 契约：所有缓存实现必须支持 `get()`/`set()`/`invalidate()`
  - SecureStorage 契约：所有存储实现必须支持 `set_key()`/`get_key()`/`load_to_env()`
- 新增实现时自动运行契约测试，确保接口合规

### 4.2 测试分层与标记

**DevSquad 做法**：测试分为单元测试、角色映射测试、上游集成测试、MCP适配器测试、E2E测试、协议测试、契约测试、安全测试等多个层次。

**OPC-Agents 现状**：测试主要分为快速单元测试（mock）和真实 E2E 测试（需 API Key），层次较少。

**可借鉴**：
- 引入**pytest 标记**分层：
  ```python
  @pytest.mark.unit        # 纯单元测试，无外部依赖
  @pytest.mark.integration # 集成测试，需要 mock 外部服务
  @pytest.mark.e2e         # 端到端测试，需要真实 API Key
  @pytest.mark.security    # 安全测试
  @pytest.mark.contract    # 契约测试
  @pytest.mark.slow        # 慢速测试（>1s）
  ```
- CI 中分层执行：unit → integration → contract → security → e2e
- 快速反馈：开发者本地只跑 unit + integration（<10s）

### 4.3 安全测试专项

**DevSquad 做法**：`tests/test_rule_injection_security.py`（18个测试）专门测试规则注入的安全性。

**OPC-Agents 现状**：安全测试散落在各测试文件中，没有专项。

**可借鉴**：
- 创建 `tests/test_security.py` 安全测试专项：
  - Prompt 注入攻击测试（10+种变体）
  - XSS 攻击测试（HTML/JS/事件处理器）
  - 路径遍历攻击测试
  - API Key 泄露测试（日志/错误消息/前端显示）
  - 加密存储安全测试（密钥派生/文件权限/原子写入）
  - 输入验证绕过测试

### 4.4 内嵌测试模式

**DevSquad 做法**：每个核心模块文件旁都有 `*_test.py` 内嵌测试文件（如 `scratchpad.py` + `scratchpad_test.py`），共15个内嵌测试文件。

**OPC-Agents 现状**：所有测试集中在 `tests/` 目录。

**可借鉴**：
- 考虑在核心模块旁添加内嵌测试，方便开发时快速验证
- 但保持 `tests/` 目录作为 CI 执行的统一入口
- 两种模式并存：内嵌测试用于开发调试，集中测试用于 CI

### 4.5 反合理化测试

**DevSquad 做法**：AntiRationalizationEngine 注入"借口-反驳"对照表（50条），防止 Worker 跳过关键步骤。

**OPC-Agents 现状**：没有类似机制，LLM 可能跳过重要步骤（如"因为时间有限，省略了竞品分析部分"）。

**可借鉴**：
- 在 LLM prompt 中注入**反合理化指令**：
  - "不要因为时间有限而省略关键分析"
  - "不要用'建议后续深入研究'来回避给出具体建议"
  - "不要因为数据不足就编造数据，应明确标注数据来源缺失"
- 对 LLM 输出做**反合理化检查**：检测"省略"、"后续"、"暂不"等回避性词汇

---

## 五、综合改进路线图

基于以上分析，按优先级排列 OPC-Agents 的改进方向：

### Sprint 1（v0.1.5 — 当前版本）

| 编号 | 改进项 | 来源视角 | 优先级 | 状态 |
|------|--------|---------|--------|------|
| S1-01 | Protocol 接口 + NullProvider 降级模式 | 架构师 | P0 | ✅ 部分实现（SecureKeyStore 有降级） |
| S1-02 | 扩展输入验证攻击模式库 | 安全专家 | P0 | 🔲 待实现 |
| S1-03 | 安全测试专项 | 测试专家 | P1 | 🔲 待实现 |
| S1-04 | pytest 标记分层 | 测试专家 | P1 | 🔲 待实现 |
| S1-05 | 版本号 SSOT | 架构师 | P1 | 🔲 待实现 |

### Sprint 2（v0.2.0）

| 编号 | 改进项 | 来源视角 | 优先级 |
|------|--------|---------|--------|
| S2-01 | 任务阶段模板 + 门禁条件 | 产品经理 | P0 |
| S2-02 | 四级权限守卫 | 安全专家 | P0 |
| S2-03 | 契约测试 | 测试专家 | P1 |
| S2-04 | 项目级配置文件（opc-agents.yaml） | 架构师 | P1 |
| S2-05 | 审计日志 | 安全专家 | P1 |
| S2-06 | 反合理化指令注入 | 测试专家 | P2 |

### Sprint 3（v0.2.2）

| 编号 | 改进项 | 来源视角 | 优先级 |
|------|--------|---------|--------|
| S3-01 | 需求变更机制 | 产品经理 | P1 |
| S3-02 | 结构化上下文（Scratchpad 模式） | 架构师 | P1 |
| S3-03 | 检查点 SHA256 完整性校验 | 架构师 | P1 |
| S3-04 | 安否决权机制 | 安全专家 | P2 |
| S3-05 | 多视角生成 + 共识合并 | 产品经理 | P2 |
| S3-06 | 批处理调度器 | 架构师 | P2 |

---

## 六、关键设计对比

| 维度 | DevSquad | OPC-Agents 现状 | OPC-Agents 目标 |
|------|----------|-----------------|-----------------|
| **协作模式** | 7角色并行 + 共识 | 单线程生成 | 多视角生成 + 质量门禁 |
| **降级策略** | NullProvider 模式 | 部分降级 | 统一 Protocol + NullProvider |
| **权限控制** | 4级权限 + 风险评分 | 无 | 危险操作需确认 |
| **输入验证** | 21+攻击模式 | 基本防护 | 扩展攻击模式库 |
| **测试分层** | 7层（单元→契约→安全→E2E） | 2层（单元→E2E） | 5层（单元→集成→契约→安全→E2E） |
| **配置管理** | YAML + 环境变量 + SSOT | 环境变量 + .env | YAML + 环境变量 + 加密存储 + SSOT |
| **状态持久化** | Checkpoint + SHA256 + Handoff | JSON dump | Checkpoint + SHA256 + 交接文档 |
| **冲突解决** | 共识投票 + 否决权 + 升级 | 无 | 质量门禁 + 安全否决 |
| **审计追踪** | PermissionGuard 审计日志 | 运行日志 | 操作审计 + 安全审计 |

---

## 七、核心收获

### 7.1 最重要的3个教训

1. **NullProvider 模式是系统韧性的基石**：DevSquad 的每个外部依赖都有空实现降级，确保系统永远不会因为某个组件不可用而崩溃。OPC-Agents 应该为所有外部依赖（LLM/搜索/加密/监控）统一实现这个模式。

2. **门禁条件是质量保障的核心**：DevSquad 的每个工作流阶段都有明确的门禁条件，不满足就不进入下一阶段。OPC-Agents 应该为交付物设置质量门禁（零占位符、最低字数、来源数量），不满足就重试或降级。

3. **契约测试是接口演进的保障**：DevSquad 的契约测试确保所有实现都遵守 Protocol 接口。OPC-Agents 正在快速增加 LLM 后端（MOKA/GLM/OpenAI/Ollama），契约测试可以防止接口不一致。

### 7.2 最值得警惕的3个风险

1. **不要照搬 DevSquad 的所有设计**：DevSquad 是 AI 编排框架，OPC-Agents 是任务执行系统，两者的复杂度需求不同。7角色共识机制对 OPC-Agents 来说过重，多视角生成 + 质量门禁就足够。

2. **配置爆炸风险**：DevSquad 的 `.devsquad.yaml` 有7大子系统、数十个配置项。OPC-Agents 应该保持配置简洁，只引入真正需要的配置（如质量门禁阈值、权限级别）。

3. **测试维护成本**：DevSquad 有 1030+ 个测试函数，维护成本很高。OPC-Agents 应该聚焦关键路径的测试，避免为了覆盖率而写测试。

### 7.3 一句话总结

> **DevSquad 教会我们的不是"怎么做"，而是"怎么想"：用 Protocol 定义边界、用门禁保障质量、用降级保证韧性、用契约守护演进。**
