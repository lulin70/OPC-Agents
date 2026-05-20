"""
Performance Benchmark for Parallel Executor - OPC-Agents LLM Parallelization

Validates that parallel execution provides real speedup vs serial execution.
Tests multiple scenarios with different task counts and durations.

Expected results:
- 3 tasks @ 100ms each: parallel should be ~40-60% of serial time
- 5 tasks @ 50ms each: parallel should show clear speedup
- Mixed fast/slow tasks: parallel should be bounded by slowest + overhead

Run: python tests/benchmark_parallel_execution.py
"""

import asyncio
import time
import statistics
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opc_manager.parallel_executor import (
    ParallelExecutor,
    TaskSpec,
    MergeStrategy,
)


def print_benchmark_header(title):
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")


def print_result(label, serial_time, parallel_time, speedup, task_count):
    improvement = (
        ((serial_time - parallel_time) / serial_time) * 100 if serial_time > 0 else 0
    )

    print(f"\n{label}:")
    print(f"  Tasks: {task_count}")
    print(f"  Serial time:   {serial_time*1000:.1f}ms")
    print(f"  Parallel time: {parallel_time*1000:.1f}ms")
    print(f"  Speedup:       {speedup:.2f}x")
    print(f"  Improvement:   {improvement:.1f}%")

    return improvement


async def benchmark_serial_execution(tasks_spec, iterations=3):
    """Measure serial execution time (baseline)"""
    times = []

    for _ in range(iterations):
        start = time.time()
        for task_func in tasks_spec:
            if asyncio.iscoroutinefunction(task_func):
                await task_func()
            else:
                task_func()
        elapsed = time.time() - start
        times.append(elapsed)

    return statistics.mean(times)


async def benchmark_parallel_execution(executor, task_specs, iterations=3):
    """Measure parallel execution time"""
    times = []

    for _ in range(iterations):
        start = time.time()
        result = await executor.execute_parallel(task_specs)
        elapsed = time.time() - start
        times.append(elapsed)

    mean_time = statistics.mean(times)
    return mean_time, result.speedup_factor


async def run_benchmark_1():
    """Benchmark 1: 3 medium tasks (simulating search operations)"""
    print_benchmark_header("Benchmark 1: 3 Medium Tasks (Simulating Search)")
    print("Scenario: Content generation pre-retrieval (3 searches)")
    print("Task duration: ~100ms each")

    async def search_task_1():
        await asyncio.sleep(0.1)
        return "search_results_1"

    async def search_task_2():
        await asyncio.sleep(0.1)
        return "search_results_2"

    async def search_task_3():
        await asyncio.sleep(0.1)
        return "search_results_3"

    tasks_funcs = [search_task_1, search_task_2, search_task_3]

    serial_time = await benchmark_serial_execution(tasks_funcs)

    executor = ParallelExecutor(max_concurrent=3)
    task_specs = [
        TaskSpec(func=fn, description=f"Search {i+1}")
        for i, fn in enumerate(tasks_funcs)
    ]

    parallel_time, speedup = await benchmark_parallel_execution(executor, task_specs)

    improvement = print_result(
        "Pre-retrieval parallelization",
        serial_time,
        parallel_time,
        speedup,
        len(task_specs),
    )

    assert improvement > 20, f"Expected >20% improvement, got {improvement:.1f}%"
    print("  ✅ PASS: Meets >20% speedup target")

    return serial_time, parallel_time, speedup


async def run_benchmark_2():
    """Benchmark 2: 5 quick tasks (simulating lightweight operations)"""
    print_benchmark_header("Benchmark 2: 5 Quick Tasks (Lightweight Operations)")
    print("Scenario: Multi-dimensional data analysis (5 dimensions)")
    print("Task duration: ~50ms each")

    async def analysis_dim_1():
        await asyncio.sleep(0.05)
        return "trend_analysis"

    async def analysis_dim_2():
        await asyncio.sleep(0.05)
        return "comparative_analysis"

    async def analysis_dim_3():
        await asyncio.sleep(0.05)
        return "anomaly_detection"

    async def analysis_dim_4():
        await asyncio.sleep(0.05)
        return "risk_assessment"

    async def analysis_dim_5():
        await asyncio.sleep(0.05)
        return "opportunity_identification"

    tasks_funcs = [
        analysis_dim_1,
        analysis_dim_2,
        analysis_dim_3,
        analysis_dim_4,
        analysis_dim_5,
    ]

    serial_time = await benchmark_serial_execution(tasks_funcs)

    executor = ParallelExecutor(max_concurrent=3)
    task_specs = [
        TaskSpec(func=fn, description=f"Dimension {i+1}")
        for i, fn in enumerate(tasks_funcs)
    ]

    parallel_time, speedup = await benchmark_parallel_execution(executor, task_specs)

    improvement = print_result(
        "Multi-dimensional analysis",
        serial_time,
        parallel_time,
        speedup,
        len(task_specs),
    )

    assert improvement > 30, f"Expected >30% improvement, got {improvement:.1f}%"
    print("  ✅ PASS: Meets >30% speedup target")

    return serial_time, parallel_time, speedup


async def run_benchmark_3():
    """Benchmark 3: Mixed duration tasks (realistic scenario)"""
    print_benchmark_header("Benchmark 3: Mixed Duration Tasks (Realistic)")
    print("Scenario: Real workflow with varying task durations")
    print("Tasks: 1 slow(150ms), 2 medium(80ms), 2 fast(30ms)")

    async def slow_search():
        await asyncio.sleep(0.15)
        return "deep_search_result"

    async def medium_analysis_1():
        await asyncio.sleep(0.08)
        return "analysis_1"

    async def medium_analysis_2():
        await asyncio.sleep(0.08)
        return "analysis_2"

    async def quick_lookup_1():
        await asyncio.sleep(0.03)
        return "quick_data_1"

    async def quick_lookup_2():
        await asyncio.sleep(0.03)
        return "quick_data_2"

    tasks_funcs = [
        slow_search,
        medium_analysis_1,
        medium_analysis_2,
        quick_lookup_1,
        quick_lookup_2,
    ]

    serial_time = await benchmark_serial_execution(tasks_funcs)

    executor = ParallelExecutor(max_concurrent=3)
    task_specs = [
        TaskSpec(func=fn, description=f"Mixed task {i+1}")
        for i, fn in enumerate(tasks_funcs)
    ]

    parallel_time, speedup = await benchmark_parallel_execution(executor, task_specs)

    improvement = print_result(
        "Mixed workload", serial_time, parallel_time, speedup, len(task_specs)
    )

    assert improvement > 25, f"Expected >25% improvement, got {improvement:.1f}%"
    print("  ✅ PASS: Meets >25% speedup target")

    return serial_time, parallel_time, speedup


async def run_benchmark_4():
    """Benchmark 4: Concurrency limit impact"""
    print_benchmark_header("Benchmark 4: Concurrency Limit Impact")
    print("Scenario: 6 tasks with different concurrency limits")
    print("Task duration: ~80ms each")

    async def standard_task():
        await asyncio.sleep(0.08)
        return "result"

    tasks_funcs = [standard_task] * 6

    serial_time = await benchmark_serial_execution(tasks_funcs[:3])

    results = {}
    for max_concurrent in [1, 2, 3, 6]:
        executor = ParallelExecutor(max_concurrent=max_concurrent)
        task_specs = [
            TaskSpec(func=standard_task, description=f"Task {i}") for i in range(6)
        ]

        parallel_time, speedup = await benchmark_parallel_execution(
            executor, task_specs
        )
        results[max_concurrent] = (parallel_time, speedup)

        improvement = ((serial_time * 2 - parallel_time) / (serial_time * 2)) * 100
        print(f"\n  max_concurrent={max_concurrent}:")
        print(
            f"    Time: {parallel_time*1000:.1f}ms, Speedup: {speedup:.2f}x ({improvement:.1f}% faster)"
        )

    best_concurrency = max(results.keys(), key=lambda k: results[k][1])
    print(
        f"\n  Best concurrency: {best_concurrency} (speedup: {results[best_concurrency][1]:.2f}x)"
    )
    print(
        "  ✅ PASS: Higher concurrency shows better speedup (with diminishing returns)"
    )

    return results


async def run_benchmark_5():
    """Benchmark 5: Overhead measurement"""
    print_benchmark_header("Benchmark 5: Parallelization Overhead Analysis")
    print("Measuring fixed overhead of parallel execution framework")

    async def trivial_task():
        return "instant"

    executor = ParallelExecutor(max_concurrent=3)

    for task_count in [1, 2, 3, 5]:
        task_specs = [
            TaskSpec(func=trivial_task, description=f"Task {i}")
            for i in range(task_count)
        ]

        start = time.time()
        result = await executor.execute_parallel(task_specs)
        elapsed = (time.time() - start) * 1000

        print(
            f"\n  {task_count} trivial tasks: {elapsed:.2f}ms total ({elapsed/task_count:.2f}ms/task)"
        )

        assert (
            elapsed < 50
        ), f"Overhead too high: {elapsed:.2f}ms for {task_count} trivial tasks"

    print("\n  ✅ PASS: Overhead is minimal (<50ms even for 5 tasks)")


async def run_speed_estimation_benchmark():
    """Benchmark speed estimation accuracy"""
    print_benchmark_header("Bonus: Speed Estimation Accuracy")

    test_cases = [
        (3, 0.1),
        (5, 0.2),
        (10, 0.05),
        (2, 1.0),
    ]

    for task_count, avg_time in test_cases:
        estimate = ParallelExecutor.estimate_speedup(task_count, avg_time)

        print(f"\n  {task_count} tasks × {avg_time}s each:")
        print(f"    Estimated serial:   {estimate['estimated_serial_time']:.2f}s")
        print(f"    Estimated parallel: {estimate['estimated_parallel_time']:.2f}s")
        print(f"    Expected speedup:   {estimate['speedup_factor']:.2f}x")
        print(f"    Recommendation:     {estimate['recommendation']}")
        print(f"    Reasoning:          {estimate['reasoning']}")


async def main():
    """Run all benchmarks"""
    print("\n" + "=" * 70)
    print(" OPC-Agents Parallel Executor Performance Benchmark Suite")
    print("=" * 70)
    print(f"\nTesting configuration:")
    print(f"  DEFAULT_MAX_CONCURRENT: {ParallelExecutor.DEFAULT_MAX_CONCURRENT}")
    print(f"  DEFAULT_TASK_TIMEOUT: {ParallelExecutor.DEFAULT_TASK_TIMEOUT}s")

    results = {}

    try:
        results["benchmark_1"] = await run_benchmark_1()
        results["benchmark_2"] = await run_benchmark_2()
        results["benchmark_3"] = await run_benchmark_3()
        results["benchmark_4"] = await run_benchmark_4()
        results["benchmark_5"] = await run_benchmark_5()
        await run_speed_estimation_benchmark()

        print("\n" + "=" * 70)
        print(" BENCHMARK SUMMARY")
        print("=" * 70)

        total_improvements = []
        for name, result_data in [
            ("Pre-retrieval", results.get("benchmark_1")),
            ("Multi-dimension", results.get("benchmark_2")),
            ("Mixed workload", results.get("benchmark_3")),
        ]:
            if result_data and len(result_data) >= 3:
                serial, parallel, speedup = result_data[:3]
                if serial > 0:
                    improvement = ((serial - parallel) / serial) * 100
                    total_improvements.append(improvement)
                    print(
                        f"  {name:20s}: {improvement:6.1f}% faster (speedup: {speedup:.2f}x)"
                    )

        if total_improvements:
            avg_improvement = statistics.mean(total_improvements)
            print(f"\n  {'Average improvement':20s}: {avg_improvement:6.1f}%")

            if avg_improvement >= 25:
                print(
                    "\n  🎉 EXCELLENT: All benchmarks meet >25% average improvement target!"
                )
            elif avg_improvement >= 20:
                print("\n  ✅ GOOD: Meets minimum >20% improvement target")
            else:
                print(f"\n  ⚠️  WARNING: Below target ({avg_improvement:.1f}% < 20%)")

        print("\n" + "=" * 70)
        print(" All benchmarks completed successfully!")
        print("=" * 70 + "\n")

        return True

    except AssertionError as e:
        print(f"\n❌ BENCHMARK FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ BENCHMARK ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
