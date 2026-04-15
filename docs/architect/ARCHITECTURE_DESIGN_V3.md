# OPC-Agents 架构设计文档 v3.0 (Phase 3)

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v3.0.0 | 2026-04-15 | 架构师 | Phase 3架构：Web层/LLM服务/持久化/适配器/CI-CD | 待审核 |
| v2.1.0 | 2026-04-14 | 架构师 | Phase 2架构：6类型+9场景+人格系统 | 已审核 |

---

## 一、架构概述

### 1.1 系统边界（v3.0 扩展）

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPC-Agents v3.0 系统边界                       │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Web 前端     │  │  REST API    │  │  外部平台集成         │  │
│  │ (Streamlit)  │  │ (FastAPI)   │  │  (PlatformAdapter)   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────────────┘  │
│         │                 │                  │                   │
│  ┌──────▼─────────────────▼──────────────────▼───────────────┐  │
│  │                    核心业务层 (v2.2.0 稳定)                │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │  │
│  │  │ScenarioEngine│ │DetectorV2  │ │  FlywheelTracker    │  │  │
│  │  │    V2        │ │            │ │  (新增DB持久化)      │  │  │
│  │  └──────┬──────┘ └──────┬──────┘ └──────────┬──────────┘  │  │
│  │         │               │                    │              │  │
│  │  ┌──────▼───────────────▼────────────────────▼──────────┐  │  │
│  │  │              LLM 服务层 (v3.0 新增)                   │  │  │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐               │  │  │
│  │  │  │OpenAI   │ │ Ollama  │ │ Mock    │               │  │  │
│  │  │  │Backend  │ │(本地)   │ │Backend  │               │  │  │
│  │  │  └─────────┘ └─────────┘ └─────────┘               │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              数据持久化层 (v3.0 新增)                       │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │  │
│  │  │ SQLite   │  │PostgreSQL│  │ Redis    │ (可选缓存)     │  │
│  │  │ (开发)   │  │ (生产)   │  │ (缓存)   │               │  │
│  │  └──────────┘  └──────────┘  └──────────┘               │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 模块清单（v3.0 vs v2.2.0 对比）

| 模块 | v2.2.0 状态 | v3.0 变更 | 优先级 |
|------|------------|-----------|--------|
| `scenario_engine_v2` | ✅ 9场景 | 🔧 无变化（稳定） | - |
| `business_type_detector_v2` | ✅ 100%准确 | 🆕 集成LLM服务层 | P0 |
| `flywheel_tracker` | ✅ 内存存储 | 🆕 DB持久化迁移 | P0 |
| `persona_manager` | ✅ 6变体 | 🔧 无变化 | - |
| `web_app` | ❌ 不存在 | 🆕 FastAPI + Streamlit | P0 |
| `llm_service` | ❌ 存根 | 🆕 完整实现 | P0 |
| `db_models` | ❌ 不存在 | 🆕 SQLAlchemy ORM | P0 |
| `platform_adapters` | ❌ 不存在 | 🆕 抽象适配器 + Mock | P1 |
| `ci_cd` | ❌ 不存在 | 🆕 GitHub Actions | P1 |

---

## 二、核心模块设计

### 2.1 Web应用层

#### 2.1.1 技术选型决策 (ADR-003)

**决策**：采用 **FastAPI (后端) + Streamlit (前端)** 组合

**备选方案对比**：

| 方案 | 优势 | 劣势 | 决策理由 |
|------|------|------|---------|
| **FastAPI+Streamlit** ✅ | 快速原型；API自动文档；Python全栈 | 定制UI受限 | **Phase 3选此：速度优先** |
| FastAPI+React | UI完全可控；生态丰富 | 前端工程量大 | 推迟到Phase 4 |
| Flask+Jinja2 | 简单直接 | API文档需手写 | 过于传统 |
| Gradio | AI demo专用 | 生产环境不适合 | 仅适合demo |

#### 2.1.2 项目结构

```
opc_agents_v3/
├── web_app/
│   ├── __init__.py
│   ├── main.py              # FastAPI应用入口
│   ├── config.py             # 应用配置（环境变量）
│   ├── dependencies.py       # 依赖注入（DB session, LLM service）
│   ├── routes/
│   │   ├── chat.py           # 对话接口
│   │   ├── flywheel.py       # 飞轮数据接口
│   │   ├── scenarios.py      # 场景执行接口
│   │   ├── personas.py       # 人格管理接口
│   │   └── health.py         # 健康检查
│   ├── schemas/              # Pydantic请求/响应模型
│   │   ├── chat.py
│   │   ├── flywheel.py
│   │   └── common.py
│   ├── middleware/
│   │   ├── auth.py           # JWT认证中间件
│   │   ├── rate_limit.py     # 限流中间件
│   │   └── error_handler.py  # 统一错误处理
│   └── services/
│       ├── chat_service.py   # 对话业务逻辑
│       └── export_service.py # 交付物导出
├── frontend/
│   ├── app.py                # Streamlit前端入口
│   ├── pages/
│   │   ├── chat.py           # 聊天页面
│   │   ├── dashboard.py      # 飞轮仪表盘
│   │   ├── settings.py       # 设置页面
│   │   └── history.py        # 历史记录
│   └── components/
│       ├── persona_card.py   # 人格卡片组件
│       └── progress_bar.py   # 进度条组件
```

#### 2.1.3 核心API接口定义

```python
# web_app/routes/chat.py
from fastapi import APIRouter, Depends
from web_app.schemas.chat import ChatRequest, ChatResponse, ChatMessage
from web_app.dependencies import get_llm_service, get_detector, get_persona_mgr

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    detector: BusinessTypeDetectorV2 = Depends(get_detector),
    persona_mgr: PersonaManager = Depends(get_persona_mgr),
    llm_svc: LLMService = Depends(get_llm_service),
):
    """
    发送消息到对话系统
    
    流程：
    1. 业务类型检测（关键词 → LLM兜底）
    2. 加载对应人格配置
    3. 场景匹配与路由
    4. 生成回复（含人格风格）
    5. 记录会话历史到DB
    """
    pass


@router.get("/history", response_model=list[ChatMessage])
async def get_history(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
):
    """获取会话历史记录（分页）"""
    pass


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    pass
```

```python
# web_app/schemas/chat.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatMessage(BaseModel):
    role: ChatRole
    content: str
    timestamp: datetime
    persona_variant: Optional[str] = None
    business_type: Optional[str] = None
    scenario_id: Optional[str] = None
    metadata: dict = {}

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    user_id: str = Field(..., min_length=1)
    explicit_business_type: Optional[str] = None
    stream: bool = False

class ChatResponse(BaseModel):
    reply: ChatMessage
    detected_business_type: str
    confidence: float
    scenario_matched: bool
    scenario_id: Optional[str] = None
    deliverables: list[dict] = []
    flywheel_update: Optional[dict] = None
    suggestions: list[str] = []
```

### 2.2 LLM服务层

#### 2.2.1 架构设计

```python
# opc_manager/llm_service.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

class LLMProvider(Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    MOCK = "mock"

@dataclass
class LLMResponse:
    content: str
    provider: LLMProvider
    model: str
    usage: Dict[str, int]
    latency_ms: float
    raw_response: Any = None

@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.MOCK
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 500
    temperature: float = 0.3
    timeout_seconds: float = 10.0
    max_retries: int = 2
    cost_budget_daily: float = 5.0

class LLMBackend(ABC):
    """LLM后端抽象接口"""
    
    @abstractmethod
    async def complete(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        pass
    
    @abstractmethod
    def estimate_cost(self, prompt: str) -> float:
        pass

class OpenAIBackend(LLMBackend):
    """OpenAI API 后端实现"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = None
    
    async def complete(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        import openai
        if not self.client:
            self.client = openai.AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            timeout=self.config.timeout_seconds,
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            provider=LLMProvider.OPENAI,
            model=self.config.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            latency_ms=0,
            raw_response=response,
        )

class OllamaBackend(LLMBackend):
    """本地Ollama后端实现"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or "http://localhost:11434"
    
    async def complete(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        import httpx
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            data = resp.json()
            
            return LLMResponse(
                content=data.get("response", ""),
                provider=LLMProvider.OLLAMA,
                model=self.config.model,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                latency_ms=data.get("total_duration", 0) / 1_000_000,
            )

class MockLLMBackend(LLMBackend):
    """Mock后端，用于开发和测试"""
    
    MOCK_RESPONSES = {
        "detect_type": '{"business_type":"content_creator","confidence":0.85,"reasoning":"检测到内容创作相关关键词"}',
        "default": "这是一个模拟的LLM响应，用于开发和测试。"
    }
    
    async def complete(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        import time
        import random
        
        simulated_latency = random.uniform(50, 200)
        await asyncio.sleep(simulated_latency / 1000)
        
        for key, response in self.MOCK_RESPONSES.items():
            if key in prompt.lower():
                return LLMResponse(
                    content=response,
                    provider=LLMProvider.MOCK,
                    model="mock-model",
                    usage={"prompt_tokens": len(prompt)//4, "completion_tokens": len(response)//4, "total_tokens": 0},
                    latency_ms=simulated_latency,
                )
        
        return LLMResponse(
            content=self.MOCK_RESPONSES["default"],
            provider=LLMProvider.MOCK,
            model="mock-model",
            usage={"prompt_tokens": len(prompt)//4, "completion_tokens": 20, "total_tokens": 0},
            latency_ms=simulated_latency,
        )

class LLMService:
    """LLM服务统一入口"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.backend = self._create_backend(config.provider)
        self._usage_tracker = UsageTracker(config.cost_budget_daily)
    
    def _create_backend(self, provider: LLMProvider) -> LLMBackend:
        backends = {
            LLMProvider.OPENAI: OpenAIBackend,
            LLMProvider.OLLAMA: OllamaBackend,
            LLMProvider.MOCK: MockLLMBackend,
        }
        return backends[provider](self.config)
    
    async def detect_business_type_by_llm(self, user_input: str, history: list = None) -> dict:
        """使用LLM进行业务类型检测"""
        system_prompt = """你是一个业务类型分类专家。根据用户的输入，判断其属于以下哪种一人公司类型：

选项：
- content_creator: 内容创作者（写文章、做视频、自媒体）
- digital_product: 数字产品开发者（卖课程、电子书、模板）
- ai_tool_builder: AI工具开发者（做SaaS、API、插件）
- consultant: 专业咨询顾问（企业培训、1v1咨询）
- ecommerce: 电商运营者（卖实物商品、闲鱼、抖音小店）
- creative_work: 创意工作者（设计师、摄影师、翻译）

只返回JSON格式：{"business_type": "类型", "confidence": 0.95, "reasoning": "原因"}"""
        
        response = await self.backend.complete(user_input, system_prompt)
        self._usage_tracker.record(response.usage)
        
        try:
            import json
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"business_type": "unknown", "confidence": 0.0, "reasoning": "LLM返回格式异常"}
    
    async def generate_persona_response(self, user_input: str, persona_config: dict, context: dict = None) -> str:
        """基于人格配置生成风格化回复"""
        tone = persona_config.get("style_overrides", {}).get("tone", "专业")
        expertise = persona_config.get("expertise_tags", [])
        
        system_prompt = f"""你是{persona_config.get('display_name', '总裁办秘书')}。
语气：{tone}
专业领域：{', '.join(expertise[:3])}
回复要求：简洁、有温度、带适当emoji。"""
        
        response = await self.backend.complete(user_input, system_prompt)
        self._usage_tracker.record(response.usage)
        return response.content
    
    def switch_provider(self, new_provider: LLMProvider, config_override: dict = None):
        """动态切换LLM后端"""
        new_config = self.config.copy()
        new_config.provider = new_provider
        if config_override:
            for k, v in config_override.items():
                setattr(new_config, k, v)
        self.backend = self._create_backend(new_provider)

class UsageTracker:
    """Token用量追踪器"""
    
    def __init__(self, daily_budget: float):
        self.daily_budget = daily_budget
        self.daily_usage = {}
        self.total_today = 0.0
    
    def record(self, usage: dict):
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.daily_usage:
            self.daily_usage[today] = {"tokens": 0, "cost": 0.0, "calls": 0}
        
        self.daily_usage[today]["tokens"] += usage.get("total_tokens", 0)
        self.daily_usage[today]["calls"] += 1
        
    def is_budget_exceeded(self) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.daily_usage.get(today, {}).get("cost", 0) >= self.daily_budget
    
    def get_report(self) -> dict:
        return self.daily_usage
```

#### 2.2.2 Detector V2 集成改造

```python
# 在 business_type_detector_v2.py 中修改 detect() 方法
class BusinessTypeDetectorV2:
    def __init__(self, enable_llm: bool = False, llm_service: LLMService = None):
        self.enable_llm = enable_llm
        self.llm_service = llm_service
        # ... 其他初始化保持不变
    
    def detect(self, input_text, user_profile=None, history=None, min_confidence=None) -> DetectionResult:
        # Step 1-5 保持原有逻辑不变...
        result = self._detect_original(input_text, user_profile, history, min_confidence)
        
        # Step 6: LLM辅助检测（仅在置信度低时触发）
        if self.enable_llm and self.llm_service and result.confidence < 0.7:
            import asyncio
            try:
                llm_result = asyncio.get_event_loop().run_until_complete(
                    self.llm_service.detect_business_type_by_llm(input_text, history)
                )
                
                if llm_result.get("confidence", 0) > result.confidence:
                    result.business_type = BusinessType(llm_result["business_type"])
                    result.confidence = llm_result["confidence"]
                    result.method = "llm_assisted"
                    result.reasoning = llm_result.get("reasoning", "")
            except Exception as e:
                logger.warning(f"LLM detection failed, fallback to keyword: {e}")
        
        return result
```

### 2.3 数据持久化层

#### 2.3.1 数据模型设计

```python
# db_models/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum
import json

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(64), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    primary_business_type = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    flywheel_state = relationship("FlywheelState", back_populates="user", uselist=False)
    conversations = relationship("Conversation", back_populates="user")

class FlywheelState(Base):
    __tablename__ = "flywheel_states"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey("users.id"), unique=True, nullable=False)
    current_level = Column(Integer, default=1)
    active_types = Column(JSON, default=list)
    health_score = Column(Float, default=0.0)
    
    dimension_scores = Column(JSON, default=dict)
    total_scenarios_completed = Column(Integer, default=0)
    active_days = Column(Integer, default=0)
    achievements = Column(JSON, default=list)
    last_transition_date = Column(DateTime)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="flywheel_state")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    user = relationship("User", back_populates="conversations")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    business_type = Column(String(32))
    persona_variant = Column(String(32))
    scenario_id = Column(String(64))
    confidence = Column(Float)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")

class ScenarioExecution(Base):
    __tablename__ = "scenario_executions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    scenario_id = Column(String(64), nullable=False)
    business_type = Column(String(32))
    status = Column(String(20), default="completed")
    duration_ms = Column(Integer)
    deliverables = Column(JSON, default=list)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class LLMUsageLog(Base):
    __tablename__ = "llm_usage_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey("users.id"))
    provider = Column(String(20))
    model = Column(String(50))
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Float)
    function_name = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 2.3.2 FlywheelTracker 持久化改造

```python
# 在 flywheel_tracker.py 中添加 DB 支持
from db_models.models import FlywheelState, Base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

class FlywheelTrackerDB(FlywheelTracker):
    """支持数据库持久化的飞轮追踪器"""
    
    def __init__(self, db_session: Session = None, engine=None):
        super().__init__()
        self.db_session = db_session
        self.engine = engine
    
    def _load_from_db(self, user_id: str) -> UserFlywheelState:
        """从数据库加载用户飞轮状态"""
        if not self.db_session:
            return super()._get_or_create_state(user_id)
        
        db_state = self.db_session.query(FlywheelState).filter(
            FlywheelState.user_id == user_id
        ).first()
        
        if not db_state:
            return self._create_default_state(user_id)
        
        return UserFlywheelState(
            user_id=db_state.user_id,
            current_level=FlywheelLevel(db_state.current_level),
            active_types=[BusinessType(t) for t in (db_state.active_types or [])],
            dimension_scores=DimensionScore(**(db_state.dimension_scores or {})),
            scenario_completion_count={},
            total_scenarios_completed=db_state.total_scenarios_completed,
            active_days=db_state.active_days,
            achievements=db_state.achievements or [],
        )
    
    def _save_to_db(self, state: UserFlywheelState):
        """保存飞轮状态到数据库"""
        if not self.db_session:
            return
        
        db_state = self.db_session.query(FlywheelState).filter(
            FlywheelState.user_id == state.user_id
        ).first()
        
        if not db_state:
            db_state = FlywheelState(user_id=state.user_id)
            self.db_session.add(db_state)
        
        db_state.current_level = state.current_level.value
        db_state.active_types = [t.value for t in state.active_types]
        db_state.health_score = self.get_flywheel_health_score(state.user_id)
        db_state.dimension_scores = {
            "content_quality": state.dimension_scores.content_quality,
            "audience_growth": state.dimension_scores.audience_growth,
            "monetization": state.dimension_scores.monetization,
            "cross_promotion": state.dimension_scores.cross_promotion,
            "ecosystem_synergy": state.dimension_scores.ecosystem_synergy,
        }
        db_state.total_scenarios_completed = state.total_scenarios_completed
        db_state.active_days = state.active_days
        db_state.achievements = state.achievements
        db_state.updated_at = datetime.utcnow()
        
        self.db_session.commit()
```

### 2.4 外部平台适配器

```python
# opc_manager/platform_adapters.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import time
import random

class PlatformType(Enum):
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    GUMROAD = "gumroad"
    BILIBILI = "bilibili"
    WECHAT = "wechat"

@dataclass
class PlatformData:
    platform: PlatformType
    data_type: str
    raw_data: Dict[str, Any]
    fetched_at: float
    is_mock: bool = False
    cache_ttl: int = 3600

class PlatformAdapter(ABC):
    """外部平台数据适配器抽象基类"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self._cache = {}
    
    @property
    @abstractmethod
    def platform_type(self) -> PlatformType:
        pass
    
    @abstractmethod
    async def fetch_hot_topics(self, category: str = None, limit: int = 10) -> List[Dict]:
        """获取热点话题"""
        pass
    
    @abstractmethod
    async def fetch_user_data(self, user_credentials: dict) -> Dict:
        """获取用户数据（需要认证）"""
        pass
    
    @abstractmethod
    def validate_credentials(self, credentials: dict) -> tuple[bool, str]:
        """验证凭据有效性"""
        pass
    
    async def fetch_with_fallback(self, func, *args, **kwargs):
        """带降级策略的数据获取"""
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            print(f"[{self.platform_type.value}] API调用失败: {e}，启用Mock降级")
            return await self._fallback_response(func.__name__)

class MockXiaohongshuAdapter(PlatformAdapter):
    """小红书 Mock 适配器"""
    
    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.XIAOHONGSHU
    
    async def fetch_hot_topics(self, category: str = None, limit: int = 10) -> List[Dict]:
        mock_topics = [
            {"title": "春季穿搭OOTD", "heat": 98500, "category": "时尚"},
            {"title": "居家办公好物分享", "heat": 78200, "category": "生活"},
            {"title": "减脂餐食谱合集", "heat": 65400, "category": "美食"},
            {"title": "AI工具效率提升", "heat": 54300, "category": "科技"},
            {"title": "副业赚钱方法", "heat": 48900, "category": "职场"},
            {"title": "旅行摄影攻略", "heat": 42100, "category": "旅行"},
            {"title": "读书笔记分享", "height": 38700, "category": "学习"},
            {"title": "护肤步骤详解", "heat": 35600, "category": "美妆"},
            {"title": "健身打卡记录", "heat": 29800, "category": "运动"},
            {"title": "数码产品测评", "heat": 25400, "category": "科技"},
        ]
        
        if category:
            mock_topics = [t for t in mock_topics if t["category"] == category]
        
        return mock_topics[:limit]
    
    async def fetch_user_data(self, user_credentials: dict) -> Dict:
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return {
            "followers": random.randint(1000, 100000),
            "notes_count": random.randint(50, 500),
            "avg_likes": random.randint(100, 10000),
            "engagement_rate": round(random.uniform(0.02, 0.15), 4),
        }
    
    def validate_credentials(self, credentials: dict) -> tuple[bool, str]:
        return True, "Mock模式，始终有效"

class MockGumroadAdapter(PlatformAdapter):
    """Gumroad Mock 适配器"""
    
    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.GUMROAD
    
    async def fetch_hot_topics(self, category: str = None, limit: int = 10) -> List[Dict]:
        return [{"title": f"Gumroad热门产品-{i}", "sales": random.randint(10, 1000)} for i in range(limit)]
    
    async def fetch_user_data(self, user_credentials: dict) -> Dict:
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return {
            "total_sales": round(random.uniform(1000, 50000), 2),
            "products_count": random.randint(1, 20),
            "customers": random.randint(50, 2000),
            "revenue_mtd": round(random.uniform(500, 5000), 2),
        }
    
    def validate_credentials(self, credentials: dict) -> tuple[bool, str]:
        return True, "Mock模式，始终有效"

class AdapterFactory:
    """适配器工厂"""
    
    _adapters = {}
    
    @classmethod
    def get_adapter(cls, platform: PlatformType, use_mock: bool = True, config: dict = None) -> PlatformAdapter:
        cache_key = f"{platform.value}_{'mock' if use_mock else 'real'}"
        
        if cache_key not in cls._adapters:
            if use_mock:
                adapter_map = {
                    PlatformType.XIAOHONGSHU: MockXiaohongshuAdapter,
                    PlatformType.GUMROAD: MockGumroadAdapter,
                }
                cls._adapters[cache_key] = adapter_map[platform](config)
            else:
                raise NotImplementedError(f"真实{platform.value}适配器尚未实现")
        
        return cls._adapters[cache_key]
```

---

## 三、技术风险评估

### 3.1 风险矩阵（Phase 3）

| 风险项 | 影响 | 概率 | 应对策略 |
|--------|------|------|---------|
| LLM API成本不可控 | 高 | 中 | Token限制 + 本地模型降级 + 用量监控 |
| Streamlit性能瓶颈 | 中 | 低 | 数据量有限，足够应对初期用户 |
| DB Schema变更导致回归失败 | 高 | 低 | 向后兼容迁移脚本 + 全量回归测试 |
| FastAPI异步编程复杂度 | 中 | 中 | 先用同步方式，后续优化 |
| 外部API不稳定 | 中 | 高 | Mock兜底 + 缓存 + 超时控制 |

### 3.2 性能指标要求（v3.0）

| 指标 | v2.2.0 | v3.0 目标 | 实现方式 |
|------|---------|-----------|---------|
| 场景识别延迟 | < 500ms | < 300ms (关键词) / < 2s (LLM) | 分层策略 |
| Web API响应 | N/A | < 300ms (P50) | 异步 + 缓存 |
| 页面首屏加载 | N/A | < 2s | Streamlit懒加载 |
| 并发支持 | 单线程 | 100用户 | uvicorn多worker |
| DB查询 | N/A | < 50ms | 索引 + 连接池 |

---

## 四、ADR决策记录（Phase 3 新增）

### ADR-003: 选择FastAPI+Streamlit作为Web技术栈
**决策**：FastAPI后端 + Streamlit前端
**理由**：
- 开发速度快（Python全栈，无需前后端分离）
- FastAPI自带OpenAPI文档，便于调试
- Streamlit适合数据展示和对话式交互
- 团队熟悉度高
**替代方案**：FastAPI+React（更灵活但工期长）

### ADR-004: 采用SQLite/PostgreSQL双模式数据库
**决策**：开发环境SQLite，生产环境PostgreSQL
**理由**：
- SQLAlchemy ORM天然支持多数据库切换
- SQLite零配置，适合本地开发
- PostgreSQL适合生产环境并发和扩展
**替代方案**：仅PostgreSQL（开发需额外部署）

### ADR-005: LLM采用混合检测策略
**决策**：关键词匹配优先（快），LLM兜底（准）
**理由**：
- 关键词匹配 <100ms，满足80%常见case
- LLM处理复杂语义，提升边界case准确率
- 成本可控（仅20%请求走LLM）
**替代方案**：纯LLM（准但慢且贵）/ 纯关键词（快但不准）

---

## 五、部署架构

```
┌─────────────────────────────────────────────────────┐
│                  部署架构 (v3.0)                      │
│                                                     │
│  开发环境:                                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │Streamlit│→│ FastAPI │→│ SQLite  │           │
│  │ :8501   │  │ :8000   │  │ 文件DB   │           │
│  └─────────┘  └─────────┘  └─────────┘           │
│                                                     │
│  生产环境:                                          │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐          │
│  │Nginx    │→│uvicorn×4 │→│PostgreSQL│          │
│  │(反代+SSL)│  │(多Worker)│  │(主从复制) │          │
│  └─────────┘  └─────────┘  └──────────┘          │
│                      │                              │
│               ┌──────▼──────┐                      │
│               │ Redis(可选)  │                     │
│               │ 会话缓存     │                     │
│               └─────────────┘                     │
└─────────────────────────────────────────────────────┘
```

---

**文档状态**：✅ 初稿完成 | ⏳ 待产品经理确认需求覆盖完整性 | ⏳ 待测试专家评估可测试性 | ⏳ 待独立开发者评审可实现性 | ⏳ 待多角色共识

**下一步**：提交给测试专家制定测试计划
