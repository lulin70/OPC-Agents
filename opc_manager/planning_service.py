"""PlanningService - 任务规划服务

[P2-15] Step 3: 从 StrategistBrain 抽出的任务规划职责。
负责将 Intent 转换为 ExecutionPlan，支持 LLM 规划 + 规则降级。
"""

from typing import Any, List, Optional
import json
import logging
import uuid

from opc_manager.intent_types import IntentType, INTENT_STEP_MAP
from opc_manager.utils import (
    extract_json_from_llm,
    sanitize_for_llm,
    call_llm_service,
)
from opc_manager.strategist_models import (
    Intent,
    Step,
    ExecutionPlan,
)

logger = logging.getLogger(__name__)

ESTIMATED_TIME_PER_STEP = 30


class PlanningService:
    """任务规划服务 — 将 Intent 转换为 ExecutionPlan。

    支持双路径：LLM 规划（基于 SkillRegistry 实际技能）+ 规则降级（INTENT_STEP_MAP）。
    """

    def __init__(
        self, llm_service: Optional[Any] = None, skill_registry: Optional[Any] = None
    ) -> None:
        self.llm_service = llm_service
        self.skill_registry = skill_registry

    def plan(self, intent: Intent) -> ExecutionPlan:
        logger.info("开始制定执行计划: %s...", intent.goal[:50])

        if self.llm_service:
            try:
                plan = self._plan_with_llm(intent)
                if plan and plan.steps:
                    logger.info("LLM规划完成: %s 个步骤", len(plan.steps))
                    return plan
                logger.info("LLM规划失败，降级到规则规划")
            except Exception as e:
                logger.warning("LLM规划异常，降级到规则规划: %s", e)

        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        steps = self._generate_steps(intent)
        estimated_time = len(steps) * ESTIMATED_TIME_PER_STEP

        plan = ExecutionPlan(
            plan_id=plan_id, intent=intent, steps=steps, estimated_time=estimated_time
        )

        logger.info("执行计划制定完成: %s 个步骤", len(steps))
        return plan

    def _get_valid_skill_ids(self) -> set:
        """从 SkillRegistry 动态获取所有有效的技能 ID。

        若注入了 skill_registry，则返回注册表中已注册的技能 ID；
        否则降级到基础技能集，保持向后兼容。

        Returns:
            set: 有效技能 ID 集合，始终包含系统技能 intent_analysis / output_result
        """
        # 系统技能始终可用，不在 SkillRegistry 中注册
        system_skills = {"intent_analysis", "output_result"}

        if self.skill_registry is None:
            # 向后兼容：未注入注册表时使用基础技能集
            base_skills = {
                "search",
                "analysis",
                "content_generation",
                "execute_operation",
                "send_notification",
            }
            return base_skills | system_skills

        try:
            all_skills = self.skill_registry.list_all_skills()
            registry_ids = {skill.skill_id for skill in all_skills}
            return registry_ids | system_skills
        except Exception as e:
            logger.warning("从 SkillRegistry 获取技能列表失败，降级到基础技能集: %s", e)
            base_skills = {
                "search",
                "analysis",
                "content_generation",
                "execute_operation",
                "send_notification",
            }
            return base_skills | system_skills

    def _build_planning_prompt(
        self, safe_goal: str, intent_type_value: str, safe_sub_goals: str
    ) -> str:
        """构建包含动态技能列表的 LLM 规划提示词。

        从 SkillRegistry 获取已启用的技能，生成 "skill_id(技能名)" 形式的
        描述列表注入到提示词中，提升 LLM 生成有效 skill_id 的准确率。

        Args:
            safe_goal: 已脱敏的任务目标
            intent_type_value: 意图类型字符串
            safe_sub_goals: 已脱敏的子目标

        Returns:
            str: 完整的 LLM 规划提示词
        """
        if self.skill_registry is not None:
            try:
                all_skills = self.skill_registry.list_all_skills()
                skill_descriptions = [
                    f"{skill.skill_id}({skill.name})"
                    for skill in all_skills
                    if skill.enabled
                ]
                if not skill_descriptions:
                    # 注册表为空时降级到基础技能
                    skill_descriptions = [
                        "search(搜索)",
                        "analysis(分析)",
                        "content_generation(内容创作)",
                        "execute_operation(执行操作)",
                        "send_notification(发送通知)",
                    ]
            except Exception as e:
                logger.warning("构建规划提示词时获取技能列表失败，使用基础技能: %s", e)
                skill_descriptions = [
                    "search(搜索)",
                    "analysis(分析)",
                    "content_generation(内容创作)",
                    "execute_operation(执行操作)",
                    "send_notification(发送通知)",
                ]
        else:
            # 未注入注册表，使用基础技能集（向后兼容）
            skill_descriptions = [
                "search(搜索)",
                "analysis(分析)",
                "content_generation(内容创作)",
                "execute_operation(执行操作)",
                "send_notification(发送通知)",
            ]

        skills_text = ", ".join(skill_descriptions)

        return f"""为以下任务制定执行计划，返回JSON格式。

任务目标: {safe_goal}
意图类型: {intent_type_value}
子目标: {safe_sub_goals}

可用技能: {skills_text}, output_result(输出结果)

请返回JSON格式:
{{
  "steps": [
    {{"skill_id": "技能名", "description": "步骤描述", "parameters": {{"key": "value"}}}},
    ...
  ]
}}

规则:
1. 第一步通常是搜索或分析
2. 后续步骤基于前一步结果
3. 最后一步是output_result
4. 复合意图需要多步骤
5. skill_id必须从上述可用技能列表中选择"""

    def _plan_with_llm(self, intent: Intent) -> Optional[ExecutionPlan]:
        sub_goals = [si.goal for si in intent.sub_intents] if intent.sub_intents else []

        safe_goal = sanitize_for_llm(intent.goal, 500)
        safe_sub_goals = (
            sanitize_for_llm(json.dumps(sub_goals, ensure_ascii=False), 500)
            if sub_goals
            else "无"
        )

        prompt = self._build_planning_prompt(
            safe_goal, intent.type.value, safe_sub_goals
        )

        llm_response = call_llm_service(self.llm_service, prompt)
        if not llm_response:
            return None

        try:
            data = extract_json_from_llm(llm_response)
            if not data:
                return None

            steps_data = data.get("steps", [])
            if not steps_data:
                return None

            valid_skill_ids = self._get_valid_skill_ids()

            steps = []
            for i, sd in enumerate(steps_data):
                skill_id = sd.get("skill_id", "output_result")
                if skill_id not in valid_skill_ids:
                    logger.warning(
                        "LLM生成的技能ID '%s' 不在注册表中，降级为 output_result",
                        skill_id,
                    )
                    skill_id = "output_result"
                steps.append(
                    Step(
                        id=f"step_{i+1}",
                        skill_id=skill_id,
                        description=sd.get("description", f"执行步骤{i+1}"),
                        parameters=sd.get("parameters", {"goal": intent.goal}),
                        dependencies=[f"step_{i}"] if i > 0 else [],
                    )
                )

            plan_id = f"plan_{uuid.uuid4().hex[:8]}"
            return ExecutionPlan(
                plan_id=plan_id,
                intent=intent,
                steps=steps,
                estimated_time=len(steps) * ESTIMATED_TIME_PER_STEP,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("LLM规划结果解析失败: %s", e)
            return None

    def _generate_steps(self, intent: Intent) -> List[Step]:
        steps = []
        step_id = 1

        steps.append(
            Step(
                id=f"step_{step_id}",
                skill_id="intent_analysis",
                description="分析用户需求和约束条件",
                parameters={
                    "goal": intent.goal,
                    "constraints": [c.type.value for c in (intent.constraints or [])],
                },
            )
        )
        step_id += 1

        if intent.type == IntentType.COMBINED and intent.sub_intents:
            prev_step_id = "step_1"
            for sub_intent in intent.sub_intents:
                sub_steps = self._generate_skill_steps(
                    sub_intent, step_id, prev_step_id
                )
                steps.extend(sub_steps)
                if sub_steps:
                    prev_step_id = sub_steps[-1].id
                    step_id += len(sub_steps)
        else:
            skill_steps = self._generate_skill_steps(intent, step_id, "step_1")
            steps.extend(skill_steps)
            if skill_steps:
                step_id += len(skill_steps)

        steps.append(
            Step(
                id=f"step_{step_id}",
                skill_id="output_result",
                description="输出最终结果",
                parameters={"format": "markdown"},
                dependencies=[steps[-1].id] if len(steps) > 1 else [],
            )
        )

        return steps

    def _generate_skill_steps(
        self, intent: Intent, start_id: int, dep_id: str
    ) -> List[Step]:
        steps: List[Step] = []
        step_id = start_id

        if intent.type == IntentType.COMBINED:
            if intent.sub_intents:
                for sub in intent.sub_intents[:3]:
                    sub_steps = self._generate_skill_steps(
                        sub, step_id, dep_id if not steps else steps[-1].id
                    )
                    steps.extend(sub_steps)
                    step_id += len(sub_steps)
            else:
                steps.append(
                    Step(
                        id=f"step_{step_id}",
                        skill_id="search",
                        description="搜索相关信息和数据",
                        parameters={"query": intent.goal, "max_results": 10},
                        dependencies=[dep_id],
                    )
                )
                step_id += 1
                steps.append(
                    Step(
                        id=f"step_{step_id}",
                        skill_id="analysis",
                        description="进行深度分析",
                        parameters={"goal": intent.goal},
                        dependencies=[steps[-1].id],
                    )
                )
                step_id += 1
                steps.append(
                    Step(
                        id=f"step_{step_id}",
                        skill_id="content_generation",
                        description="生成内容",
                        parameters={"goal": intent.goal, "format": "markdown"},
                        dependencies=[steps[-1].id],
                    )
                )
        elif intent.type == IntentType.ANALYSIS:
            steps.append(
                Step(
                    id=f"step_{step_id}",
                    skill_id="search",
                    description="搜索相关信息和数据",
                    parameters={"query": intent.goal, "max_results": 10},
                    dependencies=[dep_id],
                )
            )
            step_id += 1
            steps.append(
                Step(
                    id=f"step_{step_id}",
                    skill_id="analysis",
                    description="进行深度分析",
                    parameters={"goal": intent.goal},
                    dependencies=[steps[-1].id],
                )
            )
        elif intent.type == IntentType.SEARCH:
            steps.append(
                Step(
                    id=f"step_{step_id}",
                    skill_id="search",
                    description="执行搜索",
                    parameters={"query": intent.goal, "max_results": 15},
                    dependencies=[dep_id],
                )
            )
        else:
            mapping = INTENT_STEP_MAP.get(intent.type)
            if mapping:
                skill_id, desc = mapping
                params = {"goal": intent.goal}
                if intent.type == IntentType.EXTENDED_SKILL and intent.context:
                    params["skill_id"] = intent.context.get("skill_id", "")
                    params["source"] = intent.context.get("source", "")
                steps.append(
                    Step(
                        id=f"step_{step_id}",
                        skill_id=skill_id,
                        description=desc,
                        parameters=params,
                        dependencies=[dep_id],
                    )
                )

        return steps
