"""
OPC-Agents 网页搜索技能

功能：
- 支持多搜索引擎（百度/谷歌/必应）
- 支持高级搜索语法
- 结果去重和排序
- 支持中文优化
"""

import requests
from typing import Dict, List, Optional
from urllib.parse import quote_plus
import re
from bs4 import BeautifulSoup


class WebSearchSkill:
    """网页搜索技能"""
    
    # 技能元数据
    METADATA = {
        'name': 'web_search',
        'version': '1.0.0',
        'description': '多引擎网页搜索技能，支持百度/谷歌/必应',
        'author': 'OPC-Agents Team',
        'category': 'information_retrieval',
        'tags': ['搜索', '网页', '信息检索', '中文'],
        'permissions': ['network_access'],
    }
    
    # 搜索引擎配置
    SEARCH_ENGINES = {
        'baidu': {
            'url': 'https://www.baidu.com/s',
            'params': {'wd': '{query}', 'rn': '{count}'},
            'result_selector': 'div.result.c-container',
            'title_selector': 'h3.t a',
            'snippet_selector': 'div.c-abstract',
            'link_selector': 'h3.t a',
        },
        'google': {
            'url': 'https://www.google.com/search',
            'params': {'q': '{query}', 'num': '{count}'},
            'result_selector': 'div.g',
            'title_selector': 'h3 a',
            'snippet_selector': 'div.VwiC3b',
            'link_selector': 'a[href*="url?q="]',
        },
        'bing': {
            'url': 'https://www.bing.com/search',
            'params': {'q': '{query}', 'count': '{count}'},
            'result_selector': 'li.b_algo',
            'title_selector': 'h2 a',
            'snippet_selector': 'div.b_caption p',
            'link_selector': 'h2 a',
        },
        'duckduckgo': {
            'url': 'https://html.duckduckgo.com/html/',
            'params': {'q': '{query}'},
            'result_selector': 'div.results_links',
            'title_selector': 'a.result__a',
            'snippet_selector': 'a.result__snippet',
            'link_selector': 'a.result__url',
        },
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化搜索技能
        
        Args:
            config: 配置字典，包含：
                - default_engine: 默认搜索引擎 (default: 'baidu')
                - max_results: 最大结果数 (default: 10)
                - timeout: 请求超时时间 (default: 10)
                - language: 语言偏好 (default: 'zh-CN')
        """
        self.config = config or {}
        self.default_engine = self.config.get('default_engine', 'baidu')
        self.max_results = self.config.get('max_results', 10)
        self.timeout = self.config.get('timeout', 30)  # 增加超时时间到 30 秒
        self.language = self.config.get('language', 'zh-CN')
        
        # 设置请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': self.language,
        }
    
    def execute(self, 
                query: str,
                engine: Optional[str] = None,
                max_results: Optional[int] = None,
                advanced: bool = False,
                **kwargs) -> Dict:
        """
        执行网页搜索
        
        Args:
            query: 搜索关键词
            engine: 搜索引擎（baidu/google/bing/duckduckgo）
            max_results: 最大结果数
            advanced: 是否使用高级搜索语法
            **kwargs: 其他参数
            
        Returns:
            dict: {
                'success': bool,
                'results': List[Dict],
                'total': int,
                'query': str,
                'engine': str,
                'error': str (if failed)
            }
        """
        try:
            # 参数处理
            engine = engine or self.default_engine
            max_results = max_results or self.max_results
            
            if engine not in self.SEARCH_ENGINES:
                return {
                    'success': False,
                    'error': f'不支持的搜索引擎：{engine}',
                    'available_engines': list(self.SEARCH_ENGINES.keys())
                }
            
            # 高级搜索语法处理
            if advanced:
                query = self._process_advanced_query(query, **kwargs)
            
            # 执行搜索
            results = self._search(engine, query, max_results)
            
            # 去重和排序
            results = self._deduplicate_and_sort(results, query)
            
            # 限制结果数量
            results = results[:max_results]
            
            return {
                'success': True,
                'results': results,
                'total': len(results),
                'query': query,
                'engine': engine,
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def _search(self, engine: str, query: str, max_results: int) -> List[Dict]:
        """
        执行搜索请求
        
        Args:
            engine: 搜索引擎名称
            query: 搜索词
            max_results: 最大结果数
            
        Returns:
            List[Dict]: 搜索结果列表
        """
        engine_config = self.SEARCH_ENGINES[engine]
        
        # 构建 URL 和参数
        url = engine_config['url']
        params = {}
        for key, value in engine_config['params'].items():
            params[key] = value.format(query=query, count=max_results)
        
        # 发送请求
        response = requests.get(
            url,
            params=params,
            headers=self.headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        # 解析结果
        results = self._parse_results(response.text, engine_config)
        
        return results
    
    def _parse_results(self, html: str, engine_config: Dict) -> List[Dict]:
        """
        解析搜索结果
        
        Args:
            html: HTML 内容
            engine_config: 搜索引擎配置
            
        Returns:
            List[Dict]: 解析后的结果
        """
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # 查找所有结果项
        result_items = soup.select(engine_config['result_selector'])
        
        for item in result_items[:self.max_results]:
            try:
                # 提取标题
                title_elem = item.select_one(engine_config['title_selector'])
                title = title_elem.get_text(strip=True) if title_elem else ''
                
                # 提取链接
                link_elem = item.select_one(engine_config['link_selector'])
                link = link_elem.get('href', '') if link_elem else ''
                
                # 提取摘要
                snippet_elem = item.select_one(engine_config['snippet_selector'])
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                
                # 清理链接（处理 Google 的重定向链接）
                if 'url?q=' in link:
                    link = link.split('url?q=')[1].split('&')[0]
                
                if title and link:
                    results.append({
                        'title': title,
                        'link': link,
                        'snippet': snippet,
                        'source': engine_config.get('name', 'unknown'),
                    })
            except Exception as e:
                # 跳过解析失败的项
                continue
        
        return results
    
    def _process_advanced_query(self, query: str, **kwargs) -> str:
        """
        处理高级搜索语法
        
        支持的高级语法：
        - site: 限定网站
        - filetype: 限定文件类型
        - intitle: 标题包含
        - inurl: URL 包含
        - - 排除词
        - "" 精确匹配
        - time: 时间范围
        
        Args:
            query: 原始搜索词
            **kwargs: 高级搜索参数
            
        Returns:
            str: 处理后的高级搜索查询
        """
        advanced_query = query
        
        # 限定网站
        if 'site' in kwargs:
            advanced_query += f' site:{kwargs["site"]}'
        
        # 限定文件类型
        if 'filetype' in kwargs:
            advanced_query += f' filetype:{kwargs["filetype"]}'
        
        # 标题包含
        if 'intitle' in kwargs:
            advanced_query += f' intitle:{kwargs["intitle"]}'
        
        # 排除词
        if 'exclude' in kwargs:
            exclude_words = kwargs['exclude'] if isinstance(kwargs['exclude'], list) else [kwargs['exclude']]
            for word in exclude_words:
                advanced_query += f' -{word}'
        
        # 精确匹配
        if 'exact' in kwargs:
            advanced_query = f'"{advanced_query}"'
        
        # 时间范围
        if 'time' in kwargs:
            # DuckDuckGo 时间语法
            if self.default_engine == 'duckduckgo':
                advanced_query += f' df:{kwargs["time"]}'
        
        return advanced_query
    
    def _deduplicate_and_sort(self, results: List[Dict], query: str) -> List[Dict]:
        """
        去重和排序
        
        Args:
            results: 搜索结果列表
            query: 搜索词
            
        Returns:
            List[Dict]: 去重排序后的结果
        """
        # 基于链接去重
        seen_links = set()
        unique_results = []
        
        for result in results:
            link = result.get('link', '')
            if link not in seen_links:
                seen_links.add(link)
                unique_results.append(result)
        
        # 基于相关性排序
        # 简单实现：基于标题和摘要中包含搜索词的数量
        def relevance_score(result):
            score = 0
            text = (result.get('title', '') + ' ' + result.get('snippet', '')).lower()
            query_words = query.lower().split()
            
            for word in query_words:
                if len(word) > 2:  # 忽略太短的词
                    score += text.count(word)
            
            return score
        
        sorted_results = sorted(
            unique_results,
            key=relevance_score,
            reverse=True
        )
        
        return sorted_results
    
    def get_schema(self) -> Dict:
        """返回输入输出 schema"""
        return {
            'input': {
                'query': {'type': 'string', 'required': True, 'description': '搜索关键词'},
                'engine': {'type': 'string', 'required': False, 'description': '搜索引擎：baidu/google/bing/duckduckgo'},
                'max_results': {'type': 'integer', 'required': False, 'description': '最大结果数'},
                'advanced': {'type': 'boolean', 'required': False, 'description': '是否使用高级搜索'},
                'site': {'type': 'string', 'required': False, 'description': '限定网站'},
                'filetype': {'type': 'string', 'required': False, 'description': '限定文件类型'},
                'exclude': {'type': 'array', 'required': False, 'description': '排除的词'},
            },
            'output': {
                'success': {'type': 'boolean'},
                'results': {'type': 'array', 'items': {
                    'title': 'string',
                    'link': 'string',
                    'snippet': 'string',
                    'source': 'string',
                }},
                'total': {'type': 'integer'},
                'query': {'type': 'string'},
                'engine': {'type': 'string'},
                'error': {'type': 'string'},
            }
        }


# 便捷函数
def search_web(query: str, **kwargs) -> Dict:
    """
    便捷搜索函数
    
    Args:
        query: 搜索关键词
        **kwargs: 其他参数
        
    Returns:
        Dict: 搜索结果
    """
    skill = WebSearchSkill()
    return skill.execute(query, **kwargs)


# 测试
if __name__ == '__main__':
    import time
    
    # 简单测试 - 使用 DuckDuckGo（更容易解析）
    print("=" * 60)
    print("测试网页搜索技能 - DuckDuckGo")
    print("=" * 60)
    
    skill = WebSearchSkill({'default_engine': 'duckduckgo', 'max_results': 5})
    
    # 基础搜索
    result = skill.execute('AI Agent 发展趋势')
    print(f"\n搜索成功：{result.get('success', False)}")
    
    if result.get('success') and result.get('results'):
        print(f"结果数量：{result.get('total', 0)}")
        print(f"搜索引擎：{result.get('engine', 'unknown')}")
        print("\n前 3 个结果：")
        for i, r in enumerate(result['results'][:3], 1):
            print(f"\n{i}. {r['title']}")
            print(f"   链接：{r['link']}")
            print(f"   摘要：{r['snippet'][:100]}...")
    elif not result.get('success'):
        print(f"错误：{result.get('error', '未知错误')}")
        print("提示：可能是网络问题或搜索引擎反爬虫机制，建议稍后重试或切换搜索引擎")
    
    # 高级搜索
    print("\n" + "=" * 60)
    print("测试高级搜索")
    print("=" * 60)
    
    time.sleep(1)  # 避免请求太快
    result = skill.execute(
        'AI Agent',
        advanced=True,
        site='github.com'
    )
    
    if result.get('success'):
        print(f"\n高级搜索结果：{result.get('total', 0)} 条")
        if result.get('results'):
            print(f"限定网站：github.com")
            for i, r in enumerate(result['results'][:2], 1):
                print(f"\n{i}. {r['title']}")
                print(f"   链接：{r['link']}")
    else:
        print(f"高级搜索失败：{result.get('error', '未知错误')}")
