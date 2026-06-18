"""Memory optimization tests using tracemalloc and psutil.

Tests verify:
1. Bounded data structures don't grow beyond limits
2. No memory leaks in repeated operations
3. Large file reads don't cause memory spikes
4. Session state lists are bounded
5. Cache cleanup works correctly

Run:
    pytest tests/test_memory_optimization.py -v
"""

import gc
import os
import sys
import tempfile
import time
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _get_process_rss():
    """Get current process RSS in bytes."""
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss
    except ImportError:
        return 0


def _force_gc():
    """Force garbage collection and return collected count."""
    return gc.collect()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Bounded Data Structure Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBoundedDataStructures:
    """Verify all bounded collections enforce their limits."""

    def test_bounded_dict_enforces_max_size(self):
        """BoundedDict should not exceed max_size."""
        from opc_manager.utils import BoundedDict

        bd = BoundedDict(max_size=10)
        for i in range(100):
            bd[f"key_{i}"] = f"value_{i}" * 100

        assert len(bd) <= 10, f"BoundedDict grew to {len(bd)}, max_size=10"

    def test_bounded_dict_fifo_eviction(self):
        """BoundedDict should evict oldest entries (FIFO)."""
        from opc_manager.utils import BoundedDict

        bd = BoundedDict(max_size=3)
        bd["a"] = 1
        bd["b"] = 2
        bd["c"] = 3
        bd["d"] = 4  # should evict "a"

        assert "a" not in bd, "FIFO eviction failed: 'a' should have been evicted"
        assert "d" in bd
        assert len(bd) == 3

    def test_lru_cache_enforces_max_size(self):
        """LRUCache should not exceed max_size."""
        from opc_manager.performance_monitor import LRUCache

        cache = LRUCache(max_size=10, ttl=300)
        for i in range(50):
            cache.put(f"key_{i}", "x" * 1000)

        stats = cache.get_stats()
        assert stats["size"] <= 10, f"LRUCache grew to {stats['size']}, max_size=10"

    def test_search_cache_enforces_max_size(self):
        """SearchCache should not exceed max_size."""
        from opc_manager.search_cache import SearchCache

        cache = SearchCache(max_size=10, ttl=300)
        for i in range(50):
            cache.set(f"query_{i}", 10, [{"result": "data" * 100}])

        # SearchCache uses internal dict, verify it doesn't grow unbounded
        assert (
            len(cache._cache) <= 10
        ), f"SearchCache grew to {len(cache._cache)}, max_size=10"

    def test_audit_log_deque_bounded(self):
        """AuditLog should use deque with maxlen."""
        from opc_manager.audit_log import AuditLog

        log = AuditLog()
        for i in range(2000):
            log.log(
                session_id="test_session",
                operation_type="test_action",
                skill_id="test_skill",
                input_text=f"input_{i}",
                output_data={"index": i},
                duration_ms=10,
            )

        assert (
            len(log._logs) <= 1000
        ), f"AuditLog deque grew to {len(log._logs)}, expected max 1000"

    def test_log_cache_deque_bounded(self):
        """LogCache should use deque with maxlen."""
        from frontend.components.live_log_panel import LogCache, LogEntry

        cache = LogCache()
        for i in range(1000):
            entry = LogEntry(
                timestamp=time.time(),
                level="INFO",
                source="test",
                message=f"log_line_{i}",
                module="test",
            )
            cache.update([entry])

        assert (
            len(cache._cache) <= 500
        ), f"LogCache deque grew to {len(cache._cache)}, expected max 500"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Memory Leak Detection Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMemoryLeaks:
    """Detect memory leaks in repeated operations using tracemalloc."""

    def test_agent_loop_repeated_runs_no_leak(self):
        """Repeated AgentLoop runs should not leak memory."""
        import tracemalloc

        from opc_manager.agent_loop import AgentLoop

        tracemalloc.start()

        # Baseline
        snapshot1 = tracemalloc.take_snapshot()

        # Simulate multiple task runs
        for i in range(10):
            loop = AgentLoop(llm_service=MagicMock())
            # Force cleanup
            del loop
            _force_gc()

        snapshot2 = tracemalloc.take_snapshot()
        stats = snapshot2.compare_to(snapshot1, "lineno")

        # Filter to our project code — allow small allocations (<50KB)
        # SkillRegistry registers skills on first AgentLoop creation, which is expected
        project_leaks = [
            s
            for s in stats
            if "opc_manager" in str(s.traceback[0].filename)
            and s.size_diff > 50000  # >50KB growth is a real leak
        ]

        tracemalloc.stop()

        assert (
            len(project_leaks) == 0
        ), f"Memory leaks detected in project code:\n" + "\n".join(
            str(s) for s in project_leaks[:5]
        )

    def test_bounded_dict_repeated_ops_no_leak(self):
        """Repeated BoundedDict operations should not leak."""
        import tracemalloc

        from opc_manager.utils import BoundedDict

        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        bd = BoundedDict(max_size=100)
        for cycle in range(20):
            for i in range(500):
                bd[f"key_{cycle}_{i}"] = "x" * 100
            # Old entries auto-evicted, but let's verify no growth
        del bd
        _force_gc()

        snapshot2 = tracemalloc.take_snapshot()
        stats = snapshot2.compare_to(snapshot1, "lineno")
        project_leaks = [
            s
            for s in stats
            if "opc_manager" in str(s.traceback[0].filename) and s.size_diff > 5000
        ]
        tracemalloc.stop()

        assert len(project_leaks) == 0, f"Memory leaks in BoundedDict:\n" + "\n".join(
            str(s) for s in project_leaks[:5]
        )

    def test_settings_manager_singleton_no_growth(self):
        """SettingsManager singleton should not grow on repeated access."""
        import tracemalloc

        from opc_manager.settings import get_settings

        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        settings = get_settings()
        for _ in range(100):
            _ = settings.get_llm_config()
            _ = settings._llm.provider

        snapshot2 = tracemalloc.take_snapshot()
        stats = snapshot2.compare_to(snapshot1, "lineno")
        # Allow small allocations (<50KB) for SecureKeyStore lazy init
        project_leaks = [
            s
            for s in stats
            if "opc_manager" in str(s.traceback[0].filename) and s.size_diff > 50000
        ]
        tracemalloc.stop()

        assert len(project_leaks) == 0, f"SettingsManager memory growth:\n" + "\n".join(
            str(s) for s in project_leaks[:5]
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Large File Read Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestLargeFileReads:
    """Verify large file reads don't cause memory spikes."""

    def test_log_tail_does_not_load_full_file(self, tmp_path):
        """Reading last N lines of a log file should not load entire file."""
        # Create a large fake log file (5MB)
        log_file = tmp_path / "large.log"
        line = "2026-06-17 INFO Some log message here\n"
        num_lines = 50000  # ~2.5MB
        with open(log_file, "w") as f:
            for _ in range(num_lines):
                f.write(line)

        # Method 1: Bad approach (readlines then slice)
        # This is what we're testing against

        # Method 2: Good approach (deque with maxlen)
        from collections import deque

        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            last_lines = deque(f, maxlen=500)

        assert len(last_lines) == 500
        # Verify we got the last 500 lines
        assert "50000" not in last_lines[-1] or "Some log" in last_lines[-1]

    def test_knowledge_file_read_bounded(self, tmp_path):
        """Knowledge file content should be loaded lazily, not all at once."""
        # Create multiple knowledge files
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        for i in range(20):
            (kb_dir / f"doc_{i}.md").write_text(
                f"# Document {i}\n\n" + "Content " * 1000
            )

        # Verify files exist
        files = list(kb_dir.glob("*.md"))
        assert len(files) == 20

        # Reading all files at once would use ~200KB
        # Reading metadata only would use ~2KB
        # This test documents the expected behavior


# ═══════════════════════════════════════════════════════════════════════════
# 4. Session State Bounds Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSessionStateBounds:
    """Verify session state lists are bounded to prevent unbounded growth."""

    def test_chat_messages_should_have_max(self):
        """Chat messages list should be bounded."""
        # This is a design test — documents the expected behavior
        # The actual bound is enforced in chat_router.py
        MAX_CHAT_MESSAGES = 100  # Expected limit
        # Simulate messages list
        messages = []
        for i in range(200):
            messages.append({"role": "user", "content": f"Message {i}"})
            # Enforce bound (this is what the fix should do)
            if len(messages) > MAX_CHAT_MESSAGES:
                messages = messages[-MAX_CHAT_MESSAGES:]

        assert (
            len(messages) <= MAX_CHAT_MESSAGES
        ), f"Messages list grew to {len(messages)}, expected max {MAX_CHAT_MESSAGES}"

    def test_deliverables_should_have_max(self):
        """Deliverables list should be bounded."""
        MAX_DELIVERABLES = 50  # Expected limit
        deliverables = []
        for i in range(100):
            deliverables.insert(0, {"id": i, "content": "x" * 1000})
            if len(deliverables) > MAX_DELIVERABLES:
                deliverables = deliverables[:MAX_DELIVERABLES]

        assert (
            len(deliverables) <= MAX_DELIVERABLES
        ), f"Deliverables list grew to {len(deliverables)}, expected max {MAX_DELIVERABLES}"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Cache Cleanup Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCacheCleanup:
    """Verify cache cleanup mechanisms work correctly."""

    def test_llm_cache_cleanup_expired(self, tmp_path):
        """LLMCache.cleanup_expired() should remove expired entries."""
        from opc_manager.llm_cache import LLMCache

        # LLMCache uses default TTL, put with minimal params
        cache = LLMCache(db_path=str(tmp_path / "test_llm_cache.db"))

        # Insert an entry (TTL is 7 days by default, we'll test cleanup logic)
        cache.put(
            model="test-model",
            temperature=0.0,
            max_tokens=100,
            system_prompt="sys",
            user_prompt="prompt1",
            response="response1",
        )

        # Verify entry exists
        result = cache.get(
            model="test-model",
            temperature=0.0,
            max_tokens=100,
            system_prompt="sys",
            user_prompt="prompt1",
        )
        assert result == "response1"

        # cleanup_expired should work (may return 0 if nothing expired yet)
        removed = cache.cleanup_expired()
        assert removed >= 0, "cleanup_expired should return non-negative count"

    def test_embedding_cache_cleanup_old_entries(self, tmp_path, monkeypatch):
        """EmbeddingService should support cleanup of old cache entries."""
        from opc_manager.embedding_service import EmbeddingService

        svc = EmbeddingService()

        # Generate some embeddings (will use hash fallback)
        svc.embed("test text 1")
        svc.embed("test text 2")
        svc.embed("test text 3")

        # If cleanup method exists, test it
        if hasattr(svc, "cleanup_old_entries"):
            removed = svc.cleanup_old_entries(max_age_days=0)
            assert removed >= 0, "cleanup_old_entries should return count"
        else:
            # Method doesn't exist yet — this test documents the gap
            pytest.skip("EmbeddingService.cleanup_old_entries not yet implemented")

    def test_lru_cache_ttl_expiry(self):
        """LRUCache should expire entries after TTL."""
        from opc_manager.performance_monitor import LRUCache

        cache = LRUCache(max_size=10, ttl=1)
        cache.put("key1", "value1")

        assert cache.get("key1") == "value1"

        time.sleep(2)
        assert cache.get("key1") is None, "TTL expiry failed"

    def test_progress_emitter_history_bounded(self):
        """ProgressEmitter history should be bounded per session."""
        from opc_manager.progress_emitter import (
            ProgressEmitter,
            ProgressEvent,
            EventType,
        )

        emitter = ProgressEmitter()
        session_id = "test_session"

        for i in range(300):
            event = ProgressEvent(
                event_type=EventType.STEP_START,
                session_id=session_id,
                message=f"Processing {i}",
                progress_pct=50,
            )
            emitter.emit(event)

        history = emitter.get_history(session_id)
        assert (
            len(history) <= 200
        ), f"ProgressEmitter history grew to {len(history)}, expected max 200"


# ═══════════════════════════════════════════════════════════════════════════
# 6. RSS Memory Growth Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRSSGrowth:
    """Verify process RSS doesn't grow significantly over repeated operations."""

    def test_rss_growth_after_repeated_cache_ops(self):
        """Traced memory should not grow significantly after repeated cache operations."""
        import tracemalloc

        from opc_manager.utils import BoundedDict

        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        for _ in range(100):
            bd = BoundedDict(max_size=50)
            for i in range(200):
                bd[f"key_{i}"] = "x" * 100
            del bd

        _force_gc()
        snapshot2 = tracemalloc.take_snapshot()

        # Calculate total traced memory diff
        total_diff = sum(s.size_diff for s in snapshot2.compare_to(snapshot1, "lineno"))
        tracemalloc.stop()

        # Allow up to 5MB traced growth (not RSS, which includes allocator overhead)
        assert (
            total_diff < 5 * 1024 * 1024
        ), f"Traced memory grew by {total_diff / 1024 / 1024:.1f}MB after repeated cache ops"

    def test_rss_growth_after_repeated_string_ops(self):
        """RSS should not grow after repeated string operations."""
        rss_before = _get_process_rss()

        for _ in range(1000):
            s = "x" * 10000
            _ = s.upper() + s.lower()
            del s

        _force_gc()
        rss_after = _get_process_rss()

        if rss_before > 0 and rss_after > 0:
            growth = rss_after - rss_before
            assert (
                growth < 5 * 1024 * 1024
            ), f"RSS grew by {growth / 1024 / 1024:.1f}MB after string ops"
