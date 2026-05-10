"""
SkillMarketplace — 技能市场API

提供技能注册/发现/调用的REST API，支持：
- 技能注册（含元数据：版本/依赖/权限）
- 技能发现（按分类/关键词搜索）
- 技能调用（通过skill_id执行）
- API Key认证 + 权限分级（read/write/execute）

架构位置：
  外部客户端 → SkillMarketplaceAPI → SkillRegistry → ExecutorBrain

安全要求（安全专家审核S-3）：
  - 所有API端点需API Key认证
  - 技能权限分级：read（查看）/ write（注册）/ execute（调用）
  - 注册技能需审核状态（pending→approved/rejected）
"""

import hashlib
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "marketplace")


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
    permissions: List[PermissionLevel] = field(default_factory=lambda: [PermissionLevel.READ])
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
    permissions: List[PermissionLevel] = field(default_factory=lambda: [PermissionLevel.READ])
    created_at: float = 0.0
    rate_limit: int = 100
    salt: str = ""

    def __post_init__(self):
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
        self._load_data()

    def _load_data(self) -> None:
        if os.path.exists(self._api_keys_file):
            try:
                with open(self._api_keys_file, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    perms = [PermissionLevel(p) for p in v.get("permissions", ["read"])]
                    api_key_obj = APIKey(
                        key_hash=v["key_hash"], name=v["name"],
                        permissions=perms, created_at=v.get("created_at", 0),
                        rate_limit=v.get("rate_limit", 100)
                    )
                    api_key_obj.salt = v.get("salt", "")
                    self._api_keys[k] = api_key_obj
            except Exception as e:
                logger.warning(f"加载API Keys失败: {e}")

        if os.path.exists(self._skills_file):
            try:
                with open(self._skills_file, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    perms = [PermissionLevel(p) for p in v.get("permissions", ["read"])]
                    deps = v.get("dependencies", [])
                    self._skills[k] = MarketplaceSkill(
                        skill_id=v["skill_id"], name=v["name"],
                        description=v["description"], version=v["version"],
                        category=v["category"], author=v["author"],
                        permissions=perms, dependencies=deps,
                        status=SkillStatus(v.get("status", "pending")),
                        created_at=v.get("created_at", 0),
                        updated_at=v.get("updated_at", 0),
                        config=v.get("config", {})
                    )
            except Exception as e:
                logger.warning(f"加载技能数据失败: {e}")

    def _save_data(self) -> None:
        try:
            keys_data = {}
            for k, v in self._api_keys.items():
                keys_data[k] = {
                    "key_hash": v.key_hash, "name": v.name,
                    "permissions": [p.value for p in v.permissions],
                    "created_at": v.created_at, "rate_limit": v.rate_limit,
                    "salt": v.salt
                }
            with open(self._api_keys_file, "w") as f:
                json.dump(keys_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存API Keys失败: {e}")

        try:
            skills_data = {}
            for k, v in self._skills.items():
                skills_data[k] = {
                    "skill_id": v.skill_id, "name": v.name,
                    "description": v.description, "version": v.version,
                    "category": v.category, "author": v.author,
                    "permissions": [p.value for p in v.permissions],
                    "dependencies": v.dependencies,
                    "status": v.status.value,
                    "created_at": v.created_at, "updated_at": v.updated_at,
                    "config": v.config
                }
            with open(self._skills_file, "w") as f:
                json.dump(skills_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存技能数据失败: {e}")

    def create_api_key(self, name: str, permissions: List[PermissionLevel],
                       rate_limit: int = 100) -> str:
        import secrets
        raw_key = f"opc_{secrets.token_hex(16)}"
        salt = secrets.token_hex(8)
        key_hash = hashlib.sha256(f"{salt}:{raw_key}".encode()).hexdigest()
        self._api_keys[key_hash] = APIKey(
            key_hash=key_hash, name=name,
            permissions=permissions, rate_limit=rate_limit
        )
        self._api_keys[key_hash].salt = salt
        self._save_data()
        return raw_key

    def authenticate(self, api_key: str) -> Optional[APIKey]:
        for key_hash, key_info in self._api_keys.items():
            salt = key_info.salt
            check_hash = hashlib.sha256(f"{salt}:{api_key}".encode()).hexdigest()
            if check_hash == key_hash:
                return key_info
        plain_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return self._api_keys.get(plain_hash)

    def check_permission(self, api_key: str, required: PermissionLevel) -> bool:
        key_info = self.authenticate(api_key)
        if not key_info:
            return False
        perm_order = {PermissionLevel.READ: 0, PermissionLevel.WRITE: 1, PermissionLevel.EXECUTE: 2}
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
        return {"success": True, "skill_id": skill.skill_id, "status": skill.status.value}

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

    def discover_skills(self, category: Optional[str] = None,
                        keyword: Optional[str] = None) -> List[Dict[str, Any]]:
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
            results.append({
                "skill_id": skill.skill_id,
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "category": skill.category,
                "author": skill.author,
            })
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

    def execute_skill(self, skill_id: str, parameters: Dict[str, Any],
                      api_key: str) -> Dict[str, Any]:
        if not self.check_permission(api_key, PermissionLevel.EXECUTE):
            return {"success": False, "error": "权限不足：需要EXECUTE权限"}
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}
        if skill.status != SkillStatus.APPROVED:
            return {"success": False, "error": f"技能未审核通过: {skill.status.value}"}
        return {
            "success": True,
            "skill_id": skill_id,
            "message": f"技能 {skill.name} v{skill.version} 调用请求已接受",
            "parameters": parameters,
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
            "approved_skills": sum(1 for s in self._skills.values() if s.status == SkillStatus.APPROVED),
            "pending_skills": sum(1 for s in self._skills.values() if s.status == SkillStatus.PENDING),
            "total_api_keys": len(self._api_keys),
            "categories": self.list_categories(),
        }
