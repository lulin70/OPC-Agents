"""
OPC-Agents 性能与压力测试

覆盖模块:
- DataManager: SQLite 数据层性能
- LLMCache: LLM 响应缓存性能
- PerformanceMonitor & LRUCache: 性能监控与缓存
- TaskEngineV3: 任务引擎吞吐量
- 内存与资源限制
- 并发压力测试

所有文件操作使用 tmp_path，不触碰真实 data/ 目录。
"""

import os
import sys
import time
import threading
import sqlite3
import gc
from unittest.mock import patch, MagicMock

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """将 DATA_DIR 重定向到 tmp_path，确保测试隔离"""
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    monkeypatch.setenv("OPC_DATA_DIR", data_dir)

    # 重置 DataManager 模块级状态，确保每个测试使用独立的 DB
    import opc_manager.data_manager as dm
    dm._db_initialized = False
    dm._local = threading.local()
    dm._fallback_key = None

    yield

    # 清理：关闭可能残留的连接
    if hasattr(dm._local, "conn") and dm._local.conn is not None:
        try:
            dm._local.conn.close()
        except Exception:
            pass
        dm._local.conn = None
    dm._db_initialized = False


@pytest.fixture
def data_manager(tmp_path):
    """提供已初始化的 DataManager 模块"""
    import opc_manager.data_manager as dm
    dm.init_db()
    return dm


@pytest.fixture
def llm_cache(tmp_path):
    """提供独立的 LLMCache 实例"""
    from opc_manager.llm_cache import LLMCache
    db_path = str(tmp_path / "test_llm_cache.db")
    cache = LLMCache(db_path, ttl=3600)
    yield cache
    cache.close()


@pytest.fixture
def lru_cache():
    """提供独立的 LRUCache 实例"""
    from opc_manager.performance_monitor import LRUCache
    return LRUCache(max_size=50, ttl=300)


@pytest.fixture
def performance_monitor(tmp_path, monkeypatch):
    """提供独立的 PerformanceMonitor 实例"""
    from opc_manager.performance_monitor import PerformanceMonitor
    monkeypatch.setattr(
        PerformanceMonitor, "PERSIST_FILE",
        str(tmp_path / "perf_metrics.json")
    )
    return PerformanceMonitor()


# ============================================================================
# 1. DataManager 性能测试
# ============================================================================


class TestDataManagerPerformance:
    """DataManager SQLite 数据层性能测试"""

    def test_batch_insert_1000_finance_records(self, data_manager):
        """批量插入 1000 条 finance_records，耗时 < 5 秒"""
        # 先清空表，避免其他测试残留数据
        data_manager.execute_write("DELETE FROM finance_records")

        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        rows = [
            (
                data_manager.gen_id(),
                "income" if i % 2 == 0 else "expense",
                100.0 + i,
                f"category_{i % 10}",
                f"source_{i}",
                "2024-01-01",
                f"note_{i}",
                now,
            )
            for i in range(1000)
        ]

        start = time.time()
        data_manager.execute_write(
            "INSERT INTO finance_records "
            "(id, type, amount, category, source, date, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            params=rows,
            many=True,
        )
        elapsed = time.time() - start

        assert elapsed < 5.0, f"批量插入 1000 条耗时 {elapsed:.2f}s，超过 5s 阈值"

        # 验证数据完整性
        count = data_manager.execute_query("SELECT COUNT(*) as cnt FROM finance_records")
        assert count[0]["cnt"] == 1000

    def test_batch_query_1000_records(self, data_manager):
        """批量查询 1000 条记录，耗时 < 1 秒"""
        # 先清空表，避免其他测试残留数据
        data_manager.execute_write("DELETE FROM finance_records")

        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        rows = [
            (
                data_manager.gen_id(),
                "income" if i % 2 == 0 else "expense",
                100.0 + i,
                f"category_{i % 10}",
                f"source_{i}",
                "2024-01-01",
                f"note_{i}",
                now,
            )
            for i in range(1000)
        ]
        data_manager.execute_write(
            "INSERT INTO finance_records "
            "(id, type, amount, category, source, date, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            params=rows,
            many=True,
        )

        start = time.time()
        results = data_manager.execute_query("SELECT * FROM finance_records")
        elapsed = time.time() - start

        assert elapsed < 1.0, f"查询 1000 条耗时 {elapsed:.2f}s，超过 1s 阈值"
        assert len(results) >= 1000

    def test_concurrent_write_stress(self, data_manager):
        """10 线程 × 100 次写入，验证无数据损坏"""
        errors = []
        written_ids = []
        lock = threading.Lock()

        def writer(thread_id):
            try:
                for j in range(100):
                    rid = data_manager.gen_id()
                    now = time.strftime("%Y-%m-%dT%H:%M:%S")
                    data_manager.execute_write(
                        "INSERT INTO finance_records "
                        "(id, type, amount, category, source, date, note, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        params=(
                            rid, "income", 50.0 + thread_id,
                            f"concurrent_cat_{thread_id}",
                            f"source_t{thread_id}_j{j}",
                            "2024-06-01", f"thread_{thread_id}_note_{j}", now,
                        ),
                    )
                    with lock:
                        written_ids.append(rid)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"并发写入出错: {errors}"
        assert len(written_ids) == 1000, f"预期写入 1000 条，实际 {len(written_ids)}"

        # 验证数据完整性：所有 ID 都在数据库中
        all_records = data_manager.execute_query("SELECT id FROM finance_records")
        db_ids = {r["id"] for r in all_records}
        missing = set(written_ids) - db_ids
        assert len(missing) == 0, f"有 {len(missing)} 条记录丢失"

    def test_large_result_set_5000_plus_rows(self, data_manager):
        """查询返回 5000+ 行，验证内存和时间可控"""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        rows = [
            (
                data_manager.gen_id(),
                "expense",
                10.0 + i,
                "bulk_cat",
                "bulk_src",
                "2024-03-01",
                f"bulk_note_{i}",
                now,
            )
            for i in range(5000)
        ]
        data_manager.execute_write(
            "INSERT INTO finance_records "
            "(id, type, amount, category, source, date, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            params=rows,
            many=True,
        )

        start = time.time()
        results = data_manager.execute_query("SELECT * FROM finance_records")
        elapsed = time.time() - start

        assert len(results) >= 5000
        assert elapsed < 3.0, f"查询 5000+ 行耗时 {elapsed:.2f}s，超过 3s 阈值"


# ============================================================================
# 2. LLMCache 性能测试
# ============================================================================


class TestLLMCachePerformance:
    """LLMCache SQLite 缓存性能测试"""

    def test_cache_hit_rate_repeated_queries(self, llm_cache):
        """100 次相同查询 → 命中率 99%+"""
        model = "test-model"
        temperature = 0.3
        max_tokens = 1000
        system_prompt = "You are a helpful assistant."
        user_prompt = "What is OPC-Agents?"
        response = "OPC-Agents is a one-person company assistant."

        # 首次 put
        llm_cache.put(model, temperature, max_tokens, system_prompt, user_prompt, response)

        # 99 次 get
        hits = 0
        for _ in range(99):
            result = llm_cache.get(model, temperature, max_tokens, system_prompt, user_prompt)
            if result is not None:
                hits += 1

        hit_rate = hits / 99
        assert hit_rate >= 0.99, f"缓存命中率 {hit_rate:.2%}，低于 99%"

    def test_cache_miss_rate_unique_queries(self, llm_cache):
        """100 次唯一查询 → 命中率 0%"""
        hits = 0
        for i in range(100):
            result = llm_cache.get(
                "model", 0.3, 1000, "system", f"unique_prompt_{i}"
            )
            if result is not None:
                hits += 1

        assert hits == 0, f"唯一查询不应命中缓存，但命中了 {hits} 次"

    def test_bulk_put_get_500_entries(self, llm_cache):
        """批量 put/get 500 条缓存项"""
        start_put = time.time()
        for i in range(500):
            llm_cache.put(
                "model", 0.3, 1000, "system",
                f"bulk_prompt_{i}", f"bulk_response_{i}",
            )
        put_elapsed = time.time() - start_put

        start_get = time.time()
        hits = 0
        for i in range(500):
            result = llm_cache.get("model", 0.3, 1000, "system", f"bulk_prompt_{i}")
            if result is not None:
                hits += 1
        get_elapsed = time.time() - start_get

        assert hits == 500, f"批量 get 命中 {hits}/500"
        assert put_elapsed < 10.0, f"500 次 put 耗时 {put_elapsed:.2f}s"
        assert get_elapsed < 5.0, f"500 次 get 耗时 {get_elapsed:.2f}s"

    def test_cleanup_expired_1000_entries(self, tmp_path):
        """清理 1000 条过期缓存项的性能"""
        from opc_manager.llm_cache import LLMCache

        db_path = str(tmp_path / "cleanup_test.db")
        # TTL=1 秒，使条目快速过期
        cache = LLMCache(db_path, ttl=1)

        for i in range(1000):
            cache.put("model", 0.3, 1000, "sys", f"expire_prompt_{i}", f"resp_{i}")

        # 等待过期
        time.sleep(1.1)

        start = time.time()
        removed = cache.cleanup_expired()
        elapsed = time.time() - start

        assert removed == 1000, f"预期清理 1000 条，实际 {removed}"
        assert elapsed < 5.0, f"清理 1000 条耗时 {elapsed:.2f}s"

        cache.close()

    def test_high_temperature_not_cached(self, llm_cache):
        """高 temperature (>=0.7) 的请求不被缓存"""
        llm_cache.put("model", 0.8, 1000, "sys", "hot_prompt", "response")
        result = llm_cache.get("model", 0.8, 1000, "sys", "hot_prompt")
        assert result is None, "高 temperature 请求不应被缓存"


# ============================================================================
# 3. PerformanceMonitor & LRUCache 性能测试
# ============================================================================


class TestLRUCachePerformance:
    """LRUCache 性能测试"""

    def test_lru_eviction_under_pressure(self, lru_cache):
        """100 条目 + max_size=50 → 验证 LRU 淘汰"""
        # 插入 100 条
        for i in range(100):
            lru_cache.put(f"key_{i}", f"value_{i}")

        # 缓存大小不应超过 max_size
        stats = lru_cache.get_stats()
        assert stats["size"] == 50, f"缓存大小应为 50，实际 {stats['size']}"

        # 前 50 个 key 应被淘汰（LRU），后 50 个应存在
        for i in range(50):
            assert lru_cache.get(f"key_{i}") is None, f"key_{i} 应被淘汰"
        for i in range(50, 100):
            assert lru_cache.get(f"key_{i}") is not None, f"key_{i} 应存在"

    def test_lru_ttl_expiry(self):
        """LRUCache TTL 过期行为"""
        from opc_manager.performance_monitor import LRUCache
        cache = LRUCache(max_size=100, ttl=1)  # 1 秒 TTL

        cache.put("ttl_key", "ttl_value")
        assert cache.get("ttl_key") == "ttl_value", "TTL 内应命中"

        time.sleep(1.1)
        assert cache.get("ttl_key") is None, "TTL 过期后应未命中"

    def test_lru_cache_hit_miss_stats(self, lru_cache):
        """LRUCache 命中/未命中统计准确性"""
        lru_cache.put("stat_key", "stat_value")

        # 1 次命中
        lru_cache.get("stat_key")
        # 2 次未命中
        lru_cache.get("missing_1")
        lru_cache.get("missing_2")

        stats = lru_cache.get_stats()
        assert stats["hits"] == 1, f"命中次数应为 1，实际 {stats['hits']}"
        assert stats["misses"] == 2, f"未命中次数应为 2，实际 {stats['misses']}"
        assert abs(stats["hit_rate"] - 1/3) < 0.01, f"命中率应为 ~0.333，实际 {stats['hit_rate']}"


class TestPerformanceMonitorPerformance:
    """PerformanceMonitor 性能测试"""

    def test_record_1000_metrics(self, performance_monitor):
        """记录 1000 条指标，验证统计计算"""
        for i in range(1000):
            performance_monitor.record(
                "test_op", duration_ms=10.0 + i * 0.1, success=(i % 10 != 0)
            )

        stats = performance_monitor.get_stats()
        assert stats["total_operations"] == 1000
        assert "test_op" in stats["operations"]

        op_stats = stats["operations"]["test_op"]
        assert op_stats["count"] == 1000
        assert op_stats["min_ms"] == pytest.approx(10.0, abs=0.5)
        assert op_stats["max_ms"] == pytest.approx(109.9, abs=0.5)

    def test_sla_breach_detection(self, performance_monitor):
        """SLA 违规检测准确性"""
        from opc_manager.performance_monitor import SLA_SINGLE_REQUEST_MS, SLA_REFLECT_LOOP_MS

        # 正常记录
        performance_monitor.record("agent_loop", duration_ms=1000.0)
        performance_monitor.record("reflect_loop", duration_ms=2000.0)
        sla = performance_monitor.check_sla()
        assert sla["single_request"] is True
        assert sla["reflect_loop"] is True

        # 超出 SLA
        performance_monitor.record("agent_loop", duration_ms=SLA_SINGLE_REQUEST_MS + 1)
        performance_monitor.record("reflect_loop", duration_ms=SLA_REFLECT_LOOP_MS + 1)
        sla = performance_monitor.check_sla()
        assert sla["single_request"] is False
        assert sla["reflect_loop"] is False

    def test_concurrent_record_and_get_stats(self, performance_monitor):
        """并发 record + get_stats 无数据丢失"""
        errors = []

        def recorder():
            try:
                for i in range(200):
                    performance_monitor.record("concurrent_op", duration_ms=float(i))
            except Exception as e:
                errors.append(str(e))

        def stats_reader():
            try:
                for _ in range(50):
                    stats = performance_monitor.get_stats()
                    assert "total_operations" in stats
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=recorder),
            threading.Thread(target=recorder),
            threading.Thread(target=stats_reader),
            threading.Thread(target=stats_reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(errors) == 0, f"并发操作出错: {errors}"

        # 验证记录数正确
        stats = performance_monitor.get_stats()
        assert stats["total_operations"] == 400, \
            f"预期 400 条记录，实际 {stats['total_operations']}"

    def test_max_metrics_cap(self, performance_monitor):
        """验证指标数量上限（_max_metrics=1000）"""
        for i in range(1500):
            performance_monitor.record("cap_op", duration_ms=float(i))

        stats = performance_monitor.get_stats()
        assert stats["total_operations"] == 1000, \
            f"指标应被截断到 1000，实际 {stats['total_operations']}"


# ============================================================================
# 4. TaskEngine 吞吐量测试
# ============================================================================


class TestTaskEngineThroughput:
    """TaskEngineV3 吞吐量测试"""

    @pytest.fixture
    def task_engine(self):
        """提供 TaskEngineV3 实例，mock 掉外部依赖"""
        from opc_manager.task_engine_v3 import TaskEngineV3
        engine = TaskEngineV3()
        # 标记已初始化，跳过懒加载
        engine._initialized = True
        engine.web_search = None
        engine.scenario_engine = None
        engine.llm_content_gen = None
        return engine

    def test_sequential_50_tasks(self, task_engine):
        """顺序执行 50 个任务，测量总耗时"""
        start = time.time()
        results = []
        for i in range(50):
            result = task_engine.execute(f"测试任务 {i}")
            results.append(result)
        elapsed = time.time() - start

        assert len(results) == 50
        # 无搜索/LLM 的纯模板生成应很快
        assert elapsed < 30.0, f"50 个顺序任务耗时 {elapsed:.2f}s，超过 30s"

        # 所有结果应成功
        success_count = sum(1 for r in results if r.success)
        assert success_count == 50, f"成功 {success_count}/50"

    def test_intent_classification_speed(self):
        """100 次意图分类速度"""
        from opc_manager.task_engine_v3 import IntentClassifier

        test_inputs = [
            "帮我收集最新的AI趋势",
            "写一份营销方案",
            "分析一下我的业务现状",
            "执行内容日历场景",
            "你好",
        ] * 20  # 100 次

        start = time.time()
        for inp in test_inputs:
            IntentClassifier.classify(inp)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"100 次意图分类耗时 {elapsed:.2f}s，超过 1s"

    def test_large_content_handling(self, task_engine):
        """大内容 (100KB+) 处理"""
        large_input = "帮我写一份详细的方案 " + "x" * 100000
        # InputValidator 会截断到 2000 字符，但引擎应正常处理
        start = time.time()
        result = task_engine.execute(large_input)
        elapsed = time.time() - start

        assert result is not None
        assert elapsed < 10.0, f"大内容处理耗时 {elapsed:.2f}s"

    def test_task_result_contains_execution_time(self, task_engine):
        """TaskResult 包含 execution_time_ms"""
        result = task_engine.execute("帮我写方案")
        assert hasattr(result, "execution_time_ms")
        assert result.execution_time_ms >= 0


# ============================================================================
# 5. 内存与资源限制测试
# ============================================================================


class TestMemoryAndResourceLimits:
    """内存与资源限制测试"""

    def test_no_file_descriptor_leak_after_db_ops(self, data_manager, tmp_path):
        """多次 DB 操作后无文件描述符泄漏"""
        # 获取当前进程的 FD 数量基线
        import subprocess
        pid = os.getpid()

        try:
            baseline = len(os.listdir(f"/dev/fd/{pid}")) if os.path.exists(f"/dev/fd/{pid}") else 0
        except (OSError, PermissionError):
            # macOS 可能无法访问 /dev/fd，使用 lsof
            try:
                result = subprocess.run(
                    ["lsof", "-p", str(pid)],
                    capture_output=True, text=True, timeout=5
                )
                baseline = len(result.stdout.strip().split("\n"))
            except Exception:
                pytest.skip("无法获取文件描述符计数")

        # 执行大量 DB 操作
        for _ in range(500):
            data_manager.execute_query("SELECT COUNT(*) as cnt FROM finance_records")
            data_manager.execute_write(
                "INSERT OR REPLACE INTO user_preferences (key, value, updated_at) "
                "VALUES (?, ?, ?)",
                params=(f"test_key_{_}", "test_val", time.strftime("%Y-%m-%dT%H:%M:%S")),
            )

        gc.collect()

        try:
            after = len(os.listdir(f"/dev/fd/{pid}")) if os.path.exists(f"/dev/fd/{pid}") else 0
        except (OSError, PermissionError):
            try:
                result = subprocess.run(
                    ["lsof", "-p", str(pid)],
                    capture_output=True, text=True, timeout=5
                )
                after = len(result.stdout.strip().split("\n"))
            except Exception:
                pytest.skip("无法获取文件描述符计数")

        # 允许少量波动，但不应该有大量泄漏（>20）
        fd_growth = after - baseline
        assert fd_growth < 20, f"文件描述符增长 {fd_growth}，可能存在泄漏"

    def test_lru_cache_memory_bounded(self):
        """LRUCache 内存不会无限增长"""
        from opc_manager.performance_monitor import LRUCache

        cache = LRUCache(max_size=100, ttl=300)

        # 插入远超 max_size 的数据
        for i in range(10000):
            cache.put(f"key_{i}", f"value_{i}" * 10)

        stats = cache.get_stats()
        assert stats["size"] == 100, f"缓存大小应为 100，实际 {stats['size']}"

    def test_data_manager_connection_cleanup(self, data_manager):
        """DataManager 连接清理验证"""
        import opc_manager.data_manager as dm

        # 执行一些操作
        for i in range(10):
            data_manager.execute_query("SELECT 1")

        # 验证连接存在
        conn = dm._get_conn()
        assert conn is not None

        # 模拟关闭
        conn.close()
        dm._local.conn = None
        dm._db_initialized = False

        # 重新初始化应正常工作
        dm.init_db()
        result = data_manager.execute_query("SELECT 1 as val")
        assert result[0]["val"] == 1


# ============================================================================
# 6. 并发压力测试
# ============================================================================


class TestConcurrencyStress:
    """并发压力测试"""

    def test_20_threads_data_manager_read_write(self, data_manager):
        """20 线程并发读写 DataManager"""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        errors = []
        results_lock = threading.Lock()
        read_counts = []
        write_counts = []

        def reader(thread_id):
            try:
                count = 0
                for _ in range(50):
                    rows = data_manager.execute_query(
                        "SELECT COUNT(*) as cnt FROM finance_records"
                    )
                    count += 1
                with results_lock:
                    read_counts.append(count)
            except Exception as e:
                with results_lock:
                    errors.append(f"reader_{thread_id}: {e}")

        def writer(thread_id):
            try:
                count = 0
                for j in range(25):
                    rid = data_manager.gen_id()
                    data_manager.execute_write(
                        "INSERT INTO finance_records "
                        "(id, type, amount, category, source, date, note, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        params=(
                            rid, "expense", 10.0, "stress_cat",
                            f"stress_src_{thread_id}", "2024-01-01",
                            f"stress_note_{thread_id}_{j}", now,
                        ),
                    )
                    count += 1
                with results_lock:
                    write_counts.append(count)
            except Exception as e:
                with results_lock:
                    errors.append(f"writer_{thread_id}: {e}")

        threads = []
        # 10 个读线程 + 10 个写线程
        for i in range(10):
            threads.append(threading.Thread(target=reader, args=(i,)))
        for i in range(10):
            threads.append(threading.Thread(target=writer, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"并发读写出错: {errors}"
        assert sum(read_counts) == 500, f"读操作次数不对: {sum(read_counts)}"
        assert sum(write_counts) == 250, f"写操作次数不对: {sum(write_counts)}"

    def test_10_threads_llm_cache(self, llm_cache):
        """10 线程并发使用 LLMCache"""
        errors = []
        hits = []
        lock = threading.Lock()

        def cache_worker(thread_id):
            try:
                local_hits = 0
                for i in range(50):
                    prompt = f"concurrent_prompt_{thread_id}_{i % 5}"
                    # 先尝试 get
                    result = llm_cache.get("model", 0.3, 1000, "sys", prompt)
                    if result is not None:
                        local_hits += 1
                    else:
                        # put 进去
                        llm_cache.put(
                            "model", 0.3, 1000, "sys", prompt,
                            f"response_{thread_id}_{i}",
                        )
                with lock:
                    hits.append(local_hits)
            except Exception as e:
                with lock:
                    errors.append(f"worker_{thread_id}: {e}")

        threads = [threading.Thread(target=cache_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"并发 LLMCache 出错: {errors}"
        # 由于每个线程对 5 个 prompt 重复操作，应有缓存命中
        total_hits = sum(hits)
        assert total_hits > 0, "并发场景下应有缓存命中"

    def test_performance_monitor_singleton_race(self, tmp_path, monkeypatch):
        """PerformanceMonitor 单例竞态条件"""
        from opc_manager.performance_monitor import (
            PerformanceMonitor,
            _reset_performance_monitor,
            get_performance_monitor,
        )

        monkeypatch.setattr(
            PerformanceMonitor, "PERSIST_FILE",
            str(tmp_path / "race_perf.json")
        )
        _reset_performance_monitor()

        instances = []
        lock = threading.Lock()
        errors = []

        def get_monitor():
            try:
                mon = get_performance_monitor()
                with lock:
                    instances.append(id(mon))
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=get_monitor) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"单例竞态出错: {errors}"
        # 所有线程应获得同一个实例
        unique_ids = set(instances)
        assert len(unique_ids) == 1, \
            f"应获得同一实例，但得到 {len(unique_ids)} 个不同实例"

        _reset_performance_monitor()

    def test_data_manager_transaction_integrity(self, data_manager):
        """并发事务完整性验证"""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        errors = []
        success_count = 0
        lock = threading.Lock()

        def transaction_worker(thread_id):
            nonlocal success_count
            try:
                # 使用 execute_transaction 保证原子性
                statements = [
                    (
                        "INSERT INTO finance_records "
                        "(id, type, amount, category, source, date, note, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            data_manager.gen_id(), "income", 100.0,
                            "txn_cat", f"txn_src_{thread_id}", "2024-01-01",
                            f"txn_note_{thread_id}", now,
                        ),
                    ),
                    (
                        "INSERT INTO tasks "
                        "(id, title, description, priority, status, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            data_manager.gen_id(), f"txn_task_{thread_id}",
                            "transaction test", 2, "pending", now,
                        ),
                    ),
                ]
                result = data_manager.execute_transaction(statements)
                with lock:
                    if result:
                        success_count += 1
            except Exception as e:
                with lock:
                    errors.append(f"txn_{thread_id}: {e}")

        threads = [threading.Thread(target=transaction_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"事务执行出错: {errors}"
        assert success_count == 20, f"成功事务 {success_count}/20"
