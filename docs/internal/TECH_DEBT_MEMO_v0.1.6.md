# OPC-Agents v0.1.6 技术债务备忘录

**日期**: 2026-05-03
**状态**: v0.1.6 已修复 CRITICAL/HIGH 问题，以下为后续版本需处理的技术债务

---

## 🔒 安全（待后续版本处理）

### C4: 轮询循环阻塞 Streamlit 主线程
- **文件**: `frontend/app.py` L870-1110
- **问题**: `time.sleep()` 轮询阻塞整个应用
- **建议**: 使用 `st.fragment` 或 SSE 推送模式
- **优先级**: v0.2.0（需 Streamlit 架构调整）

### H5: 聊天历史明文存储
- **文件**: `frontend/app.py` L77-83
- **问题**: `chat_history.json` 无加密保护
- **建议**: 复用 `SecureKeyStore` 的 Fernet 加密
- **优先级**: v0.2.0

### M1: get_status() 读操作有副作用
- **文件**: `opc_manager/async_executor.py` L296-310
- **问题**: 超时检测修改任务状态，违反最小惊讶原则
- **建议**: 分离到 `_check_timeouts()` 方法
- **优先级**: v0.1.7

### M2: _schedule_retry() 在锁外修改任务状态
- **文件**: `opc_manager/async_executor.py` L606-626
- **建议**: 统一在锁内修改
- **优先级**: v0.1.7

### M3: 异常堆栈完整输出到stdout
- **文件**: `frontend/app.py` L545-548
- **建议**: 仅记录异常类型，用 `logger.debug()` 输出堆栈
- **优先级**: v0.1.7

### M4: 无会话超时和过期机制
- **文件**: `opc_manager/session_context.py` L135-146
- **建议**: 添加30分钟无活动自动清除
- **优先级**: v0.2.0

### M5: 加密密钥派生依赖非秘密信息
- **文件**: `opc_manager/secure_storage.py` L47-101
- **建议**: 文档中明确说明安全边界
- **优先级**: v0.1.7（文档）

### L1: LLM输出Markdown链接未做安全检查
- **文件**: `frontend/app.py` L760/801/806/946
- **建议**: 对外部链接添加视觉标记
- **优先级**: v0.2.0

### L2: ConfigManager.set() 允许设置任意环境变量
- **文件**: `opc_manager/config.py` L156-168
- **建议**: 添加环境变量白名单
- **优先级**: v0.2.0

---

## ⚡ 性能（待后续版本处理）

### C5: 每次渲染对每条历史消息执行磁盘文件读取
- **文件**: `frontend/app.py` L764-765
- **问题**: N条消息=N次磁盘I/O
- **建议**: 缓存文件内容到 session_state
- **优先级**: v0.1.7

### H9: SearchResultProcessor 每次调用 import jieba
- **文件**: `opc_manager/search_processor.py` L455-478
- **建议**: 模块级导入或 `_jieba_initialized` 标志
- **优先级**: v0.1.7

### H11: ConfigManager.config 每次重新读取环境变量
- **文件**: `opc_manager/config.py` L107-110
- **建议**: 添加 TTL 缓存
- **优先级**: v0.1.7

### H12: 每个任务创建新线程而非线程池
- **文件**: `opc_manager/async_executor.py` L246-253
- **建议**: 使用 `ThreadPoolExecutor`
- **优先级**: v0.2.0（需并发测试）

### H13: LLM HTTP 请求无连接池
- **文件**: `opc_manager/llm_content.py` L601-606
- **建议**: 使用 `requests.Session()` 复用连接
- **优先级**: v0.2.0

### M7: _save_chat_history 每次全量写入 JSON
- **文件**: `frontend/app.py` L77-83
- **建议**: 增量追加或写入节流
- **优先级**: v0.1.7

### M8: session_context get_context_for_llm 每次重新格式化
- **文件**: `opc_manager/session_context.py` L215-288
- **建议**: 缓存格式化结果
- **优先级**: v0.2.0

### M9: session_context get_last_result 线性扫描
- **文件**: `opc_manager/session_context.py` L306-307
- **建议**: 维护 `_last_assistant_turn` 引用
- **优先级**: v0.1.7

### M10: async_executor 重试线程 time.sleep 占用线程资源
- **文件**: `opc_manager/async_executor.py` L606-629
- **建议**: 使用 `threading.Timer`
- **优先级**: v0.2.0

### M11: monitoring 每次事件追踪 import sentry_sdk
- **文件**: `opc_manager/monitoring.py` L70-78
- **建议**: 模块级缓存
- **优先级**: v0.1.7

### M12: llm_content _get_llm_config 每次读取环境变量
- **文件**: `opc_manager/llm_content.py` L629-674
- **建议**: TTL 缓存
- **优先级**: v0.1.7

### M13: task_engine_v3 execute() 内部重复 import
- **文件**: `opc_manager/task_engine_v3.py` L564-566
- **建议**: 移至文件顶部
- **优先级**: v0.1.7

### M14: app.py get_version 重复导入
- **文件**: `frontend/app.py` L630/1354
- **建议**: 移至文件顶部
- **优先级**: v0.1.7

### L3: PersonaManager 缓存为实例级别不复用
- **文件**: `opc_manager/persona_manager.py` L94
- **建议**: 已通过 session_state 缓存实例解决
- **优先级**: 已解决

### L5: async_executor zombie 扫描间隔可能过长
- **文件**: `opc_manager/async_executor.py` L638
- **建议**: 降至10-15秒
- **优先级**: v0.1.7

### L6: app.py 文件大小重复计算
- **文件**: `frontend/app.py` L775
- **建议**: 使用 deliverable_record 中的 size_kb
- **优先级**: v0.1.7

### L7: search_processor 滑动窗口 O(n*4)
- **文件**: `opc_manager/search_processor.py` L538-544
- **建议**: 限制输入文本长度
- **优先级**: v0.2.0

---

## 📝 文档（待后续版本处理）

### L8: CONTRIBUTING.md CHANGELOG 路径未明确
- **建议**: 明确为 `docs/CHANGELOG.md`
- **优先级**: v0.1.7

### L9: CHANGELOG 缺失 3 个版本记录
- **建议**: 补充 0.1.2、0.1.1-beta、0.1.0-beta
- **优先级**: v0.2.0

### L10: start.sh 未检查 Ollama 配置
- **建议**: 添加 Ollama 检测逻辑
- **优先级**: v0.1.7

---

## 版本规划建议

| 版本 | 重点 | 关键债务 |
|------|------|---------|
| v0.1.7 | 小修快补 | C5(文件缓存), H9(jieba), H11(config缓存), M7-M14(小优化) |
| v0.2.0 | 架构优化 | C4(轮询改非阻塞), H12(线程池), H13(连接池), H5(聊天加密), M8(上下文缓存) |
| v0.3.0 | 安全增强 | M4(会话超时), L1(链接安全), L2(配置白名单) |
