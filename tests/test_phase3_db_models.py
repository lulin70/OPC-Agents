"""Phase 3: 数据模型 ORM 测试"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_models.models import Base, User, FlywheelState, Conversation, Message, ScenarioExecution, LLMUsageLog


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestUserModel:
    """User 模型 CRUD 测试"""

    def test_create_user(self, db_session):
        user = User(id="user_001", username="test_user", primary_business_type="content_creator")
        db_session.add(user)
        db_session.commit()

        fetched = db_session.query(User).filter_by(id="user_001").first()
        assert fetched is not None
        assert fetched.username == "test_user"
        assert fetched.primary_business_type == "content_creator"

    def test_unique_username_constraint(self, db_session):
        db_session.add(User(id="u1", username="dup_name"))
        db_session.commit()

        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            db_session.add(User(id="u2", username="dup_name"))
            db_session.commit()


class TestFlywheelStateModel:
    """FlywheelState 模型测试"""

    def test_create_flywheel_state(self, db_session):
        user = User(id="user_fw", username="fw_test")
        db_session.add(user)
        db_session.flush()

        state = FlywheelState(
            user_id="user_fw",
            current_level=2,
            active_types=["content_creator", "ecommerce"],
            health_score=62.5,
            dimension_scores={"content_quality": 70.0, "audience_growth": 55.0},
            total_scenarios_completed=15,
            achievements=["first_step", "cross_discipline"],
        )
        db_session.add(state)
        db_session.commit()

        fetched = db_session.query(FlywheelState).filter_by(user_id="user_fw").first()
        assert fetched.current_level == 2
        assert fetched.health_score == 62.5
        assert "first_step" in fetched.achievements

    def test_json_fields_persistence(self, db_session):
        user = User(id="user_json", username="json_test")
        db_session.add(user)
        db_session.flush()

        complex_data = {"nested": {"key": "value"}, "list": [1, 2, 3]}
        state = FlywheelState(user_id="user_json", metadata_json=complex_data)
        db_session.add(state)
        db_session.commit()

        fetched = db_session.query(FlywheelState).filter_by(user_id="user_json").first()
        assert fetched.metadata_json == complex_data


class TestConversationAndMessage:
    """会话和消息模型测试"""

    def test_conversation_with_messages(self, db_session):
        user = User(id="user_conv", username="conv_test")
        db_session.add(user)
        db_session.flush()

        conv = Conversation(id="conv_001", user_id="user_conv", title="测试对话")
        db_session.add(conv)
        db_session.flush()

        msg1 = Message(conversation_id="conv_001", role="user", content="帮我规划内容日历",
                        business_type="content_creator")
        msg2 = Message(conversation_id="conv_001", role="assistant",
                        content="好的！让我分析一下热点...",
                        persona_variant="content_creator", confidence=0.92)
        db_session.add_all([msg1, msg2])
        db_session.commit()

        messages = db_session.query(Message).filter_by(conversation_id="conv_001").all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].persona_variant == "content_creator"


class TestScenarioExecution:
    """场景执行记录测试"""

    def test_scenario_execution_crud(self, db_session):
        user = User(id="user_se", username="se_test")
        db_session.add(user)
        db_session.flush()

        exec_record = ScenarioExecution(
            user_id="user_se",
            scenario_id="content_calendar",
            business_type="content_creator",
            status="completed",
            duration_ms=1250,
            deliverables=[{"type": "markdown", "title": "内容日历.md"}],
        )
        db_session.add(exec_record)
        db_session.commit()

        records = db_session.query(ScenarioExecution).filter_by(user_id="user_se").all()
        assert len(records) == 1
        assert records[0].scenario_id == "content_calendar"
        assert records[0].status == "completed"
        assert len(records[0].deliverables) == 1


class TestLLMUsageLog:
    """LLM 用量日志测试"""

    def test_usage_log_crud(self, db_session):
        log = LLMUsageLog(
            provider="mock",
            model="mock-model",
            prompt_tokens=150,
            completion_tokens=80,
            total_tokens=230,
            estimated_cost_usd=0.0,
            latency_ms=120.5,
            function_name="detect_business_type_by_llm",
        )
        db_session.add(log)
        db_session.commit()

        logs = db_session.query(LLMUsageLog).all()
        assert len(logs) == 1
        assert logs[0].total_tokens == 230
        assert logs[0].function_name == "detect_business_type_by_llm"
