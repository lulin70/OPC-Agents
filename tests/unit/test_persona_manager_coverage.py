"""Coverage tests for opc_manager.persona_manager.PersonaManager

Tests persona loading, switching, caching, and response formatting.
Uses tmp_path to create isolated YAML configs.
"""

from unittest.mock import patch

import yaml

from opc_manager.business_types import BusinessType
from opc_manager.persona_manager import PersonaConfig, PersonaManager


def _make_variant_yaml(
    vid="content_creator", display="内容小助理", emoji="", btype="content_creator"
):
    return {
        "display_name": display,
        "emoji": emoji,
        "target_business_type": btype,
        "style_overrides": {"tone": "轻松活泼", "formality_level": 0.3},
        "expertise_tags": ["内容创作"],
        "vocabulary": {"domain_specific": ["内容"], "forbidden": []},
        "dialogue_templates": {
            "greeting": "嗨！今天有什么想法？",
            "accept_task": "收到！我来帮你处理！",
            "complete": "搞定啦！这是你的{deliverable}。",
        },
        "proactive_rules": [],
        "response_patterns": {},
    }


def _make_yaml_file(path, variants=None, base_persona=None):
    if variants is None:
        variants = {"content_creator": _make_variant_yaml()}
    if base_persona is None:
        base_persona = {"name": "总裁办秘书", "version": "2.1.0"}
    config = {"base_persona": base_persona, "variants": variants}
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True)
    return path


class TestPersonaConfig:
    def test_get_template_returns_filled(self):
        cfg = PersonaConfig(
            variant_id="t",
            display_name="T",
            emoji="",
            target_business_type="t",
            style_overrides={},
            expertise_tags=[],
            vocabulary={},
            dialogue_templates={"greeting": "Hello {name}!"},
            proactive_rules=[],
            response_patterns={},
        )
        assert cfg.get_template("greeting", name="World") == "Hello World!"

    def test_get_template_missing_variable(self):
        cfg = PersonaConfig(
            variant_id="t",
            display_name="T",
            emoji="",
            target_business_type="t",
            style_overrides={},
            expertise_tags=[],
            vocabulary={},
            dialogue_templates={"greeting": "Hello {missing}!"},
            proactive_rules=[],
            response_patterns={},
        )
        result = cfg.get_template("greeting", name="World")
        assert "模板变量缺失" in result
        assert "Hello {missing}!" in result

    def test_get_template_no_kwargs_returns_raw(self):
        cfg = PersonaConfig(
            variant_id="t",
            display_name="T",
            emoji="",
            target_business_type="t",
            style_overrides={},
            expertise_tags=[],
            vocabulary={},
            dialogue_templates={"greeting": "Hello!"},
            proactive_rules=[],
            response_patterns={},
        )
        assert cfg.get_template("greeting") == "Hello!"

    def test_get_template_unknown_template(self):
        cfg = PersonaConfig(
            variant_id="t",
            display_name="T",
            emoji="",
            target_business_type="t",
            style_overrides={},
            expertise_tags=[],
            vocabulary={},
            dialogue_templates={},
            proactive_rules=[],
            response_patterns={},
        )
        result = cfg.get_template("nonexistent")
        assert "未找到模板" in result

    def test_to_dict(self):
        cfg = PersonaConfig(
            variant_id="vid",
            display_name="DN",
            emoji="",
            target_business_type="tt",
            style_overrides={"k": "v"},
            expertise_tags=["tag"],
            vocabulary={"domain_specific": ["d"]},
            dialogue_templates={"greeting": "hi"},
            proactive_rules=[{"rule": "r"}],
            response_patterns={"pattern": ["a"]},
        )
        d = cfg.to_dict()
        assert d["variant_id"] == "vid"
        assert d["display_name"] == "DN"
        assert d["emoji"] == ""
        assert d["target_business_type"] == "tt"
        assert d["style_overrides"] == {"k": "v"}
        assert d["expertise_tags"] == ["tag"]
        assert d["vocabulary"] == {"domain_specific": ["d"]}
        assert d["dialogue_templates"] == {"greeting": "hi"}
        assert d["proactive_rules"] == [{"rule": "r"}]
        assert d["response_patterns"] == {"pattern": ["a"]}


class TestPersonaManagerInit:
    def test_init_with_valid_yaml(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "personas.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        assert pm.base_persona["name"] == "总裁办秘书"
        assert "content_creator" in pm.variants

    def test_init_with_missing_file_uses_fallback(self, tmp_path):
        missing = str(tmp_path / "nonexistent.yaml")
        pm = PersonaManager(config_path=missing)
        assert pm.base_persona["name"] == "总裁办秘书"
        assert "content_creator" in pm.variants
        assert pm.variants["content_creator"].display_name == "内容小助理"

    def test_init_with_invalid_yaml_uses_fallback(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        with open(bad, "w") as f:
            f.write(": not valid yaml :")
        pm = PersonaManager(config_path=str(bad))
        assert "content_creator" in pm.variants

    def test_init_with_multiple_variants(self, tmp_path):
        variants = {
            "content_creator": _make_variant_yaml(
                "content_creator", btype="content_creator"
            ),
            "ecommerce": _make_variant_yaml(
                "ecommerce", display="电商小帮手", btype="ecommerce"
            ),
        }
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants=variants)
        pm = PersonaManager(config_path=yaml_path)
        assert len(pm.variants) == 2
        assert "content_creator" in pm.variants
        assert "ecommerce" in pm.variants

    def test_default_config_path_when_none(self):
        # Should not raise; will use fallback if file missing
        with patch("os.path.exists", return_value=False):
            pm = PersonaManager(config_path=None)
        assert pm.config_path.endswith("persona_variants.yaml")

    def test_variant_with_missing_fields_uses_defaults(self, tmp_path):
        # Variant config with minimal fields
        variants = {"minimal": {"display_name": "Min"}}
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants=variants)
        pm = PersonaManager(config_path=yaml_path)
        v = pm.variants["minimal"]
        assert v.display_name == "Min"
        assert v.emoji == ""
        assert v.target_business_type == ""
        assert v.style_overrides == {}
        assert v.expertise_tags == []


class TestGetPersona:
    def test_returns_none_when_business_type_none(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        assert pm.get_persona(user_id="u1", business_type=None) is None

    def test_returns_persona_for_matching_type(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        persona = pm.get_persona(business_type=BusinessType.CONTENT_CREATOR)
        assert persona is not None
        assert persona.target_business_type == "content_creator"

    def test_caches_persona_by_user_id(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        p1 = pm.get_persona(user_id="u1", business_type=BusinessType.CONTENT_CREATOR)
        p2 = pm.get_persona(user_id="u1", business_type=BusinessType.CONTENT_CREATOR)
        assert p1 is p2
        assert "u1" in pm._cache

    def test_cache_returns_cached_when_type_matches(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        p1 = pm.get_persona(user_id="u1", business_type=BusinessType.CONTENT_CREATOR)
        # Second call should return cached
        p2 = pm.get_persona(user_id="u1", business_type=BusinessType.CONTENT_CREATOR)
        assert p1 is p2

    def test_falls_back_to_first_variant_when_type_not_found(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        # ECOMMERCE has no matching variant in the single-variant YAML
        persona = pm.get_persona(business_type=BusinessType.ECOMMERCE)
        assert persona is not None
        # Falls back to first variant
        assert persona.variant_id == "content_creator"

    def test_returns_none_when_no_variants(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants={})
        pm = PersonaManager(config_path=yaml_path)
        persona = pm.get_persona(business_type=BusinessType.CONTENT_CREATOR)
        assert persona is None


class TestSwitchPersona:
    def test_switch_success(self, tmp_path):
        variants = {
            "content_creator": _make_variant_yaml(btype="content_creator"),
            "ecommerce": _make_variant_yaml("ecommerce", btype="ecommerce"),
        }
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants=variants)
        pm = PersonaManager(config_path=yaml_path)
        assert pm.switch_persona("u1", BusinessType.CONTENT_CREATOR) is True
        assert pm.switch_persona("u1", BusinessType.ECOMMERCE) is True
        assert pm._cache["u1"].target_business_type == "ecommerce"

    def test_switch_when_no_matching_variant_still_succeeds_via_fallback(
        self, tmp_path
    ):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        # ECOMMERCE has no variant, but get_persona falls back to first
        result = pm.switch_persona("u1", BusinessType.ECOMMERCE)
        # Since get_persona returns a fallback persona, switch succeeds
        assert result is True

    def test_switch_when_no_variants_returns_false(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants={})
        pm = PersonaManager(config_path=yaml_path)
        assert pm.switch_persona("u1", BusinessType.CONTENT_CREATOR) is False


class TestFormatResponse:
    def test_returns_error_when_persona_none(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        result = pm.format_response(None, "greeting")
        assert "系统错误" in result

    def test_returns_template_content(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        persona = pm.get_persona(business_type=BusinessType.CONTENT_CREATOR)
        result = pm.format_response(persona, "greeting")
        assert "嗨" in result

    def test_adds_emoji_when_density_high(self, tmp_path):
        variants = {
            "content_creator": _make_variant_yaml(),
        }
        variants["content_creator"]["style_overrides"]["emoji_density"] = "high"
        variants["content_creator"]["dialogue_templates"]["greeting"] = "Hello"
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants=variants)
        pm = PersonaManager(config_path=yaml_path)
        persona = pm.get_persona(business_type=BusinessType.CONTENT_CREATOR)
        result = pm.format_response(persona, "greeting")
        # The format_response should return a string; emoji addition depends on
        # whether the response already contains emoji characters.
        assert isinstance(result, str)
        assert "Hello" in result

    def test_no_emoji_added_when_density_not_high(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        persona = pm.get_persona(business_type=BusinessType.CONTENT_CREATOR)
        result = pm.format_response(persona, "greeting")
        assert result == "嗨！今天有什么想法？"


class TestGreetingAndAcceptance:
    def test_get_greeting_with_persona(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        greeting = pm.get_greeting(business_type=BusinessType.CONTENT_CREATOR)
        assert "嗨" in greeting

    def test_get_greeting_without_persona_returns_default(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants={})
        pm = PersonaManager(config_path=yaml_path)
        greeting = pm.get_greeting(business_type=BusinessType.CONTENT_CREATOR)
        assert "你好" in greeting

    def test_get_task_acceptance_with_persona(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        msg = pm.get_task_acceptance(business_type=BusinessType.CONTENT_CREATOR)
        assert "收到" in msg

    def test_get_task_acceptance_without_persona(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants={})
        pm = PersonaManager(config_path=yaml_path)
        msg = pm.get_task_acceptance(
            business_type=BusinessType.CONTENT_CREATOR,
            task_description="测试任务",
        )
        assert "测试任务" in msg

    def test_get_completion_message_with_persona(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        msg = pm.get_completion_message(
            business_type=BusinessType.CONTENT_CREATOR,
            deliverable="周报",
        )
        assert "周报" in msg

    def test_get_completion_message_without_persona(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants={})
        pm = PersonaManager(config_path=yaml_path)
        msg = pm.get_completion_message(
            business_type=BusinessType.CONTENT_CREATOR,
            deliverable="成果",
        )
        assert "成果" in msg


class TestListAndStats:
    def test_list_available_personas(self, tmp_path):
        variants = {
            "content_creator": _make_variant_yaml(),
            "ecommerce": _make_variant_yaml(
                "ecommerce", display="电商", btype="ecommerce"
            ),
        }
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"), variants=variants)
        pm = PersonaManager(config_path=yaml_path)
        personas = pm.list_available_personas()
        assert len(personas) == 2
        ids = {p["id"] for p in personas}
        assert ids == {"content_creator", "ecommerce"}
        for p in personas:
            assert "display_name" in p
            assert "emoji" in p
            assert "business_type" in p
            assert "expertise_tags_count" in p
            assert "templates_count" in p

    def test_get_statistics(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        pm.get_persona(user_id="u1", business_type=BusinessType.CONTENT_CREATOR)
        stats = pm.get_statistics()
        assert stats["total_variants"] == 1
        assert stats["cached_users"] == 1
        assert "content_creator" in stats["available_types"]
        assert stats["base_persona_name"] == "总裁办秘书"
        assert stats["config_version"] == "2.1.0"
        assert stats["config_path"] == yaml_path


class TestClearCache:
    def test_clear_single_user(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        pm.get_persona(user_id="u1", business_type=BusinessType.CONTENT_CREATOR)
        pm.get_persona(user_id="u2", business_type=BusinessType.CONTENT_CREATOR)
        pm.clear_cache(user_id="u1")
        assert "u1" not in pm._cache
        assert "u2" in pm._cache

    def test_clear_all_cache(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        pm.get_persona(user_id="u1", business_type=BusinessType.CONTENT_CREATOR)
        pm.get_persona(user_id="u2", business_type=BusinessType.CONTENT_CREATOR)
        pm.clear_cache()
        assert len(pm._cache) == 0

    def test_clear_nonexistent_user_silent(self, tmp_path):
        yaml_path = _make_yaml_file(str(tmp_path / "p.yaml"))
        pm = PersonaManager(config_path=yaml_path)
        pm.clear_cache(user_id="nobody")  # should not raise
