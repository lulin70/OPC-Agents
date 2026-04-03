# OPC-Agents 系统架构设计文档

> 参考TraeMultiAgentSkill的双层动态上下文工程、DAG任务调度、智能角色匹配等核心设计模式。

## 1. 设计理念

### 1.1 核心原则

| 原则 | 说明 | 来源 |
|------|------|------|
| 经验沉淀 | 系统越用越聪明，每次任务都积累知识和经验 | TraeMultiAgentSkill DualLayerContext |
| 依赖感知 | 任务之间有依赖关系，按DAG顺序执行 | TraeMultiAgentSkill TaskListManager |
| 质量保障 | Agent产出物必须通过校验才能标记完成 | TraeMultiAgentSkill TaskCompletionChecker |
| 断点恢复 | 系统崩溃后可以从断点继续，不丢失进度 | TraeMultiAgentSkill CheckpointManager |
| 智能匹配 | 自动为任务找到最合适的Agent | TraeMultiAgentSkill RoleMatcher |

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
| ExperienceItem | 历史经验（成功/失败/最佳实践） | 同上 |
| UserProfile | 用户画像（偏好/常用部门/任务历史） | 同上 |

**容量控制：**
- 知识库上限1000条，LRU淘汰（按access_count）
- 经验库上限500条，按时间淘汰
- 任务历史上限100条

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
| API回归 | tests/test_api_regression.py | 6 |
| **总计** | | **63** |
