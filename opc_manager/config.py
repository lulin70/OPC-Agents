#!/usr/bin/env python3
"""
Configuration management for OPC Manager

Reads configuration from environment variables (.env file).
Legacy config.toml support has been removed in v0.1.0.
"""

import os
import threading
from typing import Dict, Any, Callable, Optional


class ConfigManager:
    """Environment-based configuration manager for OPC-Agents system

    Reads configuration from environment variables (loaded via .env by python-dotenv).
    Supports change callbacks for runtime reconfiguration.
    """

    _ENV_MAP = {
        "moka": {
            "api_key": "MOKA_API_KEY",
            "base_url": "MOKA_API_BASE",
            "model": "MOKA_MODEL",
        },
        "glm": {
            "api_key": "GLM_API_KEY",
            "base_url": "GLM_API_BASE",
            "model": "GLM_MODEL",
        },
        "openai": {
            "api_key": "OPENAI_API_KEY",
            "base_url": "OPENAI_API_BASE",
            "model": "OPENAI_MODEL",
        },
        "ollama": {
            "base_url": "OLLAMA_BASE_URL",
            "model": "OLLAMA_MODEL",
        },
    }

    _DEFAULTS = {
        "MOKA_API_BASE": "https://api.moka-ai.com/v1",
        "MOKA_MODEL": "moka/claude-sonnet-4-6",
        "GLM_API_BASE": "https://open.bigmodel.cn/api/paas/v4",
        "GLM_MODEL": "glm-4",
        "OPENAI_API_BASE": "https://api.openai.com/v1",
        "OPENAI_MODEL": "gpt-4o",
        "OLLAMA_MODEL": "llama3",
        "LLM_MAX_TOKENS": "4000",
        "LLM_TEMPERATURE": "0.7",
        "LLM_TIMEOUT_SECONDS": "60.0",
        "LOG_DIR": "logs",
    }

    def __init__(self, config_path: str = None):
        self._lock = threading.RLock()
        self._callbacks = []
        self._config_path = config_path

    def _load_config(self) -> Dict[str, Any]:
        models = {}
        for model_name, env_vars in self._ENV_MAP.items():
            model_config = {}
            for key, env_key in env_vars.items():
                val = os.environ.get(env_key, self._DEFAULTS.get(env_key, ""))
                if val:
                    model_config[key] = val
            if model_name == "ollama":
                ollama_enabled = os.environ.get("OLLAMA_ENABLED", "").strip().lower() in ("1", "true", "yes")
                if "base_url" not in model_config and not ollama_enabled:
                    continue
                if "base_url" not in model_config and ollama_enabled:
                    model_config["base_url"] = "http://localhost:11434"
            if model_config:
                models[model_name] = model_config

        default_model = "moka"
        for candidate in ["moka", "glm", "openai", "ollama"]:
            if candidate == "ollama":
                if models.get("ollama", {}).get("base_url"):
                    default_model = "ollama"
                    break
            elif models.get(candidate, {}).get("api_key"):
                default_model = candidate
                break

        return {
            "models": {"default": default_model, **models},
            "llm": {
                "max_tokens": int(
                    os.environ.get("LLM_MAX_TOKENS", self._DEFAULTS["LLM_MAX_TOKENS"])
                ),
                "temperature": float(
                    os.environ.get("LLM_TEMPERATURE", self._DEFAULTS["LLM_TEMPERATURE"])
                ),
                "timeout_seconds": float(
                    os.environ.get(
                        "LLM_TIMEOUT_SECONDS", self._DEFAULTS["LLM_TIMEOUT_SECONDS"]
                    )
                ),
            },
            "log_dir": os.environ.get("LOG_DIR", self._DEFAULTS["LOG_DIR"]),
        }

    @property
    def config(self) -> Dict[str, Any]:
        with self._lock:
            return self._load_config()

    def reload_config(self) -> bool:
        try:
            with self._lock:
                for callback in self._callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.debug("[Config] Callback failed: %s", e)
                return True
        except Exception as e:
            logger.debug("[Config] Notify callbacks failed: %s", e)
            return False

    def register_callback(self, callback: Callable) -> None:
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable) -> None:
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        with self._lock:
            cfg = self._load_config()
            if not model_name:
                model_name = cfg.get("models", {}).get("default", "moka")
            return cfg.get("models", {}).get(model_name, {})

    def get_available_models(self) -> list:
        with self._lock:
            cfg = self._load_config()
            models = cfg.get("models", {})
            return [key for key in models if key != "default"]

    def get(self, section: str, key: str = None, default: Any = None) -> Any:
        with self._lock:
            cfg = self._load_config()
            if section in cfg:
                if key:
                    return cfg[section].get(key, default)
                return cfg[section]
            return default

    def set(self, section: str, key: str, value: Any) -> bool:
        try:
            with self._lock:
                env_key = f"{section.upper()}_{key.upper()}"
                os.environ[env_key] = str(value)
                for callback in self._callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.debug("[Config] Set callback failed: %s", e)
                return True
        except Exception as e:
            logger.debug("[Config] Set value failed: %s", e)
            return False


def get_config() -> ConfigManager:
    return ConfigManager()
