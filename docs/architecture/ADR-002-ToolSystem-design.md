# ADR-002: ToolSystem — 工具注册与安全执行框架

**Status**: Accepted
**Date**: 2026-07-11
**Supersedes**: N/A
**Related**: [PROJECT_STATUS.md](../PROJECT_STATUS.md), [SECURITY_DESIGN.md](../internal/SECURITY_DESIGN.md)

---

## Context

OPC-Agents 需要一个工具系统来执行文件操作、命令执行等系统能力。这些工具需要：
- 统一的注册和发现机制
- 基于权限的访问控制（不同用户/角色可使用不同工具）
- 安全的执行沙箱（防止命令注入、路径穿越等安全风险）
- 支持同步和异步调用

**问题陈述**：
- Agent 需要调用多种工具（文件读写、命令执行、网络请求等）
- 不同场景下可用工具集不同（如 demo 模式禁用文件写入）
- 工具执行必须安全（用户输入不可直接作为命令执行）
- 工具数量会持续增长，需要可扩展的注册机制

**约束**：
- 安全性优先：所有工具执行必须经过权限检查和输入验证
- 性能敏感：工具调用不能引入显著开销
- 向后兼容：新增工具不能影响已有工具的行为

## Decision

**采用基于注册表模式的 ToolSystem，配合类别索引和权限分级。**

### 架构设计

```
ToolSystem
├── tools: Dict[str, Tool]           # 工具注册表（tool_id → Tool）
├── category_index: Dict[str, List]  # 类别索引（category → [tool_id, ...]）
├── permission_index: Dict[str, List] # 权限索引（permission → [tool_id, ...]）
└── _register_builtin_tools()        # 内置工具自动注册
```

**文件**: `opc_manager/tool_system.py` (L168-L753)

### 关键设计决策

1. **注册表模式**：所有工具通过 `register_tool()` 注册到统一字典，支持运行时动态注册
2. **类别索引**：工具按 `ToolCategory`（FILE / COMMAND / NETWORK / DATA / SYSTEM）分类，支持按类别批量查询
3. **权限分级**：工具按 `PermissionLevel`（USER / ADMIN / SYSTEM）分级，`check_permission()` 在执行前验证
4. **安全执行**：
   - 文件操作限制在工作目录内（路径穿越防护）
   - 命令执行使用参数列表而非字符串拼接（命令注入防护）
   - 网络请求限制白名单域名
5. **内置工具自动注册**：构造函数 `register_builtins=True` 时自动注册 file_read/file_write 等内置工具

### 工具数据模型

```python
@dataclass
class Tool:
    tool_id: str           # 唯一标识
    name: str              # 显示名称
    description: str       # 工具描述
    category: ToolCategory # 类别
    parameters: List[ToolParameter]  # 参数 schema
    execute: Callable      # 执行函数
    permission: PermissionLevel       # 所需权限
```

### 权限模型

```
PermissionLevel.USER    → 常规工具（文件读取、数据查询）
PermissionLevel.ADMIN   → 管理工具（文件写入、命令执行）
PermissionLevel.SYSTEM  → 系统工具（配置修改、服务管理）
```

权限检查在 `execute_tool()` 入口处执行，未通过则抛出 PermissionError，不执行任何操作。

## Consequences

### 正面影响

- **统一管理**：所有工具通过注册表统一管理，新增工具只需注册不需修改框架
- **安全屏障**：权限分级 + 输入验证 + 路径限制三层防护
- **可发现性**：类别索引支持按类别枚举工具，便于 UI 展示和 Agent 选择
- **可测试性**：工具注册表可在测试中替换为 mock 工具，不影响生产代码

### 负面影响

- **单文件膨胀风险**：所有工具定义集中在一个文件中（753 行），需关注 God Class 风险
- **同步阻塞**：当前工具执行为同步模式，长时间运行的工具会阻塞调用线程
- **权限粒度固定**：三级权限可能不够灵活，某些工具需要更细粒度的权限控制

### 风险缓解

- Phase 3 计划将 `tool_system.py` 拆分为 tool_registry / tool_audit / tool_handlers_fs / tool_handlers_smtp（见 PROJECT_STATUS.md Phase 3）
- 异步执行可通过 `asyncio.to_thread()` 包装同步工具，无需重写工具
- 权限粒度可通过在 Tool 上添加 `required_scopes: List[str]` 扩展

## Alternatives Considered

### 方案 A: 插件系统（已否决）

使用动态插件加载机制（如 setuptools entry_points）实现工具注册。

**否决原因**：
- 插件加载增加启动复杂度
- 插件沙箱安全风险高（第三方代码直接运行）
- 当前工具数量有限（<20），注册表模式已足够

### 方案 B: MCP (Model Context Protocol) 工具（部分采用）

通过 MCP 协议从外部服务器获取工具能力。

**状态**：部分采用。`mcp_transport.py` 已实现 MCP 客户端，用于连接外部 MCP 服务器。ToolSystem 作为内部工具的统一管理器，与 MCP 外部工具互补。

### 方案 C: 函数即工具（已否决）

直接将 Python 函数作为工具，不使用 Tool 数据类包装。

**否决原因**：
- 无法统一描述参数 schema
- 无法在 UI 中展示工具列表和参数说明
- 权限检查需要每个函数手动实现，违反 DRY 原则
