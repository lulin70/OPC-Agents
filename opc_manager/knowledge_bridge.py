"""KnowledgeBridge — OPC-Agents 外接知识库适配层。

支持国内用户常见的知识库选择：
1. Obsidian — 本地优先，Markdown 文件夹，零成本
2. 语雀 (Yuque) — 阿里系，国内最流行的知识管理平台
3. 飞书文档 (Feishu/Lark) — 字节系，企业协作首选
4. Notion — 全球流行，国内用户也很多
5. 思源笔记 (SiYuan) — 开源本地优先，国内开发者喜爱
6. 本地文件夹 — 最简方案，直接指向一个 Markdown 文件夹

架构设计：
    KnowledgeBridge (统一接口)
        ├── ObsidianAdapter — 读取 .obsidian vault
        ├── YuqueAdapter — 语雀 API
        ├── FeishuAdapter — 飞书开放平台 API
        ├── NotionAdapter — Notion API
        ├── SiYuanAdapter — 思源笔记 API
        └── LocalFolderAdapter — 本地 Markdown 文件夹

配置（环境变量）：
    OPC_KB_ENABLED=true
    OPC_KB_TYPE=obsidian          # obsidian/yuque/feishu/notion/siyuan/local
    OPC_KB_PATH=~/my-vault        # Obsidian/本地文件夹路径
    OPC_KB_MAX_RESULTS=5          # 每次检索最大结果数
    OPC_KB_MAX_TOKENS=1500        # 知识注入 token 预算

依赖：
    pip install opc-agents[knowledge]  # 安装知识库可选依赖
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from .embedding_service import EmbeddingService, cosine_similarity

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_DEFAULT = 10
_HTTP_TIMEOUT_SHORT = 3
_HTTP_TIMEOUT_MEDIUM = 5


@dataclass
class KnowledgeEntry:
    """知识条目"""

    title: str
    content: str
    source: str  # 来源标识（文件路径/文档ID等）
    source_type: str  # obsidian/yuque/feishu/notion/siyuan/local
    tags: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeAdapter(ABC):
    """知识库适配器基类"""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[KnowledgeEntry]:
        """搜索知识库"""
        ...

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取适配器状态"""
        ...

    @abstractmethod
    def list_sources(self) -> List[str]:
        """列出知识来源"""
        ...

    def _urlopen_with_timeout(self, request, timeout: int = _HTTP_TIMEOUT_DEFAULT):
        """Open URL with configurable timeout, propagating timeout errors clearly."""
        import urllib.request
        import socket

        try:
            return urllib.request.urlopen(request, timeout=timeout)  # nosec B310
        except socket.timeout as e:
            logger.warning(
                "[KnowledgeBridge] HTTP request timed out after %ds: %s", timeout, e
            )
            raise
        except urllib.error.URLError as e:
            logger.warning("[KnowledgeBridge] HTTP request failed: %s", e)
            raise


class LocalFolderAdapter(KnowledgeAdapter):
    """本地 Markdown 文件夹适配器 — 最简方案"""

    def __init__(self, folder_path: str):
        self._path = os.path.expanduser(folder_path)
        self._index: List[Dict[str, Any]] = []
        self._embedding_svc = EmbeddingService()
        if os.path.isdir(self._path):
            self._embedding_svc.init_cache(self._path)
            self._build_index()

    def _build_index(self):
        """构建文件索引"""
        for root, dirs, files in os.walk(self._path):
            # 跳过隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fname.endswith((".md", ".txt", ".markdown")):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            content = f.read()
                        title = (
                            fname.replace(".md", "")
                            .replace(".txt", "")
                            .replace(".markdown", "")
                        )
                        # 提取标签（#tag 格式）
                        tags = re.findall(r"#(\w+)", content[:500])
                        self._index.append(
                            {
                                "title": title,
                                "content": content,
                                "path": fpath,
                                "tags": tags,
                                "size": len(content),
                            }
                        )
                    except (OSError, UnicodeDecodeError) as e:
                        logger.warning(
                            "[KnowledgeBridge] Obsidian config parsing failed: %s", e
                        )
        logger.info("[LocalFolder] 索引完成: %d 个文件", len(self._index))

        # Generate embeddings for semantic search
        if self._embedding_svc.enabled and self._index:
            logger.info(
                "[LocalFolder] Generating embeddings for %d documents...",
                len(self._index),
            )
            for entry in self._index:
                # Use title + first 500 chars for embedding
                embed_text = f"{entry['title']} {entry['content'][:500]}"
                entry["embedding"] = self._embedding_svc.embed(embed_text)
            embedded_count = sum(1 for e in self._index if e.get("embedding"))
            logger.info(
                "[LocalFolder] Embeddings generated: %d/%d",
                embedded_count,
                len(self._index),
            )

    def search(self, query: str, max_results: int = 5) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        # Get query embedding for semantic search
        query_embedding = None
        if self._embedding_svc.enabled:
            query_embedding = self._embedding_svc.embed(query)

        for entry in self._index:
            # --- Keyword score (existing logic) ---
            title_lower = entry["title"].lower()
            content_lower = entry["content"][:2000].lower()

            kw_score = 0.0
            if query_lower in title_lower:
                kw_score += 0.5
            title_terms = set(title_lower.split())
            kw_score += len(query_terms & title_terms) * 0.2
            for term in query_terms:
                if term in content_lower:
                    kw_score += 0.1
            for tag in entry.get("tags", []):
                if tag.lower() in query_terms:
                    kw_score += 0.15

            # --- Semantic score ---
            sem_score = 0.0
            if query_embedding and entry.get("embedding"):
                sem_score = cosine_similarity(query_embedding, entry["embedding"])

            # --- Hybrid score ---
            # Semantic gets 60% weight when available, keyword 40%
            if query_embedding is not None:
                score = 0.4 * min(kw_score, 1.0) + 0.6 * sem_score
            else:
                score = min(kw_score, 1.0)

            if score > 0:
                results.append(
                    KnowledgeEntry(
                        title=entry["title"],
                        content=entry["content"][:1500],
                        source=entry["path"],
                        source_type="local",
                        tags=entry.get("tags", []),
                        relevance_score=round(score, 4),
                    )
                )

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:max_results]

    def get_status(self) -> Dict[str, Any]:
        return {
            "type": "local",
            "path": self._path,
            "available": os.path.isdir(self._path),
            "file_count": len(self._index),
        }

    def list_sources(self) -> List[str]:
        return [e["path"] for e in self._index]


class ObsidianAdapter(LocalFolderAdapter):
    """Obsidian Vault 适配器 — 读取 .obsidian 配置 + Markdown 文件"""

    def __init__(self, vault_path: str):
        super().__init__(vault_path)
        self._obsidian_config = {}
        config_path = os.path.join(self._path, ".obsidian", "app.json")
        if os.path.isfile(config_path):
            try:
                import json

                with open(config_path, "r") as f:
                    self._obsidian_config = json.load(f)
            except Exception as e:
                logger.warning(
                    "[KnowledgeBridge] Obsidian config loading failed: %s", e
                )

    def search(self, query: str, max_results: int = 5) -> List[KnowledgeEntry]:
        results = super().search(query, max_results)
        for r in results:
            r.source_type = "obsidian"
        return results

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status["type"] = "obsidian"
        status["has_obsidian_config"] = bool(self._obsidian_config)
        return status


class YuqueAdapter(KnowledgeAdapter):
    """语雀 (Yuque) 适配器 — 通过语雀 API 搜索知识库

    配置:
        YUQUE_TOKEN=xxx          # 个人访问令牌
        YUQUE_REPO=xxx/yyy       # 仓库路径（用户名/仓库名）
    """

    def __init__(self, token: str = "", repo: str = ""):
        self._token = token or os.environ.get("YUQUE_TOKEN", "")
        self._repo = repo or os.environ.get("YUQUE_REPO", "")
        self._available = bool(self._token)

    def search(self, query: str, max_results: int = 5) -> List[KnowledgeEntry]:
        if not self._available:
            return []
        try:
            import urllib.request
            import json

            url = f"{os.environ.get('YUQUE_API_BASE', 'https://www.yuque.com/api/v2')}/search?q={urllib.parse.quote(query)}&limit={max_results}"
            req = urllib.request.Request(
                url,
                headers={
                    "X-Auth-Token": self._token,
                    "User-Agent": "OPC-Agents/0.2.5",
                },
            )
            with self._urlopen_with_timeout(
                req, timeout=_HTTP_TIMEOUT_DEFAULT
            ) as resp:  # nosec B310
                data = json.loads(resp.read().decode())

            results = []
            for hit in data.get("data", [])[:max_results]:
                results.append(
                    KnowledgeEntry(
                        title=hit.get("title", ""),
                        content=hit.get("highlight", hit.get("description", ""))[:1500],
                        source=f"yuque:{hit.get('slug', '')}",
                        source_type="yuque",
                        relevance_score=hit.get("score", 0.5),
                    )
                )
            return results
        except Exception as e:
            logger.warning("[Yuque] 搜索失败: %s", e)
            return []

    def get_status(self) -> Dict[str, Any]:
        return {
            "type": "yuque",
            "available": self._available,
            "repo": self._repo,
        }

    def list_sources(self) -> List[str]:
        return [f"yuque:{self._repo}"] if self._repo else []


class FeishuAdapter(KnowledgeAdapter):
    """飞书文档 (Feishu/Lark) 适配器 — 通过飞书开放平台 API

    配置:
        FEISHU_APP_ID=xxx
        FEISHU_APP_SECRET=xxx
        FEISHU_FOLDER_TOKEN=xxx   # 知识库文件夹 token
    """

    def __init__(self, app_id: str = "", app_secret: str = "", folder_token: str = ""):
        self._app_id = app_id or os.environ.get("FEISHU_APP_ID", "")
        self._app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET", "")
        self._folder_token = folder_token or os.environ.get("FEISHU_FOLDER_TOKEN", "")
        self._tenant_token = ""
        self._available = bool(self._app_id and self._app_secret)

    def _get_tenant_token(self) -> str:
        if self._tenant_token:
            return self._tenant_token
        try:
            import urllib.request
            import json

            url = os.environ.get(
                "FEISHU_AUTH_URL",
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            )
            data = json.dumps(
                {
                    "app_id": self._app_id,
                    "app_secret": self._app_secret,
                }
            ).encode()
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            with self._urlopen_with_timeout(
                req, timeout=_HTTP_TIMEOUT_DEFAULT
            ) as resp:  # nosec B310
                result = json.loads(resp.read().decode())
            self._tenant_token = result.get("tenant_access_token", "")
            return self._tenant_token
        except Exception as e:
            logger.warning("[Feishu] 获取 token 失败: %s", e)
            return ""

    def search(self, query: str, max_results: int = 5) -> List[KnowledgeEntry]:
        if not self._available:
            return []
        token = self._get_tenant_token()
        if not token:
            return []
        try:
            import urllib.request
            import json

            url = f"{os.environ.get('FEISHU_SEARCH_URL', 'https://open.feishu.cn/open-apis/suite/docs/search')}?query={urllib.parse.quote(query)}&page_size={max_results}"
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            with self._urlopen_with_timeout(
                req, timeout=_HTTP_TIMEOUT_DEFAULT
            ) as resp:  # nosec B310
                data = json.loads(resp.read().decode())

            results = []
            for item in data.get("data", {}).get("items", [])[:max_results]:
                results.append(
                    KnowledgeEntry(
                        title=item.get("title", ""),
                        content=item.get("snippet", "")[:1500],
                        source=f"feishu:{item.get('obj_token', '')}",
                        source_type="feishu",
                        relevance_score=0.5,
                    )
                )
            return results
        except Exception as e:
            logger.warning("[Feishu] 搜索失败: %s", e)
            return []

    def get_status(self) -> Dict[str, Any]:
        return {
            "type": "feishu",
            "available": self._available,
            "folder_token": self._folder_token,
        }

    def list_sources(self) -> List[str]:
        return [f"feishu:{self._folder_token}"] if self._folder_token else []


class NotionAdapter(KnowledgeAdapter):
    """Notion 适配器 — 通过 Notion API 搜索

    配置:
        NOTION_TOKEN=xxx          # Integration Token
        NOTION_DATABASE_ID=xxx    # 可选，限定搜索范围
    """

    def __init__(self, token: str = "", database_id: str = ""):
        self._token = token or os.environ.get("NOTION_TOKEN", "")
        self._database_id = database_id or os.environ.get("NOTION_DATABASE_ID", "")
        self._available = bool(self._token)

    def search(self, query: str, max_results: int = 5) -> List[KnowledgeEntry]:
        if not self._available:
            return []
        try:
            import urllib.request
            import json

            url = f"{os.environ.get('NOTION_API_BASE', 'https://api.notion.com/v1')}/search"
            body = {"query": query, "page_size": max_results}
            if self._database_id:
                body["filter"] = {"property": "object", "value": "page"}

            data = json.dumps(body).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
            )
            with self._urlopen_with_timeout(
                req, timeout=_HTTP_TIMEOUT_DEFAULT
            ) as resp:  # nosec B310
                result = json.loads(resp.read().decode())

            entries = []
            for page in result.get("results", [])[:max_results]:
                props = page.get("properties", {})
                title_prop = props.get("title", props.get("Name", {}))
                title = ""
                if isinstance(title_prop, dict):
                    title_list = title_prop.get("title", [])
                    title = title_list[0].get("plain_text", "") if title_list else ""
                elif isinstance(title_prop, list) and title_prop:
                    title = title_prop[0].get("plain_text", "")

                entries.append(
                    KnowledgeEntry(
                        title=title or page.get("id", "Untitled"),
                        content=f"Notion page: {title}",
                        source=f"notion:{page.get('id', '')}",
                        source_type="notion",
                        relevance_score=0.5,
                    )
                )
            return entries
        except Exception as e:
            logger.warning("[Notion] 搜索失败: %s", e)
            return []

    def get_status(self) -> Dict[str, Any]:
        return {
            "type": "notion",
            "available": self._available,
            "database_id": self._database_id,
        }

    def list_sources(self) -> List[str]:
        return [f"notion:{self._database_id}"] if self._database_id else []


class SiYuanAdapter(KnowledgeAdapter):
    """思源笔记 (SiYuan) 适配器 — 通过本地 API 搜索

    配置:
        SIYUAN_API_URL=http://127.0.0.1:6806  # 思源笔记本地 API
        SIYUAN_TOKEN=xxx                        # API Token
        SIYUAN_BOX=20210808180117-6v0mkcx       # 笔记本 ID
    """

    def __init__(self, api_url: str = "", token: str = "", box_id: str = ""):
        self._api_url = api_url or os.environ.get(
            "SIYUAN_API_URL", "http://127.0.0.1:6806"
        )
        self._token = token or os.environ.get("SIYUAN_TOKEN", "")
        self._box_id = box_id or os.environ.get("SIYUAN_BOX", "")
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """初始化时验证思源笔记是否可达"""
        try:
            import urllib.request
            import json

            url = f"{self._api_url}/api/system/version"
            headers = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Token {self._token}"
            req = urllib.request.Request(url, headers=headers)
            with self._urlopen_with_timeout(
                req, timeout=_HTTP_TIMEOUT_SHORT
            ) as resp:  # nosec B310
                result = json.loads(resp.read().decode())
                return result.get("code", -1) == 0
        except Exception as e:
            logger.warning("[KnowledgeBridge] SiYuan API call failed: %s", e)
            return False

    def search(self, query: str, max_results: int = 5) -> List[KnowledgeEntry]:
        try:
            import urllib.request
            import json

            url = f"{self._api_url}/api/search/fullTextSearchBlock"
            body = {"query": query, "limit": max_results}
            if self._box_id:
                body["box"] = self._box_id

            headers = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Token {self._token}"

            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, headers=headers)
            with self._urlopen_with_timeout(
                req, timeout=_HTTP_TIMEOUT_MEDIUM
            ) as resp:  # nosec B310
                result = json.loads(resp.read().decode())

            entries = []
            for block in result.get("data", {}).get("blocks", [])[:max_results]:
                entries.append(
                    KnowledgeEntry(
                        title=block.get("hPath", block.get("content", "")[:50]),
                        content=block.get("content", "")[:1500],
                        source=f"siyuan:{block.get('id', '')}",
                        source_type="siyuan",
                        relevance_score=float(block.get("score", 0.5)),
                    )
                )
            return entries
        except Exception as e:
            logger.debug("[SiYuan] 搜索失败（可能未运行）: %s", e)
            self._available = False
            return []

    def get_status(self) -> Dict[str, Any]:
        # Re-check availability on each status call
        self._available = self._check_availability()
        return {
            "type": "siyuan",
            "available": self._available,
            "api_url": self._api_url,
        }

    def list_sources(self) -> List[str]:
        return [f"siyuan:{self._box_id}"] if self._box_id else []


class KnowledgeBridge:
    """OPC-Agents 知识库桥接层 — 统一接口，支持多种知识库后端。

    使用方式：
        kb = KnowledgeBridge()
        results = kb.search("营销策略")
        prompt = kb.build_knowledge_prompt("营销策略")
    """

    def __init__(self):
        self._adapter: Optional[KnowledgeAdapter] = None
        self._enabled = False
        self._kb_type = ""

        kb_enabled = os.environ.get("OPC_KB_ENABLED", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        if not kb_enabled:
            logger.debug("[KnowledgeBridge] 知识库未启用")
            return

        self._kb_type = os.environ.get("OPC_KB_TYPE", "local").lower()
        try:
            self._adapter = self._create_adapter(self._kb_type)
            self._enabled = self._adapter is not None
            if self._enabled:
                logger.info("[KnowledgeBridge] 初始化成功: %s", self._kb_type)
        except Exception as e:
            logger.warning("[KnowledgeBridge] 初始化失败: %s", e)

    def _create_adapter(self, kb_type: str) -> Optional[KnowledgeAdapter]:
        if kb_type == "obsidian":
            path = os.environ.get("OPC_KB_PATH", "~/obsidian-vault")
            return ObsidianAdapter(path)
        elif kb_type == "local":
            path = os.environ.get("OPC_KB_PATH", "~/knowledge")
            return LocalFolderAdapter(path)
        elif kb_type == "yuque":
            return YuqueAdapter()
        elif kb_type == "feishu":
            return FeishuAdapter()
        elif kb_type == "notion":
            return NotionAdapter()
        elif kb_type == "siyuan":
            return SiYuanAdapter()
        else:
            logger.warning("[KnowledgeBridge] 未知知识库类型: %s", kb_type)
            return None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def kb_type(self) -> str:
        return self._kb_type

    def search(self, query: str, max_results: int = 0) -> List[KnowledgeEntry]:
        """搜索知识库"""
        if not self._enabled or not self._adapter:
            return []
        if max_results <= 0:
            max_results = int(os.environ.get("OPC_KB_MAX_RESULTS", "5"))
        try:
            return self._adapter.search(query, max_results)
        except Exception as e:
            logger.warning("[KnowledgeBridge] 搜索失败: %s", e)
            return []

    def build_knowledge_prompt(
        self, query: str, max_results: int = 0, max_tokens: int = 0
    ) -> str:
        """生成知识库注入的 prompt 片段"""
        if not self._enabled:
            return ""
        if max_results <= 0:
            max_results = int(os.environ.get("OPC_KB_MAX_RESULTS", "5"))
        if max_tokens <= 0:
            max_tokens = int(os.environ.get("OPC_KB_MAX_TOKENS", "1500"))

        results = self.search(query, max_results)
        if not results:
            return ""

        sections = []
        total_len = 0
        for entry in results:
            section = (
                f"### {entry.title} (来源: {entry.source_type})\n{entry.content[:800]}"
            )
            if total_len + len(section) > max_tokens:
                break
            sections.append(section)
            total_len += len(section)

        if not sections:
            return ""

        return f"[知识库参考]\n{chr(10).join(sections)}\n[/知识库参考]"

    def get_status(self) -> Dict[str, Any]:
        """获取知识库状态"""
        if not self._enabled or not self._adapter:
            return {
                "enabled": False,
                "type": self._kb_type or "none",
                "available": False,
                "source_count": 0,
            }
        status = self._adapter.get_status()
        status["enabled"] = True
        return status


# 模块级单例
_instance: Optional[KnowledgeBridge] = None


def get_knowledge_bridge() -> KnowledgeBridge:
    """获取 KnowledgeBridge 单例"""
    global _instance
    if _instance is None:
        _instance = KnowledgeBridge()
    return _instance
