"""
Shared Types for Task Engine v3.5

This module contains data types and utility classes used by both
task_engine_v3.py and task_content_generators.py, extracted to avoid circular imports.
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

MAX_INPUT_LENGTH = 2000


class TaskType(Enum):
    """Task type enum — determines which processing path execute() dispatches to"""

    INFO_COLLECTION = "info_collection"
    CONTENT_GENERATION = "content_generation"
    DATA_ANALYSIS = "data_analysis"
    SCENARIO_BASED = "scenario_based"
    BUSINESS_OPERATION = "business_operation"
    GENERAL_CHAT = "general_chat"


@dataclass
class TaskResult:
    """Unified task execution result container

    Design intent:
    - All execution paths must return this type, ensuring unified frontend handling
    - success field allows frontend to distinguish success/failure and display different UI
    - sources field preserves search source info for displaying reference links
    - execution_time_ms for performance monitoring and timeout diagnostics
    """

    success: bool
    content: str
    task_type: TaskType
    sources: List[Dict[str, str]] = None
    execution_time_ms: float = 0
    error: str = None
    deliverable_format: str = ""
    search_results: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class InputValidator:
    """Input validator — First line of defense for user input entering the engine

    Design intent:
    - Defensive programming: Intercept all invalid input before business logic
    - Security first: Filter control characters to prevent injection, remove HTML tags to prevent XSS
    - Graceful degradation: Truncate overly long input rather than reject, ensuring UX continuity

    Sanitization rules (executed in order):
    1. Empty value detection → Return error message
    2. Leading/trailing whitespace removal
    3. Over-length truncation (2000 char limit) — Prevent DoS and memory overflow
    4. Control character removal (\x00-\x08, \x0b, \x0c, \x0e-\x1f) — Prevent terminal injection
    5. HTML/XML tag removal — Prevent XSS attacks
    """

    @staticmethod
    def sanitize(user_input: str) -> Tuple[str, Optional[str]]:
        if not user_input or not user_input.strip():
            return "", "输入不能为空"
        text = user_input.strip()
        if len(text) > MAX_INPUT_LENGTH:
            text = text[:MAX_INPUT_LENGTH]
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        text = re.sub(r"<[^>]*>", "", text)
        text = re.sub(r"<[^>]*$", "", text)
        return text, None

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Validate URL safety, block dangerous protocols like javascript:"""
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https", ""):
            return ""
        if url.lower().startswith("javascript:"):
            return ""
        return url
