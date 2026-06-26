"""
Persona Manager - PersonaManager

Load, manage, and switch persona variants for different business types.
Phase 1 MVP: Supports 3 core persona variants.
"""

import os
import logging
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from opc_manager.business_types import BusinessType

logger = logging.getLogger(__name__)


@dataclass
class PersonaConfig:
    """Persona configuration data class"""

    variant_id: str
    display_name: str
    emoji: str
    target_business_type: str
    style_overrides: Dict[str, Any]
    expertise_tags: List[str]
    vocabulary: Dict[str, List[str]]
    dialogue_templates: Dict[str, str]
    proactive_rules: List[Dict[str, str]]
    response_patterns: Dict[str, List[str]]

    def get_template(self, template_name: str, **kwargs) -> str:
        """
        Get dialogue template and fill variables

        Args:
            template_name: Template name (greeting/accept_task etc.)
            **kwargs: Variables to fill

        Returns:
            Filled template string
        """
        template = self.dialogue_templates.get(template_name, "")
        if template and kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                return f"[模板变量缺失: {e}] {template}"
        return template or f"[未找到模板: {template_name}]"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "variant_id": self.variant_id,
            "display_name": self.display_name,
            "emoji": self.emoji,
            "target_business_type": self.target_business_type,
            "style_overrides": self.style_overrides,
            "expertise_tags": self.expertise_tags,
            "vocabulary": self.vocabulary,
            "dialogue_templates": self.dialogue_templates,
            "proactive_rules": self.proactive_rules,
            "response_patterns": self.response_patterns,
        }


class PersonaManager:
    """
    Persona Manager

    Responsibilities:
    1. Load YAML configuration file
    2. Select appropriate persona based on business type
    3. Manage persona switching and caching
    4. Provide response formatting interface
    """

    def __init__(self, config_path: str = None):
        """
        Initialize persona manager

        Args:
            config_path: YAML config file path (optional, defaults to standard path)
        """
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "persona_variants.yaml",
            )

        self.config_path = config_path
        self.base_persona: Dict[str, Any] = {}
        self.variants: Dict[str, PersonaConfig] = {}
        self._cache: Dict[str, PersonaConfig] = {}  # User-level cache

        self._load_config()

    def _load_config(self):
        """Load YAML configuration file"""
        if not os.path.exists(self.config_path):
            logger.warning("Config file not found - %s", self.config_path)
            self._load_fallback_config()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            self.base_persona = config.get("base_persona", {})
            variants_raw = config.get("variants", {})

            for variant_id, variant_config in variants_raw.items():
                self.variants[variant_id] = PersonaConfig(
                    variant_id=variant_id,
                    display_name=variant_config.get("display_name", variant_id),
                    emoji=variant_config.get("emoji", ""),
                    target_business_type=variant_config.get("target_business_type", ""),
                    style_overrides=variant_config.get("style_overrides", {}),
                    expertise_tags=variant_config.get("expertise_tags", []),
                    vocabulary=variant_config.get(
                        "vocabulary", {"domain_specific": [], "forbidden": []}
                    ),
                    dialogue_templates=variant_config.get("dialogue_templates", {}),
                    proactive_rules=variant_config.get("proactive_rules", []),
                    response_patterns=variant_config.get("response_patterns", {}),
                )

            logger.info("Successfully loaded %d persona variants", len(self.variants))
            for vid, v in self.variants.items():
                logger.info("  - [%s] %s (%s)", v.emoji, v.display_name, vid)

        except Exception as e:
            logger.error("Failed to load config: %s", e)
            self._load_fallback_config()

    def _load_fallback_config(self):
        """Load fallback config when YAML file is unavailable"""
        logger.warning("Using built-in default config")
        self.base_persona = {
            "name": "总裁办秘书",
            "version": "2.1.0",
            "core_principles": ["凡事有交代", "主动不被动", "结果导向"],
        }

        self.variants["content_creator"] = PersonaConfig(
            variant_id="content_creator",
            display_name="内容小助理",
            emoji="",
            target_business_type="content_creator",
            style_overrides={"tone": "轻松活泼", "formality_level": 0.3},
            expertise_tags=["内容创作"],
            vocabulary={"domain_specific": ["内容"], "forbidden": []},
            dialogue_templates={
                "greeting": "嗨！今天有什么想法？",
                "accept_task": "收到！我来帮你处理！",
                "complete": "搞定啦！",
            },
            proactive_rules=[],
            response_patterns={},
        )

    def get_persona(
        self,
        user_id: str = None,
        business_type: BusinessType = None,
        context: Dict[str, Any] = None,
    ) -> Optional[PersonaConfig]:
        """
        Get persona configuration for user

        Args:
            user_id: User ID (optional, for caching)
            business_type: Business type (required)
            context: Additional context info (optional)

        Returns:
            PersonaConfig: Persona config object, or None if not found
        """
        if business_type is None:
            logger.error("business_type parameter cannot be None")
            return None

        type_key = business_type.value

        if user_id and user_id in self._cache:
            cached = self._cache[user_id]
            if cached.target_business_type == type_key:
                return cached

        persona = self.variants.get(type_key)

        if persona is None:
            logger.warning("No persona config found for business type %s", type_key)
            available = list(self.variants.keys())
            logger.info("Available persona variants: %s", available)

            if self.variants:
                persona = list(self.variants.values())[0]

        if persona and user_id:
            self._cache[user_id] = persona

        return persona

    def switch_persona(
        self,
        user_id: str,
        new_business_type: BusinessType,
        reason: str = "user_request",
    ) -> bool:
        """
        Switch user's persona

        Args:
            user_id: User ID
            new_business_type: New business type
            reason: Switch reason (for logging)

        Returns:
            bool: Whether switch was successful
        """
        new_persona = self.get_persona(user_id=user_id, business_type=new_business_type)

        if new_persona:
            old_persona = self._cache.get(user_id)
            old_type = old_persona.target_business_type if old_persona else "none"

            self._cache[user_id] = new_persona

            logger.info("User %s persona switch successful", user_id)
            logger.info("  From: %s → To: %s", old_type, new_business_type.value)
            logger.info("  Reason: %s", reason)

            return True
        else:
            logger.error(
                "User %s persona switch failed: no config for %s",
                user_id,
                new_business_type.value,
            )
            return False

    def format_response(
        self, persona: PersonaConfig, template_name: str, **kwargs
    ) -> str:
        """
        Format response using specified persona

        Args:
            persona: Persona configuration
            template_name: Template name
            **kwargs: Template variables

        Returns:
            str: Formatted response text
        """
        if not persona:
            return "[系统错误：无法获取人格配置]"

        base_response = persona.get_template(template_name, **kwargs)

        style = persona.style_overrides
        emoji_density = style.get("emoji_density", "medium")

        if emoji_density == "high" and not any(
            c in base_response for c in ["", "", "", ""]
        ):
            emojis = ["", "", "", "", ""]
            import random

            base_response += (
                f" {random.choice(emojis)}"  # nosec B311 - non-crypto emoji selection
            )

        return base_response

    def get_greeting(
        self, user_id: str = None, business_type: BusinessType = None
    ) -> str:
        """Get greeting message"""
        persona = self.get_persona(user_id=user_id, business_type=business_type)
        if persona:
            return self.format_response(persona, "greeting")
        return "你好！我是你的AI助手，有什么可以帮你的吗？"

    def get_task_acceptance(
        self,
        user_id: str = None,
        business_type: BusinessType = None,
        task_description: str = "",
    ) -> str:
        """Get task acceptance response"""
        persona = self.get_persona(user_id=user_id, business_type=business_type)
        if persona:
            return self.format_response(persona, "accept_task")
        return f"收到！我来帮你处理「{task_description}」这个任务。"

    def get_completion_message(
        self,
        user_id: str = None,
        business_type: BusinessType = None,
        deliverable: str = "成果",
    ) -> str:
        """Get task completion message"""
        persona = self.get_persona(user_id=user_id, business_type=business_type)
        if persona:
            return self.format_response(persona, "complete", deliverable=deliverable)
        return f"完成了！这是你的{deliverable}。"

    def list_available_personas(self) -> List[Dict[str, Any]]:
        """List all available persona variants"""
        result = []
        for variant_id, persona in self.variants.items():
            result.append(
                {
                    "id": variant_id,
                    "display_name": persona.display_name,
                    "emoji": persona.emoji,
                    "business_type": persona.target_business_type,
                    "expertise_tags_count": len(persona.expertise_tags),
                    "templates_count": len(persona.dialogue_templates),
                }
            )
        return result

    def get_statistics(self) -> Dict[str, Any]:
        """Get persona manager statistics"""
        return {
            "total_variants": len(self.variants),
            "cached_users": len(self._cache),
            "available_types": list(self.variants.keys()),
            "base_persona_name": self.base_persona.get("name", "Unknown"),
            "config_version": self.base_persona.get("version", "Unknown"),
            "config_path": self.config_path,
        }

    def clear_cache(self, user_id: str = None):
        """
        Clear cache

        Args:
            user_id: If provided, only clear cache for this user; otherwise clear all
        """
        if user_id:
            if user_id in self._cache:
                del self._cache[user_id]
                logger.info("Cleared cache for user %s", user_id)
        else:
            self._cache.clear()
            logger.info("Cleared all cache")


if __name__ == "__main__":
    manager = PersonaManager()

    print("=" * 60)
    print("OPC-Agents 人格管理器 v1.0")
    print("=" * 60)

    stats = manager.get_statistics()
    print(f"\n 统计信息:")
    print(f"   总变体数: {stats['total_variants']}")
    print(f"   缓存用户数: {stats['cached_users']}")
    print(f"   基础人格: {stats['base_persona_name']}")
    print(f"   配置版本: {stats['config_version']}")

    print(f"\n 可用人格列表:")
    personas = manager.list_available_personas()
    for p in personas:
        print(f"   [{p['emoji']}] {p['display_name']} ({p['id']})")

    test_users = [
        ("user_001_content", BusinessType.CONTENT_CREATOR),
        ("user_002_digital", BusinessType.DIGITAL_PRODUCT),
        ("user_003_ecommerce", BusinessType.ECOMMERCE),
    ]

    print("\n" + "=" * 60)
    print(" 功能测试")
    print("=" * 60)

    for user_id, btype in test_users:
        print(f"\n--- 测试用户: {user_id} (类型: {btype.value}) ---")

        persona = manager.get_persona(user_id=user_id, business_type=btype)
        if persona:
            print(f" 加载成功: {persona.display_name} {persona.emoji}")

            greeting = manager.get_greeting(user_id=user_id, business_type=btype)
            print(f"问候语: {greeting}")

            accept_msg = manager.get_task_acceptance(
                user_id=user_id, business_type=btype, task_description="测试任务"
            )
            print(f"接受任务: {accept_msg}")

            complete_msg = manager.get_completion_message(
                user_id=user_id, business_type=btype, deliverable="周内容日历"
            )
            print(f"完成任务: {complete_msg}")

            suggestion = manager.format_response(
                persona, "suggestion", suggestion="在周二发布效果更好"
            )
            print(f"建议: {suggestion}")
        else:
            print(" 加载失败")

    print("\n" + "=" * 60)
    print(" 人格切换测试")
    print("=" * 60)

    test_user = "test_switch_user"
    manager.get_persona(user_id=test_user, business_type=BusinessType.CONTENT_CREATOR)
    print(
        f"\n初始状态: {manager._cache.get(test_user).display_name if test_user in manager._cache else 'None'}"
    )

    success = manager.switch_persona(
        test_user, BusinessType.ECOMMERCE, reason="测试切换"
    )
    print(f"切换结果: {'成功 ' if success else '失败 '}")

    current = manager._cache.get(test_user)
    if current:
        print(f"当前人格: {current.display_name} {current.emoji}")

    final_stats = manager.get_statistics()
    print(f"\n最终统计: 缓存用户数 = {final_stats['cached_users']}")
