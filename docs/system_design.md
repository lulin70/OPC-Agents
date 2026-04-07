# OPC-Agents 系统设计文档

**版本**: 1.0  
**创建时间**: 2026-04-07  
**最后更新**: 2026-04-07

---

## 一、系统愿景

### 1.1 核心理念
> **让一人公司用户通过与总裁办的对话来完成所有任务**

### 1.2 价值主张
- **对话即交互**：用户无需学习复杂界面，通过自然语言对话即可完成任务
- **总裁办中枢**：总裁办作为统一入口，智能分发任务到各部门
- **透明化执行**：实时了解任务进度，无需主动询问
- **主动式服务**：系统主动通知重要事件，无需用户轮询
- **越用越聪明**：每次任务都积累知识和经验，后续任务自动复用

---

## 二、系统架构

### 2.1 三层架构

```
用户层 (User Layer)
    ↓
对话层 (Conversation Layer) - 新增
    ↓
执行层 (Execution Layer)
```

#### 对话层（新增）
**职责**：管理用户与总裁办的交互过程
- 对话生命周期管理（创建/归档/删除）
- 消息管理（发送/接收/存储）
- 任务 - 对话关联
- 通知管理

**核心组件**：
- `ConversationManager`: 对话管理
- `NotificationManager`: 通知管理
- `WebSocketManager`: 实时通信（阶段 2 实现）

**数据模型**：
```python
Conversation:
  - id, title, user_id, status
  - message_count, last_message_at
  - related_task_ids: List[str]
  - metadata: Dict

Message:
  - id, conversation_id, role, message_type
  - content, metadata, created_at, read

Notification:
  - id, user_id, type, priority
  - title, content, is_read
  - related_object_type, related_object_id

TaskConversationLink:
  - task_id, conversation_id, link_type
```

#### 执行层（现有）
**职责**：任务分解、调度、执行
- 意图识别
- 三贤者决策
- 任务分解
- Agent 匹配
- DAG 调度
- 执行监控

---

## 三、对话与任务关系

### 3.1 设计原则
> **对话是界面，任务是后台**  
> 用户通过对话表达需求，系统在背后创建和执行任务

### 3.2 关系模式

#### 模式 1：一个对话 → 多个任务
```
对话："帮我规划下季度工作"
├─> 任务 1：市场分析（task-001）
├─> 任务 2：竞品调研（task-002）
└─> 任务 3：产品路线图（task-003）
```

#### 模式 2：多个对话 → 一个任务
```
对话 1（周一）："我想做个新网站" → 创建任务 task-100
对话 2（周三）："网站进度如何？" → 查询任务 task-100
对话 3（周五）："网站能加个联系表单吗？" → 更新任务 task-100
```

#### 模式 3：纯对话（不产生任务）
```
用户："今天心情不好"
总裁办："理解，要不要聊聊？或者我给您讲个笑话？"
（纯情感交流，不产生任务）
```

#### 模式 4：对话中嵌入任务卡片
```
[对话流]
用户：帮我创建一个待办事项应用
总裁办：好的，正在为您规划...
       [任务卡片：task-200]
       ├─ 状态：in_progress
       ├─ 进度：30%
       └─ [查看详情] [暂停] [取消]
```

### 3.3 数据流

```
用户发送消息
    ↓
ConversationManager.add_message()
    ↓
意图识别（GLM）
    ↓
判断是否需要创建任务？
    ├─ 是 → TaskManager.create_task()
    │         ↓
    │     TaskConversationLink.create()
    │         ↓
    │     任务执行 → 结果返回到对话
    │
    └─ 否 → 直接回复（闲聊/查询）
```

---

## 四、通知系统

### 4.1 通知类型

| 类型 | 说明 | 示例 |
|------|------|------|
| task | 任务通知 | 任务完成/失败/进度更新 |
| confirmation | 确认通知 | 计划待确认/资源引入待确认 |
| system | 系统通知 | 系统维护/配置变更 |
| finance | 财务通知 | 预算预警/账单提醒 |
| hr | 人事通知 | 新 Agent 可用/技能缺口 |

### 4.2 优先级分级

| 优先级 | 标识 | 响应时间 | 示例 |
|--------|------|----------|------|
| 🔴 urgent | P0 | 立即处理 | 任务失败/系统故障 |
| 🟡 important | P1 | 今天内处理 | 计划待确认/预算预警 |
| 🟢 normal | P2 | 空闲时处理 | 任务完成/新功能可用 |
| 🔵 info | P3 | 仅告知 | 系统更新/使用提示 |

### 4.3 事件驱动通知

```python
# 自动创建通知的事件
event_bus.subscribe('task.completed', _on_task_completed)
event_bus.subscribe('task.failed', _on_task_failed)
event_bus.subscribe('plan.pending_confirmation', _on_plan_pending)

# 示例：任务完成通知
def _on_task_completed(event_data: Dict) -> None:
    task_info = event_data.get('task', {})
    create_notification(
        user_id=event_data.get('user_id'),
        type=NotificationType.TASK.value,
        priority=NotificationPriority.NORMAL.value,
        title="任务完成",
        content=f"任务 {task_info.get('task_name')} 已完成",
        related_object_type='task',
        related_object_id=task_info.get('task_id')
    )
```

---

## 五、API 设计

### 5.1 对话 API（v2）

```python
# 创建对话
POST /api/v2/chat
Request: { "user_id": "user_123", "title": "新对话", "initial_message": "你好" }
Response: { "success": true, "data": { "id": "conv_123", ... } }

# 获取对话列表
GET /api/v2/chat?user_id=user_123&status=active&page=1&limit=20
Response: { "items": [...], "total": 100, "page": 1 }

# 获取对话详情
GET /api/v2/chat/{chat_id}?limit=50
Response: { "conversation": {...}, "messages": [...] }

# 发送消息
POST /api/v2/chat/{chat_id}/message
Request: { "role": "user", "type": "text", "content": "消息内容" }
Response: { "success": true, "data": { "message": {...} } }

# WebSocket 推送（阶段 2）
WS /api/v2/ws/chat/{chat_id}
-> Server: { "type": "new_message", "data": {...} }
```

### 5.2 通知 API（v2）

```python
# 获取通知列表
GET /api/v2/notifications?user_id=user_123&unread_only=true
Response: { "items": [...], "total": 50, "unread_count": 5 }

# 标记已读
PUT /api/v2/notifications/{id}/read?user_id=user_123
Response: { "success": true }

# 批量标记已读
PUT /api/v2/notifications/read-all?user_id=user_123&before=timestamp
Response: { "success": true, "marked_count": 10 }

# 删除通知
DELETE /api/v2/notifications/{id}?user_id=user_123
Response: { "success": true }

# WebSocket 推送（阶段 2）
WS /api/v2/ws/notifications
-> Server: { "type": "new_notification", "data": {...} }
```

---

## 六、数据库设计

### 6.1 ER 图

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│Conversations│◄──────│   Messages   │──────►│   Tasks     │
├─────────────┤       ├──────────────┤       ├─────────────┤
│ id          │       │ id           │       │ task_id     │
│ title       │       │ conversation │       │ task_name   │
│ user_id     │       │ role         │       │ status      │
│ status      │       │ message_type │       │ ...         │
│ ...         │       │ content      │       └─────────────┘
└─────────────┘       │ ...          │
         │            └──────────────┘
         │
         ▼
┌─────────────────┐
│TaskConversation │
├─────────────────┤
│ task_id         │
│ conversation_id │
│ link_type       │
└─────────────────┘

┌─────────────┐
│Notifications│
├─────────────┤
│ id          │
│ user_id     │
│ type        │
│ priority    │
│ ...         │
└─────────────┘
```

### 6.2 关键索引

```sql
-- 对话查询优化
CREATE INDEX idx_conversations_user_status ON conversations(user_id, status);
CREATE INDEX idx_conversations_last_message ON conversations(user_id, last_message_at DESC);

-- 消息查询优化
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_unread ON messages(conversation_id, read) WHERE read = FALSE;

-- 通知查询优化
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read) WHERE is_read = FALSE;
CREATE INDEX idx_notifications_user_created ON notifications(user_id, created_at DESC);

-- 任务 - 对话关联优化
CREATE INDEX idx_links_task ON task_conversation_links(task_id);
CREATE INDEX idx_links_conversation ON task_conversation_links(conversation_id);
```

---

## 七、实施路线图

### Phase 1: 基础架构（2 周）✅ 进行中
- [x] 数据库 Schema 设计
- [x] ConversationManager 实现
- [x] NotificationManager 实现
- [x] 单元测试（14/14 通过）
- [ ] 对话 API 路由
- [ ] 通知 API 路由
- [ ] 通知中心前端
- [ ] 对话中心前端

### Phase 2: 实时通信（2 周）
- [ ] WebSocketManager 实现
- [ ] WebSocket 路由
- [ ] 前端 WebSocket 客户端
- [ ] 消息推送优化

### Phase 3: 高级功能（2 周）
- [ ] 对话搜索
- [ ] 对话导出
- [ ] 浏览器桌面通知
- [ ] 通知偏好设置

---

## 八、技术栈

### 后端
- **语言**: Python 3.9+
- **Web 框架**: Flask
- **数据库**: SQLite
- **实时通信**: WebSocket (阶段 2)
- **事件总线**: 自研 EventBus

### 前端
- **模板**: Jinja2
- **样式**: CSS3 + CSS Variables
- **交互**: Vanilla JavaScript
- **实时推送**: SSE / WebSocket

### 部署
- **服务器**: 本地/云服务器
- **进程管理**: systemd / supervisord
- **反向代理**: Nginx（可选）

---

## 九、性能指标

### 设计目标
- **页面加载**: < 2 秒
- **API 响应**: P95 < 200ms
- **消息推送**: < 1 秒延迟
- **WebSocket 在线率**: > 99.9%

### 测试结果（当前）
- **单元测试**: 14/14 通过（0.19 秒）
- **数据库查询**: 索引优化后 < 10ms
- **内存占用**: < 100MB（空闲）

---

## 十、安全考虑

### 数据安全
- **输入验证**: 所有 API 参数严格验证
- **SQL 注入防护**: 参数化查询
- **XSS 防护**: HTML 转义

### 访问控制
- **用户隔离**: 每个用户只能访问自己的数据
- **API 鉴权**: Token 验证（阶段 2 实现）

### 隐私保护
- **对话加密**: 敏感数据加密存储（阶段 3）
- **数据导出**: 支持用户导出所有数据

---

## 十一、监控与日志

### 监控指标
- **系统资源**: CPU/内存/磁盘
- **API 性能**: 响应时间/错误率/QPS
- **业务指标**: 对话数/任务数/通知数

### 日志级别
- **ERROR**: 系统错误
- **WARNING**: 可恢复错误
- **INFO**: 关键操作
- **DEBUG**: 调试信息

---

## 十二、容灾与恢复

### 备份策略
- **数据库**: 每日自动备份
- **配置文件**: 版本控制
- **用户数据**: 工作目录独立

### 恢复机制
- **断点恢复**: 任务执行中断后可恢复
- **数据迁移**: 数据库 Schema 版本管理

---

**文档维护**: 架构师  
**审核周期**: 每两周更新  
**分发范围**: 全体开发团队
