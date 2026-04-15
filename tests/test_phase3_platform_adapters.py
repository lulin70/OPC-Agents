"""Phase 3: 外部平台适配器测试"""
import pytest
import asyncio
from opc_manager.platform_adapters import (
    PlatformType, PlatformAdapter, MockXiaohongshuAdapter,
    MockGumroadAdapter, AdapterFactory
)


class TestPlatformAdapterBase:
    """适配器基类接口测试"""

    def test_xiaohongshu_adapter_type(self):
        adapter = MockXiaohongshuAdapter()
        assert adapter.platform_type == PlatformType.XIAOHONGSHU

    def test_gumroad_adapter_type(self):
        adapter = MockGumroadAdapter()
        assert adapter.platform_type == PlatformType.GUMROAD


class TestMockXiaohongshuAdapter:
    """小红书 Mock 适配器测试"""

    @pytest.fixture
    def xhs_adapter(self):
        return MockXiaohongshuAdapter()

    @pytest.mark.asyncio
    async def test_fetch_hot_topics_default_count(self, xhs_adapter):
        topics = await xhs_adapter.fetch_hot_topics(limit=10)
        assert len(topics) == 10
        for topic in topics:
            assert "title" in topic
            assert "heat" in topic
            assert "category" in topic

    @pytest.mark.asyncio
    async def test_fetch_hot_topics_filtered_by_category(self, xhs_adapter):
        topics = await xhs_adapter.fetch_hot_topics(category="时尚", limit=5)
        for topic in topics:
            assert topic["category"] == "时尚"

    @pytest.mark.asyncio
    async def test_fetch_user_data_structure(self, xhs_adapter):
        data = await xhs_adapter.fetch_user_data({"cookie": "test"})
        assert "followers" in data
        assert "notes_count" in data
        assert data["followers"] > 0

    def test_validate_credentials_mock_mode(self, xhs_adapter):
        ok, msg = xhs_adapter.validate_credentials({})
        assert ok is True

    @pytest.mark.asyncio
    async def test_fetch_with_fallback_success(self, xhs_adapter):
        result = await xhs_adapter.fetch_with_fallback(xhs_adapter.fetch_hot_topics, limit=3)
        assert isinstance(result, list)
        assert len(result) <= 3


class TestMockGumroadAdapter:
    """Gumroad Mock 适配器测试"""

    @pytest.fixture
    def gumroad_adapter(self):
        return MockGumroadAdapter()

    @pytest.mark.asyncio
    async def test_fetch_sales_data(self, gumroad_adapter):
        data = await gumroad_adapter.fetch_user_data({"token": "test"})
        assert "total_sales" in data
        assert "products_count" in data
        assert data["products_count"] >= 1

    @pytest.mark.asyncio
    async def test_fetch_hot_topics(self, gumroad_adapter):
        topics = await gumroad_adapter.fetch_hot_topics(limit=5)
        assert len(topics) == 5
        for t in topics:
            assert "sales" in t


class TestAdapterFactory:
    """适配器工厂测试"""

    def setup_method(self):
        AdapterFactory.clear_cache()

    def test_get_mock_xiaohongshu_adapter(self):
        adapter = AdapterFactory.get_adapter(PlatformType.XIAOHONGSHU, use_mock=True)
        assert isinstance(adapter, MockXiaohongshuAdapter)

    def test_get_mock_gumroad_adapter(self):
        adapter = AdapterFactory.get_adapter(PlatformType.GUMROAD, use_mock=True)
        assert isinstance(adapter, MockGumroadAdapter)

    def test_real_adapter_not_implemented(self):
        with pytest.raises((NotImplementedError, ValueError)):
            AdapterFactory.get_adapter(PlatformType.XIAOHONGSHU, use_mock=False)

    def test_caching_same_instance(self):
        a1 = AdapterFactory.get_adapter(PlatformType.GUMROAD)
        a2 = AdapterFactory.get_adapter(PlatformType.GUMROAD)
        assert a1 is a2

    def test_clear_cache(self):
        AdapterFactory.get_adapter(PlatformType.XIAOHONGSHU)
        AdapterFactory.clear_cache()
        assert len(AdapterFactory._adapters) == 0
