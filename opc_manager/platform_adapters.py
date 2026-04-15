"""外部平台适配器 - PlatformAdapter 抽象层 (Phase 3)"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum
import asyncio
import random
import time
import logging

logger = logging.getLogger(__name__)


class PlatformType(Enum):
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    GUMROAD = "gumroad"
    BILIBILI = "bilibili"
    WECHAT = "wechat"


@dataclass
class PlatformData:
    platform: PlatformType
    data_type: str
    raw_data: Dict[str, Any]
    fetched_at: float
    is_mock: bool = False
    cache_ttl: int = 3600


class PlatformAdapter(ABC):
    """外部平台数据适配器抽象基类"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._cache: Dict[str, tuple] = {}

    @property
    @abstractmethod
    def platform_type(self) -> PlatformType:
        pass

    @abstractmethod
    async def fetch_hot_topics(self, category: str = None, limit: int = 10) -> List[Dict]:
        pass

    @abstractmethod
    async def fetch_user_data(self, user_credentials: dict) -> Dict:
        pass

    @abstractmethod
    def validate_credentials(self, credentials: dict) -> tuple:
        pass

    async def fetch_with_fallback(self, func, *args, **kwargs):
        """带降级策略的数据获取"""
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            logger.warning(f"[{self.platform_type.value}] API调用失败: {e}，启用Mock降级")
            return await self._fallback_response(func.__name__)

    async def _fallback_response(self, func_name: str):
        """降级响应"""
        if func_name == "fetch_hot_topics":
            return await self.fetch_hot_topics()
        elif func_name == "fetch_user_data":
            return await self.fetch_user_data({})
        return {}


class MockXiaohongshuAdapter(PlatformAdapter):
    """小红书 Mock 适配器"""

    MOCK_TOPICS = [
        {"title": "春季穿搭OOTD", "heat": 98500, "category": "时尚", "url": ""},
        {"title": "居家办公好物分享", "heat": 78200, "category": "生活", "url": ""},
        {"title": "减脂餐食谱合集", "heat": 65400, "category": "美食", "url": ""},
        {"title": "AI工具效率提升", "heat": 54300, "category": "科技", "url": ""},
        {"title": "副业赚钱方法", "heat": 48900, "category": "职场", "url": ""},
        {"title": "旅行摄影攻略", "heat": 42100, "category": "旅行", "url": ""},
        {"title": "读书笔记分享", "heat": 38700, "category": "学习", "url": ""},
        {"title": "护肤步骤详解", "heat": 35600, "category": "美妆", "url": ""},
        {"title": "健身打卡记录", "heat": 29800, "category": "运动", "url": ""},
        {"title": "数码产品测评", "heat": 25400, "category": "科技", "url": ""},
    ]

    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.XIAOHONGSHU

    async def fetch_hot_topics(self, category: str = None, limit: int = 10) -> List[Dict]:
        topics = list(self.MOCK_TOPICS)
        if category:
            topics = [t for t in topics if t["category"] == category]
        await asyncio.sleep(random.uniform(0.05, 0.15))
        return topics[:limit]

    async def fetch_user_data(self, user_credentials: dict) -> Dict:
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return {
            "followers": random.randint(1000, 100000),
            "notes_count": random.randint(50, 500),
            "avg_likes": random.randint(100, 10000),
            "engagement_rate": round(random.uniform(0.02, 0.15), 4),
            "platform": "xiaohongshu",
        }

    def validate_credentials(self, credentials: dict) -> tuple:
        return True, "Mock模式，始终有效"


class MockGumroadAdapter(PlatformAdapter):
    """Gumroad Mock 适配器"""

    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.GUMROAD

    async def fetch_hot_topics(self, category: str = None, limit: int = 10) -> List[Dict]:
        await asyncio.sleep(random.uniform(0.05, 0.15))
        return [{"title": f"Gumroad热门数字产品-{i}", "sales": random.randint(10, 1000)} for i in range(limit)]

    async def fetch_user_data(self, user_credentials: dict) -> Dict:
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return {
            "total_sales": round(random.uniform(1000, 50000), 2),
            "products_count": random.randint(1, 20),
            "customers": random.randint(50, 2000),
            "revenue_mtd": round(random.uniform(500, 5000), 2),
            "platform": "gumroad",
        }

    def validate_credentials(self, credentials: dict) -> tuple:
        return True, "Mock模式，始终有效"


class AdapterFactory:
    """适配器工厂 - 单例缓存"""

    _adapters: Dict[str, PlatformAdapter] = {}

    @classmethod
    def get_adapter(cls, platform: PlatformType, use_mock: bool = True, config: dict = None) -> PlatformAdapter:
        cache_key = f"{platform.value}_{'mock' if use_mock else 'real'}"

        if cache_key not in cls._adapters:
            if use_mock:
                adapter_map = {
                    PlatformType.XIAOHONGSHU: MockXiaohongshuAdapter,
                    PlatformType.GUMROAD: MockGumroadAdapter,
                }
                adapter_cls = adapter_map.get(platform)
                if adapter_cls is None:
                    raise ValueError(f"No mock adapter available for platform: {platform.value}")
                cls._adapters[cache_key] = adapter_cls(config)
            else:
                raise NotImplementedError(f"真实 {platform.value} 适配器尚未实现（Phase 4）")

        return cls._adapters[cache_key]

    @classmethod
    def clear_cache(cls):
        """清除适配器缓存（用于测试）"""
        cls._adapters.clear()
