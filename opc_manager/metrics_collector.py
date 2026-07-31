"""MetricsCollector — OPC-Agents v0.5.0 unified metrics collection entry point.

Implements ADR-004: collects 5 business metrics (activation / upgrade /
flywheel / payment / NPS) and 3 experience metrics (dialogue_naturalness /
result_satisfaction / proactive_service) into a local SQLite database.

Design constraints (HARD_CONSTRAINTS):
- S4: all data stays local by default; export is opt-in and anonymized.
- REL-4-01: WAL mode so writes never block concurrent reads.

Thread safety:
- Singleton via ``__new__`` + class-level lock (mirrors ``AuditLog``).
- All write paths serialize on ``self._lock`` to avoid ``database is locked``.
- Single connection with ``check_same_thread=False`` (mirrors ``data_manager``).

Standalone DB:
- Default path: ``~/.opc-agents/data/metrics.db`` (overridable via
  ``METRICS_DB_PATH`` env var or ``db_path`` ctor arg).
- Schema is created idempotently by ``_ensure_tables`` using the same DDL
  constants as ``opc_manager.migrations.v8_metrics.migrate_v8``.

Usage:
    from opc_manager.metrics_collector import get_metrics_collector
    collector = get_metrics_collector()
    collector.record_activation(user_id="u1", onboarding_completed_at=...,
                                 first_use_at=...)
    collector.record_nps(user_id="u1", score=9, comment="great")
"""

import hashlib
import json
import logging
import os
import secrets
import sqlite3
import stat
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ADR-004 §6: metadata JSON capped at 4KB per row to prevent bloat.
_METADATA_MAX_BYTES = 4096

# Default DB location (HARD_CONSTRAINTS S4: data stays under user home).
_DEFAULT_DB_PATH = "~/.opc-agents/data/metrics.db"
_DEFAULT_SALT_PATH = "~/.opc-agents/data/.metrics_salt"

# Enumerations (centralized for validation + get_summary dispatch).
_EXPERIENCE_METRIC_TYPES = frozenset(
    {"dialogue_naturalness", "result_satisfaction", "proactive_service"}
)
_NPS_METRIC_TYPE = "nps"
_ALL_METRIC_TYPES = _EXPERIENCE_METRIC_TYPES | {_NPS_METRIC_TYPE}
_PAYMENT_STATUSES = frozenset({"trial", "paid", "cancelled", "refunded"})

# Mapping: metric_type -> source table (used by get_summary + export).
_TABLE_FOR_METRIC = {
    "activation": "metrics_activation",
    "upgrade": "metrics_upgrade",
    "flywheel": "metrics_flywheel",
    "payment": "metrics_payment",
    "dialogue_naturalness": "metrics_experience",
    "result_satisfaction": "metrics_experience",
    "proactive_service": "metrics_experience",
    "nps": "metrics_experience",
}

# Feedback categories (api/models.py FeedbackCategory enum values).
_FEEDBACK_CATEGORIES = frozenset({"bug", "suggestion", "praise", "question"})

# v0.5.0 P3 新增表：metrics_feedback + metrics_export_log
# 这些表不在 v8 migration 中（v8 仅覆盖 5 个原始指标表），
# 由 MetricsCollector._ensure_tables 直接创建以保证 standalone DB 可用。
_FEEDBACK_DDL: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS metrics_feedback (
        id          TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL,
        rating      INTEGER NOT NULL,
        comment     TEXT,
        category    TEXT NOT NULL,
        skill_id    TEXT,
        session_id  TEXT,
        timestamp   TEXT NOT NULL,
        metadata    TEXT,
        created_at  TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_feedback_user_id      ON metrics_feedback(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_feedback_created_at   ON metrics_feedback(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_feedback_category     ON metrics_feedback(category)",
    "CREATE INDEX IF NOT EXISTS idx_feedback_user_created ON metrics_feedback(user_id, created_at DESC)",
]

_EXPORT_LOG_DDL: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS metrics_export_log (
        id             TEXT PRIMARY KEY,
        exported_at    TEXT NOT NULL,
        exported_count INTEGER DEFAULT 0,
        metadata       TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_export_log_exported_at ON metrics_export_log(exported_at DESC)",
]


class MetricsCollectionError(Exception):
    """Base exception for MetricsCollector (validation + DB failures)."""


class MetricsDBError(MetricsCollectionError):
    """SQLite write or schema operation failed."""


class MetricsValidationError(MetricsCollectionError):
    """Input validation failed (empty user_id, score out of range, etc.)."""


class MetricsCollector:
    """Unified metrics collection entry point (singleton, thread-safe).

    Implements ADR-004: collects 5 business metrics + 3 experience metrics
    to local SQLite. All data stays local by default (HARD_CONSTRAINTS S4).

    The singleton is process-global: the first call (with or without
    ``db_path``) initializes the connection; subsequent calls return the
    same instance regardless of ``db_path``. Tests reset the singleton
    via ``MetricsCollector._reset_singleton()``.
    """

    _instance: Optional["MetricsCollector"] = None
    _instance_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton plumbing
    # ------------------------------------------------------------------
    def __new__(cls, *args: Any, **kwargs: Any) -> "MetricsCollector":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None) -> None:
        # Guard against re-initialization when singleton already set up.
        # Sprint 4.3 fix: 必须在 _instance_lock 内双检锁，否则多线程并发
        # 调用 MetricsCollector() 时，__new__ 返回同一实例但 __init__ 会并发
        # 执行 _connect_db()，触发 SQLite "database is locked" 异常（CI 环境复现率
        # 高，本地难复现）。__new__ 的双检锁只保证实例唯一，不保证 __init__ 单次执行.
        if getattr(self, "_initialized", False):
            return
        with type(self)._instance_lock:
            if getattr(self, "_initialized", False):
                return
            self._db_path: str = self._resolve_db_path(db_path)
            self._lock = threading.Lock()
            self._conn: Optional[sqlite3.Connection] = None
            self._salt: str = self._resolve_anonymization_salt()
            self._connect_db()
            self._ensure_tables()
            self._initialized = True

    @classmethod
    def _reset_singleton(cls) -> None:
        """Reset the singleton (testing only). Closes any open connection."""
        with cls._instance_lock:
            inst = cls._instance
            if inst is not None:
                try:
                    inst.close()
                except Exception:
                    pass
            cls._instance = None

    @classmethod
    def reset_singleton(cls) -> None:
        """Public alias for ``_reset_singleton`` (v0.5.0 P3 API surface).

        Tests and external callers should use this public classmethod rather
        than the underscore-prefixed private helper. Delegates to
        ``_reset_singleton`` to preserve backward compatibility.
        """
        cls._reset_singleton()

    # ------------------------------------------------------------------
    # Public API: record_* methods
    # ------------------------------------------------------------------
    def record_activation(
        self,
        user_id: str,
        onboarding_completed_at: str,
        first_use_at: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record an activation event (Onboarding COMPLETED + first task use).

        Args:
            user_id: non-empty user identifier.
            onboarding_completed_at: ISO8601 timestamp of onboarding completion.
            first_use_at: ISO8601 timestamp of first task execution.
            metadata: optional JSON-serializable dict (capped at 4KB).

        Returns:
            record_id (UUID v4 hex).

        Raises:
            MetricsValidationError: if user_id is empty or timestamps missing.
            MetricsDBError: if SQLite write fails.
        """
        if not user_id or not user_id.strip():
            raise MetricsValidationError("user_id is required")
        if not onboarding_completed_at:
            raise MetricsValidationError("onboarding_completed_at is required")
        if not first_use_at:
            raise MetricsValidationError("first_use_at is required")
        record_id = uuid.uuid4().hex
        now = self._now_iso()
        self._write(
            "metrics_activation",
            {
                "id": record_id,
                "user_id": user_id,
                "onboarding_completed_at": onboarding_completed_at,
                "first_use_at": first_use_at,
                "activation_criteria_met": 0,
                "activation_met_at": None,
                "days_to_activate": None,
                "metadata": self._serialize_metadata(metadata),
                "created_at": now,
                "updated_at": now,
            },
        )
        return record_id

    def record_upgrade(
        self,
        user_id: str,
        from_version: str,
        to_version: str,
        license_key_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a version upgrade event (basic/pro_trial → pro_activated).

        Args:
            user_id: non-empty user identifier.
            from_version: previous tier ('basic' / 'pro_trial' / None for fresh).
            to_version: new tier (e.g. 'pro_activated').
            license_key_hash: pre-hashed license key (SHA256[:16]); never raw.
            metadata: optional JSON-serializable dict.

        Returns:
            record_id (UUID v4 hex).
        """
        if not user_id or not user_id.strip():
            raise MetricsValidationError("user_id is required")
        if not to_version:
            raise MetricsValidationError("to_version is required")
        record_id = uuid.uuid4().hex
        self._write(
            "metrics_upgrade",
            {
                "id": record_id,
                "user_id": user_id,
                "from_version": from_version,
                "to_version": to_version,
                "upgrade_at": self._now_iso(),
                "license_key": license_key_hash,
                "metadata": self._serialize_metadata(metadata),
                "created_at": self._now_iso(),
            },
        )
        return record_id

    def record_flywheel(
        self,
        user_id: str,
        flywheel_level: int,
        previous_level: Optional[int] = None,
        skills_used: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a flywheel level change (FlywheelTracker L0-L4).

        Args:
            user_id: non-empty user identifier.
            flywheel_level: new level (0-4).
            previous_level: prior level (None for first entry).
            skills_used: list of skill names involved in this cycle.
            metadata: optional JSON-serializable dict.

        Returns:
            record_id (UUID v4 hex).
        """
        if not user_id or not user_id.strip():
            raise MetricsValidationError("user_id is required")
        if not isinstance(flywheel_level, int) or not 0 <= flywheel_level <= 4:
            raise MetricsValidationError(
                f"flywheel_level must be int in 0-4, got {flywheel_level!r}"
            )
        if previous_level is not None and (
            not isinstance(previous_level, int) or not 0 <= previous_level <= 4
        ):
            raise MetricsValidationError(
                f"previous_level must be int in 0-4 or None, got {previous_level!r}"
            )
        record_id = uuid.uuid4().hex
        skills_json = (
            json.dumps(skills_used, ensure_ascii=False) if skills_used else None
        )
        self._write(
            "metrics_flywheel",
            {
                "id": record_id,
                "user_id": user_id,
                "flywheel_level": flywheel_level,
                "previous_level": previous_level,
                "level_up_at": self._now_iso(),
                "skills_used": skills_json,
                "metadata": self._serialize_metadata(metadata),
                "created_at": self._now_iso(),
            },
        )
        return record_id

    def record_payment(
        self,
        user_id: str,
        payment_status: str,
        amount: Optional[float] = None,
        currency: str = "CNY",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a payment conversion event (trial/paid/cancelled/refunded).

        Args:
            user_id: non-empty user identifier.
            payment_status: one of trial/paid/cancelled/refunded.
            amount: payment amount (None for trial; >=0 otherwise).
            currency: ISO 4217 code, default CNY.
            metadata: optional JSON-serializable dict.

        Returns:
            record_id (UUID v4 hex).
        """
        if not user_id or not user_id.strip():
            raise MetricsValidationError("user_id is required")
        if payment_status not in _PAYMENT_STATUSES:
            raise MetricsValidationError(
                f"payment_status must be one of {sorted(_PAYMENT_STATUSES)}, "
                f"got {payment_status!r}"
            )
        if amount is not None:
            if not isinstance(amount, (int, float)) or isinstance(amount, bool):
                raise MetricsValidationError(
                    f"amount must be a number or None, got {amount!r}"
                )
            if amount < 0:
                raise MetricsValidationError(f"amount must be >= 0, got {amount}")
        record_id = uuid.uuid4().hex
        now = self._now_iso()
        self._write(
            "metrics_payment",
            {
                "id": record_id,
                "user_id": user_id,
                "payment_status": payment_status,
                "amount": float(amount) if amount is not None else None,
                "currency": currency,
                "paid_at": now if payment_status == "paid" else None,
                "metadata": self._serialize_metadata(metadata),
                "created_at": now,
            },
        )
        return record_id

    def record_experience(
        self,
        user_id: str,
        metric_type: str,
        score: float,
        skill_id: Optional[str] = None,
        session_id: Optional[str] = None,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record an experience metric score (1.0-5.0) or NPS score (0-10).

        Args:
            user_id: non-empty user identifier.
            metric_type: one of dialogue_naturalness / result_satisfaction /
                proactive_service / nps.
            score: 1.0-5.0 for experience metrics, 0-10 for NPS.
            skill_id: optional related skill id (None for NPS).
            session_id: optional related session id.
            comment: optional user feedback text.
            metadata: optional JSON-serializable dict.

        Returns:
            record_id (UUID v4 hex).
        """
        if not user_id or not user_id.strip():
            raise MetricsValidationError("user_id is required")
        if metric_type not in _ALL_METRIC_TYPES:
            raise MetricsValidationError(
                f"metric_type must be one of {sorted(_ALL_METRIC_TYPES)}, "
                f"got {metric_type!r}"
            )
        # Score range depends on metric_type.
        if metric_type == _NPS_METRIC_TYPE:
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                raise MetricsValidationError(
                    f"NPS score must be a number, got {score!r}"
                )
            if not 0 <= score <= 10:
                raise MetricsValidationError(f"NPS score must be 0-10, got {score}")
            # NPS score is conventionally an integer; coerce for storage.
            score_value: float = float(int(score))
        else:
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                raise MetricsValidationError(
                    f"experience score must be a number, got {score!r}"
                )
            if not 1.0 <= score <= 5.0:
                raise MetricsValidationError(
                    f"experience score must be 1.0-5.0, got {score}"
                )
            score_value = float(score)
        record_id = uuid.uuid4().hex
        now = self._now_iso()
        self._write(
            "metrics_experience",
            {
                "id": record_id,
                "user_id": user_id,
                "metric_type": metric_type,
                "score": score_value,
                "skill_id": skill_id,
                "session_id": session_id,
                "comment": comment,
                "timestamp": now,
                "metadata": self._serialize_metadata(metadata),
                "created_at": now,
            },
        )
        return record_id

    def record_nps(
        self,
        user_id: str,
        score: int,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Convenience wrapper for record_experience(metric_type='nps').

        Args:
            user_id: non-empty user identifier.
            score: NPS score 0-10 (integer).
            comment: optional user feedback text.
            metadata: optional JSON-serializable dict.

        Returns:
            record_id (UUID v4 hex).
        """
        if not isinstance(score, int) or isinstance(score, bool):
            raise MetricsValidationError(f"NPS score must be int 0-10, got {score!r}")
        if not 0 <= score <= 10:
            raise MetricsValidationError(f"NPS score must be 0-10, got {score}")
        return self.record_experience(
            user_id=user_id,
            metric_type=_NPS_METRIC_TYPE,
            score=float(score),
            comment=comment,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Public API: export + summary
    # ------------------------------------------------------------------
    def export_anonymized(
        self,
        start_date: str,
        end_date: str,
        metric_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Export anonymized records for opt-in user-triggered upload.

        Removes ``user_id``, replaces with ``anonymized_user_hash``
        (= SHA256(user_id + salt)[:16]). Returns a flat list across all
        5 metric tables, filtered by ``created_at`` between start_date
        and end_date (inclusive).

        Args:
            start_date: ISO8601 lower bound on ``created_at`` (inclusive).
            end_date: ISO8601 upper bound on ``created_at`` (inclusive).
            metric_types: optional list of metric categories to include.
                Valid values: 'activation' / 'upgrade' / 'flywheel' /
                'payment' / 'experience' (matches table suffix). If None,
                all categories are exported.

        Returns:
            List of dicts, each with original fields (minus ``user_id``)
            plus ``anonymized_user_hash`` and ``metric_category``.
        """
        if not start_date or not end_date:
            raise MetricsValidationError(
                "start_date and end_date are required (ISO8601)"
            )

        # Map requested categories to (table_name, category_label).
        all_categories: List[tuple] = [
            ("metrics_activation", "activation"),
            ("metrics_upgrade", "upgrade"),
            ("metrics_flywheel", "flywheel"),
            ("metrics_payment", "payment"),
            ("metrics_experience", "experience"),
        ]
        if metric_types:
            requested = set(metric_types)
            categories = [(tbl, lbl) for tbl, lbl in all_categories if lbl in requested]
        else:
            categories = all_categories

        results: List[Dict[str, Any]] = []
        for table, label in categories:
            rows = (
                self._get_conn()
                .execute(
                    f"SELECT * FROM {table} "  # nosec B608 — table name from internal categories list, values parameterized
                    "WHERE created_at >= ? AND created_at <= ? "
                    "ORDER BY created_at ASC",
                    (start_date, end_date),
                )
                .fetchall()
            )
            for row in rows:
                results.append(self._sanitize_for_export(dict(row), label))
        return results

    def get_summary(
        self,
        metric_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return aggregate stats for a metric type over an optional range.

        Args:
            metric_type: one of activation / upgrade / flywheel / payment /
                nps / dialogue_naturalness / result_satisfaction /
                proactive_service.
            start_date: optional ISO8601 lower bound on created_at/timestamp.
            end_date: optional ISO8601 upper bound.

        Returns:
            Dict of aggregate fields (e.g. total, rate_pct, avg_score).
            Empty stats dict if metric_type is unrecognized.
        """
        if metric_type == "activation":
            return self._summary_activation(start_date, end_date)
        if metric_type == "upgrade":
            return self._summary_upgrade(start_date, end_date)
        if metric_type == "flywheel":
            return self._summary_flywheel(start_date, end_date)
        if metric_type == "payment":
            return self._summary_payment(start_date, end_date)
        if metric_type == "nps":
            return self._summary_nps(start_date, end_date)
        if metric_type in _EXPERIENCE_METRIC_TYPES:
            return self._summary_experience(metric_type, start_date, end_date)
        return {}

    # ------------------------------------------------------------------
    # Public API: v0.5.0 P3 feedback + unified summary + export log
    # ------------------------------------------------------------------
    def record_feedback(
        self,
        user_id: str,
        rating: int,
        comment: str = "",
        category: str = "praise",
        skill_id: Optional[str] = None,
        session_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a user feedback entry (rating 1-5 + comment + category).

        Args:
            user_id: non-empty user identifier.
            rating: integer 1-5 (star rating).
            comment: optional feedback text (already sanitized at API layer).
            category: one of bug/suggestion/praise/question.
            skill_id: optional related skill id.
            session_id: optional related session id.
            timestamp: ISO8601 user-reported feedback time; defaults to now.
            metadata: optional JSON-serializable dict (capped at 4KB).

        Returns:
            record_id (UUID v4 hex).

        Raises:
            MetricsValidationError: if user_id empty, rating out of range,
                or category not in allowed set.
            MetricsDBError: if SQLite write fails.
        """
        if not user_id or not user_id.strip():
            raise MetricsValidationError("user_id is required")
        if not isinstance(rating, int) or isinstance(rating, bool):
            raise MetricsValidationError(f"rating must be int 1-5, got {rating!r}")
        if not 1 <= rating <= 5:
            raise MetricsValidationError(f"rating must be 1-5, got {rating}")
        if category not in _FEEDBACK_CATEGORIES:
            raise MetricsValidationError(
                f"category must be one of {sorted(_FEEDBACK_CATEGORIES)}, "
                f"got {category!r}"
            )
        record_id = uuid.uuid4().hex
        now = self._now_iso()
        self._write(
            "metrics_feedback",
            {
                "id": record_id,
                "user_id": user_id,
                "rating": rating,
                "comment": comment or "",
                "category": category,
                "skill_id": skill_id,
                "session_id": session_id,
                "timestamp": timestamp or now,
                "metadata": self._serialize_metadata(metadata),
                "created_at": now,
            },
        )
        return record_id

    def get_feedback_list(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query feedback entries with optional filters.

        Args:
            user_id: filter by user (None = all users).
            start_date: ISO8601 lower bound on created_at (inclusive).
            end_date: ISO8601 upper bound on created_at (inclusive).
            category: filter by category (bug/suggestion/praise/question).
            limit: max rows to return (1-1000).
            offset: pagination offset (>=0).

        Returns:
            List of dicts with keys: record_id, user_id, rating, comment,
            category, skill_id, session_id, timestamp, metadata, created_at.
            Ordered by created_at DESC.
        """
        if not isinstance(limit, int) or limit < 1:
            raise MetricsValidationError(f"limit must be >= 1, got {limit}")
        if limit > 1000:
            raise MetricsValidationError(f"limit must be <= 1000, got {limit}")
        if not isinstance(offset, int) or offset < 0:
            raise MetricsValidationError(f"offset must be >= 0, got {offset}")
        conditions: List[str] = []
        params: List[Any] = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if start_date:
            conditions.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= ?")
            params.append(end_date)
        if category:
            conditions.append("category = ?")
            params.append(category)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            f"SELECT * FROM metrics_feedback {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        with self._lock:
            rows = self._get_conn().execute(sql, tuple(params)).fetchall()
        # Convert Row → dict and alias 'id' → 'record_id' for API layer.
        result: List[Dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            d["record_id"] = d.pop("id", "")
            result.append(d)
        return result

    def get_metrics_summary(
        self,
        metric_type: str,
        start_date: str,
        end_date: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return unified summary with total_count/avg/p50/p90/time_range.

        Unlike ``get_summary`` (which returns metric-specific shapes), this
        method always returns the same 6-key dict so the API layer can map
        it directly to the ``MetricsSummary`` Pydantic model.

        Args:
            metric_type: one of nps / dialogue_naturalness /
                result_satisfaction / proactive_service / experience /
                activation / upgrade / flywheel / payment.
            start_date: ISO8601 lower bound on created_at (inclusive).
            end_date: ISO8601 upper bound on created_at (inclusive).
            user_id: optional filter by user.

        Returns:
            Dict with keys: metric_type, total_count, avg_score, p50_score,
            p90_score, time_range.

        Raises:
            MetricsValidationError: if metric_type is unrecognized.
        """
        if not start_date or not end_date:
            raise MetricsValidationError(
                "start_date and end_date are required (ISO8601)"
            )
        # Build WHERE clause + params based on metric_type
        conditions: List[str] = ["created_at >= ?", "created_at <= ?"]
        params: List[Any] = [start_date, end_date]
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if metric_type in ("nps",) or metric_type in _EXPERIENCE_METRIC_TYPES:
            table = "metrics_experience"
            conditions.append("metric_type = ?")
            params.append(metric_type)
            score_col = "score"
        elif metric_type == "experience":
            # Aggregate all 3 experience sub-types (exclude NPS)
            table = "metrics_experience"
            placeholders = ",".join(["?"] * len(_EXPERIENCE_METRIC_TYPES))
            conditions.append(f"metric_type IN ({placeholders})")
            params.extend(sorted(_EXPERIENCE_METRIC_TYPES))
            score_col = "score"
        elif metric_type in ("activation", "upgrade", "flywheel", "payment"):
            table = _TABLE_FOR_METRIC[metric_type]
            score_col = None  # no score column for these tables
        else:
            raise MetricsValidationError(f"unknown metric_type: {metric_type!r}")
        where = " AND ".join(conditions)
        with self._lock:
            if score_col:
                rows = (
                    self._get_conn()
                    .execute(
                        f"SELECT {score_col} AS score FROM {table} "  # nosec B608 — column/table names from internal config, values parameterized
                        f"WHERE {where} ORDER BY {score_col}",
                        tuple(params),
                    )
                    .fetchall()
                )
                scores: List[float] = [
                    float(r["score"]) for r in rows if r["score"] is not None
                ]
                total = len(scores)
                avg = sum(scores) / total if total else 0.0
                p50 = self._percentile(scores, 50)
                p90 = self._percentile(scores, 90)
            else:
                row = (
                    self._get_conn()
                    .execute(
                        f"SELECT COUNT(*) AS cnt FROM {table} WHERE {where}",  # nosec B608 — table/where from internal config, values parameterized
                        tuple(params),
                    )
                    .fetchone()
                )
                total = int(row["cnt"]) if row else 0
                avg = 0.0
                p50 = 0.0
                p90 = 0.0
        return {
            "metric_type": metric_type,
            "total_count": total,
            "avg_score": round(avg, 2),
            "p50_score": round(p50, 2),
            "p90_score": round(p90, 2),
            "time_range": f"{start_date}~{end_date}",
        }

    def get_last_export_at(self) -> Optional[str]:
        """Return ISO8601 timestamp of the most recent export, or None."""
        with self._lock:
            row = (
                self._get_conn()
                .execute(
                    "SELECT exported_at FROM metrics_export_log "
                    "ORDER BY exported_at DESC LIMIT 1"
                )
                .fetchone()
            )
        return row["exported_at"] if row else None

    def set_last_export_at(
        self,
        timestamp: Optional[str] = None,
        exported_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record an export event. Returns the record id.

        Args:
            timestamp: ISO8601 timestamp; defaults to current UTC time.
            exported_count: number of records exported.
            metadata: optional JSON-serializable dict.
        """
        ts = timestamp or self._now_iso()
        record_id = uuid.uuid4().hex
        self._write(
            "metrics_export_log",
            {
                "id": record_id,
                "exported_at": ts,
                "exported_count": exported_count,
                "metadata": self._serialize_metadata(metadata),
            },
        )
        return record_id

    @staticmethod
    def _percentile(scores: List[float], p: float) -> float:
        """Compute percentile using linear interpolation (numpy-style).

        Args:
            scores: list of numeric scores (will be sorted in-place).
            p: percentile 0-100.

        Returns:
            Percentile value, or 0.0 if scores is empty.
        """
        if not scores:
            return 0.0
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        if n == 1:
            return float(sorted_scores[0])
        k = (p / 100.0) * (n - 1)
        f = int(k)
        c = min(f + 1, n - 1)
        return float(sorted_scores[f] + (sorted_scores[c] - sorted_scores[f]) * (k - f))

    def close(self) -> None:
        """Close the SQLite connection. Safe to call multiple times."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error as e:
                    logger.warning("[MetricsCollector] close failed: %s", e)
                self._conn = None

    # ------------------------------------------------------------------
    # Private: connection + schema
    # ------------------------------------------------------------------
    def _connect_db(self) -> None:
        """Open SQLite connection with WAL mode + 0600 file permissions.

        Mirrors ``data_manager._get_conn``: WAL for non-blocking reads,
        ``synchronous=NORMAL`` for throughput, ``busy_timeout=5000`` to
        tolerate writer contention, ``check_same_thread=False`` so the
        singleton can be called from any thread (writes still serialize
        on ``self._lock``).
        """
        db_path = os.path.expanduser(self._db_path)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(
            db_path,
            timeout=5.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        self._conn = conn
        # Enforce 0600 on the DB file (HARD_CONSTRAINTS S4: data stays local).
        try:
            os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError as e:
            logger.debug("[MetricsCollector] chmod DB failed: %s", e)

    def _get_conn(self) -> sqlite3.Connection:
        """Return the SQLite connection, raising if not initialized.

        Use this instead of accessing ``self._conn`` directly so mypy
        can infer a non-Optional type.
        """
        if self._conn is None:
            raise RuntimeError("MetricsCollector connection not initialized")
        return self._conn

    def _ensure_tables(self) -> None:
        """Idempotently create metrics schema (tables/indexes/triggers/views).

        Uses the same DDL constants as ``migrate_v8`` so a standalone
        ``metrics.db`` (without ``data_manager``) has identical structure.
        Does NOT touch ``_meta`` or ``schema_version`` — those are owned
        by the migration chain.

        v0.5.0 P3: also applies ``_FEEDBACK_DDL`` and ``_EXPORT_LOG_DDL``
        for the new feedback + export-log tables (not part of v8 migration).
        """
        from opc_manager.migrations.v8_metrics import ALL_DDL

        with self._lock:
            for stmt in ALL_DDL:
                self._get_conn().execute(stmt)
            for stmt in _FEEDBACK_DDL:
                self._get_conn().execute(stmt)
            for stmt in _EXPORT_LOG_DDL:
                self._get_conn().execute(stmt)
            self._get_conn().commit()

    # ------------------------------------------------------------------
    # Private: write path
    # ------------------------------------------------------------------
    def _write(self, table: str, row: Dict[str, Any]) -> None:
        """Thread-safe single-row INSERT.

        Uses parameterized placeholders (?), never f-string interpolation,
        to prevent SQL injection.
        """
        if self._conn is None:
            raise MetricsDBError("database connection is closed")
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        with self._lock:
            try:
                self._conn.execute(sql, tuple(row.values()))
                self._conn.commit()
            except sqlite3.Error as e:
                logger.error("[MetricsCollector] write to %s failed: %s", table, e)
                raise MetricsDBError(f"write to {table} failed: {e}") from e

    # ------------------------------------------------------------------
    # Private: helpers
    # ------------------------------------------------------------------
    def _serialize_metadata(self, metadata: Optional[Dict[str, Any]]) -> str:
        """JSON-encode metadata, truncating to 4KB (ADR-004 §6 risk table)."""
        if not metadata:
            return "{}"
        try:
            text = json.dumps(metadata, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            logger.warning("[MetricsCollector] metadata serialization failed: %s", e)
            return "{}"
        encoded = text.encode("utf-8")
        if len(encoded) > _METADATA_MAX_BYTES:
            logger.warning(
                "[MetricsCollector] metadata truncated (>4KB): %d bytes",
                len(encoded),
            )
            # Truncate by bytes, then cut back to last valid UTF-8 boundary.
            text = encoded[:_METADATA_MAX_BYTES].decode("utf-8", errors="ignore")
        return text

    def _sanitize_for_export(
        self, row: Dict[str, Any], category: str
    ) -> Dict[str, Any]:
        """Strip PII from a row for anonymized export.

        - Removes ``user_id``.
        - Adds ``anonymized_user_hash`` = SHA256(user_id + salt)[:16].
        - Scrubs PII keys from ``metadata`` JSON (business_name / ip /
          email / phone).
        - Adds ``metric_category`` to identify source table.
        """
        user_id = row.pop("user_id", "") or ""
        row.pop("license_key", None)  # already hashed at write time, but be safe
        row["anonymized_user_hash"] = self._hash_user_id(user_id)
        row["metric_category"] = category
        # Scrub PII from metadata JSON.
        meta_raw = row.get("metadata")
        if meta_raw and isinstance(meta_raw, str):
            try:
                meta = json.loads(meta_raw)
            except (json.JSONDecodeError, TypeError):
                meta = {}
            for key in ("business_name", "ip", "email", "phone"):
                meta.pop(key, None)
            row["metadata"] = meta
        return row

    def _hash_user_id(self, user_id: str) -> str:
        """anonymized_user_hash = SHA256(user_id + salt)[:16]."""
        digest = hashlib.sha256(f"{user_id}{self._salt}".encode("utf-8")).hexdigest()
        return digest[:16]

    @staticmethod
    def _now_iso() -> str:
        """UTC ISO8601 timestamp with timezone suffix."""
        return datetime.now(timezone.utc).isoformat()

    def _resolve_db_path(self, db_path: Optional[str]) -> str:
        """Resolve DB path: arg > env var METRICS_DB_PATH > default."""
        if db_path:
            return db_path
        env_path = os.environ.get("METRICS_DB_PATH")
        if env_path:
            return env_path
        return _DEFAULT_DB_PATH

    def _resolve_anonymization_salt(self) -> str:
        """Resolve salt: env var > salt file > generate + persist.

        Salt file is created with 0600 permissions to match DB file
        protection level. Generated via ``secrets.token_hex(16)`` (32
        hex chars, 128 bits of entropy).
        """
        env_salt = os.environ.get("METRICS_ANONYMIZATION_SALT")
        if env_salt:
            return env_salt
        salt_path = os.path.expanduser(_DEFAULT_SALT_PATH)
        if os.path.exists(salt_path):
            try:
                with open(salt_path, "r", encoding="utf-8") as fh:
                    salt = fh.read().strip()
                if salt:
                    return salt
            except OSError as e:
                logger.warning("[MetricsCollector] salt read failed: %s", e)
        # Generate + persist.
        salt_dir = os.path.dirname(salt_path)
        if salt_dir:
            os.makedirs(salt_dir, exist_ok=True)
        new_salt = secrets.token_hex(16)
        try:
            with open(salt_path, "w", encoding="utf-8") as fh:
                fh.write(new_salt)
            os.chmod(salt_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError as e:
            logger.warning(
                "[MetricsCollector] salt persist failed (using ephemeral): %s",
                e,
            )
        return new_salt

    # ------------------------------------------------------------------
    # Private: summary queries
    # ------------------------------------------------------------------
    def _date_clause(
        self,
        column: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> tuple:
        """Build a WHERE clause fragment for date filtering.

        Returns (clause_string, params_tuple). Empty string if no filter.
        """
        conditions: List[str] = []
        params: List[Any] = []
        if start_date:
            conditions.append(f"{column} >= ?")
            params.append(start_date)
        if end_date:
            conditions.append(f"{column} <= ?")
            params.append(end_date)
        if not conditions:
            return "", ()
        return " AND ".join(conditions), tuple(params)

    def _summary_activation(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> Dict[str, Any]:
        clause, params = self._date_clause("created_at", start_date, end_date)
        where = f"WHERE {clause}" if clause else ""
        row = (
            self._get_conn()
            .execute(
                f"SELECT COUNT(DISTINCT user_id) AS total_onboarded, "  # nosec B608 — static SQL with parameterized values
                f"COUNT(DISTINCT CASE WHEN activation_criteria_met = 1 "
                f"THEN user_id END) AS activated_users "
                f"FROM metrics_activation {where}",
                params,
            )
            .fetchone()
        )
        total = row["total_onboarded"] if row else 0
        activated = row["activated_users"] if row else 0
        rate = round(activated / total * 100, 2) if total else 0.0
        return {
            "total_onboarded": total,
            "activated_users": activated,
            "activation_rate_pct": rate,
        }

    def _summary_upgrade(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> Dict[str, Any]:
        clause, params = self._date_clause("created_at", start_date, end_date)
        where = f"WHERE {clause}" if clause else ""
        row = (
            self._get_conn()
            .execute(
                f"SELECT COUNT(DISTINCT user_id) AS upgraded_users, "  # nosec B608 — static SQL with parameterized values
                f"COUNT(DISTINCT CASE WHEN from_version='basic' "
                f"THEN user_id END) AS from_basic_count "
                f"FROM metrics_upgrade {where}",
                params,
            )
            .fetchone()
        )
        return {
            "upgraded_users": row["upgraded_users"] if row else 0,
            "from_basic_count": row["from_basic_count"] if row else 0,
        }

    def _summary_flywheel(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> Dict[str, Any]:
        clause, params = self._date_clause("created_at", start_date, end_date)
        where = f"WHERE {clause}" if clause else ""
        rows = (
            self._get_conn()
            .execute(
                f"SELECT user_id, MAX(flywheel_level) AS max_level "  # nosec B608 — static SQL with parameterized values
                f"FROM metrics_flywheel {where} "
                f"GROUP BY user_id",
                params,
            )
            .fetchall()
        )
        total = len(rows)
        flywheel_users = sum(1 for r in rows if r["max_level"] >= 2)
        rate = round(flywheel_users / total * 100, 2) if total else 0.0
        return {
            "total_users": total,
            "flywheel_users": flywheel_users,
            "flywheel_rate_pct": rate,
        }

    def _summary_payment(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> Dict[str, Any]:
        clause, params = self._date_clause("created_at", start_date, end_date)
        where = f"WHERE {clause}" if clause else ""
        row = (
            self._get_conn()
            .execute(
                f"SELECT COUNT(DISTINCT CASE WHEN payment_status='paid' "  # nosec B608 — static SQL with parameterized values
                f"THEN user_id END) AS paid_users, "
                f"COUNT(DISTINCT CASE WHEN payment_status='trial' "
                f"THEN user_id END) AS trial_count, "
                f"COALESCE(SUM(CASE WHEN payment_status='paid' "
                f"THEN amount ELSE 0 END), 0) AS total_paid_amount "
                f"FROM metrics_payment {where}",
                params,
            )
            .fetchone()
        )
        return {
            "paid_users": row["paid_users"] if row else 0,
            "trial_count": row["trial_count"] if row else 0,
            "total_paid_amount": round(row["total_paid_amount"], 2) if row else 0.0,
        }

    def _summary_nps(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> Dict[str, Any]:
        clause, params = self._date_clause("created_at", start_date, end_date)
        where = "WHERE metric_type='nps'" + (f" AND {clause}" if clause else "")
        row = (
            self._get_conn()
            .execute(
                f"SELECT COUNT(*) AS total, "  # nosec B608 — static SQL with parameterized values
                f"SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) AS promoters, "
                f"SUM(CASE WHEN score BETWEEN 7 AND 8 THEN 1 ELSE 0 END) AS passives, "
                f"SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END) AS detractors "
                f"FROM metrics_experience {where}",
                params,
            )
            .fetchone()
        )
        total = row["total"] if row and row["total"] else 0
        promoters = row["promoters"] if row else 0
        passives = row["passives"] if row else 0
        detractors = row["detractors"] if row else 0
        if total > 0:
            nps = round((promoters - detractors) / total * 100, 2)
        else:
            nps = 0.0
        return {
            "total_responses": total,
            "promoters": promoters,
            "passives": passives,
            "detractors": detractors,
            "nps_score": nps,
        }

    def _summary_experience(
        self,
        metric_type: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Dict[str, Any]:
        clause, params = self._date_clause("created_at", start_date, end_date)
        where = "WHERE metric_type=?" + (f" AND {clause}" if clause else "")
        all_params = (metric_type,) + params
        row = (
            self._get_conn()
            .execute(
                f"SELECT COUNT(*) AS cnt, "  # nosec B608 — static SQL with parameterized values
                f"COALESCE(ROUND(AVG(score), 2), 0) AS avg_score, "
                f"COALESCE(ROUND(MIN(score), 2), 0) AS min_score, "
                f"COALESCE(ROUND(MAX(score), 2), 0) AS max_score "
                f"FROM metrics_experience {where}",
                all_params,
            )
            .fetchone()
        )
        return {
            "metric_type": metric_type,
            "response_count": row["cnt"] if row else 0,
            "avg_score": row["avg_score"] if row else 0.0,
            "min_score": row["min_score"] if row else 0.0,
            "max_score": row["max_score"] if row else 0.0,
        }


def get_metrics_collector(db_path: Optional[str] = None) -> MetricsCollector:
    """Factory returning the singleton MetricsCollector.

    Mirrors the ``get_settings()`` / ``get_onboarding()`` style. The
    ``db_path`` argument is honored only on first initialization;
    subsequent calls return the existing singleton regardless of args.
    """
    return MetricsCollector(db_path=db_path)


__all__ = [
    "MetricsCollectionError",
    "MetricsDBError",
    "MetricsValidationError",
    "MetricsCollector",
    "get_metrics_collector",
]
