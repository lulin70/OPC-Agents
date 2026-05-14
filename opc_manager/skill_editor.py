"""
SkillEditor — 自定义技能编辑器

MVP版本：表单式配置（技能名/输入参数/输出格式）
- 技能创建/编辑/删除
- 技能测试/预览
- 技能发布到技能市场

架构位置：
  Streamlit UI → SkillEditor → SkillRegistry / SkillMarketplace
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "custom_skills")


class ParameterType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    TEXT = "text"
    HTML = "html"


@dataclass
class SkillParameter:
    name: str
    param_type: ParameterType = ParameterType.STRING
    description: str = ""
    required: bool = True
    default_value: Any = None
    enum_values: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "name": self.name,
            "type": self.param_type.value,
            "description": self.description,
            "required": self.required,
        }
        if self.default_value is not None:
            d["default"] = self.default_value
        if self.enum_values:
            d["enum"] = self.enum_values
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillParameter":
        return cls(
            name=data["name"],
            param_type=ParameterType(data.get("type", "string")),
            description=data.get("description", ""),
            required=data.get("required", True),
            default_value=data.get("default"),
            enum_values=data.get("enum", []),
        )


@dataclass
class CustomSkill:
    skill_id: str
    name: str
    description: str
    category: str = "custom"
    version: str = "1.0.0"
    author: str = "user"
    input_parameters: List[SkillParameter] = field(default_factory=list)
    output_format: OutputFormat = OutputFormat.MARKDOWN
    template: str = ""
    prompt_template: str = ""
    dependencies: List[str] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.updated_at == 0.0:
            self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "input_parameters": [p.to_dict() for p in self.input_parameters],
            "output_format": self.output_format.value,
            "template": self.template,
            "prompt_template": self.prompt_template,
            "dependencies": self.dependencies,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomSkill":
        params = [SkillParameter.from_dict(p) for p in data.get("input_parameters", [])]
        return cls(
            skill_id=data["skill_id"],
            name=data["name"],
            description=data["description"],
            category=data.get("category", "custom"),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "user"),
            input_parameters=params,
            output_format=OutputFormat(data.get("output_format", "markdown")),
            template=data.get("template", ""),
            prompt_template=data.get("prompt_template", ""),
            dependencies=data.get("dependencies", []),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
        )


class SkillEditor:

    def __init__(self, skills_dir: Optional[str] = None):
        self._skills_dir = skills_dir or SKILLS_DIR
        os.makedirs(self._skills_dir, exist_ok=True)
        self._skills: Dict[str, CustomSkill] = {}
        self._load_skills()

    def _load_skills(self) -> None:
        for filename in os.listdir(self._skills_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self._skills_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                    skill = CustomSkill.from_dict(data)
                    self._skills[skill.skill_id] = skill
                except Exception as e:
                    logger.warning("加载技能失败 %s: %s", filename, e)

    def _save_skill(self, skill: CustomSkill) -> None:
        filepath = os.path.join(self._skills_dir, f"{skill.skill_id}.json")
        with open(filepath, "w") as f:
            json.dump(skill.to_dict(), f, ensure_ascii=False, indent=2)

    def create_skill(self, skill: CustomSkill) -> Dict[str, Any]:
        if skill.skill_id in self._skills:
            return {"success": False, "error": f"技能ID已存在: {skill.skill_id}"}
        self._skills[skill.skill_id] = skill
        self._save_skill(skill)
        return {"success": True, "skill_id": skill.skill_id}

    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}

        for key, value in updates.items():
            if key == "input_parameters":
                skill.input_parameters = [SkillParameter.from_dict(p) for p in value]
            elif key == "output_format":
                skill.output_format = OutputFormat(value)
            elif hasattr(skill, key):
                setattr(skill, key, value)

        skill.updated_at = time.time()
        self._save_skill(skill)
        return {"success": True, "skill_id": skill_id}

    def delete_skill(self, skill_id: str) -> Dict[str, Any]:
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}
        del self._skills[skill_id]
        filepath = os.path.join(self._skills_dir, f"{skill_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
        return {"success": True, "skill_id": skill_id}

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        skill = self._skills.get(skill_id)
        return skill.to_dict() if skill else None

    def list_skills(self) -> List[Dict[str, Any]]:
        return [
            {
                "skill_id": s.skill_id,
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "version": s.version,
                "output_format": s.output_format.value,
                "parameter_count": len(s.input_parameters),
            }
            for s in self._skills.values()
        ]

    def preview_skill(self, skill_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}

        preview = skill.template or skill.prompt_template
        if not preview:
            preview = f"# {skill.name}\n\n{skill.description}"

        for param in skill.input_parameters:
            value = parameters.get(param.name, param.default_value or f"<{param.name}>")
            preview = preview.replace(f"{{{{{param.name}}}}}", str(value))

        return {
            "success": True,
            "skill_id": skill_id,
            "preview": preview,
            "output_format": skill.output_format.value,
        }

    def test_skill(self, skill_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}

        missing = [
            p.name for p in skill.input_parameters
            if p.required and p.name not in parameters
        ]
        if missing:
            return {"success": False, "error": f"缺少必需参数: {missing}"}

        preview_result = self.preview_skill(skill_id, parameters)
        return {
            "success": True,
            "skill_id": skill_id,
            "test_result": preview_result.get("preview", ""),
            "parameters_used": parameters,
            "output_format": skill.output_format.value,
        }

    def publish_to_marketplace(self, skill_id: str, marketplace=None) -> Dict[str, Any]:
        skill = self._skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}

        if marketplace:
            from .skill_marketplace import MarketplaceSkill, PermissionLevel
            market_skill = MarketplaceSkill(
                skill_id=skill.skill_id,
                name=skill.name,
                description=skill.description,
                version=skill.version,
                category=skill.category,
                author=skill.author,
                permissions=[PermissionLevel.READ, PermissionLevel.EXECUTE],
                dependencies=skill.dependencies,
                config={"template": skill.template, "prompt_template": skill.prompt_template},
            )
            return {"success": True, "skill_id": skill_id, "marketplace_status": "pending"}

        return {"success": True, "skill_id": skill_id, "marketplace_status": "not_connected"}

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_skills": len(self._skills),
            "categories": list(set(s.category for s in self._skills.values())),
            "skills_dir": self._skills_dir,
        }
