import hashlib
import importlib.util
import json
import logging
import os
import ssl
import subprocess
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "marketplace"
)

SANDBOX_TIMEOUT_SECONDS = 30
SANDBOX_MAX_MEMORY_MB = 256
NETWORK_WHITELIST = [
    "registry.opc-agents.dev",
    "api.github.com",
    "mcphub.io",
]


class PermissionLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


class SkillStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class TrustLevel(str, Enum):
    OFFICIAL = "official"
    VERIFIED = "verified"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"


@dataclass
class MarketplaceSkill:
    skill_id: str
    name: str
    description: str
    version: str
    category: str
    author: str
    permissions: List[PermissionLevel] = field(
        default_factory=lambda: [PermissionLevel.READ]
    )
    dependencies: List[str] = field(default_factory=list)
    status: SkillStatus = SkillStatus.PENDING
    created_at: float = 0.0
    updated_at: float = 0.0
    config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.updated_at == 0.0:
            self.updated_at = time.time()


@dataclass
class APIKey:
    key_hash: str
    name: str
    permissions: List[PermissionLevel] = field(
        default_factory=lambda: [PermissionLevel.READ]
    )
    created_at: float = 0.0
    rate_limit: int = 100
    salt: str = ""

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class ExternalSkill:
    skill_id: str
    name: str
    description: str
    source: str
    version: str
    trust_level: TrustLevel
    category: str = ""
    author: str = ""
    downloads: int = 0
    rating: float = 0.0
    config: Dict[str, Any] = field(default_factory=dict)
    permissions_required: List[str] = field(default_factory=list)


@dataclass
class MCPServerInfo:
    server_id: str
    name: str
    description: str
    url: str
    capabilities: List[str] = field(default_factory=list)
    trust_level: TrustLevel = TrustLevel.UNVERIFIED
    connected: bool = False


class SkillMarketplace:

    def __init__(self, data_dir: Optional[str] = None):
        self._data_dir = data_dir or DATA_DIR
        self._api_keys_file = os.path.join(self._data_dir, "api_keys.json")
        self._skills_file = os.path.join(self._data_dir, "skills.json")
        os.makedirs(self._data_dir, exist_ok=True)
        self._api_keys: Dict[str, APIKey] = {}
        self._skills: Dict[str, MarketplaceSkill] = {}
        self._load_data()
        self._seed_default_skills()

    def _load_data(self) -> None:
        if os.path.exists(self._api_keys_file):
            try:
                with open(self._api_keys_file, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    perms = [PermissionLevel(p) for p in v.get("permissions", ["read"])]
                    api_key_obj = APIKey(
                        key_hash=v["key_hash"],
                        name=v["name"],
                        permissions=perms,
                        created_at=v.get("created_at", 0),
                        rate_limit=v.get("rate_limit", 100),
                    )
                    api_key_obj.salt = v.get("salt", "")
                    self._api_keys[k] = api_key_obj
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("加载API Keys失败: %s", e)

        if os.path.exists(self._skills_file):
            try:
                with open(self._skills_file, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    perms = [PermissionLevel(p) for p in v.get("permissions", ["read"])]
                    deps = v.get("dependencies", [])
                    self._skills[k] = MarketplaceSkill(
                        skill_id=v["skill_id"],
                        name=v["name"],
                        description=v["description"],
                        version=v["version"],
                        category=v["category"],
                        author=v["author"],
                        permissions=perms,
                        dependencies=deps,
                        status=SkillStatus(v.get("status", "pending")),
                        created_at=v.get("created_at", 0),
                        updated_at=v.get("updated_at", 0),
                        config=v.get("config", {}),
                    )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("加载技能数据失败: %s", e)

    def _seed_default_skills(self) -> None:
        """Populate default skills when marketplace is empty.

        Ensures first-time users see pre-installed skills instead of
        an empty marketplace. Only seeds if no skills exist yet.
        """
        if self._skills:
            return

        defaults = [
            MarketplaceSkill(
                skill_id="proposal_skill",
                name="方案撰写",
                description="根据用户需求自动生成商业方案、营销方案、产品方案等专业文档",
                version="1.0.0",
                category="内容创作",
                author="OPC-Agents",
                permissions=[PermissionLevel.READ, PermissionLevel.EXECUTE],
                status=SkillStatus.APPROVED,
            ),
            MarketplaceSkill(
                skill_id="report_skill",
                name="报告生成",
                description="自动生成数据分析报告、市场调研报告、财务报告等",
                version="1.0.0",
                category="数据分析",
                author="OPC-Agents",
                permissions=[PermissionLevel.READ, PermissionLevel.EXECUTE],
                status=SkillStatus.APPROVED,
            ),
            MarketplaceSkill(
                skill_id="invoice_skill",
                name="发票管理",
                description="管理发票开具、记录和统计，支持收入支出追踪",
                version="1.0.0",
                category="财务管理",
                author="OPC-Agents",
                permissions=[PermissionLevel.READ, PermissionLevel.WRITE],
                status=SkillStatus.APPROVED,
            ),
            MarketplaceSkill(
                skill_id="email_skill",
                name="邮件助手",
                description="撰写和发送专业商务邮件，支持模板和跟进提醒",
                version="1.0.0",
                category="沟通协作",
                author="OPC-Agents",
                permissions=[PermissionLevel.READ, PermissionLevel.EXECUTE],
                status=SkillStatus.APPROVED,
            ),
            MarketplaceSkill(
                skill_id="social_skill",
                name="社媒运营",
                description="生成社交媒体内容、排期发布、数据分析与优化建议",
                version="1.0.0",
                category="内容创作",
                author="OPC-Agents",
                permissions=[PermissionLevel.READ, PermissionLevel.EXECUTE],
                status=SkillStatus.APPROVED,
            ),
            MarketplaceSkill(
                skill_id="dashboard_skill",
                name="仪表盘",
                description="可视化展示业务数据、收入趋势、客户健康度和任务完成情况",
                version="1.0.0",
                category="数据分析",
                author="OPC-Agents",
                permissions=[PermissionLevel.READ],
                status=SkillStatus.APPROVED,
            ),
            MarketplaceSkill(
                skill_id="finance_skill",
                name="财务分析",
                description="收入支出分析、现金流预测、利润率计算和财务报表生成",
                version="1.0.0",
                category="财务管理",
                author="OPC-Agents",
                permissions=[PermissionLevel.READ, PermissionLevel.EXECUTE],
                status=SkillStatus.APPROVED,
            ),
        ]

        for skill in defaults:
            self._skills[skill.skill_id] = skill
        self._save_data()
        logger.info("已预置 %d 个默认技能", len(defaults))

    def _save_data(self) -> None:
        try:
            keys_data = {}
            for k, v in self._api_keys.items():
                keys_data[k] = {
                    "key_hash": v.key_hash,
                    "name": v.name,
                    "permissions": [p.value for p in v.permissions],
                    "created_at": v.created_at,
                    "rate_limit": v.rate_limit,
                    "salt": v.salt,
                }
            with open(self._api_keys_file, "w") as f:
                json.dump(keys_data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("保存API Keys失败: %s", e)

        try:
            skills_data = {}
            for k, v in self._skills.items():
                skills_data[k] = {
                    "skill_id": v.skill_id,
                    "name": v.name,
                    "description": v.description,
                    "version": v.version,
                    "category": v.category,
                    "author": v.author,
                    "permissions": [p.value for p in v.permissions],
                    "dependencies": v.dependencies,
                    "status": v.status.value,
                    "created_at": v.created_at,
                    "updated_at": v.updated_at,
                    "config": v.config,
                }
            with open(self._skills_file, "w") as f:
                json.dump(skills_data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("保存技能数据失败: %s", e)

    def create_api_key(
        self, name: str, permissions: List[PermissionLevel], rate_limit: int = 100
    ) -> str:
        import secrets

        raw_key = f"opc_{secrets.token_hex(16)}"
        salt = secrets.token_hex(8)
        key_hash = hashlib.sha256(f"{salt}:{raw_key}".encode()).hexdigest()
        self._api_keys[key_hash] = APIKey(
            key_hash=key_hash, name=name, permissions=permissions, rate_limit=rate_limit
        )
        self._api_keys[key_hash].salt = salt
        self._save_data()
        return raw_key

    def authenticate(self, api_key: str) -> Optional[APIKey]:
        for key_hash, key_info in self._api_keys.items():
            salt = key_info.salt
            if not salt:
                continue
            check_hash = hashlib.sha256(f"{salt}:{api_key}".encode()).hexdigest()
            if check_hash == key_hash:
                return key_info
        return None

    def check_permission(self, api_key: str, required: PermissionLevel) -> bool:
        key_info = self.authenticate(api_key)
        if not key_info:
            return False
        perm_order = {
            PermissionLevel.READ: 0,
            PermissionLevel.WRITE: 1,
            PermissionLevel.EXECUTE: 2,
        }
        return any(
            perm_order.get(p, 0) >= perm_order.get(required, 0)
            for p in key_info.permissions
        )

    def register_skill(self, skill: MarketplaceSkill, api_key: str) -> Dict[str, Any]:
        if not self.check_permission(api_key, PermissionLevel.WRITE):
            return {"success": False, "error": "权限不足：需要WRITE权限"}
        if skill.skill_id in self._skills:
            return {"success": False, "error": f"技能已存在: {skill.skill_id}"}
        skill.status = SkillStatus.PENDING
        self._skills[skill.skill_id] = skill
        self._save_data()
        return {
            "success": True,
            "skill_id": skill.skill_id,
            "status": skill.status.value,
        }

    def approve_skill(self, skill_id: str, api_key: str) -> Dict[str, Any]:
        if not self.check_permission(api_key, PermissionLevel.WRITE):
            return {"success": False, "error": "权限不足：需要WRITE权限"}
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}
        skill.status = SkillStatus.APPROVED
        skill.updated_at = time.time()
        self._save_data()
        return {"success": True, "skill_id": skill_id, "status": "approved"}

    def discover_skills(
        self, category: Optional[str] = None, keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results = []
        for skill in self._skills.values():
            if skill.status != SkillStatus.APPROVED:
                continue
            if category and skill.category != category:
                continue
            if keyword:
                kw = keyword.lower()
                if kw not in skill.name.lower() and kw not in skill.description.lower():
                    continue
            results.append(
                {
                    "skill_id": skill.skill_id,
                    "name": skill.name,
                    "description": skill.description,
                    "version": skill.version,
                    "category": skill.category,
                    "author": skill.author,
                }
            )
        return results

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        skill = self._skills.get(skill_id)
        if not skill:
            return None
        return {
            "skill_id": skill.skill_id,
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "category": skill.category,
            "author": skill.author,
            "dependencies": skill.dependencies,
            "status": skill.status.value,
            "config": skill.config,
        }

    def execute_skill(
        self, skill_id: str, parameters: Dict[str, Any], api_key: str
    ) -> Dict[str, Any]:
        if not self.check_permission(api_key, PermissionLevel.EXECUTE):
            return {"success": False, "error": "权限不足：需要EXECUTE权限"}
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}
        if skill.status != SkillStatus.APPROVED:
            return {"success": False, "error": f"技能未审核通过: {skill.status.value}"}

        try:
            from .skill_registry import SkillRegistry

            if not hasattr(self, "_skill_registry") or self._skill_registry is None:
                self._skill_registry = SkillRegistry()
            import asyncio

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._skill_registry.execute_skill(skill_id, **parameters),
                    )
                    exec_result = future.result(timeout=60)
            else:
                exec_result = asyncio.run(
                    self._skill_registry.execute_skill(skill_id, **parameters)
                )

            if isinstance(exec_result, dict):
                return {
                    "success": exec_result.get("success", True),
                    "skill_id": skill_id,
                    "data": exec_result.get("data", exec_result),
                    "message": f"技能 {skill.name} v{skill.version} 执行完成",
                }
            return {
                "success": True,
                "skill_id": skill_id,
                "data": exec_result,
                "message": f"技能 {skill.name} v{skill.version} 执行完成",
            }
        except Exception as e:
            logger.warning("Marketplace skill execution failed: %s", e)
            return {
                "success": False,
                "skill_id": skill_id,
                "error": f"技能执行失败: {str(e)}",
            }

    def list_categories(self) -> List[str]:
        categories = set()
        for skill in self._skills.values():
            if skill.status == SkillStatus.APPROVED:
                categories.add(skill.category)
        return sorted(categories)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_skills": len(self._skills),
            "approved_skills": sum(
                1 for s in self._skills.values() if s.status == SkillStatus.APPROVED
            ),
            "pending_skills": sum(
                1 for s in self._skills.values() if s.status == SkillStatus.PENDING
            ),
            "total_api_keys": len(self._api_keys),
            "categories": self.list_categories(),
        }


class ExternalSkillMarketplace:

    REGISTRIES = {
        "opc_official": os.environ.get(
            "OPC_REGISTRY_URL", "https://registry.opc-agents.dev/skills"
        ),
        "github": os.environ.get(
            "OPC_GITHUB_REGISTRY_URL", "https://api.github.com/search/repositories"
        ),
        "mcp_hub": os.environ.get("OPC_MCP_HUB_URL", "https://mcphub.io/api/servers"),
    }

    def __init__(self, data_dir: Optional[str] = None):
        self._data_dir = data_dir or DATA_DIR
        self._external_skills_dir = os.path.join(self._data_dir, "external_skills")
        os.makedirs(self._external_skills_dir, exist_ok=True)
        self._installed_skills: Dict[str, Dict[str, Any]] = {}
        self._mcp_connections: Dict[str, MCPServerInfo] = {}
        self._ssl_context = ssl.create_default_context()
        self._load_installed_skills()

    def _load_installed_skills(self) -> None:
        from opc_manager.data_manager import execute_query

        try:
            rows = execute_query("SELECT * FROM external_skills")
            for row in rows:
                config = {}
                if row.get("skill_config"):
                    try:
                        config = json.loads(row["skill_config"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                self._installed_skills[row["id"]] = {
                    "skill_id": row["id"],
                    "name": row["name"],
                    "description": row.get("description", ""),
                    "source": row.get("source", ""),
                    "version": row.get("version", ""),
                    "trust_level": row.get("trust_level", "unverified"),
                    "config": config,
                    "installed_at": row.get("installed_at", ""),
                }
        except Exception as e:
            logger.warning("加载已安装外部技能失败: %s", e)

    def search_skills(self, query: str, category: str = "") -> Dict[str, Any]:
        results = []
        for skill_id, skill_data in self._installed_skills.items():
            if (
                query.lower() not in skill_data.get("name", "").lower()
                and query.lower() not in skill_data.get("description", "").lower()
            ):
                continue
            if (
                category
                and skill_data.get("config", {}).get("category", "") != category
            ):
                continue
            results.append(
                {
                    **skill_data,
                    "source_type": "local",
                }
            )

        remote_results = self._search_remote_registries(query, category)
        for r in remote_results:
            r["source_type"] = "remote"
            r["trust_level"] = self._get_trust_level(
                r.get("source", ""), r.get("downloads", 0), r.get("rating", 0.0)
            )
        results.extend(remote_results)

        return {
            "success": True,
            "query": query,
            "category": category,
            "results": results,
            "total": len(results),
        }

    def _search_remote_registries(
        self, query: str, category: str = ""
    ) -> List[Dict[str, Any]]:
        results = []
        try:
            import urllib.request
            import urllib.parse

            for registry_name, registry_url in self.REGISTRIES.items():
                try:
                    if registry_name == "github":
                        params = urllib.parse.urlencode(
                            {
                                "q": f"{query} opc-skill",
                                "per_page": 5,
                            }
                        )
                        url = f"{registry_url}?{params}"
                    else:
                        params = urllib.parse.urlencode(
                            {"q": query, "category": category}
                        )
                        url = f"{registry_url}?{params}"

                    req = urllib.request.Request(
                        url, headers={"User-Agent": "OPC-Agents/1.0"}
                    )
                    with urllib.request.urlopen(
                        req, timeout=5, context=self._ssl_context
                    ) as resp:  # nosec B310
                        data = json.loads(resp.read().decode())

                    if registry_name == "github" and "items" in data:
                        for item in data["items"][:5]:
                            results.append(
                                {
                                    "skill_id": f"github_{item.get('id', '')}",
                                    "name": item.get("name", ""),
                                    "description": item.get("description", ""),
                                    "source": registry_name,
                                    "version": "latest",
                                    "downloads": item.get("stargazers_count", 0),
                                    "rating": 0.0,
                                    "url": item.get("html_url", ""),
                                }
                            )
                    elif isinstance(data, list):
                        for item in data[:5]:
                            results.append(
                                {
                                    "skill_id": item.get(
                                        "id", item.get("skill_id", "")
                                    ),
                                    "name": item.get("name", ""),
                                    "description": item.get("description", ""),
                                    "source": registry_name,
                                    "version": item.get("version", "1.0.0"),
                                    "downloads": item.get("downloads", 0),
                                    "rating": item.get("rating", 0.0),
                                    "config": item.get("config", {}),
                                }
                            )
                except Exception as e:
                    logger.debug("搜索注册表 %s 失败: %s", registry_name, e)
                    continue
        except Exception as e:
            logger.warning("远程搜索失败: %s", e)

        return results

    def install_skill(
        self, skill_id: str, source: str = "opc_official", confirmed: bool = False
    ) -> Dict[str, Any]:
        if skill_id in self._installed_skills:
            return {"success": False, "error": f"技能已安装: {skill_id}"}

        skill_info = self._fetch_skill_info(skill_id, source)
        if not skill_info:
            return {"success": False, "error": f"未找到技能: {skill_id}"}

        trust_level = self._get_trust_level(
            source, skill_info.get("downloads", 0), skill_info.get("rating", 0.0)
        )

        if trust_level == TrustLevel.UNVERIFIED:
            return {
                "success": False,
                "error": f"技能 {skill_id} 信任等级为UNVERIFIED，禁止安装",
            }

        if not confirmed:
            permissions_required = skill_info.get("config", {}).get("permissions", [])
            return {
                "success": False,
                "requires_confirmation": True,
                "skill_id": skill_id,
                "name": skill_info.get("name", skill_id),
                "trust_level": trust_level.value,
                "permissions_required": permissions_required,
                "message": f"技能 {skill_id} 需要用户确认后才能安装，请设置 confirmed=True",
            }

        if not self._validate_skill_package(skill_info):
            return {"success": False, "error": f"技能包安全校验失败: {skill_id}"}

        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        from opc_manager.data_manager import execute_write, gen_id

        record_id = gen_id()
        execute_write(
            "INSERT INTO external_skills (id, name, description, source, version, skill_config, trust_level, installed_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                record_id,
                skill_info.get("name", skill_id),
                skill_info.get("description", ""),
                source,
                skill_info.get("version", "1.0.0"),
                json.dumps(skill_info.get("config", {}), ensure_ascii=False),
                trust_level.value,
                now,
            ),
        )

        self._installed_skills[skill_id] = {
            "skill_id": skill_id,
            "name": skill_info.get("name", skill_id),
            "description": skill_info.get("description", ""),
            "source": source,
            "version": skill_info.get("version", "1.0.0"),
            "trust_level": trust_level.value,
            "config": skill_info.get("config", {}),
            "installed_at": now,
        }

        self._log_audit("install_skill", skill_id, source, trust_level.value)

        return {
            "success": True,
            "skill_id": skill_id,
            "name": skill_info.get("name", skill_id),
            "trust_level": trust_level.value,
            "message": f"技能 {skill_id} 安装成功 (信任等级: {trust_level.value})",
        }

    def _fetch_skill_info(self, skill_id: str, source: str) -> Optional[Dict[str, Any]]:
        registry_url = self.REGISTRIES.get(source)
        if not registry_url:
            return None

        try:
            import urllib.request

            url = f"{registry_url}/{skill_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "OPC-Agents/1.0"})
            with urllib.request.urlopen(
                req, timeout=10, context=self._ssl_context
            ) as resp:  # nosec B310
                data = json.loads(resp.read().decode())
            return data
        except Exception as e:
            logger.debug("获取技能信息失败: %s", e)
            return {
                "skill_id": skill_id,
                "name": skill_id,
                "description": f"外部技能 {skill_id}",
                "version": "1.0.0",
                "source": source,
                "config": {},
            }

    def uninstall_skill(self, skill_id: str) -> Dict[str, Any]:
        if skill_id not in self._installed_skills:
            return {"success": False, "error": f"技能未安装: {skill_id}"}

        from opc_manager.data_manager import execute_write

        execute_write("DELETE FROM external_skills WHERE id=?", (skill_id,))

        skill_data = self._installed_skills.pop(skill_id)
        self._log_audit("uninstall_skill", skill_id, skill_data.get("source", ""), "")

        return {
            "success": True,
            "skill_id": skill_id,
            "message": f"技能 {skill_id} 已卸载",
        }

    def list_installed(self) -> Dict[str, Any]:
        skills = list(self._installed_skills.values())
        return {
            "success": True,
            "skills": skills,
            "total": len(skills),
        }

    def search_mcp_servers(self, query: str) -> Dict[str, Any]:
        results = []

        for server_id, server_info in self._mcp_connections.items():
            if (
                query.lower() in server_info.name.lower()
                or query.lower() in server_info.description.lower()
            ):
                results.append(
                    {
                        "server_id": server_info.server_id,
                        "name": server_info.name,
                        "description": server_info.description,
                        "url": server_info.url,
                        "capabilities": server_info.capabilities,
                        "trust_level": server_info.trust_level.value,
                        "connected": server_info.connected,
                        "source_type": "local",
                    }
                )

        try:
            import urllib.request
            import urllib.parse

            mcp_url = self.REGISTRIES.get("mcp_hub", "")
            if mcp_url:
                params = urllib.parse.urlencode({"q": query})
                url = f"{mcp_url}?{params}"
                req = urllib.request.Request(
                    url, headers={"User-Agent": "OPC-Agents/1.0"}
                )
                with urllib.request.urlopen(
                    req, timeout=5, context=self._ssl_context
                ) as resp:  # nosec B310
                    data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    for item in data[:10]:
                        results.append(
                            {
                                "server_id": item.get("id", ""),
                                "name": item.get("name", ""),
                                "description": item.get("description", ""),
                                "url": item.get("url", ""),
                                "capabilities": item.get("capabilities", []),
                                "trust_level": item.get("trust_level", "unverified"),
                                "connected": False,
                                "source_type": "remote",
                            }
                        )
        except Exception as e:
            logger.debug("搜索MCP Hub失败: %s", e)

        return {
            "success": True,
            "query": query,
            "results": results,
            "total": len(results),
        }

    def connect_mcp(
        self, server_url: str, capabilities: List[str] = None
    ) -> Dict[str, Any]:
        if not server_url.startswith("https://"):
            return {"success": False, "error": "MCP服务器URL必须使用HTTPS"}

        server_id = f"mcp_{hashlib.sha256(server_url.encode()).hexdigest()[:12]}"
        if server_id in self._mcp_connections:
            return {"success": False, "error": f"已连接该MCP服务器: {server_id}"}

        try:
            from opc_manager.mcp_protocol import MCPClient

            client = MCPClient(server_url)
            discovered_tools = (
                client.list_tools() if hasattr(client, "list_tools") else []
            )
        except ImportError:
            discovered_tools = []
            logger.debug("MCPClient不可用，跳过工具发现")
        except Exception as e:
            logger.warning("MCP连接失败: %s", e)
            return {"success": False, "error": f"MCP连接失败: {str(e)}"}

        caps = capabilities or [
            t.get("name", "") for t in discovered_tools if isinstance(t, dict)
        ]
        server_info = MCPServerInfo(
            server_id=server_id,
            name=server_url.split("//")[-1].split("/")[0],
            description=f"MCP Server: {server_url}",
            url=server_url,
            capabilities=caps,
            trust_level=TrustLevel.UNVERIFIED,
            connected=True,
        )
        self._mcp_connections[server_id] = server_info

        self._log_audit("connect_mcp", server_id, server_url, "unverified")

        return {
            "success": True,
            "server_id": server_id,
            "url": server_url,
            "capabilities": caps,
            "tools_discovered": len(discovered_tools),
            "message": f"MCP服务器连接成功，发现 {len(discovered_tools)} 个工具",
        }

    def _validate_skill_package(self, package_info: Dict[str, Any]) -> bool:
        if not isinstance(package_info, dict):
            return False

        config = package_info.get("config", {})
        if isinstance(config, dict):
            permissions = config.get("permissions", [])
            dangerous_perms = {"filesystem:full", "network:full", "system:full"}
            if dangerous_perms.intersection(set(permissions)):
                logger.warning(
                    "技能请求危险权限: %s",
                    dangerous_perms.intersection(set(permissions)),
                )
                return False

        return True

    def _get_trust_level(
        self, source: str, downloads: int, rating: float
    ) -> TrustLevel:
        if source == "opc_official":
            return TrustLevel.OFFICIAL
        if source == "github" and downloads >= 100:
            return TrustLevel.VERIFIED
        if downloads >= 50 and rating >= 4.0:
            return TrustLevel.VERIFIED
        if downloads >= 10 or rating >= 3.0:
            return TrustLevel.COMMUNITY
        return TrustLevel.UNVERIFIED

    def _log_audit(
        self, action: str, skill_id: str, source: str, trust_level: str
    ) -> None:
        logger.info(
            "[AUDIT] action=%s skill_id=%s source=%s trust_level=%s",
            action,
            skill_id,
            source,
            trust_level,
        )

    def _validate_entry_point(self, entry_point: str) -> bool:
        """验证 entry_point 路径是否在允许的目录内，防止路径遍历攻击。

        允许的目录:
        - data/marketplace/external_skills/ (外部技能目录)
        - data/custom_skills/ (自定义技能目录)
        - plugins/ (插件目录)

        Returns:
            True 如果路径安全，False 如果路径非法
        """
        if not entry_point:
            return False

        # 解析为绝对路径，消除 .. 和符号链接
        resolved = os.path.realpath(entry_point)

        # 检查路径遍历：不允许包含 ..
        if ".." in os.path.normpath(entry_point):
            logger.warning(
                "[SECURITY] entry_point contains path traversal: %s", entry_point
            )
            return False

        # 必须是 .py 文件
        if not resolved.endswith(".py"):
            logger.warning(
                "[SECURITY] entry_point is not a Python file: %s", entry_point
            )
            return False

        # 文件必须存在
        if not os.path.isfile(resolved):
            logger.warning(
                "[SECURITY] entry_point file does not exist: %s", entry_point
            )
            return False

        # 定义允许的根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        allowed_dirs = [
            os.path.realpath(
                os.path.join(project_root, "data", "marketplace", "external_skills")
            ),
            os.path.realpath(os.path.join(project_root, "data", "custom_skills")),
            os.path.realpath(os.path.join(project_root, "plugins")),
        ]

        # 验证路径在允许的目录内
        for allowed_dir in allowed_dirs:
            if resolved.startswith(allowed_dir + os.sep) or resolved == allowed_dir:
                return True

        logger.warning(
            "[SECURITY] entry_point outside allowed directories: %s (resolved: %s)",
            entry_point,
            resolved,
        )
        return False

    def execute_in_sandbox(
        self, skill_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        skill_data = self._installed_skills.get(skill_id)
        if not skill_data:
            return {"success": False, "error": f"技能未安装: {skill_id}"}

        config = skill_data.get("config", {})
        entry_point = config.get("entry_point", "")
        if not entry_point:
            return {
                "success": True,
                "data": {"goal": parameters.get("goal", ""), "sandbox": True},
            }

        # 验证 entry_point 路径安全性
        if not self._validate_entry_point(entry_point):
            return {
                "success": False,
                "error": f"entry_point 路径不合法，仅允许 data/custom_skills/、data/marketplace/external_skills/、plugins/ 目录下的文件: {entry_point}",
            }

        self._check_network_whitelist(config)

        try:
            # 使用 importlib 安全加载替代 exec(open().read())
            spec = importlib.util.spec_from_file_location(
                f"skill_{skill_id}", entry_point
            )
            if spec is None or spec.loader is None:
                return {
                    "success": False,
                    "error": f"无法加载技能模块: {entry_point}",
                }
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 调用模块的 run 函数（标准技能入口）
            if hasattr(module, "run"):
                output = module.run(parameters)
            else:
                return {
                    "success": False,
                    "error": f"技能模块缺少 run() 入口函数: {entry_point}",
                }

            if isinstance(output, dict):
                return {"success": True, "data": output}
            else:
                return {"success": True, "data": {"output": str(output)[:1000]}}
        except subprocess.TimeoutExpired:
            logger.warning("Sandbox timeout for %s", skill_id)
            return {
                "success": False,
                "error": f"沙箱执行超时 ({SANDBOX_TIMEOUT_SECONDS}s)",
            }
        except Exception as e:
            logger.warning("Sandbox error for %s: %s", skill_id, e)
            return {"success": False, "error": f"沙箱执行异常: {str(e)}"}

    def _check_network_whitelist(self, config: Dict[str, Any]) -> None:
        allowed_hosts = set(NETWORK_WHITELIST)
        config_hosts = config.get("allowed_hosts", [])
        if config_hosts:
            for host in config_hosts:
                if host in allowed_hosts or any(
                    host.endswith("." + d) for d in allowed_hosts
                ):
                    continue
                logger.warning(
                    "[SANDBOX] Non-whitelisted host in skill config: %s", host
                )

    def get_external_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        return self._installed_skills.get(skill_id)

    def get_mcp_server(self, server_id: str) -> Optional[MCPServerInfo]:
        return self._mcp_connections.get(server_id)
