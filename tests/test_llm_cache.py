"""Tests for opc_manager.llm_cache — LLM response caching layer."""

import os
import time
import tempfile
import pytest

from opc_manager.llm_cache import LLMCache, DEFAULT_CACHE_TTL


@pytest.fixture
def cache_db(tmp_path):
    """Create a temporary LLMCache instance for each test."""
    db_path = str(tmp_path / "test_cache.db")
    return LLMCache(db_path, ttl=3600)


class TestComputeKey:
    def test_compute_key_deterministic(self):
        key1 = LLMCache.compute_key("gpt-4", 0.3, 500, "sys", "hello")
        key2 = LLMCache.compute_key("gpt-4", 0.3, 500, "sys", "hello")
        assert key1 == key2

    def test_compute_key_different_params(self):
        key1 = LLMCache.compute_key("gpt-4", 0.3, 500, "sys", "hello")
        key2 = LLMCache.compute_key("gpt-4", 0.3, 500, "sys", "world")
        key3 = LLMCache.compute_key("glm-4", 0.3, 500, "sys", "hello")
        key4 = LLMCache.compute_key("gpt-4", 0.5, 500, "sys", "hello")
        key5 = LLMCache.compute_key("gpt-4", 0.3, 1000, "sys", "hello")
        key6 = LLMCache.compute_key("gpt-4", 0.3, 500, "other", "hello")
        # All keys should be different
        keys = [key1, key2, key3, key4, key5, key6]
        assert len(set(keys)) == len(keys)


class TestPutAndGet:
    def test_put_and_get(self, cache_db):
        cache_db.put("gpt-4", 0.3, 500, "system prompt", "user prompt", "response text")
        result = cache_db.get("gpt-4", 0.3, 500, "system prompt", "user prompt")
        assert result == "response text"

    def test_get_nonexistent_returns_none(self, cache_db):
        result = cache_db.get("gpt-4", 0.3, 500, "sys", "nonexistent")
        assert result is None

    def test_get_expired_returns_none(self, tmp_path):
        db_path = str(tmp_path / "expired_cache.db")
        # TTL of 0 means entries expire immediately
        cache = LLMCache(db_path, ttl=0)
        cache.put("gpt-4", 0.3, 500, "sys", "prompt", "response")
        # Small sleep to ensure time has passed
        time.sleep(0.01)
        result = cache.get("gpt-4", 0.3, 500, "sys", "prompt")
        assert result is None

    def test_skip_high_temperature(self, cache_db):
        # temperature > 0.7 should not be cached
        cache_db.put("gpt-4", 0.8, 500, "sys", "prompt", "response")
        result = cache_db.get("gpt-4", 0.8, 500, "sys", "prompt")
        assert result is None

    def test_cache_hit_increments_count(self, cache_db):
        cache_db.put("gpt-4", 0.3, 500, "sys", "prompt", "response")
        # First get
        cache_db.get("gpt-4", 0.3, 500, "sys", "prompt")
        # Second get
        cache_db.get("gpt-4", 0.3, 500, "sys", "prompt")
        stats = cache_db.stats()
        assert stats["total_hits"] == 2


class TestCleanup:
    def test_cleanup_expired(self, tmp_path):
        db_path = str(tmp_path / "cleanup_cache.db")
        cache = LLMCache(db_path, ttl=0)
        cache.put("gpt-4", 0.3, 500, "sys", "prompt1", "response1")
        cache.put("gpt-4", 0.3, 500, "sys", "prompt2", "response2")
        time.sleep(0.01)
        removed = cache.cleanup_expired()
        assert removed == 2
        stats = cache.stats()
        assert stats["total_entries"] == 0

    def test_cleanup_does_not_remove_valid(self, cache_db):
        cache_db.put("gpt-4", 0.3, 500, "sys", "prompt", "response")
        removed = cache_db.cleanup_expired()
        assert removed == 0
        stats = cache_db.stats()
        assert stats["total_entries"] == 1


class TestStats:
    def test_stats_empty(self, cache_db):
        stats = cache_db.stats()
        assert stats["total_entries"] == 0
        assert stats["total_hits"] == 0

    def test_stats_with_entries(self, cache_db):
        cache_db.put("gpt-4", 0.3, 500, "sys", "prompt", "response")
        stats = cache_db.stats()
        assert stats["total_entries"] == 1
        assert stats["total_hits"] == 0

    def test_stats_with_hits(self, cache_db):
        cache_db.put("gpt-4", 0.3, 500, "sys", "prompt", "response")
        cache_db.get("gpt-4", 0.3, 500, "sys", "prompt")
        stats = cache_db.stats()
        assert stats["total_entries"] == 1
        assert stats["total_hits"] == 1
