"""
Business Type Enum Definitions - Unified Version

6 business types corresponding to the "One-Person Company Six Types" framework.
All modules should import BusinessType from here to avoid duplicate definition comparison issues.
"""

from enum import Enum


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
    def from_string(cls, type_str: str):
        """Convert string to enum value"""
        for bt in cls:
            if bt.value == type_str:
                return bt
        return None

    @property
    def display_name(self) -> str:
        """Get display name"""
        names = {
            self.CONTENT_CREATOR: "内容创作者",
            self.DIGITAL_PRODUCT: "数字产品开发者",
            self.AI_TOOL_BUILDER: "AI工具开发者",
            self.CONSULTANT: "专业咨询师",
            self.ECOMMERCE: "电商运营者",
            self.CREATIVE_WORK: "创意工作者",
        }
        return names.get(self, self.value)

    @property
    def emoji(self) -> str:
        """Get corresponding emoji icon"""
        emojis = {
            self.CONTENT_CREATOR: "",
            self.DIGITAL_PRODUCT: "",
            self.AI_TOOL_BUILDER: "",
            self.CONSULTANT: "",
            self.ECOMMERCE: "",
            self.CREATIVE_WORK: "",
        }
        return emojis.get(self, "")
