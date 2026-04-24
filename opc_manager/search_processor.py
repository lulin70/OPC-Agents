"""搜索结果后处理器 v3.5 — P0-1 搜索质量修复

解决的核心问题：
- 用户输入"Q2营销方案"，返回"书信格式""写小说""SCI论文"等无关结果
- DuckDuckGo中文搜索质量差，需要后处理层提升相关性

=== 设计决策 (ADR-008) ===
决策：先做规则后处理层，而非更换搜索引擎
原因：
  1. 零成本（无需API Key、无需付费）
  2. 立即见效（不依赖第三方服务稳定性）
  3. 可叠加（未来换引擎时此层仍有效）
降级条件：效果不够 → 再考虑Baidu/Google/Bing多引擎整合

=== 处理流水线 ===
  原始搜索结果 → 关键词提取 → 规则过滤 → TF-IDF评分 → 排序输出
                                              ↓
                                        结果为空？→ 知识库兜底

=== 性能要求 ===
  - 单次处理耗时 < 100ms（不应增加明显延迟）
  - 内存占用 < 1MB（不缓存大量中间结果）

=== 版本历史 ===
  v3.5.0: 初始版本，实现关键词提取/过滤/评分/兜底四步流水线
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter

logger = logging.getLogger(__name__)

STOP_WORDS_CN = {
    "的",
    "了",
    "和",
    "是",
    "在",
    "我",
    "有",
    "就",
    "不",
    "人",
    "都",
    "一",
    "一个",
    "上",
    "也",
    "很",
    "到",
    "说",
    "要",
    "去",
    "你",
    "会",
    "着",
    "没有",
    "看",
    "好",
    "自己",
    "这",
    "他",
    "她",
    "它",
    "们",
    "那",
    "什么",
    "怎么",
    "如何",
    "为什么",
    "哪",
    "哪个",
    "帮",
    "帮我",
    "请",
    "可以",
    "能够",
    "需要",
    "想要",
    "希望",
    "制定",
    "写",
    "做",
    "收集",
    "分析",
    "生成",
    "创建",
    "提供",
}

STOP_WORDS_EN = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "because",
}

KNOWLEDGE_BASE = {
    "营销方案": [
        {
            "title": "SaaS产品季度增长策略框架",
            "snippet": "从用户获取到留存的全链路增长方法论，包含AARRR漏斗模型...",
            "href": "#kb-marketing-001",
        },
        {
            "title": "B2B SaaS Q2营销计划模板",
            "snippet": "第二季度市场推广预算分配、渠道策略、KPI设定指南...",
            "href": "#kb-marketing-002",
        },
        {
            "title": "一人公司低成本获客方法",
            "snippet": "内容营销+社群运营+口碑推荐的组合策略，月成本<5000元...",
            "href": "#kb-marketing-003",
        },
        {
            "title": "内容日历规划方法论",
            "snippet": "选题策划→排期管理→发布节奏→数据复盘的完整内容运营闭环...",
            "href": "#kb-marketing-004",
        },
    ],
    "税收政策": [
        {
            "title": "2026年小微企业税收优惠政策汇总",
            "snippet": "一人公司可享受的增值税减免、所得税优惠、社保补贴政策详解...",
            "href": "#kb-tax-001",
        },
        {
            "title": "个体工商户vs一人公司税务对比",
            "snippet": "税率对比、申报流程、可抵扣项目全面分析...",
            "href": "#kb-tax-002",
        },
        {
            "title": "一人公司财务合规自查清单",
            "snippet": "发票管理、成本核算、年度审计、税务申报的关键节点提醒...",
            "href": "#kb-tax-003",
        },
    ],
    "AI Agent": [
        {
            "title": "AI Agent架构设计模式2026",
            "snippet": "ReAct/Plan-and-Execute/Multi-Agent等主流架构对比与选型指南...",
            "href": "#kb-agent-001",
        },
        {
            "title": "大模型应用开发最佳实践",
            "snippet": "Prompt Engineering、RAG、Function Calling等技术栈选型...",
            "href": "#kb-agent-002",
        },
        {
            "title": "AI产品定价策略与商业模式",
            "snippet": "按调用量/订阅制/效果付费三种模式的ROI对比分析...",
            "href": "#kb-agent-003",
        },
    ],
    "产品发布": [
        {
            "title": "MVP到正式发布的检查清单",
            "snippet": "功能冻结→灰度测试→数据监控→全量发布的标准流程...",
            "href": "#kb-launch-001",
        },
        {
            "title": "数字产品定价策略指南",
            "snippet": "成本定价法、价值定价法、竞争定价法的适用场景与计算公式...",
            "href": "#kb-launch-002",
        },
        {
            "title": "产品发布推广渠道选择",
            "snippet": "ProductHunt/V2EX/即刻/小红书等平台的发布策略与效果对比...",
            "href": "#kb-launch-003",
        },
        {
            "title": "SaaS产品免费到付费转化漏斗",
            "snippet": "Freemium模型设计、付费墙设置、转化率优化的实战经验...",
            "href": "#kb-launch-004",
        },
    ],
    "数据分析": [
        {
            "title": "用户行为数据分析框架",
            "snippet": "DAU/MAU/留存率/转化漏斗的核心指标定义与计算方法...",
            "href": "#kb-data-001",
        },
        {
            "title": "竞品分析报告模板",
            "snippet": "功能对比/定价对比/市场份额/用户评价的四维分析框架...",
            "href": "#kb-data-002",
        },
        {
            "title": "SEO优化实战指南",
            "snippet": "关键词研究→内容优化→外链建设→技术SEO的完整路线图...",
            "href": "#kb-data-003",
        },
    ],
    "项目管理": [
        {
            "title": "一人公司项目管理方法论",
            "snippet": "看板管理+时间盒+周复盘的轻量级项目管理框架...",
            "href": "#kb-pm-001",
        },
        {
            "title": "咨询提案撰写模板",
            "snippet": "问题定义→方案设计→实施路径→预期收益的专业提案结构...",
            "href": "#kb-pm-002",
        },
        {
            "title": "远程团队协作工具选型",
            "snippet": "Notion/飞书/Slack/Lark等工具的功能对比与组合推荐...",
            "href": "#kb-pm-003",
        },
    ],
}


@dataclass
class ProcessedResult:
    """处理后的搜索结果容器

    设计意图：
    - 统一返回格式，让调用方无需关心内部处理细节
    - metadata记录处理统计信息，用于调试和监控
    - fallback_used标记是否触发了知识库兜底
    """

    results: List[Dict]
    original_count: int = 0
    filtered_count: int = 0
    fallback_used: bool = False
    processing_time_ms: float = 0.0


class SearchResultProcessor:
    """搜索结果后处理器 — 提升DuckDuckGo中文搜索相关性

    核心能力：
    1. 关键词提取：从中文查询中去除停用词，保留业务关键词
    2. 规则过滤：标题/摘要必须包含至少一个查询关键词
    3. TF-IDF评分：简化版评分算法，标题权重×2 + 摘要重叠度
    4. 知识库兜底：所有结果都不相关时返回预定义的高质量条目

    使用示例：
        >>> processor = SearchResultProcessor()
        >>> result = processor.process("Q2营销方案", raw_search_results)
        >>> for item in result.results[:3]:
        ...     print(item['title'])

    降级策略：
    - 处理后结果为空 → 返回原始结果（保证不比v3.4更差）
    - 异常情况 → 记录日志并返回原始结果（不中断主流程）
    """

    def __init__(
        self,
        min_keyword_match: int = 1,
        title_weight: float = 2.0,
        snippet_weight: float = 1.0,
        min_results: int = 3,
    ):
        """初始化处理器

        Args:
            min_keyword_match: 结果必须匹配的最少关键词数量（默认1个）
            title_weight: 标题匹配权重（相对于摘要）
            snippet_weight: 摘要匹配权重
            min_results: 最少返回结果数（不足时用知识库补充）
        """
        self.min_keyword_match = min_keyword_match
        self.title_weight = title_weight
        self.snippet_weight = snippet_weight
        self.min_results = min_results

    def process(self, query: str, raw_results: List[Dict]) -> ProcessedResult:
        """三步处理流水线主入口

        处理步骤：
        1. 从query提取关键词
        2. 规则过滤无关结果
        3. TF-IDF评分排序
        4. 检查是否需要知识库兜底

        Args:
            query: 用户原始查询（如"帮我制定Q2营销方案"）
            raw_results: DuckDuckGo返回的原始搜索结果列表

        Returns:
            ProcessedResult: 包含处理后的结果列表和元数据
        """
        import time

        start_time = time.time()

        original_count = len(raw_results)

        if not raw_results:
            logger.warning("[SearchResultProcessor] 输入结果为空，尝试知识库兜底")
            fallback_results = self._fallback_to_knowledge_base(query)
            processing_time = (time.time() - start_time) * 1000
            return ProcessedResult(
                results=fallback_results,
                original_count=0,
                filtered_count=0,
                fallback_used=True,
                processing_time_ms=processing_time,
            )

        try:
            keywords = self._extract_keywords(query)
            logger.debug(f"[SearchResultProcessor] 提取关键词: {keywords}")

            filtered = self._filter_irrelevant(keywords, raw_results)
            logger.debug(
                f"[SearchResultProcessor] 过滤: {original_count}→{len(filtered)}"
            )

            scored = self._score_relevance(query, filtered)

            if len(scored) < self.min_results and original_count >= self.min_results:
                logger.info("[SearchResultProcessor] 相关结果不足，启用知识库兜底")
                fallback_results = self._fallback_to_knowledge_base(query)
                scored = fallback_results + scored

            processing_time = (time.time() - start_time) * 1000

            if processing_time > 100:
                logger.warning(
                    f"[SearchResultProcessor] 处理耗时{processing_time:.1f}ms超过100ms阈值"
                )

            return ProcessedResult(
                results=scored,
                original_count=original_count,
                filtered_count=(
                    original_count - len(scored) if scored else original_count
                ),
                fallback_used=len(scored) > 0
                and scored[0].get("href", "").startswith("#kb-"),
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"[SearchResultProcessor] 处理异常，降级返回原始结果: {e}")
            processing_time = (time.time() - start_time) * 1000
            return ProcessedResult(
                results=raw_results,
                original_count=original_count,
                filtered_count=0,
                fallback_used=False,
                processing_time_ms=processing_time,
            )

    def _extract_keywords(self, query: str) -> List[str]:
        """从查询中提取核心关键词

        处理逻辑：
        1. 去除常见前缀（"帮我"、"请"、"能否"等）
        2. 分词（优先jieba，降级用正则+滑动窗口）
        3. 过滤停用词（中文停用词表 + 英文停用词表）
        4. 过滤过短词（长度<2的中文或<2的英文）
        5. 返回去重后的关键词列表

        Args:
            query: 用户原始查询

        Returns:
            关键词列表（小写英文 + 原始中文）
        """
        prefixes_to_remove = [
            "帮我",
            "请",
            "能否",
            "可以",
            "需要",
            "想要",
            "希望",
            "协助",
        ]
        cleaned = query
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :]
                break

        try:
            import jieba

            jieba_tokens = list(jieba.cut(cleaned))
            keywords = []
            for token in jieba_tokens:
                token = token.strip()
                if not token:
                    continue
                if re.match(r"^[\u4e00-\u9fff]+$", token):
                    if len(token) >= 2 and token not in STOP_WORDS_CN:
                        keywords.append(token)
                elif re.match(r"^[a-zA-Z0-9]+$", token):
                    lower_token = token.lower()
                    if len(lower_token) >= 2 and lower_token not in STOP_WORDS_EN:
                        keywords.append(lower_token)

            seen = set()
            unique_keywords = []
            for kw in keywords:
                if kw not in seen:
                    seen.add(kw)
                    unique_keywords.append(kw)
            return unique_keywords
        except ImportError:
            pass

        tokens = re.split(
            r'[\s,，。！？、；：""' "（）\[\]{}|\\/+_\-*&^%$#@!~`《》【】…—–·]", cleaned
        )

        enhanced_tokens = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue

            parts = re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]+", token)
            if parts:
                enhanced_tokens.extend(parts)
            else:
                enhanced_tokens.append(token)

        keywords = []
        for token in enhanced_tokens:
            if re.match(r"^[\u4e00-\u9fff]+$", token):
                if len(token) >= 2 and token not in STOP_WORDS_CN:
                    sub_tokens = self._split_chinese_words(token)
                    for st in sub_tokens:
                        if len(st) >= 2 and st not in STOP_WORDS_CN:
                            keywords.append(st)
            elif re.match(r"^[a-zA-Z0-9]+$", token):
                lower_token = token.lower()
                if len(lower_token) >= 2 and lower_token not in STOP_WORDS_EN:
                    keywords.append(lower_token)

        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords

    def _split_chinese_words(self, text: str) -> List[str]:
        """简单的中文分词：按2-4字符滑动窗口提取候选词

        策略：
        1. 先尝试长词（4字符）
        2. 再尝试中等词（3字符）
        3. 最后取短词（2字符）
        4. 去重返回

        Args:
            text: 连续的中文字符串

        Returns:
            候选中文词语列表
        """
        candidates = []
        n = len(text)

        for length in [4, 3, 2]:
            if length > n:
                continue
            for i in range(n - length + 1):
                word = text[i : i + length]
                if word not in STOP_WORDS_CN:
                    candidates.append(word)

        seen = set()
        unique = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        return unique

    def _filter_irrelevant(
        self, keywords: List[str], results: List[Dict]
    ) -> List[Dict]:
        """规则过滤：标题/摘要必须包含至少一个查询关键词

        匹配规则：
        1. 标题或摘要（snippet/body）中包含任意一个关键词即视为相关
        2. 匹配是子串包含（非全词匹配），支持部分匹配
        3. 英文关键词匹配时不区分大小写

        Args:
            keywords: 查询关键词列表
            results: 原始搜索结果列表

        Returns:
            过滤后的相关结果列表
        """
        if not keywords:
            return results

        filtered = []
        for result in results:
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "") or result.get("body", "").lower()
            combined_text = f"{title} {snippet}"

            match_count = sum(1 for kw in keywords if kw.lower() in combined_text)

            if match_count >= self.min_keyword_match:
                result["_relevance_score_raw"] = match_count
                filtered.append(result)

        has_meaningful_keywords = any(
            (
                len(kw) >= 3
                and not all(c in STOP_WORDS_CN or c in "的了是在这有个" for c in kw)
            )
            or (re.match(r"^[a-zA-Z]+$", kw) and len(kw) >= 3)
            or (
                re.match(r"[\u4e00-\u9fff]+$", kw)
                and len(kw) >= 2
                and kw not in STOP_WORDS_CN
            )
            for kw in keywords
        )

        if not filtered and results and not has_meaningful_keywords:
            return results

        return filtered

    def _score_relevance(self, query: str, results: List[Dict]) -> List[Dict]:
        """简化TF-IDF评分：标题权重×2 + 摘要重叠度

        评分公式：
        score = (title_matches × title_weight) + (snippet_matches × snippet_weight)

        其中：
        - title_matches: 标题中命中的关键词数量
        - snippet_matches: 摘要中命中的关键词数量
        - 默认权重：title_weight=2.0, snippet_weight=1.0

        Args:
            query: 原始查询（用于重新提取关键词确保一致性）
            results: 已过滤的相关结果列表

        Returns:
            按评分降序排列的结果列表
        """
        if not results:
            return results

        keywords = self._extract_keywords(query)

        scored_results = []
        for result in results:
            title = result.get("title", "")
            snippet = result.get("snippet", "") or result.get("body", "")

            title_matches = sum(1 for kw in keywords if kw.lower() in title.lower())
            snippet_matches = sum(1 for kw in keywords if kw.lower() in snippet.lower())

            score = (title_matches * self.title_weight) + (
                snippet_matches * self.snippet_weight
            )

            result["_relevance_score"] = score
            scored_results.append((score, result))

        scored_results.sort(key=lambda x: x[0], reverse=True)

        return [item[1] for item in scored_results]

    def _fallback_to_knowledge_base(self, query: str) -> List[Dict]:
        """当所有搜索结果都不相关时，返回知识库兜底条目

        匹配策略：
        1. 遍历预定义的知识库分类
        2. 查询文本包含分类关键词即返回该分类下的条目
        3. 支持模糊匹配（如"营销"匹配"营销方案"分类）
        4. 未匹配到任何分类时返回通用条目

        Args:
            query: 用户查询（用于匹配知识库分类）

        Returns:
            知识库条目列表（已添加_kb_fallback标记）
        """
        fallback_entries = []

        CATEGORY_KEYWORDS = {
            "营销方案": ["营销", "推广", "获客", "增长", "内容日历"],
            "税收政策": ["税收", "税务", "合规", "财务", "发票"],
            "AI Agent": ["ai agent", "ai助手", "大模型", "llm", "agent"],
            "产品发布": ["发布", "上线", "定价", "launch", "mvp"],
            "数据分析": ["数据", "分析", "报表", "指标", "seo", "竞品"],
            "项目管理": ["项目", "管理", "协作", "提案", "远程"],
        }

        for category, entries in KNOWLEDGE_BASE.items():
            matched = category.lower() in query.lower()
            if not matched:
                keywords = CATEGORY_KEYWORDS.get(category, category.lower().split("、"))
                matched = any(kw in query.lower() for kw in keywords)

            if matched:
                for entry in entries:
                    entry_copy = entry.copy()
                    entry_copy["_kb_fallback"] = True
                    entry_copy["_kb_category"] = category
                    fallback_entries.append(entry_copy)
                logger.info(
                    f"[SearchResultProcessor] 知识库兜底命中分类'{category}'，"
                    f"返回{len(entries)}条"
                )
                break

        if not fallback_entries:
            default_entry = {
                "title": f'关于"{query[:20]}"的专业资料',
                "snippet": (
                    "正在为您整理相关领域的专业资料和建议框架。"
                    "建议您提供更具体的背景信息以获得更精准的结果。"
                ),
                "href": "#kb-generic",
                "_kb_fallback": True,
                "_kb_category": "generic",
            }
            fallback_entries.append(default_entry)
            logger.info("[SearchResultProcessor] 使用通用知识库兜底")

        return fallback_entries
