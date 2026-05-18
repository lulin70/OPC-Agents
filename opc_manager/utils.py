"""
公共工具模块 — 三贤者架构共享的数据结构

将重复定义的工具类提取到统一位置，避免代码重复。
"""

import os

import asyncio
import json
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, AsyncIterator, List, Optional
import logging

logger = logging.getLogger(__name__)

DEFAULT_MAX_SIZE = 100
EVENT_QUEUE_MAX_SIZE = 1000
LLM_CONCURRENCY_LIMIT = 5

_llm_thread_semaphore = threading.Semaphore(LLM_CONCURRENCY_LIMIT)

_INJECTION_PATTERNS = [
    re.compile(r"(?i)(ignore|忽略)\s*(previous|之前的|above)\s*(instruction|指令|prompt)", re.IGNORECASE),
    re.compile(r"(?i)system\s*:", re.IGNORECASE),
    re.compile(r"(?i)(you\s+are\s+now|你现在是)", re.IGNORECASE),
    re.compile(r"(?i)(forget|忘记)\s*(everything|所有|previous|之前的)", re.IGNORECASE),
    re.compile(r"(?i)(new\s+instruction|新指令|override|覆盖)", re.IGNORECASE),
]


def extract_json_from_llm(text: str) -> Optional[dict]:
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    start = -1
                    continue
    return None


def call_llm_service(llm_service, prompt: str, max_tokens: int = 500, timeout: int = 15) -> Optional[str]:
    if not llm_service:
        return None
    try:
        if hasattr(llm_service, 'complete'):
            return llm_service.complete(prompt, max_tokens=max_tokens, timeout=timeout)
        elif hasattr(llm_service, 'generate'):
            return llm_service.generate(prompt, max_tokens=max_tokens, timeout=timeout)
        elif hasattr(llm_service, '_call_llm_api'):
            return llm_service._call_llm_api(prompt)
    except Exception as e:
        logger.warning("LLM调用失败: %s", e)
    return None


def parse_date_from_text(text: str, default: str = "") -> str:
    from datetime import datetime, timedelta

    today = time.strftime("%Y-%m-%d")
    if "今天" in text or "今日" in text:
        return today
    if "明天" in text:
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    if "后天" in text:
        return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    if "下周一" in text:
        d = datetime.now()
        days_ahead = 7 - d.weekday()
        return (d + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    if "下周五" in text:
        d = datetime.now()
        days_ahead = (4 - d.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (d + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    m = re.search(r'(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})', text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return default if default else today


def load_json_data(relative_path: str) -> Any:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, relative_path)
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_for_llm(text: str, max_len: int = 800) -> str:
    sanitized = text[:max_len].replace("```", "").replace("---", "")
    for pattern in _INJECTION_PATTERNS:
        sanitized = pattern.sub("[FILTERED]", sanitized)
    return sanitized


class BoundedDict:
    """有界字典 — 自动清理超限历史记录，防止内存泄漏

    基于 OrderedDict 实现 FIFO 淘汰策略：
    - 新增元素时自动检查容量
    - 超出 max_size 时移除最早插入的元素
    - 线程安全：内置 threading.Lock 保护并发访问
    """

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE):
        self._data: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self.max_size = max_size

    def __setitem__(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._cleanup()

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            return self._data[key]

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def __delitem__(self, key: str) -> None:
        with self._lock:
            del self._data[key]

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __bool__(self) -> bool:
        with self._lock:
            return bool(self._data)

    def __repr__(self) -> str:
        with self._lock:
            return f"BoundedDict(max_size={self.max_size}, items={len(self._data)})"

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def pop(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.pop(key, default)

    def items(self):
        with self._lock:
            return list(self._data.items())

    def values(self):
        with self._lock:
            return list(self._data.values())

    def keys(self):
        with self._lock:
            return list(self._data.keys())

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
            except Exception as e:
                logger.debug("[Utils] Progress event queue put failed: %s", e)

    async def subscribe(self) -> AsyncIterator[Event]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self.unsubscribe(queue)

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def cleanup(self) -> None:
        for queue in self._subscribers:
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
        self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
