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
    def __init__(self):
        self.name = "web_search"
        self.description = "网页搜索MCP - 通过DuckDuckGo搜索互联网信息"
        self.capabilities = ["search", "fetch_content"]
    
    def search(self, query: str, max_results: int = 5, region: str = "cn-zh") -> List[Dict[str, Any]]:
        if not HAS_DDGS:
            logger.warning("[WebSearch] duckduckgo-search未安装，返回模拟结果")
            return [{"title": f"模拟结果: {query}", "href": "", "body": "请安装duckduckgo-search: pip3 install duckduckgo-search"}]
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
