# OPC-Agents 架构设计文档 v2.1

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v2.1.0 | 2026-04-14 | 架构师 | 基于6大业务类型扩展场景引擎、人格系统、标签体系 | 待审核 |
| v2.0.0 | 2026-04-07 | 架构师 | 初始版本，3场景+基础架构 | 已审核 |

---

## 一、架构概述

### 1.1 系统边界

```
┌─────────────────────────────────────────────────────────────┐
│                    OPC-Agents 系统边界                        │
│                                                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ 用户界面层 │  │ API 层    │  │ 外部集成   │              │
│  │ (Web/Chat) │  │ (REST)   │  │ (平台API) │              │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘              │
│        │               │               │                     │
│  ┌─────▼───────────────▼───────────────▼─────┐            │
│  │              核心业务层                      │            │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────────┐  │            │
│  │  │ 场景引擎 │ │ 人格系统 │ │ 工作流引擎   │  │            │
│  │  └────┬────┘ └────┬────┘ └──────┬──────┘  │            │
│  │       │           │             │          │            │
│  │  ┌────▼───────────▼─────────────▼──────┐  │            │
│  │  │         任务管理与执行层              │  │            │
│  │  │  ┌─────────┐ ┌─────────┐ ┌────────┐ │  │            │
│  │  │  │ 任务调度 │ │ 执行器   │ │ 结果管理│ │  │            │
│  │  │  └─────────┘ └─────────┘ └────────┘ │  │            │
│  │  └─────────────────────────────────────┘  │            │
│  └───────────────────────────────────────────┘            │
│                                                             │
│  ┌───────────────────────────────────────────┐            │
│  │              基础设施层                      │            │
│  │  数据存储 │ 消息队列 │ 缓存 │ 日志 │ 监控     │            │
│  └───────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心模块清单

| 模块 | 职责 | 当前状态 | v2.1 变更 |
|------|------|---------|-----------|
| `scenario_engine` | 场景识别与工作流编排 | ✅ 3个场景 | 🆕 扩展至9个 |
| `persona_system` | 人格配置与切换 | ⚠️ 单一人格 | 🆕 6种变体 |
| `workflow_engine` | 工作流步骤执行 | ✅ 基础版 | 🔧 增加并行支持 |
| `task_manager` | 任务生命周期管理 | ✅ 完整 | 🔧 增加类型维度 |
| `tag_system` | 标签分类与管理 | ✅ 4维度 | 🆕 增加 business_type |

---

## 二、功能映射分析（6大类型 × 现有架构）

### 2.1 覆盖度矩阵

```
                现有模块覆盖情况
                ════════════════

类型        场景引擎  人格系统  工作流  标签  数据源  集成
─────────────────────────────────────────────────────
① 内容创作   ⚠️ 部分   ❌ 缺失  ⚠️ 部分  ✅    ❌      ❌
② 数字产品   ✅ 较好   ❌ 缺失  ✅ 较好  ✅    ❌      ❌
③ AI工具     ❌ 空白   ❌ 缺失  ❌ 空白  ⚠️    ⚠️      ✅
④ 咨询服务   ⚠️ 部分   ❌ 缺失  ⚠️ 部分  ✅    ❌      ❌
⑤ 电商运营   ❌ 空白   ❌ 缺失  ❌ 空白  ❌      ❌      ❌
⑥ 创意工作   ⚠️ 部分   ❌ 缺失  ⚠️ 部分  ✅    ⚠️      ❌

图例：
✅ = 完全覆盖（>80%）
⚠️ = 部分覆盖（30-80%）
❌ = 几乎空白（<30%）
```

### 2.2 各类型详细映射

#### 类型①：内容创作者 - 功能缺口分析

```python
CONTENT_CREATOR_GAP_ANALYSIS = {
    "scenario_engine": {
        "covered": ["organize_meeting"],  # 可用于内容策划会议
        "missing": [
            "content_calendar",       # 核心！内容日历规划
            "trend_analysis",         # 热点趋势分析
            "multi_platform_publish"  # 多平台发布协调
        ],
        "gap_score": 0.35  # 35%覆盖
    },
    "data_sources": {
        "required": [
            ("小红书", "热点API / 爬虫"),
            ("抖音", "Trend API"),
            ("微信", "公众号数据"),
            ("B站", "数据中心API")
        ],
        "current_support": None,  # 无现成集成
        "priority": "P0"
    },
    "integration_needs": [
        "Notion API (日历同步)",
        "Canva API (封面生成)",
        "各平台发布API"
    ]
}
```

#### 类型②：数字产品开发者 - 功能缺口分析

```python
DIGITAL_PRODUCT_GAP_ANALYSIS = {
    "scenario_engine": {
        "covered": ["launch_product"],  # 可复用为产品发布
        "missing": [
            "digital_product_launch",  # 需要定制化
            "pricing_optimizer",        # 定价优化
            "sales_page_generator"       # 销售页生成
        ],
        "gap_score": 0.55  # 55%覆盖
    },
    "data_sources": {
        "required": [
            ("Gumroad", "销售数据API"),
            ("小报童", "订单API"),
            ("知识星球", "成员API")
        ],
        "current_support": None,
        "priority": "P1"
    }
}
```

#### 类型③：AI工具开发者 - 功能缺口分析

```python
AI_TOOL_BUILDER_GAP_ANALYSIS = {
    "scenario_engine": {
        "covered": [],  # 几乎无覆盖
        "missing": [
            "feedback_analysis",       # 核心！用户反馈分析
            "feature_roadmap",         # 功能路线图
            "tech_doc_generator",      # 技术文档生成
            "changelog_auto"           # 自动更新日志
        ],
        "gap_score": 0.10  # 仅10%覆盖
    },
    "data_sources": {
        "required": [
            ("App Store", "Reviews API"),
            ("GitHub", "Issues API"),
            ("Discord", "Community API"),
            ("Intercom/Zendesk", "Support API")
        ],
        "current_support": "部分（GitHub Issues可对接）",
        "priority": "P0"
    },
    "special_requirements": [
        "代码仓库集成",
        "CI/CD Pipeline联动",
        "版本管理系统对接"
    ]
}
```

#### 类型④-⑥ 的类似分析...（略，结构相同）

---

## 三、场景引擎扩展架构

### 3.1 新架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                   场景引擎 V2.1 架构                         │
│                                                             │
│  ┌─────────────┐                                           │
│  │  输入层     │  用户自然语言输入                           │
│  └──────┬──────┘                                           │
│         │                                                   │
│  ┌──────▼──────┐    ┌──────────────────────────────────┐    │
│  │ 意图识别器   │───▶│  业务类型检测器 (BusinessTypeDetector)│    │
│  │ (NLU)      │    │  - 关键词匹配                      │    │
│  └─────────────┘    │  - 上下文推理                      │    │
│                     │  - 用户历史偏好                    │    │
│                     └──────────────┬───────────────────┘    │
│                                    │                       │
│                     ┌──────────────▼───────────────────┐    │
│                     │      场景路由器 (ScenarioRouter)   │    │
│                     │  - 9个核心场景注册表               │    │
│                     │  - 置信度评分                      │    │
│                     │  - 多场景候选排序                  │    │
│                     └──────────────┬───────────────────┘    │
│                                    │                       │
│         ┌──────────────────────────┼──────────────────┐    │
│         │                          │                  │    │
│  ┌──────▼──────┐          ┌───────▼──────┐   ┌───────▼───┐│
│  │ 内容场景簇  │          │ 产品场景簇    │   │ ... 其他   ││
│  │ (3个场景)  │          │ (3个场景)    │   │           ││
│  └──────┬──────┘          └───────┬──────┘   └───────────┘│
│         │                         │                       │
│  ┌──────▼─────────────────────────▼───────────────────────┐│
│  │                    工作流引擎                            ││
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐ ││
│  │  │ 步骤1   │→│ 步骤2   │→│ 步骤3   │→│ 交付物生成  │ ││
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────┘ ││
│  └───────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心类设计

```python
# scenario_engine_v2.py

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class BusinessType(Enum):
    """6大业务类型枚举"""
    CONTENT_CREATOR = "content_creator"       # ① 内容创作
    DIGITAL_PRODUCT = "digital_product"       # ② 数字产品
    AI_TOOL_BUILDER = "ai_tool_builder"       # ③ AI工具
    CONSULTANT = "consultant"                 # ④ 专业咨询
    ECOMMERCE = "ecommerce"                   # ⑤ 电商运营
    CREATIVE_WORK = "creative_work"           # ⑥ 创意生产


@dataclass
class ScenarioConfig:
    """场景配置"""
    id: str
    name: str
    description: str
    trigger_phrases: List[str]
    target_business_types: List[BusinessType]
    workflow_steps: List[WorkflowStep]
    estimated_duration: str
    deliverable_template: DeliverableTemplate
    confidence_threshold: float = 0.5


@dataclass
class WorkflowStep:
    """工作流步骤"""
    step_id: int
    name: str
    type: str  # research/analysis/writing/generation/review
    description: str
    estimated_duration: str
    dependencies: List[int]  # 依赖的步骤ID列表
    output_spec: OutputSpec
    executor: str  # 执行器名称（如 "hotspot_scanner", "llm_writer"）


class ScenarioEngineV2:
    """场景引擎 V2 - 支持9个核心场景"""
    
    def __init__(self):
        self.scenarios = self._load_scenarios()
        self.type_detector = BusinessTypeDetector()
        self.persona_manager = PersonaManager()
        
    def _load_scenarios(self) -> Dict[str, ScenarioConfig]:
        """加载所有场景配置"""
        return {
            # 现有场景（v2.0）
            "launch_product": self._launch_product_scenario(),
            "write_report": self._write_report_scenario(),
            "organize_meeting": self._organize_meeting_scenario(),
            
            # 新增场景（v2.1）
            "content_calendar": self._content_calendar_scenario(),
            "digital_product_launch": self._digital_product_launch_scenario(),
            "feedback_analysis": self._feedback_analysis_scenario(),
            "consulting_proposal": self._consulting_proposal_scenario(),
            "ecommerce_ops": self._ecommerce_ops_scenario(),
            "project_deliverable": self._project_deliverable_scenario(),
        }
    
    def process(self, user_input: str, user_context: Dict) -> ScenarioResult:
        """
        处理用户输入，返回场景匹配结果
        
        Args:
            user_input: 用户自然语言输入
            user_context: 用户上下文（含profile、history等）
            
        Returns:
            ScenarioResult: 匹配结果及推荐的工作流
        """
        # Step 1: 检测业务类型
        detected_type = self.type_detector.detect(
            input_text=user_input,
            user_profile=user_context.get("profile"),
            history=user_context.get("conversation_history", [])
        )
        
        # Step 2: 匹配场景（过滤目标类型）
        candidates = []
        for scenario_id, config in self.scenarios.items():
            if detected_type in config.target_business_types or \
               BusinessType.ALL in config.target_business_types:
                confidence = self._calculate_match_confidence(
                    user_input, config.trigger_phrases
                )
                if confidence >= config.confidence_threshold:
                    candidates.append((scenario_id, confidence, config))
        
        # Step 3: 排序并选择最佳匹配
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        if not candidates:
            return ScenarioResult(
                matched=False,
                suggestion="未匹配到具体场景，是否需要我帮您梳理需求？"
            )
        
        best_match = candidates[0]
        
        # Step 4: 加载对应人格
        persona = self.persona_manager.get_persona(
            user_id=user_context.get("user_id"),
            business_type=detected_type,
            context={"scenario_id": best_match[0]}
        )
        
        return ScenarioResult(
            matched=True,
            scenario_id=best_match[0],
            scenario_config=best_match[2],
            confidence=best_match[1],
            detected_business_type=detected_type,
            persona=persona,
            workflow=self._build_workflow(best_match[2])
        )
    
    def _content_calendar_scenario(self) -> ScenarioConfig:
        """内容日历规划场景"""
        return ScenarioConfig(
            id="content_calendar",
            name="内容日历规划",
            description="基于热点和粉丝画像，智能规划多平台内容发布计划",
            trigger_phrases=["内容日历", "选题", "发布计划", "下周发什么", "内容排期"],
            target_business_types=[BusinessType.CONTENT_CREATOR],
            estimated_duration="5-10分钟",
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="热点扫描",
                    type="data_collection",
                    description="抓取各平台热搜和趋势话题",
                    estimated_duration="30秒",
                    dependencies=[],
                    output_spec=OutputSpec(name="热点话题库", format="JSON"),
                    executor="hotspot_scanner"
                ),
                WorkflowStep(
                    step_id=2,
                    name="画像匹配",
                    type="analysis",
                    description="结合粉丝画像筛选合适话题",
                    estimated_duration="20秒",
                    dependencies=[1],
                    output_spec=OutputSpec(name="筛选后选题池", format="List"),
                    executor="audience_matcher"
                ),
                WorkflowStep(
                    step_id=3,
                    name="选题生成",
                    type="generation",
                    description="生成具体选题建议和角度",
                    estimated_duration="1分钟",
                    dependencies=[2],
                    output_spec=OutputSpec(name="选题清单", format="Table"),
                    executor="topic_generator_llm"
                ),
                WorkflowStep(
                    step_id=4,
                    name="日历排期",
                    type="scheduling",
                    description="分配到具体日期和平台",
                    estimated_duration="30秒",
                    dependencies=[3],
                    output_spec=OutputSpec(name="内容日历", format="Calendar/Excel"),
                    output_spec=OutputSpec(name="效果预估", format="Metrics"),
                    executor="calendar_scheduler"
                ),
                WorkflowStep(
                    step_id=5,
                    name="输出整理",
                    type="formatting",
                    description="格式化为可执行的发布计划",
                    estimated_duration="15秒",
                    dependencies=[4],
                    output_spec=OutputSpec(name="最终交付物", format="Multi-format"),
                    executor="output_formatter"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="周内容日历",
                sections=["选题清单", "发布时间表", "素材准备清单", "效果预估"]
            )
        )
    
    # ... 其他场景定义方法类似
```

### 3.3 数据模型扩展

```sql
-- 新增：business_type 维度
CREATE TABLE user_business_types (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    business_type VARCHAR(32) NOT NULL,  -- 对应 BusinessType 枚举
    is_primary BOOLEAN DEFAULT FALSE,
    confidence_score FLOAT DEFAULT 0.0,
    detected_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, business_type)
);

-- 新增：场景执行记录（扩展）
ALTER TABLE task_executions 
ADD COLUMN business_type VARCHAR(32),
ADD COLUMN scenario_id VARCHAR(64),
ADD COLUMN persona_variant VARCHAR(32);

-- 新增：飞轮状态追踪
CREATE TABLE user_flywheel_status (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL UNIQUE,
    current_level INT DEFAULT 1,  -- 1=单一, 2=双类型, 3=全生态
    active_types JSONB DEFAULT '[]',
    flywheel_health_score FLOAT DEFAULT 0.0,
    last_transition_date TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 四、人格系统架构

### 4.1 组件设计

```
┌─────────────────────────────────────────────────────────────┐
│                     人格系统架构                              │
│                                                             │
│  ┌─────────────┐                                           │
│  │ PersonaConfig│  YAML配置文件（6种变体定义）               │
│  │ Repository  │                                           │
│  └──────┬──────┘                                           │
│         │                                                   │
│  ┌──────▼──────┐    ┌──────────────────────────────────┐    │
│  │  Persona    │◀──▶│  ContextAnalyzer                 │    │
│  │  Resolver   │    │  - 用户输入分析                   │    │
│  │             │    │  - 历史行为分析                   │    │
│  │  职责：      │    │  - 显式偏好检查                  │    │
│  │  - 选择人格 │    └──────────────────────────────────┘    │
│  │  - 合并配置 │                                           │
│  │  - 缓存结果 │    ┌──────────────────────────────────┐    │
│  └─────────────┘    │  PersonalizationEngine           │    │
│                     │  - 用户偏好学习                   │    │
│  ┌─────────────┐    │  - 长期记忆整合                   │    │
│  │  Response   │◀──▶│  - A/B测试支持                   │    │
│  │  Formatter  │    └──────────────────────────────────┘    │
│  │             │                                           │
│  │  职责：      │                                           │
│  │  - 应用风格  │                                           │
│  │  - 注入术语  │                                           │
│  │  - 格式化输出│                                           │
│  └─────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 配置示例

```yaml
# config/persona_variants.yaml

base_persona:
  name: "总裁办秘书"
  version: "2.1.0"
  core_principles:
    - name: "凡事有交代"
      description: "每个任务都有始有终"
    - name: "主动不被动"
      description: "提前思考，主动汇报"
    - name: "结果导向"
      description: "关注交付质量，不只是过程"
    - name: "简单高效"
      description: "不让您思考，一站式解决"
    - name: "持续学习"
      description: "记住您的偏好，越用越懂你"

variants:
  content_creator:
    display_name: "内容小助理"
    emoji: "✍️"
    inherits: base_persona
    style_overrides:
      tone: "轻松活泼"
      formality_level: 0.3  # 0=最随意, 1=最正式
      emoji_density: "high"
      sentence_length: "short"
      slang_allowed: true
    expertise_tags: ["内容趋势", "平台算法", "流量密码", "爆款选题"]
    vocabulary:
      domain_specific: ["种草", "拔草", "爆款", "涨粉", "完播率", "互动率"]
      forbidden: ["赋能", "抓手", "闭环", "底层逻辑"]
    dialogue_templates:
      greeting: "嗨！今天有什么爆款想法？💡"
      accept_task: "收到！这个选题很有潜力🔥，我马上帮你策划！"
      progress: "进度汇报来啦~ 📊 {task}已完成{progress}%"
      complete: "搞定啦！✨ 这是你的{deliverable}，记得检查哦~"
    proactive_rules:
      - trigger: "daily_hotspot_push"
        condition: "每天早9点"
        action: "推送当日热点TOP10"
      
  digital_product:
    display_name: "产品顾问"
    emoji: "💰"
    inherits: base_persona
    style_overrides:
      tone: "专业但亲切"
      formality_level: 0.7
      emoji_density: "medium"
      data_first: true
    expertise_tags: ["产品包装", "定价心理学", "销售文案", "漏斗分析"]
    dialogue_templates:
      greeting: "老板好！今天要打造什么爆款产品？💰"
      pricing_response: "基于竞品分析，建议定价 ${price}。理由：{reasoning}"
      
  # ... 其他4种变体配置
```

---

## 五、技术风险评估

### 5.1 风险矩阵

| 风险项 | 影响 | 概率 | 应对策略 |
|--------|------|------|---------|
| 场景识别准确率不足 | 高 | 中 | 增加人工确认环节 + 持续优化NLU模型 |
| 外部API不稳定 | 高 | 高 | 多源备份 + 本地缓存 + 降级方案 |
| 人格切换突兀 | 中 | 低 | 渐进式过渡 + 用户反馈闭环 |
| 性能瓶颈（9场景并发） | 中 | 中 | 异步处理 + 结果缓存 + 预计算 |
| 数据隐私（电商/咨询数据） | 高 | 低 | 端到端加密 + 数据脱敏 + GDPR合规 |

### 5.2 性能指标要求

| 指标 | 当前(v2.0) | 目标(v2.1) | 实现方式 |
|------|------------|------------|---------|
| 场景识别延迟 | < 1s | < 500ms | 预计算 + 缓存 |
| 工作流启动时间 | < 2s | < 1s | 异步预加载 |
| 并发场景支持 | 3个 | 9个 | 独立Worker池 |
| 人格切换延迟 | N/A | < 200ms | 配置预加载 |

---

## 六、实施路线图

### Phase 1: MVP（4周）
- [ ] 实现6个新场景的核心工作流（content_calendar, feedback_analysis, ecommerce_ops 等）
- [ ] 开发BusinessTypeDetector基础版（关键词匹配）
- [ ] 实现3种核心人格变体（content/digital/ecommerce）
- [ ] 扩展数据库schema

### Phase 2: 完善（4周）
- [ ] 剩余3种人格变体
- [ ] 外部数据源集成（小红书/抖音/Gumroad等API）
- [ ] 飞轮状态追踪系统
- [ ] A/B测试框架搭建

### Phase 3: 优化（持续）
- [ ] 基于用户反馈优化场景识别准确率
- [ ] 个性化学习引擎
- [ ] 性能调优和规模化

---

## 七、决策记录（ADR）

### ADR-001: 选择关键词匹配作为主要检测方式
**决策**：优先使用关键词匹配，辅以LLM语义理解
**理由**：
- 实现简单，可解释性强
- 速度快（<100ms vs LLM >1s）
- 可通过规则快速迭代
**替代方案**：纯LLM意图识别（更准但更慢）

### ADR-002: 人格采用YAML配置而非代码硬编码
**决策**：使用外部YAML配置文件定义人格
**理由**：
- 运营团队可直接调整
- 支持A/B测试快速切换
- 多语言适配更容易
**替代方案**：Python类继承（开发效率高但灵活性差）

---

**文档状态**：✅ 初稿完成 | ⏳ 待独立开发者评审技术可行性 | ⏳ 待测试专家评估测试策略 | ⏳ 待多角色共识

**下一步**：提交给独立开发者进行MVP范围拆解和技术实现评估
