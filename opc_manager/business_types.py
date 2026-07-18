"""
Business Type Enum Definitions - Unified Version

6 business types corresponding to the "One-Person Company Six Types" framework.
All modules should import BusinessType from here to avoid duplicate definition comparison issues.
"""

from enum import Enum
from typing import Dict, Optional


class BusinessType(Enum):
    """6 Business Type Enums - Corresponding to One-Person Company Six Types"""

    CONTENT_CREATOR = "content_creator"  # 1. Content Creation
    DIGITAL_PRODUCT = "digital_product"  # 2. Digital Products
    AI_TOOL_BUILDER = "ai_tool_builder"  # 3. AI Tools
    CONSULTANT = "consultant"  # 4. Professional Consulting
    ECOMMERCE = "ecommerce"  # 5. E-commerce Operations
    CREATIVE_WORK = "creative_work"  # 6. Creative Production

    @classmethod
    def get_all_types(cls) -> list:
        """Get all business type list"""
        return list(cls)

    @classmethod
    def from_string(cls, type_str: str) -> Optional["BusinessType"]:
        """Convert string to enum value"""
        for bt in cls:
            if bt.value == type_str:
                return bt
        return None

    @property
    def display_name(self) -> str:
        """Get display name"""
        names: Dict[BusinessType, str] = {
            BusinessType.CONTENT_CREATOR: "内容创作者",
            BusinessType.DIGITAL_PRODUCT: "数字产品开发者",
            BusinessType.AI_TOOL_BUILDER: "AI工具开发者",
            BusinessType.CONSULTANT: "专业咨询师",
            BusinessType.ECOMMERCE: "电商运营者",
            BusinessType.CREATIVE_WORK: "创意工作者",
        }
        return names.get(self, self.value)

    @property
    def emoji(self) -> str:
        """Get corresponding emoji icon"""
        emojis: Dict[BusinessType, str] = {
            BusinessType.CONTENT_CREATOR: "",
            BusinessType.DIGITAL_PRODUCT: "",
            BusinessType.AI_TOOL_BUILDER: "",
            BusinessType.CONSULTANT: "",
            BusinessType.ECOMMERCE: "",
            BusinessType.CREATIVE_WORK: "",
        }
        return emojis.get(self, "")
