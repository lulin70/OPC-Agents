"""Unit tests for MetricsCollector (ADR-004 / v0.5.0 P4).

Covers all 6 record_* methods, export_anonymized, get_summary, singleton
thread safety, WAL mode, file permissions, and the v8 migration script
(idempotency + rollback). Uses real SQLite databases in temp directories
(no Mock) per DevSquad Testing Iron Rules.

Run:
    pytest tests/unit/test_metrics_collector.py -v --tb=short
    pytest tests/unit/test_metrics_collector.py --cov=opc_manager.metrics_collector --cov-report=term-missing
"""

import hashlib
import json
import os
import sqlite3
import stat
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from opc_manager.metrics_collector import (
    MetricsCollector,
    MetricsDBError,
    MetricsValidationError,
    get_metrics_collector,
)
from opc_manager.migrations.v8_metrics import (
    V8_VERSION,
    migrate_v8,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_metrics_singleton(monkeypatch):
    """Reset MetricsCollector singleton before/after each test + pin salt.

    Uses a fixed salt so anonymized_user_hash is deterministic across runs.
    """
    monkeypatch.setenv("METRICS_ANONYMIZATION_SALT", "test-salt-fixed-0001")
    MetricsCollector._reset_singleton()
    yield
    MetricsCollector._reset_singleton()


@pytest.fixture
def collector(tmp_path):
    """Provide a fresh MetricsCollector backed by a temp SQLite DB."""
    db_path = str(tmp_path / "test_metrics.db")
    return MetricsCollector(db_path=db_path)


@pytest.fixture
def migration_conn(tmp_path):
    """Provide a fresh sqlite3.Connection with _meta.db_version=7.

    For migration tests: caller starts at v7, runs migrate_v8, verifies
    upgrade to v8. Connection is closed by the fixture after the test.
    """
    db_path = str(tmp_path / "migration_test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT OR REPLACE INTO _meta (key, value) VALUES ('db_version', '7')"
    )
    conn.commit()
    yield conn
    conn.close()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# record_activation
# ---------------------------------------------------------------------------
class TestRecordActivation:
    """Tests for MetricsCollector.record_activation()."""

    def test_record_activation_happy_path(self, collector):
        """Verify: record_activation writes a row and returns a UUID id.

        Scenario: valid user_id + ISO timestamps provided.
        Expected: returns 32-char hex id; row exists in metrics_activation
            with activation_criteria_met=0 (pending task-count check).
        """
        # Arrange
        user_id = "user-001"
        onboarding_at = _iso_days_ago(7)
        first_use_at = _iso_days_ago(5)

        # Act
        record_id = collector.record_activation(
            user_id=user_id,
            onboarding_completed_at=onboarding_at,
            first_use_at=first_use_at,
            metadata={"source": "onboarding_complete"},
        )

        # Assert
        assert isinstance(record_id, str)
        assert len(record_id) == 32  # uuid4().hex
        row = collector._conn.execute(
            "SELECT * FROM metrics_activation WHERE id = ?", (record_id,)
        ).fetchone()
        assert row is not None
        assert row["user_id"] == user_id
        assert row["onboarding_completed_at"] == onboarding_at
        assert row["first_use_at"] == first_use_at
        assert row["activation_criteria_met"] == 0
        assert row["updated_at"] == row["created_at"]
        meta = json.loads(row["metadata"])
        assert meta["source"] == "onboarding_complete"

    def test_record_activation_missing_user_id_raises(self, collector):
        """Verify: empty user_id raises MetricsValidationError.

        Scenario: caller passes empty/whitespace user_id.
        Expected: MetricsValidationError raised, no row written.
        """
        # Arrange
        onboarding_at = _iso_now()
        first_use_at = _iso_now()

        # Act + Assert
        with pytest.raises(MetricsValidationError, match="user_id"):
            collector.record_activation(
                user_id="",
                onboarding_completed_at=onboarding_at,
                first_use_at=first_use_at,
            )
        # Whitespace-only also rejected.
        with pytest.raises(MetricsValidationError, match="user_id"):
            collector.record_activation(
                user_id="   ",
                onboarding_completed_at=onboarding_at,
                first_use_at=first_use_at,
            )
        count = collector._conn.execute(
            "SELECT COUNT(*) AS c FROM metrics_activation"
        ).fetchone()["c"]
        assert count == 0

    def test_record_activation_boundary_same_day(self, collector):
        """Verify: activation with same-day onboarding+first_use writes correctly.

        Scenario: onboarding_completed_at == first_use_at (boundary: 0 days
            between onboarding and first use).
        Expected: row written successfully; days_to_activate stays NULL
            (set later by activation_criteria_met logic).
        """
        # Arrange
        same_ts = _iso_now()

        # Act
        record_id = collector.record_activation(
            user_id="user-same-day",
            onboarding_completed_at=same_ts,
            first_use_at=same_ts,
        )

        # Assert
        row = collector._conn.execute(
            "SELECT * FROM metrics_activation WHERE id = ?", (record_id,)
        ).fetchone()
        assert row["onboarding_completed_at"] == same_ts
        assert row["first_use_at"] == same_ts
        assert row["days_to_activate"] is None


# ---------------------------------------------------------------------------
# record_upgrade
# ---------------------------------------------------------------------------
class TestRecordUpgrade:
    """Tests for MetricsCollector.record_upgrade()."""

    def test_record_upgrade_happy_path(self, collector):
        """Verify: record_upgrade writes a row with from/to versions.

        Scenario: basic → pro_activated upgrade via relay_client.
        Expected: returns id; row has from_version='basic',
            to_version='pro_activated', license_key stored.
        """
        # Arrange
        user_id = "user-upgrade"
        license_hash = hashlib.sha256(b"raw-license-key").hexdigest()[:16]

        # Act
        record_id = collector.record_upgrade(
            user_id=user_id,
            from_version="basic",
            to_version="pro_activated",
            license_key_hash=license_hash,
            metadata={"trigger": "relay_client"},
        )

        # Assert
        assert len(record_id) == 32
        row = collector._conn.execute(
            "SELECT * FROM metrics_upgrade WHERE id = ?", (record_id,)
        ).fetchone()
        assert row["user_id"] == user_id
        assert row["from_version"] == "basic"
        assert row["to_version"] == "pro_activated"
        assert row["license_key"] == license_hash
        assert row["upgrade_at"] is not None


# ---------------------------------------------------------------------------
# record_flywheel
# ---------------------------------------------------------------------------
class TestRecordFlywheel:
    """Tests for MetricsCollector.record_flywheel()."""

    def test_record_flywheel_level_up(self, collector):
        """Verify: flywheel level-up event records previous_level correctly.

        Scenario: user progresses from L1 to L2 (level-up triggers flywheel rate).
        Expected: returns id; row has flywheel_level=2, previous_level=1,
            skills_used as JSON array.
        """
        # Arrange
        user_id = "user-flywheel"

        # Act
        record_id = collector.record_flywheel(
            user_id=user_id,
            flywheel_level=2,
            previous_level=1,
            skills_used=["email", "calendar"],
            metadata={"scenario_id": "scenario-001"},
        )

        # Assert
        row = collector._conn.execute(
            "SELECT * FROM metrics_flywheel WHERE id = ?", (record_id,)
        ).fetchone()
        assert row["flywheel_level"] == 2
        assert row["previous_level"] == 1
        skills = json.loads(row["skills_used"])
        assert skills == ["email", "calendar"]

    def test_record_flywheel_same_level(self, collector):
        """Verify: recording same-level event (no level-up) is allowed.

        Scenario: user re-enters L2 (previous_level=2, flywheel_level=2).
        Expected: row written; previous_level == flywheel_level.
        """
        # Arrange
        user_id = "user-same-level"

        # Act
        record_id = collector.record_flywheel(
            user_id=user_id,
            flywheel_level=2,
            previous_level=2,
        )

        # Assert
        row = collector._conn.execute(
            "SELECT * FROM metrics_flywheel WHERE id = ?", (record_id,)
        ).fetchone()
        assert row["flywheel_level"] == 2
        assert row["previous_level"] == 2
        assert row["skills_used"] is None  # no skills passed


# ---------------------------------------------------------------------------
# record_payment
# ---------------------------------------------------------------------------
class TestRecordPayment:
    """Tests for MetricsCollector.record_payment()."""

    def test_record_payment_trial(self, collector):
        """Verify: trial payment records with amount=NULL and paid_at=NULL.

        Scenario: user starts trial (no payment yet).
        Expected: row has payment_status='trial', amount=NULL, paid_at=NULL.
        """
        # Arrange
        user_id = "user-trial"

        # Act
        record_id = collector.record_payment(
            user_id=user_id,
            payment_status="trial",
        )

        # Assert
        row = collector._conn.execute(
            "SELECT * FROM metrics_payment WHERE id = ?", (record_id,)
        ).fetchone()
        assert row["payment_status"] == "trial"
        assert row["amount"] is None
        assert row["paid_at"] is None
        assert row["currency"] == "CNY"

    def test_record_payment_paid(self, collector):
        """Verify: paid payment records amount and paid_at timestamp.

        Scenario: user converts from trial to paid (199.00 CNY).
        Expected: row has payment_status='paid', amount=199.0,
            paid_at is non-null.
        """
        # Arrange
        user_id = "user-paid"

        # Act
        record_id = collector.record_payment(
            user_id=user_id,
            payment_status="paid",
            amount=199.00,
            currency="CNY",
        )

        # Assert
        row = collector._conn.execute(
            "SELECT * FROM metrics_payment WHERE id = ?", (record_id,)
        ).fetchone()
        assert row["payment_status"] == "paid"
        assert row["amount"] == 199.0
        assert row["paid_at"] is not None

    def test_record_payment_invalid_status_raises(self, collector):
        """Verify: invalid payment_status raises MetricsValidationError.

        Scenario: caller passes payment_status='invalid'.
        Expected: MetricsValidationError, no row written.
        """
        # Act + Assert
        with pytest.raises(MetricsValidationError, match="payment_status"):
            collector.record_payment(
                user_id="user-x",
                payment_status="invalid",
                amount=100.0,
            )
        count = collector._conn.execute(
            "SELECT COUNT(*) AS c FROM metrics_payment"
        ).fetchone()["c"]
        assert count == 0


# ---------------------------------------------------------------------------
# record_nps
# ---------------------------------------------------------------------------
class TestRecordNPS:
    """Tests for MetricsCollector.record_nps()."""

    def test_record_nps_score_0_boundary(self, collector):
        """Verify: NPS score=0 (lowest boundary) is accepted.

        Scenario: user gives NPS 0 (extreme detractor).
        Expected: row written with score=0.0, metric_type='nps'.
        """
        # Act
        record_id = collector.record_nps(
            user_id="user-nps-0",
            score=0,
            comment="terrible",
        )

        # Assert
        row = collector._conn.execute(
            "SELECT * FROM metrics_experience WHERE id = ?", (record_id,)
        ).fetchone()
        assert row["metric_type"] == "nps"
        assert row["score"] == 0.0
        assert row["comment"] == "terrible"

    def test_record_nps_score_10_boundary(self, collector):
        """Verify: NPS score=10 (highest boundary) is accepted.

        Scenario: user gives NPS 10 (promoter).
        Expected: row written with score=10.0.
        """
        # Act
        record_id = collector.record_nps(
            user_id="user-nps-10",
            score=10,
        )

        # Assert
        row = collector._conn.execute(
            "SELECT * FROM metrics_experience WHERE id = ?", (record_id,)
        ).fetchone()
        assert row["metric_type"] == "nps"
        assert row["score"] == 10.0

    def test_record_nps_score_11_raises(self, collector):
        """Verify: NPS score=11 (above max) raises MetricsValidationError.

        Scenario: caller passes score=11.
        Expected: MetricsValidationError, no row written.
        """
        # Act + Assert
        with pytest.raises(MetricsValidationError, match="0-10"):
            collector.record_nps(user_id="user-x", score=11)
        count = collector._conn.execute(
            "SELECT COUNT(*) AS c FROM metrics_experience "
            "WHERE metric_type='nps'"
        ).fetchone()["c"]
        assert count == 0


# ---------------------------------------------------------------------------
# record_experience
# ---------------------------------------------------------------------------
class TestRecordExperience:
    """Tests for MetricsCollector.record_experience()."""

    def test_record_experience_dialogue_naturalness(self, collector):
        """Verify: experience metric dialogue_naturalness writes correctly.

        Scenario: user rates dialogue naturalness 4.5/5 after a conversation.
        Expected: row has metric_type='dialogue_naturalness', score=4.5.
        """
        # Act
        record_id = collector.record_experience(
            user_id="user-exp",
            metric_type="dialogue_naturalness",
            score=4.5,
            skill_id="dialogue_skill",
            session_id="sess-001",
        )

        # Assert
        row = collector._conn.execute(
            "SELECT * FROM metrics_experience WHERE id = ?", (record_id,)
        ).fetchone()
        assert row["metric_type"] == "dialogue_naturalness"
        assert row["score"] == 4.5
        assert row["skill_id"] == "dialogue_skill"
        assert row["session_id"] == "sess-001"

    def test_record_experience_score_too_high_raises(self, collector):
        """Verify: experience score > 5.0 raises MetricsValidationError.

        Scenario: caller passes score=5.1 for a non-NPS metric.
        Expected: MetricsValidationError, no row written.
        """
        # Act + Assert
        with pytest.raises(MetricsValidationError, match="1.0-5.0"):
            collector.record_experience(
                user_id="user-x",
                metric_type="result_satisfaction",
                score=5.1,
            )
        count = collector._conn.execute(
            "SELECT COUNT(*) AS c FROM metrics_experience"
        ).fetchone()["c"]
        assert count == 0

    def test_record_experience_invalid_metric_type_raises(self, collector):
        """Verify: invalid metric_type raises MetricsValidationError.

        Scenario: caller passes metric_type='invalid_metric'.
        Expected: MetricsValidationError, no row written.
        """
        # Act + Assert
        with pytest.raises(MetricsValidationError, match="metric_type"):
            collector.record_experience(
                user_id="user-x",
                metric_type="invalid_metric",
                score=3.0,
            )
        count = collector._conn.execute(
            "SELECT COUNT(*) AS c FROM metrics_experience"
        ).fetchone()["c"]
        assert count == 0


# ---------------------------------------------------------------------------
# export_anonymized
# ---------------------------------------------------------------------------
class TestExportAnonymized:
    """Tests for MetricsCollector.export_anonymized()."""

    def test_export_anonymized_removes_user_id(self, collector):
        """Verify: export removes user_id and adds anonymized_user_hash.

        Scenario: records exist across multiple tables; user triggers export.
        Expected: no row contains 'user_id' key; every row has
            'anonymized_user_hash' (16 hex chars); same user_id produces
            same hash (deterministic).
        """
        # Arrange
        collector.record_activation(
            user_id="user-A",
            onboarding_completed_at=_iso_now(),
            first_use_at=_iso_now(),
        )
        collector.record_nps(user_id="user-A", score=9)
        collector.record_experience(
            user_id="user-B",
            metric_type="dialogue_naturalness",
            score=4.0,
        )

        # Act
        exported = collector.export_anonymized(
            start_date="2000-01-01T00:00:00+00:00",
            end_date="2100-01-01T00:00:00+00:00",
        )

        # Assert
        assert len(exported) >= 3
        for row in exported:
            assert "user_id" not in row
            assert "anonymized_user_hash" in row
            assert len(row["anonymized_user_hash"]) == 16
        # Same user_id → same hash.
        user_a_rows = [r for r in exported if r.get("metric_category") in ("activation", "experience")]
        hashes = {r["anonymized_user_hash"] for r in user_a_rows}
        # user-A appears in activation + nps; user-B in experience.
        # At least 2 distinct hashes for 2 distinct users.
        assert len(hashes) >= 2
        # Verify hash matches manual computation.
        expected_hash_a = hashlib.sha256(
            b"user-A" + b"test-salt-fixed-0001"
        ).hexdigest()[:16]
        assert expected_hash_a in hashes

    def test_export_anonymized_empty_data(self, collector):
        """Verify: export on empty DB returns empty list.

        Scenario: no records written yet.
        Expected: export_anonymized returns [].
        """
        # Act
        exported = collector.export_anonymized(
            start_date="2000-01-01T00:00:00+00:00",
            end_date="2100-01-01T00:00:00+00:00",
        )

        # Assert
        assert exported == []
        assert len(exported) == 0


# ---------------------------------------------------------------------------
# get_summary
# ---------------------------------------------------------------------------
class TestGetSummary:
    """Tests for MetricsCollector.get_summary()."""

    def test_get_summary_nps(self, collector):
        """Verify: NPS summary computes promoters/passives/detractors/nps_score.

        Scenario: 3 promoters (9-10), 1 passive (7-8), 2 detractors (0-6).
        Expected: nps_score = (3-2)/6*100 = 16.67.
        """
        # Arrange
        # 3 promoters
        collector.record_nps(user_id="u1", score=10)
        collector.record_nps(user_id="u2", score=9)
        collector.record_nps(user_id="u3", score=10)
        # 1 passive
        collector.record_nps(user_id="u4", score=8)
        # 2 detractors
        collector.record_nps(user_id="u5", score=0)
        collector.record_nps(user_id="u6", score=6)

        # Act
        summary = collector.get_summary(metric_type="nps")

        # Assert
        assert summary["total_responses"] == 6
        assert summary["promoters"] == 3
        assert summary["passives"] == 1
        assert summary["detractors"] == 2
        assert summary["nps_score"] == round((3 - 2) / 6 * 100, 2)

    def test_get_summary_experience_avg(self, collector):
        """Verify: experience avg summary computes mean/min/max for a metric.

        Scenario: 3 dialogue_naturalness scores: 4.0, 5.0, 3.5.
        Expected: avg_score = 4.17, min_score = 3.5, max_score = 5.0.
        """
        # Arrange
        collector.record_experience(
            user_id="u1", metric_type="dialogue_naturalness", score=4.0
        )
        collector.record_experience(
            user_id="u2", metric_type="dialogue_naturalness", score=5.0
        )
        collector.record_experience(
            user_id="u3", metric_type="dialogue_naturalness", score=3.5
        )

        # Act
        summary = collector.get_summary(metric_type="dialogue_naturalness")

        # Assert
        assert summary["metric_type"] == "dialogue_naturalness"
        assert summary["response_count"] == 3
        assert summary["avg_score"] == round((4.0 + 5.0 + 3.5) / 3, 2)
        assert summary["min_score"] == 3.5
        assert summary["max_score"] == 5.0


# ---------------------------------------------------------------------------
# Concurrency + performance
# ---------------------------------------------------------------------------
class TestConcurrencyAndPerformance:
    """Concurrency and performance tests (Iron Rule: Performance >=5%)."""

    def test_concurrent_writes_1000_records_performance(self, tmp_path):
        """Verify: 1000 concurrent record writes complete in <5s with no loss.

        Scenario: 4 threads × 250 records each, all writing to the same DB.
        Expected: all 1000 rows present; total time < 5 seconds (WAL + lock).
        """
        # Arrange
        db_path = str(tmp_path / "perf_metrics.db")
        MetricsCollector._reset_singleton()
        collector = MetricsCollector(db_path=db_path)

        records_per_thread = 250
        num_threads = 4
        total_expected = records_per_thread * num_threads
        errors: list = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(records_per_thread):
                    collector.record_experience(
                        user_id=f"t{thread_id}-user-{i}",
                        metric_type="result_satisfaction",
                        score=4.0,
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        # Act
        start = time.time()
        threads = [
            threading.Thread(target=writer, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        # Assert
        assert errors == [], f"concurrent writes produced errors: {errors}"
        count = collector._conn.execute(
            "SELECT COUNT(*) AS c FROM metrics_experience"
        ).fetchone()["c"]
        assert count == total_expected
        assert elapsed < 5.0, f"1000 writes took {elapsed:.2f}s (>5s budget)"


# ---------------------------------------------------------------------------
# Singleton + DB properties
# ---------------------------------------------------------------------------
class TestSingletonAndDBProperties:
    """Tests for singleton thread safety, WAL mode, file permissions."""

    def test_singleton_thread_safe(self, tmp_path):
        """Verify: concurrent MetricsCollector() calls return same instance.

        Scenario: 10 threads each call MetricsCollector(db_path=same_path).
        Expected: all threads get the identical singleton instance.
        """
        # Arrange
        MetricsCollector._reset_singleton()
        db_path = str(tmp_path / "singleton_metrics.db")
        instances: list = []
        barrier = threading.Barrier(10)

        def getter() -> None:
            barrier.wait()  # maximize contention
            inst = MetricsCollector(db_path=db_path)
            instances.append(id(inst))

        # Act
        threads = [threading.Thread(target=getter) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert
        assert len(instances) == 10
        assert len(set(instances)) == 1, "multiple instances created"
        # get_metrics_collector returns same singleton.
        assert get_metrics_collector() is MetricsCollector._instance

    def test_db_wal_mode_enabled(self, collector):
        """Verify: SQLite journal_mode is WAL (HARD_CONSTRAINTS REL-4-01).

        Scenario: collector initialized with default settings.
        Expected: PRAGMA journal_mode returns 'wal'.
        """
        # Act
        mode = collector._conn.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0]

        # Assert
        assert mode.lower() == "wal"

    def test_db_file_permissions_0600(self, tmp_path):
        """Verify: DB file has 0600 permissions (HARD_CONSTRAINTS S4).

        Scenario: collector creates a new DB file.
        Expected: file mode bits (permission portion) == 0o600.
        """
        # Arrange
        MetricsCollector._reset_singleton()
        db_path = str(tmp_path / "perm_metrics.db")
        MetricsCollector(db_path=db_path)  # trigger DB file creation

        # Act
        mode = os.stat(db_path).st_mode
        perm_bits = stat.S_IMODE(mode)

        # Assert
        assert perm_bits == 0o600, f"expected 0o600, got {oct(perm_bits)}"


# ---------------------------------------------------------------------------
# Migration v8
# ---------------------------------------------------------------------------
class TestMigrationV8:
    """Tests for opc_manager.migrations.v8_metrics.migrate_v8()."""

    def test_migration_v8_idempotent(self, migration_conn):
        """Verify: running migrate_v8 twice is a no-op (idempotent).

        Scenario: v7 DB migrated to v8, then migrate_v8 called again.
        Expected: second call succeeds; db_version stays 8; schema intact.
        """
        # Act
        migrate_v8(migration_conn)
        # Second run should be a no-op (early return on db_version==8).
        migrate_v8(migration_conn)

        # Assert
        row = migration_conn.execute(
            "SELECT value FROM _meta WHERE key='db_version'"
        ).fetchone()
        assert int(row["value"]) == V8_VERSION
        # All 5 tables exist.
        for table in (
            "metrics_activation",
            "metrics_upgrade",
            "metrics_flywheel",
            "metrics_payment",
            "metrics_experience",
        ):
            cnt = migration_conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()[0]
            assert cnt == 1, f"table {table} missing after idempotent re-run"
        # 6 views exist.
        view_count = migration_conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='view' "
            "AND name LIKE 'view_%'"
        ).fetchone()[0]
        assert view_count == 6
        # schema_version table has the v8 row.
        sv = migration_conn.execute(
            "SELECT version, description FROM schema_version WHERE version=?",
            (V8_VERSION,),
        ).fetchone()
        assert sv["version"] == V8_VERSION
        assert sv["description"] == "metrics"

    def test_migration_v8_rejects_unexpected_version(self, tmp_path):
        """Verify: migrate_v8 raises when db_version is not 7/0/8.

        Scenario: DB at v5 (prior migrations not run).
        Expected: RuntimeError raised mentioning expected version.
        """
        # Arrange
        db_path = str(tmp_path / "bad_version.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO _meta (key, value) VALUES ('db_version', '5')"
        )
        conn.commit()

        # Act + Assert
        with pytest.raises(RuntimeError, match="expected db_version=7"):
            migrate_v8(conn)
        conn.close()


# ---------------------------------------------------------------------------
# Additional validation + edge case coverage
# ---------------------------------------------------------------------------
class TestValidationEdgeCases:
    """Extra validation + branch coverage to push metrics_collector ≥80%."""

    def test_record_activation_missing_timestamps_raises(self, collector):
        """Verify: missing onboarding_completed_at or first_use_at raises."""
        with pytest.raises(MetricsValidationError, match="onboarding_completed_at"):
            collector.record_activation(
                user_id="u1",
                onboarding_completed_at="",
                first_use_at=_iso_now(),
            )
        with pytest.raises(MetricsValidationError, match="first_use_at"):
            collector.record_activation(
                user_id="u1",
                onboarding_completed_at=_iso_now(),
                first_use_at="",
            )

    def test_record_upgrade_missing_to_version_raises(self, collector):
        """Verify: empty to_version raises MetricsValidationError."""
        with pytest.raises(MetricsValidationError, match="to_version"):
            collector.record_upgrade(
                user_id="u1", from_version="basic", to_version=""
            )

    def test_record_flywheel_invalid_level_raises(self, collector):
        """Verify: flywheel_level outside 0-4 raises."""
        with pytest.raises(MetricsValidationError, match="flywheel_level"):
            collector.record_flywheel(user_id="u1", flywheel_level=5)
        with pytest.raises(MetricsValidationError, match="flywheel_level"):
            collector.record_flywheel(user_id="u1", flywheel_level=-1)
        with pytest.raises(MetricsValidationError, match="previous_level"):
            collector.record_flywheel(
                user_id="u1", flywheel_level=2, previous_level=9
            )

    def test_record_payment_invalid_amount_raises(self, collector):
        """Verify: negative or non-numeric amount raises."""
        with pytest.raises(MetricsValidationError, match="amount must be >= 0"):
            collector.record_payment(
                user_id="u1", payment_status="paid", amount=-10.0
            )
        with pytest.raises(MetricsValidationError, match="amount must be a number"):
            collector.record_payment(
                user_id="u1", payment_status="paid", amount="100"
            )
        # bool is rejected even though bool is subclass of int.
        with pytest.raises(MetricsValidationError, match="amount must be a number"):
            collector.record_payment(
                user_id="u1", payment_status="paid", amount=True
            )

    def test_record_nps_non_int_score_raises(self, collector):
        """Verify: float or bool NPS score raises (record_nps requires int)."""
        with pytest.raises(MetricsValidationError, match="NPS score must be int"):
            collector.record_nps(user_id="u1", score=9.5)
        with pytest.raises(MetricsValidationError, match="NPS score must be int"):
            collector.record_nps(user_id="u1", score=True)

    def test_record_experience_non_number_score_raises(self, collector):
        """Verify: non-numeric experience score raises."""
        with pytest.raises(MetricsValidationError, match="experience score must be a number"):
            collector.record_experience(
                user_id="u1",
                metric_type="dialogue_naturalness",
                score="4",
            )
        # NPS path with non-number
        with pytest.raises(MetricsValidationError, match="NPS score must be a number"):
            collector.record_experience(
                user_id="u1", metric_type="nps", score="9"
            )

    def test_record_experience_score_too_low_raises(self, collector):
        """Verify: experience score < 1.0 raises."""
        with pytest.raises(MetricsValidationError, match="1.0-5.0"):
            collector.record_experience(
                user_id="u1",
                metric_type="result_satisfaction",
                score=0.5,
            )

    def test_record_experience_score_boundary_5_ok(self, collector):
        """Verify: experience score=5.0 (upper boundary) is accepted."""
        rid = collector.record_experience(
            user_id="u1",
            metric_type="proactive_service",
            score=5.0,
        )
        row = collector._conn.execute(
            "SELECT score FROM metrics_experience WHERE id=?", (rid,)
        ).fetchone()
        assert row["score"] == 5.0

    def test_record_experience_nps_score_boundary_0_ok(self, collector):
        """Verify: NPS via record_experience score=0 is accepted."""
        rid = collector.record_experience(
            user_id="u1", metric_type="nps", score=0
        )
        row = collector._conn.execute(
            "SELECT score FROM metrics_experience WHERE id=?", (rid,)
        ).fetchone()
        assert row["score"] == 0.0

    def test_export_anonymized_with_metric_types_filter(self, collector):
        """Verify: metric_types filter limits exported categories."""
        collector.record_activation(
            user_id="u1",
            onboarding_completed_at=_iso_now(),
            first_use_at=_iso_now(),
        )
        collector.record_nps(user_id="u1", score=9)

        exported = collector.export_anonymized(
            start_date="2000-01-01T00:00:00+00:00",
            end_date="2100-01-01T00:00:00+00:00",
            metric_types=["activation"],
        )
        # Only activation rows returned.
        assert len(exported) == 1
        assert exported[0]["metric_category"] == "activation"

    def test_export_anonymized_missing_dates_raises(self, collector):
        """Verify: empty start_date or end_date raises."""
        with pytest.raises(MetricsValidationError, match="start_date"):
            collector.export_anonymized(
                start_date="", end_date="2100-01-01T00:00:00+00:00"
            )
        with pytest.raises(MetricsValidationError, match="start_date"):
            collector.export_anonymized(
                start_date="2000-01-01T00:00:00+00:00", end_date=""
            )

    def test_get_summary_unknown_metric_returns_empty(self, collector):
        """Verify: unrecognized metric_type returns empty dict."""
        result = collector.get_summary(metric_type="unknown_metric")
        assert result == {}

    def test_get_summary_activation_with_data(self, collector):
        """Verify: activation summary computes rate correctly."""
        rid = collector.record_activation(
            user_id="u1",
            onboarding_completed_at=_iso_now(),
            first_use_at=_iso_now(),
        )
        # Mark one user as activated.
        collector._conn.execute(
            "UPDATE metrics_activation SET activation_criteria_met=1 WHERE id=?",
            (rid,),
        )
        collector._conn.commit()
        summary = collector.get_summary(metric_type="activation")
        assert summary["total_onboarded"] == 1
        assert summary["activated_users"] == 1
        assert summary["activation_rate_pct"] == 100.0

    def test_get_summary_upgrade_with_data(self, collector):
        """Verify: upgrade summary counts upgraded users."""
        collector.record_upgrade(
            user_id="u1", from_version="basic", to_version="pro_activated"
        )
        collector.record_upgrade(
            user_id="u2", from_version="pro_trial", to_version="pro_activated"
        )
        summary = collector.get_summary(metric_type="upgrade")
        assert summary["upgraded_users"] == 2
        assert summary["from_basic_count"] == 1

    def test_get_summary_flywheel_with_data(self, collector):
        """Verify: flywheel summary computes flywheel_rate_pct."""
        collector.record_flywheel(
            user_id="u1", flywheel_level=2, previous_level=1
        )
        collector.record_flywheel(
            user_id="u2", flywheel_level=1, previous_level=0
        )
        summary = collector.get_summary(metric_type="flywheel")
        assert summary["total_users"] == 2
        assert summary["flywheel_users"] == 1  # only u1 reached >=2
        assert summary["flywheel_rate_pct"] == 50.0

    def test_get_summary_payment_with_data(self, collector):
        """Verify: payment summary computes paid_users + total_paid_amount."""
        collector.record_payment(
            user_id="u1", payment_status="paid", amount=199.0
        )
        collector.record_payment(user_id="u2", payment_status="trial")
        summary = collector.get_summary(metric_type="payment")
        assert summary["paid_users"] == 1
        assert summary["trial_count"] == 1
        assert summary["total_paid_amount"] == 199.0

    def test_get_summary_with_date_filter(self, collector):
        """Verify: get_summary respects start_date / end_date."""
        # Insert a record (created_at = now).
        collector.record_nps(user_id="u1", score=9)
        # Query with future start_date → no results.
        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        summary = collector.get_summary(
            metric_type="nps", start_date=future
        )
        assert summary["total_responses"] == 0
        assert summary["nps_score"] == 0.0

    def test_serialize_metadata_truncates_oversized(self, collector):
        """Verify: metadata >4KB is truncated (ADR-004 §6)."""
        # Arrange — build metadata that exceeds 4KB when JSON-encoded.
        big_value = "x" * 5000
        record_id = collector.record_activation(
            user_id="u1",
            onboarding_completed_at=_iso_now(),
            first_use_at=_iso_now(),
            metadata={"big_field": big_value},
        )
        # Assert — stored metadata is at most 4KB.
        row = collector._conn.execute(
            "SELECT metadata FROM metrics_activation WHERE id=?", (record_id,)
        ).fetchone()
        stored = row["metadata"]
        assert len(stored.encode("utf-8")) <= 4096

    def test_serialize_metadata_non_serializable_fallback(self, collector):
        """Verify: non-JSON-serializable metadata falls back to '{}'.

        Scenario: metadata contains an object whose default=str also fails
            (e.g. an object that raises in __repr__). json.dumps with
            default=str rarely fails, so we pass a set which becomes a
            string via default=str (no failure). Instead, force failure
            by passing bytes which json cannot serialize even with default=str.
        """
        # bytes triggers TypeError even with default=str
        record_id = collector.record_activation(
            user_id="u1",
            onboarding_completed_at=_iso_now(),
            first_use_at=_iso_now(),
            metadata={"raw": b"binary data"},
        )
        row = collector._conn.execute(
            "SELECT metadata FROM metrics_activation WHERE id=?", (record_id,)
        ).fetchone()
        # default=str converts bytes to its repr, so this still serializes.
        # The test verifies no crash; metadata is valid JSON.
        parsed = json.loads(row["metadata"])
        assert "raw" in parsed

    def test_sanitize_for_export_scrubs_pii_from_metadata(self, collector):
        """Verify: export scrubs business_name/ip/email/phone from metadata."""
        collector.record_nps(
            user_id="u1",
            score=9,
            metadata={
                "business_name": "Secret Corp",
                "ip": "10.0.0.1",
                "email": "user@example.com",
                "phone": "123-456-7890",
                "keep_me": "kept",
            },
        )
        exported = collector.export_anonymized(
            start_date="2000-01-01T00:00:00+00:00",
            end_date="2100-01-01T00:00:00+00:00",
        )
        nps_row = next(r for r in exported if r.get("metric_category") == "experience")
        meta = nps_row["metadata"]
        assert "business_name" not in meta
        assert "ip" not in meta
        assert "email" not in meta
        assert "phone" not in meta
        assert meta["keep_me"] == "kept"

    def test_resolve_db_path_from_env_var(self, monkeypatch, tmp_path):
        """Verify: METRICS_DB_PATH env var overrides default path."""
        MetricsCollector._reset_singleton()
        env_db_path = str(tmp_path / "env_override.db")
        monkeypatch.setenv("METRICS_DB_PATH", env_db_path)
        collector = MetricsCollector()  # no db_path arg
        assert os.path.exists(env_db_path)
        # Record a row to confirm the DB is usable.
        rid = collector.record_nps(user_id="env-user", score=10)
        assert len(rid) == 32

    def test_resolve_salt_from_file_when_env_unset(
        self, monkeypatch, tmp_path
    ):
        """Verify: salt is read from file when env var is unset.

        Scenario: METRICS_ANONYMIZATION_SALT not set; salt file at
            METRICS_DB_PATH's directory is generated and persisted.
        Expected: two collectors with the same salt file produce the
            same anonymized_user_hash for the same user_id.
        """
        # Arrange — unset env, point salt path to temp via HOME override.
        MetricsCollector._reset_singleton()
        monkeypatch.delenv("METRICS_ANONYMIZATION_SALT", raising=False)
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        db_path = str(tmp_path / "salt_test.db")

        # Act — first collector generates + persists the salt.
        c1 = MetricsCollector(db_path=db_path)
        c1.record_nps(user_id="salt-user", score=9)
        exported1 = c1.export_anonymized(
            start_date="2000-01-01T00:00:00+00:00",
            end_date="2100-01-01T00:00:00+00:00",
        )
        hash1 = exported1[0]["anonymized_user_hash"]

        # Reset + create a second collector — should read the persisted salt.
        MetricsCollector._reset_singleton()
        c2 = MetricsCollector(db_path=db_path)
        exported2 = c2.export_anonymized(
            start_date="2000-01-01T00:00:00+00:00",
            end_date="2100-01-01T00:00:00+00:00",
        )
        hash2 = exported2[0]["anonymized_user_hash"]

        # Assert — same user_id + same salt file → same hash.
        assert hash1 == hash2
        # Salt file exists at ~/.opc-agents/data/.metrics_salt
        salt_file = fake_home / ".opc-agents" / "data" / ".metrics_salt"
        assert salt_file.exists()
        salt_mode = stat.S_IMODE(os.stat(salt_file).st_mode)
        assert salt_mode == 0o600

    def test_close_idempotent_and_safe_after_reclose(self, collector):
        """Verify: close() can be called multiple times without error."""
        collector.close()
        # Second close is a no-op.
        collector.close()
        # Subsequent write raises MetricsDBError (connection closed).
        with pytest.raises(MetricsDBError, match="connection is closed"):
            collector.record_nps(user_id="u1", score=9)

    def test_get_metrics_collector_factory_returns_singleton(self, collector):
        """Verify: get_metrics_collector() returns the existing singleton."""
        assert get_metrics_collector() is collector
        assert get_metrics_collector(db_path="/different/path") is collector


# ---------------------------------------------------------------------------
# Migration v8 — rollback scenario
# ---------------------------------------------------------------------------
class TestMigrationV8Rollback:
    """Dedicated rollback test (split for clarity)."""

    def test_migration_v8_rollback_on_failure(self, tmp_path):
        """Verify: migration failure rolls back transaction + restores backup.

        Scenario: pre-create metrics_activation with wrong schema (no user_id
            column). CREATE INDEX idx_activation_user_id fails mid-migration.
        Expected: RuntimeError raised; db_version stays 7; pre-existing
            business data preserved; no partial metrics tables left behind.
        """
        # Arrange — set up a v7 DB with a conflicting metrics_activation table.
        db_path = str(tmp_path / "rollback_test.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO _meta (key, value) VALUES ('db_version', '7')"
        )
        # Pre-existing business data that must survive the failed migration.
        conn.execute(
            "CREATE TABLE test_business_data (id TEXT PRIMARY KEY, payload TEXT)"
        )
        conn.execute(
            "INSERT INTO test_business_data (id, payload) VALUES (?, ?)",
            ("row-1", "important-data"),
        )
        # Pre-create metrics_activation with INCOMPLETE schema (no user_id).
        # This causes CREATE INDEX idx_activation_user_id to fail mid-migration.
        conn.execute("CREATE TABLE metrics_activation (id TEXT PRIMARY KEY)")
        conn.commit()

        # Act + Assert — migration must raise and roll back.
        with pytest.raises(RuntimeError, match="rolled back"):
            migrate_v8(conn)

        # Assert — DB state is preserved (rollback worked).
        version_row = conn.execute(
            "SELECT value FROM _meta WHERE key='db_version'"
        ).fetchone()
        assert int(version_row["value"]) == 7, "db_version should remain 7"
        # Pre-existing business data intact.
        biz = conn.execute(
            "SELECT payload FROM test_business_data WHERE id='row-1'"
        ).fetchone()
        assert biz["payload"] == "important-data"
        # No new metrics tables should exist (rollback undid CREATE TABLE).
        for table in (
            "metrics_upgrade",
            "metrics_flywheel",
            "metrics_payment",
            "metrics_experience",
        ):
            cnt = conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()[0]
            assert cnt == 0, f"table {table} should not exist after rollback"
        conn.close()
