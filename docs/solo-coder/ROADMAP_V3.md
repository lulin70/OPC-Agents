# OPC-Agents 开发路线图 v3.0 (Phase 3)

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v3.0.0 | 2026-04-15 | 独立开发者 | Phase 3完整路线图：Web UI / LLM / DB / 适配器 / CI-CD | 待审核 |
| v2.1.0 | 2026-04-14 | 独立开发者 | Phase 2路线图：3人格+DetectorV2+Flywheel | 已审核 |

---

## 一、Phase 3 目标与成功标准

### 1.1 核心目标

```
OPC-Agents v3.0 = 可交互的产品（而非仅是库）

从 v2.2.0 到 v3.0 的质变：
  ❌ v2.2.0: Python库，需要写代码调用
  ✅ v3.0:   Web应用，浏览器打开即用
```

### 1.2 成功标准 (DoD)

- [ ] **Web UI 可访问**: 浏览器打开 localhost 能看到完整界面
- [ ] **对话功能正常**: 发送消息能收到带人格风格的回复
- [ ] **飞轮可视化**: 仪表盘展示等级和5维评分
- [ ] **LLM 集成生效**: 复杂句子检测准确率提升至 ≥90%
- [ ] **数据持久化**: 重启应用后飞轮数据和会话历史不丢失
- [ ] **外部适配器可用**: Mock 适配器返回合理假数据
- [ ] **CI/CD 运行**: GitHub Actions 流水线自动跑通
- [ ] **测试达标**: 总测试数 ≥ 110；覆盖率 ≥ 87%；全部通过
- [ ] **回归保障**: Phase 1 + 2 的 65 个旧测试仍然全部通过
- [ ] **文档更新**: README 更新至 v3.0；部署指南可用

---

## 二、任务分解

### 2.1 任务总览

```
Phase 3 任务依赖图
═════════════════

P3-T01: 项目结构搭建
    │
    ├─→ P3-T02: 数据模型 (ORM)
    │       │
    │       ├─→ P3-T03: FlywheelTracker DB改造
    │       │       │
    │       │       ├─→ P3-T04: LLM 服务层
    │       │       │       │
    │       │       │       ├─→ P3-T05: Detector V2 + LLM 集成
    │       │       │       │
    │       │       │       └─→ P3-T06: Web API (FastAPI)
    │       │       │               │
    │       │       │               ├─→ P3-T07: Streamlit 前端
    │       │       │               │
    │       │       │               └─→ P3-T08: 外部平台适配器
    │       │       │
    │       │       └─→ P3-T09: 会话历史存储
    │       │
    │       └─→ P3-T10: 数据迁移脚本
    │
    ├─→ P3-T11: Phase 3 测试编写
    │       │
    │       ├─→ P3-T12: 全量回归测试
    │       │
    │       └─→ P3-T13: CI/CD Pipeline 配置
    │
    └─→ P3-T14: 文档更新 + Git 推送
```

### 2.2 详细任务定义

#### P3-T01: 项目结构搭建

| 属性 | 内容 |
|------|------|
| **ID** | P3-T01 |
| **名称** | 创建 Phase 3 目录结构和基础配置文件 |
| **优先级** | P0 |
| **依赖** | 无 |
| **估算** | 0.5h |
| **验收标准** | `web_app/`, `frontend/`, `db_models/`, `tests/test_phase3/` 目录存在；`requirements.txt` 包含 FastAPI/Streamlit/SQLAlchemy/httpx |

**具体工作**：
1. 创建目录结构（参考架构文档 2.1.2）
2. 更新 `requirements.txt` 添加新依赖
3. 创建 `web_app/config.py` 环境变量配置
4. 创建 `.env.example` 模板文件

#### P3-T02: 数据模型 (ORM)

| 属性 | 内容 |
|------|------|
| **ID** | P3-T02 |
| **名称** | 实现 SQLAlchemy ORM 数据模型 |
| **优先级** | P0 |
| **依赖** | P3-T01 |
| **估算** | 1h |
| **验收标准** | `db_models/models.py` 包含 User/FlywheelState/Conversation/Message/ScenarioExecution/LLMUsageLog 六个模型；`alembic.ini` 初始化完成 |

**具体工作**：
1. 编写 `db_models/__init__.py`
2. 编写 `db_models/models.py`（参考架构文档 2.3.1）
3. 初始化 Alembic 迁移工具
4. 编写数据库连接管理 (`db_models/database.py`)
5. 编写基础 CRUD 测试

#### P3-T03: FlywheelTracker DB 改造

| 属性 | 内容 |
|------|------|
| **ID** | P3-T03 |
| **名称** | 将 FlywheelTracker 从内存存储迁移到数据库持久化 |
| **优先级** | P0 |
| **依赖** | P3-T02 |
| **估算** | 1.5h |
| **验收标准** | `FlywheelTrackerDB` 类可正常读写数据库；重启后数据不丢失；原有 65 个测试不受影响 |

**具体工作**：
1. 在 `flywheel_tracker.py` 中添加 `FlywheelTrackerDB` 类（参考架构文档 2.3.2）
2. 保持原 `FlywheelTracker` 不变（向后兼容）
3. 添加 `_load_from_db()` 和 `_save_to_db()` 方法
4. 编写 DB 版本的 FlywheelTracker 测试（≥8个）

#### P3-T04: LLM 服务层

| 属性 | 内容 |
|------|------|
| **ID** | P3-T04 |
| **名称** | 实现完整的 LLM 服务抽象层和三个后端实现 |
| **优先级** | P0 |
| **依赖** | P3-T01 |
| **估算** | 2h |
| **验收标准** | `opc_manager/llm_service.py` 存在且包含 LLMService/LLMBackend/OpenAIBackend/OllamaBackend/MockLLMBackend/UsageTracker；Mock 后端测试全部通过（≥10个） |

**具体工作**：
1. 编写 `opc_manager/llm_service.py`（参考架构文档 2.2.1）
2. 实现 `LLMBackend` 抽象基类
3. 实现 `MockLLMBackend`（含 detect_type mock 响应）
4. 实现 `OpenAIBackend`（异步 HTTP 调用）
5. 实现 `OllamaBackend`（本地模型调用）
6. 实现 `LLMService` 统一入口和 `UsageTracker`
7. 编写完整测试套件（≥12个）

#### P3-T05: Detector V2 + LLM 集成

| 属性 | 内容 |
|------|------|
| **ID** | P3-T05 |
| **名称** | 在 Detector V2 中集成 LLM 辅助检测（混合策略） |
| **优先级** | P0 |
| **依赖** | P3-T04 |
| **估算** | 1h |
| **验收标准** | `BusinessTypeDetectorV2.__init__` 支持 `enable_llm` 和 `llm_service` 参数；置信度<0.7 时自动触发 LLM 兜底；原有关键词检测逻辑不受影响 |

**具体工作**：
1. 修改 `business_type_detector_v2.py` 的 `__init__` 和 `detect()` 方法
2. 添加 `_detect_original()` 保留原有逻辑
3. 在 `detect()` 末尾添加 LLM 兜底逻辑（参考架构文档 2.2.2）
4. 编写混合检测策略测试（≥5个）

#### P3-T06: Web API (FastAPI)

| 属性 | 内容 |
|------|------|
| **ID** | P3-T06 |
| **名称** | 实现 FastAPI REST API 后端 |
| **优先级** | P0 |
| **依赖** | P3-T03, P3-T05 |
| **估算** | 2.5h |
| **验收标准** | `uvicorn` 启动无报错；`/docs` 页面可访问 OpenAPI 文档；`POST /api/v1/chat/message` 返回有效 JSON；`GET /api/v1/health` 返回状态正常 |

**具体工作**：
1. 编写 `web_app/main.py`（FastAPI 应用入口）
2. 编写 `web_app/config.py`（环境变量加载）
3. 编写 `web_app/dependencies.py`（依赖注入）
4. 编写 `web_app/schemas/` （Pydantic 模型）
5. 编写 `web_app/routes/chat.py`（对话接口）
6. 编写 `web_app/routes/flywheel.py`（飞轮数据接口）
7. 编写 `web_app/routes/health.py`（健康检查）
8. 编写 `web_app/middleware/error_handler.py`（统一错误处理）
9. 编写 API 测试（≥15个）

#### P3-T07: Streamlit 前端

| 属性 | 内容 |
|------|------|
| **ID** | P3-T07 |
| **名称** | 实现 Streamlit 前端界面 |
| **优先级** | P0 |
| **依赖** | P3-T06 |
| **估算** | 2h |
| **验收标准** | `streamlit run frontend/app.py` 启动成功；聊天页面可发送消息并收到回复；仪表盘页面显示飞轮数据；6种人格卡片可切换显示 |

**具体工作**：
1. 编写 `frontend/app.py`（Streamlit 入口和多页面路由）
2. 编写 `frontend/pages/chat.py`（聊天界面）
3. 编写 `frontend/pages/dashboard.py`（飞轮仪表盘）
4. 编写 `frontend/pages/settings.py`（设置页面）
5. 编写 `frontend/components/persona_card.py`（人格卡片组件）
6. 手动验证前端交互

#### P3-T08: 外部平台适配器

| 属性 | 内容 |
|------|------|
| **ID** | P3-T08 |
| **名称** | 实现平台适配器抽象基类和 Mock 适配器 |
| **优先级** | P1 |
| **依赖** | P3-T01 |
| **估算** | 1.5h |
| **验收标准** | `opc_manager/platform_adapters.py` 存在；`PlatformAdapter` 抽象类定义完整；`MockXiaohongshuAdapter` 和 `MockGumroadAdapter` 可用；`AdapterFactory` 正确缓存实例 |

**具体工作**：
1. 编写 `opc_manager/platform_adapters.py`（参考架构文档 2.4）
2. 实现 `PlatformAdapter` 抽象基类
3. 实现 `MockXiaohongshuAdapter`（含10条模拟热点数据）
4. 实现 `MockGumroadAdapter`
5. 实现 `AdapterFactory` 工厂类
6. 编写适配器测试（≥10个）

#### P3-T09: 会话历史存储

| 属性 | 内容 |
|------|------|
| **ID** | P3-T09 |
| **名称** | 实现对话记录的数据库存储和查询 |
| **优先级** | P1 |
| **依赖** | P3-T02, P3-T06 |
| **估算** | 1h |
| **验收标准** | 发送消息后可在 `/api/v1/chat/history` 查询到历史记录；分页查询正常；删除会话功能正常 |

**具体工作**：
1. 在 `chat_service.py` 中添加会话创建/消息保存逻辑
2. 实现 history API 的数据库查询
3. 添加分页支持
4. 编写会话历史测试（≥5个）

#### P3-T10: 数据迁移脚本

| 属性 | 内容 |
|------|------|
| **ID** | P3-T10 |
| **名称** | 编写内存数据到数据库的迁移工具 |
| **优先级** | P1 |
| **依赖** | P3-T03 |
| **估算** | 0.5h |
| **验收标准** | `scripts/migrate_to_db.py` 可一键执行；迁移后数据完整性验证通过 |

**具体工作**：
1. 编写 `scripts/migrate_to_db.py`
2. 支持回滚操作
3. 编写迁移测试

#### P3-T11: Phase 3 测试编写

| 属性 | 内容 |
|------|------|
| **ID** | P3-T11 |
| **名称** | 编写所有 Phase 3 新功能的测试用例 |
| **优先级** | P0 |
| **依赖** | P3-T04, P3-T06, P3-T08, P3-T03 |
| **估算** | 2h |
| **验收标准** | 新增测试数 ≥ 45；新测试全部通过；总测试数 ≥ 110 |

**具体工作**：
1. 编写 `tests/test_llm_service.py`（≥12个）
2. 编写 `tests/test_web_api.py`（≥15个）
3. 编写 `tests/test_db_models.py`（≥10个）
4. 编写 `tests/test_platform_adapters.py`（≥10个）
5. 编写 `tests/test_flywheel_tracker_db.py`（≥8个）

#### P3-T12: 全量回归测试

| 属性 | 内容 |
|------|------|
| **ID** | P3-T12 |
| **名称** | 执行全量回归测试确保旧功能不受影响 |
| **优先级** | P0 |
| **依赖** | P3-T11 |
| **估算** | 0.5h |
| **验收标准** | Phase 1 (23) + Phase 2 (27) + Phase 3 新增 (45+) 全部通过；总覆盖率 ≥ 87% |

**具体工作**：
1. 运行 `pytest tests/ -v --cov=opc_manager --cov=web_app --cov=db_models`
2. 分析覆盖率报告
3. 修复任何失败的测试或覆盖率不足的模块

#### P3-T13: CI/CD Pipeline 配置

| 属性 | 内容 |
|------|------|
| **ID** | P3-T13 |
| **名称** | 配置 GitHub Actions 自动化流水线 |
| **优先级** | P1 |
| **依赖** | P3-T12 |
| **估算** | 1h |
| **验收标准** | `.github/workflows/ci-cd-v3.yml` 存在；push 到 main 分支自动触发测试；测试结果可在 Actions 页面查看 |

**具体工作**：
1. 编写 `.github/workflows/ci-cd-v3.yml`（参考测试计划 第六章）
2. 配置单元测试 job
3. 配置集成测试 job（含 PostgreSQL service）
4. 配置代码质量检查 job（flake8 + bandit）
5. 手动触发一次 workflow 验证

#### P3-T14: 文档更新 + Git 推送

| 属性 | 内容 |
|------|------|
| **ID** | P3-T14 |
| **名称** | 更新 README 和所有相关文档，推送到 Git |
| **优先级** | P0 |
| **依赖** | P3-T12, P3-T13 |
| **估算** | 1h |
| **验收标准** | README.md 更新至 v3.0；版本号变更说明清晰；Git commit 并 push 成功 |

**具体工作**：
1. 更新 `README.md` 至 v3.0
2. 更新 `CHANGELOG.md`
3. Git add + commit + push

---

## 三、里程碑时间线

```
Week 1 (Day 1-3): 核心基础设施
  Day 1 (上午):  P3-T01 项目结构搭建
  Day 1 (下午):  P3-T02 数据模型 ORM
  Day 2 (全天):   P3-T03 FlywheelTracker DB改造
  Day 3 (上午):  P3-T04 LLM 服务层
  Day 3 (下午):  P3-T05 Detector V2 + LLM 集成

Week 1 (Day 4-5): Web 应用
  Day 4 (全天):   P3-T06 FastAPI 后端
  Day 5 (全天):   P3-T07 Streamlit 前端

Week 2 (Day 6-7): 扩展功能
  Day 6 (上午):  P3-T08 外部平台适配器
  Day 6 (下午):  P3-T09 会话历史存储 + P3-T10 迁移脚本
  Day 7 (全天):   P3-T11 Phase 3 测试编写

Week 2 (Day 8-9): 质量保障
  Day 8 (上午):  P3-T12 全量回归测试
  Day 8 (下午):  P3-T13 CI/CD Pipeline
  Day 9 (全天):   P3-T14 文档更新 + Git 推送

总计: 约 15 小时有效工作时间
```

---

## 四、技术债务清单

| ID | 债务描述 | 影响 | 处理计划 | 优先级 |
|----|---------|------|---------|--------|
| TD-01 | `business_type_detector.py` (V1) 仍保留但已废弃 | 代码冗余 | Phase 3 标记为 deprecated，Phase 4 清除 | 低 |
| TD-02 | FlywheelTracker 内存版和 DB 版并存 | 维护两份代码 | Phase 3 逐步迁移调用方到 DB 版 | 中 |
| TD-03 | 缺少统一的日志框架 | 调试困难 | Phase 3 引入 structlog 或 logging 统一配置 | 中 |
| TD-04 | 配置散落在多个文件 | 部署复杂 | Phase 3 统一到 config.py + .env | 高 |
| TD-05 | 异步处理不完善 | 性能瓶颈 | Phase 3 先同步实现，后续优化 | 低 |

---

## 五、风险识别与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| FastAPI + Streamlit 集成复杂度超预期 | 中 | 中 | 先保证 API 独立可用，前端后续迭代 |
| SQLAlchemy 版本兼容问题 | 低 | 中 | 锁定版本号在 requirements.txt |
| LLM API Key 未配置导致测试失败 | 高 | 低 | 默认使用 Mock 后端，真实 API 仅在手动测试启用 |
| 数据库迁移破坏现有数据 | 低 | 高 | 迁移脚本先备份，支持回滚 |
| GitHub Actions 配置错误 | 中 | 中 | 参考 test-expert 提供的标准 YAML |

---

## 六、代码规范补充（Phase 3 更新）

### 6.1 新增规范

1. **FastAPI 路由**: 所有路由函数必须有 docstring 说明用途
2. **Pydantic 模型**: 所有字段必须有 Field 描述和约束
3. **async/await**: I/O 密集操作必须使用异步；纯计算保持同步
4. **数据库操作**: 必须通过 ORM，禁止 raw SQL
5. **环境变量**: 所有敏感信息通过 `os.environ` 或 `pydantic-settings` 读取
6. **错误处理**: API 层统一异常捕获，返回标准化错误格式

### 6.2 API 文档要求

每个新增 API 端点需包含：
- OpenAPI/Swagger 自动生成的文档
- 请求/响应示例
- 错误码说明
- 认证方式说明

---

**文档状态**：✅ 初稿完成 | ⏳ 待产品经理确认需求对齐 | ⏳ 待架构师确认技术可行性 | ⏳ 待测试专家确认测试覆盖 | ⏳ 待多角色共识

**下一步**：召开多角色共识评审会议
