"""Unit tests for LLM concurrency control (semaphores)."""
import asyncio
import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from opc_manager.utils import (
    LLM_CONCURRENCY_LIMIT,
    _llm_thread_semaphore,
    get_llm_async_semaphore,
)


class TestThreadSemaphore(unittest.TestCase):
    """Test threading semaphore for sync LLM calls."""

    def test_semaphore_limit(self):
        self.assertEqual(LLM_CONCURRENCY_LIMIT, 5)

    def test_semaphore_acquire_release(self):
        self.assertTrue(_llm_thread_semaphore.acquire(blocking=False))
        _llm_thread_semaphore.release()

    def test_concurrent_access_bounded(self):
        """Verify that concurrent access is bounded by LLM_CONCURRENCY_LIMIT."""
        active_count = 0
        max_active = 0
        lock = threading.Lock()
        start_event = threading.Event()

        def worker():
            nonlocal active_count, max_active
            with _llm_thread_semaphore:
                with lock:
                    active_count += 1
                    max_active = max(max_active, active_count)
                # Hold semaphore briefly so other threads can overlap
                start_event.wait(timeout=2)
                with lock:
                    active_count -= 1

        # Start all threads; they will block on start_event while holding semaphore
        threads = [threading.Thread(target=worker) for _ in range(LLM_CONCURRENCY_LIMIT + 3)]
        for t in threads:
            t.start()
        # Give threads time to acquire semaphore up to the limit
        time.sleep(0.3)
        # Release all waiting threads
        start_event.set()
        for t in threads:
            t.join(timeout=10)

        self.assertLessEqual(max_active, LLM_CONCURRENCY_LIMIT)


class TestAsyncSemaphore(unittest.TestCase):
    """Test async semaphore for async LLM calls."""

    def test_get_semaphore_returns_same_instance(self):
        sem1 = get_llm_async_semaphore()
        sem2 = get_llm_async_semaphore()
        self.assertIs(sem1, sem2)

    def test_async_semaphore_bounded(self):
        """Verify async semaphore bounds concurrent access."""
        max_active = 0
        active_count = 0
        lock = asyncio.Lock()

        async def worker(sem):
            nonlocal max_active, active_count
            async with sem:
                async with lock:
                    active_count += 1
                    max_active = max(max_active, active_count)
                await asyncio.sleep(0.05)
                async with lock:
                    active_count -= 1

        async def run_test():
            sem = get_llm_async_semaphore()
            tasks = [worker(sem) for _ in range(LLM_CONCURRENCY_LIMIT + 3)]
            await asyncio.gather(*tasks)

        asyncio.run(run_test())
        self.assertLessEqual(max_active, LLM_CONCURRENCY_LIMIT)


if __name__ == "__main__":
    unittest.main()
