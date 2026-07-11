"""
Task-Type Executors Mixin for Task Engine v3.5

Extracted from TaskEngineV3 to reduce the God Class size.
Contains the per-task-type execution methods:
- _execute_info_collection: Path A — real web search + structured research report
- _execute_content_generation: Path B — search reference + generate specific document
- _execute_data_analysis: Path C — SWOT framework + search data + action recommendations
- _execute_scenario_based: Path D — multi-step workflow based on ScenarioEngineV2
- _exec_step_with_data: dispatch a single workflow step to a generation strategy
- _execute_business_operation: Path for business operations via SkillRegistry
- _execute_general_chat: Path E — chat/greeting/help fallback path
- _execute_fallback: scenario execution degradation path (falls back to info collection)

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
TaskEngineV3 inherits from this mixin, so all external callers see no change.
Cross-mixin calls (e.g. self._search, self._gen_real_report) are resolved at
runtime via the composed TaskEngineV3 instance.
"""

import time
import logging
from typing import TYPE_CHECKING, Optional, List, Dict, Tuple, Any

from opc_manager.utils import SECONDS_PER_DAY
from opc_manager.skill_registry import SkillRegistry
from opc_manager.task_types import TaskType, TaskResult, InputValidator

if TYPE_CHECKING:
    # Lazy import to avoid circular dependency; only needed for type checking.
    from opc_manager.scenario_engine_v2 import ScenarioEngineV2

logger = logging.getLogger(__name__)

# Timeout constants (seconds)
_SKILL_EXEC_TIMEOUT = 120

# Search result count constants
SEARCH_MAX_RESULTS_INFO = 8
SEARCH_MAX_RESULTS_CONTENT = 5
SEARCH_MAX_RESULTS_ANALYSIS = 5
SEARCH_MAX_RESULTS_STEP = 5
SEARCH_MAX_RESULTS_STEP_ANALYSIS = 3


class TaskEngineExecutorsMixin:
    """Mixin class containing per-task-type executor methods for TaskEngineV3.

    Each ``_execute_*`` method corresponds to one TaskType and produces a
    fully-populated TaskResult. Cross-mixin dependencies resolved at runtime:
    - self._search / self._extract_search_query (TaskEngineSearchMixin)
    - self._gen_real_report / _gen_real_plan / _gen_real_content /
      _gen_writing_for_step / _try_llm_generate (ContentGenerationMixin)
    - self.scenario_engine (lazy-initialized backend)
    """

    # Type declarations for cross-mixin attributes/methods (provided by the
    # TaskEngineV3 facade at runtime). Declared under TYPE_CHECKING so they
    # exist only for static analysis, never at runtime.
    if TYPE_CHECKING:
        scenario_engine: "ScenarioEngineV2"

        def _search(
            self, query: str, max_results: int = 8
        ) -> Tuple[List[Dict], List[Dict]]: ...

        def _extract_search_query(self, user_input: str) -> str: ...

        def _gen_real_report(
            self,
            query: str,
            context: List[str],
            search_results: List[Dict],
            business_type: Optional[str] = None,
            is_follow_up: bool = False,
            llm_query: Optional[str] = None,
        ) -> str: ...

        def _gen_real_plan(
            self,
            query: str,
            context: List[str],
            search_results: List[Dict],
            business_type: Optional[str] = None,
            is_follow_up: bool = False,
            llm_query: Optional[str] = None,
        ) -> str: ...

        def _gen_real_content(
            self,
            query: str,
            context: List[str],
            search_results: List[Dict],
            business_type: Optional[str] = None,
            is_follow_up: bool = False,
            llm_query: Optional[str] = None,
        ) -> str: ...

        def _try_llm_generate(
            self,
            query: str,
            search_results: List[Dict],
            doc_type: str = "report",
            business_type: Optional[str] = None,
            is_follow_up: bool = False,
            title: Optional[str] = None,
        ) -> Optional[str]: ...

        def _gen_writing_for_step(self, desc: str, query: str) -> str: ...

    def _execute_info_collection(
        self,
        search_query: str,
        llm_query: Optional[str] = None,
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
    ) -> TaskResult:
        """Path A: Information collection — Real web search + structured research report

        Typical user input: "收集2024年AI Agent框架最新信息"

        Output format:
        #  「Query」 Research Report
        - Search result summaries (8 items, each with title/summary/link)
        - Core points extraction (automatically extracted from titles)
        - Next step action suggestions (read/verify/apply/deep analysis)

        Degradation handling:
        When search returns no results, output a "insufficient information" page,
        including possible cause analysis and alternative suggestions (not a blank page).
        """
        if llm_query is None:
            llm_query = search_query
        results, sources = self._search(
            self._extract_search_query(search_query),
            max_results=SEARCH_MAX_RESULTS_INFO,
        )

        if not results:
            content = (
                f"#  「{search_query}」— 未找到足够信息\n\n"
                f"> 搜索时间: {time.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"## 说明\n\n"
                f"针对「**{search_query}**」的搜索未返回足够的相关结果。\n\n"
                f"**可能的原因：**\n"
                f"1. 关键词过于具体或小众，建议拆分为多个更通用的查询\n"
                f"2. 该主题在公开网络上信息较少，可能需要专业数据库或行业报告\n"
                f"3. 搜索引擎对该领域的中文索引不够完善\n\n"
                f"**建议下一步：**\n"
                f'- 尝试用英文关键词重新搜索（如 "{self._extract_search_query(search_query)}" 的英文翻译）\n'
                f"- 告诉我更多背景信息，我可以从其他角度帮你查找\n"
                f"- 如果这是特定行业的专业问题，建议查阅该行业的权威报告或咨询专业人士\n\n"
                "---\n"
                " **Note**: No external data was retrieved for this query. "
                "The following content is generated from general knowledge "
                "and may not reflect the latest information.\n"
            )
            return TaskResult(
                success=True, content=content, task_type=TaskType.INFO_COLLECTION
            )

        lines = []
        lines.append(f"#  「{search_query}」研究报告\n")
        lines.append(
            f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M')} | 信息来源: {len(results)} 条\n"
        )
        lines.append("---\n")

        lines.append("## 搜索结果摘要\n")
        for i, r in enumerate(results[:SEARCH_MAX_RESULTS_INFO], 1):
            title = r.get("title", "无标题")
            body = r.get("body", "无摘要") or r.get("snippet", "无摘要")
            href = InputValidator.sanitize_url(r.get("href", ""))
            lines.append(f"### {i}. {title}\n")
            lines.append(f"{body[:400]}{'...' if len(body) > 400 else ''}\n")
            if href:
                lines.append(f" [{title}]({href})\n")
            lines.append("")

        lines.append("---\n")

        key_topics = [r.get("title", "") for r in results[:5]]
        lines.append("## 核心要点提炼\n")
        lines.append(
            f"基于以上 {min(len(results), SEARCH_MAX_RESULTS_INFO)} 条搜索结果，提炼出以下关键信息：\n\n"
        )
        for i, topic in enumerate(key_topics, 1):
            lines.append(f"**{i}. {topic}**\n")
        lines.append("\n")

        lines.append("## 下一步行动建议\n")
        lines.append(
            f"根据以上关于「{search_query}」的信息，建议：\n\n"
            f"1. **深入阅读**: 点击上方来源链接，获取完整信息和数据支撑\n"
            f"2. **交叉验证**: 对比多个来源的信息，识别共识和分歧点\n"
            f"3. **结合实际**: 将这些信息与你当前的具体情况对照，找出可操作的切入点\n"
            f"4. **如需进一步分析**: 告诉我你最关注的方向，我可以帮你做更深度的整理\n"
        )

        content = "".join(lines)
        return TaskResult(
            success=True,
            content=content,
            task_type=TaskType.INFO_COLLECTION,
            sources=sources,
            deliverable_format="Markdown",
        )

    def _execute_content_generation(
        self,
        search_query: str,
        llm_query: Optional[str] = None,
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
    ) -> TaskResult:
        """Path B: Content generation — Search reference materials first, then generate specific document

        Typical user input: "帮我写一份Q2营销方案"

        Sub-type routing (based on keyword detection):
        - Contains "报告/总结/分析" → _gen_real_report() — Report format
        - Contains "方案/计划/策划/提案" → _gen_real_plan() — Plan format
        - Other → _gen_real_content() — General format

        Search enhancement strategy:
        Append keywords like " 方案 案例 最佳实践 模板" to the original query,
        improving search result relevance to the "generate document" objective.
        """
        if llm_query is None:
            llm_query = search_query
        results, sources = self._search(
            self._extract_search_query(search_query) + " 方案 案例 最佳实践 模板",
            max_results=SEARCH_MAX_RESULTS_CONTENT,
        )

        context_lines = []
        if results:
            context_lines.append("> 参考资料（来自网络搜索）：\n")
            for i, r in enumerate(results[:3], 1):
                context_lines.append(
                    f"{i}. **{r.get('title', '')}**: {r.get('body', '')[:200]}\n"
                )
            context_lines.append("\n---\n\n")

        is_report = any(kw in search_query for kw in ["报告", "report", "总结", "分析"])
        is_plan = any(kw in search_query for kw in ["方案", "plan", "策划", "策略"])
        is_proposal = any(kw in search_query for kw in ["提案", "proposal", "建议书"])

        if is_report:
            content = self._gen_real_report(
                search_query,
                context_lines,
                results,
                business_type,
                is_follow_up=is_follow_up,
                llm_query=llm_query,
            )
        elif is_plan or is_proposal:
            content = self._gen_real_plan(
                search_query,
                context_lines,
                results,
                business_type,
                is_follow_up=is_follow_up,
                llm_query=llm_query,
            )
        else:
            content = self._gen_real_content(
                search_query,
                context_lines,
                results,
                business_type,
                is_follow_up=is_follow_up,
                llm_query=llm_query,
            )

        if not results:
            disclaimer = (
                "\n\n---\n"
                " **Note**: No external data was retrieved for this query. "
                "The following content is generated from general knowledge "
                "and may not reflect the latest information.\n"
            )
            content += disclaimer

        return TaskResult(
            success=True,
            content=content,
            task_type=TaskType.CONTENT_GENERATION,
            sources=sources,
            deliverable_format="Markdown",
        )

    def _execute_data_analysis(
        self,
        search_query: str,
        llm_query: Optional[str] = None,
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
    ) -> TaskResult:
        """Path C: Data analysis — SWOT framework + search data + action recommendations

        Typical user input: "分析一下我的业务现状"

        Output features:
        - SWOT four-quadrant analysis (3 items each for strengths/weaknesses/opportunities/threats)
        - Opportunities section integrates market info from first search result
        - Conclusions section provides overall strategic direction
        - Action list graded by P0-P3, with expected benefits and time investment estimates
        """
        if llm_query is None:
            llm_query = search_query
        results, sources = self._search(
            self._extract_search_query(search_query) + " 数据 报告 趋势 对比",
            max_results=SEARCH_MAX_RESULTS_ANALYSIS,
        )

        lines = []
        llm_content = self._try_llm_generate(
            llm_query, results, "analysis", business_type, title=search_query
        )
        if llm_content:
            lines.append(llm_content)
            return TaskResult(
                success=True,
                content="".join(lines),
                task_type=TaskType.DATA_ANALYSIS,
                sources=sources,
                deliverable_format="Markdown",
            )

        lines.append(f"#  「{search_query}」深度分析\n")
        lines.append(f"> 分析时间: {time.strftime('%Y-%m-%d %H:%M')}\n\n")

        if results:
            lines.append("> 参考资料:\n")
            for i, r in enumerate(results[:3], 1):
                lines.append(f"{i}. {r.get('title', '')}: {r.get('body', '')[:150]}\n")
            lines.append("\n---\n\n")

        topic = (
            search_query.replace("帮我分析", "")
            .replace("分析一下", "")
            .replace("看看", "")
            .replace("怎么样", "")
            .strip()
        )

        lines.append("## SWOT分析\n\n")
        lines.append("###  优势 (Strengths)\n\n")
        lines.append("1. **专注度高**: 作为一人公司，决策链条短，执行力强\n")
        lines.append("2. **灵活性大**: 可以快速试错和调整方向\n")
        lines.append("3. **成本低**: 相比传统企业，固定支出可控\n\n")

        lines.append("###  劣势 (Weaknesses)\n\n")
        lines.append("1. **资源有限**: 人力和时间是最大瓶颈\n")
        lines.append("2. **精力分散**: 需要同时处理多领域事务\n")
        lines.append("3. **规模效应弱**: 难以享受大团队的规模经济\n\n")

        lines.append("###  机会 (Opportunities)\n\n")
        if results:
            first_body = results[0].get("body", "") or results[0].get("snippet", "")
            if first_body:
                lines.append(f"根据市场信息显示：{first_body[:200]}\n\n")
            lines.append("建议抓住以下机会窗口：\n")
        else:
            lines.append("建议关注以下方向：\n")
        lines.append("1. AI工具普及带来的效率红利\n")
        lines.append("2. 细分领域的专业化服务需求增长\n")
        lines.append("3. 个人品牌和信任经济的兴起\n\n")

        lines.append("###  威胁 (Threats)\n\n")
        lines.append("1. **竞争加剧**: 同赛道参与者增多\n")
        lines.append("2. **平台依赖**: 流量入口受制于平台政策\n")
        lines.append("3. **技术迭代快**: 需要持续学习和适应\n\n")

        lines.append("## 结论与行动建议\n\n")
        lines.append("### 总体判断\n\n")
        lines.append(
            f"针对「{topic}」，综合SWOT分析，建议采取**差异化+聚焦**策略：\n\n"
        )
        lines.append("### 具体行动清单\n\n")
        lines.append("| 优先级 | 行动项 | 预期收益 | 时间投入 |\n")
        lines.append("|--------|--------|---------|--------|\n")
        lines.append(
            f"| **P0** | 明确{topic}的核心价值和独特卖点 | 建立竞争优势 | 2天 |\n"
        )
        lines.append("| P1 | 制定90天的执行路线图 | 可控的进展节奏 | 1天 |\n")
        lines.append("| P2 | 建立3个关键指标的追踪机制 | 数据驱动的决策 | 半天 |\n")
        lines.append("| P3 | 寻找2-3个互补的合作方或工具 | 弥补自身短板 | 持续 |\n\n")

        content = "".join(lines)
        return TaskResult(
            success=True,
            content=content,
            task_type=TaskType.DATA_ANALYSIS,
            sources=sources,
            deliverable_format="Markdown",
        )

    def _execute_scenario_based(
        self,
        search_query: str,
        llm_query: Optional[str] = None,
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
    ) -> TaskResult:
        """Path D: Scenario execution — Multi-step workflow based on ScenarioEngineV2

        Typical trigger methods:
        - User clicks preset scenario button (e.g. "内容日历规划")
        - Or inputs natural language containing "执行.*场景" keywords

        How it works:
        1. Pass query to ScenarioEngineV2.process()
        2. Get matched scenario config (containing workflow_steps and deliverable_template)
        3. Execute each WorkflowStep step by step (via _exec_step_with_data)
        4. Assemble all step outputs into a complete deliverable document

        Degradation handling:
        - scenario_engine not initialized → Fall back to information collection path
        - Scenario not matched → Fall back to information collection path
        - Step execution exception → Log and continue to next step (doesn't interrupt entire flow)
        """
        if llm_query is None:
            llm_query = search_query
        try:
            scenario_result = self.scenario_engine.process(search_query)

            if not scenario_result.matched:
                return self._execute_fallback(search_query)

            config = scenario_result.scenario_config
            if config is None:
                return self._execute_fallback(search_query)
            workflow_steps = config.workflow_steps
            deliverable = config.deliverable_template

            lines = []
            lines.append(f"#  {deliverable.name}\n")
            lines.append(
                f"> 场景: {config.description} | 预计耗时: {config.estimated_duration}\n"
            )
            lines.append(f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M')}\n")
            lines.append("---\n\n")

            for step in workflow_steps:
                step_content = self._exec_step_with_data(step, search_query)
                lines.append(f"## Step {step.step_id}: {step.name} ({step.type})\n")
                lines.append(f"*{step.description}*\n\n")
                lines.append(f"{step_content}\n")
                if step.output_spec:
                    lines.append(
                        f" **预期产出**: {step.output_spec.name} ({step.output_spec.format})\n"
                    )
                    lines.append(f"   包含: {', '.join(step.output_spec.includes)}\n")
                lines.append("---\n\n")

            lines.append("#  最终交付物\n\n")
            lines.append(f"以上各步骤的产出整合为完整的**{deliverable.name}**。\n\n")
            lines.append("**包含章节**:\n")
            for i, section in enumerate(deliverable.sections, 1):
                lines.append(f"{i}. {section}\n")
            lines.append("\n---\n*由 OPC-Agents 场景引擎驱动执行*\n")

            content = "".join(lines)
            return TaskResult(
                success=True,
                content=content,
                task_type=TaskType.SCENARIO_BASED,
                deliverable_format=deliverable.format,
            )

        except Exception as e:
            logger.error("[TaskEngineV3] Scenario execution failed: %s", e)
            return self._execute_fallback(search_query)

    def _exec_step_with_data(self, step: Any, query: str) -> str:
        """Execute a single workflow step — Dispatch to different generation strategies based on step.type

        Supported step types and their output strategies:
        - research/data_collection: Search and organize 5 results (with title/summary/link)
        - analysis: Search "分析 数据" related content, output 3 analysis dimensions
        - writing/generation: Call _gen_writing_for_step() to generate complete draft
        - design: Output design proposal framework (UX/UI four elements)
        - marketing: Output promotion strategy matrix (4 channels + budget + KPI + timeline)
        - review: Output review checklist (5 items all  pending confirmation)
        - scheduling/invitation: Output schedule (today + tomorrow options)
        - Other: Return step description text (fallback)

        Design principle:
        Each type must produce substantive content, no empty shells or placeholders allowed.
        This is a key area of v3.4 audit fixes.
        """
        step_type = step.type
        desc = step.description

        if step_type in ("research", "data_collection"):
            results, _ = self._search(
                self._extract_search_query(query), max_results=SEARCH_MAX_RESULTS_STEP
            )
            if results:
                items = []
                for r in results[:SEARCH_MAX_RESULTS_STEP]:
                    title = r.get("title", "")
                    body = r.get("body", "") or r.get("snippet", "")
                    href = r.get("href", "")
                    item = f"- **{title}**\n  {body[:200]}{'...' if len(body) > 200 else ''}"
                    if href:
                        item += f"\n   {href}"
                    items.append(item)
                return (
                    "\n".join(items) if items else "*搜索未返回结果，建议手动补充数据*"
                )
            return f"*数据收集中：请针对「{desc}」收集相关数据和信息*"

        elif step_type == "analysis":
            results, _ = self._search(
                self._extract_search_query(query) + " 分析 数据",
                max_results=SEARCH_MAX_RESULTS_STEP_ANALYSIS,
            )
            findings = []
            if results:
                for r in results[:SEARCH_MAX_RESULTS_STEP_ANALYSIS]:
                    findings.append(
                        f"**{r.get('title', '')}**: {r.get('body', '')[:150]}"
                    )
            else:
                findings = [
                    "**维度一**: 需要基于实际数据进行量化分析",
                    "**维度二**: 与行业标杆进行对标比较",
                    "**维度三**: 识别关键成功因素和瓶颈点",
                ]
            return "\n\n".join(findings)

        elif step_type in ("writing", "generation"):
            return self._gen_writing_for_step(desc, query)

        elif step_type == "design":
            return (
                f"### 设计方案\n\n"
                f"**设计目标**: {desc}\n\n"
                f"**设计方案要点**:\n"
                f"1. **用户体验流程**: 从用户触发到获得价值的完整路径\n"
                f"2. **界面布局**: 关键页面/屏幕的信息架构\n"
                f"3. **视觉风格**: 符合目标受众审美的配色和排版\n"
                f"4. **交互细节**: 关键操作的反馈和引导机制\n\n"
                f"**下一步**: 基于此框架输出详细的设计稿（线框图/高保真原型）"
            )

        elif step_type == "marketing":
            return (
                f"### 推广策略\n\n"
                f"**推广目标**: {desc}\n\n"
                f"**渠道矩阵**:\n"
                f"| 渠道 | 策略 | 预算占比 | KPI |\n"
                f"|------|------|---------|-----|\n"
                f"| 内容营销 | SEO + 社交媒体分发 | 40% | 阅读/互动量 |\n"
                f"| 付费推广 | 精准广告投放 | 35% | CPA/CPS |\n"
                f"| 口碑传播 | KOL/用户推荐 | 15% | 转发/推荐率 |\n"
                f"| 合作置换 | 异业合作 | 10% | 获客成本 |\n\n"
                f"**时间线**: 第1周素材准备 → 第2-3周投放测试 → 第4周优化放量"
            )

        elif step_type == "review":
            return (
                f"### 评审检查清单\n\n"
                f"**评审范围**: {desc}\n\n"
                f"| 检查项 | 状态 | 验证方法 |\n"
                f"|--------|:----:|------|\n"
                f"| 完整性: 所有必需章节齐全 |  待人工确认 | 逐章节核对目录 |\n"
                f"| 准确性: 数据和事实经核实 |  待人工确认 | 数据来源可追溯 |\n"
                f"| 一致性: 各部分逻辑自洽 |  待人工确认 | 交叉引用检查 |\n"
                f"| 可行性: 建议可立即执行 |  待人工确认 | 资源和时间已评估 |\n"
                f"| 清晰度: 表达无歧义 |  待人工确认 | 第三方试读通过 |\n\n"
                f"**评审结论**:  自动生成的评审框架，需人工复核后确认。请逐项检查并标注最终状态。"
            )

        elif step_type in ("scheduling", "invitation"):
            today = time.strftime("%Y-%m-%d")
            tomorrow = time.time() + SECONDS_PER_DAY
            tomorrow_s = time.strftime("%Y-%m-%d", time.localtime(tomorrow))
            return (
                f"### 安排详情\n\n"
                f"**事项**: {desc}\n\n"
                f"| 选项 | 日期 | 时段 | 推荐 |\n"
                f"|------|------|------|------|\n"
                f"| A | {today} | 14:00-16:00 |  推荐 |\n"
                f"| B | {tomorrow_s} | 09:00-11:00 | 备选 |\n"
                f"| C | {tomorrow_s} | 15:00-17:00 | 备选 |\n\n"
                f"**准备事项**: 发送邀请 → 准备材料 → 确认参会 → 预订场地"
            )

        else:
            return f"*{desc}*（已纳入工作流，执行中）"

    def _execute_business_operation(
        self,
        search_query: str,
        llm_query: Optional[str] = None,
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
    ) -> TaskResult:
        if llm_query is None:
            llm_query = search_query

        # Guard: prevent infinite fallback loop between ExecutorBrain and TaskEngineV3
        if getattr(self, "_in_fallback", False):
            logger.warning(
                "[TaskEngineV3] Already in fallback mode — skipping SkillRegistry to prevent circular fallback"
            )
            return TaskResult(
                success=False,
                content="",
                task_type=TaskType.BUSINESS_OPERATION,
                error="Circular fallback prevented",
            )

        try:
            registry = SkillRegistry()
            skill = registry.get_skill("execute_operation")
            if skill and skill.enabled:
                import asyncio as _asyncio

                _new_loop = _asyncio.new_event_loop()
                try:
                    skill_result = _new_loop.run_until_complete(
                        registry.execute_skill(
                            "execute_operation",
                            operation=search_query,
                            parameters={
                                "goal": search_query,
                                "business_type": business_type,
                            },
                        )
                    )
                finally:
                    _new_loop.close()
                if skill_result and skill_result.get("success"):
                    content = str(skill_result.get("data", ""))
                    return TaskResult(
                        success=True,
                        content=content,
                        task_type=TaskType.BUSINESS_OPERATION,
                        deliverable_format="Markdown",
                    )
        except Exception as e:
            logger.warning(
                "[TaskEngineV3] BUSINESS_OPERATION SkillRegistry failed: %s", e
            )
        return self._execute_info_collection(
            search_query, llm_query, business_type, is_follow_up=is_follow_up
        )

    def _execute_general_chat(
        self,
        search_query: str,
        llm_query: Optional[str] = None,
        is_follow_up: bool = False,
    ) -> TaskResult:
        """Path E: Chat/greeting/help — Fallback path

        Handles input that doesn't belong to the above 4 types, mainly:
        - Greetings: "你好"/"谢谢"
        - Help requests: "帮助"/"能做什么"
        - Unclassifiable other input

        Design intent:
        Even the fallback path should provide useful information — Tell users about system capabilities,
        guide them to use correct function entry points, rather than simply replying "I don't understand".
        """
        if llm_query is None:
            llm_query = search_query
        query = search_query
        query_lower = query.lower()

        greeting_zh = (
            " 你好！我是OPC-Agents一人公司助手。\n\n"
            "我能直接帮你完成任务并交付文件：\n\n"
            "-  **收集信息** → 返回真实搜索结果+研究报告（可下载.md文件）\n"
            "-  **生成方案** → 返回完整可执行的计划文档（含时间表/资源/风险）\n"
            "-  **分析问题** → 返回SWOT分析+具体行动清单\n"
            "-  **执行场景** → 返回多步骤工作流+每步产出物\n\n"
            "直接告诉我你需要什么，我来帮你做完并交付文件！"
        )
        greeting_en = (
            " Hello! I'm OPC-Agents, your One-Person Company assistant.\n\n"
            "I can directly complete tasks and deliver files for you:\n\n"
            "-  **Collect Information** → Real search results + research report (downloadable .md)\n"
            "-  **Generate Plans** → Complete executable plan document (with timeline/resources/risks)\n"
            "-  **Analyze Issues** → SWOT analysis + specific action items\n"
            "-  **Execute Scenarios** → Multi-step workflows with deliverables at each step\n\n"
            "Tell me what you need, and I'll get it done and deliver the file!"
        )
        greeting_jp = (
            " こんにちは！OPC-Agents一人会社アシスタントです。\n\n"
            "タスクを直接完了し、ファイルを納品できます：\n\n"
            "-  **情報収集** → 実際の検索結果＋調査レポート（ダウンロード可能.md）\n"
            "-  **プラン生成** → 完全な実行計画書（タイムライン/リソース/リスク付き）\n"
            "-  **問題分析** → SWOT分析＋具体的なアクションリスト\n"
            "-  **シナリオ実行** → マルチステップワークフロー＋各ステップの成果物\n\n"
            "必要な結果を伝えてください。ファイルを納品します！"
        )

        help_zh = (
            " **我能直接为你交付的成果物**：\n\n"
            "| 你说 | 我交付 |\n"
            "|------|--------|\n"
            '| "帮我收集XX趋势" | 真实搜索结果+结构化研究报告(.md) |\n'
            '| "帮我写XX方案" | 完整执行计划(.md)，含目标/时间表/资源/风险/验收标准 |\n'
            '| "帮我分析XX" | SWOT分析+具体行动清单(.md) |\n'
            "| 点击场景按钮 | 多步骤工作流+每步产出物(.md) |\n\n"
            "所有成果物都可以直接下载使用！"
        )
        help_en = (
            " **Deliverables I can produce for you**:\n\n"
            "| You Say | I Deliver |\n"
            "|---------|----------|\n"
            '| "Collect XX trends" | Real search results + structured research report (.md) |\n'
            '| "Write a XX plan" | Complete execution plan (.md) with goals/timeline/resources/risks |\n'
            '| "Analyze XX" | SWOT analysis + specific action items (.md) |\n'
            "| Click scenario button | Multi-step workflow + deliverables at each step (.md) |\n\n"
            "All deliverables can be downloaded and used directly!"
        )
        help_jp = (
            " **納品できる成果物**：\n\n"
            "| あなたの指示 | 納品物 |\n"
            "|-------------|--------|\n"
            "| 「XXトレンドを収集」 | 実際の検索結果＋構造化調査レポート(.md) |\n"
            "| 「XXプランを作成」 | 完全な実行計画(.md)、目標/タイムライン/リソース/リスク付き |\n"
            "| 「XXを分析」 | SWOT分析＋具体的なアクションリスト(.md) |\n"
            "| シナリオボタンをクリック | マルチステップワークフロー＋各ステップの成果物(.md) |\n\n"
            "全ての成果物はダウンロードしてすぐに使えます！"
        )

        greeting_keywords = {
            "zh": ["你好", "您好", "嗨"],
            "en": [
                "hello",
                "hi",
                "hey",
                "good morning",
                "good afternoon",
                "good evening",
            ],
            "jp": ["こんにちは", "おはよう", "こんばんは"],
        }
        help_keywords = {
            "zh": ["帮助", "能做什么", "帮我", "功能"],
            "en": ["help", "what can you do", "features", "capabilities"],
            "jp": ["助けて", "何ができる", "ヘルプ"],
        }

        for lang, keywords in greeting_keywords.items():
            if any(kw in query_lower for kw in keywords):
                greeting_map = {"zh": greeting_zh, "en": greeting_en, "jp": greeting_jp}
                return TaskResult(
                    success=True,
                    content=greeting_map[lang],
                    task_type=TaskType.GENERAL_CHAT,
                )

        for lang, keywords in help_keywords.items():
            if any(kw in query_lower for kw in keywords):
                help_map = {"zh": help_zh, "en": help_en, "jp": help_jp}
                return TaskResult(
                    success=True,
                    content=help_map[lang],
                    task_type=TaskType.GENERAL_CHAT,
                )

        default = (
            f"收到！关于「{query[:50]}{'...' if len(query) > 50 else ''}」，我来帮你处理。\n\n"
            f"正在执行任务，完成后会生成文件供你下载。"
        )
        return TaskResult(
            success=True, content=default, task_type=TaskType.GENERAL_CHAT
        )

    def _execute_fallback(self, query: str) -> TaskResult:
        """Scenario execution degradation path — Fall back to information collection when scenario engine is unavailable

        Design intent: Ensure user experience continuity.
        Even if scenario functionality is unavailable, users shouldn't see an error page.
        At least return a useful search result page.
        """
        return self._execute_info_collection(query)
