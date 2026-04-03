# 总裁办（Executive Office）角色定位与职责设计

**文档类型**: 产品设计决策  
**版本**: 2.0  
**日期**: 2026-04-03  
**状态**: 待讨论

---

## 一、核心问题：总裁办的角色定位

### 问题陈述

在苏格拉底式审查中，我们提出了一个关键问题：

> **总裁办作为对用户意图负责的 Agent，需要实时监控任务执行并在失败时决定是否重试，还是只需要报告和结果？**

这个问题的本质是：**总裁办是"管家"还是"秘书"？**

- **管家（Steward）**: 全权代理，自主决策，用户只看结果
- **秘书（Secretary）**: 执行指令，汇报进度，用户参与决策

### 我们的选择：**智能秘书 + 有限代理权**

**设计原则**:
1. **用户明确优先**: 用户明确指示时，严格执行用户指令
2. **用户不明确时**: 总裁办基于依赖关系、业务价值、风险评估提供建议
3. **关键决策点**: 需要用户确认（如重试成本高的任务）
4. **常规决策点**: 总裁办自主决策（如网络错误自动重试）

---

## 二、总裁办的职责范围

### 2.1 意图理解与任务分解

**职责**:
- 理解用户模糊需求（如"帮我分析市场"）
- 分解为可执行任务（搜索竞品、收集数据、生成报告）
- 识别任务依赖关系（先收集数据，再生成报告）

**决策权**:
- ✅ **自主**: 任务分解方式
- ⚠️ **建议**: 任务执行顺序（用户可调整）
- ❌ **需确认**: 涉及成本/风险的任务（如付费 API 调用）

**示例**:
```
用户: "帮我分析市场"

总裁办思考过程（折叠显示）:
├─ 意图识别：市场分析请求
├─ 任务分解:
│  ├─ 1. 搜索竞品动态（Web Search Agent）
│  ├─ 2. 收集行业数据（Web Search Agent）
│  └─ 3. 生成分析报告（Content Summary Agent）
├─ 依赖关系: 1→2→3（顺序执行）
├─ 预计时长：15 分钟
└─ 风险评估：低（仅使用免费资源）

用户确认: [✓ 执行] [✎ 修改] [✕ 取消]
```

---

### 2.2 优先级管理

**职责**:
- 用户明确优先级时：严格执行
- 用户未明确时：基于以下因素智能推荐
  - 截止时间（如有）
  - 任务依赖（前置任务优先）
  - 业务价值（总裁办评估）
  - 资源可用性（当前系统负载）

**决策权**:
- ✅ **自主**: 默认优先级设置（用户未指定时）
- ⚠️ **建议**: 调整用户设置的优先级（如检测到冲突）
- ❌ **需确认**: 抢占式调度（中断正在执行的任务）

**示例**:
```
场景：用户同时提交 3 个任务，但未指定优先级

总裁办思考过程:
├─ 任务列表:
│  ├─ A: 产品方案讨论（无截止时间）
│  ├─ B: 客户邮件回复（隐含紧急）
│  └─ C: 市场分析（无截止时间）
├─ 优先级建议:
│  ├─ B: HIGH（客户相关，隐含紧急）
│  ├─ A: MEDIUM（重要但不紧急）
│  └─ C: LOW（可延后）
└─ 建议理由: 客户邮件通常有时效性

用户确认: [✓ 按建议执行] [✎ 调整优先级]
```

---

### 2.3 任务执行监控

**职责**:
- 实时监控任务状态（pending/running/completed/failed）
- 检测异常情况（超时、失败、资源不足）
- 决定处理方式（重试/调整/报告用户）

**决策权**:
- ✅ **自主**: 可重试错误的自动重试（如网络错误，≤3 次）
- ⚠️ **建议**: 不可重试错误的处理方案（如代码 bug，建议修复）
- ❌ **需确认**: 高成本重试（如需要付费 API）

**错误分类与处理策略**:

| 错误类型 | 示例 | 总裁办决策 | 用户参与 |
|---------|------|-----------|---------|
| **可重试 - 自动** | 网络超时、API 限流 | 自动重试（指数退避） | 事后报告 |
| **可重试 - 建议** | 资源不足、依赖缺失 | 提供解决方案建议 | 确认执行 |
| **不可重试** | 代码 bug、权限不足 | 停止执行，报告用户 | 需要用户修复 |
| **高风险** | 付费 API 失败、数据丢失 | 立即停止，等待指示 | 必须用户决策 |

**示例**:
```
场景：Web Search Agent 执行失败

总裁办思考过程:
├─ 错误类型：HTTP 503（服务不可用）
├─ 错误分类：可重试 - 自动
├─ 重试策略:
│  ├─ 第 1 次：等待 2 秒
│  ├─ 第 2 次：等待 4 秒
│  └─ 第 3 次：等待 8 秒
└─ 如果仍失败：切换到备用引擎（Google/Bing）

执行日志（折叠）:
[10:00:00] 开始执行 Web Search
[10:00:05] 错误：HTTP 503
[10:00:05] 自动重试 #1（等待 2 秒）
[10:00:08] 错误：HTTP 503
[10:00:08] 自动重试 #2（等待 4 秒）
[10:00:13] 成功

用户通知: [任务已完成]（无需知道重试过程）
```

---

### 2.4 通知管理

**职责**:
- 决定通知方式（实时/批量）
- 决定通知渠道（站内消息/邮件/微信）
- 决定通知内容（详细/摘要）

**通知分级策略**:

| 通知级别 | 触发条件 | 通知方式 | 通知渠道 | 示例 |
|---------|---------|---------|---------|------|
| **P0 - 紧急** | 任务失败且需用户决策 | 实时推送 | 站内 + 邮件/微信 | "任务失败，需要您确认是否重试" |
| **P1 - 重要** | 任务完成（用户等待中） | 实时推送 | 站内消息 | "产品方案已完成，请查看" |
| **P2 - 普通** | 任务完成（非紧急） | 批量汇总 | 站内消息 | "今日完成 5 个任务" |
| **P3 - 低优先级** | 后台任务完成 | 不通知（可查询） | - | 定时备份完成 |

**通知呈现方式**:

**方式 1: 站内消息中心**
```
📬 消息中心 (3 条未读)
├─ 🔴 P0 [10:30] 任务失败：网页搜索（需要确认）
├─ 🟡 P1 [10:15] 任务完成：产品方案讨论
└─ 🟢 P2 [09:00] 今日任务汇总：完成 5 个任务
```

**方式 2: 任务对话回复**
```
用户: "帮我分析市场"

总裁办: [10:00 AM] 已启动市场分析任务
  ├─ 正在搜索竞品动态...
  ├─ 正在收集行业数据...
  └─ 正在生成分析报告...

[10:15 AM] ✅ 市场分析完成
  └─ [查看报告]
```

**推荐方案**: **混合模式**
- 任务执行过程：在**对话窗口**实时更新（类似 Trae/DeepSeek）
- 任务完成/失败：根据优先级选择**站内消息**或**对话回复**
- 批量汇总：**每日报告**（站内消息/邮件）

---

### 2.5 资源优化建议

**职责**:
- 监控系统资源（CPU/内存/磁盘）
- 检测资源瓶颈
- 提供优化建议（自动/手动）

**决策权**:
- ✅ **自主**: 低优先级任务自动暂停（CPU > 95%）
- ⚠️ **建议**: 提供优化建议（如"建议增加内存"）
- ❌ **需确认**: 高优先级任务暂停

**示例**:
```
场景：CPU 使用率持续 > 90%

总裁办思考过程:
├─ 当前状态:
│  ├─ CPU: 95%（警告）
│  ├─ 运行任务：3 个
│  └─ 队列任务：2 个
├─ 资源分析:
│  ├─ 任务 A（产品方案）：CPU 密集型，进度 80%
│  ├─ 任务 B（市场分析）：CPU 密集型，进度 30%
│  └─ 任务 C（邮件监控）：I/O 密集型，进度持续
├─ 优化建议:
│  ├─ 方案 1: 暂停任务 B，等任务 A 完成（推荐）
│  ├─ 方案 2: 降低并发数（从 3 降到 2）
│  └─ 方案 3: 继续执行（可能系统变慢）
└─ 推荐方案：方案 1（预计节省 5 分钟）

用户确认: [✓ 按建议执行] [✎ 选择其他方案] [✕ 不处理]
```

---

### 2.6 任务历史管理

**职责**:
- 管理任务存储（活跃/归档）
- 提供搜索功能
- 提供导出功能

**存储策略**:

**活跃任务**（最近 100 个）:
- 存储位置：内存 + 本地数据库
- 访问速度：毫秒级
- 包含内容：完整任务信息 + 结果

**归档任务**（100 个之前）:
- 存储位置：本地文件系统（按日期归档）
- 访问速度：秒级（需要加载）
- 包含内容：任务元数据 + 结果索引
- 触发条件：任务数量 > 100 或 任务完成 > 7 天

**示例**:
```
任务历史界面:
├─ 🔍 搜索框 [输入关键词搜索]
├─ 活跃任务 (100)
│  └─ [列表显示]
├─ 归档任务 (500+)
│  ├─ 2026-04 (50 个)
│  ├─ 2026-03 (120 个)
│  └─ 2026-02 (80 个)
└─ [导出选中任务]

搜索示例:
用户输入："客户 A"
结果:
  ├─ 2026-03-15: 客户 A 邮件回复（已完成）
  ├─ 2026-02-20: 客户 A 合同分析（已完成）
  └─ 2026-01-10: 客户 A 市场调研（已归档）[加载]
```

---

### 2.7 调度透明化

**职责**:
- 显示调度计划
- 显示预计执行时间
- 显示思考过程（可折叠）

**呈现方式**: **类似 Trae/DeepSeek 的思考过程**

**示例**:
```
用户: "帮我分析市场，顺便回复客户邮件"

总裁办:
<div style="font-size: 12px; color: #666;">
<details>
<summary>🤔 思考过程（点击展开）</summary>

**意图理解**:
- 主任务：市场分析（重要）
- 副任务：客户邮件回复（紧急）

**任务分解**:
1. 客户邮件回复（Market Dept）- 优先级：HIGH
   └─ 原因：客户相关，隐含紧急
2. 市场数据收集（Web Search）- 优先级：MEDIUM
   └─ 依赖：无
3. 市场分析报告（Content Summary）- 优先级：MEDIUM
   └─ 依赖：任务 2 完成

**调度计划**:
┌──────────┬────────────┬─────────┬──────────┐
│ 时间     │ 任务       │ Agent   │ 状态     │
├──────────┼────────────┼─────────┼──────────┤
│ 10:00    │ 邮件回复   │ Market  │ 执行中   │
│ 10:05    │ 数据收集   │ Web     │ 等待中   │
│ 10:10    │ 分析报告   │ Content │ 等待中   │
└──────────┴────────────┴─────────┴──────────┘

**预计完成时间**: 10:20（约 20 分钟）

**资源评估**:
- CPU: 当前 30%，预计峰值 60%（安全）
- 内存：当前 2GB，可用 6GB（充足）
</details>
</div>

✅ 已启动 3 个任务，正在执行：客户邮件回复...

---
[10:05] 客户邮件回复完成，开始收集市场数据...
[10:15] 数据收集完成，开始生成分析报告...
[10:20] ✅ 所有任务完成！[查看报告]
```

**设计要点**:
1. **小字体**（12px），不喧宾夺主
2. **折叠默认**，用户需要时展开
3. **实时更新**，用户可以看到进度
4. **可交互**，用户可以调整计划

---

## 三、改进方向与实现计划

基于上述分析，更新改进方向：

### 改进方向 1: 优先级智能化 ✅

**实现方案**:
```python
class PriorityAdvisor:
    def recommend_priority(self, task, context):
        # 用户明确指定
        if task.user_priority:
            return task.user_priority
        
        # 用户未指定，智能推荐
        score = 0
        
        # 截止时间（权重 40%）
        if task.deadline:
            hours_left = (task.deadline - now).total_seconds() / 3600
            if hours_left < 2:
                score += 40  # 紧急
            elif hours_left < 24:
                score += 20  # 较急
        
        # 任务依赖（权重 30%）
        if task.is_prerequisite_for_others:
            score += 30  # 前置任务优先
        
        # 业务价值（权重 30%）
        if task.type in ['customer_email', 'contract_review']:
            score += 30  # 客户/合同相关
        elif task.type in ['market_research', 'report']:
            score += 20  # 研究/报告
        
        # 转换为优先级
        if score >= 80:
            return Priority.HIGH
        elif score >= 50:
            return Priority.MEDIUM
        else:
            return Priority.LOW
```

**用户界面**:
```
任务：市场分析
优先级：[用户指定 ▼]  [自动推荐 ●]
  ├─ 自动推荐理由:
  │  ├─ 无截止时间（0 分）
  │  ├─ 是其他任务的前置（+30 分）
  │  └─ 研究类任务（+20 分）
  └─ 推荐结果：MEDIUM（50 分）
```

---

### 改进方向 2: 通知分级 ✅

**实现方案**:
```python
class NotificationManager:
    def notify(self, task, event):
        # 决定通知级别
        if event == 'failed' and task.requires_user_decision:
            level = 'P0_URGENT'  # 需要用户决策
        elif event == 'completed' and user.is_waiting(task):
            level = 'P1_IMPORTANT'  # 用户等待中
        elif event == 'completed':
            level = 'P2_NORMAL'  # 普通完成
        else:
            level = 'P3_LOW'  # 低优先级
        
        # 决定通知方式
        if level == 'P0_URGENT':
            self.send_instant(task, channels=['in_app', 'email'])
        elif level == 'P1_IMPORTANT':
            self.send_instant(task, channels=['in_app'])
        elif level == 'P2_NORMAL':
            self.add_to_daily_digest(task)
        # P3 不通知
```

**用户界面**:
```
通知设置:
├─ 紧急通知（P0）
│  ├─ [✓] 站内消息
│  ├─ [✓] 邮件
│  └─ [ ] 微信
├─ 重要通知（P1）
│  ├─ [✓] 站内消息
│  └─ [ ] 邮件
├─ 普通通知（P2）
│  ├─ [ ] 站内消息
│  └─ [✓] 每日汇总
└─ 后台任务（P3）
   └─ [ ] 不通知（仅可查询）
```

---

### 改进方向 3: 资源优化建议 ✅

**实现方案**:
```python
class ResourceOptimizer:
    def monitor_and_optimize(self):
        cpu_usage = get_cpu_usage()
        
        if cpu_usage > 95:
            # 严重瓶颈
            tasks = get_running_tasks()
            low_priority = [t for t in tasks if t.priority == Priority.LOW]
            
            if low_priority:
                # 自动暂停低优先级
                self.pause_task(low_priority[0])
                self.notify_user("已自动暂停低优先级任务以释放资源")
        
        elif cpu_usage > 80:
            # 轻度瓶颈
            suggestion = self.generate_suggestion()
            self.notify_user(suggestion, level='suggestion')
    
    def generate_suggestion(self):
        return {
            'title': 'CPU 使用率较高',
            'current': '85%',
            'suggestions': [
                '暂停 1 个低优先级任务可释放 20% CPU',
                '降低并发数（从 3 降到 2）',
                '继续执行（可能系统变慢）'
            ],
            'recommendation': 0  # 推荐第一个方案
        }
```

---

### 改进方向 4: 错误分类 ✅

**实现方案**:
```python
class ErrorHandler:
    ERROR_CATEGORIES = {
        'retryable_auto': [
            'network_timeout',
            'api_rate_limit',
            'temporary_unavailable'
        ],
        'retryable_advised': [
            'resource_insufficient',
            'dependency_missing'
        ],
        'non_retryable': [
            'code_bug',
            'permission_denied',
            'invalid_input'
        ],
        'high_risk': [
            'payment_failed',
            'data_loss'
        ]
    }
    
    def handle_error(self, task, error):
        category = self.categorize(error)
        
        if category == 'retryable_auto':
            # 自动重试
            return self.auto_retry(task)
        elif category == 'retryable_advised':
            # 建议用户
            return self.advise_user(task, error)
        elif category == 'non_retryable':
            # 停止并报告
            return self.report_to_user(task, error)
        elif category == 'high_risk':
            # 立即停止，等待指示
            return self.wait_for_user_decision(task, error)
```

---

### 改进方向 5: 任务历史增强 ✅

**实现方案**:
```python
class TaskHistoryManager:
    def __init__(self):
        self.active_limit = 100
        self.archive_after_days = 7
    
    def add_task(self, task):
        # 添加到活跃任务
        self.active_tasks.append(task)
        
        # 检查是否需要归档
        if len(self.active_tasks) > self.active_limit:
            self.archive_old_tasks()
    
    def archive_old_tasks(self):
        # 移动旧任务到归档
        old_tasks = self.active_tasks[:50]
        for task in old_tasks:
            self.archive_task(task)
            self.active_tasks.remove(task)
    
    def search(self, keyword):
        # 搜索活跃任务
        results = [t for t in self.active_tasks if keyword in t.name]
        
        # 搜索归档任务（需要加载）
        archived = self.search_archived(keyword)
        results.extend(archived)
        
        return results
    
    def export_tasks(self, task_ids, format='json'):
        # 导出任务
        tasks = [self.get_task(id) for id in task_ids]
        return export_to_format(tasks, format)
```

**用户界面**:
```
任务历史:
├─ 🔍 搜索：[客户 A        ] [搜索]
├─ 时间范围：[最近 7 天 ▼]
├─ 状态：[全部 ▼]
│
├─ 活跃任务 (3)
│  ├─ [✓] 客户 A 邮件回复 (2026-04-02)
│  └─ [✓] 客户 A 合同分析 (2026-04-01)
│
├─ 归档任务 (1)
│  └─ [ ] 客户 A 市场调研 (2026-01-10) [加载]
│
└─ [导出选中 (0)] [批量删除]
```

---

### 改进方向 6: 调度透明化 ✅

**实现方案**:
```python
class TransparentScheduler:
    def schedule_with_explanation(self, tasks):
        explanation = {
            'intent_understanding': self.analyze_intent(tasks),
            'task_decomposition': self.decompose(tasks),
            'dependency_graph': self.build_dependency_graph(tasks),
            'scheduling_plan': self.create_schedule(tasks),
            'estimated_time': self.estimate_time(tasks),
            'resource_assessment': self.assess_resources(tasks)
        }
        
        return {
            'schedule': self.execute_schedule(tasks),
            'explanation': explanation  # 用于前端展示
        }
```

**用户界面**: **类似 Trae/DeepSeek**
```html
<div class="thinking-process">
  <details>
    <summary>🤔 思考过程</summary>
    
    <div class="intent">
      <strong>意图理解:</strong>
      <p>主任务：市场分析（重要）<br>
      副任务：客户邮件回复（紧急）</p>
    </div>
    
    <div class="decomposition">
      <strong>任务分解:</strong>
      <ol>
        <li>客户邮件回复（Market Dept）- HIGH</li>
        <li>市场数据收集（Web Search）- MEDIUM</li>
        <li>市场分析报告（Content Summary）- MEDIUM</li>
      </ol>
    </div>
    
    <div class="schedule">
      <strong>调度计划:</strong>
      <table>...</table>
    </div>
    
    <div class="eta">
      <strong>预计完成时间:</strong> 10:20（约 20 分钟）
    </div>
  </details>
</div>

<div class="execution-log">
  <p>[10:00] 已启动 3 个任务，正在执行：客户邮件回复...</p>
  <p>[10:05] 客户邮件回复完成，开始收集市场数据...</p>
  <p>[10:15] 数据收集完成，开始生成分析报告...</p>
  <p>[10:20] ✅ 所有任务完成！</p>
</div>
```

---

### 改进方向 7: 场景化模式 ✅

**实现方案**:
```python
class OPCModes:
    MODES = {
        'simple': {
            'name': '简单模式',
            'description': '适合新手，自动化程度高',
            'features': {
                'auto_priority': True,  # 自动优先级
                'auto_retry': True,     # 自动重试
                'notifications': 'minimal',  # 最少通知
                'transparency': 'low'   # 简化思考过程
            }
        },
        'advanced': {
            'name': '高级模式',
            'description': '适合专家，完全控制',
            'features': {
                'auto_priority': False,  # 手动优先级
                'auto_retry': 'advised', # 建议重试
                'notifications': 'all',  # 所有通知
                'transparency': 'high'   # 完整思考过程
            }
        }
    }
```

**用户界面**:
```
系统设置:
├─ 运行模式: [简单模式 ●] [高级模式 ○]
│
├─ 简单模式说明:
│  ├─ ✓ 自动管理任务优先级
│  ├─ ✓ 自动重试失败任务
│  ├─ ✓ 仅显示重要通知
│  └─ ✓ 简化思考过程
│
└─ [切换到高级模式]
```

---

## 四、总结

### 总裁办的角色定位

**智能秘书 + 有限代理权**:
- 用户明确时：**严格执行**
- 用户不明确时：**智能建议**
- 关键决策点：**用户确认**
- 常规决策点：**自主决策**

### 核心设计原则

1. **透明化**: 思考过程可见、可理解、可干预
2. **渐进式**: 简单模式默认，高级模式可选
3. **智能化**: 自动推荐优先级、自动重试、自动优化
4. **人性化**: 通知分级、错误分类、资源建议

### 下一步行动

1. **实现优先级智能推荐算法**
2. **实现通知分级系统**
3. **实现错误分类与处理策略**
4. **实现调度透明化 UI**
5. **用户测试与迭代优化**

---

**文档状态**: 待讨论  
**下一步**: 技术评审 → 实现计划 → 用户测试
