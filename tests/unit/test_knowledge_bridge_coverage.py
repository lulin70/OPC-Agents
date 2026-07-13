"""KnowledgeBridge 覆盖率补充测试

覆盖 LocalFolderAdapter（tmpdir 真实文件）、ObsidianAdapter、
KnowledgeBridge adapter 选择、search/build_knowledge_prompt/get_status、
_urlopen_with_timeout 异常路径、singleton 等。
"""

import json
import os
import socket
import urllib.error
from unittest.mock import patch

import pytest

from opc_manager.knowledge_bridge import (
    KnowledgeBridge,
    KnowledgeEntry,
    LocalFolderAdapter,
    ObsidianAdapter,
    YuqueAdapter,
    FeishuAdapter,
    NotionAdapter,
    SiYuanAdapter,
    get_knowledge_bridge,
)


@pytest.fixture
def kb_folder(tmp_path):
    """创建临时知识库文件夹，含 3 个 markdown 文件。"""
    (tmp_path / "笔记1.md").write_text(
        "# 笔记1\n\n这是营销策略笔记 #营销 #策略", encoding="utf-8"
    )
    (tmp_path / "plan.txt").write_text("产品发布计划 #产品 #发布", encoding="utf-8")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "deep.md").write_text("深度内容 竞品分析 #竞品", encoding="utf-8")
    # 隐藏目录应被跳过
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.md").write_text("should not appear", encoding="utf-8")
    return str(tmp_path)


class TestLocalFolderAdapter:
    """覆盖 LocalFolderAdapter 核心逻辑。"""

    def test_init_builds_index(self, kb_folder):
        adapter = LocalFolderAdapter(kb_folder)
        assert len(adapter._index) == 3  # 3 files (hidden excluded)

    def test_search_by_title(self, kb_folder):
        adapter = LocalFolderAdapter(kb_folder)
        results = adapter.search("笔记", max_results=5)
        assert len(results) > 0
        assert any("笔记1" in r.title for r in results)

    def test_search_by_content(self, kb_folder):
        adapter = LocalFolderAdapter(kb_folder)
        results = adapter.search("竞品", max_results=5)
        assert len(results) > 0

    def test_search_by_tag(self, kb_folder):
        adapter = LocalFolderAdapter(kb_folder)
        results = adapter.search("营销", max_results=5)
        assert len(results) > 0

    def test_search_no_match(self, kb_folder):
        adapter = LocalFolderAdapter(kb_folder)
        results = adapter.search("zzznonexistent", max_results=5)
        assert len(results) == 0

    def test_search_respects_max_results(self, kb_folder):
        adapter = LocalFolderAdapter(kb_folder)
        results = adapter.search("笔记", max_results=1)
        assert len(results) <= 1

    def test_get_status(self, kb_folder):
        adapter = LocalFolderAdapter(kb_folder)
        status = adapter.get_status()
        assert status["type"] == "local"
        assert status["available"] is True
        assert status["file_count"] == 3

    def test_list_sources(self, kb_folder):
        adapter = LocalFolderAdapter(kb_folder)
        sources = adapter.list_sources()
        assert len(sources) == 3
        for s in sources:
            assert os.path.isfile(s)

    def test_init_nonexistent_path(self, tmp_path):
        adapter = LocalFolderAdapter(str(tmp_path / "nonexistent"))
        assert len(adapter._index) == 0
        status = adapter.get_status()
        assert status["available"] is False

    def test_search_returns_knowledge_entry(self, kb_folder):
        adapter = LocalFolderAdapter(kb_folder)
        results = adapter.search("笔记", max_results=5)
        for r in results:
            assert isinstance(r, KnowledgeEntry)
            assert r.source_type == "local"
            assert r.relevance_score > 0


class TestObsidianAdapter:
    """覆盖 ObsidianAdapter。"""

    def test_init_without_config(self, kb_folder):
        adapter = ObsidianAdapter(kb_folder)
        assert adapter._obsidian_config == {}
        status = adapter.get_status()
        assert status["type"] == "obsidian"
        assert status["has_obsidian_config"] is False

    def test_init_with_config(self, kb_folder):
        obsidian_dir = os.path.join(kb_folder, ".obsidian")
        os.makedirs(obsidian_dir)
        config_path = os.path.join(obsidian_dir, "app.json")
        with open(config_path, "w") as f:
            json.dump({"theme": "dark"}, f)

        adapter = ObsidianAdapter(kb_folder)
        assert adapter._obsidian_config == {"theme": "dark"}
        status = adapter.get_status()
        assert status["has_obsidian_config"] is True

    def init_with_invalid_config(self, kb_folder):
        obsidian_dir = os.path.join(kb_folder, ".obsidian")
        os.makedirs(obsidian_dir)
        config_path = os.path.join(obsidian_dir, "app.json")
        with open(config_path, "w") as f:
            f.write("invalid json {")

        adapter = ObsidianAdapter(kb_folder)
        assert adapter._obsidian_config == {}

    def test_search_sets_source_type(self, kb_folder):
        adapter = ObsidianAdapter(kb_folder)
        results = adapter.search("笔记", max_results=5)
        for r in results:
            assert r.source_type == "obsidian"


class TestKnowledgeBridge:
    """覆盖 KnowledgeBridge adapter 选择与接口。"""

    def test_init_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("OPC_KB_ENABLED", raising=False)
        kb = KnowledgeBridge()
        assert kb.enabled is False

    def test_init_enabled_local(self, monkeypatch, kb_folder):
        monkeypatch.setenv("OPC_KB_ENABLED", "true")
        monkeypatch.setenv("OPC_KB_TYPE", "local")
        monkeypatch.setenv("OPC_KB_PATH", kb_folder)
        kb = KnowledgeBridge()
        assert kb.enabled is True
        assert kb.kb_type == "local"

    def test_init_enabled_obsidian(self, monkeypatch, kb_folder):
        monkeypatch.setenv("OPC_KB_ENABLED", "true")
        monkeypatch.setenv("OPC_KB_TYPE", "obsidian")
        monkeypatch.setenv("OPC_KB_PATH", kb_folder)
        kb = KnowledgeBridge()
        assert kb.enabled is True

    def test_init_unknown_type(self, monkeypatch):
        monkeypatch.setenv("OPC_KB_ENABLED", "true")
        monkeypatch.setenv("OPC_KB_TYPE", "unknown_type")
        kb = KnowledgeBridge()
        assert kb.enabled is False

    def test_search_disabled_returns_empty(self, monkeypatch):
        monkeypatch.delenv("OPC_KB_ENABLED", raising=False)
        kb = KnowledgeBridge()
        assert kb.search("test") == []

    def test_search_enabled(self, monkeypatch, kb_folder):
        monkeypatch.setenv("OPC_KB_ENABLED", "true")
        monkeypatch.setenv("OPC_KB_TYPE", "local")
        monkeypatch.setenv("OPC_KB_PATH", kb_folder)
        kb = KnowledgeBridge()
        results = kb.search("笔记")
        assert len(results) > 0

    def test_build_knowledge_prompt_disabled(self, monkeypatch):
        monkeypatch.delenv("OPC_KB_ENABLED", raising=False)
        kb = KnowledgeBridge()
        assert kb.build_knowledge_prompt("test") == ""

    def test_build_knowledge_prompt_enabled(self, monkeypatch, kb_folder):
        monkeypatch.setenv("OPC_KB_ENABLED", "true")
        monkeypatch.setenv("OPC_KB_TYPE", "local")
        monkeypatch.setenv("OPC_KB_PATH", kb_folder)
        kb = KnowledgeBridge()
        prompt = kb.build_knowledge_prompt("笔记")
        assert "[知识库参考]" in prompt

    def test_build_knowledge_prompt_no_results(self, monkeypatch, kb_folder):
        monkeypatch.setenv("OPC_KB_ENABLED", "true")
        monkeypatch.setenv("OPC_KB_TYPE", "local")
        monkeypatch.setenv("OPC_KB_PATH", kb_folder)
        kb = KnowledgeBridge()
        prompt = kb.build_knowledge_prompt("zzznonexistent")
        assert prompt == ""

    def test_get_status_disabled(self, monkeypatch):
        monkeypatch.delenv("OPC_KB_ENABLED", raising=False)
        kb = KnowledgeBridge()
        status = kb.get_status()
        assert status["enabled"] is False
        assert status["available"] is False

    def test_get_status_enabled(self, monkeypatch, kb_folder):
        monkeypatch.setenv("OPC_KB_ENABLED", "true")
        monkeypatch.setenv("OPC_KB_TYPE", "local")
        monkeypatch.setenv("OPC_KB_PATH", kb_folder)
        kb = KnowledgeBridge()
        status = kb.get_status()
        assert status["enabled"] is True


class TestKnowledgeBridgeSingleton:
    """覆盖 get_knowledge_bridge singleton。"""

    def test_singleton(self, monkeypatch):
        import opc_manager.knowledge_bridge as mod

        monkeypatch.delenv("OPC_KB_ENABLED", raising=False)
        mod._instance = None
        kb1 = get_knowledge_bridge()
        kb2 = get_knowledge_bridge()
        assert kb1 is kb2
        mod._instance = None


class TestUrwlopenWithTimeout:
    """覆盖 _urlopen_with_timeout 异常路径。"""

    def test_socket_timeout_raises(self):
        adapter = YuqueAdapter(token="fake", repo="fake/repo")
        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            with pytest.raises(socket.timeout):
                adapter._urlopen_with_timeout("http://example.com", timeout=1)

    def test_urlerror_raises(self):
        adapter = YuqueAdapter(token="fake", repo="fake/repo")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with pytest.raises(urllib.error.URLError):
                adapter._urlopen_with_timeout("http://example.com", timeout=1)


class TestYuqueAdapter:
    """覆盖 YuqueAdapter 基本逻辑。"""

    def test_search_not_available(self):
        adapter = YuqueAdapter(token="", repo="")
        assert adapter._available is False
        assert adapter.search("test") == []

    def test_get_status(self):
        adapter = YuqueAdapter(token="fake", repo="fake/repo")
        status = adapter.get_status()
        assert status["type"] == "yuque"

    def test_list_sources(self):
        adapter = YuqueAdapter(token="fake", repo="fake/repo")
        sources = adapter.list_sources()
        assert isinstance(sources, list)


class TestFeishuAdapter:
    def test_get_status(self):
        adapter = FeishuAdapter()
        status = adapter.get_status()
        assert status["type"] == "feishu"

    def test_list_sources(self):
        adapter = FeishuAdapter()
        sources = adapter.list_sources()
        assert isinstance(sources, list)


class TestNotionAdapter:
    def test_get_status(self):
        adapter = NotionAdapter()
        status = adapter.get_status()
        assert status["type"] == "notion"

    def test_list_sources(self):
        adapter = NotionAdapter()
        sources = adapter.list_sources()
        assert isinstance(sources, list)


class TestSiYuanAdapter:
    def test_get_status(self):
        adapter = SiYuanAdapter()
        status = adapter.get_status()
        assert status["type"] == "siyuan"

    def test_list_sources_empty(self):
        adapter = SiYuanAdapter()
        sources = adapter.list_sources()
        assert sources == []

    def test_list_sources_with_box(self):
        adapter = SiYuanAdapter(box_id="2023123123456-abc")
        sources = adapter.list_sources()
        assert len(sources) == 1
        assert "siyuan:" in sources[0]
