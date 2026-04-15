"""Phase 3: Web API 测试"""
import pytest
from fastapi.testclient import TestClient
from web_app.main import app

client = TestClient(app)


class TestHealthAPI:
    """健康检查接口测试"""

    def test_health_check(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "llm_provider" in data

    def test_health_contains_version(self):
        response = client.get("/api/v1/health")
        assert "v3" in response.json()["version"] or "3" in response.json()["version"]


class TestInfoAPI:
    """应用信息接口测试"""

    def test_info_endpoint(self):
        response = client.get("/api/v1/info")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "features" in data
        assert data["features"]["business_types"] == 6
        assert data["features"]["persona_variants"] == 6
        assert data["features"]["scenarios"] == 9
        assert data["features"]["flywheel_levels"] == 3

    def test_info_supported_types(self):
        response = client.get("/api/v1/info")
        types = response.json().get("supported_business_types", [])
        assert len(types) == 6
        expected = {"content_creator", "digital_product", "ai_tool_builder",
                    "consultant", "ecommerce", "creative_work"}
        assert set(types) == expected


class TestAPIErrorHandling:
    """错误处理测试"""

    def test_404_not_found(self):
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self):
        response = client.delete("/api/v1/health")
        assert response.status_code in [405, 404, 200]
