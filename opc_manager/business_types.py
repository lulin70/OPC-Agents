"""
业务类型枚举定义 - 统一版本

6大业务类型，对应"一人公司六大类型"框架
所有模块应从此处导入BusinessType，避免重复定义导致的比较问题
"""

from enum import Enum


class BusinessType(Enum):
    """6大业务类型枚举 - 对应一人公司六大类型"""

    CONTENT_CREATOR = "content_creator"  # ① 内容创作
    DIGITAL_PRODUCT = "digital_product"  # ② 数字产品
    AI_TOOL_BUILDER = "ai_tool_builder"  # ③ AI工具
    CONSULTANT = "consultant"  # ④ 专业咨询
    ECOMMERCE = "ecommerce"  # ⑤ 电商运营
    CREATIVE_WORK = "creative_work"  # ⑥ 创意生产

    @classmethod
    def get_all_types(cls) -> list:
        """获取所有业务类型列表"""
        return list(cls)

    @classmethod
    def from_string(cls, type_str: str):
        """从字符串转换为枚举值"""
        for bt in cls:
            if bt.value == type_str:
                return bt
        return None

    @property
    def display_name(self) -> str:
        """获取显示名称"""
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
        """获取对应的emoji图标"""
        emojis = {
            self.CONTENT_CREATOR: "✍️",
            self.DIGITAL_PRODUCT: "💰",
            self.AI_TOOL_BUILDER: "🤖",
            self.CONSULTANT: "💼",
            self.ECOMMERCE: "🛒",
            self.CREATIVE_WORK: "🎨",
        }
        return emojis.get(self, "📌")
