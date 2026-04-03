"""Cache utilities for memory classification engine."""

import time
from typing import Dict, List, Optional, Any, Callable
from functools import wraps
from memory_classification_engine.utils.logger import logger


class LRUCache:
    """Simple LRU (Least Recently Used) cache implementation."""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """Initialize LRU cache.

        Args:
            max_size: Maximum number of items in cache.
            ttl: Time to live in seconds for cached items.
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_order: List[str] = []

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found/expired.
        """
        if key not in self._cache:
            return None

        item = self._cache[key]
        current_time = time.time()

        # Check if expired
        if current_time - item['timestamp'] > self.ttl:
            self.delete(key)
            return None

        # Update access order
        self._access_order.remove(key)
        self._access_order.append(key)

        return item['value']

    def set(self, key: str, value: Any) -> None:
        """Set item in cache.

        Args:
            key: Cache key.
            value: Value to cache.
        """
        # If key exists, update access order
        if key in self._cache:
            self._access_order.remove(key)

        # If cache is full, remove least recently used item
        elif len(self._cache) >= self.max_size:
            lru_key = self._access_order.pop(0)
            del self._cache[lru_key]
            logger.debug(f"Cache evicted key: {lru_key}")

        # Add new item
        self._cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
        self._access_order.append(key)

    def delete(self, key: str) -> bool:
        """Delete item from cache.

        Args:
            key: Cache key.

        Returns:
            True if item was deleted, False if not found.
        """
        if key in self._cache:
            del self._cache[key]
            self._access_order.remove(key)
            return True
        return False

    def clear(self) -> None:
        """Clear all items from cache."""
        self._cache.clear()
        self._access_order.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        current_time = time.time()
        expired_count = sum(
            1 for item in self._cache.values()
            if current_time - item['timestamp'] > self.ttl
        )

        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'expired_items': expired_count,
            'ttl': self.ttl
        }


class MemoryCache:
    """Cache manager for memory storage with warmup support."""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """Initialize memory cache.

        Args:
            max_size: Maximum number of items in cache.
            ttl: Time to live in seconds.
        """
        self._cache = LRUCache(max_size=max_size, ttl=ttl)
        self._warmup_completed = False

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        self._cache.set(key, value)

    def delete(self, key: str) -> bool:
        """Delete item from cache."""
        return self._cache.delete(key)

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()

    def warmup(self, fetch_func: Callable, limit: int = 100) -> int:
        """Warm up cache with frequently accessed memories.

        Args:
            fetch_func: Function to fetch memories from storage.
                       Should return list of memory dictionaries.
            limit: Maximum number of items to preload.

        Returns:
            Number of items cached.
        """
        try:
            logger.info(f"Starting cache warmup with limit={limit}")

            # Fetch frequently accessed memories
            memories = fetch_func(limit=limit)

            # Cache each memory
            cached_count = 0
            for memory in memories:
                if 'id' in memory:
                    cache_key = f"memory:{memory['id']}"
                    self._cache.set(cache_key, memory)
                    cached_count += 1

            self._warmup_completed = True
            logger.info(f"Cache warmup completed: {cached_count} items cached")
            return cached_count

        except Exception as e:
            logger.error(f"Error during cache warmup: {e}", exc_info=True)
            return 0

    def get_memory(self, memory_id: str, fetch_func: Callable = None) -> Optional[Dict]:
        """Get memory from cache or fetch from storage.

        Args:
            memory_id: Memory ID.
            fetch_func: Optional function to fetch from storage if not in cache.

        Returns:
            Memory dictionary or None.
        """
        cache_key = f"memory:{memory_id}"

        # Try cache first
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for memory {memory_id}")
            return cached

        # Fetch from storage if function provided
        if fetch_func:
            memory = fetch_func(memory_id)
            if memory:
                self._cache.set(cache_key, memory)
            return memory

        return None

    def invalidate_memory(self, memory_id: str) -> bool:
        """Invalidate cached memory.

        Args:
            memory_id: Memory ID to invalidate.

        Returns:
            True if item was in cache and removed.
        """
        cache_key = f"memory:{memory_id}"
        return self._cache.delete(cache_key)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self._cache.get_stats()
        stats['warmup_completed'] = self._warmup_completed
        return stats


def cached(cache: MemoryCache, key_prefix: str = ""):
    """Decorator to cache function results.

    Args:
        cache: MemoryCache instance.
        key_prefix: Prefix for cache key.

    Returns:
        Decorator function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)

            return result

        return wrapper
    return decorator
