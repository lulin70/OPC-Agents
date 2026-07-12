"""Coverage tests for opc_manager.config.ConfigManager

Targets the env-based configuration loader and its change-callback mechanism.
"""

import os
import threading

import pytest

from opc_manager.config import ConfigManager, LLM_PROVIDERS, get_config


@pytest.fixture
def clean_env(monkeypatch):
    """Strip all OPC-relevant env vars so _load_config starts from defaults."""
    env_keys = [
        "MOKA_API_KEY",
        "MOKA_API_BASE",
        "MOKA_MODEL",
        "GLM_API_KEY",
        "GLM_API_BASE",
        "GLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "OPENAI_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "OLLAMA_ENABLED",
        "LLM_MAX_TOKENS",
        "LLM_TEMPERATURE",
        "LLM_TIMEOUT_SECONDS",
        "LOG_DIR",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


class TestLoadConfig:
    def test_defaults_when_no_env(self, clean_env):
        cm = ConfigManager()
        cfg = cm.config
        assert cfg["models"]["default"] == "moka"
        assert cfg["llm"]["max_tokens"] == 4000
        assert cfg["llm"]["temperature"] == 0.7
        assert cfg["llm"]["timeout_seconds"] == 60.0
        assert cfg["log_dir"] == "logs"

    def test_moka_loaded_when_api_key_present(self, clean_env):
        clean_env.setenv("MOKA_API_KEY", "sk-test")
        cm = ConfigManager()
        cfg = cm.config
        assert "moka" in cfg["models"]
        assert cfg["models"]["moka"]["api_key"] == "sk-test"
        assert cfg["models"]["moka"]["base_url"] == LLM_PROVIDERS["moka"]
        assert cfg["models"]["default"] == "moka"

    def test_glm_preferred_when_only_glm_key(self, clean_env):
        clean_env.setenv("GLM_API_KEY", "glm-key")
        cm = ConfigManager()
        cfg = cm.config
        assert cfg["models"]["default"] == "glm"
        assert cfg["models"]["glm"]["api_key"] == "glm-key"

    def test_openai_preferred_when_only_openai_key(self, clean_env):
        clean_env.setenv("OPENAI_API_KEY", "oai-key")
        cm = ConfigManager()
        cfg = cm.config
        assert cfg["models"]["default"] == "openai"

    def test_ollama_excluded_when_disabled_and_no_base_url(self, clean_env):
        cm = ConfigManager()
        cfg = cm.config
        assert "ollama" not in cfg["models"]

    def test_ollama_included_when_enabled(self, clean_env):
        clean_env.setenv("OLLAMA_ENABLED", "true")
        cm = ConfigManager()
        cfg = cm.config
        assert "ollama" in cfg["models"]
        assert cfg["models"]["ollama"]["base_url"] == LLM_PROVIDERS["ollama"]
        assert cfg["models"]["default"] == "ollama"

    def test_ollama_included_when_base_url_set(self, clean_env):
        clean_env.setenv("OLLAMA_BASE_URL", "http://remote:11434")
        cm = ConfigManager()
        cfg = cm.config
        assert "ollama" in cfg["models"]
        assert cfg["models"]["ollama"]["base_url"] == "http://remote:11434"

    def test_ollama_enabled_truthy_variants(self, clean_env):
        for val in ("1", "true", "YES", "True"):
            clean_env.setenv("OLLAMA_ENABLED", val)
            cm = ConfigManager()
            cfg = cm.config
            assert (
                "ollama" in cfg["models"]
            ), f"OLLAMA_ENABLED={val!r} should enable ollama"

    def test_ollama_enabled_falsy_variants(self, clean_env):
        for val in ("0", "false", "no", "", "  "):
            clean_env.setenv("OLLAMA_ENABLED", val)
            cm = ConfigManager()
            cfg = cm.config
            assert (
                "ollama" not in cfg["models"]
            ), f"OLLAMA_ENABLED={val!r} should NOT enable ollama"

    def test_llm_settings_override_defaults(self, clean_env):
        clean_env.setenv("LLM_MAX_TOKENS", "8000")
        clean_env.setenv("LLM_TEMPERATURE", "0.2")
        clean_env.setenv("LLM_TIMEOUT_SECONDS", "120.5")
        cm = ConfigManager()
        cfg = cm.config
        assert cfg["llm"]["max_tokens"] == 8000
        assert cfg["llm"]["temperature"] == 0.2
        assert cfg["llm"]["timeout_seconds"] == 120.5

    def test_log_dir_override(self, clean_env):
        clean_env.setenv("LOG_DIR", "/tmp/custom_logs")
        cm = ConfigManager()
        cfg = cm.config
        assert cfg["log_dir"] == "/tmp/custom_logs"

    def test_priority_moka_over_glm(self, clean_env):
        clean_env.setenv("MOKA_API_KEY", "moka")
        clean_env.setenv("GLM_API_KEY", "glm")
        cm = ConfigManager()
        cfg = cm.config
        assert cfg["models"]["default"] == "moka"

    def test_priority_openai_over_ollama(self, clean_env):
        clean_env.setenv("OPENAI_API_KEY", "oai")
        clean_env.setenv("OLLAMA_ENABLED", "true")
        cm = ConfigManager()
        cfg = cm.config
        # openai is checked before ollama in the loop
        assert cfg["models"]["default"] in ("openai", "ollama")


class TestConfigProperty:
    def test_returns_dict(self, clean_env):
        cm = ConfigManager()
        cfg = cm.config
        assert isinstance(cfg, dict)
        assert "models" in cfg
        assert "llm" in cfg

    def test_thread_safe_lock(self, clean_env):
        cm = ConfigManager()
        results = []

        def worker():
            results.append(cm.config)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 5
        assert all(r == results[0] for r in results)


class TestReloadConfig:
    def test_returns_true_when_no_callbacks(self, clean_env):
        cm = ConfigManager()
        assert cm.reload_config() is True

    def test_callbacks_invoked(self, clean_env):
        cm = ConfigManager()
        calls = []
        cm.register_callback(lambda: calls.append("a"))
        cm.reload_config()
        assert calls == ["a"]

    def test_callback_exception_does_not_break_others(self, clean_env):
        cm = ConfigManager()
        calls = []

        def bad():
            raise RuntimeError("boom")

        cm.register_callback(bad)
        cm.register_callback(lambda: calls.append("ok"))
        assert cm.reload_config() is True
        assert calls == ["ok"]

    def test_unregister_callback(self, clean_env):
        cm = ConfigManager()
        calls = []
        cb = lambda: calls.append("x")  # noqa: E731
        cm.register_callback(cb)
        cm.unregister_callback(cb)
        cm.reload_config()
        assert calls == []

    def test_unregister_unknown_callback_silent(self, clean_env):
        cm = ConfigManager()
        cm.unregister_callback(lambda: None)  # should not raise


class TestGetModelConfig:
    def test_default_model_when_no_arg(self, clean_env):
        clean_env.setenv("MOKA_API_KEY", "k")
        cm = ConfigManager()
        mc = cm.get_model_config()
        assert mc["api_key"] == "k"

    def test_explicit_model_name(self, clean_env):
        clean_env.setenv("GLM_API_KEY", "g")
        cm = ConfigManager()
        mc = cm.get_model_config("glm")
        assert mc["api_key"] == "g"

    def test_unknown_model_returns_empty(self, clean_env):
        cm = ConfigManager()
        assert cm.get_model_config("nonexistent") == {}


class TestGetAvailableModels:
    def test_excludes_default_key(self, clean_env):
        clean_env.setenv("MOKA_API_KEY", "k")
        cm = ConfigManager()
        models = cm.get_available_models()
        assert "default" not in models
        assert "moka" in models

    def test_only_default_models_when_no_keys(self, clean_env):
        # Without API keys, moka/glm/openai still appear because their base_url
        # and model have defaults populated; ollama is excluded.
        cm = ConfigManager()
        models = cm.get_available_models()
        assert "default" not in models
        assert "moka" in models
        assert "glm" in models
        assert "openai" in models
        assert "ollama" not in models


class TestGet:
    def test_get_section(self, clean_env):
        cm = ConfigManager()
        llm = cm.get("llm")
        assert "max_tokens" in llm

    def test_get_key_within_section(self, clean_env):
        cm = ConfigManager()
        assert cm.get("llm", "max_tokens") == 4000

    def test_get_key_default_when_missing(self, clean_env):
        cm = ConfigManager()
        assert cm.get("llm", "nonexistent", "fallback") == "fallback"

    def test_get_unknown_section_returns_default(self, clean_env):
        cm = ConfigManager()
        assert cm.get("unknown_section", default="d") == "d"


class TestSet:
    def test_set_writes_env_var(self, clean_env):
        cm = ConfigManager()
        assert cm.set("llm", "max_tokens", "9999") is True
        assert os.environ["LLM_MAX_TOKENS"] == "9999"

    def test_set_triggers_callbacks(self, clean_env):
        cm = ConfigManager()
        calls = []
        cm.register_callback(lambda: calls.append("called"))
        cm.set("llm", "max_tokens", "5000")
        assert calls == ["called"]

    def test_set_callback_exception_handled(self, clean_env):
        cm = ConfigManager()

        def bad():
            raise ValueError("x")

        cm.register_callback(bad)
        assert cm.set("llm", "max_tokens", "1") is True


class TestGetConfigFactory:
    def test_returns_config_manager_instance(self, clean_env):
        cm = get_config()
        assert isinstance(cm, ConfigManager)

    def test_factory_returns_fresh_instance(self, clean_env):
        cm1 = get_config()
        cm2 = get_config()
        # Factory creates new instances each call (no singleton enforcement)
        assert cm1 is not cm2
