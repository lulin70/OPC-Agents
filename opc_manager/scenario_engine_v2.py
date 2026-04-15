"""
场景引擎 V2 - 支持9个核心场景 + 6大业务类型

基于架构设计文档 v2.1 实现
支持业务类型感知、人格系统集成、结构化工作流编排
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from opc_manager.business_types import BusinessType


@dataclass
class OutputSpec:
    """输出规范定义"""
    name: str
    format: str  # JSON/Table/PDF/Excel/Calendar/Markdown等
    includes: List[str] = field(default_factory=list)


@dataclass
class DeliverableTemplate:
    """交付物模板"""
    name: str
    sections: List[str]
    format: str = "Multi-format"


@dataclass
class WorkflowStep:
    """工作流步骤定义"""
    step_id: int
    name: str
    type: str  # research/analysis/writing/generation/review/scheduling/data_collection/formatting
    description: str
    estimated_duration: str
    dependencies: List[int] = field(default_factory=list)
    output_spec: Optional[OutputSpec] = None
    executor: str = ""  # 执行器名称，如 "hotspot_scanner", "llm_writer"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "estimated_duration": self.estimated_duration,
            "dependencies": self.dependencies,
            "output_spec": {
                "name": self.output_spec.name,
                "format": self.output_spec.format,
                "includes": self.output_spec.includes
            } if self.output_spec else None,
            "executor": self.executor
        }


@dataclass
class ScenarioConfig:
    """场景配置 - 完整的场景定义"""
    id: str
    name: str
    description: str
    trigger_phrases: List[str]
    target_business_types: List[BusinessType]
    workflow_steps: List[WorkflowStep]
    estimated_duration: str
    deliverable_template: DeliverableTemplate
    confidence_threshold: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（兼容V1接口）"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger_phrases": self.trigger_phrases,
            "target_business_types": [bt.value for bt in self.target_business_types],
            "workflow_steps": [step.to_dict() for step in self.workflow_steps],
            "estimated_duration": self.estimated_duration,
            "deliverable_template": {
                "name": self.deliverable_template.name,
                "sections": self.deliverable_template.sections,
                "format": self.deliverable_template.format
            },
            "confidence_threshold": self.confidence_threshold
        }


@dataclass
class ScenarioResult:
    """场景处理结果"""
    matched: bool
    scenario_id: Optional[str] = None
    scenario_config: Optional[ScenarioConfig] = None
    confidence: float = 0.0
    detected_business_type: Optional[BusinessType] = None
    persona: Optional[Dict[str, Any]] = None
    workflow: Optional[List[Dict[str, Any]]] = None
    suggestion: Optional[str] = None
    candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "matched": self.matched,
            "confidence": self.confidence
        }
        if self.matched:
            result.update({
                "scenario_id": self.scenario_id,
                "scenario_config": self.scenario_config.to_dict() if self.scenario_config else None,
                "detected_business_type": self.detected_business_type.value if self.detected_business_type else None,
                "persona": self.persona,
                "workflow": self.workflow
            })
        else:
            result["suggestion"] = self.suggestion
        if self.candidates:
            result["candidates"] = self.candidates
        return result


class ScenarioEngineV2:
    """
    场景引擎 V2 - 核心场景识别与工作流编排引擎

    特性：
    - 支持9个核心场景（3个原有 + 6个新增）
    - 业务类型感知路由（6大类型）
    - 结构化工作流步骤定义
    - 置信度评分与多候选排序
    - 人格系统集成接口
    """

    def __init__(self):
        """初始化场景引擎V2"""
        self.scenarios: Dict[str, ScenarioConfig] = self._load_scenarios()
        self.type_detector = None  # 将在dev-2中实现
        self.persona_manager = None  # 将在dev-4中实现

    def _load_scenarios(self) -> Dict[str, ScenarioConfig]:
        """加载所有9个场景配置"""
        scenarios = {}

        # ========== 原有场景（v2.0 兼容）==========
        scenarios["launch_product"] = self._launch_product_scenario()
        scenarios["write_report"] = self._write_report_scenario()
        scenarios["organize_meeting"] = self._organize_meeting_scenario()

        # ========== 新增场景（v2.1）==========
        scenarios["content_calendar"] = self._content_calendar_scenario()
        scenarios["digital_product_launch"] = self._digital_product_launch_scenario()
        scenarios["feedback_analysis"] = self._feedback_analysis_scenario()
        scenarios["consulting_proposal"] = self._consulting_proposal_scenario()
        scenarios["ecommerce_ops"] = self._ecommerce_ops_scenario()
        scenarios["project_deliverable"] = self._project_deliverable_scenario()

        return scenarios

    # ==================== 原有场景定义 ====================

    def _launch_product_scenario(self) -> ScenarioConfig:
        """发布新产品场景（V1兼容升级版）"""
        return ScenarioConfig(
            id="launch_product",
            name="新产品发布",
            description="完整的新产品发布流程，从市场调研到最终发布",
            trigger_phrases=[
                "发布新产品", "推出新品", "新产品上线", "产品发布",
                "产品launch", "上新", "产品上市"
            ],
            target_business_types=[
                BusinessType.DIGITAL_PRODUCT,
                BusinessType.AI_TOOL_BUILDER,
                BusinessType.CONTENT_CREATOR
            ],
            estimated_duration="1 个工作日",
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="市场调研",
                    type="research",
                    description="分析目标市场、竞争对手和目标用户",
                    estimated_duration="2 小时",
                    dependencies=[],
                    output_spec=OutputSpec(
                        name="市场调研报告",
                        format="PDF/Word",
                        includes=["市场规模分析", "竞争对手分析", "目标用户画像", "市场机会点"]
                    ),
                    executor="market_researcher"
                ),
                WorkflowStep(
                    step_id=2,
                    name="产品设计方案",
                    type="design",
                    description="基于调研结果设计产品方案",
                    estimated_duration="3 小时",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="产品需求文档",
                        format="PDF/Word",
                        includes=["产品定位", "功能列表", "技术方案", "原型设计"]
                    ),
                    executor="product_designer"
                ),
                WorkflowStep(
                    step_id=3,
                    name="营销推广计划",
                    type="marketing",
                    description="制定产品营销和推广策略",
                    estimated_duration="2 小时",
                    dependencies=[2],
                    output_spec=OutputSpec(
                        name="营销推广方案",
                        format="PDF/Word",
                        includes=["营销策略", "推广渠道", "预算估算", "时间规划"]
                    ),
                    executor="marketing_planner"
                ),
                WorkflowStep(
                    step_id=4,
                    name="汇总评审",
                    type="review",
                    description="汇总所有文档，进行最终评审",
                    estimated_duration="1 小时",
                    dependencies=[1, 2, 3],
                    output_spec=OutputSpec(
                        name="新产品发布方案（完整版）",
                        format="PDF",
                        includes=["市场调研报告", "产品需求文档", "营销推广方案", "发布预算总表", "时间规划总表"]
                    ),
                    executor="review_coordinator"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="新产品发布完整方案",
                sections=["执行摘要", "市场分析", "产品方案", "营销策略", "财务预测", "风险评估", "时间规划"],
                format="PDF"
            )
        )

    def _write_report_scenario(self) -> ScenarioConfig:
        """撰写报告场景（V1兼容升级版）"""
        return ScenarioConfig(
            id="write_report",
            name="报告撰写",
            description="自动收集数据、分析并生成专业报告",
            trigger_phrases=[
                "写报告", "写总结", "分析报告", "工作汇报",
                "月度报告", "季度总结", "年度总结", "数据分析报告"
            ],
            target_business_types=[
                BusinessType.CONSULTANT,
                BusinessType.AI_TOOL_BUILDER,
                BusinessType.CONTENT_CREATOR
            ],
            estimated_duration="2-4 小时",
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="数据收集",
                    type="data_collection",
                    description="收集相关数据和资料",
                    estimated_duration="1 小时",
                    dependencies=[],
                    output_spec=OutputSpec(
                        name="数据资料包",
                        format="文件夹",
                        includes=["历史数据", "行业数据", "相关资料"]
                    ),
                    executor="data_collector"
                ),
                WorkflowStep(
                    step_id=2,
                    name="数据分析",
                    type="analysis",
                    description="分析收集的数据，提取关键信息",
                    estimated_duration="1 小时",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="分析结果",
                        format="Excel/图表",
                        includes=["数据图表", "趋势分析", "关键发现"]
                    ),
                    executor="data_analyzer"
                ),
                WorkflowStep(
                    step_id=3,
                    name="报告撰写",
                    type="writing",
                    description="基于分析结果撰写报告",
                    estimated_duration="1-2 小时",
                    dependencies=[2],
                    output_spec=OutputSpec(
                        name="完整报告",
                        format="Word/PDF",
                        includes=["摘要", "正文", "结论", "建议", "附录"]
                    ),
                    executor="report_writer"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="专业分析报告",
                sections=["摘要", "背景与目的", "数据分析", "关键发现", "结论与建议", "附录"],
                format="Word/PDF"
            )
        )

    def _organize_meeting_scenario(self) -> ScenarioConfig:
        """组织会议场景（V1兼容升级版）"""
        return ScenarioConfig(
            id="organize_meeting",
            name="会议组织",
            description="自动协调时间、发送邀请、准备材料",
            trigger_phrases=[
                "组织会议", "开会", "团队讨论", "项目会议",
                "碰头会", "安排会议", "会议安排"
            ],
            target_business_types=BusinessType.get_all_types(),  # 所有类型通用
            estimated_duration="30 分钟 - 1 小时",
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="时间协调",
                    type="scheduling",
                    description="协调参会人员时间",
                    estimated_duration="15 分钟",
                    dependencies=[],
                    output_spec=OutputSpec(
                        name="会议时间安排",
                        format="日历邀请",
                        includes=["建议时间", "备选时间", "参会人员"]
                    ),
                    executor="time_coordinator"
                ),
                WorkflowStep(
                    step_id=2,
                    name="发送邀请",
                    type="invitation",
                    description="发送会议邀请给所有参会人员",
                    estimated_duration="5 分钟",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="会议邀请",
                        format="邮件/消息",
                        includes=["会议主题", "时间地点", "议程", "参会人员"]
                    ),
                    executor="invitation_sender"
                ),
                WorkflowStep(
                    step_id=3,
                    name="材料准备",
                    type="preparation",
                    description="准备会议相关材料",
                    estimated_duration="30 分钟",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="会议材料包",
                        format="文件夹",
                        includes=["会议议程", "背景资料", "讨论要点", "决策事项"]
                    ),
                    executor="material_preparer"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="会议组织完成包",
                sections=["会议邀请", "时间安排", "材料清单", "参会确认"],
                format="Multi-format"
            )
        )

    # ==================== 新增场景定义（v2.1）====================

    def _content_calendar_scenario(self) -> ScenarioConfig:
        """内容日历规划场景 - 针对类型①内容创作者"""
        return ScenarioConfig(
            id="content_calendar",
            name="内容日历规划",
            description="基于热点和粉丝画像，智能规划多平台内容发布计划",
            trigger_phrases=[
                "内容日历", "选题", "发布计划", "下周发什么",
                "内容排期", "选题策划", "内容规划", "爆款选题"
            ],
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
                    output_spec=OutputSpec(
                        name="热点话题库",
                        format="JSON",
                        includes=["热搜榜单", "趋势话题", "热度指数"]
                    ),
                    executor="hotspot_scanner"
                ),
                WorkflowStep(
                    step_id=2,
                    name="画像匹配",
                    type="analysis",
                    description="结合粉丝画像筛选合适话题",
                    estimated_duration="20秒",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="筛选后选题池",
                        format="List",
                        includes=["匹配度评分", "受众覆盖", "竞争度"]
                    ),
                    executor="audience_matcher"
                ),
                WorkflowStep(
                    step_id=3,
                    name="选题生成",
                    type="generation",
                    description="生成具体选题建议和角度",
                    estimated_duration="1分钟",
                    dependencies=[2],
                    output_spec=OutputSpec(
                        name="选题清单",
                        format="Table",
                        includes=["标题建议", "内容角度", "预估效果"]
                    ),
                    executor="topic_generator_llm"
                ),
                WorkflowStep(
                    step_id=4,
                    name="日历排期",
                    type="scheduling",
                    description="分配到具体日期和平台",
                    estimated_duration="30秒",
                    dependencies=[3],
                    output_spec=OutputSpec(
                        name="内容日历",
                        format="Calendar/Excel",
                        includes=["发布时间", "平台分配", "内容类型"]
                    ),
                    executor="calendar_scheduler"
                ),
                WorkflowStep(
                    step_id=5,
                    name="输出整理",
                    type="formatting",
                    description="格式化为可执行的发布计划",
                    estimated_duration="15秒",
                    dependencies=[4],
                    output_spec=OutputSpec(
                        name="最终交付物",
                        format="Multi-format",
                        includes=["选题清单", "发布时间表", "素材准备清单", "效果预估"]
                    ),
                    executor="output_formatter"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="周内容日历",
                sections=["选题清单", "发布时间表", "素材准备清单", "效果预估"],
                format="Excel/Calendar"
            )
        )

    def _digital_product_launch_scenario(self) -> ScenarioConfig:
        """数字产品发布场景 - 针对类型②数字产品开发者"""
        return ScenarioConfig(
            id="digital_product_launch",
            name="数字产品发布",
            description="针对知识付费/工具类产品的完整发布流程",
            trigger_phrases=[
                "数字产品", "知识付费", "课程发布", "电子书",
                "模板售卖", "小报童", "Gumroad", "产品上架"
            ],
            target_business_types=[BusinessType.DIGITAL_PRODUCT],
            estimated_duration="2-3小时",
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="产品定位分析",
                    type="research",
                    description="分析产品独特卖点和目标用户",
                    estimated_duration="30分钟",
                    dependencies=[],
                    output_spec=OutputSpec(
                        name="产品定位文档",
                        format="PDF/Word",
                        includes=["USP分析", "竞品对比", "用户痛点"]
                    ),
                    executor="product_positioner"
                ),
                WorkflowStep(
                    step_id=2,
                    name="定价策略",
                    type="analysis",
                    description="基于市场和成本制定定价方案",
                    estimated_duration="20分钟",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="定价方案",
                        format="Table",
                        includes=["价格档位", "价值锚点", "促销策略"]
                    ),
                    executor="pricing_strategist"
                ),
                WorkflowStep(
                    step_id=3,
                    name="销售页生成",
                    type="generation",
                    description="生成高转化销售页面文案",
                    estimated_duration="45分钟",
                    dependencies=[2],
                    output_spec=OutputSpec(
                        name="销售页文案",
                        format="Markdown/HTML",
                        includes=[" headline", "卖点列表", "客户证言", "CTA"]
                    ),
                    executor="sales_page_writer"
                ),
                WorkflowStep(
                    step_id=4,
                    name="发布渠道配置",
                    type="setup",
                    description="配置各销售渠道的发布参数",
                    estimated_duration="30分钟",
                    dependencies=[3],
                    output_spec=OutputSpec(
                        name="渠道配置清单",
                        format="Checklist",
                        includes=["平台设置", "支付配置", "物流设置"]
                    ),
                    executor="channel_configurator"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="数字产品发布套件",
                sections=["产品定位", "定价策略", "销售页文案", "渠道配置", "发布检查清单"],
                format="Multi-format"
            )
        )

    def _feedback_analysis_scenario(self) -> ScenarioConfig:
        """用户反馈分析场景 - 针对类型③AI工具开发者"""
        return ScenarioConfig(
            id="feedback_analysis",
            name="用户反馈分析",
            description="自动收集、分类、分析用户反馈，提取 actionable insights",
            trigger_phrases=[
                "用户反馈", "评价分析", "评论分析", "用户声音",
                "NPS分析", "满意度调查", "App Store评论", "GitHub Issues"
            ],
            target_business_types=[BusinessType.AI_TOOL_BUILDER],
            estimated_duration="1-2小时",
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="反馈采集",
                    type="data_collection",
                    description="从各渠道收集用户反馈数据",
                    estimated_duration="15分钟",
                    dependencies=[],
                    output_spec=OutputSpec(
                        name="原始反馈库",
                        format="JSON/CSV",
                        includes=["来源", "内容", "评分", "时间戳"]
                    ),
                    executor="feedback_collector"
                ),
                WorkflowStep(
                    step_id=2,
                    name="情感分类",
                    type="analysis",
                    description="对反馈进行情感倾向和主题分类",
                    estimated_duration="20分钟",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="分类结果",
                        format="Table",
                        includes=["情感标签", "主题类别", "优先级"]
                    ),
                    executor="sentiment_classifier"
                ),
                WorkflowStep(
                    step_id=3,
                    name="洞察提取",
                    type="generation",
                    description="提取关键洞察和改进建议",
                    estimated_duration="30分钟",
                    dependencies=[2],
                    output_spec=OutputSpec(
                        name="洞察报告",
                        format="PDF/Markdown",
                        includes=["TOP问题", "改进建议", "机会点"]
                    ),
                    executor="insight_extractor_llm"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="用户反馈分析报告",
                sections=["数据概览", "情感分布", "主题聚类", "关键洞察", "行动建议", "优先级矩阵"],
                format="PDF/Dashboard"
            )
        )

    def _consulting_proposal_scenario(self) -> ScenarioConfig:
        """咨询提案场景 - 针对类型④专业咨询师"""
        return ScenarioConfig(
            id="consulting_proposal",
            name="咨询提案撰写",
            description="快速生成专业咨询服务提案",
            trigger_phrases=[
                "咨询提案", "项目建议书", "服务报价",
                "咨询方案", "专业服务", "顾问提案"
            ],
            target_business_types=[BusinessType.CONSULTANT],
            estimated_duration="1-2小时",
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="需求理解",
                    type="research",
                    description="深入理解客户需求和项目背景",
                    estimated_duration="20分钟",
                    dependencies=[],
                    output_spec=OutputSpec(
                        name="需求分析文档",
                        format="Word",
                        includes=["客户背景", "核心诉求", "约束条件"]
                    ),
                    executor="requirements_analyzer"
                ),
                WorkflowStep(
                    step_id=2,
                    name="方案设计",
                    type="generation",
                    description="设计咨询服务方案和交付物",
                    estimated_duration="30分钟",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="服务方案",
                        format="Word/PPT",
                        includes=["方法论", "阶段规划", "交付清单"]
                    ),
                    executor="solution_designer_llm"
                ),
                WorkflowStep(
                    step_id=3,
                    name="报价生成",
                    type="calculation",
                    description="基于工作量和服务标准生成报价",
                    estimated_duration="15分钟",
                    dependencies=[2],
                    output_spec=OutputSpec(
                        name="报价单",
                        format="Excel/PDF",
                        includes=["费用明细", "付款条款", "增值服务"]
                    ),
                    executor="pricing_calculator"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="专业咨询提案",
                sections=["执行摘要", "需求理解", "解决方案", "团队介绍", "项目计划", "费用报价", "成功案例"],
                format="PPT/PDF"
            )
        )

    def _ecommerce_ops_scenario(self) -> ScenarioConfig:
        """电商运营场景 - 针对类型⑤电商运营者"""
        return ScenarioConfig(
            id="ecommerce_ops",
            name="电商运营优化",
            description="电商日常运营工作的智能辅助",
            trigger_phrases=[
                "电商运营", "店铺管理", "商品上架",
                "促销活动", "库存管理", "订单处理", "淘宝", "京东", "拼多多"
            ],
            target_business_types=[BusinessType.ECOMMERCE],
            estimated_duration="30分钟-1小时",
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="数据监控",
                    type="data_collection",
                    description="获取店铺核心运营指标",
                    estimated_duration="5分钟",
                    dependencies=[],
                    output_spec=OutputSpec(
                        name="运营日报",
                        format="Dashboard",
                        includes=["GMV", "转化率", "客单价", "访客数"]
                    ),
                    executor="ecommerce_monitor"
                ),
                WorkflowStep(
                    step_id=2,
                    name="活动策划",
                    type="generation",
                    description="基于数据和节日策划促销活动",
                    estimated_duration="15分钟",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="活动方案",
                        format="Document",
                        includes=["活动主题", "优惠规则", "推广渠道"]
                    ),
                    executor="promotion_planner_llm"
                ),
                WorkflowStep(
                    step_id=3,
                    name="商品优化",
                    type="optimization",
                    description="优化商品标题、详情页、主图",
                    estimated_duration="20分钟",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="优化建议",
                        format="Checklist",
                        includes=["标题SEO", "详情页文案", "主图建议"]
                    ),
                    executor="product_optimizer"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="电商运营日报+行动计划",
                sections=["数据概览", "异常预警", "活动建议", "商品优化", "明日待办"],
                format="Dashboard/Document"
            )
        )

    def _project_deliverable_scenario(self) -> ScenarioConfig:
        """项目交付物场景 - 针对类型⑥创意工作者"""
        return ScenarioConfig(
            id="project_deliverable",
            name="项目交付物整理",
            description="创意项目的成果整理与客户交付",
            trigger_phrases=[
                "项目交付", "作品集", "成果整理",
                "客户汇报", "创意产出", "设计交付"
            ],
            target_business_types=[BusinessType.CREATIVE_WORK],
            estimated_duration="1-2小时",
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="素材收集",
                    type="data_collection",
                    description="汇集项目所有产出素材",
                    estimated_duration="20分钟",
                    dependencies=[],
                    output_spec=OutputSpec(
                        name="素材库",
                        format="Folder",
                        includes=["设计稿", "源文件", "效果图", "说明文档"]
                    ),
                    executor="asset_collector"
                ),
                WorkflowStep(
                    step_id=2,
                    name="成果包装",
                    type="generation",
                    description="将素材包装为专业的交付形式",
                    estimated_duration="30分钟",
                    dependencies=[1],
                    output_spec=OutputSpec(
                        name="交付包",
                        format="ZIP/Presentation",
                        includes=["展示文稿", "文件清单", "使用说明"]
                    ),
                    executor="deliverable_packager"
                ),
                WorkflowStep(
                    step_id=3,
                    name="汇报准备",
                    type="writing",
                    description="准备向客户汇报的材料",
                    estimated_duration="20分钟",
                    dependencies=[2],
                    output_spec=OutputSpec(
                        name="汇报材料",
                        format="PPT/PDF",
                        includes=["项目回顾", "亮点展示", "后续建议"]
                    ),
                    executor="presentation_writer"
                )
            ],
            deliverable_template=DeliverableTemplate(
                name="项目交付完整包",
                sections=["项目概览", "成果展示", "文件清单", "使用指南", "后续支持"],
                format="Presentation/ZIP"
            )
        )

    # ==================== 核心处理逻辑 ====================

    def process(self, user_input: str, user_context: Dict[str, Any] = None) -> ScenarioResult:
        """
        处理用户输入，返回场景匹配结果

        Args:
            user_input: 用户自然语言输入
            user_context: 用户上下文信息（可选）
                - profile: 用户档案
                - conversation_history: 对话历史
                - user_id: 用户ID
                - preferred_business_type: 用户偏好的业务类型

        Returns:
            ScenarioResult: 场景匹配和处理结果
        """
        if user_context is None:
            user_context = {}

        detected_type = BusinessType.CONTENT_CREATOR  # 默认值，后续由BusinessTypeDetector替换

        if self.type_detector:
            try:
                detection_result = self.type_detector.detect(
                    input_text=user_input,
                    user_profile=user_context.get("profile"),
                    history=user_context.get("conversation_history", [])
                )
                detected_type = detection_result.business_type  # 提取BusinessType枚举值
            except Exception as e:
                print(f"[ScenarioEngineV2] BusinessTypeDetector执行失败，使用默认类型: {e}")

        candidates = []
        for scenario_id, config in self.scenarios.items():
            is_target_type = (
                detected_type in config.target_business_types or
                len(config.target_business_types) == len(BusinessType.get_all_types())
            )

            if is_target_type:
                confidence = self._calculate_match_confidence(user_input, config.trigger_phrases)

                if confidence >= config.confidence_threshold:
                    candidates.append({
                        "scenario_id": scenario_id,
                        "confidence": confidence,
                        "config": config
                    })

        candidates.sort(key=lambda x: x["confidence"], reverse=True)

        persona = None
        if self.persona_manager and user_context.get("user_id"):
            try:
                persona = self.persona_manager.get_persona(
                    user_id=user_context.get("user_id"),
                    business_type=detected_type,
                    context={"scenario_id": candidates[0]["scenario_id"] if candidates else None}
                )
            except Exception as e:
                print(f"[ScenarioEngineV2] PersonaManager执行失败: {e}")

        if not candidates:
            return ScenarioResult(
                matched=False,
                confidence=0.0,
                detected_business_type=detected_type,
                suggestion="未匹配到具体场景，是否需要我帮您梳理需求？您可以尝试：\n"
                          "- 内容创作：'帮我规划下周的内容日历'\n"
                          "- 产品发布：'我要发布一个新产品'\n"
                          "- 报告撰写：'帮我写一份月度报告'",
                candidates=[]
            )

        best_match = candidates[0]

        return ScenarioResult(
            matched=True,
            scenario_id=best_match["scenario_id"],
            scenario_config=best_match["config"],
            confidence=best_match["confidence"],
            detected_business_type=detected_type,
            persona=persona,
            workflow=[step.to_dict() for step in best_match["config"].workflow_steps],
            candidates=candidates[:3]  # 返回Top-3候选
        )

    def _calculate_match_confidence(self, user_input: str, trigger_phrases: List[str]) -> float:
        """
        计算用户输入与触发短语的匹配置信度

        算法：
        - 精确匹配（完整短语出现在输入中）：0.9
        - 部分匹配（关键词命中）：0.5-0.7 * 关键词覆盖率
        """
        user_input_lower = user_input.lower().strip()

        max_confidence = 0.0

        for phrase in trigger_phrases:
            phrase_lower = phrase.lower()

            if phrase_lower in user_input_lower:
                confidence = 0.9
            else:
                keywords = phrase_lower.split()
                match_count = sum(1 for kw in keywords if kw in user_input_lower and len(kw) > 1)
                confidence = (match_count / len(keywords)) * 0.7 if keywords else 0.0

            max_confidence = max(max_confidence, confidence)

        return max_confidence

    # ==================== 辅助方法 ====================

    def get_scenario(self, scenario_id: str) -> Optional[ScenarioConfig]:
        """根据ID获取场景配置"""
        return self.scenarios.get(scenario_id)

    def list_scenarios(self, business_type: BusinessType = None) -> List[Dict[str, Any]]:
        """
        列出所有场景（可按业务类型过滤）

        Args:
            business_type: 可选的业务类型过滤器

        Returns:
            场景列表（摘要信息）
        """
        scenarios_list = []

        for scenario_id, config in self.scenarios.items():
            if business_type is None or business_type in config.target_business_types:
                scenarios_list.append({
                    "id": config.id,
                    "name": config.name,
                    "description": config.description,
                    "estimated_duration": config.estimated_duration,
                    "target_business_types": [bt.value for bt in config.target_business_types],
                    "steps_count": len(config.workflow_steps)
                })

        return scenarios_list

    def get_statistics(self) -> Dict[str, Any]:
        """获取场景引擎统计信息"""
        type_distribution = {}
        for config in self.scenarios.values():
            for bt in config.target_business_types:
                type_key = bt.value
                if type_key not in type_distribution:
                    type_distribution[type_key] = 0
                type_distribution[type_key] += 1

        return {
            "total_scenarios": len(self.scenarios),
            "business_types_supported": list(type_distribution.keys()),
            "scenarios_per_type": type_distribution,
            "version": "2.1.0",
            "loaded_at": datetime.now().isoformat()
        }


# 单例模式 - 全局实例
_scenario_engine_v2_instance = None


def get_scenario_engine_v2() -> ScenarioEngineV2:
    """获取ScenarioEngineV2单例实例"""
    global _scenario_engine_v2_instance
    if _scenario_engine_v2_instance is None:
        _scenario_engine_v2_instance = ScenarioEngineV2()
    return _scenario_engine_v2_instance


if __name__ == "__main__":
    engine = ScenarioEngineV2()

    print("=" * 60)
    print("OPC-Agents 场景引擎 V2.1")
    print("=" * 60)

    stats = engine.get_statistics()
    print(f"\n📊 引擎统计:")
    print(f"   总场景数: {stats['total_scenarios']}")
    print(f"   支持的业务类型: {', '.join(stats['business_types_supported'])}")
    print(f"   版本: {stats['version']}")

    print(f"\n📋 所有场景列表:")
    for scenario in engine.list_scenarios():
        types_str = ', '.join(scenario['target_business_types'])
        print(f"   [{scenario['id']}] {scenario['name']}")
        print(f"      描述: {scenario['description'][:50]}...")
        print(f"      目标类型: {types_str}")
        print(f"      步骤数: {scenario['steps_count']}")
        print()

    test_inputs = [
        ("帮我规划下周的内容日历", {"user_id": "test_user_001"}),
        ("我要发布一个新的AI工具", {"user_id": "test_user_002"}),
        ("帮我写一份月度工作报告", {"user_id": "test_user_003"}),
        ("明天下午组织个产品评审会", {"user_id": "test_user_004"})
    ]

    print("\n" + "=" * 60)
    print("🧪 测试用例")
    print("=" * 60)

    for i, (input_text, context) in enumerate(test_inputs, 1):
        print(f"\n测试{i}: \"{input_text}\"")
        result = engine.process(input_text, context)
        print(f"匹配结果: {'✅ 成功' if result.matched else '❌ 未匹配'}")
        if result.matched:
            print(f"场景ID: {result.scenario_id}")
            print(f"置信度: {result.confidence:.2f}")
            print(f"检测到的业务类型: {result.detected_business_type.value}")
            print(f"工作流步骤数: {len(result.workflow)}")
        print("-" * 40)
