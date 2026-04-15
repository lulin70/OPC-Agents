"""Phase 3: FlywheelTracker DB 持久化测试"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_models.models import Base
from opc_manager.flywheel_tracker import FlywheelTrackerDB
from opc_manager.business_types import BusinessType


@pytest.fixture
def tracker_with_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    tracker = FlywheelTrackerDB(db_session=session)
    yield tracker, session
    session.close()


class TestFlywheelTrackerPersistence:
    """飞轮追踪器持久化核心测试"""

    def test_initial_state_created_in_db_on_first_access(self, tracker_with_db):
        tracker, session = tracker_with_db
        tracker.record_scenario_completion("new_user_persist", "content_calendar", BusinessType.CONTENT_CREATOR)
        
        from db_models.models import FlywheelState as FS
        db_state = session.query(FS).filter_by(user_id="new_user_persist").first()
        assert db_state is not None
        assert db_state.current_level == 1

    def test_scenario_completion_persisted_to_db(self, tracker_with_db):
        tracker, _ = tracker_with_db
        tracker.record_scenario_completion("persist_user_1", "content_calendar", BusinessType.CONTENT_CREATOR)

        from db_models.models import FlywheelState as FS
        db_state = _.query(FS).filter_by(user_id="persist_user_1").first()
        assert db_state.total_scenarios_completed == 1
        assert db_state.current_level == 1

    def test_level_upgrade_from_1_to_2(self, tracker_with_db):
        tracker, session = tracker_with_db
        
        for i in range(6):
            if i < 3:
                tracker.record_scenario_completion("lv2_user_same", f"sc_{i}", BusinessType.CONTENT_CREATOR)
            else:
                tracker.record_scenario_completion("lv2_user_same", f"sc_{i}", BusinessType.ECOMMERCE)

        state = tracker.get_or_create_state("lv2_user_same")
        assert state.current_level.value == 2

    def test_restart_preserves_data(self, tracker_with_db):
        tracker, session = tracker_with_db
        tracker.record_scenario_completion("restart_test", "content_calendar", BusinessType.CONTENT_CREATOR)
        
        new_tracker = FlywheelTrackerDB(db_session=session)
        state = new_tracker.get_or_create_state("restart_test")
        assert state.total_scenarios_completed >= 1

    def test_dimension_scores_persisted(self, tracker_with_db):
        tracker, session = tracker_with_db
        
        for _ in range(5):
            tracker.record_scenario_completion("dim_test", "content_calendar", BusinessType.CONTENT_CREATOR)

        from db_models.models import FlywheelState as FS
        db_state = session.query(FS).filter_by(user_id="dim_test").first()
        scores = db_state.dimension_scores
        assert scores is not None
        assert scores.get("content_quality", 0) > 0

    def test_active_types_persisted(self, tracker_with_db):
        tracker, _ = tracker_with_db
        tracker.record_scenario_completion("types_test", "sc_a", BusinessType.CONTENT_CREATOR)
        tracker.record_scenario_completion("types_test", "sc_b", BusinessType.CONSULTANT)

        from db_models.models import FlywheelState as FS
        db_state = _.query(FS).filter_by(user_id="types_test").first()
        assert "content_creator" in db_state.active_types
        assert "consultant" in db_state.active_types

    def test_multiple_users_isolated(self, tracker_with_db):
        tracker, _ = tracker_with_db
        tracker.record_scenario_completion("user_alpha", "sc1", BusinessType.CONTENT_CREATOR)
        tracker.record_scenario_completion("user_beta", "sc1", BusinessType.AI_TOOL_BUILDER)
        tracker.record_scenario_completion("user_beta", "sc2", BusinessType.AI_TOOL_BUILDER)

        state_alpha = tracker.get_or_create_state("user_alpha")
        state_beta = tracker.get_or_create_state("user_beta")

        assert state_alpha.total_scenarios_completed == 1
        assert state_beta.total_scenarios_completed == 2
        assert BusinessType.CONTENT_CREATOR in state_alpha.active_types
        assert BusinessType.AI_TOOL_BUILDER in state_beta.active_types

    def test_fallback_to_memory_when_no_session(self):
        tracker = FlywheelTrackerDB(db_session=None)
        state = tracker.record_scenario_completion("memory_only", "sc1", BusinessType.ECOMMERCE)
        assert state.total_scenarios_completed == 1
        assert BusinessType.ECOMMERCE in state.active_types
