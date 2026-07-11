"""Skill marketplace facade.

This module hosts the local skill marketplace (``SkillMarketplace``) together
with the permission/skill enums and the local-skill dataclasses. The external
skill marketplace implementation (``ExternalSkillMarketplace`` and its
``ExternalSkill`` / ``MCPServerInfo`` dataclasses) now lives in
``skill_marketplace_external``; those names are re-exported here so that
existing ``from opc_manager.skill_marketplace import ...`` statements continue
to work unchanged.

Shared primitives (``DATA_DIR`` and ``TrustLevel``) live in
``skill_marketplace_constants`` to avoid a circular import between this facade
and ``skill_marketplace_external``.
"""

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

from opc_manager.skill_marketplace_constants import DATA_DIR, TrustLevel
from opc_manager.skill_marketplace_external import (
    ExternalSkill,
    MCPServerInfo,
    ExternalSkillMarketplace,
    NETWORK_WHITELIST,
    SANDBOX_MAX_MEMORY_MB,
)

if TYPE_CHECKING:
    # 仅为类型检查导入，避免运行时循环依赖；运行时在 execute_skill 中懒加载
    from .skill_registry import SkillRegistry

logger = logging.getLogger(__name__)

# PBKDF2 迭代次数（硬约束：禁止裸 SHA-256，与 data_manager._KEY_DERIVATION_ITERATIONS 一致）
_API_KEY_ITERATIONS = 100000


class PermissionLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


class SkillStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


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

    def __post_init__(self) -> None:
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

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()


class SkillMarketplace:

    def __init__(self, data_dir: Optional[str] = None):
        self._data_dir = data_dir or DATA_DIR
        self._api_keys_file = os.path.join(self._data_dir, "api_keys.json")
        self._skills_file = os.path.join(self._data_dir, "skills.json")
        os.makedirs(self._data_dir, exist_ok=True)
        self._api_keys: Dict[str, APIKey] = {}
        self._skills: Dict[str, MarketplaceSkill] = {}
        # 懒加载的技能注册表，首次执行技能时实例化
        self._skill_registry: Optional["SkillRegistry"] = None
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
            for k, skill in self._skills.items():
                skills_data[k] = {
                    "skill_id": skill.skill_id,
                    "name": skill.name,
                    "description": skill.description,
                    "version": skill.version,
                    "category": skill.category,
                    "author": skill.author,
                    "permissions": [p.value for p in skill.permissions],
                    "dependencies": skill.dependencies,
                    "status": skill.status.value,
                    "created_at": skill.created_at,
                    "updated_at": skill.updated_at,
                    "config": skill.config,
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
        # PBKDF2-HMAC-SHA256 + per-key salt（硬约束：禁止裸 SHA-256，与 data_manager.py 一致）
        # BREAKING CHANGE (v0.4.0): 旧 SHA-256 哈希的 API key 需重新签发
        key_hash = hashlib.pbkdf2_hmac(
            "sha256", raw_key.encode(), salt.encode(), _API_KEY_ITERATIONS
        ).hex()
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
            check_hash = hashlib.pbkdf2_hmac(
                "sha256", api_key.encode(), salt.encode(), _API_KEY_ITERATIONS
            ).hex()
            if hmac.compare_digest(check_hash, key_hash):
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

            _new_loop = asyncio.new_event_loop()
            try:
                exec_result = _new_loop.run_until_complete(
                    self._skill_registry.execute_skill(skill_id, **parameters)
                )
            finally:
                _new_loop.close()

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


__all__ = [
    "APIKey",
    "DATA_DIR",
    "ExternalSkill",
    "ExternalSkillMarketplace",
    "MCPServerInfo",
    "MarketplaceSkill",
    "NETWORK_WHITELIST",
    "PermissionLevel",
    "SANDBOX_MAX_MEMORY_MB",
    "SkillMarketplace",
    "SkillStatus",
    "TrustLevel",
]
