# ADR-001: IntentRouter — 正则匹配意图分类

**Status**: Accepted
**Date**: 2026-07-11
**Supersedes**: N/A
**Related**: [PARALLEL_SAGES_DESIGN.md](PARALLEL_SAGES_DESIGN.md), [PROJECT_STATUS.md](../PROJECT_STATUS.md)

---

## Context

OPC-Agents 需要将用户的自然语言输入分类到不同的任务类型，以便路由到相应的处理流程。这是任务执行管道的第一步，直接影响后续所有处理的正确性和性能。

**问题陈述**：
- 用户输入多样化，需要快速准确地分类到 5 种粗粒度任务类型
- 意图分类是每个请求的必经路径，延迟敏感（用户期望即时响应）
- 系统需要支持离线运行（不依赖外部 API）
- 分类结果必须确定性（相同输入永远得到相同输出，便于调试和测试）

**约束**：
- 当前 5 种任务类型为粗粒度分类，不需要细粒度语义理解
- 用户群体主要使用中文，部分使用英文/日文
- 系统需要保持低运营成本

## Decision

**采用基于正则表达式的意图分类器（IntentClassifier），而非 LLM 调用。**

### 架构设计

```
User Input → IntentClassifier.classify()
           → Regex pattern matching (priority-ordered)
           → TaskType enum (INFO_COLLECTION / CONTENT_GENERATION / DATA_ANALYSIS / SCENARIO_BASED / GENERAL_CHAT)
```

**文件**: `opc_manager/intent_classifier.py`

### 关键设计决策

1. **正则匹配优先级**：PATTERNS 字典的键顺序即为匹配优先级，从高到低：
   - `INFO_COLLECTION` > `CONTENT_GENERATION` > `DATA_ANALYSIS` > `SCENARIO_BASED` > `GENERAL_CHAT`（fallback）
2. **零外部依赖**：纯 Python `re` 模块实现，无网络调用、无 API 费用
3. **确定性输出**：相同输入永远得到相同 TaskType，便于单元测试和回归验证
4. **可扩展性**：新增任务类型只需在 PATTERNS 字典中添加键值对 + 正则列表，保持优先级顺序

### 设计意图（为何不用 LLM）

| 维度 | 正则匹配 | LLM 调用 |
|------|----------|----------|
| 延迟 | <1ms | >500ms |
| 成本 | 零 | API 调用费 |
| 确定性 | 完全确定 | 同一输入可能不同输出 |
| 离线可用 | 是 | 否 |
| 准确率 | ~95%（5 类粗粒度） | ~98%（但边际收益小） |

对于当前 5 类粗粒度分类，正则匹配的 ~95% 准确率已足够，而 LLM 的 3% 准确率提升代价是 500x 延迟和持续 API 成本。

## Consequences

### 正面影响

- **零延迟分类**：意图识别 <1ms，不阻塞后续处理
- **零运营成本**：无 API 调用费用
- **完全离线可用**：不依赖外部服务，满足"数据从不出家门"原则
- **测试友好**：确定性输出，单元测试可精确断言
- **调试简单**：正则模式可视化，问题定位直接

### 负面影响

- **语义理解有限**：正则无法理解复杂语义，对非标准表述可能误分类
- **维护成本**：新增任务类型需手动添加正则模式，模式膨胀后可能冲突
- **多语言扩展**：需要为每种语言维护独立的正则模式集

### 风险缓解

- GENERAL_CHAT 作为 fallback 确保未匹配的输入不会丢失
- FOLLOW_UP_PATTERNS 独立处理追问/修改类输入，提升上下文感知能力
- 后续可引入 LLM 作为二级分类器（仅对正则匹配置信度低的输入调用 LLM）

## Alternatives Considered

### 方案 A: LLM 意图分类（已否决）

使用 LLM（如 GPT-4）进行意图分类。

**否决原因**：
- 延迟过高（500ms+ vs 1ms），影响用户体验
- 持续 API 成本
- 非确定性输出，难以测试和调试
- 依赖外部服务，违反离线运行原则

### 方案 B: 嵌入式模型分类（已否决）

使用小型嵌入式模型（如 sentence-transformers）进行语义分类。

**否决原因**：
- 模型加载增加启动时间（~3s）
- 模型文件增加包体积（~100MB）
- 对于 5 类粗粒度分类，投入产出比不合理
- 可在后续细粒度分类场景中重新评估

### 方案 C: 混合模式（正则 + LLM fallback）（未来考虑）

正则匹配作为一级分类器，对低置信度输入调用 LLM 作为二级分类器。

**状态**：未来考虑。当前正则匹配准确率 ~95% 足够，当任务类型扩展到 10+ 类细粒度分类时可重新评估。
