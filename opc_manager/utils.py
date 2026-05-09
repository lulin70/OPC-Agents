"""
公共工具模块 — 三贤者架构共享的数据结构

将重复定义的工具类提取到统一位置，避免代码重复。
"""

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, AsyncIterator, List, Optional
import logging

logger = logging.getLogger(__name__)

DEFAULT_MAX_SIZE = 100
EVENT_QUEUE_MAX_SIZE = 1000


class BoundedDict:
    """有界字典 — 自动清理超限历史记录，防止内存泄漏

    基于 OrderedDict 实现 FIFO 淘汰策略：
    - 新增元素时自动检查容量
    - 超出 max_size 时移除最早插入的元素
    - 线程安全由调用方保证（三贤者架构中 AgentContext 每任务独立）
    """

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE):
        self._data: OrderedDict = OrderedDict()
        self.max_size = max_size

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._cleanup()

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __len__(self) -> int:
        return len(self._data)

    def __bool__(self) -> bool:
        return bool(self._data)

    def __repr__(self) -> str:
        return f"BoundedDict(max_size={self.max_size}, items={len(self._data)})"

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def pop(self, key: str, default: Any = None) -> Any:
        return self._data.pop(key, default)

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def keys(self):
        return self._data.keys()

    def _cleanup(self) -> None:
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)


@dataclass
class Event:
    event_type: str
    step_id: str
    step_name: str
    status: str
    timestamp: float
    duration_ms: float = 0.0
    data: Optional[dict] = None


class EventEmitter:
    def __init__(self, max_queue_size: int = EVENT_QUEUE_MAX_SIZE):
        self._subscribers: List[asyncio.Queue] = []
        self._max_queue_size = max_queue_size

    def emit(self, event_type: str, step_id: str, step_name: str,
             status: str, duration_ms: float = 0.0, data: Optional[dict] = None) -> None:
        event = Event(
            event_type=event_type,
            step_id=step_id,
            step_name=step_name,
            status=status,
            timestamp=time.time(),
            duration_ms=duration_ms,
            data=data
        )
        for queue in self._subscribers:
            try:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait(event)
            except Exception:
                pass

    async def subscribe(self) -> AsyncIterator[Event]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
