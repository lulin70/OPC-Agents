# OPC-Agents × CarryMem 集成方案

> **版本**: v1.0 | **日期**: 2026-05-19 | **状态**: 项目组共识通过

## 一、背景与动机

### 1.1 核心痛点

OPC-Agents 当前最大的体验缺陷是**每次对话失忆**：
- 用户说过"我不要做电商"，下次对话还得重新说
- 用户纠正过"第三阶段不是2周是3周"，下次方案还是2周
- 21个技能是静态 prompt，没有约束清单，AI 每次重新推理

### 1.2 启发来源

Claude《The Founder's Playbook》三个关键词：

| 关键词 | 含义 | OPC-Agents 对应 |
|--------|------|-----------------|
| **持久化** | CLAUDE.md 机制，跨会话保持上下文 | OPC_CONTEXT.md |
| **编码化** | Skills as SOP，将专业经验固化为可重复流程 | 技能约束清单 |
| **护城河化** | Compounding Data，用户数据积累形成壁垒 | CarryMem 规则沉淀 |

### 1.3 CarryMem 能力匹配

| CarryMem API | 对应需求 | 优先级 |
|-------------|----------|--------|
| `classify_and_remember()` | 跨会话持久化记忆 | P0 |
| `build_context()` | 任务前自动注入记忆+规则 | P0 |
| `Rule` 引擎 (avoid/always/prefer/forbid/format) | 技能约束清单 | P1 |
| `failure_experience` → Rule 自动提炼 | 失败经验学习 | P2 |
| `CodingContextAdapter` | 项目上下文文件索引 | P3 |

---

## 二、项目组共识决议

### 2.1 一致同意

1. **集成方向正确**：OPC-Agents 的"每次对话失忆"是真实痛点，CarryMem 是对症下药
2. **必须作为可选依赖**：CarryMem 不可用时，OPC-Agents 必须正常运行
3. **不修改三贤者架构内部**：记忆是横切关注点，通过 AgentLoop 钩子注入
4. **新建 MemoryBridge 适配层**：隔离 CarryMem API 细节
5. **数据完全本地**：不做云同步，记忆数据不出本机

### 2.2 分歧点与决策

| 分歧 | 决策 | 理由 |
|------|------|------|
| 向量搜索是否默认启用 | **默认禁用** | +350MB 镜像/模型，安装体验差 |
| 发布版本 | **v0.2.2 加 feature flag** | 架构变更不应在 patch 版本，但需尽早验证 |
| 失败经验自动提炼规则 | **Phase 2 再做** | 自动提炼规则可能不准确，有注入风险 |
| 记忆管理 UI | **Phase 1 只做状态指示器** | MVP 先验证价值，再完善管理 |

### 2.3 明确不做

- ❌ 不 fork/内嵌 CarryMem
- ❌ 不做云同步
- ❌ 不在 Phase 1 做向量搜索
- ❌ 不修改三贤者架构内部代码
- ❌ 不做自动规则确认（必须用户确认）

---

## 三、架构设计

### 3.1 集成点

```
AgentLoop.run()
  ├── [新增] MemoryBridge.build_context(user_input) → 注入记忆到 context
  ├── _phase_plan(context_with_memory)
  ├── _phase_execute()
  ├── _phase_observe()
  ├── _phase_reflect()
  └── [新增] MemoryBridge.remember(user_input, results, evaluation) → 存储记忆
```

### 3.2 MemoryBridge 适配层

```python
class MemoryBridge:
    """CarryMem 适配层 — 隔离 API 细节，提供降级策略"""

    def __init__(self):
        if not CARRYMEM_AVAILABLE:
            self._cm = None
            return
        try:
            self._cm = CarryMem(db_path=config.db_path)
        except Exception:
            self._cm = None

    def build_context(self, user_input: str) -> str:
        """任务前注入记忆，失败时静默降级"""
        if not self._cm:
            return ""
        try:
            result = self._cm.build_context(context=user_input)
            return result.get("system_prompt", "")
        except Exception:
            return ""

    def remember(self, user_input: str, result: str, evaluation: dict) -> None:
        """任务后存储记忆，失败时静默降级"""
        if not self._cm:
            return
        try:
            self._cm.classify_and_remember(user_input)
        except Exception:
            pass
```

### 3.3 数据流

```
用户输入 → CarryMem.build_context() → 注入规则+记忆 → 三贤者执行 → 结果+新记忆存入 CarryMem
```

### 3.4 配置

```
CARRYMEM_ENABLED=true
CARRYMEM_DB_PATH=~/.opc-agents/memory.db
CARRYMEM_ENCRYPTION_KEY=  # 可选
CARRYMEM_MAX_MEMORIES=10
CARRYMEM_MAX_TOKENS=2000
CARRYMEM_VECTOR_SEARCH=false  # Phase 1 默认禁用
```

---

## 四、分阶段路线图

### Phase 1：最小可行集成（v0.2.2）— ✅ 已完成

**目标**：验证"有记忆的OPC-Agents"是否有用户价值

| 改动 | 行数 | 说明 | 状态 |
|------|------|------|------|
| 新建 `memory_bridge.py` | ~150行 | CarryMem 适配层 | ✅ 完成 |
| base_router.py 注入钩子 | ~25行 | build_context/remember | ✅ 完成 |
| 环境变量配置 | ~7行 | .env.example 更新 | ✅ 完成 |
| pyproject.toml | ~3行 | [memory] 可选依赖 | ✅ 完成 |
| 侧边栏状态指示器 | ~12行 | 🧠 记忆已激活 \| N条记忆 | ✅ 完成 |

**验证结果**：
- 回归测试: 181/181 通过 (100%) ✅
- CarryMem 禁用: 完全正常 ✅
- CarryMem 启用: 读写记忆成功 ✅
- 降级模式: 静默降级，无异常 ✅

### Phase 2：规则引擎集成（v0.3.0）— ✅ 已完成

**目标**：从"被动记忆"升级到"主动行为约束"

| 改动 | 说明 | 状态 |
|------|------|------|
| MemoryBridge 扩展 | 新增 match_rules/inject_rules_prompt/record_failure 等 API | ✅ 完成 |
| AgentLoop._phase_plan 注入规则 | 策略脑规划时参考规则约束 | ✅ 完成 |
| AgentLoop._phase_reflect 记录失败 | 反思脑判定质量不佳时记录失败经验 | ✅ 完成 |
| 侧边栏状态增强 | 显示规则数+待审核教训数 | ✅ 完成 |
| 记忆管理 UI | Phase 2.5 再做 | ⏳ 延后 |
| 规则确认弹窗 | Phase 2.5 再做 | ⏳ 延后 |

**验证结果**：
- 回归测试: 181/181 通过 (100%) ✅
- 规则创建/匹配/注入: 全部成功 ✅
- 硬规则检测: 正确识别 ✅
- 失败经验记录: 降级模式正常 ✅

### Phase 3：知识库集成（v0.4.0）

**目标**：从"记住偏好"到"理解业务"

- 集成 CarryMem ObsidianAdapter
- 用户笔记/文档自动索引
- 知识库搜索增强技能执行
- 记忆+知识联合召回

### Phase 4：飞轮效应（v0.5.0+）

**目标**：数据壁垒形成

- 记忆质量评分 + 自动清理
- 记忆导出/迁移工具
- 记忆驱动的技能推荐
- 产品叙事升级："越用越懂你，越懂你越难离开"

---

## 五、安全考量

| 风险 | 缓解措施 |
|------|----------|
| SQLite 文件权限 | 集成时强制 `chmod 600` |
| 记忆注入攻击 | CarryMem 已有 10+ 注入模式检测，集成时做二次过滤 |
| 加密密钥管理 | 存储在 .env，确保 .gitignore 包含 |
| 数据备份 | 自动每日备份，备份文件加密 |
| GDPR 合规 | 提供一键导出/删除所有记忆 |

---

## 六、产品叙事升级

### 当前叙事
> "AI驱动的一人公司助手"

### 升级后叙事
> "你的AI合伙人，越用越懂你的经营风格"

### 核心差异化
- vs 通用AI助手：记忆完全由用户掌控（本地存储、可导出、可删除）
- vs Mem0：规则引擎 > 纯记忆检索，规则是用户行为指纹的结构化提取
- vs 角色扮演类产品：不是"扮演专家"，是"将你的专业经验编码为可重复执行的SOP"

---

## 七、行动项

| 优先级 | 行动项 | 负责角色 |
|--------|--------|---------|
| P0 | 创建 `memory_bridge.py` 适配层 | Coder |
| P0 | AgentLoop 注入 build_context/remember 钩子 | Coder |
| P0 | CarryMem 禁用状态回归测试 | Tester |
| P1 | 环境变量配置 + .env.example 更新 | Coder |
| P1 | requirements.txt 添加可选依赖 | DevOps |
| P1 | 侧边栏记忆状态指示器 | UI |
| P2 | A/B 对比测试框架 | Tester |
| P2 | build_context() 性能基准测试 | Tester |
| P2 | 安全审计：记忆注入风险评估 | Security |
