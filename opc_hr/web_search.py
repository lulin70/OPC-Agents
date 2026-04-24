"""WebSearchMCP - DuckDuckGo 网络搜索模块

=== 职责 ===
为TaskEngineV3提供真实的互联网搜索能力。
所有"信息收集"类任务和"内容生成"类任务的参考资料都来自此模块。

=== 技术选型 ===
搜索引擎: DuckDuckGo (通过 duckduckgo-search Python库)
选择原因:
1. 免费 — 无需API Key，无调用次数限制
2. 匿名 — 不追踪用户搜索历史
3. 结构化返回 — 每条结果含title/body/href三个字段
4. 中文支持 — 支持region参数指定中文区域

=== 依赖管理 ===
- 首选: ddgs (新一代Python SDK)
- 备选: duckduckgo-search (旧版SDK，兼容性更好)
- 降级: 均未安装时返回模拟提示信息（不阻塞主流程）

=== API设计 ===
search(query, max_results) → List[Dict]    # 核心搜索
fetch_content(url) → Dict               # 网页正文提取
search_and_summarize(query) → str        # 搜索+摘要一体化

=== 性能特征 ===
- 单次搜索耗时: 5-10秒（取决于网络状况和查询复杂度）
- 最大返回条数: 由调用方指定（TaskEngineV3默认8条）
- 超时处理: DDGS内部有超时机制，异常时返回空列表

=== 与SearchCache的关系 ===
本模块是数据源层（DataSource），不负责缓存。
缓存由TaskEngineV3._search()中的SearchCache统一管理。
这种分层设计确保：更换搜索引擎不影响缓存策略。
"""
import logging
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger("OPC-Agents.WebSearch")

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        HAS_DDGS = True
    except ImportError:
        HAS_DDGS = False
        logger.warning("ddgs/duckduckgo-search未安装，网页搜索将使用模拟实现")

try:
    import requests as http_requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class WebSearchMCP:
    """网页搜索MCP (Model Context Protocol) 接口实现
    
    设计为MCP接口风格，便于未来接入MCP服务器架构。
    当前为本地直接调用模式，无需启动独立的MCP服务进程。
    
    Capabilities:
    - search: 关键词搜索，返回结构化结果列表
    - fetch_content: URL内容提取，返回纯文本
    """

    def __init__(self):
        self.name = "web_search"
        self.description = "网页搜索MCP - 通过DuckDuckGo搜索互联网信息"
        self.capabilities = ["search", "fetch_content"]

    def search(self, query: str, max_results: int = 5, region: str = "cn-zh") -> List[Dict[str, Any]]:
        """执行关键词搜索 — TaskEngineV3的主要数据来源
        
        Args:
            query: 搜索关键词（支持中英文）
            max_results: 最大返回条数（建议5-8条，过多会降低相关性）
            region: 搜索区域 ("cn-zh"=中国中文, "us-en"=美国英文, "wt-wt"=全球)
            
        Returns:
            List[Dict]: 每个元素包含:
            - title: 结果标题
            - href: 来源URL
            - body: 文本摘要（通常100-500字符）
            - source: 固定为"duckduckgo"
            
        降级策略:
        1. SDK未安装 → 返回空列表（由SearchResultProcessor知识库兜底）
        2. 网络异常 → 记录日志并返回空列表（不抛异常）
        3. 无结果 → 返回空列表（由调用方决定如何展示"未找到"状态）
        """
        if not HAS_DDGS:
            logger.warning("[WebSearch] duckduckgo-search未安装，无法执行搜索，将由知识库兜底")
            return []
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results, region=region):
                    results.append({
                        "title": r.get("title", ""),
                        "href": r.get("href", ""),
                        "body": r.get("body", ""),
                        "source": "duckduckgo"
                    })
            logger.info(f"[WebSearch] 搜索 '{query}' 返回 {len(results)} 条结果")
            return results
        except Exception as e:
            logger.error(f"[WebSearch] 搜索失败: {e}")
            return []

    def fetch_content(self, url: str, max_chars: int = 3000) -> Dict[str, Any]:
        """提取指定URL的网页正文内容
        
        用途：
        - 当搜索结果的body摘要不够用时，获取完整文章内容
        - 用于深度分析任务（如竞品分析、行业报告解读）
        
        Args:
            url: 目标网页URL
            max_chars: 最大返回字符数（防止超大页面导致内存溢出）
            
        Returns:
            Dict: 包含url/content/success/length字段
            
        技术细节：
        - 使用requests库发送HTTP GET请求
        - User-Agent伪装为Chrome浏览器（避免被反爬拦截）
        - verify=False跳过SSL证书验证（开发阶段简化配置）
        - _html_to_text()方法去除HTML标签和实体编码
        """
        if not HAS_REQUESTS:
            return {"url": url, "content": "requests库未安装", "success": False}
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            resp = http_requests.get(url, headers=headers, timeout=10, verify=False)
            resp.raise_for_status()
            html = resp.text
            text = self._html_to_text(html)
            if len(text) > max_chars:
                text = text[:max_chars] + "\n...(内容已截断)"
            return {"url": url, "content": text, "success": True, "length": len(text)}
        except Exception as e:
            logger.error(f"[WebSearch] 获取网页失败: {e}")
            return {"url": url, "content": f"获取失败: {e}", "success": False}

    def _html_to_text(self, html: str) -> str:
        """HTML到纯文本的转换器 — 轻量级实现（不依赖BeautifulSoup）
        
        处理步骤：
        1. 移除<script>标签及其内容（JavaScript代码块）
        2. 移除<style>标签及其内容（CSS样式表）
        3. 将所有HTML标签替换为空格
        4. 解码HTML实体（&nbsp; &amp; &lt; &gt; &quot;）
        5. 合并连续空行为单个换行
        
        注意：这是最小化实现。对于复杂页面（大量嵌套/div布局），
        提取效果可能不如BeautifulSoup的get_text()方法。
        如需更高质量的提取，可考虑引入bs4依赖。
        """
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()

    def search_and_summarize(self, query: str, max_results: int = 3) -> str:
        """搜索+摘要一体化便捷方法
        
        将search()的结果格式化为可读文本，
        用于不需要结构化处理的场景（如直接展示给用户）。
        
        输出格式：
        关于「query」的搜索结果：
        1. 标题
           摘要...
           链接: URL
        ...
        """
        results = self.search(query, max_results=max_results)
        if not results:
            return f"未找到关于「{query}」的相关信息"
        lines = [f"关于「{query}」的搜索结果：\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', '无标题')}")
            lines.append(f"   {r.get('body', '无摘要')}")
            if r.get('href'):
                lines.append(f"   链接: {r['href']}")
            lines.append("")
        return "\n".join(lines)


web_search_mcp = WebSearchMCP()
