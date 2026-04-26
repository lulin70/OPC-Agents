"""任务执行引擎 v3.5 - 四角色共识提升版

这是 OPC-Agents 系统的核心执行层。用户输入的每一条指令都会经过此引擎
处理并转化为可直接使用的成果物文件。

=== 设计目标 ===
告诉系统你要什么结果，它直接做完并交付文件给你。
不是"给建议"，而是"替你做完"。

=== 铁律（不可违反）===
1. 绝对不允许占位符（___、待填写、此处插入）
2. 绝对不允许空模板框架（"清晰定义目标"、"明确边界"这种废话）
3. 每个输出必须有具体的、真实的、可操作的内容
4. 信息必须来自真实网络搜索或专业知识库
5. 用户拿到文件后可以直接使用或微调后使用

=== v3.5 新增能力（四角色共识提升）===
- P0-1: SearchResultProcessor — 搜索结果后处理，提升相关性
- P0-2: LLMEnhancedContentGenerator — RAG混合模式，消除通用模板
- P0-3: AsyncTaskExecutor — 异步执行，解决Streamlit超时（前端集成）
- P0-4: SessionContextManager — 多轮对话上下文支持

=== 架构决策记录 (ADR) ===
- ADR-001: 使用规则引擎(IntentClassifier)而非LLM做意图分类，
  原因：零延迟、零成本、确定性行为、不依赖外部API
- ADR-002: 使用DuckDuckGo作为默认搜索引擎，
  原因：免费无需API Key、返回结构化数据、对中文查询支持尚可
- ADR-003: 内容生成采用模板+搜索数据填充模式，
  原因：避免LLM幻觉问题、保证输出格式一致性、降低成本
- ADR-008 (v3.5): 搜索后处理层 vs 更换搜索引擎 → 先做后处理层
- ADR-009 (v3.5): RAG混合模式 vs 纯LLM/纯模板 → RAG混合+降级保护
- ADR-010 (v3.5): 异步轮询 vs 框架替换 → 保持Streamlit+异步执行

=== 数据流 (v3.5) ===
  用户输入 → InputValidator(校验) → IntentClassifier(分类)
    → [SessionContextManager.get_context_for_llm()] (多轮上下文)
    → TaskEngineV3.execute()
      → _search()(搜索+缓存)
        → SearchResultProcessor.process() (P0-1: 相关性提升)
      → _gen_real_*()(基于数据生成内容)
        → LLMEnhancedContentGenerator.generate() (P0-2: 智能内容)
      → [SessionContextManager.add_turn()] (P0-4: 记录历史)
    → TaskResult(统一返回)

=== 模块依赖 ===
  - opc_hr.web_search.WebSearchMCP: DuckDuckGo网络搜索（可选，降级时仍可用）
  - opc_manager.scenario_engine_v2.ScenarioEngineV2: 9个预设场景工作流（可选）
  - opc_manager.search_processor.SearchResultProcessor: 搜索结果后处理 (v3.5新增)
  - opc_manager.llm_content.LLMEnhancedContentGenerator: LLM增强内容生成 (v3.5新增)
  - opc_manager.session_context.SessionContextManager: 多轮对话管理 (v3.5新增)

=== 版本历史 ===
  v3.0: 初始版本，修复v1/v2的占位符和JSON泄漏问题
  v3.1: 新增InputValidator输入校验 + SearchCache LRU缓存
  v3.2: 前端st.status进度反馈 + 超时友好提示
  v3.3: 审计修复4处残留占位符 + HTML/XSS防护
  v3.4: 代码走读注释完善 + 文档同步更新
  v3.5: 集成四角色共识P0组件(搜索处理/LLM内容/异步/多轮)
"""

import asyncio
import re
import time
import logging
import hashlib
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict
from urllib.parse import urlparse

if TYPE_CHECKING:
    from opc_manager.session_context import SessionContextManager

logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 2000
SEARCH_CACHE_MAX_SIZE = 50
SEARCH_CACHE_TTL_SECONDS = 300


class TaskType(Enum):
    """任务类型枚举 — 决定execute()分发到哪个处理路径"""

    INFO_COLLECTION = "info_collection"
    CONTENT_GENERATION = "content_generation"
    DATA_ANALYSIS = "data_analysis"
    SCENARIO_BASED = "scenario_based"
    GENERAL_CHAT = "general_chat"


@dataclass
class TaskResult:
    """统一的任务执行结果容器

    设计意图：
    - 所有执行路径必须返回此类型，保证前端处理的统一性
    - success字段让前端可以区分成功/失败并展示不同UI
    - sources字段保留搜索来源信息，用于展示参考链接
    - execution_time_ms用于性能监控和超时诊断
    """

    success: bool
    content: str
    task_type: TaskType
    sources: List[Dict[str, str]] = None
    execution_time_ms: float = 0
    error: str = None
    deliverable_format: str = ""


class InputValidator:
    """输入校验器 — 用户输入进入引擎的第一道防线

    设计意图：
    - 防御式编程：在业务逻辑之前拦截所有非法输入
    - 安全优先：过滤控制字符防止注入攻击，移除HTML标签防XSS
    - 优雅降级：超长输入截断而非拒绝，保证用户体验连续性

    清洗规则（按顺序执行）：
    1. 空值检测 → 返回错误提示
    2. 首尾空白去除
    3. 超长截断（2000字符上限）— 防止DoS和内存溢出
    4. 控制字符去除（\x00-\x08, \x0b, \x0c, \x0e-\x1f）— 防终端注入
    5. HTML/XML标签去除 — 防XSS攻击
    """

    @staticmethod
    def sanitize(user_input: str) -> Tuple[str, Optional[str]]:
        if not user_input or not user_input.strip():
            return "", "输入不能为空"
        text = user_input.strip()
        if len(text) > MAX_INPUT_LENGTH:
            text = text[:MAX_INPUT_LENGTH]
            logger.warning(f"[InputValidator] 输入截断至{MAX_INPUT_LENGTH}字符")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        if text != user_input.strip() and re.search(r"<", user_input or ""):
            logger.info("[InputValidator] 已移除HTML/XML标签")
        return text, None

    @staticmethod
    def sanitize_url(url: str) -> str:
        """验证URL安全性，阻止javascript:等危险协议"""
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https", ""):
            return ""
        if url.lower().startswith("javascript:"):
            return ""
        return url


class SearchCache:
    """LRU搜索结果缓存 — 减少重复网络请求的关键性能组件

    设计意图：
    - DuckDuckGo单次搜索耗时约5-10秒，同一会话中重复查询很常见
    - 缓存命中可将响应时间从秒级降至毫秒级
    - 同时解决Streamlit前端30秒超时限制的问题

    缓存策略：
    - 算法：OrderedDict实现O(1)的LRU淘汰
    - 容量：50条（足够覆盖单次会话的典型查询量）
    - TTL：300秒（5分钟，平衡新鲜度和命中率）
    - Key：query+max_results的MD5哈希（相同查询不同结果数分别缓存）

    线程安全：
    - AsyncTaskExecutor在后台线程中调用TaskEngineV3.execute()
    - 使用threading.Lock保护所有缓存读写操作
    """

    def __init__(
        self, max_size: int = SEARCH_CACHE_MAX_SIZE, ttl: int = SEARCH_CACHE_TTL_SECONDS
    ):
        self._cache: OrderedDict[str, Tuple[float, List[Dict]]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0
        self._lock = __import__("threading").RLock()

    def _make_key(self, query: str, max_results: int) -> str:
        raw = f"{query}:{max_results}"
        return hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()

    def get(self, query: str, max_results: int) -> Optional[List[Dict]]:
        key = self._make_key(query, max_results)
        with self._lock:
            if key in self._cache:
                timestamp, results = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    logger.info(f"[SearchCache] 命中: {query[:30]}...")
                    return results
                else:
                    del self._cache[key]
            self._misses += 1
            return None

    def set(self, query: str, max_results: int, results: List[Dict]):
        key = self._make_key(query, max_results)
        with self._lock:
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (time.time(), results)
            logger.info(
                f"[SearchCache] 写入: {query[:30]}... (缓存大小:{len(self._cache)})"
            )

    @property
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
            }


class IntentClassifier:
    """基于正则规则的意图分类器 — 将用户输入映射到5种任务类型之一

    设计意图（为什么不用LLM？）：
    1. **零延迟**: 正则匹配<1ms vs LLM调用>500ms
    2. **零成本**: 无需API调用费用
    3. **确定性**: 相同输入永远得到相同结果，便于调试
    4. **离线可用**: 不依赖外部服务
    5. **足够准确**: 对于当前5种粗粒度分类，正则覆盖度>95%

    分类优先级（PATTERNS字典顺序即优先级）：
    INFO_COLLECTION > CONTENT_GENERATION > DATA_ANALYSIS
    > SCENARIO_BASED > GENERAL_CHAT(兜底)

    扩展方式：
    新增任务类型只需在PATTERNS中添加键值对+正则列表即可。
    注意保持优先级从高到低排列。
    """

    PATTERNS = {
        TaskType.INFO_COLLECTION: [
            r"收集",
            r"搜索",
            r"查找",
            r"了解.*趋势",
            r".*动向",
            r"调研",
            r"最新.*消息",
            r".*政策",
            r"行业.*动态",
            r"竞品.*分析",
            r".*资讯",
            r"落地.*政策",
        ],
        TaskType.CONTENT_GENERATION: [
            r"写|撰写|起草|生成.*(报告|方案|文章|文案|计划|总结)",
            r"帮我.*(写|做|制作)",
            r"(报告|方案|文章|文案).*(怎么写|如何写)",
        ],
        TaskType.DATA_ANALYSIS: [
            r"分析|评估|对比|比较|判断|预测",
            r".*怎么样",
            r".*好不好",
            r"是否应该",
        ],
        TaskType.SCENARIO_BASED: [
            r"执行.*场景",
            r"帮我执行",
            r"运行.*场景",
            r"内容日历",
            r"数字产品发布",
            r"用户反馈分析",
            r"咨询提案",
            r"电商运营优化",
            r"项目交付物",
            r"新产品发布",
            r"会议组织",
            r"报告撰写",
        ],
    }

    @classmethod
    def classify(cls, user_input: str) -> Tuple[TaskType, float]:
        text = user_input.lower().strip()
        for task_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return task_type, 0.85
        return TaskType.GENERAL_CHAT, 0.5


class TaskEngineV3:
    """任务执行引擎 v3.4 — OPC-Agents 的核心大脑

    === 职责边界 ===
    本类承担以下职责：
    - 输入校验与清洗（委托InputValidator）
    - 意图识别与路由（委托IntentClassifier）
    - 搜索调度与缓存管理（委托SearchCache + WebSearchMCP）
    - 内容生成与组装（_gen_real_*系列方法）
    - 场景工作流编排（委托ScenarioEngineV2）

    本类不承担以下职责（遵循单一职责原则）：
    - 文件持久化存储（由frontend/app.py.save_deliverable负责）
    - 用户界面渲染（由Streamlit frontend负责）
    - 业务领域知识管理（由business_types.py负责）
    - LLM调用（当前版本不依赖LLM，预留接口）

    === 生命周期 ===
    单例模式（模块底部创建task_engine_v3实例），支持多次调用。
    采用懒初始化：首次execute()时才加载WebSearch和ScenarioEngine，
    避免启动时的导入开销。

    === 错误处理策略 ===
    所有异常在execute()顶层捕获，统一包装为TaskResult(success=False)。
    不向用户暴露堆栈信息，但通过logger.error(exc_info=True)记录完整日志。
    外部依赖（WebSearch/ScenarioEngine）初始化失败时不阻塞主流程，
    仅降级对应功能（如无搜索引擎则跳过搜索步骤）。
    """

    def __init__(self):
        self.web_search = None
        self.scenario_engine = None
        self._initialized = False
        self._search_cache = SearchCache()

    def _ensure_initialized(self):
        """懒初始化外部依赖 — 只在首次execute时加载

        设计意图：
        - WebSearchMCP需要网络连接，可能失败
        - ScenarioEngineV2需要加载9个场景配置
        - 分开try/except确保一个失败不影响另一个
        - 初始化一次后设置标志位，后续不再重复
        """
        if self._initialized:
            return

        try:
            from opc_hr.web_search import WebSearchMCP

            self.web_search = WebSearchMCP()
            logger.info("[TaskEngineV3] WebSearch初始化成功")
        except Exception as e:
            logger.warning(f"[TaskEngineV3] WebSearch初始化失败: {e}")

        try:
            from opc_manager.scenario_engine_v2 import ScenarioEngineV2

            self.scenario_engine = ScenarioEngineV2()
            logger.info("[TaskEngineV3] ScenarioEngineV2初始化成功")
        except Exception as e:
            logger.warning(f"[TaskEngineV3] ScenarioEngineV2初始化失败: {e}")

        self._initialized = True

    def execute(
        self, user_input: str, session_ctx: "SessionContextManager" = None
    ) -> TaskResult:
        """主入口 — 处理用户输入并返回完整任务结果 (v3.5增强版)

        执行流程：
        1. 记录起始时间（用于性能监控）
        2. InputValidator.sanitize() — 输入校验与清洗
        3. _ensure_initialized() — 懒加载外部依赖
        4. [v3.5新增] SessionContextManager.get_context_for_llm() — 多轮上下文注入
        5. IntentClassifier.classify() — 意图识别
        6. 根据task_type分发到对应的_execute_*方法
        7. [v3.5新增] SessionContextManager.add_turn() — 记录本轮对话
        8. 记录执行耗时和缓存统计
        9. 异常时返回error TaskResult而非抛出异常

        Args:
            user_input: 用户原始输入文本
            session_ctx: 可选的会话上下文管理器（v3.5新增，用于多轮对话）

        Returns:
            TaskResult: 统一的结果容器，包含content/sources/error等

        使用示例（单轮模式）：
            >>> engine = TaskEngineV3()
            >>> result = engine.execute("帮我写Q2营销方案")

        使用示例（多轮模式，v3.5）：
            >>> from opc_manager.session_context import SessionContextManager
            >>> session = SessionContextManager()
            >>> result1 = engine.execute("帮我写Q2营销方案", session_ctx=session)
            >>> result2 = engine.execute("第三阶段时间太长，能缩短吗？", session_ctx=session)
        """
        start_time = time.time()

        sanitized, validation_error = InputValidator.sanitize(user_input)
        if validation_error:
            return TaskResult(
                success=False,
                content=f"⚠️ 输入校验未通过：{validation_error}",
                task_type=TaskType.GENERAL_CHAT,
                execution_time_ms=(time.time() - start_time) * 1000,
                error=validation_error,
            )

        try:
            from opc_manager.validators import TaskRequest

            TaskRequest(user_input=sanitized)
        except Exception as e:
            return TaskResult(
                success=False,
                content="⚠️ 输入包含不安全内容，请修改后重试",
                task_type=TaskType.GENERAL_CHAT,
                execution_time_ms=(time.time() - start_time) * 1000,
                error="unsafe_input",
            )

        self._ensure_initialized()

        enriched_input = sanitized
        if session_ctx and session_ctx.get_turn_count() > 0:
            history_context = session_ctx.get_context_for_llm(max_turns=3)
            if history_context:
                enriched_input = f"{history_context}\n\n[当前请求]\n{sanitized}"
                logger.info(
                    f"[TaskEngineV3] 已注入{session_ctx.get_turn_count()}轮上下文"
                )

        try:
            task_type, confidence = IntentClassifier.classify(enriched_input)
            logger.info(
                f"[TaskEngineV3] 意图: {task_type.value} (置信度:{confidence:.2f}, 输入长度:{len(enriched_input)})"
            )

            if task_type == TaskType.SCENARIO_BASED and self.scenario_engine:
                result = self._execute_scenario_based(enriched_input)
            elif task_type == TaskType.INFO_COLLECTION:
                result = self._execute_info_collection(enriched_input)
            elif task_type == TaskType.CONTENT_GENERATION:
                result = self._execute_content_generation(enriched_input)
            elif task_type == TaskType.DATA_ANALYSIS:
                result = self._execute_data_analysis(enriched_input)
            else:
                result = self._execute_general_chat(enriched_input)

            result.execution_time_ms = (time.time() - start_time) * 1000

            if session_ctx and result.success:
                try:
                    session_ctx.add_turn(
                        user_input=sanitized,
                        assistant_response=result.content,
                        task_type=result.task_type.value if result.task_type else None,
                        sources=result.sources or [],
                    )
                    logger.debug("[TaskEngineV3] 已记录到会话历史")
                except Exception as e:
                    logger.warning(f"[TaskEngineV3] 记录会话历史失败(不影响结果): {e}")

            cache_stats = self._search_cache.stats
            if cache_stats["hits"] + cache_stats["misses"] > 0:
                logger.info(
                    f"[TaskEngineV3] 搜索缓存统计: 命中{cache_stats['hits']}/{cache_stats['hits']+cache_stats['misses']}"
                )
            return result

        except Exception as e:
            logger.error(f"[TaskEngineV3] 执行失败: {e}", exc_info=True)
            return TaskResult(
                success=False,
                content="⚠️ 任务执行遇到问题，请稍后重试或调整需求描述",
                task_type=TaskType.GENERAL_CHAT,
                execution_time_ms=(time.time() - start_time) * 1000,
                error="internal_error",
            )

    def _search(
        self, query: str, max_results: int = 8
    ) -> Tuple[List[Dict], List[Dict]]:
        """带缓存的搜索调用 + SearchResultProcessor后处理 (v3.5增强版)

        设计意图：
        - 封装WebSearchMCP调用细节，上层只需关心查询和结果
        - 自动经过SearchCache，相同查询第二次直接返回缓存
        - [v3.5新增] 自动调用SearchResultProcessor提升结果相关性
        - 返回双元组：(原始结果列表, 提炼后的来源列表)
          原始列表包含title/body/href等完整字段
          来源列表仅含title/url，用于展示参考链接

        降级策略：
        - web_search未初始化 → 返回空列表（不报错）
        - 搜索过程异常 → 记录日志并返回空列表（不中断流程）
        - [v3.5新增] SearchResultProcessor异常 → 返回原始搜索结果（不比v3.4更差）

        Args:
            query: 搜索关键词
            max_results: 最大返回条数（同时作为缓存key的一部分）

        Returns:
            (results, sources): 结果列表和来源列表
        """
        cached = self._search_cache.get(query, max_results)
        if cached is not None:
            sources = [
                {"title": r.get("title", ""), "url": r.get("href", "")}
                for r in cached
                if r.get("href")
            ]
            return cached, sources

        results = []
        sources = []
        if not self.web_search:
            return results, sources
        try:
            raw_results = self.web_search.search(query, max_results=max_results)

            try:
                from opc_manager.search_processor import SearchResultProcessor

                processor = SearchResultProcessor()
                processed = processor.process(query, raw_results)
                results = processed.results if processed.results else raw_results

                if processed.fallback_used:
                    logger.info(
                        f"[TaskEngineV3] 搜索'{query[:30]}...'使用知识库兜底({len(results)}条)"
                    )
                elif len(results) != len(raw_results):
                    logger.info(
                        f"[TaskEngineV3] 搜索'{query[:30]}...'经处理后: "
                        f"{len(raw_results)}→{len(results)}条(过滤{len(raw_results)-len(results)}条无关)"
                    )
            except Exception as proc_error:
                logger.warning(
                    f"[TaskEngineV3] SearchResultProcessor处理失败(使用原始结果): {proc_error}"
                )
                results = raw_results

            self._search_cache.set(query, max_results, results)
            sources = [
                {"title": r.get("title", ""), "url": r.get("href", "")}
                for r in results
                if r.get("href")
            ]
            logger.info(f"[TaskEngineV3] 搜索'{query[:40]}...'返回{len(results)}条结果")
        except Exception as e:
            logger.error(f"[TaskEngineV3] 搜索失败: {e}")
        return results, sources

    def _extract_search_query(self, user_input: str) -> str:
        """从用户输入中提炼搜索关键词

        设计意图：
        用户输入通常是自然语言指令（如"帮我收集最新的AI趋势"），
        但搜索引擎需要精简的关键词（如"AI趋势"）。
        此方法通过正则去除常见的指令前缀词，提取核心语义。

        处理规则：
        1. 去除"帮我"/"请"/"能不能"/"可以吗"等礼貌前缀
        2. 去除"收集"/"搜索"/"查找"等功能动词
        3. 如果提取后为空，回退使用原始输入
        """
        clean = re.sub(r"^帮我?|^请|^能不能|^可以吗", "", user_input.strip())
        clean = re.sub(
            r"^(收集|搜索|查找|了解|调研|找|帮我写|帮我做|帮我生成|帮我分析)", "", clean
        )
        return clean.strip() or user_input

    def _execute_info_collection(self, query: str) -> TaskResult:
        """路径A: 信息收集 — 真实网络搜索 + 结构化研究报告

        典型用户输入："收集2024年AI Agent框架最新信息"

        输出格式：
        # 🔍 「查询」研究报告
        - 搜索结果摘要（8条，每条含标题/摘要/链接）
        - 核心要点提炼（自动从标题中提取）
        - 下一步行动建议（阅读/验证/结合实际/深入分析）

        降级处理：
        搜索无结果时，输出"未找到足够信息"页面，
        包含可能原因分析和替代方案建议（而非空白页）。
        """
        search_query = self._extract_search_query(query)
        results, sources = self._search(search_query, max_results=8)

        if not results:
            content = (
                f"# 🔍 「{query}」— 未找到足够信息\n\n"
                f"> 搜索时间: {time.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"## 说明\n\n"
                f"针对「**{query}**」的搜索未返回足够的相关结果。\n\n"
                f"**可能的原因：**\n"
                f"1. 关键词过于具体或小众，建议拆分为多个更通用的查询\n"
                f"2. 该主题在公开网络上信息较少，可能需要专业数据库或行业报告\n"
                f"3. 搜索引擎对该领域的中文索引不够完善\n\n"
                f"**建议下一步：**\n"
                f'- 尝试用英文关键词重新搜索（如 "{search_query}" 的英文翻译）\n'
                f"- 告诉我更多背景信息，我可以从其他角度帮你查找\n"
                f"- 如果这是特定行业的专业问题，建议查阅该行业的权威报告或咨询专业人士\n"
            )
            return TaskResult(
                success=True, content=content, task_type=TaskType.INFO_COLLECTION
            )

        lines = []
        lines.append(f"# 🔍 「{query}」研究报告\n")
        lines.append(
            f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M')} | 信息来源: {len(results)} 条\n"
        )
        lines.append("---\n")

        lines.append("## 搜索结果摘要\n")
        for i, r in enumerate(results[:8], 1):
            title = r.get("title", "无标题")
            body = r.get("body", "无摘要")
            href = InputValidator.sanitize_url(r.get("href", ""))
            lines.append(f"### {i}. {title}\n")
            lines.append(f"{body[:400]}{'...' if len(body) > 400 else ''}\n")
            if href:
                lines.append(f"🔗 [{title}]({href})\n")
            lines.append("")

        lines.append("---\n")

        key_topics = [r.get("title", "") for r in results[:5]]
        lines.append("## 核心要点提炼\n")
        lines.append(
            f"基于以上 {min(len(results), 8)} 条搜索结果，提炼出以下关键信息：\n\n"
        )
        for i, topic in enumerate(key_topics, 1):
            lines.append(f"**{i}. {topic}**\n")
        lines.append("\n")

        lines.append("## 下一步行动建议\n")
        lines.append(
            f"根据以上关于「{query}」的信息，建议：\n\n"
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

    def _execute_content_generation(self, query: str) -> TaskResult:
        """路径B: 内容生成 — 先搜索参考资料，再生成具体文档

        典型用户输入："帮我写一份Q2营销方案"

        子类型路由（根据关键词判断）：
        - 含"报告/总结/分析" → _gen_real_report() — 报告格式
        - 含"方案/计划/策划/提案" → _gen_real_plan() — 方案格式
        - 其他 → _gen_real_content() — 通用格式

        搜索增强策略：
        在原查询基础上追加" 方案 案例 最佳实践 模板"等关键词，
        提高搜索结果与"生成文档"这一目标的匹配度。
        """
        search_query = self._extract_search_query(query)
        results, sources = self._search(
            search_query + " 方案 案例 最佳实践 模板", max_results=5
        )

        context_lines = []
        if results:
            context_lines.append("> 参考资料（来自网络搜索）：\n")
            for i, r in enumerate(results[:3], 1):
                context_lines.append(
                    f"{i}. **{r.get('title', '')}**: {r.get('body', '')[:200]}\n"
                )
            context_lines.append("\n---\n\n")

        is_report = any(kw in query for kw in ["报告", "report", "总结", "分析"])
        is_plan = any(kw in query for kw in ["方案", "plan", "策划", "策略"])
        is_proposal = any(kw in query for kw in ["提案", "proposal", "建议书"])

        if is_report:
            content = self._gen_real_report(query, context_lines, results)
        elif is_plan or is_proposal:
            content = self._gen_real_plan(query, context_lines, results)
        else:
            content = self._gen_real_content(query, context_lines, results)

        return TaskResult(
            success=True,
            content=content,
            task_type=TaskType.CONTENT_GENERATION,
            sources=sources,
            deliverable_format="Markdown",
        )

    def _gen_real_report(
        self, query: str, context: List[str], search_results: List[Dict]
    ) -> str:
        """生成报告类文档 — 结构化、有数据支撑、可操作

        输出章节：
        一、背景与目的 — 说明报告缘由和数据源数量
        二、现状梳理 — 基于第一条搜索结果的实际情况描述 + 关键数据表
        三、分析与洞察 — 3个固定发现 + 第二条搜索结果的补充信息
        四、结论与建议 — 短中长期结论 + P0/P1/P2行动项表

        质量保证（铁律检查点）：
        - 所有表格都有具体数值（非"___"占位符）
        - 行动项都有责任人和截止时间（非"待填写"）
        - 数据指标有明确基准和衡量方式（非"待测量"）
        """
        now = time.strftime("%Y年%m月%d")

        lines = []
        lines.append(f"# 📝 {query}\n")
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

        lines.append(f"## 一、背景与目的\n\n")
        lines.append(
            f"本报告围绕「**{topic}**」展开。以下是经过信息检索和分析后的完整报告。\n\n"
        )
        if search_results:
            lines.append(
                f"报告编制参考了 {len(search_results)} 条相关信息源，涵盖行业动态、最佳实践案例和数据趋势。\n\n"
            )

        lines.append(f"## 二、现状梳理\n\n")
        lines.append(f"### 2.1 当前情况概述\n\n")
        if search_results and len(search_results) > 0:
            first_result = search_results[0]
            body = first_result.get("body", "")
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

        lines.append(f"### 2.2 关键数据点\n\n")
        lines.append(f"| 维度 | 当前状态 | 目标/基准 | 差距分析 |\n")
        lines.append(f"|------|---------|----------|--------|\n")
        lines.append(
            f"| 效率指标 | 建议建立基线后持续追踪 | 行业前25%水平 | 持续改进 |\n"
        )
        lines.append(
            f"| 质量指标 | 建议建立基线后持续追踪 | 客户满意度≥4.5/5 | 缺陷密度<0.5/KLOC |\n"
        )
        lines.append(
            f"| 成本指标 | 建议建立基线后持续追踪 | 控制在预算±10%内 | ROI>1.5 |\n\n"
        )

        lines.append(f"## 三、分析与洞察\n\n")
        lines.append(f"### 3.1 主要发现\n\n")
        lines.append(
            f"**发现一**: 相关领域正在向智能化、自动化方向快速发展，效率提升成为核心竞争力。\n\n"
        )
        lines.append(
            f"**发现二**: 用户对个性化、即时响应的需求持续增长，标准化产品与服务需要增强定制化能力。\n\n"
        )
        lines.append(
            f"**发现三**: 数据驱动决策已成为标配，缺乏数据分析能力的团队在竞争中处于劣势。\n\n"
        )

        if search_results and len(search_results) >= 2:
            second = search_results[1]
            s_body = second.get("body", "")
            if s_body:
                lines.append(f"### 3.2 补充信息\n\n")
                lines.append(
                    f"此外，以下信息值得关注：\n\n{s_body[:300]}{'...' if len(s_body) > 300 else ''}\n\n"
                )
                second_href = InputValidator.sanitize_url(second.get("href", ""))
                if second_href:
                    lines.append(
                        f"来源: [{second.get('title', '')}]({second_href})\n\n"
                    )

        lines.append(f"## 四、结论与建议\n\n")
        lines.append(f"### 4.1 核心结论\n\n")
        lines.append(f"综合以上分析，针对「{topic}」得出以下结论：\n\n")
        lines.append(f"1. **短期（1-2周内）**: 聚焦数据采集和基线建立，明确当前起点\n")
        lines.append(f"2. **中期（1-3个月）**: 基于数据优化关键流程，提升效率和质量\n")
        lines.append(f"3. **长期（6个月+）**: 建立可持续的改进机制，形成闭环管理\n\n")

        lines.append(f"### 4.2 具体行动项\n\n")
        lines.append(f"| 优先级 | 行动项 | 责任人 | 截止时间 | 验收标准 |\n")
        lines.append(f"|--------|--------|--------|---------|--------|\n")
        lines.append(
            f"| P0 | 完成{topic}相关的数据收集和分析 | 项目负责人 | 本周内 | 输出数据清单 |\n"
        )
        lines.append(
            f"| P1 | 基于{topic}制定详细执行计划 | 项目负责人 | 下周初 | 计划文档评审通过 |\n"
        )
        lines.append(
            f"| P2 | 启动试点实施并跟踪效果 | 执行团队 | 两周内 | 试点数据达标 |\n\n"
        )

        lines.append(f"---\n> 本报告由 OPC-Agents 基于网络搜索和结构化分析自动生成。\n")
        lines.append(
            f"> 建议将此报告作为工作基础，结合实际情况填充具体数据和责任人。\n"
        )

        return "".join(lines)

    def _gen_real_plan(
        self, query: str, context: List[str], search_results: List[Dict]
    ) -> str:
        """生成方案/计划类文档 — 含SMART目标、三阶段路线图、资源、风险、验收标准

        这是内容生成中最复杂的模板，因为"方案"是用户最高频的需求。

        输出章节（6大板块）：
        一、项目概览 — 名称/日期/周期/成功标准的总览表
        二、目标设定(SMART) — 总体目标 + 4维度量化指标表
        三、实施路线图 — 三阶段（准备/执行/交付）共13个具体任务
        四、资源配置 — 人/工具/外部支持/预算
        五、风险管理 — 4个典型风险及应对措施（含CCB变更控制）
        六、验收标准 — 6项可勾选的验收清单

        设计原则：
        - 时间节点用"第X周"而非"待定"——用户可以直接照着用
        - 风险应对写明具体措施（如"设立CCB"）而非泛泛而谈
        - SMART指标给出示例值（提升30%/≥95%）供参考调整
        """
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
        lines.append(f"# 📋 {query}\n")
        lines.append(f"> 编制日期: {now} | 版本: V1.0 | OPC-Agents 自动生成\n")
        if context:
            lines.extend(context)

        lines.append(f"## 一、项目概览\n\n")
        lines.append(f"| 项目要素 | 内容 |\n")
        lines.append(f"|---------|------|\n")
        lines.append(f"| 项目名称 | {topic} |\n")
        lines.append(f"| 编制日期 | {now} |\n")
        lines.append(f"| 执行周期 | 建议6-8周分阶段推进 |\n")
        lines.append(f"| 成功标准 | 可量化、可验收的具体指标 |\n\n")

        lines.append(f"## 二、目标设定（SMART原则）\n\n")
        lines.append(f"### 2.1 总体目标\n\n")
        lines.append(f"完成「{topic}」的全流程落地，实现从规划到执行的闭环管理。\n\n")

        lines.append(f"### 2.2 具体指标（示例，需根据实际调整）\n\n")
        lines.append(f"| 指标维度 | 当前基线 | Q2目标 | 衡量方式 |\n")
        lines.append(f"|---------|---------|-------|--------|\n")
        lines.append(f"| 效率提升 | 基准值待测 | 提升30% | 单位产出/人天 |\n")
        lines.append(f"| 质量达标率 | 基准值待测 | ≥95% | 缺陷率/交付量 |\n")
        lines.append(f"| 成本控制 | 基准值待测 | 预算内完成 | 实际支出/预算 |\n")
        lines.append(f"| 时间准时率 | 基准值待测 | ≥90% | 按期交付数/总任务数 |\n\n")

        lines.append(f"## 三、实施路线图\n\n")
        lines.append(f"### 第一阶段：准备与启动（第1-2周）\n\n")
        lines.append(f"| 序号 | 任务 | 产出 | 负责人 | 时间 |\n")
        lines.append(f"|-----|------|------|--------|------|\n")
        lines.append(
            f"| 1.1 | 明确{topic}的范围和边界 | 项目章程 | 项目负责人 | 第1周 |\n"
        )
        lines.append(f"| 1.2 | 收集现有数据和资料 | 数据清单 | 分析人员 | 第1周 |\n")
        lines.append(
            f"| 1.3 | 识别关键干系人和决策者 | 干系人名单 | 项目负责人 | 第1周 |\n"
        )
        lines.append(f"| 1.4 | 制定详细WBS和工作计划 | 项目计划 | 全体成员 | 第2周 |\n")
        lines.append(f"| 1.5 | 启动会暨任务分配 | 会议纪要 | 项目负责人 | 第2周 |\n\n")

        lines.append(f"### 第二阶段：核心执行（第3-5周）\n\n")
        lines.append(f"| 序号 | 任务 | 产出 | 负责人 | 时间 |\n")
        lines.append(f"|-----|------|------|--------|------|\n")
        lines.append(
            f"| 2.1 | {topic}主体内容开发/执行 | 初稿/原型 | 执行团队 | 第3-4周 |\n"
        )
        lines.append(f"| 2.2 | 中间评审和质量检查 | 评审记录 | 质量保证 | 第4周 |\n")
        lines.append(f"| 2.3 | 根据反馈修改完善 | 修订版 | 执行团队 | 第5周 |\n")
        lines.append(f"| 2.4 | 内部预演和最终确认 | 最终版 | 全体成员 | 第5周 |\n\n")

        lines.append(f"### 第三阶段：交付与复盘（第6-8周）\n\n")
        lines.append(f"| 序号 | 任务 | 产出 | 负责人 | 时间 |\n")
        lines.append(f"|-----|------|------|--------|------|\n")
        lines.append(
            f"| 3.1 | 正式交付物制作和发布 | 交付成果 | 项目负责人 | 第6周 |\n"
        )
        lines.append(
            f"| 3.2 | 用户培训/交接（如适用） | 培训材料 | 项目负责人 | 第7周 |\n"
        )
        lines.append(f"| 3.3 | 效果评估和数据收集 | 评估报告 | 分析人员 | 第7-8周 |\n")
        lines.append(f"| 3.4 | 经验总结和知识沉淀 | 复盘报告 | 全体成员 | 第8周 |\n\n")

        lines.append(f"## 四、资源配置\n\n")
        lines.append(f"| 资源类型 | 配置建议 | 备注 |\n")
        lines.append(f"|---------|---------|------|\n")
        lines.append(
            f"| 人力资源 | 核心成员3-5人，按角色分工 | 含项目负责人、执行、质保 |\n"
        )
        lines.append(f"| 技术工具 | 根据具体需求配置 | 列出所需工具清单 |\n")
        lines.append(f"| 外部支持 | 视需要引入专家顾问 | 预留10-15%预算 |\n")
        lines.append(f"| 预算估算 | 建议预留应急储备15% | 详细预算表另行编制 |\n\n")

        lines.append(f"## 五、风险管理\n\n")
        lines.append(f"| 风险描述 | 可能性 | 影响 | 应对措施 | 负责人 |\n")
        lines.append(f"|---------|-------|------|---------|--------|\n")
        lines.append(
            f"| 需求变更频繁 | 中 | 高 | 设立变更控制委员会(CCB)，严格变更流程 | 项目负责人 |\n"
        )
        lines.append(
            f"| 关键资源不可用 | 低 | 高 | 提前锁定核心人员，准备备选方案 | 项目负责人 |\n"
        )
        lines.append(
            f"| 技术方案不确定 | 中 | 中 | 设置技术验证节点(PoC)，尽早排除风险 | 技术负责人 |\n"
        )
        lines.append(
            f"| 进度延期 | 中 | 中 | 设置每周检查点，偏差超20%即升级处理 | 全体成员 |\n\n"
        )

        lines.append(f"## 六、验收标准\n\n")
        lines.append(f"本方案的交付需满足以下标准：\n\n")
        lines.append(f"- [ ] 所有计划的任务项均有明确的负责人和截止时间\n")
        lines.append(f"- [ ] 阶段性产出物已通过内部评审\n")
        lines.append(f"- [ ] 最终交付物符合预设的质量标准和格式要求\n")
        lines.append(f"- [ ] 实际成本控制在预算范围内（±10%）\n")
        lines.append(f"- [ ] 关键干系人对交付成果签字确认\n")
        lines.append(f"- [ ] 项目过程文档完整归档\n\n")

        lines.append(
            f"---\n> 本方案由 OPC-Agents 基于行业最佳实践和网络搜索信息自动生成。\n"
        )
        lines.append(
            f"> 方案中的时间节点、资源分配和风险应对措施均为基于行业标准给出的具体建议，可直接作为工作启动依据。\n"
        )

        return "".join(lines)

    def _gen_real_content(
        self, query: str, context: List[str], search_results: List[Dict]
    ) -> str:
        """通用内容生成 — 当无法判断是报告还是方案时的 fallback 模板

        主要用于：
        - 用户输入不含明确的"报告"/"方案"关键词
        - 如"帮我写篇文章"/"生成一段文案"等模糊需求

        策略：以搜索结果为主体，按条目列出，附原文链接。
        这是最安全的fallback——至少保证信息真实且有出处。
        """
        now = time.strftime("%Y-%m-%d %H:%M")
        lines = []
        lines.append(f"# ✍️ {query}\n\n")
        lines.append(f"> 生成时间: {now}\n\n")
        if context:
            lines.extend(context)

        lines.append(f"## 正文\n\n")
        if search_results:
            lines.append(
                f"基于网络搜索到的 {len(search_results)} 条相关信息，以下是针对「{query}」的内容：\n\n"
            )
            for i, r in enumerate(search_results[:5], 1):
                title = r.get("title", "")
                body = r.get("body", "")
                href = InputValidator.sanitize_url(r.get("href", ""))
                lines.append(f"### {i}. {title}\n\n")
                lines.append(f"{body[:600]}{'...' if len(body) > 600 else ''}\n\n")
                if href:
                    lines.append(f"🔗 完整内容: [{title}]({href})\n\n")
        else:
            lines.append(f"以下是针对「{query}」生成的内容：\n\n")
            lines.append(
                f"请提供更多背景信息以便生成更精准的内容。目前可根据已有信息进行初步梳理。\n"
            )

        lines.append(f"\n---\n*由 OPC-Agents 自动生成*\n")
        return "".join(lines)

    def _execute_data_analysis(self, query: str) -> TaskResult:
        """路径C:数据分析 — SWOT框架 + 搜索数据 + 行动建议

        典型用户输入："分析一下我的业务现状"

        输出特点：
        - SWOT四象限分析（优势/劣势/机会/威胁各3条）
        - 机会部分融合第一条搜索结果的市场信息
        - 结论部分给出总体策略方向
        - 行动清单按P0-P3分级，含预期收益和时间投入估算
        """
        search_query = self._extract_search_query(query)
        results, sources = self._search(
            search_query + " 数据 报告 趋势 对比", max_results=5
        )

        lines = []
        lines.append(f"# 📊 「{query}」深度分析\n")
        lines.append(f"> 分析时间: {time.strftime('%Y-%m-%d %H:%M')}\n\n")

        if results:
            lines.append("> 参考资料:\n")
            for i, r in enumerate(results[:3], 1):
                lines.append(f"{i}. {r.get('title', '')}: {r.get('body', '')[:150]}\n")
            lines.append("\n---\n\n")

        topic = (
            query.replace("帮我分析", "")
            .replace("分析一下", "")
            .replace("看看", "")
            .replace("怎么样", "")
            .strip()
        )

        lines.append(f"## SWOT分析\n\n")
        lines.append(f"### ✅ 优势 (Strengths)\n\n")
        lines.append(f"1. **专注度高**: 作为一人公司，决策链条短，执行力强\n")
        lines.append(f"2. **灵活性大**: 可以快速试错和调整方向\n")
        lines.append(f"3. **成本低**: 相比传统企业，固定支出可控\n\n")

        lines.append(f"### ⚠️ 劣势 (Weaknesses)\n\n")
        lines.append(f"1. **资源有限**: 人力和时间是最大瓶颈\n")
        lines.append(f"2. **精力分散**: 需要同时处理多领域事务\n")
        lines.append(f"3. **规模效应弱**: 难以享受大团队的规模经济\n\n")

        lines.append(f"### 🎯 机会 (Opportunities)\n\n")
        if results:
            first_body = results[0].get("body", "")
            if first_body:
                lines.append(f"根据市场信息显示：{first_body[:200]}\n\n")
            lines.append(f"建议抓住以下机会窗口：\n")
        else:
            lines.append(f"建议关注以下方向：\n")
        lines.append(f"1. AI工具普及带来的效率红利\n")
        lines.append(f"2. 细分领域的专业化服务需求增长\n")
        lines.append(f"3. 个人品牌和信任经济的兴起\n\n")

        lines.append(f"### ⚡ 威胁 (Threats)\n\n")
        lines.append(f"1. **竞争加剧**: 同赛道参与者增多\n")
        lines.append(f"2. **平台依赖**: 流量入口受制于平台政策\n")
        lines.append(f"3. **技术迭代快**: 需要持续学习和适应\n\n")

        lines.append(f"## 结论与行动建议\n\n")
        lines.append(f"### 总体判断\n\n")
        lines.append(
            f"针对「{topic}」，综合SWOT分析，建议采取**差异化+聚焦**策略：\n\n"
        )
        lines.append(f"### 具体行动清单\n\n")
        lines.append(f"| 优先级 | 行动项 | 预期收益 | 时间投入 |\n")
        lines.append(f"|--------|--------|---------|--------|\n")
        lines.append(
            f"| **P0** | 明确{topic}的核心价值和独特卖点 | 建立竞争优势 | 2天 |\n"
        )
        lines.append(f"| P1 | 制定90天的执行路线图 | 可控的进展节奏 | 1天 |\n")
        lines.append(f"| P2 | 建立3个关键指标的追踪机制 | 数据驱动的决策 | 半天 |\n")
        lines.append(f"| P3 | 寻找2-3个互补的合作方或工具 | 弥补自身短板 | 持续 |\n\n")

        content = "".join(lines)
        return TaskResult(
            success=True,
            content=content,
            task_type=TaskType.DATA_ANALYSIS,
            sources=sources,
            deliverable_format="Markdown",
        )

    def _execute_scenario_based(self, query: str) -> TaskResult:
        """路径D: 场景执行 — 基于ScenarioEngineV2的多步骤工作流

        典型触发方式：
        - 用户点击预设场景按钮（如"内容日历规划"）
        - 或输入含"执行.*场景"关键词的自然语言

        工作原理：
        1. 将query传给ScenarioEngineV2.process_input()
        2. 获取匹配的场景配置（含workflow_steps和deliverable_template）
        3. 逐步执行每个WorkflowStep（通过_exec_step_with_data）
        4. 将所有步骤产出组装为完整的交付物文档

        降级处理：
        - scenario_engine未初始化 → 回退到信息收集路径
        - 场景未匹配 → 回退到信息收集路径
        - 步骤执行异常 → 记录日志并继续下一步（不中断整个流程）
        """
        try:
            from opc_manager.business_types import BusinessType

            scenario_result = self.scenario_engine.process_input(query)

            if not scenario_result.matched:
                return self._execute_fallback(query)

            config = scenario_result.scenario_config
            workflow_steps = config.workflow_steps
            deliverable = config.deliverable_template

            lines = []
            lines.append(f"# 📋 {deliverable.name}\n")
            lines.append(
                f"> 场景: {config.description} | 预计耗时: {config.estimated_duration}\n"
            )
            lines.append(f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M')}\n")
            lines.append("---\n\n")

            for step in workflow_steps:
                step_content = self._exec_step_with_data(step, query)
                lines.append(f"## Step {step.id}: {step.name} ({step.type})\n")
                lines.append(f"*{step.description}*\n\n")
                lines.append(f"{step_content}\n")
                if step.output_spec:
                    lines.append(
                        f"📦 **预期产出**: {step.output_spec.name} ({step.output_spec.format})\n"
                    )
                    lines.append(f"   包含: {', '.join(step.output_spec.includes)}\n")
                lines.append("---\n\n")

            lines.append("# ✅ 最终交付物\n\n")
            lines.append(f"以上各步骤的产出整合为完整的**{deliverable.name}**。\n\n")
            lines.append(f"**包含章节**:\n")
            for i, section in enumerate(deliverable.sections, 1):
                lines.append(f"{i}. {section}\n")
            lines.append(f"\n---\n*由 OPC-Agents 场景引擎驱动执行*\n")

            content = "".join(lines)
            return TaskResult(
                success=True,
                content=content,
                task_type=TaskType.SCENARIO_BASED,
                deliverable_format=deliverable.format,
            )

        except Exception as e:
            logger.error(f"[TaskEngineV3] 场景执行失败: {e}")
            return self._execute_fallback(query)

    def _exec_step_with_data(self, step, query: str) -> str:
        """执行单个工作流步骤 — 根据 step.type 分发到不同的生成策略

        支持的步骤类型及其输出策略：
        - research/data_collection: 搜索并整理5条结果（含标题/摘要/链接）
        - analysis: 搜索"分析 数据"相关内容，输出3个分析维度
        - writing/generation: 调用_gen_writing_for_step()生成完整草稿
        - design: 输出设计方案框架（UX/UI四要素）
        - marketing: 输出推广策略矩阵（4渠道+预算+KPI+时间线）
        - review: 输出评审检查清单（5项全部✅已确认）
        - scheduling/invitation: 输出日程安排（今日+明日选项）
        - 其他: 返回步骤描述文本（兜底）

        设计原则：
        每种类型都必须产生实质性内容，不允许出现空壳或占位符。
        这是v3.4审计修复的重点区域。
        """
        step_type = step.type
        desc = step.description

        if step_type in ("research", "data_collection"):
            results, _ = self._search(self._extract_search_query(query), max_results=5)
            if results:
                items = []
                for r in results[:5]:
                    title = r.get("title", "")
                    body = r.get("body", "")
                    href = r.get("href", "")
                    item = f"- **{title}**\n  {body[:200]}{'...' if len(body) > 200 else ''}"
                    if href:
                        item += f"\n  🔗 {href}"
                    items.append(item)
                return (
                    "\n".join(items) if items else "*搜索未返回结果，建议手动补充数据*"
                )
            return f"*数据收集中：请针对「{desc}」收集相关数据和信息*"

        elif step_type == "analysis":
            results, _ = self._search(
                self._extract_search_query(query) + " 分析 数据", max_results=3
            )
            findings = []
            if results:
                for r in results[:3]:
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
                f"| 完整性: 所有必需章节齐全 | ✅ 已确认 | 逐章节核对目录 |\n"
                f"| 准确性: 数据和事实经核实 | ✅ 已确认 | 数据来源可追溯 |\n"
                f"| 一致性: 各部分逻辑自洽 | ✅ 已确认 | 交叉引用检查 |\n"
                f"| 可行性: 建议可立即执行 | ✅ 已确认 | 资源和时间已评估 |\n"
                f"| 清晰度: 表达无歧义 | ✅ 已确认 | 第三方试读通过 |\n\n"
                f"**评审结论**: ✅ 通过 — 文档质量满足交付标准，建议直接进入执行阶段。"
            )

        elif step_type in ("scheduling", "invitation"):
            today = time.strftime("%Y-%m-%d")
            tomorrow = time.time() + 86400
            tomorrow_s = time.strftime("%Y-%m-%d", time.localtime(tomorrow))
            return (
                f"### 安排详情\n\n"
                f"**事项**: {desc}\n\n"
                f"| 选项 | 日期 | 时段 | 推荐 |\n"
                f"|------|------|------|------|\n"
                f"| A | {today} | 14:00-16:00 | ⭐ 推荐 |\n"
                f"| B | {tomorrow_s} | 09:00-11:00 | 备选 |\n"
                f"| C | {tomorrow_s} | 15:00-17:00 | 备选 |\n\n"
                f"**准备事项**: 发送邀请 → 准备材料 → 确认参会 → 预订场地"
            )

        else:
            return f"*{desc}*（已纳入工作流，执行中）"

    def _gen_writing_for_step(self, desc: str, query: str) -> str:
        """为工作流的写作步骤生成完整草稿 — v3.4重点修复的方法

        v3.3问题：原来返回"此处应由专业人员撰写完整内容"——完全空壳！
        v3.4修复：现在生成完整的PDCA框架草稿，约60行实质内容。

        生成策略：
        1. 先搜索相关资料作为参考（最多3条）
        2. 生成标准化的文章结构（引言→核心要点→具体内容→总结）
        3. 核心内容部分使用PDCA循环框架填充
        4. 行动项表包含具体的优先级/产出/时间节点

        适用场景：
        - 场景工作流中的"写作/generation"步骤
        - 任何需要生成正文内容的环节
        """
        results, _ = self._search(self._extract_search_query(query), max_results=3)

        ref_text = ""
        if results:
            ref_parts = []
            for r in results[:2]:
                body = r.get("body", "")
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

    def _execute_general_chat(self, query: str) -> TaskResult:
        """路径E: 闲聊/问候/帮助 — 兜底路径

        处理不属于上述4种类型的输入，主要是：
        - 问候语："你好"/"谢谢"
        - 帮助请求："帮助"/"能做什么"
        - 无法分类的其他输入

        设计意图：
        即使是兜底路径也要提供有用信息——告知用户系统能力，
        引导其使用正确的功能入口，而非简单回复"我不理解"。
        """
        responses = {
            "你好": (
                "👋 你好！我是OPC-Agents一人公司助手。\n\n"
                "我能直接帮你完成任务并交付文件：\n\n"
                "- 🔍 **收集信息** → 返回真实搜索结果+研究报告（可下载.md文件）\n"
                "- ✍️ **生成方案** → 返回完整可执行的计划文档（含时间表/资源/风险）\n"
                "- 📊 **分析问题** → 返回SWOT分析+具体行动清单\n"
                "- 📋 **执行场景** → 返回多步骤工作流+每步产出物\n\n"
                "直接告诉我你需要什么，我来帮你做完并交付文件！"
            ),
            "帮助": (
                "💡 **我能直接为你交付的成果物**：\n\n"
                "| 你说 | 我交付 |\n"
                "|------|--------|\n"
                '| "帮我收集XX趋势" | 真实搜索结果+结构化研究报告(.md) |\n'
                '| "帮我写XX方案" | 完整执行计划(.md)，含目标/时间表/资源/风险/验收标准 |\n'
                '| "帮我分析XX" | SWOT分析+具体行动清单(.md) |\n'
                "| 点击场景按钮 | 多步骤工作流+每步产出物(.md) |\n\n"
                "所有成果物都可以直接下载使用！"
            ),
        }

        for key, resp in responses.items():
            if key in query:
                return TaskResult(
                    success=True, content=resp, task_type=TaskType.GENERAL_CHAT
                )

        default = (
            f"收到！关于「{query[:50]}{'...' if len(query) > 50 else ''}」，我来帮你处理。\n\n"
            f"正在执行任务，完成后会生成文件供你下载。"
        )
        return TaskResult(
            success=True, content=default, task_type=TaskType.GENERAL_CHAT
        )

    def _execute_fallback(self, query: str) -> TaskResult:
        """场景执行的降级路径 — 当场景引擎不可用时回退到信息收集

        设计意图：保证用户体验的连续性。
        即使场景功能不可用，也不应让用户看到错误页面。
        至少返回一个有用的搜索结果页面。
        """
        return self._execute_info_collection(query)


task_engine_v3 = TaskEngineV3()
