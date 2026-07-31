import logging
import os
import time
from typing import Optional, Dict, Any, List

import requests

from opc_manager.config import LLM_PROVIDERS

logger = logging.getLogger(__name__)

LLM_CALL_TIMEOUT = 30
LLM_MAX_RETRIES = 3
LLM_RETRY_BACKOFF = 2.0
_CIRCUIT_BREAKER_THRESHOLD = 3
LLM_TOTAL_TIMEOUT = 90


def _read_mock_error_file() -> Optional[str]:
    """从文件读取 mock 错误类型（E2E 测试专用）.

    server 子进程无法读取测试进程的 os.environ 修改，
    通过文件传递错误类型实现跨进程通信。

    文件路径由环境变量 OPC_MOCK_LLM_ERROR_FILE 指定（conftest.py 设置）。
    文件内容为错误类型字符串（timeout/connection/api_key/rate_limit/server_500）。

    Returns:
        Optional[str]: 错误类型字符串，或 None（无错误注入）
    """
    try:
        path = os.environ.get("OPC_MOCK_LLM_ERROR_FILE")
        if not path:
            return None
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            content = f.read().strip().lower()
        return content if content else None
    except Exception:
        return None


def discover_llm_config() -> Dict[str, Any]:
    config = {"api_key": "", "base_url": "", "model": "", "is_ollama": False}

    # 优先通过 SettingsManager 获取（不通过 os.environ）
    try:
        from opc_manager.settings import get_settings

        settings = get_settings()
        llm_config = settings.get_llm_config()
        if llm_config.get("api_key"):
            config.update(llm_config)
            return config
    except Exception as e:
        logger.warning("[SimpleLLM] Auto-config failed: %s", e)

    # 回退到 os.environ（兼容外部设置的环境变量）
    config["api_key"] = os.environ.get("MOKA_API_KEY", "")
    if config["api_key"]:
        config["base_url"] = os.environ.get("MOKA_API_BASE", LLM_PROVIDERS["moka"])
        config["model"] = os.environ.get("MOKA_MODEL", "moka/claude-sonnet-4-6")
        return config

    for env_key, env_url, env_model in [
        ("GLM_API_KEY", LLM_PROVIDERS["zhipu"], "glm-4"),
        (
            "OPENAI_API_KEY",
            os.environ.get("OPENAI_API_BASE", LLM_PROVIDERS["openai"]),
            "gpt-4",
        ),
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
        config["base_url"] = ollama_url or LLM_PROVIDERS["ollama"]
        config["model"] = os.environ.get("OLLAMA_MODEL", "llama3")
        config["is_ollama"] = True

    return config


def _discover_all_providers() -> List[Dict[str, Any]]:
    providers = []

    # 优先通过 SettingsManager 获取 moka 配置
    moka_key = ""
    moka_base_url = os.environ.get("MOKA_API_BASE", LLM_PROVIDERS["moka"])
    moka_model = os.environ.get("MOKA_MODEL", "moka/claude-sonnet-4-6")
    try:
        from opc_manager.settings import get_settings

        settings = get_settings()
        moka_key = settings.get_api_key("moka") or ""
        llm_config = settings.get_llm_config()
        if llm_config.get("base_url"):
            moka_base_url = llm_config["base_url"]
        if llm_config.get("model"):
            moka_model = llm_config["model"]
    except Exception as e:
        moka_key = os.environ.get("MOKA_API_KEY", "").strip()
        logger.warning("[SimpleLLM] MOKA key extraction failed: %s", e)

    if moka_key:
        providers.append(
            {
                "api_key": moka_key,
                "base_url": moka_base_url,
                "model": moka_model,
                "is_ollama": False,
                "name": "moka",
            }
        )
    glm_key = os.environ.get("GLM_API_KEY", "").strip()
    if glm_key:
        providers.append(
            {
                "api_key": glm_key,
                "base_url": LLM_PROVIDERS["zhipu"],
                "model": "glm-4",
                "is_ollama": False,
                "name": "glm",
            }
        )
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        providers.append(
            {
                "api_key": openai_key,
                "base_url": os.environ.get("OPENAI_API_BASE", LLM_PROVIDERS["openai"]),
                "model": "gpt-4",
                "is_ollama": False,
                "name": "openai",
            }
        )
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "")
    ollama_enabled = os.environ.get("OLLAMA_ENABLED", "").lower() == "true"
    if ollama_enabled or ollama_url:
        providers.append(
            {
                "api_key": "ollama",
                "base_url": ollama_url or LLM_PROVIDERS["ollama"],
                "model": os.environ.get("OLLAMA_MODEL", "llama3"),
                "is_ollama": True,
                "name": "ollama",
            }
        )
    return providers


class SimpleLLMService:

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
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

        # Enforce HTTPS for non-Ollama providers (API keys must not be sent over plaintext HTTP)
        if (
            not self._is_ollama
            and self._base_url
            and self._base_url.startswith("http://")
        ):
            logger.warning(
                "[SECURITY] API base URL uses plaintext HTTP: %s — "
                "API keys will be transmitted unencrypted. "
                "Please use HTTPS or set OLLAMA_ENABLED=true for local models.",
                self._base_url,
            )

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _is_provider_circuit_open(self, name: str) -> bool:
        return self._circuit_breaker.get(name, 0) >= _CIRCUIT_BREAKER_THRESHOLD

    def _record_provider_failure(self, name: str) -> None:
        self._circuit_breaker[name] = self._circuit_breaker.get(name, 0) + 1

    def _record_provider_success(self, name: str) -> None:
        self._circuit_breaker.pop(name, None)

    def _try_provider(
        self,
        provider: Dict[str, Any],
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        timeout: int,
    ) -> Optional[str]:
        from opc_manager.utils import _llm_thread_semaphore

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
                    result = svc._call_ollama(
                        prompt, system_prompt, max_tokens, timeout
                    )
                else:
                    result = svc._call_openai_compat(
                        prompt, system_prompt, max_tokens, timeout
                    )
                if result:
                    self._record_provider_success(name)
                    return result
            finally:
                _llm_thread_semaphore.release()
        except Exception as e:
            self._record_provider_failure(name)
            logger.warning("Provider %s call failed: %s", name, e)
        return None

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        timeout: int = LLM_CALL_TIMEOUT,
    ) -> Optional[str]:
        if not self._api_key:
            return None

        # E2E 测试支持: OPC_MOCK_LLM=true 时返回 mock 响应，不调用真实 API
        # 用于真实模式 Chat 全链路 E2E 测试（验证输入框→提交→成果物渲染→下载）
        # 生产环境不设置此环境变量，无影响
        if os.environ.get("OPC_MOCK_LLM", "").lower() == "true":
            # Sprint 4.1 GAP-P0-4: 错误恢复 E2E 支持
            # 通过文件传递错误类型（server 子进程无法读取测试进程的 os.environ）
            mock_error = _read_mock_error_file()
            if mock_error:
                raise self._make_mock_error(mock_error)
            logger.info("[SimpleLLMService] OPC_MOCK_LLM=true, returning mock response")
            return self._generate_mock_response(prompt)

        from opc_manager.utils import sanitize_for_llm, _llm_thread_semaphore

        prompt = sanitize_for_llm(prompt, 2000)
        if system_prompt:
            system_prompt = sanitize_for_llm(system_prompt, 500)

        # Try LLM cache first
        from opc_manager.llm_cache import get_llm_cache

        cache = get_llm_cache()
        _temperature = 0.3  # matches _call_openai_compat and _call_ollama
        if cache is not None:
            cached = cache.get(
                self._model, _temperature, max_tokens, system_prompt or "", prompt
            )
            if cached is not None:
                logger.debug("[SimpleLLMService] Cache hit for prompt")
                return cached

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
                        result = self._call_ollama(
                            prompt, system_prompt, max_tokens, timeout
                        )
                    else:
                        result = self._call_openai_compat(
                            prompt, system_prompt, max_tokens, timeout
                        )
                    if result:
                        self._record_provider_success("primary")
                        # Cache the response
                        if cache is not None:
                            cache.put(
                                self._model,
                                _temperature,
                                max_tokens,
                                system_prompt or "",
                                prompt,
                                result,
                                provider=self._base_url,
                            )
                        return result
                finally:
                    _llm_thread_semaphore.release()
            except Exception as e:
                self._record_provider_failure("primary")
                logger.warning(
                    "LLM call attempt %s/%s failed: %s", attempt + 1, LLM_MAX_RETRIES, e
                )
                if attempt < LLM_MAX_RETRIES - 1:
                    time.sleep(min(LLM_RETRY_BACKOFF ** (attempt + 1), 10))

        all_providers = _discover_all_providers()
        primary_key = self._api_key
        for provider in all_providers:
            if (
                provider["api_key"] == primary_key
                and provider["base_url"] == self._base_url
            ):
                continue
            result = self._try_provider(
                provider, prompt, system_prompt, max_tokens, timeout
            )
            if result:
                logger.info(
                    "Fallback to provider %s succeeded", provider.get("name", "unknown")
                )
                # Cache the fallback response
                if cache is not None:
                    cache.put(
                        self._model,
                        _temperature,
                        max_tokens,
                        system_prompt or "",
                        prompt,
                        result,
                        provider=provider.get("base_url", ""),
                    )
                return result

        return None

    def _make_mock_error(self, error_type: str) -> Exception:
        """构造模拟 LLM 错误异常（仅用于 E2E 测试，OPC_MOCK_LLM_ERROR 设置时调用）.

        错误消息包含 chat_router.FRIENDLY_ERRORS 映射的关键字，
        确保 chat_router 能匹配并展示对应的友好提示。

        Args:
            error_type: 错误类型 (timeout/connection/api_key/rate_limit/server_500)

        Returns:
            Exception: 包含关键字的异常实例
        """
        error_map = {
            "timeout": "LLM call timeout: request exceeded 60s limit",
            "connection": "Connection error: failed to establish connection to LLM service",
            "api_key": "Incorrect API key: authentication failed (401)",
            "rate_limit": "Rate limit exceeded (429): too many requests",
            "server_500": "LLM service returned 500 Internal Server Error",
        }
        msg = error_map.get(error_type, f"Unknown mock error type: {error_type}")
        logger.info(
            "[SimpleLLMService] OPC_MOCK_LLM_ERROR=%s, raising: %s", error_type, msg
        )
        return RuntimeError(msg)

    def _generate_mock_response(self, prompt: str) -> str:
        """生成 mock LLM 响应（仅用于 E2E 测试，OPC_MOCK_LLM=true 时调用）.

        返回结构化 markdown，模拟真实 LLM 成果物格式，
        让 Chat 页面能够渲染成果物区域并触发下载按钮。
        响应内容足够丰富（>500 字符）以通过 Quality Gate 检查。
        """
        prompt_preview = prompt[:120].replace("\n", " ") if prompt else ""
        return (
            f"# 产品介绍文案\n\n"
            f"## 概述\n\n"
            f'基于用户需求 "{prompt_preview}"，以下是为您生成的内容方案。'
            f"本方案聚焦于一人公司（One-Person Company）的运营场景，"
            f"提供结构化的成果物输出。\n\n"
            f"## 核心价值主张\n\n"
            f"我们的产品致力于解决用户在日常工作中的效率痛点，"
            f"通过智能化的工作流管理，帮助用户节省时间、提升产出质量。"
            f"产品核心功能包括任务自动化、智能分析和可视化报告，"
            f"全面覆盖独立创业者的运营需求。\n\n"
            f"## 目标用户\n\n"
            f"- 独立创业者和小团队\n"
            f"- 内容创作者和咨询顾问\n"
            f"- 需要高效管理多项目的知识工作者\n\n"
            f"## 竞争优势\n\n"
            f"1. 智能任务分解与优先级排序\n"
            f"2. AI 辅助内容生成与质量检查\n"
            f"3. 多维度数据可视化分析\n"
            f"4. 轻量级部署，本地优先保护数据隐私\n\n"
            f"## 参考资料\n\n"
            f"- 来源：产品需求文档 PRD v0.5.9\n"
            f"- 参考：用户访谈记录 2026Q2\n"
            f"- https://example.com/opc-agents/market-research-2026\n\n"
            f"---\n_Mock response generated at "
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} (OPC_MOCK_LLM=true)_"
        )

    def _call_openai_compat(
        self, prompt: str, system_prompt: Optional[str], max_tokens: int, timeout: int
    ) -> Optional[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload: Dict[str, Any] = {
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

    def _call_ollama(
        self, prompt: str, system_prompt: Optional[str], max_tokens: int, timeout: int
    ) -> Optional[str]:
        payload: Dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": max_tokens},
        }
        if system_prompt:
            payload["system"] = system_prompt

        resp = requests.post(
            f"{self._base_url.rstrip('/')}/api/generate",
            json=payload,
            timeout=(10, timeout),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip() or None
