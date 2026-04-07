# OPC-Agents 测试计划

**版本**: 1.0  
**创建时间**: 2026-04-07  
**最后更新**: 2026-04-07

---

## 一、测试策略

### 1.1 测试层次

```
┌─────────────────────────────────┐
│   E2E 测试 (端到端测试)          │  ← 用户旅程
├─────────────────────────────────┤
│   集成测试 (模块间集成)          │  ← 业务流程
├─────────────────────────────────┤
│   单元测试 (单个模块/函数)       │  ← 代码逻辑
└─────────────────────────────────┘
```

### 1.2 测试类型

| 类型 | 目标 | 工具 | 覆盖率目标 |
|------|------|------|------------|
| 单元测试 | 验证单个函数/类 | pytest | > 80% |
| 集成测试 | 验证模块间协作 | pytest + 模拟数据 | 核心流程 100% |
| E2E 测试 | 验证完整用户旅程 | pytest + Selenium | 关键路径 100% |
| 性能测试 | 验证系统性能 | locust | P95 < 200ms |
| 回归测试 | 确保修改不破坏现有功能 | pytest | 100% 通过 |

---

## 二、测试范围

### 2.1 核心功能测试

#### 2.1.1 对话系统（Phase 1 新增）

**测试文件**: `tests/unit/test_conversation_notification.py`

| 测试项 | 测试内容 | 状态 |
|--------|----------|------|
| ConversationManager.create_conversation | 创建对话，含初始消息 | ✅ 已覆盖 |
| ConversationManager.get_conversation | 获取对话详情 | ✅ 已覆盖 |
| ConversationManager.list_conversations | 分页查询，状态过滤，搜索 | ✅ 已覆盖 |
| ConversationManager.add_message | 添加消息，更新统计 | ✅ 已覆盖 |
| ConversationManager.get_messages | 分页查询消息 | ✅ 已覆盖 |
| ConversationManager.link_task_to_conversation | 关联任务到对话 | ✅ 已覆盖 |
| ConversationManager.archive_conversation | 归档对话 | ✅ 已覆盖 |
| ConversationManager.delete_conversation | 软删除对话 | ✅ 已覆盖 |
| NotificationManager.create_notification | 创建通知 | ✅ 已覆盖 |
| NotificationManager.get_notifications | 获取通知列表，分页 | ✅ 已覆盖 |
| NotificationManager.mark_as_read | 标记已读 | ✅ 已覆盖 |
| NotificationManager.mark_all_as_read | 批量标记已读 | ✅ 已覆盖 |
| NotificationManager.get_unread_count | 获取未读数 | ✅ 已覆盖 |
| NotificationManager.delete_notification | 删除通知 | ✅ 已覆盖 |

**覆盖率**: 14/14 核心功能（100%）  
**测试通过率**: 14/14（100%）

#### 2.1.2 任务执行系统

**测试文件**: `tests/integration/scenarios/test_scenario_*.py`

| 测试场景 | 测试用例数 | 状态 |
|----------|-----------|------|
| 完整任务流程 | 4 | ✅ 100% 通过 |
| 经验库学习 | 5 | ✅ 100% 通过 |
| 多任务/错误/恢复 | 3 | ✅ 100% 通过 |

**覆盖率**: 12/12 集成测试（100%）

#### 2.1.3 智能化改进

**测试文件**: `tests/unit/test_*.py`

| 模块 | 测试用例数 | 状态 |
|------|-----------|------|
| 错误处理 | 15 | ✅ 已覆盖 |
| 通知系统 | 12 | ✅ 已覆盖 |
| 优先级推荐 | 8 | ✅ 已覆盖 |
| 资源监控 | 7 | ✅ 已覆盖 |
| 任务历史 | 10 | ✅ 已覆盖 |

**覆盖率**: 52/52 测试（100%）

#### 2.1.4 技能系统

**测试文件**: `tests/skills/test_*.py`

| 技能 | 测试用例数 | 状态 |
|------|-----------|------|
| 网页搜索 | 5 | ✅ 已覆盖 |
| 文档处理 | 5 | ✅ 已覆盖 |
| 内容摘要 | 5 | ✅ 已覆盖 |
| 其他技能 | 5 | ✅ 已覆盖 |

**覆盖率**: 20/20 测试（100%）

#### 2.1.5 工作流引擎

**测试文件**: `tests/unit/test_workflow_engine.py`

| 测试项 | 测试用例数 | 状态 |
|--------|-----------|------|
| 状态机转换 | 3 | ✅ 已覆盖 |
| 条件分支 | 3 | ✅ 已覆盖 |
| 变量模板 | 2 | ✅ 已覆盖 |
| 暂停/恢复 | 2 | ✅ 已覆盖 |

**覆盖率**: 10/10 测试（100%）

### 2.2 待补充测试

#### 2.2.1 API 集成测试（计划中）

**测试文件**: `tests/integration/test_api_v2.py`

| API | 测试内容 | 优先级 | 状态 |
|-----|----------|--------|------|
| POST /api/v2/chat | 创建对话 | P0 | ⏳ 待开发 |
| GET /api/v2/chat | 获取对话列表 | P0 | ⏳ 待开发 |
| GET /api/v2/chat/{id} | 获取对话详情 | P0 | ⏳ 待开发 |
| POST /api/v2/chat/{id}/message | 发送消息 | P0 | ⏳ 待开发 |
| GET /api/v2/notifications | 获取通知列表 | P0 | ⏳ 待开发 |
| PUT /api/v2/notifications/{id}/read | 标记已读 | P0 | ⏳ 待开发 |
| DELETE /api/v2/notifications/{id} | 删除通知 | P0 | ⏳ 待开发 |

**预计完成**: Phase 1 Week 2

#### 2.2.2 前端 UI 测试（计划中）

**测试文件**: `tests/e2e/test_ui.py`

| 功能 | 测试内容 | 优先级 | 状态 |
|------|----------|--------|------|
| 通知铃铛 | 显示未读数，点击展开 | P0 | ⏳ 待开发 |
| 通知下拉面板 | 显示最近通知，标记已读 | P0 | ⏳ 待开发 |
| 对话中心页面 | 加载对话列表，发送消息 | P0 | ⏳ 待开发 |
| 对话历史侧边栏 | 切换对话，搜索对话 | P1 | ⏳ 待开发 |
| 任务卡片 | 点击查看详情，进度同步 | P0 | ⏳ 待开发 |

**预计完成**: Phase 1 Week 2

#### 2.2.3 性能测试（计划中）

**测试文件**: `tests/performance/test_performance.py`

| 测试项 | 性能指标 | 目标值 | 状态 |
|--------|----------|--------|------|
| 对话列表加载 | P95 响应时间 | < 200ms | ⏳ 待测试 |
| 通知列表加载 | P95 响应时间 | < 100ms | ⏳ 待测试 |
| 消息推送延迟 | 平均延迟 | < 1s | ⏳ 待测试 |
| WebSocket 并发 | 最大连接数 | > 1000 | ⏳ 待测试 |
| 数据库查询 | 索引命中率 | > 95% | ⏳ 待测试 |

**预计完成**: Phase 2

---

## 三、测试环境

### 3.1 环境配置

```yaml
# 测试环境配置
test_environment:
  python_version: 3.9+
  os: macOS / Linux
  database: SQLite (in-memory for unit tests)
  
  dependencies:
    - pytest>=7.0
    - pytest-cov>=3.0
    - pytest-html>=3.1
    - requests>=2.28
    - flask>=2.0
    
  test_data:
    - 模拟用户数据
    - 模拟任务数据
    - 模拟对话数据
    - 模拟通知数据
```

### 3.2 CI/CD 集成

```yaml
# GitHub Actions 工作流（待实现）
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-html
    
    - name: Run unit tests
      run: |
        pytest tests/unit/ -v --cov=opc_manager --cov-report=xml
    
    - name: Run integration tests
      run: |
        pytest tests/integration/ -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## 四、测试执行

### 4.1 本地执行

```bash
# 运行所有测试
python3 -m pytest tests/ -v

# 运行特定模块测试
python3 -m pytest tests/unit/test_conversation_notification.py -v

# 运行测试并生成覆盖率报告
python3 -m pytest tests/ -v --cov=opc_manager --cov-report=html

# 运行测试并生成 HTML 报告
python3 -m pytest tests/ -v --html=reports/test_report.html
```

### 4.2 测试报告

**测试报告内容**:
- 测试总览（总数/通过/失败/跳过）
- 按模块分类统计
- 失败测试详情（错误信息/堆栈跟踪）
- 覆盖率统计
- 性能指标（如适用）

**报告位置**: `reports/test_report_*.html`

---

## 五、缺陷管理

### 5.1 缺陷分级

| 级别 | 说明 | 响应时间 |
|------|------|----------|
| Critical | 系统崩溃/数据丢失 | 立即修复 |
| Major | 核心功能失效 | 24 小时内 |
| Minor | 非核心功能问题 | 下次迭代 |
| Trivial | 界面/文档小问题 | 有空时修复 |

### 5.2 缺陷流程

```
发现缺陷 → 记录到 Issue → 分级 → 分配 → 修复 → 测试 → 关闭
```

### 5.3 缺陷追踪

使用 GitHub Issues 追踪缺陷：
- 标签：`bug`, `critical`, `major`, `minor`
- 指派给相应开发人员
- 关联到相关 PR

---

## 六、质量指标

### 6.1 代码质量

| 指标 | 目标值 | 当前值 | 状态 |
|------|--------|--------|------|
| 单元测试覆盖率 | > 80% | 85% | ✅ 达标 |
| 集成测试通过率 | 100% | 100% | ✅ 达标 |
| Critical Bug 数 | 0 | 0 | ✅ 达标 |
| 代码审查通过率 | 100% | 100% | ✅ 达标 |

### 6.2 性能质量

| 指标 | 目标值 | 当前值 | 状态 |
|------|--------|--------|------|
| API P95 响应时间 | < 200ms | TBD | ⏳ 待测试 |
| 页面加载时间 | < 2s | TBD | ⏳ 待测试 |
| 消息推送延迟 | < 1s | TBD | ⏳ 待测试 |
| WebSocket 在线率 | > 99.9% | TBD | ⏳ 待测试 |

---

## 七、持续改进

### 7.1 测试改进计划

**Phase 1 (Week 1-2)**:
- ✅ 完成对话/通知单元测试
- ⏳ 完成 API 集成测试
- ⏳ 完成前端 UI 测试

**Phase 2 (Week 3-4)**:
- ⏳ 添加性能测试
- ⏳ 添加 WebSocket 测试
- ⏳ 添加 E2E 测试

**Phase 3 (Week 5-6)**:
- ⏳ 添加负载测试
- ⏳ 添加安全性测试
- ⏳ 自动化测试覆盖率 > 90%

### 7.2 测试工具改进

- [ ] 引入测试数据工厂（factory_boy）
- [ ] 引入测试夹具（pytest fixtures）优化
- [ ] 引入 Mock 服务器（responses）
- [ ] 引入 UI 自动化（Selenium）
- [ ] 引入性能测试工具（locust）

---

## 八、测试总结

### 8.1 当前测试状态

**总计**: 253 个测试通过，4 个跳过，0 个失败  
**覆盖率**: 85% 代码覆盖率  
**质量**: 所有核心功能测试通过，无 Critical Bug

### 8.2 下一步行动

1. **Week 2**: 完成 API 集成测试和前端 UI 测试
2. **Week 3**: 开始性能测试和优化
3. **Week 4**: 完善 E2E 测试和自动化测试

---

**测试负责人**: 测试经理  
**审核周期**: 每周更新  
**分发范围**: 全体开发团队
