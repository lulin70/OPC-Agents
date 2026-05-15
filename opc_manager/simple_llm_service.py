import json
import logging
import os
import time
from typing import Optional, Dict, Any, List

import requests

logger = logging.getLogger(__name__)

LLM_CALL_TIMEOUT = 30
LLM_MAX_RETRIES = 3
LLM_RETRY_BACKOFF = 2.0
_CIRCUIT_BREAKER_THRESHOLD = 3
LLM_TOTAL_TIMEOUT = 90


def discover_llm_config() -> Dict[str, str]:
    config = {"api_key": "", "base_url": "", "model": "", "is_ollama": False}

    config["api_key"] = os.environ.get("MOKA_API_KEY", "")
    if config["api_key"]:
        config["base_url"] = os.environ.get("MOKA_API_BASE", "https://api.moka-ai.com/v1")
        config["model"] = os.environ.get("MOKA_MODEL", "moka/claude-sonnet-4-6")
        return config

    for env_key, env_url, env_model in [
        ("GLM_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-4"),
        ("OPENAI_API_KEY", os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"), "gpt-4"),
    ]:
        key = os.environ.get(env_key, "").strip()
        if key:
            config["api_key"] = key
            config["base_url"] = env_url
            config["model"] = env_model
            return config

    ollama_url = os.environ.get("OLLAMA_BASE_URL", "")
    ollama_enabled = os.environ.get("OLLAMA_ENABLED", "").lower() == "true"
    if ollama_enabled or ollama_url:
        config["api_key"] = "ollama"
        config["base_url"] = ollama_url or "http://localhost:11434"
        config["model"] = os.environ.get("OLLAMA_MODEL", "llama3")
        config["is_ollama"] = True

    return config


def _discover_all_providers() -> List[Dict[str, Any]]:
    providers = []
    moka_key = os.environ.get("MOKA_API_KEY", "").strip()
    if moka_key:
        providers.append({
            "api_key": moka_key,
            "base_url": os.environ.get("MOKA_API_BASE", "https://api.moka-ai.com/v1"),
            "model": os.environ.get("MOKA_MODEL", "moka/claude-sonnet-4-6"),
            "is_ollama": False,
            "name": "moka",
        })
    glm_key = os.environ.get("GLM_API_KEY", "").strip()
    if glm_key:
        providers.append({
            "api_key": glm_key,
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4",
            "is_ollama": False,
            "name": "glm",
        })
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        providers.append({
            "api_key": openai_key,
            "base_url": os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
            "model": "gpt-4",
            "is_ollama": False,
            "name": "openai",
        })
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "")
    ollama_enabled = os.environ.get("OLLAMA_ENABLED", "").lower() == "true"
    if ollama_enabled or ollama_url:
        providers.append({
            "api_key": "ollama",
            "base_url": ollama_url or "http://localhost:11434",
            "model": os.environ.get("OLLAMA_MODEL", "llama3"),
            "is_ollama": True,
            "name": "ollama",
        })
    return providers


class SimpleLLMService:

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self._circuit_breaker: Dict[str, int] = {}
        if api_key and base_url and model:
            self._api_key = api_key
            self._base_url = base_url
            self._model = model
            self._is_ollama = False
        else:
            config = discover_llm_config()
            self._api_key = api_key or config["api_key"]
            self._base_url = base_url or config["base_url"]
            self._model = model or config["model"]
            self._is_ollama = config["is_ollama"]

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _is_provider_circuit_open(self, name: str) -> bool:
        return self._circuit_breaker.get(name, 0) >= _CIRCUIT_BREAKER_THRESHOLD

    def _record_provider_failure(self, name: str) -> None:
        self._circuit_breaker[name] = self._circuit_breaker.get(name, 0) + 1

    def _record_provider_success(self, name: str) -> None:
        self._circuit_breaker.pop(name, None)

    def _try_provider(self, provider: Dict[str, Any], prompt: str,
                      system_prompt: str, max_tokens: int, timeout: int) -> Optional[str]:
        from opc_manager.utils import sanitize_for_llm, _llm_thread_semaphore
        name = provider.get("name", "unknown")
        if self._is_provider_circuit_open(name):
            logger.info("Skipping provider %s: circuit breaker open", name)
            return None
        try:
            _llm_thread_semaphore.acquire(timeout=30)
            try:
                svc = SimpleLLMService.__new__(SimpleLLMService)
                svc._api_key = provider["api_key"]
                svc._base_url = provider["base_url"]
                svc._model = provider["model"]
                svc._is_ollama = provider["is_ollama"]
                svc._circuit_breaker = self._circuit_breaker
                if svc._is_ollama:
                    result = svc._call_ollama(prompt, system_prompt, max_tokens, timeout)
                else:
                    result = svc._call_openai_compat(prompt, system_prompt, max_tokens, timeout)
                if result:
                    self._record_provider_success(name)
                    return result
            finally:
                _llm_thread_semaphore.release()
        except Exception as e:
            self._record_provider_failure(name)
            logger.warning("Provider %s call failed: %s", name, e)
        return None

    def complete(self, prompt: str, system_prompt: str = None,
                 max_tokens: int = 500, timeout: int = LLM_CALL_TIMEOUT) -> Optional[str]:
        if not self._api_key:
            return None

        from opc_manager.utils import sanitize_for_llm, _llm_thread_semaphore
        prompt = sanitize_for_llm(prompt, 2000)
        if system_prompt:
            system_prompt = sanitize_for_llm(system_prompt, 500)

        total_start = time.time()

        for attempt in range(LLM_MAX_RETRIES):
            elapsed = time.time() - total_start
            if elapsed >= LLM_TOTAL_TIMEOUT:
                logger.warning("LLM总超时(%ss)已到，停止重试", LLM_TOTAL_TIMEOUT)
                break

            try:
                _llm_thread_semaphore.acquire(timeout=30)
                try:
                    if self._is_ollama:
                        result = self._call_ollama(prompt, system_prompt, max_tokens, timeout)
                    else:
                        result = self._call_openai_compat(prompt, system_prompt, max_tokens, timeout)
                    if result:
                        self._record_provider_success("primary")
                        return result
                finally:
                    _llm_thread_semaphore.release()
            except Exception as e:
                self._record_provider_failure("primary")
                logger.warning("LLM call attempt %s/%s failed: %s", attempt + 1, LLM_MAX_RETRIES, e)
                if attempt < LLM_MAX_RETRIES - 1:
                    time.sleep(min(LLM_RETRY_BACKOFF ** (attempt + 1), 10))

        all_providers = _discover_all_providers()
        primary_key = self._api_key
        for provider in all_providers:
            if provider["api_key"] == primary_key and provider["base_url"] == self._base_url:
                continue
            result = self._try_provider(provider, prompt, system_prompt, max_tokens, timeout)
            if result:
                logger.info("Fallback to provider %s succeeded", provider.get("name", "unknown"))
                return result

        return None

    def _call_openai_compat(self, prompt: str, system_prompt: str,
                            max_tokens: int, timeout: int) -> Optional[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }

        url = f"{self._base_url.rstrip('/')}/chat/completions"
        if not self._base_url.startswith("https://"):
            logger.warning("API base URL is not HTTPS: %s", self._base_url)
        resp = requests.post(url, headers=headers, json=payload, timeout=(10, timeout))
        resp.raise_for_status()
        data = resp.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip() if content else None

    def _call_ollama(self, prompt: str, system_prompt: str,
                     max_tokens: int, timeout: int) -> Optional[str]:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": max_tokens},
        }
        if system_prompt:
            payload["system"] = system_prompt

        resp = requests.post(
            f"{self._base_url.rstrip('/')}/api/generate",
            json=payload, timeout=(10, timeout),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip() or None
