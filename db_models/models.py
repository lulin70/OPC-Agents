"""Phase 3 数据持久化层 - ORM 模型定义"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    primary_business_type = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    flywheel_state = relationship("FlywheelState", back_populates="user", uselist=False)
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, type={self.primary_business_type})>"


class FlywheelState(Base):
    __tablename__ = "flywheel_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    current_level = Column(Integer, default=1)
    active_types = Column(JSON, default=list)
    health_score = Column(Float, default=0.0)

    dimension_scores = Column(JSON, default=dict)
    total_scenarios_completed = Column(Integer, default=0)
    active_days = Column(Integer, default=0)
    achievements = Column(JSON, default=list)
    last_transition_date = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="flywheel_state")

    def __repr__(self):
        return f"<FlywheelState(user_id={self.user_id}, level=Lv{self.current_level}, score={self.health_score})>"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan",
                           order_by="Message.created_at")
    user = relationship("User", back_populates="conversations")

    __table_args__ = (
        Index("ix_conversations_user_id", "user_id"),
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title}, messages={len(self.messages)})>"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    business_type = Column(String(32), nullable=True)
    persona_variant = Column(String(32), nullable=True)
    scenario_id = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, content={self.content[:50]}...)"


class ScenarioExecution(Base):
    __tablename__ = "scenario_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scenario_id = Column(String(64), nullable=False)
    business_type = Column(String(32), nullable=True)
    status = Column(String(20), default="completed")
    duration_ms = Column(Integer, nullable=True)
    deliverables = Column(JSON, default=list)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_scenario_executions_user_id", "user_id"),
        Index("ix_scenario_executions_scenario_id", "scenario_id"),
    )


class LLMUsageLog(Base):
    __tablename__ = "llm_usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    provider = Column(String(20), nullable=False)
    model = Column(String(50), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Float, nullable=True)
    function_name = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_llm_usage_logs_user_id", "user_id"),
        Index("ix_llm_usage_logs_created_at", "created_at"),
    )
