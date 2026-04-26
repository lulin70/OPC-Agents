"""
人格管理器 - PersonaManager

加载、管理和切换不同业务类型的人格变体
Phase 1 MVP版本：支持3种核心人格变体
"""

import os
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from opc_manager.business_types import BusinessType


@dataclass
class PersonaConfig:
    """人格配置数据类"""

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
        获取对话模板并填充变量

        Args:
            template_name: 模板名称（greeting/accept_task等）
            **kwargs: 要填充的变量

        Returns:
            填充后的模板字符串
        """
        template = self.dialogue_templates.get(template_name, "")
        if template and kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                return f"[模板变量缺失: {e}] {template}"
        return template or f"[未找到模板: {template_name}]"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
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
    人格管理器

    职责：
    1. 加载YAML配置文件
    2. 根据业务类型选择合适的人格
    3. 管理人格切换和缓存
    4. 提供响应格式化接口
    """

    def __init__(self, config_path: str = None):
        """
        初始化人格管理器

        Args:
            config_path: YAML配置文件路径（可选，默认使用标准路径）
        """
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "persona_variants.yaml",
            )

        self.config_path = config_path
        self.base_persona: Dict[str, Any] = {}
        self.variants: Dict[str, PersonaConfig] = {}
        self._cache: Dict[str, PersonaConfig] = {}  # 用户级缓存

        self._load_config()

    def _load_config(self):
        """加载YAML配置文件"""
        if not os.path.exists(self.config_path):
            print(f"[PersonaManager] 警告：配置文件不存在 - {self.config_path}")
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
                    emoji=variant_config.get("emoji", "🤖"),
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

            print(f"[PersonaManager] 成功加载 {len(self.variants)} 个人格变体")
            for vid, v in self.variants.items():
                print(f"  - [{v.emoji}] {v.display_name} ({vid})")

        except Exception as e:
            print(f"[PersonaManager] 加载配置失败: {e}")
            self._load_fallback_config()

    def _load_fallback_config(self):
        """加载备用配置（当YAML文件不可用时）"""
        print("[PersonaManager] 使用内置默认配置")
        self.base_persona = {
            "name": "总裁办秘书",
            "version": "2.1.0",
            "core_principles": ["凡事有交代", "主动不被动", "结果导向"],
        }

        self.variants["content_creator"] = PersonaConfig(
            variant_id="content_creator",
            display_name="内容小助理",
            emoji="✍️",
            target_business_type="content_creator",
            style_overrides={"tone": "轻松活泼", "formality_level": 0.3},
            expertise_tags=["内容创作"],
            vocabulary={"domain_specific": ["内容"], "forbidden": []},
            dialogue_templates={
                "greeting": "嗨！今天有什么想法？💡",
                "accept_task": "收到！我来帮你处理！",
                "complete": "搞定啦！✨",
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
        获取用户应使用的人格配置

        Args:
            user_id: 用户ID（可选，用于缓存）
            business_type: 业务类型（必须）
            context: 额外上下文信息（可选）

        Returns:
            PersonaConfig: 人格配置对象，如果找不到则返回None
        """
        if business_type is None:
            print("[PersonaManager] 错误：business_type参数不能为None")
            return None

        type_key = business_type.value

        if user_id and user_id in self._cache:
            cached = self._cache[user_id]
            if cached.target_business_type == type_key:
                return cached

        persona = self.variants.get(type_key)

        if persona is None:
            print(f"[PersonaManager] 未找到业务类型 {type_key} 对应的人格配置")
            available = list(self.variants.keys())
            print(f"[PersonaManager] 可用的人格变体: {available}")

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
        切换用户的人格

        Args:
            user_id: 用户ID
            new_business_type: 新的业务类型
            reason: 切换原因（用于日志）

        Returns:
            bool: 是否切换成功
        """
        new_persona = self.get_persona(user_id=user_id, business_type=new_business_type)

        if new_persona:
            old_persona = self._cache.get(user_id)
            old_type = old_persona.target_business_type if old_persona else "none"

            self._cache[user_id] = new_persona

            print(f"[PersonaManager] 用户{user_id}人格切换成功")
            print(f"  从: {old_type} → 到: {new_business_type.value}")
            print(f"  原因: {reason}")

            return True
        else:
            print(
                f"[PersonaManager] 用户{user_id}人格切换失败：找不到{new_business_type.value}对应配置"
            )
            return False

    def format_response(
        self, persona: PersonaConfig, template_name: str, **kwargs
    ) -> str:
        """
        使用指定人格格式化响应

        Args:
            persona: 人格配置
            template_name: 模板名称
            **kwargs: 模板变量

        Returns:
            str: 格式化后的响应文本
        """
        if not persona:
            return "[系统错误：无法获取人格配置]"

        base_response = persona.get_template(template_name, **kwargs)

        style = persona.style_overrides
        emoji_density = style.get("emoji_density", "medium")

        if emoji_density == "high" and not any(
            c in base_response for c in ["💡", "🔥", "✨", "📊"]
        ):
            emojis = ["✨", "💡", "🎯", "⚡", "🚀"]
            import random

            base_response += f" {random.choice(emojis)}"  # nosec B311 - non-crypto emoji selection

        return base_response

    def get_greeting(
        self, user_id: str = None, business_type: BusinessType = None
    ) -> str:
        """获取问候语"""
        persona = self.get_persona(user_id=user_id, business_type=business_type)
        if persona:
            return self.format_response(persona, "greeting")
        return "你好！我是你的AI助手，有什么可以帮你的吗？😊"

    def get_task_acceptance(
        self,
        user_id: str = None,
        business_type: BusinessType = None,
        task_description: str = "",
    ) -> str:
        """获取任务接受响应"""
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
        """获取任务完成消息"""
        persona = self.get_persona(user_id=user_id, business_type=business_type)
        if persona:
            return self.format_response(persona, "complete", deliverable=deliverable)
        return f"完成了！这是你的{deliverable}。"

    def list_available_personas(self) -> List[Dict[str, Any]]:
        """列出所有可用的人格变体"""
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
        """获取人格管理器的统计信息"""
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
        清除缓存

        Args:
            user_id: 如果提供，只清除该用户的缓存；否则清除所有缓存
        """
        if user_id:
            if user_id in self._cache:
                del self._cache[user_id]
                print(f"[PersonaManager] 已清除用户{user_id}的缓存")
        else:
            self._cache.clear()
            print(f"[PersonaManager] 已清除所有缓存")


if __name__ == "__main__":
    manager = PersonaManager()

    print("=" * 60)
    print("OPC-Agents 人格管理器 v1.0")
    print("=" * 60)

    stats = manager.get_statistics()
    print(f"\n📊 统计信息:")
    print(f"   总变体数: {stats['total_variants']}")
    print(f"   缓存用户数: {stats['cached_users']}")
    print(f"   基础人格: {stats['base_persona_name']}")
    print(f"   配置版本: {stats['config_version']}")

    print(f"\n📋 可用人格列表:")
    personas = manager.list_available_personas()
    for p in personas:
        print(f"   [{p['emoji']}] {p['display_name']} ({p['id']})")

    test_users = [
        ("user_001_content", BusinessType.CONTENT_CREATOR),
        ("user_002_digital", BusinessType.DIGITAL_PRODUCT),
        ("user_003_ecommerce", BusinessType.ECOMMERCE),
    ]

    print("\n" + "=" * 60)
    print("🧪 功能测试")
    print("=" * 60)

    for user_id, btype in test_users:
        print(f"\n--- 测试用户: {user_id} (类型: {btype.value}) ---")

        persona = manager.get_persona(user_id=user_id, business_type=btype)
        if persona:
            print(f"✅ 加载成功: {persona.display_name} {persona.emoji}")

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
            print("❌ 加载失败")

    print("\n" + "=" * 60)
    print("🔄 人格切换测试")
    print("=" * 60)

    test_user = "test_switch_user"
    manager.get_persona(user_id=test_user, business_type=BusinessType.CONTENT_CREATOR)
    print(
        f"\n初始状态: {manager._cache.get(test_user).display_name if test_user in manager._cache else 'None'}"
    )

    success = manager.switch_persona(
        test_user, BusinessType.ECOMMERCE, reason="测试切换"
    )
    print(f"切换结果: {'成功 ✅' if success else '失败 ❌'}")

    current = manager._cache.get(test_user)
    if current:
        print(f"当前人格: {current.display_name} {current.emoji}")

    final_stats = manager.get_statistics()
    print(f"\n最终统计: 缓存用户数 = {final_stats['cached_users']}")
