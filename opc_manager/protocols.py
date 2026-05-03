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
from loguru import logger


@runtime_checkable
class LLMProvider(Protocol):
    def is_available(self) -> bool: ...
    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> Optional[str]: ...


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
    def track(self, event: str, data: Dict[str, Any] = None) -> None: ...


class NullLLMProvider:
    def is_available(self) -> bool:
        return False

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> Optional[str]:
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
        logger.warning(f"[NullSecureProvider] Secure storage unavailable — set_key({name}) returned False")
        return False

    def get_key(self, name: str) -> Optional[str]:
        return None

    def load_to_env(self) -> int:
        logger.warning("[NullSecureProvider] Secure storage unavailable — load_to_env() returned 0")
        return 0


class NullMonitorProvider:
    def is_available(self) -> bool:
        return False

    def track(self, event: str, data: Dict[str, Any] = None) -> None:
        pass


_llm_provider = None
_search_provider = None
_secure_provider = None
_monitor_provider = None


def get_llm_provider() -> LLMProvider:
    global _llm_provider
    if _llm_provider is not None:
        return _llm_provider
    try:
        from opc_manager.llm_content import LLMEnhancedContentGenerator
        gen = LLMEnhancedContentGenerator()
        api_key, api_base, model = gen._get_llm_config()
        if api_base:
            _llm_provider = _LLMProviderWrapper(gen)
            return _llm_provider
    except Exception:
        pass
    _llm_provider = NullLLMProvider()
    return _llm_provider


def get_search_provider() -> SearchProvider:
    global _search_provider
    if _search_provider is not None:
        return _search_provider
    try:
        from opc_manager.search_processor import SearchResultProcessor
        _search_provider = _SearchProviderWrapper(SearchResultProcessor())
        return _search_provider
    except Exception:
        pass
    _search_provider = NullSearchProvider()
    return _search_provider


def get_secure_provider() -> SecureProvider:
    global _secure_provider
    if _secure_provider is not None:
        return _secure_provider
    try:
        from opc_manager.secure_storage import SecureKeyStore
        store = SecureKeyStore()
        if store.is_available:
            _secure_provider = _SecureProviderWrapper(store)
            return _secure_provider
    except Exception:
        pass
    _secure_provider = NullSecureProvider()
    return _secure_provider


def get_monitor_provider() -> MonitorProvider:
    global _monitor_provider
    if _monitor_provider is not None:
        return _monitor_provider
    _monitor_provider = NullMonitorProvider()
    return _monitor_provider


class _LLMProviderWrapper:
    def __init__(self, generator):
        self._gen = generator

    def is_available(self) -> bool:
        api_key, api_base, model = self._gen._get_llm_config()
        return bool(api_base)

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> Optional[str]:
        return self._gen._call_llm_api(prompt)


class _SearchProviderWrapper:
    def __init__(self, processor):
        self._processor = processor

    def is_available(self) -> bool:
        return True

    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        return self._processor.search(query, max_results=max_results)


class _SecureProviderWrapper:
    def __init__(self, store):
        self._store = store

    def is_available(self) -> bool:
        return self._store.is_available

    def set_key(self, name: str, value: str) -> bool:
        return self._store.set_key(name, value)

    def get_key(self, name: str) -> Optional[str]:
        return self._store.get_key(name)

    def load_to_env(self) -> int:
        return self._store.load_to_env()
