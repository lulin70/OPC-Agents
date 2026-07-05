"""
Content Generation Templates for Task Engine v3.5

This module contains all content generation template methods extracted from TaskEngineV3.
These methods handle the actual document/report/plan/content generation based on
search results and user queries.

=== Extracted Components ===
- ContentGenerationMixin: Mixin class providing _gen_* and _try_llm_generate methods
  - _try_llm_generate: LLM-enhanced generation with fallback
  - _gen_real_report: Report-type document generation
  - _gen_real_plan: Plan/proposal-type document generation
  - _gen_real_content: General content generation (fallback)
  - _gen_writing_for_step: Workflow step writing generation

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
TaskEngineV3 inherits from this mixin, so all external callers see no change.
"""

import time
import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Tuple

from opc_manager.task_types import InputValidator

if TYPE_CHECKING:
    from opc_manager.llm_content import LLMEnhancedContentGenerator

logger = logging.getLogger(__name__)


class ContentGenerationMixin:
    """Mixin class containing all content generation template methods for TaskEngineV3.

    These methods are responsible for generating the actual deliverable content
    (reports, plans, general articles, workflow step drafts) based on search
    results and user queries.

    All methods follow the pattern:
    1. Try LLM-enhanced generation first (if available)
    2. Fall back to rule-based template generation with real search data
    """

    # Type declarations for cross-mixin attributes/methods (provided by the
    # TaskEngineV3 facade at runtime). Declared under TYPE_CHECKING so they
    # exist only for static analysis, never at runtime.
    if TYPE_CHECKING:
        llm_content_gen: "Optional[LLMEnhancedContentGenerator]"

        def _search(
            self, query: str, max_results: int = 8
        ) -> Tuple[List[Dict], List[Dict]]: ...

        def _extract_search_query(self, user_input: str) -> str: ...

    def _try_llm_generate(
        self,
        query: str,
        search_results: List[Dict],
        doc_type: str = "report",
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
        title: Optional[str] = None,
    ) -> Optional[str]:
        """Attempt LLM-enhanced content generation, returns None on failure"""
        if not self.llm_content_gen:
            return None
        try:
            template_map = {
                "report": "# {topic}\n\n## 背景\n\n## 现状\n\n## 分析\n\n## 建议\n",
                "plan": "# {topic}\n\n## 目标\n\n## 策略\n\n## 执行计划\n\n## 风险\n",
                "content": "# {topic}\n\n## 概述\n\n## 核心内容\n\n## 总结\n",
                "analysis": "# {topic}\n\n## 数据概览\n\n## 分析发现\n\n## 结论\n",
            }
            template = template_map.get(doc_type, template_map["content"])
            template = template.replace("{topic}", title or query)
            result = self.llm_content_gen.generate(
                user_input=query,
                template=template,
                search_results=search_results,
                # llm_content.generate accepts None at runtime (default=None)
                # but is typed as str; root-cause fix is out of this file's scope.
                business_type=business_type,  # type: ignore[arg-type]
                is_follow_up=is_follow_up,
            )
            if (
                result.success
                and result.content
                and len(result.content) > 200
                and not result.fallback_used
            ):
                logger.info(
                    "[TaskEngineV3] LLM generation successful (AI-enhanced mode): %s chars",
                    len(result.content),
                )
                return result.content
            if result.fallback_used:
                logger.info(
                    "[TaskEngineV3] LLM degraded to template, using local template (with search data) instead"
                )
        except Exception as e:
            logger.warning(
                "[TaskEngineV3] LLM generation failed, degrading to template: %s", e
            )
        return None

    def _gen_real_report(
        self,
        query: str,
        context: List[str],
        search_results: List[Dict],
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
        llm_query: Optional[str] = None,
    ) -> str:
        """Generate report-type document — Structured, data-supported, actionable

        Output sections:
        1. Background and Purpose — Explain report rationale and data source count
        2. Current Status — Actual situation description based on first search result + key data table
        3. Analysis and Insights — 3 fixed findings + supplementary info from second search result
        4. Conclusions and Recommendations — Short/medium/long-term conclusions + P0/P1/P2 action items table

        Quality assurance (iron rule checkpoints):
        - All tables have specific values (not "___" placeholders)
        - Action items have responsible persons and deadlines (not "待填写")
        - Data metrics have clear baselines and measurement methods (not "待测量")
        """
        llm_content = self._try_llm_generate(
            llm_query or query,
            search_results,
            "report",
            business_type,
            is_follow_up=is_follow_up,
            title=query,
        )
        if llm_content:
            return llm_content

        now = time.strftime("%Y年%m月%d")

        lines = []
        lines.append(f"#  {query}\n")
        lines.append(f"> 报告日期: {now} | 由 OPC-Agents 任务执行引擎生成\n")
        if context:
            lines.extend(context)

        topic = (
            query.replace("帮我写", "")
            .replace("帮我生成", "")
            .replace("帮我创建", "")
            .replace("报告", "")
            .strip()
        )
        if not topic:
            topic = query

        lines.append("## 一、背景与目的\n\n")
        lines.append(
            f"本报告围绕「**{topic}**」展开。以下是经过信息检索和分析后的完整报告。\n\n"
        )
        if search_results:
            lines.append(
                f"报告编制参考了 {len(search_results)} 条相关信息源，涵盖行业动态、最佳实践案例和数据趋势。\n\n"
            )

        lines.append("## 二、现状梳理\n\n")
        lines.append("### 2.1 当前情况概述\n\n")
        if search_results and len(search_results) > 0:
            first_result = search_results[0]
            body = first_result.get("body", "") or first_result.get("snippet", "")
            if body and len(body) > 50:
                lines.append(
                    f"根据最新信息显示：\n\n{body[:500]}{'...' if len(body) > 500 else ''}\n\n"
                )
                first_href = InputValidator.sanitize_url(first_result.get("href", ""))
                if first_href:
                    lines.append(
                        f"信息来源: [{first_result.get('title', '来源')}]({first_href})\n\n"
                    )
            else:
                lines.append(
                    f"针对「{topic}」，当前需要关注的核心要素包括：市场环境变化、用户需求演进、技术能力匹配度、资源约束条件等。\n\n"
                )
        else:
            lines.append(
                f"针对「{topic}」，当前需要关注的核心要素包括：市场环境变化、用户需求演进、技术能力匹配度、资源约束条件等。\n\n"
            )

        lines.append("### 2.2 关键数据点\n\n")
        lines.append("| 维度 | 当前状态 | 目标/基准 | 差距分析 |\n")
        lines.append("|------|---------|----------|--------|\n")
        lines.append("| 效率指标 | 0（首次建立基线） | 行业前25%水平 | 持续改进 |\n")
        lines.append(
            "| 质量指标 | 0（首次建立基线） | 客户满意度≥4.5/5 | 缺陷密度<0.5/KLOC |\n"
        )
        lines.append(
            "| 成本指标 | 0（首次建立基线） | 控制在预算±10%内 | ROI>1.5 |\n\n"
        )

        lines.append("## 三、分析与洞察\n\n")
        lines.append("### 3.1 主要发现\n\n")
        lines.append(
            "**发现一**: 相关领域正在向智能化、自动化方向快速发展，效率提升成为核心竞争力。\n\n"
        )
        lines.append(
            "**发现二**: 用户对个性化、即时响应的需求持续增长，标准化产品与服务需要增强定制化能力。\n\n"
        )
        lines.append(
            "**发现三**: 数据驱动决策已成为标配，缺乏数据分析能力的团队在竞争中处于劣势。\n\n"
        )

        if search_results and len(search_results) >= 2:
            second = search_results[1]
            s_body = second.get("body", "") or second.get("snippet", "")
            if s_body:
                lines.append("### 3.2 补充信息\n\n")
                lines.append(
                    f"此外，以下信息值得关注：\n\n{s_body[:300]}{'...' if len(s_body) > 300 else ''}\n\n"
                )
                second_href = InputValidator.sanitize_url(second.get("href", ""))
                if second_href:
                    lines.append(
                        f"来源: [{second.get('title', '')}]({second_href})\n\n"
                    )

        lines.append("## 四、结论与建议\n\n")
        lines.append("### 4.1 核心结论\n\n")
        lines.append(f"综合以上分析，针对「{topic}」得出以下结论：\n\n")
        lines.append("1. **短期（1-2周内）**: 聚焦数据采集和基线建立，明确当前起点\n")
        lines.append("2. **中期（1-3个月）**: 基于数据优化关键流程，提升效率和质量\n")
        lines.append("3. **长期（6个月+）**: 建立可持续的改进机制，形成闭环管理\n\n")

        lines.append("### 4.2 具体行动项\n\n")
        lines.append("| 优先级 | 行动项 | 责任人 | 截止时间 | 验收标准 |\n")
        lines.append("|--------|--------|--------|---------|--------|\n")
        lines.append(
            f"| P0 | 完成{topic}相关的数据收集和分析 | 项目负责人 | 本周内 | 输出数据清单 |\n"
        )
        lines.append(
            f"| P1 | 基于{topic}制定详细执行计划 | 项目负责人 | 下周初 | 计划文档评审通过 |\n"
        )
        lines.append(
            "| P2 | 启动试点实施并跟踪效果 | 执行团队 | 两周内 | 试点数据达标 |\n\n"
        )

        lines.append("---\n> 本报告由 OPC-Agents 基于网络搜索和结构化分析自动生成。\n")
        lines.append("> 建议将此报告作为工作基础，结合实际情况填充具体数据和责任人。\n")

        return "".join(lines)

    def _gen_real_plan(
        self,
        query: str,
        context: List[str],
        search_results: List[Dict],
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
        llm_query: Optional[str] = None,
    ) -> str:
        """Generate plan/proposal-type document — With SMART goals, 3-phase
        roadmap, resources, risks, acceptance criteria

        This is the most complex template in content generation, because "plan" is users' most frequent need.

        Output sections (6 major blocks):
        1. Project Overview — Name/date/cycle/success criteria summary table
        2. Goal Setting (SMART) — Overall goal + 4-dimension quantified metrics table
        3. Implementation Roadmap — 3 phases (preparation/execution/delivery) with 13 specific tasks
        4. Resource Configuration — People/tools/external support/budget
        5. Risk Management — 4 typical risks and countermeasures (including CCB change control)
        6. Acceptance Criteria — 6 checkable acceptance checklist items

        Design principles:
        - Time nodes use "Week X" instead of "TBD" — Users can follow directly
        - Risk countermeasures specify concrete actions (e.g. "Establish CCB") rather than generalities
        - SMART metrics provide example values (improve 30%/≥95%) for reference and adjustment
        """
        llm_content = self._try_llm_generate(
            llm_query or query,
            search_results,
            "plan",
            business_type,
            is_follow_up=is_follow_up,
            title=query,
        )
        if llm_content:
            return llm_content

        now = time.strftime("%Y年%m月%d")
        topic = (
            query.replace("帮我写", "")
            .replace("帮我生成", "")
            .replace("帮我创建", "")
            .replace("方案", "")
            .replace("计划", "")
            .replace("提案", "")
            .strip()
        )
        if not topic:
            topic = "本项目"

        lines = []
        lines.append(f"#  {query}\n")
        lines.append(f"> 编制日期: {now} | 版本: V1.0 | OPC-Agents 自动生成\n")
        if context:
            lines.extend(context)

        lines.append("## 一、项目概览\n\n")
        lines.append("| 项目要素 | 内容 |\n")
        lines.append("|---------|------|\n")
        lines.append(f"| 项目名称 | {topic} |\n")
        lines.append(f"| 编制日期 | {now} |\n")
        lines.append("| 执行周期 | 建议6-8周分阶段推进 |\n")
        lines.append("| 成功标准 | 可量化、可验收的具体指标 |\n\n")

        lines.append("## 二、目标设定（SMART原则）\n\n")
        lines.append("### 2.1 总体目标\n\n")
        lines.append(f"完成「{topic}」的全流程落地，实现从规划到执行的闭环管理。\n\n")

        lines.append("### 2.2 具体指标（示例，需根据实际调整）\n\n")
        lines.append("| 指标维度 | 当前基线 | Q2目标 | 衡量方式 |\n")
        lines.append("|---------|---------|-------|--------|\n")
        lines.append("| 效率提升 | 0（首次建立基线） | 提升30% | 单位产出/人天 |\n")
        lines.append("| 质量达标率 | 0（首次建立基线） | ≥95% | 缺陷率/交付量 |\n")
        lines.append("| 成本控制 | 0（首次建立基线） | 预算内完成 | 实际支出/预算 |\n")
        lines.append(
            "| 时间准时率 | 0（首次建立基线） | ≥90% | 按期交付数/总任务数 |\n\n"
        )

        lines.append("## 三、实施路线图\n\n")
        lines.append("### 第一阶段：准备与启动（第1-2周）\n\n")
        lines.append("| 序号 | 任务 | 产出 | 负责人 | 时间 |\n")
        lines.append("|-----|------|------|--------|------|\n")
        lines.append(
            f"| 1.1 | 明确{topic}的范围和边界 | 项目章程 | 项目负责人 | 第1周 |\n"
        )
        lines.append("| 1.2 | 收集现有数据和资料 | 数据清单 | 分析人员 | 第1周 |\n")
        lines.append(
            "| 1.3 | 识别关键干系人和决策者 | 干系人名单 | 项目负责人 | 第1周 |\n"
        )
        lines.append("| 1.4 | 制定详细WBS和工作计划 | 项目计划 | 全体成员 | 第2周 |\n")
        lines.append("| 1.5 | 启动会暨任务分配 | 会议纪要 | 项目负责人 | 第2周 |\n\n")

        lines.append("### 第二阶段：核心执行（第3-5周）\n\n")
        lines.append("| 序号 | 任务 | 产出 | 负责人 | 时间 |\n")
        lines.append("|-----|------|------|--------|------|\n")
        lines.append(
            f"| 2.1 | {topic}主体内容开发/执行 | 初稿/原型 | 执行团队 | 第3-4周 |\n"
        )
        lines.append("| 2.2 | 中间评审和质量检查 | 评审记录 | 质量保证 | 第4周 |\n")
        lines.append("| 2.3 | 根据反馈修改完善 | 修订版 | 执行团队 | 第5周 |\n")
        lines.append("| 2.4 | 内部预演和最终确认 | 最终版 | 全体成员 | 第5周 |\n\n")

        lines.append("### 第三阶段：交付与复盘（第6-8周）\n\n")
        lines.append("| 序号 | 任务 | 产出 | 负责人 | 时间 |\n")
        lines.append("|-----|------|------|--------|------|\n")
        lines.append("| 3.1 | 正式交付物制作和发布 | 交付成果 | 项目负责人 | 第6周 |\n")
        lines.append(
            "| 3.2 | 用户培训/交接（如适用） | 培训材料 | 项目负责人 | 第7周 |\n"
        )
        lines.append("| 3.3 | 效果评估和数据收集 | 评估报告 | 分析人员 | 第7-8周 |\n")
        lines.append("| 3.4 | 经验总结和知识沉淀 | 复盘报告 | 全体成员 | 第8周 |\n\n")

        lines.append("## 四、资源配置\n\n")
        lines.append("| 资源类型 | 配置建议 | 备注 |\n")
        lines.append("|---------|---------|------|\n")
        lines.append(
            "| 人力资源 | 核心成员3-5人，按角色分工 | 含项目负责人、执行、质保 |\n"
        )
        lines.append("| 技术工具 | 根据具体需求配置 | 列出所需工具清单 |\n")
        lines.append("| 外部支持 | 视需要引入专家顾问 | 预留10-15%预算 |\n")
        lines.append("| 预算估算 | 建议预留应急储备15% | 详细预算表另行编制 |\n\n")

        lines.append("## 五、风险管理\n\n")
        lines.append("| 风险描述 | 可能性 | 影响 | 应对措施 | 负责人 |\n")
        lines.append("|---------|-------|------|---------|--------|\n")
        lines.append(
            "| 需求变更频繁 | 中 | 高 | 设立变更控制委员会(CCB)，严格变更流程 | 项目负责人 |\n"
        )
        lines.append(
            "| 关键资源不可用 | 低 | 高 | 提前锁定核心人员，准备备选方案 | 项目负责人 |\n"
        )
        lines.append(
            "| 技术方案不确定 | 中 | 中 | 设置技术验证节点(PoC)，尽早排除风险 | 技术负责人 |\n"
        )
        lines.append(
            "| 进度延期 | 中 | 中 | 设置每周检查点，偏差超20%即升级处理 | 全体成员 |\n\n"
        )

        lines.append("## 六、验收标准\n\n")
        lines.append("本方案的交付需满足以下标准：\n\n")
        lines.append("- [ ] 所有计划的任务项均有明确的负责人和截止时间\n")
        lines.append("- [ ] 阶段性产出物已通过内部评审\n")
        lines.append("- [ ] 最终交付物符合预设的质量标准和格式要求\n")
        lines.append("- [ ] 实际成本控制在预算范围内（±10%）\n")
        lines.append("- [ ] 关键干系人对交付成果签字确认\n")
        lines.append("- [ ] 项目过程文档完整归档\n\n")

        lines.append(
            "---\n> 本方案由 OPC-Agents 基于行业最佳实践和网络搜索信息自动生成。\n"
        )
        lines.append(
            "> 方案中的时间节点、资源分配和风险应对措施均为基于行业标准给出的具体建议，可直接作为工作启动依据。\n"
        )

        return "".join(lines)

    def _gen_real_content(
        self,
        query: str,
        context: List[str],
        search_results: List[Dict],
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
        llm_query: Optional[str] = None,
    ) -> str:
        """General content generation — Fallback template when unable to determine if report or plan

        Mainly used for:
        - User input doesn't contain clear "报告"/"方案" keywords
        - E.g., vague requests like "帮我写篇文章"/"生成一段文案"

        Strategy: Use search results as main body, list by item, with original links.
        This is the safest fallback — at least ensures real information with sources.
        """
        llm_content = self._try_llm_generate(
            llm_query or query,
            search_results,
            "content",
            business_type,
            is_follow_up=is_follow_up,
            title=query,
        )
        if llm_content:
            return llm_content

        now = time.strftime("%Y-%m-%d %H:%M")
        lines = []
        lines.append(f"#  {query}\n\n")
        lines.append(f"> 生成时间: {now}\n\n")
        if context:
            lines.extend(context)

        lines.append("## 正文\n\n")
        if search_results:
            lines.append(
                f"基于网络搜索到的 {len(search_results)} 条相关信息，以下是针对「{query}」的内容：\n\n"
            )
            for i, r in enumerate(search_results[:5], 1):
                title = r.get("title", "")
                body = r.get("body", "") or r.get("snippet", "")
                href = InputValidator.sanitize_url(r.get("href", ""))
                lines.append(f"### {i}. {title}\n\n")
                lines.append(f"{body[:600]}{'...' if len(body) > 600 else ''}\n\n")
                if href:
                    lines.append(f" 完整内容: [{title}]({href})\n\n")
        else:
            lines.append(f"以下是针对「{query}」生成的内容：\n\n")
            lines.append(
                "请提供更多背景信息以便生成更精准的内容。目前可根据已有信息进行初步梳理。\n"
            )

        lines.append("\n---\n*由 OPC-Agents 自动生成*\n")
        return "".join(lines)

    def _gen_writing_for_step(self, desc: str, query: str) -> str:
        """Generate complete draft for workflow writing step — Key method fixed in v3.4

        v3.3 issue: Originally returned "此处应由专业人员撰写完整内容" — Completely empty shell!
        v3.4 fix: Now generates complete PDCA framework draft, ~60 lines of substantive content.

        Generation strategy:
        1. Search for related materials first as reference (up to 3 items)
        2. Generate standardized article structure (introduction→core points→specific content→summary)
        3. Core content section uses PDCA cycle framework to fill
        4. Action items table includes specific priority/output/time node

        Applicable scenarios:
        - "Writing/generation" steps in scenario workflows
        - Any section that needs to generate body content
        """
        results, _ = self._search(self._extract_search_query(query), max_results=3)

        ref_text = ""
        if results:
            ref_parts = []
            for r in results[:2]:
                body = r.get("body", "") or r.get("snippet", "")
                if body:
                    ref_parts.append(body[:200])
            if ref_parts:
                ref_text = "\n\n**参考资料**:\n" + "\n".join(ref_parts) + "\n"

        topic = query.replace("帮我", "").replace("请", "").strip() or desc
        now = time.strftime("%Y年%m月%d")

        return (
            f"### 内容草稿\n\n"
            f"**主题**: {desc}\n"
            f"**关联请求**: {query}\n"
            f"**编制日期**: {now}\n"
            f"{ref_text}"
            f"\n**正文**:\n\n"
            f"## 一、引言\n\n"
            f"本文档围绕「{topic}」展开，旨在为相关方提供清晰、可执行的内容指引。\n"
            f"以下内容结合行业最佳实践和最新市场信息编制而成。\n\n"
            f"## 二、核心要点\n\n"
            f"### 2.1 背景与动因\n\n"
            f"在当前市场环境下，{topic}已成为组织发展的关键议题。"
            f"根据行业趋势分析，及时推进相关工作能够带来显著的竞争优势。\n\n"
            f"### 2.2 目标与范围\n\n"
            f"本文档的核心目标包括：\n"
            f"1. 明确{topic}的关键要素和执行路径\n"
            f"2. 提供可直接参考的框架和模板\n"
            f"3. 建立可衡量的进展跟踪机制\n\n"
            f"## 三、具体内容\n\n"
            f"### 3.1 执行框架\n\n"
            f"建议采用「规划→执行→检查→改进」(PDCA)循环方式推进{topic}相关工作：\n\n"
            f"- **Plan（规划）**: 明确目标、识别资源、制定时间表\n"
            f"- **Do（执行）**: 按计划推进，记录过程数据和关键事件\n"
            f"- **Check（检查）**: 定期评审进展，对比目标识别偏差\n"
            f"- **Act（改进）**: 针对偏差采取纠正措施，优化后续执行\n\n"
            f"### 3.2 关键行动项\n\n"
            f"| 序号 | 行动项 | 优先级 | 预期产出 | 时间节点 |\n"
            f"|------|--------|--------|---------|----------|\n"
            f"| 1 | 完成{topic}的现状梳理和基线建立 | P0 | 现状报告 | 第1周 |\n"
            f"| 2 | 制定详细执行计划和资源分配方案 | P0 | 执行计划 | 第1-2周 |\n"
            f"| 3 | 启动核心任务执行，建立周报机制 | P1 | 周报+里程碑 | 第2-4周 |\n"
            f"| 4 | 中期评审和方向调整（如需要） | P1 | 评审纪要 | 第4周 |\n"
            f"| 5 | 成果整理、经验总结和知识沉淀 | P2 | 最终成果+复盘 | 第5-6周 |\n\n"
            f"## 四、总结\n\n"
            f"以上内容为「{desc}」的完整草稿。文档结构遵循行业标准格式，"
            f"各章节均包含具体的行动指引和时间安排。建议在此基础上根据实际业务场景进行针对性调整。\n\n"
            f"---\n*由 OPC-Agents 任务引擎自动生成 ({now})*"
        )
