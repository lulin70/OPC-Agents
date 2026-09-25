"""PromiseLink v0.9.0 API client for OPC-Agents v1.0.0.

契约来源（不得偏离）:
  - docs/architecture/TDD_V1.0.0.md §3.1 已确认路由（17 条）
  - docs/architecture/TDD_V1.0.0.md §3.2 明确不使用的路径（禁止封装）
  - docs/architecture/TDD_V1.0.0.md §3.3 客户端职责
  - docs/architecture/TDD_V1.0.0.md §3.4 失败状态
  - docs/spec/SKILL_FREEZE_LIST_V1.0.0.md §八 Skill 输出结构化约束

安全约束:
  - Bearer Token 从环境变量 PROMISELINK_TOKEN 或 SecureKeyStore 读取
  - 任何日志不得出现明文 Token
  - 默认 PROMISELINK_ENABLED=false，启用需显式配置
"""

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 0.5
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_RESET_SECONDS = 30.0

RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})
RATE_LIMIT_STATUS = 429

TOKEN_ENV = "PROMISELINK_TOKEN"
TOKEN_KEYSTORE_NAME = "PROMISELINK_TOKEN"
BASE_URL_ENV = "PROMISELINK_BASE_URL"
ENABLED_ENV = "PROMISELINK_ENABLED"


class ClientState(str, Enum):
    """TDD §3.4 显式失败状态。"""

    DISABLED = "DISABLED"
    UNCONFIGURED = "UNCONFIGURED"
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"


@dataclass
class ClientResult:
    """结构化且可校验的输出（SKILL_FREEZE_LIST §八）。

    失败时 state 给出 TDD §3.4 显式状态，error 给出用户可见原因，
    不静默吞掉。
    """

    success: bool
    state: ClientState
    data: Optional[Any] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    trace_id: str = ""
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "state": self.state.value,
            "data": self.data,
            "error": self.error,
            "status_code": self.status_code,
            "trace_id": self.trace_id,
            "duration_ms": self.duration_ms,
        }


def _new_trace_id() -> str:
    return uuid.uuid4().hex


class PromiseLinkClient:
    """PromiseLink v0.9.0 唯一 HTTP 出口。

    - 仅封装 TDD §3.1 已确认路由
    - 超时 / 指数退避 / 429 Retry-After / circuit breaker
    - 响应 schema 最小校验，不匹配返回 SCHEMA_MISMATCH
    - trace_id 贯穿每次调用并记录耗时
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
        transport: Optional[httpx.BaseTransport] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        enabled: Optional[bool] = None,
    ) -> None:
        resolved_base_url = base_url or os.environ.get(BASE_URL_ENV) or ""
        self._base_url = resolved_base_url.rstrip("/")
        self._explicit_token = token
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._transport = transport
        self._sleep_fn = sleep_fn

        if enabled is None:
            enabled = os.environ.get(ENABLED_ENV, "false").strip().lower() in (
                "1",
                "true",
                "yes",
            )
        self._enabled = enabled

        self._lock = threading.RLock()
        self._consecutive_failures = 0
        self._circuit_opened_at: Optional[float] = None

    # ------------------------------------------------------------------
    # 配置与状态
    # ------------------------------------------------------------------

    def _resolve_token(self) -> Optional[str]:
        if self._explicit_token:
            return self._explicit_token
        env_token = os.environ.get(TOKEN_ENV, "")
        if env_token:
            return env_token
        try:
            from opc_manager.secure_storage import SecureKeyStore

            return SecureKeyStore().get_key(TOKEN_KEYSTORE_NAME)
        except Exception as exc:  # pragma: no cover - keystore 环境异常
            logger.warning(
                "[PromiseLinkClient] keystore 读取失败: %s", type(exc).__name__
            )
            return None

    def is_configured(self) -> bool:
        return bool(self._base_url) and bool(self._resolve_token())

    def state(self) -> ClientState:
        if not self._enabled:
            return ClientState.DISABLED
        if not self.is_configured():
            return ClientState.UNCONFIGURED
        with self._lock:
            if self._circuit_opened_at is not None:
                return ClientState.CIRCUIT_OPEN
        return ClientState.AVAILABLE

    def is_available(self) -> bool:
        """TDD §4.2 读路径入口：探活成功且未被熔断。"""
        if self.state() not in (ClientState.AVAILABLE, ClientState.DEGRADED):
            return False
        result = self.health()
        return result.success

    # ------------------------------------------------------------------
    # 熔断器
    # ------------------------------------------------------------------

    def _circuit_open(self) -> bool:
        with self._lock:
            if self._circuit_opened_at is None:
                return False
            elapsed = time.monotonic() - self._circuit_opened_at
            if elapsed >= CIRCUIT_RESET_SECONDS:
                # 半开：放行一次探测请求，失败会重新开门
                logger.info("[PromiseLinkClient] 熔断半开，放行探测 trace 请求")
                return False
            return True

    def _record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= CIRCUIT_FAILURE_THRESHOLD:
                if self._circuit_opened_at is None:
                    logger.warning(
                        "[PromiseLinkClient] 连续失败 %d 次，熔断打开 %.0fs",
                        self._consecutive_failures,
                        CIRCUIT_RESET_SECONDS,
                    )
                self._circuit_opened_at = time.monotonic()

    def _record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._circuit_opened_at = None

    # ------------------------------------------------------------------
    # 请求核心
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        required_keys: tuple = (),
        required_list: bool = False,
    ) -> ClientResult:
        trace_id = _new_trace_id()
        started = time.monotonic()

        def finish(result: ClientResult) -> ClientResult:
            result.trace_id = trace_id
            result.duration_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                "[PromiseLinkClient] %s %s state=%s status=%s duration_ms=%d trace_id=%s",
                method,
                path,
                result.state.value,
                result.status_code,
                result.duration_ms,
                trace_id,
            )
            return result

        if not self._enabled:
            return finish(
                ClientResult(False, ClientState.DISABLED, error="PromiseLink 未启用")
            )
        if not self.is_configured():
            return finish(
                ClientResult(
                    False,
                    ClientState.UNCONFIGURED,
                    error="缺少 PROMISELINK_BASE_URL 或 Token",
                )
            )
        if self._circuit_open():
            return finish(
                ClientResult(
                    False, ClientState.CIRCUIT_OPEN, error="连续失败熔断中，稍后重试"
                )
            )

        headers = {"Authorization": f"Bearer {self._resolve_token()}"}

        attempt = 0
        while True:
            try:
                with httpx.Client(
                    base_url=self._base_url,
                    timeout=self._timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = client.request(
                        method,
                        f"{API_PREFIX}{path}",
                        params=params,
                        json=json_body,
                        headers=headers,
                    )
            except httpx.HTTPError as exc:
                attempt += 1
                if attempt > self._max_retries:
                    self._record_failure()
                    return finish(
                        ClientResult(
                            False,
                            ClientState.DEGRADED,
                            error=f"网络错误: {type(exc).__name__}",
                        )
                    )
                self._sleep_fn(self._backoff_base_seconds * (2 ** (attempt - 1)))
                continue

            if response.status_code == RATE_LIMIT_STATUS:
                attempt += 1
                if attempt > self._max_retries:
                    self._record_failure()
                    return finish(
                        ClientResult(
                            False,
                            ClientState.DEGRADED,
                            status_code=response.status_code,
                            error="请求过于频繁(429)，重试耗尽",
                        )
                    )
                retry_after = response.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.replace(".", "", 1).isdigit()
                    else (self._backoff_base_seconds * (2 ** (attempt - 1)))
                )
                self._sleep_fn(delay)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES:
                attempt += 1
                if attempt > self._max_retries:
                    self._record_failure()
                    return finish(
                        ClientResult(
                            False,
                            ClientState.DEGRADED,
                            status_code=response.status_code,
                            error=f"服务端错误 {response.status_code}，重试耗尽",
                        )
                    )
                self._sleep_fn(self._backoff_base_seconds * (2 ** (attempt - 1)))
                continue

            if response.status_code >= 400:
                self._record_failure()
                return finish(
                    ClientResult(
                        False,
                        ClientState.DEGRADED,
                        status_code=response.status_code,
                        error=f"请求失败 {response.status_code}",
                    )
                )

            data = self._validate_schema(
                response, required_keys=required_keys, required_list=required_list
            )
            if isinstance(data, ClientResult):
                # SCHEMA_MISMATCH 属于契约破坏：显式失败，不计入熔断计数
                return finish(data)

            self._record_success()
            return finish(
                ClientResult(
                    True,
                    ClientState.AVAILABLE,
                    data=data,
                    status_code=response.status_code,
                )
            )

    @staticmethod
    def _validate_schema(
        response: httpx.Response, required_keys: tuple, required_list: bool
    ) -> Any:
        try:
            payload = response.json()
        except ValueError:
            return ClientResult(
                False,
                ClientState.SCHEMA_MISMATCH,
                status_code=response.status_code,
                error="响应不是合法 JSON",
            )
        if required_list:
            if not isinstance(payload, list):
                return ClientResult(
                    False,
                    ClientState.SCHEMA_MISMATCH,
                    status_code=response.status_code,
                    error="响应契约不匹配: 期望列表",
                )
            return payload
        if required_keys and not isinstance(payload, dict):
            return ClientResult(
                False,
                ClientState.SCHEMA_MISMATCH,
                status_code=response.status_code,
                error="响应契约不匹配: 期望对象",
            )
        missing = [key for key in required_keys if key not in payload]
        if missing:
            return ClientResult(
                False,
                ClientState.SCHEMA_MISMATCH,
                status_code=response.status_code,
                error=f"响应契约不匹配: 缺少字段 {missing}",
            )
        return payload

    # ------------------------------------------------------------------
    # DTO 映射（外部 → OPC-Agents 内部结构）
    # ------------------------------------------------------------------

    @staticmethod
    def map_entity_dto(entity: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "entity_id": entity.get("id") or entity.get("entity_id"),
            "display_name": entity.get("name") or entity.get("display_name") or "",
            "source": "promiselink",
            "last_synced_at": entity.get("updated_at") or "",
            "raw": entity,
        }

    # ==================================================================
    # TDD §3.1 已确认路由（17 条）。禁止封装 §3.2 不存在的路径。
    # ==================================================================

    def health(self) -> ClientResult:
        """GET /api/v1/health — 启用前探活。"""
        return self._request("GET", "/health", required_keys=("status",))

    def post_event(self, payload: Dict[str, Any]) -> ClientResult:
        """POST /api/v1/events — 触发完整异步管线。"""
        return self._request("POST", "/events", json_body=payload)

    def get_event(self, event_id: str) -> ClientResult:
        """GET /api/v1/events/{event_id} — 轮询处理状态。"""
        return self._request("GET", f"/events/{event_id}")

    def list_entities(
        self,
        search: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> ClientResult:
        """GET /api/v1/entities — 搜索/过滤/分页。"""
        params: Dict[str, Any] = {}
        if search:
            params["search"] = search
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        return self._request("GET", "/entities", params=params, required_list=True)

    def list_dormant_entities(self, min_days: int) -> ClientResult:
        """GET /api/v1/entities/dormant?min_days=N — CRM 核心路径。

        注意：参数名固定为 min_days，禁止使用 §3.2 禁用的 dormant_days。
        """
        return self._request(
            "GET",
            "/entities/dormant",
            params={"min_days": min_days},
            required_list=True,
        )

    def get_entity(self, entity_id: str) -> ClientResult:
        """GET /api/v1/entities/{entity_id} — CRM 详情。"""
        return self._request("GET", f"/entities/{entity_id}")

    def get_entity_stage_info(self, entity_id: str) -> ClientResult:
        """GET /api/v1/entities/{entity_id}/stage-info — 生命周期。"""
        return self._request("GET", f"/entities/{entity_id}/stage-info")

    def get_relationship_brief(self, entity_id: str) -> ClientResult:
        """GET /api/v1/persons/{entity_id}/relationship-brief/aggregated — 关系卡。"""
        return self._request(
            "GET", f"/persons/{entity_id}/relationship-brief/aggregated"
        )

    def list_todos(
        self, status: Optional[str] = None, page: Optional[int] = None
    ) -> ClientResult:
        """GET /api/v1/todos — 跟进队列。"""
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        if page is not None:
            params["page"] = page
        return self._request("GET", "/todos", params=params, required_list=True)

    def list_promises(self, direction: Optional[str] = None) -> ClientResult:
        """GET /api/v1/promises — 双向承诺。"""
        params = {"direction": direction} if direction else None
        return self._request("GET", "/promises", params=params, required_list=True)

    def get_promise_stats(self) -> ClientResult:
        """GET /api/v1/promises/stats — 经营摘要。"""
        return self._request("GET", "/promises/stats")

    def get_nudge_draft(self, todo_id: str) -> ClientResult:
        """GET /api/v1/promises/{todo_id}/nudge-draft — 仅草稿，不自动发送。"""
        return self._request("GET", f"/promises/{todo_id}/nudge-draft")

    def get_daily_reminders(self) -> ClientResult:
        """GET /api/v1/reminders/daily — 早报/提醒。"""
        return self._request("GET", "/reminders/daily")

    def get_reminder_preferences(self) -> ClientResult:
        """GET /api/v1/reminders/preferences — 疲劳控制。"""
        return self._request("GET", "/reminders/preferences")

    def patch_reminder_preferences(self, payload: Dict[str, Any]) -> ClientResult:
        """PATCH /api/v1/reminders/preferences — 疲劳控制。"""
        return self._request("PATCH", "/reminders/preferences", json_body=payload)

    def create_scheduled_event(self, payload: Dict[str, Any]) -> ClientResult:
        """POST /api/v1/scheduled-events — 一次性关系事件，不是 cron 后端（TDD §5.6）。"""
        return self._request("POST", "/scheduled-events", json_body=payload)

    def list_scheduled_events(self) -> ClientResult:
        """GET /api/v1/scheduled-events — 一次性排程事件列表。"""
        return self._request("GET", "/scheduled-events", required_list=True)

    def get_morning_brief(self) -> ClientResult:
        """GET /api/v1/dashboard/morning-brief — 经营早报。"""
        return self._request("GET", "/dashboard/morning-brief")

    def get_care_reminders(self) -> ClientResult:
        """GET /api/v1/dashboard/care-reminders — 关系维护。"""
        return self._request("GET", "/dashboard/care-reminders")
