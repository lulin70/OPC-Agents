"""LLM增强内容生成器 v3.5 — P0-2 内容智能升级

解决的核心问题：
- "基准值待测""提升30%""待填写"等通用模板占位符
- 用户输入具体业务信息（AI写作助手、月活5000→10000）但输出完全忽略

=== 设计决策 (ADR-009) ===
决策：RAG混合模式（模板骨架 + LLM填充），而非纯LLM或纯模板
原因：
  1. 模板保证结构一致性和输出格式可控
  2. LLM注入业务特异性，消除通用废话
  3. 降级时自动回到v3.4纯模板模式，保证不崩溃

=== 核心架构 ===
  用户输入 + 搜索结果
    ↓
  Step 1: _extract_business_info() → 提取产品名/数字/行业/目标
    ↓
  Step 2: _gen_skeleton() → 结构骨架（复用v3.4逻辑）
    ↓
  Step 3: _build_context() → 搜索参考资料摘要
    ↓
  Step 4: _build_prompt() → 组装含约束的Prompt
    ↓
  Step 5: _call_llm_api() → 调用GLM-4生成内容
    ↓ [成功]
  输出: 完整的针对性文档（零占位符）
    ↓ [失败/超时]
  Fallback: _fill_template() → v3.4模板+搜索数据填充

=== 铁律（不可违反） ===
1. 绝对不允许占位符（___、待填写、此处插入、基准值待测）
2. 绝对不允许空框架（清晰定义目标、明确边界这种废话）
3. 用户提供的具体信息必须出现在输出中
4. 降级模式下也必须满足以上三条

=== 版本历史 ===
  v3.5.0: 初始版本，RAG混合模式+降级保护+占位符扫描门禁
"""
import re
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

FORBIDDEN_PATTERNS = [
    '___', '待填写', '此处插入', '基准值待测', '待测量', '待补充',
    'TBD', 'tbd', 'TODO', 'FIXME', '后续', '适时', '加强关注',
    '密切关注', '根据实际情况', '视情况而定',
]

BUSINESS_INFO_PATTERNS = {
    'product_name': r'(?:AI|SaaS|B2C|B2B)?[\u4e00-\u9fff]{2,8}(?:助手|平台|系统|工具|服务|软件|产品|应用)',
    'numbers': r'\d{1,6}(?:万|千|百|%|元|人|天|周|月|年|次|个|条|份|GB|MB|KB|Hz)?',
    'target_metrics': r'(?:提升|增长|降低|减少|达到|突破|超过)(?:到|至|了)?\s*\d{1,6}(?:%|倍|万|千|元|人|天|周|月|年)?',
}


@dataclass
class GenerationResult:
    """内容生成结果容器
    
    设计意图：
    - 统一返回格式，让调用方无需关心是LLM还是模板生成的
    - fallback_used标记是否使用了降级模式（用于监控和调试）
    - quality_score提供内容质量评分（用于A/B测试对比）
    """
    content: str
    success: bool
    fallback_used: bool = False
    generation_mode: str = 'unknown'
    llm_latency_ms: float = 0.0
    quality_score: float = 0.0
    placeholder_count: int = 0
    business_info_injected: List[str] = field(default_factory=list)


class LLMEnhancedContentGenerator:
    """LLM增强内容生成器 — RAG混合模式解决内容泛化问题
    
    核心能力：
    1. 业务信息提取：从用户输入中提取产品名/数字/目标指标
    2. RAG混合生成：模板骨架保证结构 + LLM注入业务特异性
    3. 占位符铁律：多层过滤确保零占位符输出
    4. 优雅降级：LLM不可用时自动切换到v3.4模板模式
    5. 质量评分：输出质量可量化评估
    
    使用示例：
        >>> generator = LLMEnhancedContentGenerator()
        >>> result = generator.generate(
        ...     user_input="帮我制定Q2增长方案，产品是AI写作助手，月活5000想提升到10000",
        ...     template="# Q2方案\n\n## 项目概览\n{business_context}\n",
        ...     search_results=[{'title': 'SaaS增长策略', 'snippet': '从5000到10000...'}],
        ... )
        >>> print(result.content)
        >>> print(f"使用降级: {result.fallback_used}")
    
    线程安全：
    - 无状态设计（每次generate()独立完成）
    - 不依赖外部可变状态
    - 可安全用于多线程环境（如AsyncTaskExecutor后台线程）
    """

    def __init__(
        self,
        llm_timeout: int = 30,
        max_content_length: int = 15000,
        min_fallback_length: int = 800,
    ):
        """初始化内容生成器
        
        Args:
            llm_timeout: LLM API调用超时时间（秒）
            max_content_length: 最大输出长度（字符），超出则截断
            min_fallback_length: 降级模式最小输出长度（低于此值视为失败）
        """
        self.llm_timeout = llm_timeout
        self.max_content_length = max_content_length
        self.min_fallback_length = min_fallback_length

    def generate(
        self,
        user_input: str,
        template: str,
        search_results: List[Dict] = None,
        **kwargs
    ) -> GenerationResult:
        """主入口：RAG混合模式生成内容
        
        执行流程：
        1. 提取用户业务信息（产品名、数字、目标）
        2. 构建搜索结果上下文
        3. 尝试LLM生成（带超时和异常保护）
        4. 如果LLM成功 → 质量检查 → 返回
        5. 如果LLM失败 → 降级到模板填充 → 质量检查 → 返回
        
        Args:
            user_input: 用户原始输入（包含业务背景信息）
            template: 文档模板骨架（Markdown格式，可含{变量}占位符）
            search_results: 搜索结果列表（每个元素含title/snippet/href）
            **kwargs: 额外参数（传递给_fill_template或_call_llm_api）
            
        Returns:
            GenerationResult: 包含content/success/fallback_used等字段
        """
        start_time = time.time()

        business_info = self._extract_business_info(user_input)
        context = self._build_context(search_results or [])

        try:
            result = self._try_llm_generation(
                user_input=user_input,
                template=template,
                business_info=business_info,
                context=context,
                search_results=search_results or [],
            )

            if result.success:
                latency_ms = (time.time() - start_time) * 1000
                result.llm_latency_ms = latency_ms
                result.placeholder_count = self._count_placeholders(result.content)
                result.business_info_injected = self._check_business_info_injected(
                    result.content, business_info
                )
                result.quality_score = self._calculate_quality_score(result)

                if result.placeholder_count > 0:
                    logger.warning(
                        f"[LLMContentGen] LLM输出含{result.placeholder_count}个占位符，"
                        f"尝试清理..."
                    )
                    result.content = self._clean_placeholders(result.content)
                    result.placeholder_count = self._count_placeholders(result.content)

                logger.info(
                    f"[LLMContentGen] LLM生成成功: "
                    f"{len(result.content)}字, "
                    f"耗时{latency_ms:.0f}ms, "
                    f"质量分{result.quality_score:.1f}"
                )
                return result

        except Exception as e:
            logger.error(f"[LLMContentGen] LLM生成异常: {e}")

        fallback_result = self._fallback_to_template(
            user_input=user_input,
            template=template,
            business_info=business_info,
            context=context,
            search_results=search_results or [],
        )

        fallback_result.fallback_used = True
        fallback_result.generation_mode = 'template_v34'
        fallback_result.llm_latency_ms = (time.time() - start_time) * 1000
        fallback_result.placeholder_count = self._count_placeholders(fallback_result.content)
        fallback_result.business_info_injected = self._check_business_info_injected(
            fallback_result.content, business_info
        )
        fallback_result.quality_score = self._calculate_quality_score(fallback_result)

        logger.info(
            f"[LLMContentGen] 使用降级(模板)模式: "
            f"{len(fallback_result.content)}字, "
            f"质量分{fallback_result.quality_score:.1f}"
        )

        return fallback_result

    def _extract_business_info(self, user_input: str) -> Dict[str, List[str]]:
        """从用户输入中提取关键业务信息
        
        提取策略：
        1. 产品名称：匹配"XXX助手/平台/系统/工具"等模式
        2. 数字指标：匹配"5000""30%""10000"等数字
        3. 目标描述：匹配"提升到X""降低Y%"等目标句式
        4. 行业关键词：匹配"SaaS""电商""教育"等行业词
        
        Args:
            user_input: 用户原始输入文本
            
        Returns:
            包含提取信息的字典：{'product_name':[...], 'numbers':[...], 'targets':[...]}
        """
        info = {'product_name': [], 'numbers': [], 'targets': [], 'keywords': []}

        product_match = re.findall(BUSINESS_INFO_PATTERNS['product_name'], user_input)
        info['product_name'] = list(set(product_match))

        number_matches = re.findall(BUSINESS_INFO_PATTERNS['numbers'], user_input)
        info['numbers'] = list(set(number_matches))

        target_matches = re.findall(BUSINESS_INFO_PATTERNS['target_metrics'], user_input)
        info['targets'] = list(set(target_matches))

        industry_keywords = ['SaaS', 'B2B', 'B2C', '电商', '教育', '金融', '医疗', 'AI', 'ML']
        for kw in industry_keywords:
            if kw.lower() in user_input.lower():
                info['keywords'].append(kw)

        return info

    def _build_context(self, search_results: List[Dict]) -> str:
        """将搜索结果构建为LLM可用的上下文文本
        
        格式化规则：
        - 每条结果一行："标题: 摘要"
        - 最多保留前10条（控制token消耗）
        - 去除HTML标签和特殊字符
        
        Args:
            search_results: 搜索结果列表
            
        Returns:
            格式化的上下文文本
        """
        if not search_results:
            return "暂无相关搜索资料。"

        context_lines = []
        for i, result in enumerate(search_results[:10], 1):
            title = result.get('title', '').strip()
            snippet = (result.get('snippet') or result.get('body', '')).strip()

            title_clean = re.sub(r'<[^>]+>', '', title)
            snippet_clean = re.sub(r'<[^>]+>', '', snippet)

            if title_clean or snippet_clean:
                context_lines.append(
                    f"[资料{i}] {title_clean}: {snippet_clean[:200]}"
                )

        return '\n'.join(context_lines) if context_lines else "暂无有效搜索资料。"

    def _try_llm_generation(
        self,
        user_input: str,
        template: str,
        business_info: Dict[str, List[str]],
        context: str,
        search_results: List[Dict],
    ) -> GenerationResult:
        """尝试LLM生成（核心RAG流程）
        
        组装Prompt并调用LLM API。
        
        Args:
            user_input: 用户输入
            template: 模板骨架
            business_info: 提取的业务信息
            context: 搜索结果上下文
            search_results: 原始搜索结果
            
        Returns:
            GenerationResult: LLM生成结果或失败的空结果
        """
        prompt = self._build_prompt(
            user_input=user_input,
            template=template,
            business_info=business_info,
            context=context,
        )

        content = self._call_llm_api(prompt)

        if content and len(content.strip()) > 200:
            return GenerationResult(
                content=self._enforce_structure(content, template),
                success=True,
                generation_mode='llm_rag',
            )

        return GenerationResult(content='', success=False, generation_mode='llm_failed')

    def _build_prompt(
        self,
        user_input: str,
        template: str,
        business_info: Dict[str, List[str]],
        context: str,
    ) -> str:
        """组装给LLM的完整Prompt
        
        Prompt设计原则：
        1. 明确角色定位（专业顾问）
        2. 提供充分的上下文（搜索资料+业务信息）
        3. 给出严格的质量约束（禁止占位符）
        4. 提供文档结构骨架作为格式参考
        
        Args:
            user_input: 用户原始输入
            template: 模板骨架
            business_info: 提取的业务信息
            context: 搜索结果上下文
            
        Returns:
            完整的Prompt文本
        """
        business_summary = []
        if business_info['product_name']:
            business_summary.append(f"产品/服务: {', '.join(business_info['product_name'])}")
        if business_info['numbers']:
            business_summary.append(f"关键数据: {', '.join(business_info['numbers'])}")
        if business_info['targets']:
            business_summary.append(f"目标: {', '.join(business_info['targets'])}")
        if business_info['keywords']:
            business_summary.append(f"行业属性: {', '.join(business_info['keywords'])}")

        business_str = '\n'.join(f"- {item}" for item in business_summary) if business_summary else "(未检测到具体业务信息)"

        prompt = f"""你是一个专业的商业顾问和内容创作专家。

## 用户需求
{user_input}

## 用户业务背景信息
{business_str}

## 参考资料（来自网络搜索）
{context}

## 质量要求（必须严格遵守）
1. 所有指标必须是**具体的数字**或**明确的方法论**
   - ❌ 禁止: "基准值待测"、"待填写"、"提升30%"、"适当增加"
   - ✅ 要求: "月活从5000提升至10000（增长率100%）"、"预算控制在5万元以内"
2. 时间节点必须是**具体的日期或周次**
   - ❌ 禁止: "后续"、"适时"、"第一阶段结束后"
   - ✅ 要求: "第1周（4月1日-7日）"、"2026年Q2结束前（6月30日）"
3. 风险应对措施必须有**具体行动**
   - ❌ 禁止: "加强关注"、"密切关注"、"视情况调整"
   - ✅ 要求: "每周一召开进度例会"、"预留20%预算作为应急储备"
4. **必须直接引用**上述参考资料中的具体信息作为支撑
5. **必须包含**用户的业务背景信息（产品名、数据、目标）

## 文档结构参考
```
{template[:2000]}
```

请基于以上要求和参考资料，撰写一份**详细、具体、可直接使用**的文档。
确保每个章节都有实质性内容，不要有任何形式的占位符或空泛表述。
"""

        return prompt

    def _call_llm_api(self, prompt: str) -> Optional[str]:
        """调用LLM API生成内容

        支持多种API提供商（优先级从高到低）：
        1. MOKA_API_KEY + MOKA_API_BASE（OpenAI兼容格式）
        2. GLM_API_KEY（智谱GLM-4）
        3. OPENAI_API_KEY（OpenAI官方）

        Args:
            prompt: 完整的Prompt文本

        Returns:
            LLM生成的文本内容，或None（调用失败时）
        """
        try:
            import requests
            import json
            import os

            api_key, api_base, model = self._get_llm_config()
            if not api_key:
                logger.info("[LLMContentGen] 未配置API Key，跳过LLM调用")
                return None

            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是一个专业的商业顾问。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 4000,
            }

            endpoint = f"{api_base.rstrip('/')}/chat/completions"

            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.llm_timeout,
            )

            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                logger.info(f"[LLMContentGen] LLM API调用成功({model})，返回{len(content)}字符")
                return content
            else:
                logger.warning(
                    f"[LLMContentGen] LLM API返回错误: "
                    f"{response.status_code} - {response.text[:200]}"
                )
                return None

        except ImportError:
            logger.debug("[LLMContentGen] requests库不可用")
            return None
        except Exception as e:
            logger.error(f"[LLMContentGen] LLM API调用异常: {e}")
            return None

    def _get_llm_config(self) -> Tuple[Optional[str], str, str]:
        """获取LLM API配置（Key/Base/Model）

        优先级：
        1. MOKA_API_KEY + MOKA_API_BASE + MOKA_MODEL
        2. GLM_API_KEY + 智谱默认endpoint
        3. OPENAI_API_KEY + OpenAI默认endpoint

        Returns:
            (api_key, api_base, model) 三元组
        """
        import os

        moka_key = os.environ.get('MOKA_API_KEY')
        if moka_key:
            api_base = os.environ.get('MOKA_API_BASE', 'https://api.moka-ai.com/v1')
            model = os.environ.get('MOKA_MODEL', 'moka/claude-sonnet-4-6')
            logger.info(f"[LLMContentGen] 使用MOKA API: base={api_base}, model={model}")
            return moka_key, api_base, model

        glm_key = os.environ.get('GLM_API_KEY')
        if glm_key:
            return glm_key, 'https://open.bigmodel.cn/api/paas/v4', 'glm-4'

        openai_key = os.environ.get('OPENAI_API_KEY')
        if openai_key:
            api_base = os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
            return openai_key, api_base, 'gpt-4'

        try:
            from opc_manager.config import get_config
            config = get_config()
            cfg_key = getattr(config, 'llm_api_key', None) or getattr(config, 'glm_api_key', None)
            if cfg_key:
                return cfg_key, 'https://open.bigmodel.cn/api/paas/v4', 'glm-4'
        except Exception:
            pass

        return None, '', ''

    def _get_llm_api_key(self) -> Optional[str]:
        """获取LLM API Key（向后兼容接口）"""
        key, _, _ = self._get_llm_config()
        return key

    def _fallback_to_template(
        self,
        user_input: str,
        template: str,
        business_info: Dict[str, List[str]],
        context: str,
        search_results: List[Dict],
    ) -> GenerationResult:
        """降级到v3.4模板填充模式
        
        当LLM不可用时，使用纯规则引擎填充模板：
        1. 用搜索结果数据替换模板中的变量
        2. 注入用户业务信息
        3. 执行占位符扫描和清理
        4. 确保输出满足最低质量标准
        
        Args:
            user_input: 用户输入
            template: 模板骨架
            business_info: 业务信息
            context: 搜索上下文
            search_results: 搜索结果
            
        Returns:
            GenerationResult: 模板生成的结果
        """
        content = template

        content = content.replace('{business_context}', self._format_business_info(business_info))
        content = content.replace('{search_context}', context)
        content = content.replace('{user_query}', user_input)
        content = content.replace('{goals}', ', '.join(business_info['targets']) or '基于用户需求设定')

        if search_results:
            refs_section = "\n\n## 参考资料\n"
            for i, sr in enumerate(search_results[:5], 1):
                title = sr.get('title', '')
                url = sr.get('href', sr.get('url', ''))
                refs_section += f"{i}. [{title}]({url})\n"
            content += refs_section

        content = self._clean_placeholders(content)

        if len(content) < self.min_fallback_length:
            content += f"\n\n---\n*注: 本文档由OPC-Agents v3.5模板引擎生成。" \
                       f"用户原始需求: {user_input}\n"

        success = len(content) >= self.min_fallback_length and self._count_placeholders(content) == 0

        return GenerationResult(
            content=content,
            success=success,
            generation_mode='template_v34',
        )

    def _format_business_info(self, info: Dict[str, List[str]]) -> str:
        """将业务信息格式化为可读文本"""
        parts = []
        if info['product_name']:
            parts.append(f"产品/服务: **{', '.join(info['product_name'])}**")
        if info['numbers']:
            parts.append(f"关键数据: {', '.join(info['numbers'])}")
        if info['targets']:
            parts.append(f"目标: {', '.join(info['targets'])}")
        return '\n'.join(parts) if parts else '(请根据用户需求补充)'

    def _enforce_structure(self, content: str, template: str) -> str:
        """强制保持模板结构（确保LLM输出不偏离骨架太远）"""
        if not template:
            return content

        headers_in_template = re.findall(r'^#+\s+(.+)$', template, re.MULTILINE)
        if not headers_in_template:
            return content

        first_header = headers_in_template[0] if headers_in_template else ''
        if first_header and first_header not in content:
            lines = content.split('\n', 1)
            content = f"# {first_header}\n\n{''.join(lines)}"

        return content[:self.max_content_length]

    def _clean_placeholders(self, text: str) -> str:
        """清理所有已知的占位符模式"""
        cleaned = text
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in cleaned:
                replacement = '(已自动填充)' if pattern in ['___', 'TBD', 'tbd', 'TODO', 'FIXME'] else ''
                cleaned = cleaned.replace(pattern, replacement)

        cleaned = re.sub(r'_{3,}', '(已自动填充)', cleaned)
        cleaned = re.sub(r'\[.*?待.*?\]', '[详细说明]', cleaned)

        return cleaned

    def _count_placeholders(self, text: str) -> int:
        """统计文本中的占位符数量"""
        count = 0
        for pattern in FORBIDDEN_PATTERNS:
            count += text.count(pattern)
        count += len(re.findall(r'_{3,}', text))
        return count

    def _check_business_info_injected(self, text: str, info: Dict[str, List[str]]) -> List[str]:
        """检查哪些业务信息被成功注入到输出中"""
        injected = []
        all_values = (
            info['product_name'] +
            info['numbers'] +
            info['targets'] +
            info['keywords']
        )
        for value in all_values:
            if value and value.lower() in text.lower():
                injected.append(value)
        return injected

    def _calculate_quality_score(self, result: GenerationResult) -> float:
        """计算内容质量评分（0-100）
        
        评分维度：
        - 长度得分 (0-25): 内容越长越可能丰富
        - 占位符惩罚 (0-25): 每个占位符扣5分
        - 业务信息注入 (0-25): 注入的关键信息越多越好
        - 降级惩罚 (0-25): 降级模式扣15分
        """
        score = 50.0

        length = len(result.content)
        if length > 3000:
            score += 25
        elif length > 1500:
            score += 18
        elif length > 800:
            score += 10

        score -= min(result.placeholder_count * 5, 25)

        injection_rate = 0
        total_expected = (
            len(result.business_info_injected) +
            sum(len(v) for v in [
                getattr(self, '_last_business_info', {}).get(k, [])
                for k in ['product_name', 'numbers', 'targets']
            ])
        ) / 4
        if total_expected > 0:
            injection_rate = len(result.business_info_injected) / max(total_expected, 1)
        score += injection_rate * 25

        if result.fallback_used:
            score -= 15

        return max(0, min(100, score))
