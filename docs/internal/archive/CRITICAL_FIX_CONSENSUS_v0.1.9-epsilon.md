# OPC-Agents v0.1.9-delta 致命问题整改共识文档

**日期**: 2026-05-10
**版本**: v0.1.9-delta → v0.1.9-epsilon
**触发**: 试运行发现三贤者LLM从未真正工作

---

## 致命问题清单

| # | 问题 | 影响 | 严重度 |
|---|------|------|--------|
| F1 | 三贤者LLM接口不匹配 — `_call_llm`调用`generate(prompt, max_tokens)`但接口需要`generate(user_input, template)` | 三贤者LLM从未工作，每次降级到规则引擎 | 🔴致命 |
| F2 | 通知技能完全Mock — `_execute_send_email()`只返回`{"sent": True}` | 用户以为邮件已发送，实际未发送 | 🔴致命 |
| F3 | 知识库硬编码字典 — 20条固定条目，无动态管理 | 不是真正的知识库，无法满足用户需求 | 🔴致命 |

## 重要问题清单

| # | 问题 | 影响 | 严重度 |
|---|------|------|--------|
| I1 | LLM API调用30秒超时，经常超时 | 用户等待后得到模板输出 | 🟡重要 |
| I2 | 质量门禁过于严格 — `no_data_source`拒绝有效内容 | LLM生成的好内容被拒绝 | 🟡重要 |
| I3 | 三贤者LLM降级无用户提示 | 用户以为在用AI增强模式 | 🟡重要 |
| I4 | 搜索处理慢（500ms+） | 影响响应速度 | 🟡重要 |
| I5 | 缺少端到端集成测试 | 470测试通过但核心链路不通 | 🟡重要 |

---

## 7角色整改方案

### 🏗 架构师方案

**F1修复：统一LLM调用接口**

根因：三贤者传入的`llm_service`是`LLMEnhancedContentGenerator`实例，其`generate()`方法是面向内容生成的（需要template+search_results），不适合三贤者的简单prompt→response模式。

方案：在`llm_service.py`中添加`SimpleLLMService`适配器，三贤者使用该适配器：

```python
class SimpleLLMService:
    """三贤者专用LLM接口 — 简单prompt→response"""
    
    def __init__(self, config: LLMConfig = None):
        self._config = config or self._auto_config()
        self._backend = OpenAIBackend(self._config)
    
    def _auto_config(self) -> LLMConfig:
        # 从环境变量自动配置 MOKA/GLM/OpenAI/Ollama
        ...
    
    def complete(self, prompt: str, system_prompt: str = None, 
                 max_tokens: int = 500, timeout: int = 15) -> Optional[str]:
        """同步调用LLM，返回文本响应"""
        # 使用requests同步调用（避免async/sync桥接问题）
        ...
```

三贤者的`_call_llm`改为调用`self.llm_service.complete(prompt)`。

**I5修复：添加端到端集成测试**

新增`tests/test_e2e_three_sage.py`，使用真实LLM调用验证完整链路。

### 📋 产品经理方案

**F2修复：通知技能分级实现**

| 级别 | 实现 | 说明 |
|------|------|------|
| L1 | 日志通知 | 将通知内容写入`data/notifications/`目录，用户可在UI中查看 |
| L2 | 邮件通知 | 集成SMTP，需用户配置SMTP服务器 |
| L3 | Webhook通知 | 支持企业微信/钉钉/Slack Webhook |

v0.1.9-epsilon实现L1（日志通知），v0.2.0实现L2/L3。

**F3修复：知识库改为文件系统+搜索**

| 级别 | 实现 | 说明 |
|------|------|------|
| L1 | 文件系统知识库 | 用户上传.md/.txt文件到`data/knowledge/`，搜索时作为补充数据源 |
| L2 | 向量检索 | 集成embedding模型，语义搜索知识库 |
| L3 | 知识图谱 | 结构化知识管理 |

v0.1.9-epsilon实现L1（文件系统知识库），v0.2.0实现L2。

**I3修复：降级提示**

当三贤者LLM降级到规则引擎时，在输出中添加`> ⚠ 当前为规则引擎模式，配置API Key后可获得AI增强分析`提示。

### 🔒 安全专家方案

**F1安全补充**：`SimpleLLMService`必须：
- 使用sanitize_for_llm处理所有prompt
- 限制max_tokens防止LLM输出过长
- 记录所有LLM调用到审计日志

**F2安全补充**：邮件通知必须：
- 验证收件人邮箱格式
- 防止邮件头注入
- 限制发送频率

### 🧪 测试专家方案

**I5修复：端到端测试**

```python
# tests/test_e2e_three_sage.py
class TestE2EThreeSage:
    def test_strategist_llm_intent(self):
        """验证策略脑LLM意图理解真实工作"""
        brain = StrategistBrain(llm_service=SimpleLLMService())
        intent = brain.understand_intent("分析竞品SWOT")
        assert intent.type == IntentType.ANALYSIS
        assert intent.confidence > 0.5
    
    def test_reflector_llm_evaluate(self):
        """验证反思脑LLM评估真实工作"""
        brain = ReflectorBrain(llm_service=SimpleLLMService())
        evaluation = brain.evaluate_result(...)
        assert evaluation.quality_score > 0
    
    def test_full_agent_loop(self):
        """验证AgentLoop完整链路"""
        loop = AgentLoop(...)
        result = asyncio.run(loop.run("写营销方案"))
        assert result["success"]
```

### 💻 开发者方案

**F1实现细节**：

1. 新增`opc_manager/simple_llm_service.py`
2. 修改`strategist_brain.py`：`_call_llm`使用`self.llm_service.complete(prompt)`
3. 修改`reflector_brain.py`：同上
4. 修改`frontend/app.py`：初始化AgentLoop时传入`SimpleLLMService`而非`LLMEnhancedContentGenerator`
5. 保留`LLMEnhancedContentGenerator`用于TaskEngineV3的内容生成

**I1修复**：增加LLM超时重试机制（3次重试，指数退避）

**I4修复**：搜索结果缓存TTL从300秒延长到600秒

### 🚀 DevOps方案

**I1补充**：在.env中配置MOKA_API_KEY，确保LLM可用

**I3补充**：健康检查端点增加LLM可用性检测

### 🎨 UI设计师方案

**I3修复**：在执行结果区域显示当前使用的模式标签：
- 🟢 AI增强模式（LLM可用）
- 🟡 规则引擎模式（LLM不可用）
- 🔴 模板模式（无LLM无搜索）

---

## 共识决议

| 决议 | 投票 | 结果 |
|------|------|------|
| F1：新增SimpleLLMService，三贤者使用complete()接口 | 7/7 | ✅ 通过 |
| F2：通知技能实现L1日志通知 | 7/7 | ✅ 通过 |
| F3：知识库实现L1文件系统知识库 | 7/7 | ✅ 通过 |
| I1：LLM超时重试3次+指数退避 | 7/7 | ✅ 通过 |
| I2：质量门禁放宽，允许无搜索结果时LLM直接生成 | 5/7 | ✅ 通过 |
| I3：降级模式UI提示 | 7/7 | ✅ 通过 |
| I4：搜索缓存TTL延长到600秒 | 7/7 | ✅ 通过 |
| I5：端到端集成测试 | 7/7 | ✅ 通过 |

---

## 实施计划

| 步骤 | 内容 | 依赖 |
|------|------|------|
| 1 | 新增SimpleLLMService | 无 |
| 2 | 修改三贤者_call_llm使用complete() | 步骤1 |
| 3 | 修改前端初始化AgentLoop传入SimpleLLMService | 步骤1 |
| 4 | 通知技能L1实现（日志通知） | 无 |
| 5 | 知识库L1实现（文件系统知识库） | 无 |
| 6 | LLM超时重试机制 | 步骤1 |
| 7 | 质量门禁放宽 | 无 |
| 8 | 降级模式UI提示 | 步骤2 |
| 9 | 端到端集成测试 | 步骤2 |
| 10 | 回归测试 | 全部 |
