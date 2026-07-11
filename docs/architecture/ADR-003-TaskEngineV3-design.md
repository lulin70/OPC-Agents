# ADR-003: TaskEngineV3 — Mixin 模式 + 单例 + 懒初始化

**Status**: Accepted
**Date**: 2026-07-11
**Supersedes**: TaskEngineV2 (implicit)
**Related**: [PARALLEL_SAGES_DESIGN.md](PARALLEL_SAGES_DESIGN.md), [PROJECT_STATUS.md](../PROJECT_STATUS.md)

---

## Context

TaskEngine 是 OPC-Agents 的核心执行引擎，负责从用户输入到任务结果的全链路处理。随着功能增长，TaskEngineV2 膨胀至 1853 行，承担了输入验证、意图识别、搜索调度、内容生成、场景编排、并行执行等多重职责，成为典型的 God Class。

**问题陈述**：
- TaskEngineV2 单文件 1853 行，修改任何功能都需要在巨大文件中定位代码
- 内容生成、搜索、执行器、并行处理四个职责高度耦合，难以独立测试
- 外部依赖（WebSearch、ScenarioEngine）在构造时初始化，导致启动慢且依赖失败时整体不可用
- 多个模块共享同一个引擎实例，需要线程安全

**约束**：
- 公共 API 100% 向后兼容（53+ 导入站点不能修改）
- 线程安全（多线程并发调用 execute()）
- 启动时间 <5s（不能在启动时加载所有外部依赖）
- 遵循 Simplicity First 原则，不引入过度抽象

## Decision

**采用 Mixin 组合模式拆分 TaskEngineV3，配合单例模式和懒初始化。**

### 架构设计

```
TaskEngineV3 (Facade + Singleton)
├── ContentGenerationMixin    # 内容生成（LLM + 模板 + RAG）
├── TaskEngineSearchMixin     # 搜索调度（WebSearch + 缓存）
├── TaskEngineExecutorsMixin  # 场景执行器（9 种场景编排）
└── TaskEngineParallelMixin   # 并行处理（asyncio.gather）

Lifecycle:
  __init__() → 不加载外部依赖，仅初始化空引用
  _ensure_initialized() → 首次 execute() 时懒加载 WebSearch + ScenarioEngine
  线程安全：_init_lock (class-level Lock) + _task_results_lock (instance-level Lock)
```

**文件**: `opc_manager/task_engine_v3.py` (L67-L500, Facade)

### 关键设计决策

1. **Mixin 组合而非继承层级**：
   - 4 个 Mixin 类各自独立，职责单一
   - TaskEngineV3 通过多继承组合所有能力
   - 每个 Mixin 可独立单元测试（创建子类实例）
   - 避免深层继承树的脆弱基类问题

2. **单例模式 + 模块级实例**：
   - 文件底部创建模块级 `task_engine_v3` 实例
   - 所有模块通过 `from opc_manager.task_engine_v3 import task_engine_v3` 获取
   - 避免重复实例化导致的状态不一致

3. **懒初始化**：
   - `__init__()` 仅设置 `_initialized = False` 和空引用
   - `_ensure_initialized()` 在首次 `execute()` 时加载外部依赖
   - 使用类级 `threading.Lock()` + double-checked locking 确保线程安全
   - 外部依赖加载失败时优雅降级（WebSearch 不可用则跳过搜索步骤）

4. **错误处理边界**：
   - `execute()` 顶层 try/except 捕获所有异常，包装为 `TaskResult(success=False)`
   - 外部依赖失败不崩溃，降级执行（无搜索结果时直接走内容生成）

### Mixin 职责划分

| Mixin | 职责 | 独立测试 |
|-------|------|----------|
| ContentGenerationMixin | LLM 调用 / 模板填充 / RAG 混合模式 | ✅ 可 mock LLM |
| TaskEngineSearchMixin | WebSearch 调用 / 搜索缓存 / 结果去重 | ✅ 可 mock WebSearch |
| TaskEngineExecutorsMixin | 9 种场景编排 / 状态机管理 | ✅ 可 mock ScenarioEngine |
| TaskEngineParallelMixin | asyncio.gather 并行 / 超时控制 | ✅ 可 mock 并行任务 |

## Consequences

### 正面影响

- **关注点分离**：4 个 Mixin 各自独立，修改内容生成不影响搜索逻辑
- **可测试性**：每个 Mixin 可独立单元测试，无需启动完整引擎
- **启动快**：懒初始化避免启动时加载所有依赖，首屏时间 <5s
- **线程安全**：double-checked locking 确保多线程安全，_task_results_lock 保护状态
- **向后兼容**：公共 API 100% 保持，53+ 导入站点零修改

### 负面影响

- **Mixin 属性隐式声明**：Mixin 中使用的 `self.xxx` 属性需要 `# type: ignore[misc]` 注解
- **初始化顺序敏感**：Mixin 之间的依赖需在 `_ensure_initialized()` 中按顺序初始化
- **单例测试隔离**：模块级单例需要测试中重置 `_initialized` 标志或创建新实例

### 风险缓解

- TYPE_CHECKING block 声明 Mixin 跨模块属性类型（mypy 兼容）
- `_ensure_initialized()` 中每个外部依赖独立 try/except，一个失败不影响其他
- 测试中使用 `monkeypatch.setattr(engine, "_initialized", False)` 重置懒初始化标志

## Alternatives Considered

### 方案 A: 服务注入模式（已否决）

将 ContentGeneration/Search/Executors/Parallel 作为独立服务注入 TaskEngine 构造函数。

**否决原因**：
- 需要修改 53+ 导入站点的实例化代码
- 引入依赖注入框架增加复杂度，违反 Simplicity First
- Mixin 模式已实现关注点分离，且保持 API 兼容

### 方案 B: 依赖注入容器（已否决）

使用 DI 容器（如 dependency-injector）管理服务生命周期。

**否决原因**：
- 引入新依赖，增加包体积
- 配置复杂度高，对当前项目规模过度设计
- 单例 + 懒初始化已满足线程安全和性能需求

### 方案 C: God Class 保留 + 方法提取（已否决）

不拆分 God Class，仅提取方法到独立文件通过 `from ... import` 引入。

**否决原因**：
- 仍然是 God Class，只是文件拆分而非职责分离
- 无法独立测试提取的方法（仍需在 God Class 上下文中运行）
- v0.3.2 已尝试此方案（Phase 3 God Class 拆分），效果有限
