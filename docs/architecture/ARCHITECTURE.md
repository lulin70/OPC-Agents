# OPC-Agents 系统架构设计文档

> 参考TraeMultiAgentSkill的双层动态上下文工程、DAG任务调度、智能角色匹配等核心设计模式。

## 1. 设计理念

### 1.1 核心原则

| 原则 | 说明 | 来源 |
|------|------|------|
| 经验沉淀 | 系统越用越聪明，每次任务都积累知识和经验（6 种类型/权重计算/冲突检测/遗忘机制） | TraeMultiAgentSkill DualLayerContext + Memory Classification Engine |
| 依赖感知 | 任务之间有依赖关系，按 DAG 顺序执行 | TraeMultiAgentSkill TaskListManager |
| 质量保障 | Agent 产出物必须通过校验才能标记完成 | TraeMultiAgentSkill TaskCompletionChecker |
| 断点恢复 | 系统崩溃后可以从断点继续，不丢失进度 | TraeMultiAgentSkill CheckpointManager |
| 智能匹配 | 自动为任务找到最合适的 Agent | TraeMultiAgentSkill RoleMatcher |

### 1.2 架构风格

**三层架构 + 双层上下文 + DAG调度**

```
┌─────────────────────────────────────────────────────────────┐
│                    全局上下文层 (Global Context)             │
│                     长期记忆 (Long-term Memory)              │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 用户画像     │  │ 知识库       │  │ 经验库       │      │
│  │ UserProfile  │  │ Knowledge    │  │ Experience   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                     ↕ ContextSynchronizer
┌─────────────────────────────────────────────────────────────┐
│                    任务上下文层 (Task Context)               │
│                     工作记忆 (Working Memory)                │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 任务定义     │  │ 思考记录     │  │ 产出物       │      │
│  │ Definition   │  │ Thoughts     │  │ Artifacts    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                     ↕ DAGScheduler
┌─────────────────────────────────────────────────────────────┐
│                    执行层 (Execution Layer)                  │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ TaskExecutor │  │ Completion   │  │ Checkpoint   │      │
│  │              │  │ Checker      │  │ Manager      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ RoleMatcher  │  │ HandoffDoc   │                        │
│  │              │  │              │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## 2. 双层上下文管理

### 2.1 设计参考

参考TraeMultiAgentSkill的 [双层动态上下文工程](https://mp.weixin.qq.com/s/Jw9Rr-0t7MNF_NJJybidIQ) 理念。

### 2.2 全局上下文层（长期记忆）

| 组件 | 说明 | 存储位置 |
|------|------|---------|
| KnowledgeItem | 领域知识（架构/测试/需求/设计） | data/context/global_context.json |
| ExperienceItem | 历史经验（6 种类型/权重评分/冲突检测） | 同上 |
| UserProfile | 用户画像（偏好/常用部门/任务历史） | 同上 |

**经验类型（6 种）：**
- `user_preference` - 用户偏好（配置/沟通风格/交付要求）
- `correction` - 纠正信号（用户纠正 Agent 判断）
- `decision` - 决策记录（任务中的关键决策）
- `task_pattern` - 任务模式（反复出现的任务类型）
- `agent_optimization` - Agent 优化（成功/失败经验）
- `skill_usage` - 技能使用（哪些技能有效/无效）

**权重计算（4 维度）：**
```
权重 = 置信度 40% + 时效性 30% + 使用频率 20% + 来源可靠性 10%
```

**容量控制：**
- 知识库上限 1000 条，LRU 淘汰（按 access_count）
- 经验库上限 500 条，按权重淘汰（低权重优先）
- 任务历史上限 100 条

### 2.3 任务上下文层（工作记忆）

| 组件 | 说明 | 生命周期 |
|------|------|---------|
| TaskContext.definition | 任务定义（名称/目标/约束） | 任务开始→结束 |
| TaskContext.thought_records | Agent思考记录 | 任务开始→结束 |
| TaskContext.artifacts | 产出物（代码/文档/设计） | 任务开始→结束 |
| TaskContext.injected_context | 从全局注入的知识/经验 | 任务开始时注入 |

### 2.4 双向同步机制

**sync_global_to_task（任务开始时）：**
1. 搜索相关知识（关键词匹配，最多5条）
2. 查找相似经验（任务描述匹配，最多3条）
3. 注入用户偏好和常用部门

**sync_task_to_global（任务完成时）：**
1. 提取经验教训 → 经验库
2. 从产出物提取新知识 → 知识库
3. 更新用户画像（部门使用频率）

## 3. DAG任务调度

### 3.1 设计参考

参考TraeMultiAgentSkill的 TaskListManager（TaskItem.depends_on / is_ready / get_ready_tasks）。

### 3.2 执行计划数据结构

```json
{
  "execution_steps": [
    {
      "step": 1,
      "task": "需求分析",
      "department": "product",
      "description": "分析用户需求",
      "deliverable": "需求文档.md",
      "depends_on": [],
      "required_skills": ["需求分析", "用户研究"],
      "acceptance_criteria": ["包含用户故事", "包含验收标准"]
    },
    {
      "step": 2,
      "task": "架构设计",
      "department": "engineering",
      "depends_on": [1],
      "required_skills": ["系统设计"],
      "acceptance_criteria": ["包含技术选型", "包含模块划分"]
    },
    {
      "step": 3,
      "task": "UI设计",
      "department": "design",
      "depends_on": [1],
      "required_skills": ["UI设计", "原型"],
      "acceptance_criteria": ["包含交互流程", "包含视觉规范"]
    },
    {
      "step": 4,
      "task": "开发实现",
      "department": "engineering",
      "depends_on": [2, 3],
      "required_skills": ["Python", "Flask"],
      "acceptance_criteria": ["代码可运行", "通过单元测试"]
    }
  ]
}
```

### 3.3 DAG调度流程

```
confirm_plan → 构建DAG图 → is_dag()检测循环
    ↓
get_ready_tasks() → 提交依赖已满足的任务
    ↓
Agent执行完成 → on_task_completed() → 检查新的ready任务
    ↓
Agent执行失败 → on_task_failed() → 标记依赖任务为blocked
    ↓
所有任务完成 → get_progress() = 100%
```

## 4. 任务完成校验

### 4.1 设计参考

参考TraeMultiAgentSkill的 TaskCompletionChecker（进度跟踪 + 状态同步 + 完成率计算）。

### 4.2 校验流程

```
Agent执行完成
    ↓
检查1: 产出物文件是否存在（output.md）
    ↓
检查2: 产出物非空（>50字符）
    ↓
检查3: 验收标准是否满足（关键词匹配）
    ↓
检查4: GLM质量评估（可选，只对有验收标准的任务）
    ↓
综合评分 ≥ 75% → 通过
综合评分 50-75% → 部分通过
综合评分 < 50% → 不通过
```

### 4.3 校验结果持久化

每次校验结果保存到 `data/completions/{task_id}.json`，包含：
- passed/score/verdict
- 每项检查的详细结果
- 时间戳

## 5. 断点恢复

### 5.1 设计参考

参考TraeMultiAgentSkill的 CheckpointManager（Checkpoint + HandoffDocument）。

### 5.2 检查点结构

```json
{
  "task_id": "task-001",
  "step_index": 2,
  "completed_steps": [
    {"task_id": "task-001-step1", "task_name": "需求分析", "output_path": "data/tasks/task-001/product_output.md"}
  ],
  "remaining_steps": [
    {"task_id": "task-001-step3", "task_name": "UI设计", "depends_on": [1]}
  ],
  "context_snapshot": { ... },
  "dag_state": { ... }
}
```

### 5.3 交接文档

Agent完成后生成标准化HandoffDocument，包含：
- 已完成的工作
- 当前状态
- 下一步骤
- 重要注意事项
- 传递给下一个Agent的上下文

以Markdown格式保存到 `data/checkpoints/{task_id}_handoff.md`。

## 6. 智能角色调度

### 6.1 设计参考

参考TraeMultiAgentSkill的 RoleMatcher（AI语义匹配 + 关键词匹配 + 混合策略降级）。

### 6.2 三层匹配策略

| 层级 | 策略 | 权重 | 说明 |
|------|------|------|------|
| 1 | 历史表现 | 30% | 该Agent在类似任务上的成功率（从经验库获取） |
| 2 | 技能匹配 | 40% | 任务所需技能 vs Agent技能等级 |
| 3 | 关键词匹配 | 30% | 任务描述关键词 vs Agent部门/技能名称 |

### 6.3 降级机制

```
完整匹配（历史+技能+关键词）
    ↓ AI调用失败
关键词匹配（降级）
    ↓ 无Agent可用
返回空列表（由总裁办决定下一步）
```

## 7. 数据存储

| 数据 | 位置 | 格式 | 说明 |
|------|------|------|------|
| 全局上下文 | data/context/global_context.json | JSON | 知识库+经验库+用户画像 |
| 校验结果 | data/completions/{task_id}.json | JSON | 每个任务的校验记录 |
| 检查点 | data/checkpoints/{task_id}.json | JSON | 断点恢复数据 |
| 交接文档 | data/checkpoints/{task_id}_handoff.md | Markdown | Agent间交接文档 |
| 任务产出物 | data/tasks/{task_id}/{agent}_output.md | Markdown | Agent执行产出物 |
| 操作日志 | data/tasks/{task_id}/{agent}_YYYYMMDD.log | 文本 | Agent执行日志 |
| 执行计划 | data/tasks/{task_id}/plan.md | Markdown | 用户确认的执行计划 |
| 任务数据 | data/opc_agents.db | SQLite | 任务/Agent/对话持久化 |

## 8. 测试覆盖

| 模块 | 测试文件 | 测试数量 |
|------|---------|---------|
| 核心流程 | tests/test_e2e_task_flow.py | 14 |
| 完成校验 | tests/test_enhancement_modules.py | 5 |
| DAG调度 | tests/test_enhancement_modules.py | 6 |
| 上下文管理 | tests/test_enhancement_modules.py | 6 |
| 断点恢复 | tests/test_enhancement_modules.py | 4 |
| 角色匹配 | tests/test_enhancement_modules.py | 3 |
| 安全审核 | tests/opc_hr/test_mcp_integration.py | 5 |
| 模型管理 | tests/model_integration/ | 6 |
| HR管理 | tests/opc_hr/ | 3 |
| 集成测试 | tests/integration_test.py | 5 |
| API 回归 | tests/test_api_regression.py | 6 |
| 智能化改进 | tests/opc_manager/ | 52 |
| **总计** | | **225** |

---

## 9. 智能化改进系统（Phase 1-3）

### 9.1 错误分类与处理系统

**设计目标**: 智能识别错误类型并采取相应策略，提高任务成功率。

**错误分类**:
```python
class ErrorCategory(Enum):
    RETRYABLE_AUTO = "retryable_auto"      # 自动重试（网络超时、API 限流）
    RETRYABLE_ADVISED = "retryable_advised"  # 建议重试（资源不足、依赖缺失）
    NON_RETRYABLE = "non_retryable"         # 停止执行（代码 bug、权限不足）
    HIGH_RISK = "high_risk"                 # 等待指示（付费 API 失败、数据丢失风险）
```

**重试策略**:
- 指数退避：2 秒 → 4 秒 → 8 秒 → 16 秒
- 最大重试次数：3 次
- 重试耗尽后升级错误级别

**核心组件**:
- `ErrorClassifier`: 50+ 错误模式识别
- `ErrorHandler`: 错误处理策略执行
- `TaskErrorTracker`: 任务错误跟踪

### 9.2 通知分级系统

**设计目标**: 根据通知级别和用户偏好，通过合适渠道发送通知。

**通知级别**:
```python
class NotificationLevel(Enum):
    P0_URGENT = "p0_urgent"        # 紧急：任务失败需决策 → 站内 + 邮件 + 微信
    P1_IMPORTANT = "p1_important"  # 重要：任务完成（用户等待） → 站内 + 邮件
    P2_NORMAL = "p2_normal"        # 普通：任务完成（非紧急） → 每日汇总
    P3_LOW = "p3_low"              # 低：后台任务 → 不通知（可查询）
```

**通知渠道**:
- 站内消息：所有级别
- 邮件：P0/P1
- 微信/钉钉：P0（紧急）

**免打扰时段**:
- 默认：22:00 - 08:00
- 期间 P2/P3通知 → 加入每日汇总

**核心组件**:
- `NotificationManager`: 通知发送
- `NotificationPreferences`: 用户偏好配置
- `DailyDigest`: 每日汇总报告

### 9.3 调度透明化系统

**设计目标**: 可视化展示系统思考过程，让用户理解调度逻辑。

**思考过程结构**:
```python
class ThinkingProcess:
    intent: TaskIntent              # 意图理解
    decomposition: List[DecomposedTask]  # 任务分解
    dependency_graph: Dict          # 依赖关系
    scheduling_plan: List[SchedulingPlan]  # 调度计划
    estimated_completion: datetime  # 预计完成时间
    resource_assessment: ResourceAssessment  # 资源评估
```

**输出格式**:
- HTML: 可折叠详情标签，小字体（12px）
- Markdown: 结构化文档
- JSON: 程序化处理

**核心组件**:
- `TransparentScheduler`: 调度透明化
- `ThinkingProcess`: 思考过程数据结构
- `ProgressVisualizer`: 进度可视化

### 9.4 优先级智能推荐系统

**设计目标**: 基于多维度评分自动推荐任务优先级。

**评分算法**:
```
总分 100 分 = 截止时间 40% + 依赖关系 30% + 业务价值 30%

截止时间得分（40 分）:
  - 今天截止：40 分
  - 明天截止：20 分
  - 本周截止：10 分
  - 无明确截止：0 分

依赖关系得分（30 分）:
  - 有关键依赖：30 分
  - 有一般依赖：15 分
  - 无依赖：0 分

业务价值得分（30 分）:
  - 客户邮件：30 分
  - 市场调研：20 分
  - 文档整理：15 分
  - 内部会议：10 分
```

**优先级映射**:
- 80-100 分 → CRITICAL (10)
- 60-79 分 → URGENT (8)
- 40-59 分 → HIGH (6)
- 20-39 分 → MEDIUM (4)
- 0-19 分 → LOW (2)

**核心组件**:
- `PriorityAdvisor`: 优先级推荐
- `BusinessValueDB`: 业务价值数据库
- `TaskContext`: 任务上下文分析

### 9.5 资源优化系统

**设计目标**: 实时监控系统资源，提供优化建议或自动优化。

**监控指标**:
- CPU 使用率
- 内存使用率
- 磁盘空间
- 进程信息（线程数、打开文件数）

**健康度评分**:
```python
资源健康度 (0-100) = (CPU 得分 + 内存得分 + 磁盘得分) / 3

健康等级:
  - excellent: 90-100
  - good: 70-89
  - fair: 50-69
  - poor: 30-49
  - critical: 0-29
```

**优化策略**:
```python
CPU > 95%: 自动暂停低优先级任务（<3）
CPU > 80%: 提供优化建议
内存 > 85%: 建议清理或升级
磁盘 < 10GB: 建议清理
```

**核心组件**:
- `ResourceMonitor`: 资源监控
- `ResourceOptimizer`: 资源优化
- `HealthScorer`: 健康度评分

### 9.6 任务历史增强系统

**设计目标**: 提供任务搜索、归档、导出功能，支持知识沉淀。

**分层存储**:
```python
活跃任务（内存中）:
  - 最近 7 天
  - 或最近 100 个任务
  - 快速访问

归档任务（文件中）:
  - 超过 7 天或超过 100 个任务
  - 自动压缩存储
  - 按需加载
```

**搜索功能**:
- 全文搜索（任务名称/描述/结果）
- 同时搜索活跃任务和归档任务
- 支持状态过滤

**导出格式**:
- JSON: 完整任务数据
- CSV: 表格数据

**核心组件**:
- `TaskHistoryManager`: 任务历史管理
- `TaskSearchEngine`: 任务搜索
- `TaskArchiver`: 任务归档
- `TaskExporter`: 任务导出

### 9.7 场景化模式系统

**设计目标**: 为不同经验水平的用户提供合适的操作模式。

**模式配置**:
```python
class ModeConfig:
    auto_priority: bool         # 自动管理优先级
    auto_retry: bool            # 自动重试失败任务
    notification_level: str     # 通知级别（all/minimal）
    thinking_detail_level: str  # 思考过程详细程度（full/simple）
```

**预定义模式**:
```python
MODE_CONFIGS = {
    SystemMode.SIMPLE: ModeConfig(
        auto_priority=True,
        auto_retry=True,
        notification_level='minimal',
        thinking_detail_level='simple',
    ),
    SystemMode.ADVANCED: ModeConfig(
        auto_priority=False,
        auto_retry=False,
        notification_level='all',
        thinking_detail_level='full',
    )
}
```

**模式切换**:
- 运行时切换，无需重启
- 配置即时生效
- 用户偏好持久化

**核心组件**:
- `ModeManager`: 模式管理
- `ModeConfig`: 模式配置
- `UserPreferences`: 用户偏好存储

---

## 10. 多任务并发管理

### 10.1 并发模型

**设计目标**: 支持多个任务同时由不同 Agent 执行，提高整体效率。

**并发策略**:
- 不同 Agent 可同时执行任务
- 同 Agent 串行执行（避免资源冲突）
- 任务间资源隔离

**Agent 工作池**:
```python
Agent 状态:
  - idle: 空闲，可接受新任务
  - busy: 忙碌，正在执行任务
  - paused: 暂停，任务被暂停
  - error: 错误，需要干预
```

**核心组件**:
- `MultiTaskManager`: 多任务管理
- `AgentPool`: Agent 工作池
- `ResourceIsolator`: 资源隔离

### 10.2 优先级调度

**6 级优先级**:
```python
class Priority(IntEnum):
    CRITICAL = 10    # 紧急
    URGENT = 8       # 加急
    HIGH = 6         # 高
    MEDIUM = 4       # 中
    LOW = 2          # 低
    BACKGROUND = 0   # 后台
```

**调度规则**:
- 高优先级优先
- 同优先级按提交时间排序（FIFO）
- 支持运行时调整优先级

**核心组件**:
- `PriorityQueue`: 优先级队列
- `TaskScheduler`: 任务调度器
