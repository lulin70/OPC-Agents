"""
PerformanceMonitor — 性能监控与SLA管理

提供：
- AgentLoop执行耗时监控（SLA: 单次请求<30秒, 反思循环<60秒）
- LLM调用缓存（相同prompt 5分钟内返回缓存结果）
- 性能指标采集与报告
"""

import hashlib
import json
import logging
import os
import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import OrderedDict

logger = logging.getLogger(__name__)

SLA_SINGLE_REQUEST_MS = 30000
SLA_REFLECT_LOOP_MS = 60000
LLM_CACHE_TTL_SECONDS = 300
LLM_CACHE_MAX_SIZE = 100


@dataclass
class PerformanceMetric:
    operation: str
    duration_ms: float
    success: bool
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class LRUCache:

    def __init__(self, max_size: int = LLM_CACHE_MAX_SIZE, ttl: int = LLM_CACHE_TTL_SECONDS):
        self._max_size = max_size
        self._ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return value
                del self._cache[key]
            self._misses += 1
            return None

    def put(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (value, time.time())

    @staticmethod
    def make_key(prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def get_stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }


class PerformanceMonitor:

    PERSIST_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "perf_metrics.json")

    def __init__(self):
        self._metrics: List[PerformanceMetric] = []
        self._llm_cache = LRUCache()
        self._max_metrics = 1000
        self._lock = threading.Lock()
        self._persist_interval = 60
        self._last_persist = 0.0

    def record(self, operation: str, duration_ms: float, success: bool = True, **metadata) -> None:
        metric = PerformanceMetric(
            operation=operation, duration_ms=duration_ms,
            success=success, metadata=metadata
        )
        should_persist = False
        with self._lock:
            self._metrics.append(metric)
            if len(self._metrics) > self._max_metrics:
                self._metrics = self._metrics[-self._max_metrics:]
            now = time.time()
            if now - self._last_persist > self._persist_interval:
                self._last_persist = now
                should_persist = True

        if operation == "agent_loop" and duration_ms > SLA_SINGLE_REQUEST_MS:
            logger.warning(f"SLA breach: agent_loop took {duration_ms:.0f}ms (SLA: {SLA_SINGLE_REQUEST_MS}ms)")
        if operation == "reflect_loop" and duration_ms > SLA_REFLECT_LOOP_MS:
            logger.warning(f"SLA breach: reflect_loop took {duration_ms:.0f}ms (SLA: {SLA_REFLECT_LOOP_MS}ms)")

        if should_persist:
            self._persist_metrics()

    def cache_get(self, prompt: str) -> Optional[str]:
        key = LRUCache.make_key(prompt)
        return self._llm_cache.get(key)

    def cache_put(self, prompt: str, response: str) -> None:
        key = LRUCache.make_key(prompt)
        self._llm_cache.put(key, response)

    def get_stats(self) -> Dict[str, Any]:
        if not self._metrics:
            return {"total_operations": 0}
        
        by_op = {}
        for m in self._metrics:
            if m.operation not in by_op:
                by_op[m.operation] = []
            by_op[m.operation].append(m.duration_ms)
        
        op_stats = {}
        for op, durations in by_op.items():
            op_stats[op] = {
                "count": len(durations),
                "avg_ms": sum(durations) / len(durations),
                "max_ms": max(durations),
                "min_ms": min(durations),
                "p95_ms": sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0],
            }
        
        return {
            "total_operations": len(self._metrics),
            "operations": op_stats,
            "cache": self._llm_cache.get_stats(),
        }

    def check_sla(self) -> Dict[str, Any]:
        sla_status = {"single_request": True, "reflect_loop": True}
        with self._lock:
            for m in self._metrics:
                if m.operation == "agent_loop" and m.duration_ms > SLA_SINGLE_REQUEST_MS:
                    sla_status["single_request"] = False
                if m.operation == "reflect_loop" and m.duration_ms > SLA_REFLECT_LOOP_MS:
                    sla_status["reflect_loop"] = False
        return sla_status

    def _persist_metrics(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.PERSIST_FILE), exist_ok=True)
            with self._lock:
                data = [{"op": m.operation, "ms": m.duration_ms, "ok": m.success, "ts": m.timestamp} for m in self._metrics[-200:]]
            with open(self.PERSIST_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Metrics persist failed: {e}")

    def _load_metrics(self) -> None:
        try:
            if os.path.exists(self.PERSIST_FILE):
                with open(self.PERSIST_FILE, "r") as f:
                    data = json.load(f)
                with self._lock:
                    for d in data[-200:]:
                        self._metrics.append(PerformanceMetric(
                            operation=d["op"], duration_ms=d["ms"],
                            success=d.get("ok", True), timestamp=d.get("ts", 0)
                        ))
        except Exception as e:
            logger.warning(f"Metrics load failed: {e}")


performance_monitor = PerformanceMonitor()
