import time
import hashlib
import threading
import logging
from typing import Dict, List, Optional, Tuple
from collections import OrderedDict

logger = logging.getLogger(__name__)

SEARCH_CACHE_MAX_SIZE = 50
SEARCH_CACHE_TTL_SECONDS = 300


class SearchCache:
    """LRU search result cache — Key performance component for reducing duplicate network requests

    Design intent:
    - DuckDuckGo single search takes ~5-10 seconds, repeated queries in same session are common
    - Cache hits can reduce response time from seconds to milliseconds
    - Also solves the Streamlit frontend 30-second timeout limit

    Cache strategy:
    - Algorithm: OrderedDict implements O(1) LRU eviction
    - Capacity: 50 entries (enough to cover typical query volume in a single session)
    - TTL: 300 seconds (5 minutes, balances freshness and hit rate)
    - Key: MD5 hash of query+max_results (same query different result counts cached separately)

    Thread safety:
    - AsyncTaskExecutor calls TaskEngineV3.execute() in background thread
    - Uses threading.Lock to protect all cache read/write operations
    """

    def __init__(
        self, max_size: int = SEARCH_CACHE_MAX_SIZE, ttl: int = SEARCH_CACHE_TTL_SECONDS
    ) -> None:
        self._cache: OrderedDict[str, Tuple[float, List[Dict]]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0
        self._lock = threading.RLock()

    def _make_key(self, query: str, max_results: int) -> str:
        raw = f"{query}:{max_results}"
        return hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()

    def get(self, query: str, max_results: int) -> Optional[List[Dict]]:
        key = self._make_key(query, max_results)
        with self._lock:
            if key in self._cache:
                timestamp, results = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    logger.info("[SearchCache] Hit: %s...", query[:30])
                    return [dict(r) if isinstance(r, dict) else r for r in results]
                else:
                    del self._cache[key]
            self._misses += 1
            return None

    def set(self, query: str, max_results: int, results: List[Dict]) -> None:
        key = self._make_key(query, max_results)
        with self._lock:
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (time.time(), results)
            logger.info(
                "[SearchCache] Write: %s... (cache size: %s)",
                query[:30],
                len(self._cache),
            )

    @property
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
            }
