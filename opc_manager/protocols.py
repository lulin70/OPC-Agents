"""
Protocol interfaces + Null Provider pattern for OPC-Agents

Design principle (learned from DevSquad):
- Every external dependency has a Protocol interface
- Every Protocol has a NullProvider that does nothing but never crashes
- Components check is_available() before using a provider
- Graceful degradation: if a component is unavailable, system still works

ADR-012: Why Protocol + NullProvider?
  1. LLM backend may be unconfigured → NullLLMProvider → template mode
  2. Search may be blocked → NullSearchProvider → knowledge base fallback
  3. Secure storage may lack cryptography → NullSecureProvider → .env plaintext
  4. Monitoring may be disabled → NullMonitorProvider → loguru only

Usage:
  from opc_manager.protocols import get_llm_provider, get_search_provider

  llm = get_llm_provider()
  if llm.is_available():
      result = llm.generate(prompt)
  else:
      result = template_fallback(prompt)
"""

from typing import Optional, Dict, List, Any, Protocol, runtime_checkable
import threading

from .consensus_engine import Opinion

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]


@runtime_checkable
class BrainProtocol(Protocol):
    """三贤者统一接口 [S2-T8] - 用于解耦共识调用方与具体贤者实现。

    共识流程中，贤者通过 express_opinion 输出意见对象。
    注意：StrategistBrain/ReflectorBrain 的 express_opinion 返回 Dict，
    由调用方 (AgentLoop/TaskLifecycle) 通过 _dict_to_opinion 转换；
    ExecutorBrain 直接返回 Opinion。此 Protocol 描述共识参与者契约。
    """

    def express_opinion(
        self, context: Dict[str, Any], decision_point: str = ""
    ) -> Opinion: ...


@runtime_checkable
class SkillRegistryProtocol(Protocol):
    """技能注册表接口 [S2-T8] - 用于解耦依赖 SkillRegistry 的调用方。"""

    def get_skill(self, skill_id: str) -> Any: ...
    def list_all_skills(self) -> List[Any]: ...


@runtime_checkable
class LLMProvider(Protocol):
    def is_available(self) -> bool: ...

    def generate(
        self, prompt: str, system_prompt: str = "", **kwargs: Any
    ) -> Optional[str]: ...


@runtime_checkable
class LLMServiceProtocol(Protocol):
    def is_available(self) -> bool: ...

    def generate(
        self, prompt: str, system_prompt: str = "", **kwargs: Any
    ) -> Optional[str]: ...
    def analyze(self, text: str, **kwargs: Any) -> Optional[Dict[str, Any]]: ...


@runtime_checkable
class SearchProvider(Protocol):
    def is_available(self) -> bool: ...
    def search(self, query: str, max_results: int = 10) -> List[Dict]: ...


@runtime_checkable
class SecureProvider(Protocol):
    def is_available(self) -> bool: ...
    def set_key(self, name: str, value: str) -> bool: ...
    def get_key(self, name: str) -> Optional[str]: ...
    def load_to_env(self) -> int: ...


@runtime_checkable
class MonitorProvider(Protocol):
    def is_available(self) -> bool: ...
    def track(self, event: str, data: Optional[Dict[str, Any]] = None) -> None: ...


class NullLLMProvider:
    def is_available(self) -> bool:
        return False

    def generate(
        self, prompt: str, system_prompt: str = "", **kwargs: Any
    ) -> Optional[str]:
        logger.warning("[NullLLMProvider] LLM unavailable — generate() returned None")
        return None


class NullSearchProvider:
    def is_available(self) -> bool:
        return False

    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        logger.warning("[NullSearchProvider] Search unavailable — search() returned []")
        return []


class NullSecureProvider:
    def is_available(self) -> bool:
        return False

    def set_key(self, name: str, value: str) -> bool:
        logger.warning(
            "[NullSecureProvider] Secure storage unavailable — set_key(%s) returned False",
            name,
        )
        return False

    def get_key(self, name: str) -> Optional[str]:
        return None

    def load_to_env(self) -> int:
        logger.warning(
            "[NullSecureProvider] Secure storage unavailable — load_to_env() returned 0"
        )
        return 0


class NullMonitorProvider:
    def is_available(self) -> bool:
        return False

    def track(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        pass


_llm_provider: Optional[LLMProvider] = None
_search_provider: Optional[SearchProvider] = None
_secure_provider: Optional[SecureProvider] = None
_monitor_provider: Optional[MonitorProvider] = None
_provider_lock = threading.Lock()


def get_llm_provider() -> LLMProvider:
    global _llm_provider
    if _llm_provider is not None:
        return _llm_provider
    with _provider_lock:
        if _llm_provider is not None:
            return _llm_provider
        try:
            from opc_manager.llm_content import LLMEnhancedContentGenerator

            gen = LLMEnhancedContentGenerator()
            api_key, api_base, model = gen._get_llm_config()
            if api_base:
                _llm_provider = _LLMProviderWrapper(gen)
                return _llm_provider
        except Exception as e:
            logger.debug("[Protocols] LLM provider init failed: %s", e)
        _llm_provider = NullLLMProvider()
        return _llm_provider


def get_search_provider() -> SearchProvider:
    global _search_provider
    if _search_provider is not None:
        return _search_provider
    with _provider_lock:
        if _search_provider is not None:
            return _search_provider
        try:
            from opc_manager.search_processor import SearchResultProcessor

            _search_provider = _SearchProviderWrapper(SearchResultProcessor())
            return _search_provider
        except Exception as e:
            logger.debug("[Protocols] Search provider init failed: %s", e)
        _search_provider = NullSearchProvider()
        return _search_provider


def get_secure_provider() -> SecureProvider:
    global _secure_provider
    if _secure_provider is not None:
        return _secure_provider
    with _provider_lock:
        if _secure_provider is not None:
            return _secure_provider
        try:
            from opc_manager.secure_storage import SecureKeyStore

            store = SecureKeyStore()
            if store.is_available:
                _secure_provider = _SecureProviderWrapper(store)
                return _secure_provider
        except Exception as e:
            logger.debug("[Protocols] Secure provider init failed: %s", e)
        _secure_provider = NullSecureProvider()
        return _secure_provider


def get_monitor_provider() -> MonitorProvider:
    global _monitor_provider
    if _monitor_provider is not None:
        return _monitor_provider
    with _provider_lock:
        if _monitor_provider is not None:
            return _monitor_provider
        _monitor_provider = NullMonitorProvider()
        return _monitor_provider


class _LLMProviderWrapper:
    def __init__(self, generator: Any) -> None:
        self._gen = generator

    def is_available(self) -> bool:
        api_key, api_base, model = self._gen._get_llm_config()
        return bool(api_base)

    def generate(
        self, prompt: str, system_prompt: str = "", **kwargs: Any
    ) -> Optional[str]:
        return self._gen._call_llm_api(prompt)


class _SearchProviderWrapper:
    def __init__(self, processor: Any) -> None:
        self._processor = processor

    def is_available(self) -> bool:
        return True

    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        return self._processor.search(query, max_results=max_results)


class _SecureProviderWrapper:
    def __init__(self, store: Any) -> None:
        self._store = store

    def is_available(self) -> bool:
        return self._store.is_available

    def set_key(self, name: str, value: str) -> bool:
        return self._store.set_key(name, value)

    def get_key(self, name: str) -> Optional[str]:
        return self._store.get_key(name)

    def load_to_env(self) -> int:
        return self._store.load_to_env()
