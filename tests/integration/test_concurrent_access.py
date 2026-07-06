"""Concurrent access tests for thread-safety validation.

Tests LLMCache, SkillReviewManager, and module-level singletons
under multi-threaded concurrent access to ensure no data corruption
or crashes occur.
"""

import threading
import time


class TestLLMCacheConcurrency:
    """Test LLMCache under concurrent access."""

    def test_concurrent_puts_and_gets(self, tmp_path):
        """Multiple threads writing and reading cache simultaneously."""
        from opc_manager.llm_cache import LLMCache

        db_path = str(tmp_path / "test_cache.db")
        cache = LLMCache(db_path, ttl=3600)
        errors = []

        def writer(thread_id):
            try:
                for i in range(20):
                    cache.put(
                        model="test-model",
                        temperature=0.3,
                        max_tokens=500,
                        system_prompt="system",
                        user_prompt=f"prompt-t{thread_id}-i{i}",
                        response=f"response-t{thread_id}-i{i}",
                        provider="test",
                    )
            except Exception as e:
                errors.append(f"writer-{thread_id}: {e}")

        def reader(thread_id):
            try:
                for i in range(20):
                    cache.get(
                        model="test-model",
                        temperature=0.3,
                        max_tokens=500,
                        system_prompt="system",
                        user_prompt=f"prompt-t0-i{i}",
                    )
                    # May or may not find it depending on timing
            except Exception as e:
                errors.append(f"reader-{thread_id}: {e}")

        threads = []
        for t in range(3):
            threads.append(threading.Thread(target=writer, args=(t,)))
        for t in range(2):
            threads.append(threading.Thread(target=reader, args=(t,)))

        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(errors) == 0, f"Concurrent errors: {errors}"

    def test_concurrent_cleanup_while_reading(self, tmp_path):
        """Cleanup running while reads happen should not crash."""
        from opc_manager.llm_cache import LLMCache

        db_path = str(tmp_path / "test_cache.db")
        cache = LLMCache(db_path, ttl=1)  # 1 second TTL

        # Add some entries
        for i in range(10):
            cache.put("model", 0.3, 500, "sys", f"prompt-{i}", f"resp-{i}")

        errors = []

        def cleaner():
            try:
                time.sleep(1.5)  # Wait for entries to expire
                cache.cleanup_expired()
            except Exception as e:
                errors.append(f"cleaner: {e}")

        def reader():
            try:
                for i in range(10):
                    cache.get("model", 0.3, 500, "sys", f"prompt-{i}")
            except Exception as e:
                errors.append(f"reader: {e}")

        t1 = threading.Thread(target=cleaner)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Concurrent errors: {errors}"


class TestSkillReviewConcurrency:
    """Test SkillReviewManager under concurrent access."""

    def test_concurrent_add_reviews(self, tmp_path):
        """Multiple threads adding reviews simultaneously."""
        from opc_manager.skill_reviews import SkillReviewManager

        db_path = str(tmp_path / "test_reviews.db")
        mgr = SkillReviewManager(db_path)
        errors = []

        def adder(thread_id):
            try:
                for i in range(10):
                    mgr.add_review(
                        skill_id="skill-1",
                        rating=(i % 5) + 1,
                        review_text=f"Review from thread {thread_id}, iter {i}",
                        user_id=f"user-{thread_id}",
                    )
            except Exception as e:
                errors.append(f"adder-{thread_id}: {e}")

        threads = [threading.Thread(target=adder, args=(t,)) for t in range(5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(errors) == 0, f"Concurrent errors: {errors}"
        # Verify all reviews were written
        count = mgr.get_review_count("skill-1")
        assert count == 50, f"Expected 50 reviews, got {count}"

    def test_concurrent_read_write_reviews(self, tmp_path):
        """Reads and writes happening simultaneously."""
        from opc_manager.skill_reviews import SkillReviewManager

        db_path = str(tmp_path / "test_reviews.db")
        mgr = SkillReviewManager(db_path)

        # Pre-populate
        for i in range(5):
            mgr.add_review("skill-1", i + 1, user_id=f"init-user-{i}")

        errors = []

        def writer():
            try:
                for i in range(10):
                    mgr.add_review("skill-1", (i % 5) + 1, user_id=f"writer-{i}")
            except Exception as e:
                errors.append(f"writer: {e}")

        def reader():
            try:
                for _ in range(10):
                    mgr.get_average_rating("skill-1")
                    mgr.get_review_count("skill-1")
                    mgr.get_reviews("skill-1", limit=5)
            except Exception as e:
                errors.append(f"reader: {e}")

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Concurrent errors: {errors}"


class TestSingletonThreadSafety:
    """Test that module-level singletons are thread-safe."""

    def test_llm_cache_singleton_race(self, tmp_path, monkeypatch):
        """Two threads calling get_llm_cache() simultaneously should get same instance."""
        from opc_manager import llm_cache

        # Reset singleton
        llm_cache._cache_instance = None
        monkeypatch.setenv("OPC_DATA_DIR", str(tmp_path))

        results = []

        def getter():
            cache = llm_cache.get_llm_cache()
            results.append(id(cache))

        threads = [threading.Thread(target=getter) for _ in range(5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        # All should get the same instance
        assert len(set(results)) == 1, f"Got different instances: {results}"

        # Cleanup
        llm_cache._cache_instance = None

    def test_review_manager_singleton_race(self, tmp_path, monkeypatch):
        """Two threads calling get_review_manager() simultaneously should get same instance."""
        from opc_manager import skill_reviews

        # Reset singleton
        skill_reviews._manager = None
        monkeypatch.setenv("OPC_DATA_DIR", str(tmp_path))

        results = []

        def getter():
            mgr = skill_reviews.get_review_manager()
            results.append(id(mgr))

        threads = [threading.Thread(target=getter) for _ in range(5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(set(results)) == 1, f"Got different instances: {results}"

        # Cleanup
        skill_reviews._manager = None
