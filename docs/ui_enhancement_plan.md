# OPC-Agents UI 增强规划

## 一、系统设计初衷与核心理念

### 1.1 愿景
**让一人公司用户通过与总裁办的对话来完成所有任务**

### 1.2 核心价值主张
- **对话即交互**：用户无需学习复杂界面，通过自然语言对话即可完成任务
- **总裁办中枢**：总裁办作为统一入口，智能分发任务到各部门
- **透明化执行**：实时了解任务进度，无需主动询问
- **主动式服务**：系统主动通知重要事件，无需用户轮询

## 二、现有系统全面审核

### 2.1 架构审核

#### 当前架构优势 ✅
1. **三层架构清晰**：总裁办 → 部门 → Agent，职责分明
2. **对话中心已具雏形**：`/api/chat` 系列 API 支持智能意图识别
3. **任务执行链完整**：意图识别 → 三贤者决策 → 任务分解 → Agent 执行 → 经验沉淀
4. **SSE 实时推送**：`/api/progress/stream` 支持实时进度推送

#### 架构问题 ⚠️
1. **对话与任务割裂**：
   - 对话历史存储在任务系统，缺乏真正的对话上下文管理
   - 没有独立的对话 ID 概念，难以支持多轮对话
   - 缺少对话状态机（pending → plan_pending → executing → completed）

2. **通知系统缺失**：
   - 没有统一的通知中心
   - 重要事件（任务完成、失败、需要确认）依赖用户主动查看
   - 缺少通知分类、优先级、已读/未读管理

3. **API 设计问题**：
   - 对话 API 返回格式不统一（有时返回 single object，有时返回 array）
   - 缺少标准化的错误处理
   - 没有 WebSocket 支持双向通信

### 2.2 现有 Web 界面审核

#### 页面布局分析

**当前页面结构**：
```
/index.html (主页 - 对话中心 + 仪表盘)
├── 左侧导航栏（固定）
│   ├── 总裁办
│   │   ├── 仪表盘
│   │   ├── 个人助理
│   │   └── 三贤者决策
│   ├── 部门管理
│   │   ├── 共识管理
│   │   ├── 部门列表
│   │   └── 各职能部门
│   └── 任务管理
└── 主内容区
    ├── 仪表盘（任务统计卡片）
    ├── 总裁办对话区（已有 Chat UI 雏形）
    ├── 任务列表
    └── 其他功能模块
```

#### 优点 ✅
1. **导航结构清晰**：按组织架构划分，符合用户心智模型
2. **响应式设计**：支持移动端适配
3. **实时数据**：SSE 推送进度更新
4. **统一设计系统**：`design-system.css` 提供一致的视觉语言

#### 缺点 ❌
1. **对话体验不连贯**：
   - 对话区被限制在"总裁办"模块内，不是全局功能
   - 没有独立的对话历史侧边栏
   - 缺少消息输入区的快捷操作（附件、快捷命令等）
   - 无法在对话中直接查看任务详情

2. **信息过载**：
   - 主页同时展示对话、任务统计、Agent 活动，焦点不明确
   - 导航层级过深（4 层嵌套）

3. **缺少通知入口**：
   - 没有全局通知图标
   - 重要事件容易被忽略

### 2.3 API 审核

#### 现有 API 清单

**对话相关**：
- `GET /api/chat/history` - 获取对话历史
- `GET /api/chat/<chat_id>` - 获取对话详情
- `POST /api/chat/<chat_id>/message` - 发送消息
- `POST /api/chat/<task_id>/confirm_plan` - 确认执行计划
- `POST /api/task/<task_id>/complete` - 任务完成确认

**任务相关**：
- `GET /api/tasks` - 获取任务列表
- `POST /api/tasks` - 创建任务
- `PUT /api/tasks/<task_id>` - 更新任务
- `GET /api/tasks/<task_id>/history` - 任务历史

**通知相关**：
- `GET /api/progress/stream` - SSE 进度推送（唯一的通知机制）

#### API 改进建议
1. **新增通知中心 API**：
   - `GET /api/notifications` - 获取通知列表
   - `PUT /api/notifications/<id>/read` - 标记已读
   - `DELETE /api/notifications/<id>` - 删除通知
   - `WebSocket /api/ws/notifications` - 实时通知推送

2. **增强对话 API**：
   - `POST /api/chat` - 创建新对话（独立于任务）
   - `DELETE /api/chat/<chat_id>` - 删除对话
   - `PUT /api/chat/<chat_id>/title` - 重命名对话
   - `GET /api/chat/<chat_id>/export` - 导出对话记录

3. **标准化响应格式**：
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {
    "timestamp": "2026-04-07T12:00:00Z",
    "request_id": "req_123"
  }
}
```

## 三、UI 增强需求定义

### 3.0 核心概念：对话与任务的关系

#### 设计原则
> **对话是界面，任务是后台**  
> 用户通过对话表达需求，系统在背后创建和执行任务

#### 概念定义

**对话（Conversation）**：
- **本质**：用户与总裁办的**交互过程**
- **内容**：包含多轮消息往来（用户消息 + 系统回复）
- **目的**：理解用户需求、建立上下文、提供反馈
- **生命周期**：可以长期存在，支持多次交互
- **状态**：`active`（活跃）/ `archived`（归档）/ `deleted`（删除）

**任务（Task）**：
- **本质**：需要执行的**工作单元**
- **内容**：具体的执行步骤、进度、结果、交付物
- **目的**：完成具体工作
- **生命周期**：有明确的开始和结束
- **状态**：`pending` / `in_progress` / `completed` / `failed`

#### 关系模式

**模式 1：一个对话 → 多个任务**
```
对话："帮我规划下季度工作"
├─> 任务 1：市场分析（task-001）
├─> 任务 2：竞品调研（task-002）
└─> 任务 3：产品路线图（task-003）
```

**模式 2：多个对话 → 一个任务**
```
对话 1（周一）："我想做个新网站" → 创建任务 task-100
对话 2（周三）："网站进度如何？" → 查询任务 task-100
对话 3（周五）："网站能加个联系表单吗？" → 更新任务 task-100
```

**模式 3：纯对话（不产生任务）**
```
用户："今天心情不好"
总裁办："理解，要不要聊聊？或者我给您讲个笑话？"
（纯情感交流，不产生任务）
```

**模式 4：对话中嵌入任务卡片**
```
[对话流]
用户：帮我创建一个待办事项应用
总裁办：好的，正在为您规划...
       [任务卡片：task-200]
       ├─ 状态：in_progress
       ├─ 进度：30%
       └─ [查看详情] [暂停] [取消]
```

#### 数据模型设计

```python
# 对话模型
class Conversation:
    id: str                    # 对话 ID（如：conv_123）
    title: str                 # 对话标题
    user_id: str              # 用户 ID
    status: str               # active/archived/deleted
    created_at: datetime      # 创建时间
    updated_at: datetime      # 最后更新时间
    last_message_at: datetime # 最后一条消息时间
    message_count: int        # 消息数量
    related_task_ids: List[str]  # 关联的任务 ID 列表
    metadata: Dict            # 元数据（如意图分类、上下文等）

# 消息模型
class Message:
    id: str                   # 消息 ID
    conversation_id: str      # 所属对话 ID
    role: str                 # user/executive/system/task
    message_type: str         # text/plan/task/search/result/notification
    content: str              # 消息内容
    metadata: Dict            # 元数据（如任务 ID、搜索结果等）
    created_at: datetime      # 创建时间
    read: bool                # 是否已读

# 任务 - 对话关联模型
class TaskConversationLink:
    task_id: str              # 任务 ID
    conversation_id: str      # 对话 ID
    link_type: str            # created_from（创建自）/referenced_in（被提及）/updated_by（被更新）
    created_at: datetime      # 关联时间
```

### 3.1 对话式交互界面（Chat UI）增强

#### 用户故事
> 作为一人公司用户，我希望通过一个统一的对话界面与总裁办交互，让我能：
> - 随时随地发起新任务
> - 查看历史对话和任务进展
> - 在对话中直接确认计划、查看结果
> - 获得主动推送的重要通知

#### 功能需求

**FR1: 全局对话中心**
- [ ] 独立的对话中心页面（`/chat`）
- [ ] 左侧对话历史列表（支持搜索、筛选）
  - [ ] 按时间排序（最近对话置顶）
  - [ ] 按状态筛选（活跃/归档）
  - [ ] 显示未读消息数
  - [ ] 显示关联任务数
- [ ] 右侧主对话区
  - [ ] 消息列表（按时间倒序）
  - [ ] 消息输入区
  - [ ] 对话标题编辑
- [ ] 支持多对话标签页切换
  - [ ] 当前活跃对话
  - [ ] 最近 5 个对话快速切换

**FR2: 对话体验优化**
- [ ] 消息气泡样式优化（区分用户/总裁办/系统/任务）
  - [ ] 用户消息：右侧，蓝色背景
  - [ ] 总裁办消息：左侧，白色背景
  - [ ] 系统消息：居中，灰色背景
  - [ ] 任务消息：左侧，带任务卡片
- [ ] 输入区增强：
  - [ ] 快捷命令（`/task` 创建任务，`/report` 生成报告，`/search` 搜索）
  - [ ] 文件拖放上传（支持图片、文档）
  - [ ] 语音输入（可选，使用 Web Speech API）
  - [ ] 常用语模板（"进度如何"、"总结报告"、"暂停任务"）
  - [ ] @提及功能（@某个 Agent 或部门）
- [ ] 消息类型丰富化：
  - [ ] 文本消息（支持 Markdown 格式）
  - [ ] 任务卡片（可点击查看详情）
  - [ ] 计划确认卡片（带确认/修改按钮）
  - [ ] 搜索结果卡片（显示摘要和来源）
  - [ ] 图表/数据可视化（进度图、统计图）
  - [ ] 文件预览（图片、PDF 缩略图）

**FR3: 对话 - 任务一体化**
- [ ] 在对话中直接显示任务进度条
  - [ ] 进度条嵌入消息流
  - [ ] 实时更新（通过 WebSocket）
  - [ ] 点击跳转到任务详情
- [ ] 点击任务卡片弹出详情浮层（不离开对话）
  - [ ] 浮层显示：任务信息、执行步骤、当前进度、交付物
  - [ ] 浮层内操作：暂停、恢复、取消、重新分配
  - [ ] 浮层内对话：针对该任务的专门讨论
- [ ] 任务状态变更实时同步到对话
  - [ ] 任务开始 → 系统消息通知
  - [ ] 任务完成 → 结果卡片展示
  - [ ] 任务失败 → 错误提示 + 建议
- [ ] 支持在对话中追问任务相关问题
  - [ ] "task-123 进度如何？" → 自动识别任务 ID 并回复
  - [ ] "上上个任务完成了吗？" → 上下文理解
  - [ ] "把 task-456 的优先级提高" → 任务操作

**FR4: 对话上下文管理**
- [ ] 支持对话重命名
  - [ ] 自动命名（基于首条消息内容）
  - [ ] 手动编辑标题
- [ ] 支持对话归档/删除
  - [ ] 归档：移动到归档列表，保留历史记录
  - [ ] 删除：软删除（可恢复），7 天后彻底删除
- [ ] 支持对话搜索（全文检索）
  - [ ] 搜索消息内容
  - [ ] 搜索任务 ID
  - [ ] 搜索时间范围
  - [ ] 高亮显示搜索结果
- [ ] 支持对话导出（Markdown/PDF）
  - [ ] 导出为 Markdown（含消息时间戳）
  - [ ] 导出为 PDF（格式化排版）
  - [ ] 选择性导出（仅文本/含任务卡片）

### 3.2 通知中心 UI

#### 用户故事
> 作为一人公司用户，我希望有一个统一的通知中心，让我能：
> - 及时获知任务完成、失败、需要确认等事件
> - 按优先级处理通知
> - 追踪历史通知记录
> - 自定义通知偏好

#### 功能需求

**FR5: 通知展示**
- [ ] 全局通知铃铛图标（右上角，显示未读数量）
- [ ] 通知下拉面板（最近 10 条通知）
- [ ] 独立通知中心页面（`/notifications`）
- [ ] 通知分类展示（任务/系统/财务/人事）

**FR6: 通知类型与优先级**
- [ ] 定义通知类型：
  - **任务通知**：任务完成、失败、进度更新
  - **确认通知**：计划待确认、资源引入待确认
  - **系统通知**：系统维护、配置变更
  - **财务通知**：预算预警、账单提醒
  - **人事通知**：新 Agent 可用、技能缺口
- [ ] 优先级分级：
  - 🔴 紧急（需要立即处理）
  - 🟡 重要（今天内处理）
  - 🟢 普通（空闲时处理）
  - 🔵 信息（仅告知）

**FR7: 通知交互**
- [ ] 一键标记已读/全部已读
- [ ] 通知详情展开（富文本内容）
- [ ] 通知内操作（确认计划、引入 Agent 等）
- [ ] 通知跳转（点击跳转到相关页面）
- [ ] 通知删除/归档

**FR8: 实时推送**
- [ ] WebSocket 连接实时接收通知
- [ ] 浏览器桌面通知（需用户授权）
- [ ] 声音提示（可选）
- [ ] 通知免打扰模式

**FR9: 通知偏好设置**
- [ ] 按类型开关通知
- [ ] 按优先级过滤
- [ ] 设置免打扰时段
- [ ] 选择推送渠道（站内/邮件/钉钉等）

## 四、技术架构设计

### 4.1 前端架构

#### 新增组件结构
```
templates/
├── chat/
│   ├── index.html          # 对话中心主页
│   ├── chat_history.html   # 对话历史列表组件
│   ├── chat_window.html    # 对话窗口组件
│   └── message_types/      # 消息类型模板
│       ├── text_message.html
│       ├── task_card.html
│       ├── plan_card.html
│       └── search_result.html
├── notifications/
│   ├── index.html          # 通知中心主页
│   ├── notification_bell.html  # 全局铃铛组件
│   ├── notification_list.html  # 通知列表组件
│   └── notification_item.html  # 单条通知模板
└── shared/
    ├── header.html         # 顶部导航（含通知铃铛）
    └── sidebar.html        # 对话历史侧边栏

static/
├── js/
│   ├── chat/
│   │   ├── chat_app.js     # 对话应用主逻辑
│   │   ├── message_store.js # 消息状态管理
│   │   └── websocket.js    # WebSocket 连接
│   └── notifications/
│       ├── notification_store.js
│       └── notification_utils.js
└── css/
    ├── chat.css            # 对话样式
    └── notifications.css   # 通知样式
```

#### 技术选型
- **状态管理**：Vuex（如升级 Vue 3 则用 Pinia）或原生 JS 状态管理
- **WebSocket**：原生 WebSocket API + 自动重连机制
- **消息队列**：使用浏览器 Notification API
- **样式方案**：扩展现有 design-system.css

### 4.2 后端架构

#### 新增模块
```
opc_manager/
├── notification_manager.py    # 通知管理器
└── websocket_manager.py       # WebSocket 连接管理

web_interface/
├── routes/
│   ├── chat_routes.py         # 对话路由（重构）
│   └── notification_routes.py # 通知路由
└── websocket/
    ├── notification_ws.py     # 通知 WebSocket
    └── chat_ws.py             # 对话 WebSocket

models/
├── conversation.py            # 对话数据模型
└── notification.py            # 通知数据模型
```

#### 数据库 Schema 变更
```sql
-- 对话表
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    user_id TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_message_at TIMESTAMP,
    is_archived BOOLEAN DEFAULT FALSE
);

-- 消息表
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    role TEXT, -- user/executive/system/task
    content TEXT,
    message_type TEXT, -- text/plan/task/search/result
    metadata JSON,
    created_at TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- 通知表
CREATE TABLE notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    type TEXT, -- task/confirmation/system/finance/hr
    priority TEXT, -- urgent/important/normal/info
    title TEXT,
    content TEXT,
    related_object_type TEXT, -- task/agent/plan
    related_object_id TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    read_at TIMESTAMP
);
```

### 4.3 API 设计

#### 对话 API（重构）
```python
# 创建对话
POST /api/v2/chat
Request: { "title": "新对话", "initial_message": "你好" }
Response: { "id": "chat_123", "title": "新对话", ... }

# 获取对话列表
GET /api/v2/chat?page=1&limit=20&search=keyword
Response: { "items": [...], "total": 100 }

# 获取对话详情（含消息）
GET /api/v2/chat/{chat_id}?limit=50&before=message_id
Response: { "conversation": {...}, "messages": [...] }

# 发送消息
POST /api/v2/chat/{chat_id}/message
Request: { "content": "消息内容", "type": "text" }
Response: { "message": {...} }

# WebSocket 推送
WS /api/v2/ws/chat/{chat_id}
-> Server: { "type": "new_message", "data": {...} }
```

#### 通知 API（新增）
```python
# 获取通知列表
GET /api/v2/notifications?unread_only=true&page=1
Response: { "items": [...], "unread_count": 5 }

# 标记已读
PUT /api/v2/notifications/{id}/read
Response: { "success": true }

# 批量标记已读
PUT /api/v2/notifications/read-all?before=timestamp
Response: { "marked_count": 10 }

# 删除通知
DELETE /api/v2/notifications/{id}
Response: { "success": true }

# WebSocket 推送
WS /api/v2/ws/notifications
-> Server: { "type": "new_notification", "data": {...} }
```

## 五、实施计划

### 阶段 1: 基础架构（2 周）
- [ ] 设计数据库 Schema
- [ ] 实现 NotificationManager
- [ ] 实现 WebSocketManager
- [ ] 创建基础 API 路由

### 阶段 2: 对话中心重构（3 周）
- [ ] 创建独立对话中心页面
- [ ] 实现对话历史侧边栏
- [ ] 优化消息气泡样式
- [ ] 实现消息输入增强
- [ ] 集成 WebSocket 实时通信

### 阶段 3: 通知中心（2 周）
- [ ] 实现全局通知铃铛
- [ ] 创建通知中心页面
- [ ] 实现通知分类与过滤
- [ ] 集成浏览器桌面通知
- [ ] 实现通知偏好设置

### 阶段 4: 高级功能（2 周）
- [ ] 实现对话搜索
- [ ] 实现对话导出
- [ ] 实现语音输入（可选）
- [ ] 性能优化与测试

## 六、成功指标

### 用户体验指标
- **任务完成时间**：从发起到完成的平均时间缩短 30%
- **用户满意度**：NPS 评分 > 8
- **对话使用率**：> 80% 任务通过对话发起
- **通知响应时间**：紧急通知平均响应时间 < 5 分钟

### 技术指标
- **页面加载时间**：< 2 秒
- **WebSocket 连接稳定性**：> 99.9% 在线率
- **API 响应时间**：P95 < 200ms
- **消息推送延迟**：< 1 秒

## 七、风险与缓解

### 风险 1: 现有功能回归
**缓解措施**：
- 保持向后兼容（`/api/v1` vs `/api/v2`）
- 完整的回归测试套件
- 灰度发布，逐步切换流量

### 风险 2: WebSocket 连接资源消耗
**缓解措施**：
- 实现连接池管理
- 心跳检测与空闲断开
- 降级到 SSE 长轮询

### 风险 3: 数据一致性
**缓解措施**：
- 消息持久化 + 确认机制
- WebSocket 断线重连 + 消息补发
- 数据库事务保证

## 八、附录

### 8.1 竞品分析
- **Notion AI**：对话 + 文档一体化
- **Linear**：优秀的通知系统设计
- **Slack**：实时消息推送标杆

### 8.2 设计参考
- [Chat UI 设计模式](https://chatui.design/)
- [通知系统最佳实践](https://notification-systems.guide/)

---

**文档版本**: v1.0  
**创建时间**: 2026-04-07  
**审核人**: 产品经理、UI 设计师、架构师
