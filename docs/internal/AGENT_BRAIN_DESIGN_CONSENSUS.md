# OPC-Agents Agent Brain 架构设计 — 七角色共识文档

**日期**: 2026-05-07
**参与角色**: 架构师、产品经理、安全专家、测试专家、开发者、DevOps、UI设计师
**共识状态**: ✅ 已达成
**版本**: v2.0（基于PRD v3.6审核通过的15个需求更新）

---

## 📋 目录

1. [Agent Brain 核心职责 — 三贤者架构](#1-agent-brain-核心职责--三贤者架构)
2. [技能系统设计](#2-技能系统设计)
3. [工具调用框架](#3-工具调用框架)
4. [执行循环设计](#4-执行循环设计)
5. [安全架构设计（v2.0新增）](#5-安全架构设计v20新增)
6. [任务隔离与并发架构（v2.0新增）](#6-任务隔离与并发架构v20新增)
7. [资源生命周期管理架构（v2.0新增）](#7-资源生命周期管理架构v20新增)
8. [与现有代码衔接策略](#8-与现有代码衔接策略)
9. [分阶段实施路线图](#9-分阶段实施路线图)
10. [风险评估与应对](#10-风险评估与应对)
11. [角色分工与职责](#11-角色分工与职责)

---

## 1. Agent Brain 核心职责

### 1.1 三大核心能力

| 能力 | 描述 | 输入 | 输出 |
|------|------|------|------|
| **意图理解** | 理解用户自然语言输入，提取核心目标和约束 | 用户输入文本 | 结构化意图对象（目标、约束、上下文） |
| **任务规划** | 将目标分解为可执行的步骤序列 | 意图对象 | 步骤列表（每步包含：技能选择、工具调用、参数） |
| **反思能力** | 评估执行结果，决定是否重试或调整策略 | 执行结果 + 预期目标 | 反馈（继续/重试/调整/放弃） |

### 1.2 架构师观点

> **架构师**: Agent Brain 是整个系统的"大脑"，需要具备：
> - 自然语言到结构化任务的转换能力
> - 多步骤规划和资源分配能力
> - 执行监控和自我修正能力
> - 与技能系统和工具系统的标准接口

### 1.3 产品经理观点

> **产品经理**: 用户体验角度，Agent Brain 需要：
> - 能理解模糊的自然语言输入
> - 能自动规划，不需要用户指定步骤
> - 执行失败时能自动重试，减少人工干预
> - 提供清晰的执行进度反馈

---

## 2. 技能系统设计

### 2.1 技能抽象模型

```python
class Skill:
    """技能抽象定义"""
    id: str                    # 唯一标识
    name: str                  # 显示名称
    description: str           # 功能描述
    input_schema: Dict         # 输入参数规范
    output_schema: Dict        # 输出格式规范
    tools: List[str]           # 依赖的工具列表
    knowledge_base: str        # 关联知识库ID
    execute: Callable          # 执行函数
    
    # 技能元数据
    category: str              # 分类（分析/创作/操作等）
    version: str               # 版本号
    author: str                # 作者/维护者
    confidence: float          # 置信度评分
```

### 2.2 技能注册表设计

```python
class SkillRegistry:
    """技能注册与发现中心"""
    def register(self, skill: Skill):
        """注册新技能"""
        pass
    
    def find_by_intent(self, intent: str) -> List[Skill]:
        """根据意图匹配技能（支持模糊匹配）"""
        pass
    
    def find_by_category(self, category: str) -> List[Skill]:
        """按分类查找技能"""
        pass
    
    def get_skill(self, skill_id: str) -> Skill:
        """获取单个技能"""
        pass
```

### 2.3 技能组合机制

| 组合方式 | 描述 | 适用场景 |
|---------|------|---------|
| **顺序组合** | 技能按顺序执行，前一个输出作为后一个输入 | 流水线式任务 |
| **条件分支** | 根据条件选择不同技能执行 | 需要决策的任务 |
| **并行执行** | 多个技能同时执行，结果汇总 | 可并行的子任务 |
| **递归调用** | 技能内部调用其他技能 | 复杂嵌套任务 |

### 2.4 开发者观点

> **开发者**: 技能系统需要：
> - 支持热加载，无需重启即可添加新技能
> - 技能之间解耦，避免循环依赖
> - 提供技能模板，降低开发门槛
> - 支持版本管理和回滚

---

## 3. 工具调用框架

### 3.1 工具抽象层

```python
class Tool:
    """工具抽象定义"""
    id: str                    # 工具标识
    name: str                  # 显示名称
    description: str           # 功能描述
    parameters: List[Dict]     # 参数定义（名称、类型、必填）
    return_type: str           # 返回类型
    execute: Callable          # 执行函数
    
    # 安全相关
    requires_permission: bool  # 是否需要权限校验
    permission_level: str      # 权限级别
```

### 3.2 工具调用流程

```
Agent Brain → ToolRegistry → ToolExecutor → External Service
                ↓                              ↑
            参数校验                      结果返回
                ↓                              ↑
            权限检查                      错误处理
                ↓                              ↑
            调用执行 ←←←←←←←←←←←←←←←←←←
```

### 3.3 工具类型规划

| 工具类别 | 具体工具 | 用途 |
|---------|---------|------|
| **搜索类** | DuckDuckGo搜索、语义搜索 | 获取外部信息 |
| **文件类** | 文件读写、格式转换、导出 | 操作本地文件 |
| **API类** | REST API调用、Webhook | 与外部系统交互 |
| **数据类** | 数据库操作、Excel处理 | 数据存储和处理 |
| **通知类** | 邮件发送、消息推送 | 发送通知 |

### 3.4 安全专家观点

> **安全专家**: 工具调用需要：
> - 严格的输入验证，防止注入攻击
> - 权限分级管理，敏感操作需要额外授权
> - 操作审计日志，记录所有工具调用
> - 资源限制，防止滥用

---

## 4. 执行循环设计

### 4.1 四阶段执行循环（Plan→Act→Observe→Reflect）

```
┌─────────────────────────────────────────────────────────┐
│                    用户输入                              │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 1: PLAN (规划)                                   │
│  - 意图理解 → 目标分解 → 步骤规划 → 资源分配              │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 2: ACT (执行)                                    │
│  - 技能选择 → 工具调用 → 执行监控 → 结果收集              │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 3: OBSERVE (观察)                                │
│  - 结果验证 → 质量评估 → 异常检测 → 日志记录              │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  Phase 4: REFLECT (反思)                                │
│  - 结果对比 → 偏差分析 → 策略调整 → 决定下一步             │
│    ↓                                                   │
│  [继续 / 重试 / 调整策略 / 放弃并报告]                   │
└─────────────────────────────────────────────────────────┘
```

### 4.2 执行循环状态机

```python
class ExecutionState(Enum):
    IDLE = "idle"              # 空闲
    PLANNING = "planning"      # 规划中
    EXECUTING = "executing"    # 执行中
    OBSERVING = "observing"    # 观察中
    REFLECTING = "reflecting"  # 反思中
    COMPLETED = "completed"    # 完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 取消
```

### 4.3 测试专家观点

> **测试专家**: 执行循环需要覆盖：
> - 正常执行路径（Happy Path）
> - 各种失败场景（网络超时、权限拒绝、数据异常）
> - 边界条件（空输入、超大输入、极短执行时间）
> - 并发执行场景（多个任务同时执行）

### 4.4 PLAN B 核心能力映射

根据 PLAN B 的需求，执行循环需要支持以下核心能力：

| 能力 | 执行循环映射 | 实现位置 |
|------|------------|---------|
| **自主规划** | PLANNING 阶段自动生成步骤 | 策略脑 |
| **工具调用** | EXECUTING 阶段调用工具系统 | 执行脑 + 工具系统 |
| **反思修正** | REFLECTING 阶段评估并决定下一步 | 反思脑 |
| **任务跟踪** | 全流程状态管理 | 执行脑 + 状态机 |
| **多技能组合** | EXECUTING 阶段按顺序执行技能 | 执行脑 + 技能注册表 |

---

## 5. 安全架构设计（v2.0新增）

> **对应需求**：REQ-SEC-001/002/003/004
> **设计原则**：安全左移，从架构层面杜绝安全漏洞

### 5.1 工具执行安全架构（REQ-SEC-001）

```
┌──────────────────────────────────────────────────────────┐
│                    命令执行安全层                          │
│                                                          │
│  用户输入 → InputValidator → CommandParser → WhitelistCheck │
│                ↓               ↓              ↓          │
│            长度校验        shlex.split    base_cmd检查    │
│            元字符检测     参数化解析      白名单匹配      │
│                                                          │
│  通过 → asyncio.create_subprocess_exec(*parts)           │
│  拒绝 → AuditLogger.log(COMMAND_REJECTED) + 抛出异常     │
└──────────────────────────────────────────────────────────┘
```

**关键设计决策**：

| 决策 | 选择 | 原因 |
|------|------|------|
| 命令解析 | `shlex.split()` | 防止shell元字符注入 |
| 执行方式 | `shell=False` + `create_subprocess_exec` | 消除shell注入攻击面 |
| 命令限制 | 白名单机制 | 只允许预定义的安全命令 |
| 路径处理 | `os.path.basename(parts[0])` | 防止`/bin/rm`形式绕过 |
| 超时控制 | `asyncio.wait_for(30s)` | 防止命令执行挂起 |

**命令白名单**：

```python
ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "wc", "echo", "pwd", "whoami",
    "date", "df", "du", "find", "grep", "sort", "uniq", "curl", "ping",
}
```

### 5.2 文件访问安全架构（REQ-SEC-002）

```
┌──────────────────────────────────────────────────────────┐
│                    文件访问安全层                          │
│                                                          │
│  文件路径 → PathValidator → AllowedDirsCheck → 操作执行   │
│               ↓                  ↓                       │
│          ".."检测           前缀匹配                     │
│          规范化路径         绝对路径比较                   │
│                                                          │
│  通过 → 正常文件操作                                      │
│  拒绝 → AuditLogger.log(PATH_REJECTED) + 抛出异常        │
└──────────────────────────────────────────────────────────┘
```

**关键设计决策**：

| 决策 | 选择 | 原因 |
|------|------|------|
| 路径规范化 | `os.path.abspath()` | 解析符号链接和相对路径 |
| ".."检测 | `os.path.normpath().split(os.sep)` | 防止路径穿越 |
| 目录限制 | 可配置的允许目录列表 | 限制文件操作范围 |
| 配置方式 | `configure_allowed_dirs()` | 运行时动态配置 |

### 5.3 审计日志架构（REQ-SEC-003）

```python
class AuditLogger:
    """安全审计日志"""
    
    LOG_FILE = "logs/security_audit.jsonl"
    
    @classmethod
    def log(cls, event_type: str, details: Dict):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,  # COMMAND_REJECTED / PATH_REJECTED
            "details": details,
        }
        with open(cls.LOG_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
    
    @classmethod
    def query(cls, event_type: str = None, 
              start_time: str = None, end_time: str = None) -> List[Dict]:
        pass
```

### 5.4 输入长度限制架构（REQ-SEC-004）

```python
INPUT_LENGTH_LIMITS = {
    "user_input": 10000,
    "command_arg": 1000,
    "file_path": 500,
}

def validate_input_length(input_type: str, value: str) -> None:
    limit = INPUT_LENGTH_LIMITS.get(input_type, 10000)
    if len(value) > limit:
        raise ValueError(f"输入超出长度限制: {len(value)} > {limit} ({input_type})")
```

---

## 6. 任务隔离与并发架构（v2.0新增）

> **对应需求**：REQ-ARCH-003、REQ-ARCH-002、REQ-ARCH-004
> **设计原则**：每个任务完全独立，状态零共享

### 6.1 AgentContext — 任务级状态容器

```python
@dataclass
class AgentContext:
    """每个任务独立的上下文容器"""
    task_id: str
    state: AgentState = AgentState.IDLE
    intent: Optional[Intent] = None
    plan: Optional[ExecutionPlan] = None
    execution_results: List[ExecutionResult] = field(default_factory=list)
    current_step: int = 0
    cancel_requested: bool = False
    step_retry_counts: Dict[int, int] = field(default_factory=dict)
    reflect_round: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**关键设计决策**：

| 决策 | 选择 | 原因 |
|------|------|------|
| 状态存储位置 | AgentContext（任务级） | 避免并发状态污染 |
| AgentLoop实例变量 | 仅存共享配置 | 不存任何任务级状态 |
| 取消机制 | AgentContext.cancel_requested | 每个任务独立取消标志 |
| 步骤计数 | AgentContext.current_step | 每个任务独立进度 |

### 6.2 反思-重试闭环精确状态机（REQ-ARCH-002）

```
                    ┌──────────────────────────────────┐
                    │          用户输入                 │
                    └────────────┬─────────────────────┘
                                 ↓
                    ┌──────────────────────────────────┐
              ┌────→│         PLAN（规划）              │
              │     └────────────┬─────────────────────┘
              │                  ↓
              │     ┌──────────────────────────────────┐
              │     │         ACT（执行）               │
              │     └────────────┬─────────────────────┘
              │                  ↓
              │     ┌──────────────────────────────────┐
              │     │       OBSERVE（观察）             │
              │     └────────────┬─────────────────────┘
              │                  ↓
              │     ┌──────────────────────────────────┐
              │     │      REFLECT（反思）              │
              │     └────┬─────┬──────┬──────┬────────┘
              │          │     │      │      │
              │    CONTINUE  RETRY  ADJUST  ABANDON
              │          │     │  STRATEGY  │
              │          ↓     │      │      ↓
              │    COMPLETED   │      │    FAILED
              │                │      │
              │                ↓      ↓
              │          清空结果   重新PLAN
              │          保留计划   生成新计划
              │                │      │
              └────────────────┘──────┘
                    
              （最多3轮反思循环，超出后自动COMPLETED）
```

**状态转换表**：

| 当前状态 | 反思决策 | 下一状态 | 动作 |
|---------|---------|---------|------|
| REFLECTING | CONTINUE | COMPLETED | 正常完成 |
| REFLECTING | RETRY | ACT | 清空execution_results，保留plan |
| REFLECTING | ADJUST_STRATEGY | PLAN | 重新规划，然后ACT→OBSERVE→REFLECT |
| REFLECTING | REVIEW | COMPLETED | 标记需人工复核 |
| REFLECTING | ABANDON | FAILED | 记录放弃原因 |
| REFLECTING | （3轮后） | COMPLETED | 标记"反思循环已达上限" |

### 6.3 步骤级重试架构（REQ-ARCH-004）

```python
class StepRetryManager:
    """步骤级重试管理器"""
    
    MAX_RETRY_PER_STEP: int = 3
    
    def __init__(self):
        self.retry_counts: Dict[int, int] = {}  # step_index → retry_count
    
    def should_retry(self, step_index: int) -> bool:
        return self.retry_counts.get(step_index, 0) < self.MAX_RETRY_PER_STEP
    
    def record_retry(self, step_index: int) -> float:
        self.retry_counts[step_index] = self.retry_counts.get(step_index, 0) + 1
        return min(2 ** self.retry_counts[step_index], 10)  # 指数退避
    
    def is_exhausted(self, step_index: int) -> bool:
        return self.retry_counts.get(step_index, 0) >= self.MAX_RETRY_PER_STEP
```

**退避策略**：

| 重试次数 | 等待时间 | 说明 |
|---------|---------|------|
| 1 | 1s | 2^0 = 1 |
| 2 | 2s | 2^1 = 2 |
| 3 | 4s | 2^2 = 4 |
| 4+ | 10s | min(2^n, 10) |

---

## 7. 资源生命周期管理架构（v2.0新增）

> **对应需求**：REQ-QUAL-004、REQ-QUAL-005、REQ-SIDE-001
> **设计原则**：资源有界、自动清理、数据不可变

### 7.1 有界集合模式

```python
class BoundedDict:
    """有界字典：超过上限自动清理最旧的已完成记录"""
    
    def __init__(self, max_size: int = 100):
        self._data: OrderedDict = OrderedDict()
        self.max_size = max_size
    
    def __setitem__(self, key, value):
        self._data[key] = value
        self._cleanup()
    
    def _cleanup(self):
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)
```

**应用位置**：

| 组件 | 有界集合 | 上限 | 清理策略 |
|------|---------|------|---------|
| ExecutorBrain | task_statuses | 100 | 清理已完成/失败/取消的任务 |
| ExecutorBrain | execution_locks | 100 | 跟随task_statuses清理 |
| AgentLoop | contexts | 100 | 清理已完成任务的上下文 |

### 7.2 数据不可变模式

```python
def execute_plan(self, steps: List[Dict], context: Optional[Dict] = None) -> Dict:
    steps_copy = [dict(step) for step in steps]  # 深拷贝，不修改原始数据
    for step in steps_copy:
        step["status"] = ExecutionStatusType.PENDING  # 修改副本，不影响调用方
    # ...
```

### 7.3 模块初始化安全模式

```python
_migrated = False

def migrate_scenarios(registry: SkillRegistry) -> None:
    """显式调用，幂等执行"""
    global _migrated
    if _migrated:
        return
    # ... 执行迁移 ...
    _migrated = True
```

---

## 8. 与现有代码衔接策略

### 8.1 现有代码分析

| 模块 | 当前用途 | 如何复用 |
|------|---------|---------|
| `task_engine_v3.py` | 任务执行引擎 | 作为技能执行的基础层 |
| `llm_content.py` | LLM内容生成 | 作为内容创作技能的核心 |
| `search_processor.py` | 搜索结果处理 | 作为搜索工具的后端 |
| `session_context.py` | 会话上下文管理 | 复用为Agent Brain的上下文存储 |
| `async_executor.py` | 异步任务执行 | 复用为技能执行的调度器 |
| `validators.py` | 输入验证 | 复用为工具参数校验 |

### 8.2 迁移策略

```
阶段1: 封装层（最小改动）
├─ 为现有模块添加标准接口
├─ 不修改现有业务逻辑
└─ 新代码通过接口访问现有功能

阶段2: 重构层（逐步替换）
├─ 提取核心逻辑到新架构
├─ 保持接口兼容性
└─ 逐步淘汰旧实现

阶段3: 优化层（完全迁移）
├─ 移除旧代码
├─ 统一使用新架构
└─ 清理遗留代码
```

### 8.3 兼容性保证

| 保证项 | 实现方式 |
|--------|---------|
| API兼容 | 保留原有API接口，内部路由到新实现 |
| 数据兼容 | 支持旧数据格式自动迁移 |
| 配置兼容 | 支持旧配置格式，自动转换 |

---

## 9. 分阶段实施路线图

### 9.1 Phase 1 → v0.1.7：三贤者架构基础设施（4-6周）

**目标**: 建立三贤者架构的基础框架

| 任务 | 负责人 | 交付物 |
|------|--------|--------|
| 6.1.1 | 架构师 | 三贤者架构设计文档 |
| 6.1.2 | 开发者 | 策略脑 (StrategistBrain) 实现 |
| 6.1.3 | 开发者 | 执行脑 (ExecutorBrain) 实现 |
| 6.1.4 | 开发者 | 反思脑 (ReflectorBrain) 实现 |
| 6.1.5 | 开发者 | 共识引擎 (ConsensusEngine) 实现 |
| 6.1.6 | 开发者 | 技能注册表实现 |
| 6.1.7 | 开发者 | 工具调用框架实现 |
| 6.1.8 | 开发者 | 现有场景迁移为技能 |
| 6.1.9 | 测试专家 | 基础功能测试用例 |

**版本交付标准**:
- 三贤者架构完整实现
- 技能注册表可用
- 工具调用框架可用
- 执行循环正常运行

### 9.2 Phase 2 → v0.1.8：核心技能开发（6-8周）

**目标**: 打造核心技能，证明 Agent 价值

| 技能 | 负责人 | 交付物 |
|------|--------|--------|
| 6.2.1 | 开发者 | 商业分析技能 |
| 6.2.2 | 开发者 | 内容创作技能 |
| 6.2.3 | 开发者 | 文件操作技能 |
| 6.2.4 | 开发者 | 搜索增强技能 |
| 6.2.5 | 开发者 | 消息通知技能 |
| 6.2.6 | 测试专家 | 技能功能测试 |

**版本交付标准**:
- 5个核心技能开发完成并测试通过
- 技能注册表支持动态注册和发现
- 工具调用框架完善

### 9.3 Phase 3 → v0.1.9：端到端闭环（6-8周）

**目标**: 实现完整闭环能力

| 任务 | 负责人 | 交付物 |
|------|--------|--------|
| 6.3.1 | 开发者 | 任务状态管理 |
| 6.3.2 | 开发者 | 长会话支持 |
| 6.3.3 | 开发者 | 结果验证与修正 |
| 6.3.4 | 开发者 | 多技能组合 |
| 6.3.5 | UI设计师 | 进度可视化 |
| 6.3.6 | 测试专家 | 集成测试 |

**版本交付标准**:
- 完整的端到端执行闭环
- 支持长会话和上下文管理
- 结果验证和自动修正机制

### 9.4 Phase 3.5 → v0.1.9-beta：公开测试版（2-3周）

**目标**: 对外发布测试版，收集用户反馈

| 任务 | 负责人 | 交付物 |
|------|--------|--------|
| 6.4.1 | 开发者 | 性能优化 |
| 6.4.2 | 开发者 | Bug修复 |
| 6.4.3 | 开发者 | 用户反馈收集系统 |
| 6.4.4 | 测试专家 | 测试文档 |
| 6.4.5 | 产品经理 | 发布说明 |

**版本交付标准**:
- 功能完整，核心流程可用
- 性能满足基本使用需求
- 反馈收集系统就绪

### 9.5 Phase 4 → v0.1.8+

**目标**: 开放平台，支持第三方扩展

| 任务 | 负责人 | 交付物 |
|------|--------|--------|
| 6.5.1 | 架构师 | 技能市场 API 设计 |
| 6.5.2 | 开发者 | MCP 协议支持 |
| 6.5.3 | 开发者 | 插件系统 |
| 6.5.4 | UI设计师 | 技能编辑器界面 |
| 6.5.5 | DevOps | API 文档与 SDK |

**版本交付标准**:
- 技能市场 API 开放
- MCP 协议兼容
- 插件系统可用

---

## 10. 风险评估与应对

| 风险 | 等级 | 应对策略 | 负责人 |
|------|------|---------|--------|
| 技术复杂度高 | 🔴 | 分阶段实施，每个阶段有明确验收标准 | 架构师 |
| LLM 成本增加 | 🟡 | 引入缓存机制，优化 token 使用 | 开发者 |
| 用户期望管理 | 🟡 | 明确各阶段能力边界 | 产品经理 |
| 安全风险 | 🔴 | 严格输入验证、权限控制、审计日志 | 安全专家 |
| 性能问题 | 🟡 | 异步执行、结果缓存、资源限制 | DevOps |
| 兼容性问题 | 🟡 | 保留旧API，逐步迁移 | 开发者 |

---

## 11. 角色分工与职责

| 角色 | 核心职责 | 在本项目中的具体任务 |
|------|---------|---------------------|
| **架构师** | 系统架构设计 | Agent Brain 架构设计、技术选型、API 设计 |
| **产品经理** | 需求分析与规划 | 用户体验设计、功能优先级、路线图制定 |
| **安全专家** | 安全保障 | 安全审计、权限设计、漏洞防护 |
| **测试专家** | 质量保障 | 测试用例设计、自动化测试、质量门禁 |
| **开发者** | 功能实现 | 核心代码开发、技能实现、工具集成 |
| **DevOps** | 运维与部署 | CI/CD 建设、监控告警、性能优化 |
| **UI设计师** | 用户界面设计 | 执行进度展示、技能选择界面、交互设计 |

---

## 📝 共识签署

| 角色 | 签名 | 日期 |
|------|------|------|
| 架构师 | ✅ | 2026-05-07 |
| 产品经理 | ✅ | 2026-05-07 |
| 安全专家 | ✅ | 2026-05-07 |
| 测试专家 | ✅ | 2026-05-07 |
| 开发者 | ✅ | 2026-05-07 |
| DevOps | ✅ | 2026-05-07 |
| UI设计师 | ✅ | 2026-05-07 |

---

**文档版本**: v4.0  
**创建日期**: 2026-05-07  
**下次评审日期**: 2026-05-21

---

## 11. PHASE3 端到端闭环架构（v4.0 新增）

> **背景**：PHASE2（v0.1.8）已完成6个核心技能从mock到真实能力的升级。PHASE3目标是实现从用户目标到任务完成的完整闭环，让Agent真正"能干活"。

### 11.1 长会话上下文传递架构（REQ-3.2）

**设计思路**：将SessionContextManager与AgentLoop集成，通过session_id关联会话。

```
AgentLoop.run(user_input, session_id=None)
    │
    ├─ session_id=None → 创建新会话
    │   └─ SessionContextManager.create_session()
    │
    └─ session_id=xxx → 恢复已有会话
        └─ SessionContextManager.get_context(session_id)
            └─ 历史步骤结果 → SkillContext.step_results
            └─ 对话历史 → StrategistBrain.understand_intent()
```

**关键变更**：
- AgentLoop.run 新增 session_id 参数
- AgentContext 新增 session_id 字段
- 每步执行结果写入 SessionContextManager
- 策略脑理解意图时注入对话历史

### 11.2 结果验证与自动修正架构（REQ-3.3）

**设计思路**：在AgentLoop的反思阶段增加自动修正循环。

```
AgentLoop._observe_and_reflect()
    │
    ├─ ReflectorBrain.evaluate_result() → quality_score
    │
    ├─ quality_score >= 0.6 → 继续
    │
    └─ quality_score < 0.6 → 自动修正
        │
        ├─ 修正策略选择：
        │   ├─ retry: 重试当前步骤（最多2次）
        │   ├─ search_and_retry: 补充搜索后重试
        │   ├─ switch_skill: 换技能执行
        │   └─ degrade: 降级到规则引擎
        │
        └─ 修正后重新评估 → 仍不达标 → 标记需人工复核
```

**关键变更**：
- AgentLoop._observe_and_reflect 增加修正循环
- ReflectorBrain 新增 suggest_correction_strategy() 方法
- AgentContext 新增 correction_count 字段
- 最大修正次数常量 MAX_CORRECTION_ATTEMPTS = 2

### 11.3 多技能编排架构（REQ-3.4）

**设计思路**：策略脑识别复合意图，生成多步骤执行计划。

```
StrategistBrain.create_plan(composite_intent)
    │
    ├─ 识别复合意图 → 拆解为子意图列表
    │   例: "分析竞品并写方案" → [搜索, 分析, 内容创作]
    │
    ├─ 为每个子意图匹配技能
    │   └─ SkillRegistry.find_by_intent()
    │
    ├─ 生成执行计划（多步骤ExecutionPlan）
    │   └─ 步骤间数据依赖通过SkillContext传递
    │
    └─ 编排失败 → 降级为单技能执行
```

**关键变更**：
- StrategistBrain 新增 create_composite_plan() 方法
- Intent 新增 sub_intents 字段
- ExecutionPlan 支持步骤间数据依赖声明
- SkillContext.step_results 自动填充前序步骤结果

### 11.4 任务暂停/恢复架构（REQ-3.1）

**设计思路**：在AgentState中增加PAUSED状态，保存断点信息。

```
AgentState 新增:
    PAUSED = "paused"

AgentLoop 新增:
    async pause_task(task_id) → 保存断点
    async resume_task(task_id) → 从断点恢复

断点信息:
    - 当前步骤索引
    - 已完成步骤结果
    - AgentContext快照
    - 暂停时间戳（用于超时检测）
```

**关键变更**：
- AgentState 枚举新增 PAUSED
- AgentLoop 新增 pause_task/resume_task 方法
- AgentContext 新增 paused_at 字段
- 后台定时器检查暂停超时（30分钟）

### 11.5 执行进度可视化架构（REQ-3.5）

**设计思路**：基于内存队列的事件流，支持SSE推送。

```
EventEmitter:
    - emit(event_type, step_id, data)
    - subscribe() → AsyncIterator[Event]

Event:
    - event_type: step_started / step_completed / step_failed / task_completed
    - step_id: 步骤标识
    - step_name: 步骤名称
    - status: 状态
    - duration_ms: 耗时
    - timestamp: 时间戳

集成点:
    AgentLoop._execute_step() → emit("step_started")
    AgentLoop._execute_step() → emit("step_completed")
    AgentLoop._observe_and_reflect() → emit("step_failed")
```

**关键变更**：
- 新增 EventEmitter 类（内存队列实现）
- AgentLoop 持有 EventEmitter 实例
- 每步执行前后发送事件
- FastAPI SSE endpoint 订阅事件流

---

## 10. PHASE2 技能开发架构（v3.0 新增）

> **背景**：PHASE1已完成三贤者架构基础设施（v0.1.7-v0.1.9），7个内置技能均为mock。PHASE2将mock替换为真实技能，对接现有LLMService/SearchResultProcessor/ToolSystem。

### 10.1 技能-LLM集成架构（REQ-SKILL-006）

**核心设计**：SkillRegistry通过依赖注入接收LLMService实例，技能执行时通过注册表获取LLM服务。

```
┌──────────────┐     注入      ┌──────────────┐
│  LLMService  │──────────────→│ SkillRegistry │
│              │               │              │
│  - call()    │               │  - llm_service│
│  - timeout   │               │  - search_proc│
│  - fallback  │               │  - tool_system│
└──────────────┘               └──────┬───────┘
                                      │ 获取服务
                    ┌─────────────────┼─────────────────┐
                    │                 │                  │
              ┌─────▼─────┐   ┌──────▼──────┐   ┌──────▼──────┐
              │ 搜索技能   │   │ 分析技能     │   │ 创作技能     │
              │ (SKILL-003)│   │ (SKILL-001) │   │ (SKILL-002) │
              └────────────┘   └─────────────┘   └─────────────┘
```

**SkillRegistry改造**：
```python
class SkillRegistry:
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        search_processor: Optional[SearchResultProcessor] = None,
        tool_system: Optional[ToolSystem] = None,
    ):
        self.llm_service = llm_service
        self.search_processor = search_processor
        self.tool_system = tool_system
        self.skills: Dict[str, Skill] = {}
        self._register_builtin_skills()
```

**降级策略**：
- LLM不可用 → 使用规则引擎（模板+关键词匹配）
- 搜索不可用 → 使用SearchCache缓存或知识库兜底
- 工具系统不可用 → 返回明确错误信息

### 10.2 技能上下文传递机制

**设计**：技能执行时接收AgentContext，包含用户输入、历史步骤结果和会话信息。

```python
@dataclass
class SkillContext:
    user_input: str
    session_id: str
    step_results: Dict[str, Any]
    conversation_history: List[Dict[str, str]]
    metadata: Dict[str, Any]
```

**传递方式**：execute_skill方法增加可选的context参数
```python
async def execute_skill(
    self, skill_id: str, context: Optional[SkillContext] = None, **kwargs
) -> Dict[str, Any]:
```

**技能间协作**：
- 搜索技能结果 → 通过step_results传递给分析技能
- 分析技能结果 → 通过step_results传递给通知技能
- 上下文由AgentLoop在执行步骤间自动传递

### 10.3 搜索增强技能架构（REQ-SKILL-003）

**执行流程**：
```
用户输入 → 查询预处理 → DuckDuckGo搜索 → SearchResultProcessor重排序
                                              ↓
                                    结果数量不足 → 知识库兜底
                                              ↓
                                    返回结构化搜索结果
```

**对接现有代码**：
- `SearchResultProcessor.process()` — 结果重排序和知识库兜底
- `SearchCache` — 搜索结果缓存
- `validators.SearchQuery` — 搜索参数校验

### 10.4 商业分析技能架构（REQ-SKILL-001）

**执行流程**：
```
用户输入 → 搜索相关数据 → LLM生成分析报告 → 反思脑评估 → 输出
```

**对接现有代码**：
- `LLMEnhancedContentGenerator.generate()` — RAG混合生成
- 搜索技能 → 获取上下文数据
- 反思脑 → 评估报告质量

**输出结构**：
```python
{
    "summary": "分析摘要",
    "key_findings": ["发现1", "发现2"],
    "swot": {
        "strengths": [...],
        "weaknesses": [...],
        "opportunities": [...],
        "threats": [...]
    },
    "action_items": [
        {"priority": "高", "action": "具体行动", "rationale": "依据"}
    ]
}
```

### 10.5 内容创作技能架构（REQ-SKILL-002）

**执行流程**：
```
用户输入 → 意图分类 → 搜索增强 → LLM生成内容 → 零占位符检查 → 输出
```

**内容模板映射**：
| 意图关键词 | 模板类型 | 输出结构 |
|-----------|---------|---------|
| 方案/计划 | plan | 目标+路线图+资源+风险+验收 |
| 报告/总结 | report | 摘要+正文+结论+建议 |
| 文案/宣传 | copy | 标题+正文+CTA |
| 邮件/通知 | email | 主题+正文+签名 |

### 10.6 文件操作技能架构（REQ-SKILL-004）

**对接ToolSystem**：
- 读取 → `ToolSystem._execute_read_file`（含路径安全校验）
- 写入 → `ToolSystem._execute_write_file`（含路径安全校验）
- 列表 → `ToolSystem._execute_list_directory`
- 搜索 → `ToolSystem._execute_search_files`

**安全约束**：
- 路径校验复用REQ-SEC-002的安全架构
- 文件大小限制：MAX_FILE_SIZE = 10MB
- 审计日志：所有操作记录

### 10.7 消息通知技能架构（REQ-SKILL-005）

**对接ToolSystem**：
- 发送邮件 → `ToolSystem._execute_send_email`

**安全增强**（审核补充项）：
- CRLF注入防护：过滤`\r\n`字符
- HTML转义：邮件正文HTML内容转义
- 参数校验：邮箱格式、必填字段

### 10.8 PHASE2 实施顺序

```
Step 1: SKILL-006（LLM集成基础设施）
  ├── SkillRegistry依赖注入改造
  ├── SkillContext定义
  └── 降级策略实现

Step 2: SKILL-003（搜索增强）
  ├── 对接SearchResultProcessor
  ├── 对接DuckDuckGo搜索
  └── 知识库兜底

Step 3: SKILL-001（商业分析）+ SKILL-002（内容创作）
  ├── 对接LLMEnhancedContentGenerator
  ├── 搜索→分析/创作闭环
  └── 零占位符保证

Step 4: SKILL-004（文件操作）+ SKILL-005（消息通知）
  ├── 对接ToolSystem
  ├── 安全增强（CRLF防护）
  └── 审计日志

Step 5: 集成测试
  ├── 搜索→分析闭环
  ├── 搜索→创作闭环
  ├── 分析→通知闭环
  └── LLM降级路径
```

---

## 12. v0.2.5 更新记录

> **更新日期**: 2026-06-07
> **对应版本**: v0.2.5
> **更新范围**: 架构统一重构，3项核心架构变更

| # | 更新项 | 更新内容 | 影响模块 |
|---|--------|---------|---------|
| 1 | AgentLoop单一入口重构 | 统一为AgentLoop作为唯一执行入口，AgentLoop.run()返回TaskResult而非Dict；移除exec_mode切换（始终使用AgentLoop）；移除execute_task_and_deliver（不再三重回退）；TaskEngineAdapter标记为deprecated（保留向后兼容） | agent_loop.py, executor_brain.py, frontend |
| 2 | AgentContext/AgentState提取为独立模块 | 将AgentContext和AgentState从agent_loop.py中提取为独立模块，提升代码可维护性和复用性 | agent_context.py, agent_state.py |
| 3 | TaskLifecycleManager/ConsensusConsultant提取 | 将任务生命周期管理和共识咨询逻辑从核心循环中提取为独立组件，降低AgentLoop复杂度 | task_lifecycle_manager.py, consensus_consultant.py |
