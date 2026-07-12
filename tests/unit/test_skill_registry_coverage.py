"""Coverage tests for opc_manager.skill_registry.SkillRegistry

Tests skill registration, discovery, collaboration, and export.
Uses register_builtins=False to test with controlled skill sets.
"""

from unittest.mock import MagicMock

import pytest

from opc_manager.skill_models import Skill, SkillCategory, SkillInput, SkillOutput
from opc_manager.skill_registry import SkillRegistry, SKILL_COLLABORATIONS


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset SkillRegistry singleton between tests for isolation."""
    original_instance = SkillRegistry._instance
    SkillRegistry._instance = None
    yield
    SkillRegistry._instance = original_instance


def _make_skill(
    skill_id="test_skill",
    name="Test Skill",
    category=SkillCategory.UTILITY,
    keywords=None,
    version="1.0.0",
    enabled=True,
    execute=None,
    inputs=None,
):
    if inputs is None:
        inputs = [
            SkillInput(name="goal", type="str", description="Goal", required=True)
        ]
    return Skill(
        skill_id=skill_id,
        name=name,
        description=f"Test skill {skill_id}",
        category=category,
        inputs=inputs,
        outputs=[SkillOutput(name="result", type="dict", description="Result")],
        execute=execute
        or (
            lambda goal="", _context=None, **kw: {
                "success": True,
                "data": {"goal": goal},
            }
        ),
        enabled=enabled,
        version=version,
        intent_keywords=keywords or [],
    )


class TestRegisterSkill:
    def test_register_new_skill(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill = _make_skill("new_skill", keywords=["test"])
        assert registry.register_skill(skill) is True
        assert "new_skill" in registry.skills

    def test_register_duplicate_same_version_returns_false(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill1 = _make_skill("dup", version="1.0.0")
        skill2 = _make_skill("dup", version="1.0.0", name="Updated")
        assert registry.register_skill(skill1) is True
        assert registry.register_skill(skill2) is False
        # Original skill retained
        assert registry.skills["dup"].name == "Test Skill"

    def test_register_duplicate_higher_version_upgrades(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill1 = _make_skill("dup", version="1.0.0")
        skill2 = _make_skill("dup", version="2.0.0", name="Upgraded")
        assert registry.register_skill(skill1) is True
        assert registry.register_skill(skill2) is True
        assert registry.skills["dup"].name == "Upgraded"

    def test_register_duplicate_lower_version_returns_false(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill1 = _make_skill("dup", version="2.0.0")
        skill2 = _make_skill("dup", version="1.0.0", name="Downgraded")
        assert registry.register_skill(skill1) is True
        assert registry.register_skill(skill2) is False

    def test_register_updates_category_index(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill = _make_skill("cat_test", category=SkillCategory.UTILITY)
        registry.register_skill(skill)
        assert "cat_test" in registry.category_index.get("utility", [])

    def test_register_updates_keyword_index(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill = _make_skill("kw_test", keywords=["搜索", "查找"])
        registry.register_skill(skill)
        assert "kw_test" in registry.keyword_index.get("搜索", [])
        assert "kw_test" in registry.keyword_index.get("查找", [])


class TestGetAndFind:
    def test_get_skill_returns_skill(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill = _make_skill("get_test")
        registry.register_skill(skill)
        assert registry.get_skill("get_test") is skill

    def test_get_skill_returns_none_for_unknown(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        assert registry.get_skill("nonexistent") is None

    def test_find_by_intent_matches_keyword(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill = _make_skill("intent_test", keywords=["邮件", "发邮件"])
        registry.register_skill(skill)
        results = registry.find_by_intent("帮我发邮件给客户")
        assert len(results) == 1
        assert results[0].skill_id == "intent_test"

    def test_find_by_intent_no_match(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill = _make_skill("no_match", keywords=["特定关键词"])
        registry.register_skill(skill)
        results = registry.find_by_intent("完全不相关的内容")
        assert results == []

    def test_find_by_category(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        s1 = _make_skill("cat1", category=SkillCategory.UTILITY)
        s2 = _make_skill("cat2", category=SkillCategory.UTILITY)
        s3 = _make_skill("cat3", category=SkillCategory.ANALYSIS)
        for s in [s1, s2, s3]:
            registry.register_skill(s)
        utility_skills = registry.find_by_category(SkillCategory.UTILITY)
        assert len(utility_skills) == 2
        analysis_skills = registry.find_by_category(SkillCategory.ANALYSIS)
        assert len(analysis_skills) == 1

    def test_list_all_skills(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        s1 = _make_skill("list1")
        s2 = _make_skill("list2")
        registry.register_skill(s1)
        registry.register_skill(s2)
        all_skills = registry.list_all_skills()
        assert len(all_skills) == 2


class TestExecuteSkill:
    @pytest.mark.asyncio
    async def test_execute_skill_success(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill = _make_skill(
            "exec_test",
            execute=lambda goal="", _context=None, **kw: {"result": "done"},
        )
        registry.register_skill(skill)
        result = await registry.execute_skill("exec_test", goal="test")
        assert result["success"] is True
        assert "_exportable_formats" in result["data"]

    @pytest.mark.asyncio
    async def test_execute_skill_not_found(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        result = await registry.execute_skill("nonexistent")
        assert result["success"] is False
        assert "不存在" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_skill_disabled(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill = _make_skill("disabled", enabled=False)
        registry.register_skill(skill)
        result = await registry.execute_skill("disabled")
        assert result["success"] is False
        assert "禁用" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_skill_missing_required_param(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        skill = _make_skill(
            "params_test",
            inputs=[
                SkillInput(name="goal", type="str", required=True),
                SkillInput(name="target", type="str", required=True),
            ],
        )
        registry.register_skill(skill)
        result = await registry.execute_skill("params_test", goal="g")
        assert result["success"] is False
        assert "缺少必填参数" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_skill_exception_caught(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)

        def bad_execute(**kw):
            raise ValueError("boom")

        skill = _make_skill("bad", execute=bad_execute)
        registry.register_skill(skill)
        result = await registry.execute_skill("bad", goal="g")
        assert result["success"] is False
        assert "boom" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_async_skill(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)

        async def async_execute(goal="", _context=None, **kw):
            return {"async_result": goal}

        skill = _make_skill("async_test", execute=async_execute)
        registry.register_skill(skill)
        result = await registry.execute_skill("async_test", goal="async")
        assert result["success"] is True
        assert result["data"]["async_result"] == "async"


class TestToDict:
    def test_to_dict_structure(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        registry.register_skill(_make_skill("dict_test"))
        d = registry.to_dict()
        assert d["type"] == "skill_registry"
        assert d["skill_count"] == 1
        assert "dict_test" in d["skills"]
        assert d["skills"]["dict_test"]["name"] == "Test Skill"
        assert "categories" in d


class TestCollaboration:
    def test_find_collaboration_matches_trigger(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        cfg, collab_id = registry._find_collaboration("帮我跟进客户发邮件")
        assert cfg is not None
        assert collab_id == "crm_to_email"

    def test_find_collaboration_no_match(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        cfg, collab_id = registry._find_collaboration("完全无关的内容")
        assert cfg is None
        assert collab_id is None

    def test_enrich_goal_for_email_skill(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        context_data = {"crm": {"customer": {"name": "张三", "email": "z@test.com"}}}
        enriched = registry._enrich_goal_for_skill("email", "发邮件", context_data)
        assert "张三" in enriched
        assert "z@test.com" in enriched

    def test_enrich_goal_for_finance_skill(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        context_data = {"crm": {"deal": {"amount": 5000, "description": "咨询费"}}}
        enriched = registry._enrich_goal_for_skill("finance", "记账", context_data)
        assert "5000" in enriched
        assert "咨询费" in enriched

    def test_enrich_goal_no_crm_data(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        enriched = registry._enrich_goal_for_skill("email", "发邮件", {})
        assert enriched == "发邮件"

    def test_enrich_goal_crm_not_dict(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        enriched = registry._enrich_goal_for_skill(
            "email", "发邮件", {"crm": "not a dict"}
        )
        assert enriched == "发邮件"

    def test_execute_collaborative_returns_result(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        # Register the skills needed for crm_to_email collaboration
        registry.register_skill(_make_skill("crm", keywords=["跟进"]))
        registry.register_skill(_make_skill("email", keywords=["发邮件"]))
        result = registry._execute_collaborative("帮我跟进客户发邮件")
        assert result is not None
        assert result["collaboration"] == "crm_to_email"
        assert len(result["results"]) == 2

    def test_execute_collaborative_no_match_returns_none(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        result = registry._execute_collaborative("完全无关的内容")
        assert result is None

    def test_execute_collaborative_prevents_reentrance(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        registry.register_skill(_make_skill("crm"))
        registry.register_skill(_make_skill("email"))
        registry._collab_in_progress = True
        result = registry._execute_collaborative("帮我跟进客户发邮件")
        assert result is None

    def test_build_collab_result(self):
        registry = SkillRegistry(register_builtins=False, register_external=False)
        results = [
            {"skill_id": "crm", "result": {"success": True}},
            {"skill_id": "email", "result": {"success": False}},
        ]
        collab = SKILL_COLLABORATIONS["crm_to_email"]
        r = registry._build_collab_result(results, "crm_to_email", collab)
        assert r["success"] is True  # any() returns True since crm succeeded
        assert r["collaboration"] == "crm_to_email"
        assert "crm → email" in r["message"]


class TestSingletonInit:
    def test_singleton_returns_same_instance(self):
        r1 = SkillRegistry(register_builtins=False, register_external=False)
        r2 = SkillRegistry(register_builtins=False, register_external=False)
        assert r1 is r2

    def test_reinit_updates_llm_service(self):
        SkillRegistry(register_builtins=False, register_external=False)
        mock_llm = MagicMock()
        r2 = SkillRegistry(
            llm_service=mock_llm, register_builtins=False, register_external=False
        )
        assert r2.llm_service is mock_llm
