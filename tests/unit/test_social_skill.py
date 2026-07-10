"""social_skill 模块单元测试

覆盖平台配置、内容生成、草稿管理、发布标记、主题提取、撤销发布。
"""

import json
import os
import threading
from unittest.mock import patch, MagicMock

import pytest

from opc_manager.social_skill import (
    PLATFORMS,
    _extract_topic,
    _generate_body,
    _generate_tags,
    _generate_title,
    _get_publish_guide,
    execute_goal,
    generate_content,
    list_drafts,
    mark_published,
    undo_publish_content,
)


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR to tmp_path so tests never touch real data."""
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    monkeypatch.setenv("OPC_DATA_DIR", data_dir)
    import opc_manager.data_manager as dm

    monkeypatch.setattr(dm, "DATA_DIR", data_dir)
    monkeypatch.setattr(dm, "DB_PATH", os.path.join(data_dir, "opc_data.db"))
    monkeypatch.setattr(dm, "BACKUP_DIR", os.path.join(data_dir, "backups"))
    monkeypatch.setattr(dm, "_db_initialized", False)
    monkeypatch.setattr(dm, "_local", threading.local())
    dm._local.conn = None
    dm.init_db()
    return data_dir


# ---------------------------------------------------------------------------
# 纯函数测试 — 不需要 DB
# ---------------------------------------------------------------------------


class TestGenerateTitle:
    """_generate_title 测试"""

    def test_xiaohongshu(self):
        cfg = PLATFORMS["小红书"]
        title = _generate_title("小红书", "AI运营", cfg)
        assert "AI运营" in title
        assert "全攻略" in title

    def test_gongzhonghao(self):
        cfg = PLATFORMS["公众号"]
        title = _generate_title("公众号", "创业", cfg)
        assert "深度解析" in title
        assert "创业" in title

    def test_zhihu(self):
        cfg = PLATFORMS["知乎"]
        title = _generate_title("知乎", "增长黑客", cfg)
        assert "增长黑客" in title
        assert "实战经验" in title

    def test_twitter_returns_empty(self):
        cfg = PLATFORMS["推特"]
        assert _generate_title("推特", "topic", cfg) == ""

    def test_weibo_returns_empty(self):
        cfg = PLATFORMS["微博"]
        assert _generate_title("微博", "topic", cfg) == ""

    def test_unknown_platform(self):
        cfg = {"max_body": 2000}
        title = _generate_title("未知平台", "测试主题", cfg)
        assert "测试主题" in title
        assert "一人公司" in title


class TestGenerateBody:
    """_generate_body 测试"""

    def test_xiaohongshu_body(self):
        cfg = PLATFORMS["小红书"]
        body = _generate_body("小红书", "AI运营", "要点1、要点2", "种草风", cfg)
        assert "AI运营" in body
        assert "要点1" in body
        assert len(body) <= cfg["max_body"]

    def test_xiaohongshu_default_points(self):
        cfg = PLATFORMS["小红书"]
        body = _generate_body("小红书", "测试", "", "种草风", cfg)
        assert "核心要点" in body

    def test_gongzhonghao_body(self):
        cfg = PLATFORMS["公众号"]
        body = _generate_body("公众号", "创业", "管理、增长", "专业", cfg)
        assert "# 创业" in body
        assert "管理" in body

    def test_twitter_body_truncated(self):
        cfg = PLATFORMS["推特"]
        long_points = "、".join([f"要点{i}" for i in range(20)])
        body = _generate_body("推特", "topic", long_points, "简洁", cfg)
        assert len(body) <= cfg["max_body"]

    def test_weibo_body(self):
        cfg = PLATFORMS["微博"]
        body = _generate_body("微博", "话题", "点1、点2", "互动", cfg)
        assert "#话题#" in body
        assert "点1" in body

    def test_zhihu_body(self):
        cfg = PLATFORMS["知乎"]
        body = _generate_body("知乎", "方法论", "核心", "干货", cfg)
        assert "# 方法论" in body

    def test_unknown_platform_returns_topic(self):
        cfg = {"max_body": 2000}
        body = _generate_body("未知", "我的主题", "", "风格", cfg)
        assert body == "我的主题"


class TestGenerateTags:
    """_generate_tags 测试"""

    def test_xiaohongshu_tags(self):
        tags = _generate_tags("小红书", "AI")
        assert "AI" in tags
        assert "一人公司" in tags
        assert "创业日记" in tags

    def test_weibo_tags_prefixed(self):
        tags = _generate_tags("微博", "话题")
        assert all(t.startswith("#") for t in tags)
        assert any("话题" in t for t in tags)

    def test_twitter_tags_no_space(self):
        tags = _generate_tags("推特", "AI Tech")
        assert any("AITech" in t.replace("#", "") for t in tags)

    def test_generic_tags(self):
        tags = _generate_tags("未知平台", "测试")
        assert "测试" in tags
        assert "一人公司" in tags

    def test_max_six_tags(self):
        tags = _generate_tags("小红书", "主题")
        assert len(tags) <= 6


class TestGetPublishGuide:
    """_get_publish_guide 测试"""

    def test_known_platforms(self):
        for platform in ["小红书", "公众号", "推特", "微博", "知乎"]:
            guide = _get_publish_guide(platform)
            assert len(guide) > 0
            assert platform in guide or "手动" not in guide

    def test_unknown_platform(self):
        guide = _get_publish_guide("未知平台")
        assert "手动" in guide


class TestExtractTopic:
    """_extract_topic 测试"""

    def test_extract_with_chinese_quotes(self):
        topic = _extract_topic("帮我发一篇关于「AI运营」的内容到小红书", "小红书")
        assert topic == "AI运营"

    def test_extract_with_double_quotes(self):
        topic = _extract_topic('帮我写一篇关于"创业"的公众号文章', "公众号")
        assert topic == "创业"

    def test_extract_no_quotes_strips_keywords(self):
        topic = _extract_topic("帮我发小红书AI运营", "小红书")
        assert "AI运营" in topic

    def test_extract_empty_falls_back(self):
        topic = _extract_topic("帮我发小红书的内容", "小红书")
        assert topic == "今日分享"


# ---------------------------------------------------------------------------
# 数据库函数测试
# ---------------------------------------------------------------------------


class TestGenerateContent:
    """generate_content 测试"""

    def test_unsupported_platform(self):
        result = generate_content("Facebook", "话题")
        assert result["success"] is False
        assert "不支持的平台" in result["error"]

    def test_generates_and_saves(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            result = generate_content("小红书", "AI运营", "要点1、要点2", "种草风")
        assert result["success"] is True
        assert result["platform"] == "小红书"
        assert "AI运营" in result["title"]
        assert result["status"] == "draft"
        assert "publish_guide" in result

    def test_with_llm_result(self):
        llm_result = {
            "title": "LLM标题",
            "body": "LLM正文内容",
            "tags": ["标签1", "标签2"],
        }
        with patch(
            "opc_manager.social_skill._generate_with_llm", return_value=llm_result
        ):
            result = generate_content("小红书", "AI", "要点", "种草")
        assert result["success"] is True
        assert result["title"] == "LLM标题"
        assert result["body"] == "LLM正文内容"
        assert result["tags"] == ["标签1", "标签2"]

    def test_platform_without_tags(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            result = generate_content("公众号", "创业", "", "")
        assert result["success"] is True
        assert result["tags"] == []

    def test_strips_platform_whitespace(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            result = generate_content("  小红书  ", "AI", "", "")
        assert result["success"] is True
        assert result["platform"] == "小红书"


class TestListDrafts:
    """list_drafts 测试"""

    def test_empty(self):
        result = list_drafts()
        assert result["success"] is True
        assert result["count"] == 0
        assert result["drafts"] == []

    def test_lists_all_drafts(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            generate_content("小红书", "话题A", "", "")
            generate_content("微博", "话题B", "", "")
        result = list_drafts()
        assert result["count"] == 2

    def test_filter_by_platform(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            generate_content("小红书", "话题A", "", "")
            generate_content("微博", "话题B", "", "")
        result = list_drafts(platform="小红书")
        assert result["count"] == 1
        assert result["drafts"][0]["platform"] == "小红书"

    def test_excludes_published(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            gen = generate_content("小红书", "话题", "", "")
            mark_published(gen["id"])
        result = list_drafts()
        assert result["count"] == 0

    def test_tags_parsed_as_list(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            generate_content("小红书", "话题", "", "")
        result = list_drafts()
        assert isinstance(result["drafts"][0]["tags"], list)


class TestMarkPublished:
    """mark_published 测试"""

    def test_nonexistent(self):
        result = mark_published("nonexistent-id")
        assert result["success"] is False
        assert "不存在" in result["error"]

    def test_marks_published(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            gen = generate_content("小红书", "话题", "", "")
        result = mark_published(gen["id"])
        assert result["success"] is True
        assert "已发布" in result["message"]


class TestUndoPublishContent:
    """undo_publish_content 测试"""

    def test_no_published_content(self):
        result = undo_publish_content()
        assert result["success"] is False
        assert "未找到" in result["error"]

    def test_undo_by_id(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            gen = generate_content("小红书", "话题", "", "")
            mark_published(gen["id"])
        result = undo_publish_content(content_id=gen["id"])
        assert result["success"] is True
        assert "撤回" in result["message"]

    def test_undo_latest(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            gen = generate_content("微博", "话题", "", "")
            mark_published(gen["id"])
        result = undo_publish_content()
        assert result["success"] is True

    def test_undo_reverts_to_draft(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            gen = generate_content("小红书", "话题", "", "")
            mark_published(gen["id"])
        undo_publish_content(content_id=gen["id"])
        drafts = list_drafts()
        assert drafts["count"] == 1


# ---------------------------------------------------------------------------
# execute_goal 路由测试
# ---------------------------------------------------------------------------


class TestExecuteGoal:
    """execute_goal 测试"""

    def test_no_platform_with_publish_keyword(self):
        result = execute_goal("帮我发一篇内容")
        assert result["success"] is False
        assert "请指定发布平台" in result["error"]
        assert "available_platforms" in result

    def test_list_drafts_route(self):
        result = execute_goal("小红书草稿列表")
        assert result["success"] is True
        assert "drafts" in result

    def test_generate_content_route(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            result = execute_goal("帮我发一篇小红书关于「AI运营」的内容")
        assert result["success"] is True
        assert result["platform"] == "小红书"

    def test_publish_route_with_topic(self):
        with patch("opc_manager.social_skill._generate_with_llm", return_value=None):
            generate_content("小红书", "AI运营", "", "")
        result = execute_goal("小红书AI运营发布完成")
        assert result["success"] is True

    def test_publish_route_no_match(self):
        result = execute_goal("小红书未知话题已发布")
        assert result["success"] is False
        assert "内容ID" in result["error"] or "更明确" in result["error"]


# ---------------------------------------------------------------------------
# _generate_with_llm 测试
# ---------------------------------------------------------------------------


class TestGenerateWithLlm:
    """_generate_with_llm 测试"""

    def test_returns_none_when_service_unavailable(self):
        from opc_manager.social_skill import _generate_with_llm

        with patch("opc_manager.simple_llm_service.SimpleLLMService") as MockSvc:
            instance = MagicMock()
            instance.is_available.return_value = False
            MockSvc.return_value = instance
            result = _generate_with_llm("小红书", "话题", "", "")
        assert result is None

    def test_returns_parsed_result(self):
        from opc_manager.social_skill import _generate_with_llm

        llm_response = json.dumps(
            {"title": "LLM标题", "body": "LLM正文", "tags": ["标签"]}
        )
        with patch("opc_manager.simple_llm_service.SimpleLLMService") as MockSvc:
            instance = MagicMock()
            instance.is_available.return_value = True
            instance.complete.return_value = llm_response
            MockSvc.return_value = instance
            result = _generate_with_llm("小红书", "话题", "要点", "种草")
        assert result is not None
        assert result["title"] == "LLM标题"
        assert result["body"] == "LLM正文"

    def test_returns_none_on_invalid_json(self):
        from opc_manager.social_skill import _generate_with_llm

        with patch("opc_manager.simple_llm_service.SimpleLLMService") as MockSvc:
            instance = MagicMock()
            instance.is_available.return_value = True
            instance.complete.return_value = "not json"
            MockSvc.return_value = instance
            result = _generate_with_llm("小红书", "话题", "", "")
        assert result is None

    def test_returns_none_on_import_error(self):
        from opc_manager.social_skill import _generate_with_llm

        with patch(
            "opc_manager.simple_llm_service.SimpleLLMService",
            side_effect=ImportError("no module"),
        ):
            result = _generate_with_llm("小红书", "话题", "", "")
        assert result is None
