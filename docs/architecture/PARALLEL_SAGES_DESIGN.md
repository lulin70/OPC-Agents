# 三贤者并行投票架构设计

> **文档状态**: 架构设计文档（S2-T1 产出）
> **版本**: v0.3.0
> **日期**: 2026-06-19
> **负责角色**: Architect
> **任务ID**: S2-T1 [P0-5]
> **依据**: [V030_REMEDIATION_PLAN.md](../internal/V030_REMEDIATION_PLAN.md) Sprint 2
> **前置分析**: [三贤者架构当前实现分析报告](#九、当前实现基线)

---

## 一、设计目标与原则

### 1.1 设计目标

| 目标 | 当前 | 目标 | 衡量指标 |
|------|------|------|---------|
| 三贤者调用模式 | 串行流水线（3×RTT） | 并行投票（1×RTT） | 延迟降40%+ |
| ConsensusEngine 角色 | 事后补救（quality<0.7） | 核心决策（关键决策点前置） | 关键操作100%经共识 |
| ExecutorBrain 意见 | 假意见（retry_count规则） | 真实LLM判断 | express_opinion()调用LLM |
| ReflectorBrain 角色 | 事后评估（evaluate_result） | 前置预判（predict_consequence） | 预判方法生效 |
| IntentRouter | 5类TaskType正则 | 三路分类（简单/复杂/问候） | 简单任务绕过三贤者 |

### 1.2 设计原则

1. **原始设计意图回归**: 借鉴 EVA MAGI 系统 + 《Minority Report》三先知，三贤者**并行投票**而非串行流水线
2. **关键决策点前置共识**: 不可逆操作（发邮件/数据持久化）执行前必须经三贤者投票
3. **保留串行fallback**: 并行失败时降级到串行流水线，保证可用性
4. **接口契约统一**: 三个Brain的 `express_opinion()` / `predict_consequence()` 签名统一
5. **测试先行**: 并行路径新增测试覆盖，串行路径不破坏现有测试
6. **渐进式上线**: 并行投票与串行流水线共存，通过开关切换

---

## 二、原始设计意图回顾

### 2.1 EVA MAGI 系统

```
EVA MAGI 三贤者系统:
- Melchior (逻辑)
- Balthasar (情感)
- Casper (直觉)
三脑并行处理 → 投票决策 → 一致同意才执行
```

### 2.2 Minority Report 三先知

```
三先知并行预判未来:
- Agatha (主先知)
- Dashiell (副先知1)
- Arthur (副先知2)
并行预判 → 少数派报告机制 → 综合决策
```

### 2.3 OPC-Agents 三贤者映射

| EVA MAGI | Minority Report | OPC-Agents | 职责 |
|----------|----------------|------------|------|
| Melchior (逻辑) | Agatha (主先知) | **StrategistBrain** | 策略规划（逻辑分析） |
| Balthasar (情感) | Dashiell (副先知1) | **ExecutorBrain** | 执行判断（可行性） |
| Casper (直觉) | Arthur (副先知2) | **ReflectorBrain** | 后果预判（直觉预警） |

**核心**: 三脑**并行**express_opinion/predict_consequence → ConsensusEngine.collect_opinions → Decision

---

## 三、当前实现偏离分析

### 3.1 当前串行流水线（3×RTT）

```
[用户输入]
    ↓
[strategist.understand_intent()] ── RTT 1 ──
    ↓
[strategist.plan()]               ── RTT 2 ──
    ↓
[executor.execute_step()] × N步   ── RTT 3+ ──
    ↓
[reflector.evaluate_result()]     ── 事后评估 ──
    ↓
[consensus.consult()]             ── 仅quality<0.7触发 ──
    ├─ strategist.express_opinion()  ← 真实
    ├─ executor假意见(retry_count)   ← 伪造
    └─ reflector.express_opinion()   ← 真实
```

### 3.2 三个根本性偏离

| 偏离 | 原始设计 | 当前实现 | 影响 |
|------|---------|---------|------|
| **串行 vs 并行** | asyncio.gather 三脑同时投票 | strategist→executor→reflector 串行 | 延迟3×RTT而非1×RTT |
| **后置 vs 前置** | 每个关键决策点都投票 | 仅quality<0.7时后置补救 | 不可逆操作无保护 |
| **假意见 vs 真意见** | ExecutorBrain独立LLM判断 | retry_count规则伪造 | 决策质量下降 |

### 3.3 关键代码位置

| 问题 | 文件 | 行号 | 说明 |
|------|------|------|------|
| 串行流水线 | agent_loop.py | L428-838 | _phase_plan→_phase_execute→_phase_reflect 严格串行 |
| 后置共识 | task_lifecycle.py | L236 | `if quality_score >= 0.7: return None` |
| 假意见 | task_lifecycle.py | L248-255 | `retry_count < 2` 规则伪造executor意见 |
| 缺失方法 | executor_brain.py | — | 无 express_opinion() 方法 |
| 缺失方法 | reflector_brain.py | — | 无 predict_consequence() 方法 |
| 同步阻塞 | consensus_engine.py | L77 | collect_opinions() 是同步方法 |

---

## 四、并行投票架构设计

### 4.1 目标并行投票数据流（1×RTT）

```
[用户输入]
    ↓
[IntentRouter 三路分类]
    ├── SIMPLE（单步、无副作用）→ SingleLLMCall → Result
    ├── GREETING（问候/帮助）→ 直接响应 → Result
    └── COMPLEX（多步、有副作用）→ 三贤者并行投票
         ↓
    [asyncio.gather]
         ├── StrategistBrain.express_opinion()     ─┐
         ├── ExecutorBrain.express_opinion()        ├─ 并行 1×RTT
         └── ReflectorBrain.predict_consequence()  ─┘
         ↓
    [ConsensusEngine.collect_opinions()] → Decision
         ├── approved=True  → ExecutorBrain.execute() → Result
         └── approved=False → 返回决策理由（不执行）
```

### 4.2 关键决策点清单

以下操作为不可逆/高成本，**执行前必须经三贤者并行投票**：

| 决策点ID | 操作类型 | 触发条件 | 风险等级 | 代码位置 |
|----------|---------|---------|---------|---------|
| DP_SEND_EMAIL | 发送邮件 | skill_id=email, action=send | 高（不可撤回） | email_skill.py L104 |
| DP_EXECUTE_OPERATION | 业务操作 | skill_id=*, action=execute_operation | 高 | skill_executors.py L346 |
| DP_DATA_PERSIST | 数据持久化 | 任何 INSERT/UPDATE/DELETE | 中 | 各skill的持久化方法 |
| DP_REPORT_GENERATION | 报告生成 | skill_id=report, action=generate | 中（高成本） | report_skill.py |
| DP_NOTIFICATION | 通知发送 | skill_id=*, action=send_notification | 中 | notification skill |

**规则**:
- 关键决策点在 `executor.execute_step()` **前**触发并行投票
- 非关键操作（查询/读取）不触发投票，直接执行
- 投票否决时操作不执行，返回决策理由给用户

### 4.3 IntentRouter 三路分类

```python
class IntentCategory(Enum):
    SIMPLE = "simple"        # 单步、无副作用、纯查询
    COMPLEX = "complex"      # 多步、有副作用、需规划
    GREETING = "greeting"    # 问候/帮助/闲聊

class IntentRouter:
    @classmethod
    def classify_route(cls, user_input: str) -> Tuple[IntentCategory, float]:
        """
        三路分类（0成本，基于关键词+启发式）
        - GREETING: 你好/帮助/谢谢/再见 等问候词
        - SIMPLE: 查询/查看/列出/告诉我 等查询词 + 单步
        - COMPLEX: 发送/记录/生成/执行/创建 等动作词 + 多步/副作用
        """
```

**分类规则**（正则+启发式，0 LLM成本）:
- GREETING: `^(你好|您好|hi|hello|帮助|help|谢谢|再见|bye)` 
- SIMPLE: `(查询|查看|列出|告诉我|显示|搜索)` 且无副作用动词
- COMPLEX: `(发送|记录|生成|执行|创建|删除|更新|导出)` 或多步骤

### 4.4 接口契约

#### 4.4.1 Brain 统一接口（Protocol）

```python
# opc_manager/protocols.py (新增)
from typing import Protocol
from .consensus_engine import Opinion

class BrainProtocol(Protocol):
    """三贤者统一接口契约"""

    def express_opinion(self, context: Dict[str, Any],
                        decision_point: str) -> Opinion:
        """表达意见（同步或异步，由实现决定）"""
        ...

    async def express_opinion_async(self, context: Dict[str, Any],
                                     decision_point: str) -> Opinion:
        """异步表达意见（并行投票用）"""
        ...
```

#### 4.4.2 StrategistBrain（已存在，需增强）

```python
# 现有: express_opinion(self, context) -> Dict  (L750, 简单实现)
# 增强: express_opinion(self, context, decision_point) -> Opinion
#        使用 LLM 独立推理（替代 intent.confidence 阈值）
```

#### 4.4.3 ExecutorBrain（需新增）

```python
# 新增方法
def express_opinion(self, context: Dict[str, Any],
                    decision_point: str) -> Opinion:
    """
    ExecutorBrain 独立LLM判断（替代retry_count规则）
    - 调用 LLM 评估执行可行性
    - 返回 Opinion(AGREE/DISAGREE/CONDITIONAL)
    """
    prompt = self._build_opinion_prompt(context, decision_point)
    response = self.llm_service.call(prompt)
    return self._parse_opinion(response, brain_type="executor")

async def express_opinion_async(self, context, decision_point) -> Opinion:
    """异步版本（并行投票用）"""
    return await asyncio.to_thread(self.express_opinion, context, decision_point)
```

#### 4.4.4 ReflectorBrain（需新增 predict_consequence）

```python
# 新增方法
def predict_consequence(self, context: Dict[str, Any],
                        planned_action: Dict) -> Opinion:
    """
    前置预判行动后果（少数派报告模式）
    - 在执行前预测可能后果
    - 返回 Opinion(AGREE/DISAGREE/CONDITIONAL)
    - 保留 evaluate_result() 用于事后评估（二级保障）
    """
    prompt = self._build_prediction_prompt(context, planned_action)
    response = self.llm_service.call(prompt)
    return self._parse_opinion(response, brain_type="reflector")

async def predict_consequence_async(self, context, planned_action) -> Opinion:
    """异步版本（并行投票用）"""
    return await asyncio.to_thread(self.predict_consequence, context, planned_action)
```

#### 4.4.5 ConsensusEngine（需增强 async 支持）

```python
# 现有: collect_opinions(opinions: List[Opinion]) -> Decision  (同步, L77)
# 增强: 新增 async 版本用于并行投票

async def collect_opinions_async(self,
                                  strategist_op: Coroutine,
                                  executor_op: Coroutine,
                                  reflector_op: Coroutine) -> Decision:
    """
    并行收集三贤者意见（asyncio.gather）
    - 三脑并行执行，超时降级
    - 任一超时返回 ABSTAIN 意见
    """
    opinions = await asyncio.gather(
        strategist_op, executor_op, reflector_op,
        return_exceptions=True
    )
    # 异常处理：超时/错误 → ABSTAIN
    valid_opinions = []
    for op in opinions:
        if isinstance(op, Exception):
            valid_opinions.append(Opinion(
                brain_type="unknown",
                opinion_type=OpinionType.ABSTAIN,
                reasoning=f"并行投票异常: {op}",
                confidence=0.0
            ))
        else:
            valid_opinions.append(op)
    return self.collect_opinions(valid_opinions)  # 复用同步汇总逻辑
```

### 4.5 AgentLoop 并行投票入口

```python
# agent_loop.py 新增方法
async def _parallel_consensus(self, context: Dict[str, Any],
                               decision_point: str) -> Decision:
    """
    三贤者并行投票决策
    - 在关键决策点前调用
    - 并行失败时降级到串行
    """
    try:
        decision = await self.consensus_engine.collect_opinions_async(
            self.strategist_brain.express_opinion_async(context, decision_point),
            self.executor_brain.express_opinion_async(context, decision_point),
            self.reflector_brain.predict_consequence_async(context, context.get("planned_action", {})),
        )
        return decision
    except Exception as e:
        logger.warning(f"并行投票失败，降级到串行: {e}")
        return await self._serial_consensus_fallback(context, decision_point)

async def _serial_consensus_fallback(self, context, decision_point) -> Decision:
    """串行降级路径（并行失败时）"""
    s_op = self.strategist_brain.express_opinion(context, decision_point)
    e_op = self.executor_brain.express_opinion(context, decision_point)
    r_op = self.reflector_brain.predict_consequence(context, context.get("planned_action", {}))
    return self.consensus_engine.collect_opinions([s_op, e_op, r_op])
```

### 4.6 关键决策点前置共识

```python
# agent_loop.py 在 _phase_execute 前插入
async def _phase_execute_with_consensus(self, context, start_step):
    """带前置共识的执行阶段"""
    for step in context.plan.steps:
        # 检查是否为关键决策点
        if self._is_critical_decision_point(step):
            decision = await self._parallel_consensus(context, step.skill_id)
            if not decision.approved:
                return f"操作未获三贤者批准: {decision.reasoning}"
        # 执行步骤
        await self._execute_step_with_retry(context, step, ...)

def _is_critical_decision_point(self, step) -> bool:
    """判断是否为关键决策点（见4.2清单）"""
    CRITICAL_SKILLS = {"email", "report"}
    CRITICAL_ACTIONS = {"send", "execute_operation", "send_notification"}
    return (step.skill_id in CRITICAL_SKILLS or
            step.action in CRITICAL_ACTIONS)
```

---

## 五、降级与fallback策略

### 5.1 三级降级策略

```
Level 1: 并行投票正常
  → asyncio.gather 三脑并行 → collect_opinions → Decision

Level 2: 并行投票部分失败（某脑超时/异常）
  → 异常脑返回 ABSTAIN → 其余脑投票 → Decision

Level 3: 并行投票全部失败
  → 降级到串行 _serial_consensus_fallback → Decision

Level 4: 串行也失败
  → 降级到无共识直接执行（记录警告日志）
  → 保留现有 _phase_execute 路径
```

### 5.2 超时配置

```python
# agent_loop.py 常量
PARALLEL_VOTE_TIMEOUT = int(os.environ.get("OPC_PARALLEL_VOTE_TIMEOUT", "30"))  # 单脑超时30s
PARALLEL_VOTE_ENABLED = os.environ.get("OPC_PARALLEL_VOTE_ENABLED", "true").lower() == "true"
```

### 5.3 开关控制

- `OPC_PARALLEL_VOTE_ENABLED=true`: 启用并行投票（默认）
- `OPC_PARALLEL_VOTE_ENABLED=false`: 禁用，使用串行流水线（兼容旧版本）

---

## 六、与现有代码的衔接

### 6.1 保留的现有方法（不删除）

| 方法 | 文件 | 用途 |
|------|------|------|
| strategist.understand_intent() | strategist_brain.py L129 | 意图理解（执行阶段仍需） |
| strategist.plan() | strategist_brain.py L477 | 制定计划（执行阶段仍需） |
| executor.execute_step() | executor_brain.py L131 | 执行步骤（投票通过后调用） |
| reflector.evaluate_result() | reflector_brain.py L121 | 事后评估（二级保障） |
| reflector.decide_next_action() | reflector_brain.py L377 | 决定下一步（执行后） |
| consensus.collect_opinions() | consensus_engine.py L77 | 同步汇总（async版本复用） |
| ConsensusConsultant.consult() | task_lifecycle.py L217 | 事后补救（保留为二级保障） |

### 6.2 新增的方法

| 方法 | 文件 | 说明 |
|------|------|------|
| ExecutorBrain.express_opinion() | executor_brain.py | 真实LLM意见（S2-T3） |
| ExecutorBrain.express_opinion_async() | executor_brain.py | 异步版本 |
| ReflectorBrain.predict_consequence() | reflector_brain.py | 前置预判（S2-T5） |
| ReflectorBrain.predict_consequence_async() | reflector_brain.py | 异步版本 |
| ConsensusEngine.collect_opinions_async() | consensus_engine.py | 并行汇总（S2-T4） |
| AgentLoop._parallel_consensus() | agent_loop.py | 并行投票入口（S2-T2） |
| AgentLoop._serial_consensus_fallback() | agent_loop.py | 串行降级 |
| AgentLoop._phase_execute_with_consensus() | agent_loop.py | 带共识的执行 |
| AgentLoop._is_critical_decision_point() | agent_loop.py | 关键决策点判断 |
| IntentRouter.classify_route() | intent_classifier.py | 三路分类（S2-T6） |

### 6.3 修改的方法

| 方法 | 文件 | 修改内容 |
|------|------|---------|
| ConsensusConsultant.consult() | task_lifecycle.py L248-255 | 删除假意见，调用 executor.express_opinion() |
| AgentLoop.run() | agent_loop.py L104 | 入口增加 IntentRouter 路由 |
| AgentLoop._phase_execute() | agent_loop.py L491 | 增加关键决策点前置共识 |

---

## 七、测试策略

### 7.1 新增测试文件

```
tests/
├── test_parallel_sages.py          # 并行投票核心测试
├── test_intent_classifier_route.py # 三路分类测试
├── test_executor_opinion.py        # ExecutorBrain真意见测试
├── test_reflector_prediction.py    # ReflectorBrain预判测试
└── test_consensus_async.py         # 异步共识测试
```

### 7.2 测试场景

#### 并行投票核心测试（test_parallel_sages.py）

| 测试 | 场景 | 验收 |
|------|------|------|
| test_parallel_vote_normal | 三脑并行正常投票 | Decision正确返回 |
| test_parallel_vote_timeout | 某脑超时 | 超时脑ABSTAIN，其余投票 |
| test_parallel_vote_all_fail | 全部失败 | 降级到串行 |
| test_parallel_vote_veto | 某脑否决 | approved=False，操作不执行 |
| test_parallel_vs_serial_latency | 延迟对比 | 并行 < 串行 × 0.6 |

#### 关键决策点测试

| 测试 | 场景 | 验收 |
|------|------|------|
| test_send_email_consensus | 发邮件前投票 | 投票通过才发送 |
| test_data_persist_consensus | 数据持久化前投票 | 投票通过才写入 |
| test_query_no_consensus | 查询不投票 | 直接执行，无共识开销 |

#### 三路分类测试

| 测试 | 场景 | 验收 |
|------|------|------|
| test_classify_greeting | "你好" | GREETING |
| test_classify_simple | "查看本月支出" | SIMPLE |
| test_classify_complex | "发邮件给张总" | COMPLEX |

### 7.3 延迟对比基准

```python
# test_parallel_sages.py
def test_parallel_vs_serial_latency():
    """并行延迟必须 < 串行延迟 × 0.6"""
    serial_time = measure(lambda: serial_consensus(context))
    parallel_time = measure(lambda: asyncio.run(parallel_consensus(context)))
    assert parallel_time < serial_time * 0.6
```

---

## 八、风险评估与应对

### 8.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 并行LLM调用触发rate limit | 中 | 高 | 限制并发数=3；实现重试+退避 |
| 三脑并行后决策质量下降 | 低 | 高 | 保留串行fallback；A/B对比测试 |
| asyncio.gather 异常处理复杂 | 中 | 中 | return_exceptions=True；ABSTAIN降级 |
| 关键决策点识别遗漏 | 中 | 高 | 白名单+黑名单结合；可配置 |
| IntentRouter误分类 | 中 | 中 | 保守策略：不确定时归为COMPLEX |

### 8.2 兼容性风险

| 风险 | 缓解措施 |
|------|---------|
| 现有测试破坏 | 保留串行路径；OPC_PARALLEL_VOTE_ENABLED开关 |
| ConsensusConsultant.consult() 调用方 | 保留方法，内部改用真意见 |
| 前端无感知 | 并行投票对前端透明，仅延迟降低 |

### 8.3 性能风险

| 风险 | 缓解措施 |
|------|---------|
| 并行3次LLM调用成本增加 | 仅关键决策点触发；简单任务绕过 |
| asyncio.gather 调度开销 | 实测验证；超时30s兜底 |

---

## 九、当前实现基线

### 9.1 方法存在性汇总

| 方法 | StrategistBrain | ExecutorBrain | ReflectorBrain |
|------|:---:|:---:|:---:|
| express_opinion() | ✅ L750（简单） | ❌ 需新增 | ✅ L575（简单） |
| express_opinion_async() | ❌ 需新增 | ❌ 需新增 | ❌ 需新增 |
| predict_consequence() | — | — | ❌ 需新增 |
| understand_intent() | ✅ L129 | — | — |
| plan() | ✅ L477 | — | — |
| execute_step() | — | ✅ L131 | — |
| evaluate_result() | — | — | ✅ L121（事后） |
| decide_next_action() | — | — | ✅ L377 |

### 9.2 关键常量

```python
# agent_loop.py
QUALITY_THRESHOLD_CORRECTION = 0.6   # L52
QUALITY_THRESHOLD_CONSENSUS = 0.7    # L53 ← 共识触发阈值（后置）
MAX_CORRECTION_ATTEMPTS = 2          # L54
MAX_RETRY_PER_STEP = 3               # L42
MAX_REFLECT_ROUNDS = 3               # L44
```

### 9.3 数据结构（复用现有）

```python
# consensus_engine.py
@dataclass
class Opinion:
    brain_type: str           # strategist/executor/reflector
    opinion_type: OpinionType # AGREE/DISAGREE/CONDITIONAL/ABSTAIN
    reasoning: str
    confidence: float = 1.0
    alternative: Optional[str] = None

@dataclass
class Decision:
    decision_type: DecisionType  # UNANIMOUS/MAJORITY/COMPROMISE/ESCALATED/VETOED
    approved: bool
    reasoning: str
    alternative: Optional[str] = None
    confidence: float = 0.0
```

---

## 十、实施路线图（Sprint 2 任务映射）

| 任务 | 本设计章节 | 产出 |
|------|-----------|------|
| S2-T1 | 全文 | 本文档 |
| S2-T2 | 4.5, 4.6, 6.2 | agent_loop.py 并行投票入口 |
| S2-T3 | 4.4.3, 6.3 | ExecutorBrain.express_opinion() |
| S2-T4 | 4.4.5, 4.6, 6.3 | ConsensusEngine 前置 + async |
| S2-T5 | 4.4.4, 6.2 | ReflectorBrain.predict_consequence() |
| S2-T6 | 4.3, 6.3 | IntentRouter 三路分类 |
| S2-T9 | 7.2, 7.3 | 延迟对比验证 + 报告 |

---

## 十一、验收标准

### 11.1 S2-T1 验收

- [x] 设计文档经7角色评审通过
- [x] 接口契约明确（BrainProtocol）
- [x] 关键决策点清单完整（5类）
- [x] 降级策略清晰（4级）
- [x] 与现有代码衔接方案明确

### 11.2 Sprint 2 整体验收

- [ ] 并行投票功能正常（test_parallel_sages.py 通过）
- [ ] 延迟对比：并行 < 串行 × 0.6
- [ ] ExecutorBrain 假意见代码删除
- [ ] ConsensusEngine 关键决策点前置
- [ ] ReflectorBrain predict_consequence 生效
- [ ] IntentRouter 三路分类准确率 ≥ 80%
- [ ] 现有测试100%通过（无回归）
- [ ] 新测试覆盖并行路径

---

> **本设计文档是 Sprint 2 三贤者并行化改造的架构蓝图。** 实施过程中如发现设计不合理，立即更新本文档并记录变更理由。所有代码变更必须符合本设计的接口契约。
>
> **下一步**: S2-T2 Coder 按 4.5/4.6/6.2 章节实施 agent_loop.py 并行投票入口。
