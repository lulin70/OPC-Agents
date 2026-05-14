# Changelog

All notable changes to OPC-Agents will be documented in this file.

## [0.1.8] - 2026-05-14

### Added

- 21个内置业务技能（P0: email/finance/task/crm, P1: social/proposal/invoice/report/calendar, P2: competitor/pricing/tax_reminder/dashboard/knowledge）
- 外部技能市场（SkillMarketplace）：搜索、安装、管理第三方技能
- MCP服务发现：搜索和连接MCP协议服务器
- 用户画像（UserProfile）：偏好记录、使用模式分析、技能推荐
- 技能间协作机制：CRM→Email、Finance→Tax、Deal→Income
- AES加密：邮件密码、客户敏感字段加密存储
- SQLite统一存储：所有数据迁移到SQLite，消除JSON双轨制
- 数据库迁移机制：版本管理、安全升级
- 事务支持：execute_transaction() 原子操作
- 用户偏好持久化：user_preferences表
- 交互日志：interaction_log表

### Security

- 加密强制密钥：`OPC_ENCRYPTION_KEY` 未设置时 `encrypt_field()` 抛出 `RuntimeError`，拒绝使用默认密钥加密
- 外部技能沙箱隔离：UNVERIFIED信任等级技能禁止安装
- 网络白名单：外部技能网络请求仅允许 `registry.opc-agents.dev`、`api.github.com`、`mcphub.io` 及其子域
- SQL参数化：所有数据库操作使用参数化查询，防止SQL注入
- STARTTLS强制：SMTP非SSL连接强制要求STARTTLS，不支持则拒绝发送
- AES加密：邮件密码、客户手机号/邮箱加密存储
- SQLite文件权限0600
- MCP连接强制HTTPS
- 信任等级体系（official/verified/community/unverified）

### Architecture

- intent_types.py独立模块：`IntentType`枚举、`INTENT_KEYWORDS`、`INTENT_STEP_MAP`、`SKILL_INTENT_MAP` 提取为SSOT
- SkillRegistry单例模式：`__new__` 实现全局唯一实例，线程安全
- execute_goal委托：14个技能模块统一提供 `execute_goal(goal, _context, **kwargs)` 入口
- BUSINESS_OPERATION TaskType：新增业务操作任务类型，email/finance/task/crm/invoice/calendar/tax_reminder路由至此

### Performance

- get_trend()：精确月份计算，逐月聚合查询
- get_week_schedule()：单查询BETWEEN替代7次逐日查询
- generate_annual_report()：聚合查询 `GROUP BY ym, type` 替代逐月循环
- send_email_async()：异步邮件发送，`run_in_executor` 非阻塞

### Changed

- gen_id()从12位扩展到16位（进一步降低碰撞风险）
- 日志统一 `%s` 格式（loguru兼容）
- 社媒平台配置外置为 `data/knowledge/social_platforms.json`
- 定价基准外置为 `data/knowledge/pricing_benchmarks.json`
- DATA_DIR统一由 `OPC_DATA_DIR` 环境变量控制，所有模块引用同一常量

### Fixed

- social_skill不再写入email_history表（数据混淆）
- competitor_skill不再写入customers表（数据污染）
- 邮件同一收件人1小时频率限制
- 邮件正文50KB大小限制

## [0.1.9-delta] - 2026-05-09

### Added — v0.1.9-delta 真实运行验证（V2-1到V2-7）

#### V2-1: 三贤者LLM驱动升级
- 策略脑(StrategistBrain)：LLM驱动意图理解+LLM驱动执行计划生成
- 反思脑(ReflectorBrain)：LLM驱动结果评估
- AgentLoop：新增`llm_service`参数，传递给策略脑和反思脑
- 前端：AgentLoop初始化时注入LLMEnhancedContentGenerator

#### V2-3: 技能市场API服务化
- 新增 `skill_marketplace_api.py`: FastAPI REST服务

#### V2-4: MCP协议真实对接
- 新增 `mcp_transport.py`: SSE + stdio 传输层

#### V2-5: 插件示例+热加载
- 新增 `plugins/text_summarizer.py`: 文本摘要生成器示例
- 新增 `plugins/data_converter.py`: JSON→Markdown表格转换器示例

#### V2-6: 技能编辑器Streamlit UI
- 前端侧边栏新增"技能编辑器"按钮

#### V2-7: 性能调优
- 新增 `performance_monitor.py`: 性能监控与SLA管理

### Testing
- 新增20个delta集成测试
- 全量测试：470 passed, 21 skipped

## [0.1.9-gamma] - 2026-05-09

### Added — v0.1.9-gamma 整改优化（G1-G9全任务）

- AgentLoop接入主流程（TaskEngineAdapter适配器层）
- 策略脑替代IntentClassifier
- 反思脑质量把关（总超时60秒）
- 共识引擎集成（决策日志持久化）
- 执行进度可视化（质量/快速模式切换）
- 技能市场API（SkillMarketplace：注册/发现/调用）
- MCP协议支持（MCPServer：工具/资源/提示词）
- 插件系统（PluginManager+PluginSandbox沙箱隔离）
- 自定义技能编辑器（SkillEditor：表单式技能配置）

### Testing
- 新增42个gamma集成测试
- 全量测试：450 passed, 21 skipped

## [0.1.9] - 2026-05-09

### Added — PHASE3 端到端闭环

- 长会话上下文传递（session_id参数+SessionContextManager集成）
- 结果验证与自动修正（CorrectionStrategy+ReflectorBrain+最多2次修正）
- 多技能编排（复合意图拆解+子意图编排）
- 任务暂停/恢复（PAUSED状态+30分钟超时自动取消）
- 执行进度可视化（EventEmitter+事件流）

### Testing
- 新增22个PHASE3端到端闭环集成测试
- 408 tests passing, 21 skipped, 0 failures

## [0.1.8] - 2026-05-08

### Added — PHASE2 核心技能开发

- SkillContext数据类（技能间上下文传递）
- 搜索增强技能（WebSearchMCP+SearchResultProcessor）
- 商业分析技能（LLM增强+SWOT模板+规则引擎降级）
- 内容创作技能（智能模板选择+搜索→创作闭环）
- 文件操作技能（4种操作+ToolSystem对接）
- 消息通知技能（CRLF注入防护）

### Changed — 架构/性能/可维护性专项整改
- 综合评分从89.6提升至92.4

### Testing
- 373 tests passing, 21 skipped, 0 failures

## [0.1.7] - 2026-05-07

### Added — 三贤者架构 (PLAN B)

- StrategistBrain（策略脑）、ExecutorBrain（执行脑）、ReflectorBrain（反思脑）
- ConsensusEngine（共识引擎）、AgentLoop（执行循环）
- SkillRegistry（技能注册表）、ToolSystem（工具调用框架）
- 安全控制（命令注入/路径穿越/输入长度/审计日志）

### Testing
- 373 tests passing, 21 skipped, 0 failures

## [0.1.6] - 2026-05-03

### Added
- 首次用户引导、空状态示例、质量反馈、成果物搜索

### Fixed
- AsyncTaskExecutor重复重试、zombie扫描时间基准、PBKDF2盐值硬编码、XML标签注入

### Testing
- 350 tests passing, 21 skipped, 0 failures

## [0.1.5] - 2026-05-03

### Added
- 多轮对话增强、质量门禁、安全测试套件、Ollama后端支持

### Fixed
- enriched_input未传递到LLM、is_follow_up未传递、XSS修复

### Testing
- 350+ tests passing, 21 skipped, 0 failures

## [0.1.0] - 2026-04-23

### Added
- MOKA API支持、知识库扩展、异步执行、交付物磁盘恢复

### Changed
- 移除MockLLMBackend、前端同步→异步、5阶段进度

### Testing
- 174 tests passing, 0 failures
