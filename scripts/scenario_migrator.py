"""
场景到技能迁移模块

将现有的9个场景转换为可注册的技能格式，实现场景与技能的无缝衔接。

场景列表：
1. launch_product - 新产品发布
2. write_report - 报告撰写
3. organize_meeting - 会议组织
4. content_calendar - 内容日历规划
5. digital_product_launch - 数字产品发布
6. feedback_analysis - 用户反馈分析
7. consulting_proposal - 咨询方案策划
8. ecommerce_ops - 电商运营分析
9. project_deliverable - 项目交付管理
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
import logging

from opc_manager.skill_registry import (
    SkillRegistry,
    Skill,
    SkillCategory,
    SkillInput,
    SkillOutput,
)
from opc_manager.scenario_engine_v2 import ScenarioEngineV2, ScenarioConfig

logger = logging.getLogger(__name__)


@dataclass
class ScenarioSkillMapping:
    """场景到技能的映射关系"""

    scenario_id: str
    skill_id: str
    skill_name: str
    category: SkillCategory
    inputs: List[SkillInput]
    outputs: List[SkillOutput]
    description: str


class ScenarioToSkillMigrator:
    """场景到技能迁移器"""

    # 预定义的场景到技能映射
    MAPPINGS: List[ScenarioSkillMapping] = [
        ScenarioSkillMapping(
            scenario_id="launch_product",
            skill_id="launch_product",
            skill_name="新产品发布",
            category=SkillCategory.OPERATION,
            inputs=[
                SkillInput(name="product_name", type="str", description="产品名称"),
                SkillInput(name="target_market", type="str", description="目标市场"),
                SkillInput(
                    name="launch_date", type="str", description="发布日期（可选）"
                ),
            ],
            outputs=[
                SkillOutput(
                    name="market_research", type="str", description="市场调研报告"
                ),
                SkillOutput(name="product_doc", type="str", description="产品需求文档"),
                SkillOutput(
                    name="marketing_plan", type="str", description="营销推广方案"
                ),
                SkillOutput(name="full_plan", type="str", description="完整发布方案"),
            ],
            description="完整的新产品发布流程，从市场调研到最终发布",
        ),
        ScenarioSkillMapping(
            scenario_id="write_report",
            skill_id="write_report",
            skill_name="报告撰写",
            category=SkillCategory.CREATION,
            inputs=[
                SkillInput(name="report_type", type="str", description="报告类型"),
                SkillInput(name="topic", type="str", description="报告主题"),
                SkillInput(
                    name="data_sources", type="list", description="数据源列表（可选）"
                ),
            ],
            outputs=[
                SkillOutput(name="data_package", type="str", description="数据资料包"),
                SkillOutput(name="analysis_result", type="str", description="分析结果"),
                SkillOutput(name="final_report", type="str", description="完整报告"),
            ],
            description="自动收集数据、分析并生成专业报告",
        ),
        ScenarioSkillMapping(
            scenario_id="organize_meeting",
            skill_id="organize_meeting",
            skill_name="会议组织",
            category=SkillCategory.OPERATION,
            inputs=[
                SkillInput(name="topic", type="str", description="会议主题"),
                SkillInput(
                    name="participants", type="list", description="参会人员列表"
                ),
                SkillInput(
                    name="preferred_time", type="str", description="期望时间（可选）"
                ),
            ],
            outputs=[
                SkillOutput(name="time安排", type="str", description="会议时间安排"),
                SkillOutput(name="invitation", type="str", description="会议邀请"),
                SkillOutput(name="materials", type="str", description="会议材料包"),
            ],
            description="自动协调时间、发送邀请、准备会议材料",
        ),
        ScenarioSkillMapping(
            scenario_id="content_calendar",
            skill_id="content_calendar",
            skill_name="内容日历规划",
            category=SkillCategory.CREATION,
            inputs=[
                SkillInput(name="platforms", type="list", description="发布平台列表"),
                SkillInput(name="topics", type="list", description="感兴趣的话题"),
                SkillInput(name="period", type="str", description="规划周期"),
            ],
            outputs=[
                SkillOutput(
                    name="hotspot_analysis", type="str", description="热点分析"
                ),
                SkillOutput(name="content_plan", type="str", description="内容规划表"),
                SkillOutput(name="schedule", type="str", description="发布时间表"),
            ],
            description="基于热点和粉丝画像，智能规划多平台内容发布计划",
        ),
        ScenarioSkillMapping(
            scenario_id="digital_product_launch",
            skill_id="digital_product_launch",
            skill_name="数字产品发布",
            category=SkillCategory.OPERATION,
            inputs=[
                SkillInput(name="product_type", type="str", description="数字产品类型"),
                SkillInput(name="target_users", type="str", description="目标用户"),
                SkillInput(name="launch_channel", type="str", description="发布渠道"),
            ],
            outputs=[
                SkillOutput(name="launch_strategy", type="str", description="发布策略"),
                SkillOutput(name="landing_page", type="str", description="落地页文案"),
                SkillOutput(name="promotion_plan", type="str", description="推广方案"),
            ],
            description="针对数字产品（SaaS/工具/小程序）的发布流程",
        ),
        ScenarioSkillMapping(
            scenario_id="feedback_analysis",
            skill_id="feedback_analysis",
            skill_name="用户反馈分析",
            category=SkillCategory.ANALYSIS,
            inputs=[
                SkillInput(name="feedback_source", type="str", description="反馈来源"),
                SkillInput(name="analysis_type", type="str", description="分析类型"),
                SkillInput(name="time_range", type="str", description="时间范围"),
            ],
            outputs=[
                SkillOutput(
                    name="sentiment_report", type="str", description="情感分析报告"
                ),
                SkillOutput(name="issue_summary", type="str", description="问题汇总"),
                SkillOutput(
                    name="improvement_suggestions", type="str", description="改进建议"
                ),
            ],
            description="分析用户反馈，提取关键洞察和改进建议",
        ),
        ScenarioSkillMapping(
            scenario_id="consulting_proposal",
            skill_id="consulting_proposal",
            skill_name="咨询方案策划",
            category=SkillCategory.OPERATION,
            inputs=[
                SkillInput(name="client_industry", type="str", description="客户行业"),
                SkillInput(
                    name="problem_description", type="str", description="问题描述"
                ),
                SkillInput(name="budget", type="str", description="预算范围（可选）"),
            ],
            outputs=[
                SkillOutput(name="needs_analysis", type="str", description="需求分析"),
                SkillOutput(name="proposal", type="str", description="咨询方案"),
                SkillOutput(name="cost_estimate", type="str", description="费用估算"),
            ],
            description="为客户提供专业咨询方案和建议",
        ),
        ScenarioSkillMapping(
            scenario_id="ecommerce_ops",
            skill_id="ecommerce_ops",
            skill_name="电商运营分析",
            category=SkillCategory.ANALYSIS,
            inputs=[
                SkillInput(name="platform", type="str", description="电商平台"),
                SkillInput(
                    name="analysis_dimension", type="str", description="分析维度"
                ),
                SkillInput(name="time_period", type="str", description="时间周期"),
            ],
            outputs=[
                SkillOutput(
                    name="sales_analysis", type="str", description="销售数据分析"
                ),
                SkillOutput(
                    name="inventory_report", type="str", description="库存报告"
                ),
                SkillOutput(
                    name="optimization_suggestions", type="str", description="优化建议"
                ),
            ],
            description="分析电商运营数据，提供优化建议",
        ),
        ScenarioSkillMapping(
            scenario_id="project_deliverable",
            skill_id="project_deliverable",
            skill_name="项目交付管理",
            category=SkillCategory.OPERATION,
            inputs=[
                SkillInput(name="project_name", type="str", description="项目名称"),
                SkillInput(name="deadline", type="str", description="截止日期"),
                SkillInput(name="requirements", type="list", description="需求列表"),
            ],
            outputs=[
                SkillOutput(name="task_plan", type="str", description="任务分解计划"),
                SkillOutput(name="schedule", type="str", description="项目进度表"),
                SkillOutput(name="deliverables", type="str", description="交付物清单"),
            ],
            description="管理项目交付流程，确保按时完成",
        ),
    ]

    def __init__(self, skill_registry: Optional[SkillRegistry] = None):
        """初始化迁移器"""
        self.scenario_engine = ScenarioEngineV2()
        self.skill_registry = skill_registry or SkillRegistry()

    def _create_skill_executor(self, scenario_id: str) -> Callable:
        """创建技能执行器"""

        async def execute(**kwargs) -> Dict[str, Any]:
            scenario_config = self.scenario_engine._load_scenarios().get(scenario_id)
            if not scenario_config:
                return {"success": False, "error": f"场景 {scenario_id} 不存在"}

            return {
                "success": True,
                "data": {
                    "scenario_id": scenario_id,
                    "workflow_steps": [
                        step.to_dict() for step in scenario_config.workflow_steps
                    ],
                    "deliverable": scenario_config.deliverable_template.name,
                    "estimated_duration": scenario_config.estimated_duration,
                    "input_params": kwargs,
                },
            }

        return execute

    def migrate_all(self) -> Dict[str, bool]:
        """迁移所有场景为技能"""
        results = {}

        for mapping in self.MAPPINGS:
            try:
                skill = Skill(
                    skill_id=mapping.skill_id,
                    name=mapping.skill_name,
                    description=mapping.description,
                    category=mapping.category,
                    inputs=mapping.inputs,
                    outputs=mapping.outputs,
                    execute=self._create_skill_executor(mapping.scenario_id),
                )

                success = self.skill_registry.register_skill(skill)
                results[mapping.skill_id] = success

                if success:
                    logger.info(
                        "场景 %s 已成功迁移为技能 %s",
                        mapping.scenario_id,
                        mapping.skill_id,
                    )
                else:
                    logger.warning("场景 %s 迁移失败", mapping.scenario_id)

            except Exception as e:
                logger.error("迁移场景 %s 时出错: %s", mapping.scenario_id, str(e))
                results[mapping.skill_id] = False

        return results

    def migrate_by_id(self, scenario_id: str) -> bool:
        """根据场景ID迁移单个场景"""
        mapping = next((m for m in self.MAPPINGS if m.scenario_id == scenario_id), None)
        if not mapping:
            logger.error("未找到场景 %s 的映射", scenario_id)
            return False

        try:
            skill = Skill(
                skill_id=mapping.skill_id,
                name=mapping.skill_name,
                description=mapping.description,
                category=mapping.category,
                inputs=mapping.inputs,
                outputs=mapping.outputs,
                execute=self._create_skill_executor(mapping.scenario_id),
            )

            success = self.skill_registry.register_skill(skill)
            if success:
                logger.info("场景 %s 已成功迁移为技能", scenario_id)
            return success
        except Exception as e:
            logger.error("迁移场景 %s 时出错: %s", scenario_id, str(e))
            return False

    def get_migration_status(self) -> Dict[str, Any]:
        """获取迁移状态"""
        registered_skills = self.skill_registry.list_all_skills()
        scenario_skills = [
            s
            for s in registered_skills
            if s.skill_id in [m.skill_id for m in self.MAPPINGS]
        ]

        return {
            "total_scenarios": len(self.MAPPINGS),
            "migrated_skills": len(scenario_skills),
            "migrated_ids": [s.skill_id for s in scenario_skills],
            "not_migrated": [
                m.skill_id
                for m in self.MAPPINGS
                if m.skill_id not in [s.skill_id for s in scenario_skills]
            ],
        }


# 全局技能注册表实例
_global_skill_registry = SkillRegistry()

# 全局迁移状态标记
_migration_completed = False


def migrate_scenarios_to_skills(force: bool = False) -> Dict[str, bool]:
    global _migration_completed
    if _migration_completed and not force:
        return {}
    _migration_completed = True
    migrator = ScenarioToSkillMigrator(skill_registry=_global_skill_registry)
    return migrator.migrate_all()


def get_migration_status() -> Dict[str, Any]:
    migrator = ScenarioToSkillMigrator(skill_registry=_global_skill_registry)
    return migrator.get_migration_status()


def get_global_skill_registry() -> SkillRegistry:
    return _global_skill_registry
