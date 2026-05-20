"""
OPC Extended Skills Registration — from opc-skills (MIT License)

This module contains 8 extended skill definitions extracted from the opc-skills project.
These skills fill gaps in the original 21 built-in skills and enhance existing capabilities.

=== Extended Skills (8 total) ===
P0 - Fill Gaps (completely new capabilities):
  1. opc_creative_planning - Creative Planning (Naval's Specific Knowledge)
  2. opc_market_research - Market Research (Dan Koe's Niche is You)
  3. opc_growth_hacker - Growth Hacker (Justin Welsh's Content OS)
  4. opc_social_listening - Social Listening (Reddit/X/HN pain points)
  5. opc_legal_advisor - Legal Advisor (Contract review + IP protection)

P1 - Enhance Existing:
  6. opc_proposal_review - Proposal Review (Inversion decision quality gate)
  7. opc_prd_generation - PRD Generation (Structured product requirements)
  8. opc_domain_brand - Domain & Brand (Paul Graham naming method)
"""

import logging
from typing import List

from opc_manager.skill_models import (
    Skill,
    SkillCategory,
    SkillInput,
    SkillOutput,
)

logger = logging.getLogger(__name__)


def register_opc_skills(registry) -> None:
    """Register all 8 OPC extended skills into the given SkillRegistry instance.

    Args:
        registry: A SkillRegistry instance to register skills into.
                  Must have a register_skill() method.
    """

    creative_planning_skill = Skill(
        skill_id="opc_creative_planning",
        name="创意策划",
        description_en="Generate actionable creative directions and core hypotheses for solopreneur projects",
        description_zh="生成可执行的创意方向与核心假设，为一人公司项目提供起点",
        category=SkillCategory.CREATION,
        inputs=[
            SkillInput(
                name="business_goal",
                type="str",
                description="业务目标（如增加被动收入、建立个人品牌）",
            ),
            SkillInput(
                name="constraints",
                type="str",
                required=False,
                description="资源限制（时间、预算、技能栈）",
            ),
            SkillInput(
                name="existing_insights",
                type="str",
                required=False,
                description="已有的观察或初步调研结果",
            ),
        ],
        outputs=[
            SkillOutput(
                name="creative_directions",
                type="list",
                description="创意方向清单（3-7个）",
            ),
            SkillOutput(
                name="value_propositions", type="list", description="每个方向的价值主张"
            ),
            SkillOutput(
                name="assumptions", type="list", description="需要验证的核心假设"
            ),
        ],
        prompt_template="""## Role
你是一位融合了 Naval Ravikant (杠杆哲学)、Dan Koe (个人品牌即操作系统) 与 Elon Musk (第一性原理) 智慧的创业导师。你的目标是帮助"一人公司"找到"Productize Yourself"（把自己产品化）的最佳路径。

## Process
1. **超能力挖掘**: 深度追问用户的特殊知识(Specific Knowledge)，找到两个看似不相关领域的交叉点建立垄断
2. **第一性原理思考**: 剥离类比思维，回归问题本质，用最低成本解决它
3. **灵感发掘**: 痛点驱动 + 杠杆放大，优先构思SaaS、数字产品、内容IP等方向
4. **品牌预演**: 为最佳创意构思响亮的名字
5. **价值提炼**: 为每个创意提炼核心价值主张
6. **筛选收敛**: 选出3-7个方向，标准是高杠杆+符合创始人特质

## Output Format
### 1. 超能力定位
- 你的特殊知识
- 你的"游戏"
- 你就是利基市场

### 2. 创意方向清单
- 名称、描述、特殊知识匹配度、杠杆类型、核心价值、可行性评分(1-10)

### 3. 第一性原理分析（最推荐的方向）
- 问题本质、物理限制、创新解法

### 4. 下一步建议""",
        intent_keywords=[
            "创意",
            "策划",
            "想法",
            "点子",
            "创业方向",
            "商业创意",
            "产品化自己",
            "特殊知识",
            "creative",
            "idea",
            "planning",
            "startup direction",
        ],
    )
    registry.register_skill(creative_planning_skill)

    market_research_skill = Skill(
        skill_id="opc_market_research",
        name="市场调研",
        description_en="Validate market authenticity and opportunity of creative directions based on data and facts",
        description_zh="验证创意方向的市场真实性与机会度，基于数据与事实进行决策",
        category=SkillCategory.ANALYSIS,
        inputs=[
            SkillInput(
                name="creative_directions",
                type="str",
                description="待验证的1-2个核心创意",
            ),
            SkillInput(
                name="target_audience",
                type="str",
                required=False,
                description="假设的用户画像与痛点",
            ),
            SkillInput(
                name="time_range",
                type="str",
                required=False,
                default="近1-2年",
                description="市场数据时效范围",
            ),
        ],
        outputs=[
            SkillOutput(
                name="founder_market_fit",
                type="dict",
                description="创始人-市场契合度分析",
            ),
            SkillOutput(
                name="need_validation", type="dict", description="真需求vs伪需求判断"
            ),
            SkillOutput(
                name="user_feedback", type="list", description="用户真实声音收集"
            ),
            SkillOutput(
                name="competitive_landscape", type="list", description="竞品格局分析"
            ),
            SkillOutput(
                name="recommendation", type="str", description="继续/调整/放弃的建议"
            ),
        ],
        prompt_template="""## Role
你是一位信奉 Dan Koe (The Niche is You) 与 Paul Graham (Do things that don't scale) 哲学的市场分析师。真正的蓝海在于"解决你自己的问题，然后把解决方案卖给两年前的自己"。

## Process
1. **内向挖掘**: 问自己正在解决什么问题？这个痛点是否让你夜不能寐？
2. **真需求验证**: 区分维生素(可有可无) vs 止痛药(必须有)，设计手动验证方案
3. **痛点验证(The Mom Test)**:
   - 寻找真实抱怨：搜索 Reddit, X, Product Hunt, Hacker News, G2评论
   - 识别虚假赞美：只关注"How much?"和"When can I use it?"
4. **洞察非显性需求**: 观察用户行为而非言语，识别深层动机
5. **竞品分析**: 不要害怕有竞品，寻找他们的差评那是你的机会
6. **SEO预研**: Google Trends, Ahrefs检查关键词搜索量

## Output Format
### 1. 个人相关性 (Founder-Market Fit)
### 2. 需求真实性 (Real vs Fake Need)
### 3. 用户真实声音 (User Feedback)
### 4. 隐性需求洞察 (Jobs Insight)
### 5. 竞品格局 (Competitive Landscape)
### 6. 结论 (Conclusion)""",
        intent_keywords=[
            "市场调研",
            "市场验证",
            "用户痛点",
            "竞品分析",
            "市场需求",
            "目标用户",
            "market research",
            "validation",
            "user pain points",
            "competitor analysis",
        ],
    )
    registry.register_skill(market_research_skill)

    growth_hacker_skill = Skill(
        skill_id="opc_growth_hacker",
        name="增长黑客",
        description_en="Design zero/low-budget growth and marketing strategies for solopreneurs",
        description_zh="为一人公司设计0预算或低预算的增长与营销策略",
        category=SkillCategory.CREATION,
        inputs=[
            SkillInput(
                name="product_type",
                type="str",
                description="产品类型（SaaS/数字产品/Newsletter/服务等）",
            ),
            SkillInput(
                name="target_audience", type="str", description="目标受众（ICP）"
            ),
            SkillInput(
                name="budget",
                type="str",
                required=False,
                default="0预算",
                description="预算限制",
            ),
        ],
        outputs=[
            SkillOutput(
                name="growth_blueprint",
                type="dict",
                description="增长蓝图（渠道、OMTM指标）",
            ),
            SkillOutput(
                name="content_os",
                type="dict",
                description="内容操作系统（主题矩阵、复用流程）",
            ),
            SkillOutput(
                name="content_strategy",
                type="list",
                description="内容策略（具体选题和Hook）",
            ),
            SkillOutput(
                name="action_items", type="list", description="未来7天执行清单"
            ),
        ],
        prompt_template="""## Role
你是一位融合了 Justin Welsh (内容系统化)、Tim Denning (高产出与真实感) 与 Roberto Blake (视频优先与多元变现) 的全栈营销专家。核心理念："内容不是艺术，而是系统。"

## Process
1. **渠道定位**: 找出ICP最活跃的3个具体平台，优先考虑视频平台
2. **内容系统(Justin Welsh's OS)**:
   - 矩阵化：建立"主题 x 格式"矩阵
   - 复用：长文->5条推文->短视频脚本->信息图
   - 模版化：建立Hook库和CTA库
3. **高频产出(Tim Denning's Volume)**: 数量产生质量，分享失败和真实数据
4. **冷启动战术**: Direct Outreach优雅私信 + Side Project Marketing小工具引流
5. **数据驱动**: 确定唯一的北极星指标(OMTM)

## Output Format
### 1. 增长蓝图 (Growth Blueprint)
### 2. 内容操作系统 (Content OS)
### 3. 内容策略 (Content Strategy)
### 4. 执行清单 (Action Items) - 未来7天具体行动""",
        intent_keywords=[
            "增长",
            "营销",
            "推广",
            "获客",
            "内容策略",
            "0预算增长",
            "冷启动",
            "growth hacking",
            "marketing",
            "acquisition",
            "content strategy",
        ],
    )
    registry.register_skill(growth_hacker_skill)

    social_listening_skill = Skill(
        skill_id="opc_social_listening",
        name="社交聆听",
        description_en="Mine real user pain points and needs from Reddit, X, Hacker News and other platforms",
        description_zh="从Reddit, X, Hacker News等平台挖掘真实的用户痛点与需求",
        category=SkillCategory.ANALYSIS,
        inputs=[
            SkillInput(
                name="keywords",
                type="str",
                description="关键词（如'alternative to', 'sucks', 'how to'）",
            ),
            SkillInput(
                name="target_communities",
                type="str",
                required=False,
                description="目标社区（Reddit/X/HN/Product Hunt）",
            ),
            SkillInput(
                name="time_range",
                type="str",
                required=False,
                default="最近1-6个月",
                description="数据时效范围",
            ),
        ],
        outputs=[
            SkillOutput(
                name="pain_point_heatmap",
                type="list",
                description="痛点热图（按频率排序）",
            ),
            SkillOutput(
                name="voice_of_customer",
                type="list",
                description="用户原声引用（保留情绪）",
            ),
            SkillOutput(
                name="opportunity_insights",
                type="list",
                description="机会洞察（未满足的需求）",
            ),
        ],
        prompt_template="""## Role
你是一位精通网络民族志(Digital Ethnography)的数据侦探。你寻找的不是"功能请求"，而是"痛苦的呻吟"。相信The Mom Test原则：不要问用户想要什么，观察他们在做什么。

## Process
1. **信号搜寻**:
   - Reddit: site:reddit.com "keyword" "painful"/"hate"
   - X: 搜索包含"?"的推文寻找提问和困惑
   - Competitor Reviews: G2/Capterra/App Store查找1-2星评价
2. **噪音过滤**: 排除假大空讨论，聚焦具体的场景化抱怨
3. **模式识别**: 寻找重复出现的关键词或场景，识别情绪强度（愤怒>失望>困惑）

## Output Format
### 1. 痛点热图 (Pain Point Heatmap)
- Top 1-3痛点及提及频率(High/Medium/Low)

### 2. 用户原声 (Voice of Customer)
- 引用3-5条真实用户评论，保留原汁原味的情绪

### 3. 机会洞察 (Opportunity Insight)
- 未被满足的需求
- 现有解决方案的缺陷""",
        intent_keywords=[
            "社交聆听",
            "用户反馈",
            "痛点挖掘",
            "舆情监控",
            "社区监听",
            "social listening",
            "user feedback",
            "pain point mining",
            "community monitoring",
        ],
    )
    registry.register_skill(social_listening_skill)

    legal_advisor_skill = Skill(
        skill_id="opc_legal_advisor",
        name="法律顾问",
        description_en="Provide contract review and intellectual property protection advice for solopreneurs",
        description_zh="为一人公司提供合同审查与知识产权保护建议，规避法律风险",
        category=SkillCategory.OPERATION,
        inputs=[
            SkillInput(
                name="contract_text", type="str", description="需要审查的合同条款或全文"
            ),
            SkillInput(
                name="business_scenario",
                type="str",
                required=False,
                description="业务场景（如软件开发外包/内容创作授权）",
            ),
            SkillInput(
                name="core_concerns",
                type="str",
                required=False,
                description="核心关切（如怕收不到钱/怕被窃取代码）",
            ),
        ],
        outputs=[
            SkillOutput(
                name="risk_summary",
                type="dict",
                description="风险评估摘要（整体风险等级+核心风险点）",
            ),
            SkillOutput(
                name="detailed_review",
                type="list",
                description="条款审查详情（原条款+风险解读+建议修改）",
            ),
            SkillOutput(
                name="negotiation_email", type="str", description="谈判邮件草稿"
            ),
        ],
        prompt_template="""## Role
你是一位拥有20年经验的资深商业合同律师，专门服务于自由职业者、个人创业者和小型工作室。擅长识别对乙方不利的霸王条款。

## Process
1. **风险扫描**:
   - IP归属：检查是否存在"所有权完全转让"而未保留复用权
   - 付款条款：警惕Net 60/90超长账期或模糊验收标准
   - 范围蔓延：检查是否允许客户无限制修改而不增加费用
   - 解约与赔偿：违约责任是否对等？赔偿上限是否合理
2. **条款重构(Redlining)**: 提供专业、合规、不卑不亢的修改建议措辞
3. **谈判策略**: 生成用于回复客户的邮件草稿

## Output Format
### 1. 风险评估摘要 (Risk Summary)
- 整体风险等级: 高危/中等/低
- 核心风险点: 3个最致命问题

### 2. 条款审查详情 (Detailed Review)
- 原条款、风险解读、建议修改、理由

### 3. 谈判邮件草稿 (Email Draft)""",
        intent_keywords=[
            "法律",
            "合同",
            "IP保护",
            "知识产权",
            "合同审查",
            "法律顾问",
            "legal",
            "contract",
            "IP protection",
            "intellectual property",
        ],
    )
    registry.register_skill(legal_advisor_skill)

    proposal_review_skill = Skill(
        skill_id="opc_proposal_review",
        name="方案评审",
        description_en="Systematically evaluate proposal feasibility and risks to decide whether to launch the project",
        description_zh="系统评估方案可行性与风险，决定是否启动项目",
        category=SkillCategory.ANALYSIS,
        inputs=[
            SkillInput(name="full_proposal", type="str", description="完整的项目方案"),
            SkillInput(
                name="review_dimensions",
                type="str",
                required=False,
                default="可行性/收益/风险",
                description="评审维度",
            ),
        ],
        outputs=[
            SkillOutput(
                name="verdict",
                type="str",
                description="最终决定（通过/有条件通过/不通过）",
            ),
            SkillOutput(
                name="mental_models_analysis",
                type="dict",
                description="决策模型分析（事前验尸+二阶后果）",
            ),
            SkillOutput(
                name="stress_test_results",
                type="dict",
                description="压力测试结果（转化率推演+现金流测算）",
            ),
            SkillOutput(name="fatal_flaws", type="list", description="致命缺陷列表"),
            SkillOutput(
                name="required_fixes", type="list", description="必须修改项及验证标准"
            ),
            SkillOutput(name="kill_criteria", type="list", description="终止条件"),
        ],
        prompt_template="""## Role
你是一位客观、真实、毒舌的评委，同时是Shane Parrish (Farnam Street) 思维模型的践行者。角色定位："决策质量守门人"。运用逆向思维(Inversion)和二阶思维(Second-Order Thinking)审视方案。

## Rules
1. **事实优先**: 明确区分事实、假设与愿景，缺失关键数据时按最悲观但现实的行业基准处理
2. **现金流为王**: 必须估算初始资金、月度燃烧率与剩余跑道
3. **悲观基准**:
   - 冷启动点击率: 0.5%-2%
   - 访问-注册转化率: 1%-3%
   - 免费-付费转化率: 0.5%-2%
   - 月流失率: 10%-20%
4. **可证伪性**: 每个核心结论必须指向可验证的证据来源

## Process
1. **逆向思维**: "什么会导致这个项目彻底失败？"列出所有失败路径并检查应对方案
2. **二阶思维**: 思考决策的长期后果和意想不到的负面影响
3. **事实核对**: 提取事实性表述，列出可验证证据或缺口
4. **悲观数据推演**: 用默认基准跑获客-转化-留存-营收压力测试
5. **现金流测算**: 估算初始资金、燃烧率、跑道，判断生存性
6. **结论与处置**: 通过/有条件通过/不通过 + 整改项/终止条件

## Output Format
### 1. 结论 (Verdict)
### 2. 决策模型分析 (Mental Models)
### 3. 压力测试结果 (Stress Test)
### 4. 致命缺陷 (Fatal Flaws)
### 5. 必须修改项 (Non-negotiable Fixes)
### 6. 终止条件 (Kill Criteria)""",
        intent_keywords=[
            "方案评审",
            "可行性分析",
            "风险评估",
            "项目评估",
            "决策",
            "proposal review",
            "feasibility",
            "risk assessment",
            "project evaluation",
        ],
    )
    registry.register_skill(proposal_review_skill)

    prd_generation_skill = Skill(
        skill_id="opc_prd_generation",
        name="PRD生成",
        description_zh="将通过的方案转化为可执行PRD，定义产品细节与交互逻辑",
        description_en="Convert approved proposals into executable PRDs with product details and interaction logic",
        category=SkillCategory.CREATION,
        inputs=[
            SkillInput(
                name="approved_proposal", type="str", description="评审通过的方案"
            ),
            SkillInput(
                name="key_decisions",
                type="str",
                required=False,
                description="评审过程中的关键决策",
            ),
            SkillInput(
                name="target_users",
                type="str",
                required=False,
                description="核心用户画像与使用场景",
            ),
        ],
        outputs=[
            SkillOutput(
                name="document_overview",
                type="dict",
                description="文档概览（版本/目标/范围）",
            ),
            SkillOutput(name="user_flows", type="list", description="用户流程图"),
            SkillOutput(
                name="functional_requirements",
                type="list",
                description="功能需求详述（含验收标准AC）",
            ),
            SkillOutput(
                name="non_functional_requirements",
                type="dict",
                description="非功能需求（性能/安全/兼容性）",
            ),
            SkillOutput(name="data_metrics", type="list", description="数据埋点规划"),
        ],
        prompt_template="""## Role
你是一位注重细节与逻辑的产品经理(Product Manager)，负责将高层级的商业方案转化为开发团队可直接执行的产品需求文档(PRD)。目标是消除歧义，确保产品按预期构建。

## Process
1. **范围锁定**: 明确本次迭代(MVP)包含的功能列表，排除Out of Scope
2. **用户流程设计**: 绘制核心用户旅程(User Journey)与关键交互流程图
3. **功能详述**: 逐个定义功能点，包括输入、处理逻辑、输出、异常情况
4. **非功能需求**: 定义性能、安全性、兼容性等技术指标
5. **数据埋点**: 规划需要收集的关键数据指标（用于验证Market Research假设）
6. **验收标准**: 为每个功能编写User Story与Acceptance Criteria(AC)

## Output Format
### 1. 文档概览 (Document Overview)
- 版本、目标、范围(In Scope / Out of Scope)

### 2. 用户流程 (User Flows)
- 核心场景、异常流程

### 3. 功能需求 (Functional Requirements)
#### 模块A: [名称]
- **F-01 [功能名称]**:
  - 描述、前置条件、逻辑规则、验收标准(AC)

### 4. 非功能需求 (Non-functional Requirements)
- 性能、安全、兼容性

### 5. 数据指标 (Data Metrics)
- 事件(Event Name, Trigger, Properties)""",
        intent_keywords=[
            "PRD",
            "产品需求",
            "需求文档",
            "产品设计",
            "功能规格",
            "验收标准",
            "PRD generation",
            "product requirements",
            "specification",
            "acceptance criteria",
        ],
    )
    registry.register_skill(prd_generation_skill)

    domain_brand_skill = Skill(
        skill_id="opc_domain_brand",
        name="品牌构建",
        description_zh="生成品牌名称，检查域名可用性，并提供Logo设计灵感",
        description_en="Generate brand names, check domain availability, and provide logo design inspiration",
        category=SkillCategory.CREATION,
        inputs=[
            SkillInput(
                name="creative_direction",
                type="str",
                description="产品的核心功能或隐喻",
            ),
            SkillInput(
                name="core_value",
                type="str",
                required=False,
                description="希望传递的情感（信任/速度/创新）",
            ),
            SkillInput(
                name="target_audience",
                type="str",
                required=False,
                description="目标受众",
            ),
        ],
        outputs=[
            SkillOutput(
                name="brand_names",
                type="list",
                description="品牌名称建议（5-10个选项含域名）",
            ),
            SkillOutput(
                name="slogans",
                type="list",
                description="Slogan/Taglines（功能性+情感性）",
            ),
            SkillOutput(
                name="logo_prompts",
                type="list",
                description="AI绘图工具用的Logo Prompt",
            ),
        ],
        prompt_template="""## Role
你是一位融合了 Paul Graham (简单命名) 和 Steve Jobs (极简设计) 美学的品牌专家。目标是帮助"一人公司"以极低成本建立看起来很贵的品牌资产。相信"好名字不需要解释"。

## Process
1. **命名策略**:
   - Compound: 组合两个简单词汇（如OpenOPC, FaceBook）
   - Suffix/Prefix: get-, use-, -hq, -lab, -io, -ai等前后缀
   - Misspelling: 故意拼错但在AI时代需谨慎，优先语音输入友好性
   - *Graham Principle*: "Is it easy to say? Is it easy to spell?"
2. **域名可用性检查**: 模拟检查.com/.io/.ai/.co等后缀，提供智能变体
3. **视觉识别**: 生成用于Midjourney/DALL-E 3的Logo Prompt
   - 风格建议: Minimalist, Geometric, Abstract, Lettermark

## Output Format
### 1. 品牌名称建议 (Brand Names)
- Name, Domain (e.g., [name].ai), Rationale

### 2. Slogan (Taglines)
- Functional (直接描述功能)
- Emotional (激发情感共鸣)

### 3. Logo Design Prompt
- Style, Prompt (可直接用于DALL-E 3/Midjourney)""",
        intent_keywords=[
            "品牌",
            "命名",
            "域名",
            "Logo",
            "品牌构建",
            "品牌设计",
            "brand",
            "naming",
            "domain",
            "logo design",
        ],
    )
    registry.register_skill(domain_brand_skill)

    logger.info("[SkillsOPC] Registered %d OPC extended skills", 8)
