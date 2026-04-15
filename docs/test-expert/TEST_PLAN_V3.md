# OPC-Agents 测试策略与计划 v3.0 (Phase 3)

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v3.0.0 | 2026-04-15 | 测试专家 | Phase 3测试：Web API / LLM集成 / DB持久化 / 适配器 / CI-CD | 待审核 |
| v2.1.0 | 2026-04-14 | 测试专家 | Phase 2测试：9场景+6人格+飞轮（27个新测试） | 已审核 |

---

## 一、测试范围总览

### 1.1 测试范围对比

```
v2.2.0 测试范围（65个测试）
├── Phase 1 单元测试 ............ 23个
├── Phase 1 集成测试 ............ 15个
└── Phase 2 扩展测试 ............ 27个
    总计: 65个 ✅ 全部通过

v3.0 新增测试范围（目标 +40~50 个）
├── Web API 测试 ................ 12-15个
│   ├── REST 接口请求/响应验证
│   ├── 认证与授权测试
│   └── 错误处理与边界条件
├── LLM 服务层测试 .............. 10-12个
│   ├── LLMBackend 抽象接口
│   ├── Mock/OpenAI/Ollama 后端
│   ├── 混合检测策略
│   └── Token 用量追踪
├── 数据持久化测试 ............... 10-12个
│   ├── ORM 模型 CRUD 操作
│   ├── FlywheelTrackerDB 读写
│   ├── 会话历史存储查询
│   └── 并发安全性与事务
├── 外部适配器测试 ............... 8-10个
│   ├── PlatformAdapter 基类
│   ├── MockXiaohongshuAdapter
│   ├── MockGumroadAdapter
│   └── 降级策略验证
├── E2E 端到端测试 ............... 5-8个
│   ├── Web界面完整用户旅程
│   └── 跨模块数据一致性
└── CI/CD Pipeline 测试 .......... 内嵌于YAML配置
    目标新增: ~45-57个
    总目标: 110-122个
```

### 1.2 测试金字塔（v3.0 更新）

```
                    /\
                   /  \     E2E Tests (~7%)
                  /────\    - Web UI 完整旅程
                 /  端到端 \  - 跨模块数据流
                /   测试    \
               /────────────\   Integration Tests (~23%)
              /   Web API    \  - REST 接口测试
             /   LLM 服务     \ - DB 交互测试
            /   持久化层       \ - 适配器 Mock 测试
           /────────────────────\
          /                        \
         /      Unit Tests           \  (~70%)
        /   - LLMService 各方法        \
       /    - DB Models CRUD            \
      /     - PlatformAdapter 基类       \
     /      - FlywheelTrackerDB 方法      \
    /───────────────────────────────────────\
```

---

## 二、Web API 测试用例

### 2.1 对话接口测试

```python
# tests/test_web_api.py
import pytest
from fastapi.testclient import TestClient
from web_app.main import app

client = TestClient(app)

class TestChatAPI:
    """对话API接口测试"""
    
    def test_send_message_basic(self):
        """基础消息发送"""
        response = client.post("/api/v1/chat/message", json={
            "message": "帮我规划下周的小红书内容",
            "user_id": "test_user_001",
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "detected_business_type" in data
        assert data["confidence"] > 0
    
    def test_send_message_empty_content(self):
        """空消息体应返回422"""
        response = client.post("/api/v1/chat/message", json={
            "message": "",
            "user_id": "test_user_001",
        })
        assert response.status_code == 422
    
    def test_send_message_too_long(self):
        """超长消息应被拒绝"""
        long_msg = "x" * 5001
        response = client.post("/api/v1/chat/message", json={
            "message": long_msg,
            "user_id": "test_user_001",
        })
        assert response.status_code == 422
    
    def test_send_message_missing_user_id(self):
        """缺少user_id应返回422"""
        response = client.post("/api/v1/chat/message", json={
            "message": "测试消息",
        })
        assert response.status_code == 422
    
    def test_explicit_business_type(self):
        """显式指定业务类型"""
        response = client.post("/api/v1/chat/message", json={
            "message": "随便聊聊",
            "user_id": "test_user_001",
            "explicit_business_type": "ecommerce",
        })
        assert response.status_code == 200
        assert response.json()["detected_business_type"] == "ecommerce"
    
    def test_six_types_all_detectable(self):
        """6种业务类型均可正确检测"""
        test_cases = [
            ("帮我规划小红书选题", "content_creator"),
            ("帮我把课程打包上架", "digital_product"),
            ("分析一下用户反馈", "ai_tool_builder"),
            ("起草数字化转型方案", "consultant"),
            ("分析上周销售数据", "ecommerce"),
            ("整理设计项目交付物", "creative_work"),
        ]
        for msg, expected_type in test_cases:
            resp = client.post("/api/v1/chat/message", json={
                "message": msg,
                "user_id": f"user_{expected_type}",
            })
            assert resp.json()["detected_business_type"] == expected_type, f"Failed for {msg}"

class TestHistoryAPI:
    """会话历史接口测试"""
    
    def test_get_history_empty(self):
        """空会话列表"""
        response = client.get("/api/v1/chat/history?session_id=nonexistent&limit=50")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_history_pagination(self):
        """分页参数校验"""
        response = client.get("/api/v1/chat/history?session_id=test&limit=1000")
        assert response.status_code == 200
    
    def test_delete_session(self):
        """删除会话"""
        response = client.delete("/api/v1/chat/sessions/test_session_001")
        assert response.status_code in [200, 204, 404]

class TestHealthAPI:
    """健康检查接口测试"""
    
    def test_health_check(self):
        """系统健康检查"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
```

### 2.2 认证与中间件测试

```python
class TestAuthMiddleware:
    """认证中间件测试"""
    
    def test_unauthenticated_request(self):
        """未认证请求应返回401（如果启用认证）"""
        pass
    
    def test_rate_limiting(self):
        """限流测试：超过阈值应返回429"""
        for i in range(105):
            response = client.get("/api/v1/health")
        
        if response.status_code == 429:
            assert "retry_after" in response.headers or "Retry-After" in response.headers
```

---

## 三、LLM服务层测试

### 3.1 LLMBackend 抽象测试

```python
# tests/test_llm_service.py
import pytest
from opc_manager.llm_service import (
    LLMService, LLMConfig, LLMProvider, 
    MockLLMBackend, UsageTracker
)
import asyncio

class TestMockLLMBackend:
    """Mock后端测试"""
    
    @pytest.fixture
    def mock_backend(self):
        return MockLLMBackend(LLMConfig(provider=LLMProvider.MOCK))
    
    @pytest.mark.asyncio
    async def test_complete_returns_valid_response(self, mock_backend):
        """完成调用返回有效响应"""
        response = await mock_backend.complete("测试输入")
        assert response.content is not None
        assert len(response.content) > 0
        assert response.provider == LLMProvider.MOCK
        assert response.latency_ms >= 0
    
    @pytest.mark.asyncio
    async def test_detect_type_prompt(self, mock_backend):
        """检测类型Prompt返回JSON格式"""
        response = await mock_backend.complete("detect this type: 我写小红书笔记")
        import json
        try:
            parsed = json.loads(response.content)
            assert "business_type" in parsed
            assert "confidence" in parsed
        except json.JSONDecodeError:
            pytest.fail("Detect prompt should return valid JSON")
    
    @pytest.mark.asyncio
    async def test_latency_range(self, mock_backend):
        """模拟延迟在合理范围内（50-200ms）"""
        response = await mock_backend.complete("latency test")
        assert 50 <= response.latency_ms <= 200
    
    def test_validate_config(self, mock_backend):
        """Mock配置始终有效"""
        assert mock_backend.validate_config() is True

class TestLLMService:
    """LLM服务统一入口测试"""
    
    @pytest.fixture
    def llm_service(self):
        return LLMService(LLMConfig(provider=LLMProvider.MOCK))
    
    @pytest.mark.asyncio
    async def test_detect_by_llm_returns_dict(self, llm_service):
        """LLM检测返回字典格式"""
        result = await llm_service.detect_business_type_by_llm(
            "我是一个做自媒体的博主"
        )
        assert isinstance(result, dict)
        assert "business_type" in result
        assert "confidence" in result
    
    @pytest.mark.asyncio
    async def test_detect_all_six_types(self, llm_service):
        """6种类型都能通过LLM识别"""
        inputs = [
            ("写文章拍视频", "content_creator"),
            ("卖电子书课程", "digital_product"),
            ("开发SaaS工具", "ai_tool_builder"),
            ("企业培训咨询", "consultant"),
            ("电商卖货运营", "ecommerce"),
            ("UI设计摄影", "creative_work"),
        ]
        for text, expected in inputs:
            result = await llm_service.detect_business_type_by_llm(text)
            assert result["business_type"] == expected, f"Failed: {text} → {result}"
    
    @pytest.mark.asyncio
    async def test_persona_response_generation(self, llm_service):
        """人格风格回复生成"""
        persona_config = {
            "display_name": "内容小助理",
            "style_overrides": {"tone": "轻松活泼"},
            "expertise_tags": ["内容趋势", "平台算法"],
        }
        response = await llm_service.generate_persona_response(
            "今天有什么热点？", persona_config
        )
        assert isinstance(response, str)
        assert len(response) > 5
    
    def test_switch_provider(self, llm_service):
        """动态切换后端"""
        original_provider = llm_service.config.provider
        llm_service.switch_provider(LLMProvider.MOCK)
        assert llm_service.config.provider == LLMProvider.MOCK

class TestUsageTracker:
    """用量追踪器测试"""
    
    def test_record_usage(self):
        """记录使用量"""
        tracker = UsageTracker(daily_budget=10.0)
        tracker.record({"total_tokens": 100, "cost": 0.01})
        today = tracker.get_report().get(__import__("datetime").datetime.now().strftime("%Y-%m-%d"), {})
        assert today["tokens"] == 100
        assert today["calls"] == 1
    
    def test_budget_exceeded(self):
        """预算超限检测"""
        tracker = UsageTracker(daily_budget=0.01)
        tracker.record({"total_tokens": 1000, "cost": 0.02})
        assert tracker.is_budget_exceeded() is True
    
    def test_budget_not_exceeded(self):
        """预算未超限"""
        tracker = UsageTracker(daily_budget=100.0)
        tracker.record({"total_tokens": 100, "cost": 0.001})
        assert tracker.is_budget_exceeded() is False
```

---

## 四、数据持久化测试

### 4.1 ORM模型测试

```python
# tests/test_db_models.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_models.models import Base, User, FlywheelState, Conversation, Message

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

class TestUserModel:
    """User模型CRUD测试"""
    
    def test_create_user(self, db_session):
        user = User(id="user_001", username="test_user", primary_business_type="content_creator")
        db_session.add(user)
        db_session.commit()
        
        fetched = db_session.query(User).filter_by(id="user_001").first()
        assert fetched is not None
        assert fetched.username == "test_user"
        assert fetched.primary_business_type == "content_creator"
    
    def test_unique_username(self, db_session):
        db_session.add(User(id="u1", username="dup"))
        db_session.commit()
        
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            db_session.add(User(id="u2", username="dup"))
            db_session.commit()

class TestFlywheelStateModel:
    """FlywheelState模型测试"""
    
    def test_create_flywheel_state(self, db_session):
        user = User(id="user_002", username="flywheel_test")
        db_session.add(user)
        db_session.flush()
        
        state = FlywheelState(
            user_id="user_002",
            current_level=1,
            active_types=["content_creator"],
            health_score=45.5,
            dimension_scores={"content_quality": 60.0, "audience_growth": 40.0},
            total_scenarios_completed=5,
            achievements=["first_step"],
        )
        db_session.add(state)
        db_session.commit()
        
        fetched = db_session.query(FlywheelState).filter_by(user_id="user_002").first()
        assert fetched.current_level == 1
        assert fetched.health_score == 45.5
        assert "first_step" in fetched.achievements
    
    def test_json_fields_persistence(self, db_session):
        """JSON字段正确序列化和反序列化"""
        user = User(id="user_003", username="json_test")
        db_session.add(user)
        db_session.flush()
        
        complex_data = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }
        state = FlywheelState(user_id="user_003", metadata_json=complex_data)
        db_session.add(state)
        db_session.commit()
        
        fetched = db_session.query(FlywheelState).filter_by(user_id="user_003").first()
        assert fetched.metadata_json == complex_data

class TestConversationAndMessage:
    """会话和消息模型测试"""
    
    def test_conversation_with_messages(self, db_session):
        user = User(id="user_004", username="conv_test")
        db_session.add(user)
        db_session.flush()
        
        conv = Conversation(id="conv_001", user_id="user_004", title="测试对话")
        db_session.add(conv)
        db_session.flush()
        
        msg1 = Message(
            conversation_id="conv_001",
            role="user",
            content="帮我规划内容日历",
            business_type="content_creator",
        )
        msg2 = Message(
            conversation_id="conv_001",
            role="assistant",
            content="好的！让我分析一下热点...",
            persona_variant="content_creator",
            confidence=0.92,
        )
        db_session.add_all([msg1, msg2])
        db_session.commit()
        
        messages = db_session.query(Message).filter_by(conversation_id="conv_001").all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].persona_variant == "content_creator"
```

### 4.2 FlywheelTrackerDB 测试

```python
# tests/test_flywheel_tracker_db.py
import pytest
from opc_manager.flywheel_tracker import FlywheelTrackerDB
from db_models.models import Base, FlywheelState
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def tracker_with_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    tracker = FlywheelTrackerDB(db_session=session, engine=engine)
    yield tracker, session
    session.close()

class TestFlywheelTrackerPersistence:
    """飞轮追踪器持久化测试"""
    
    def test_initial_state_created_in_db(self, tracker_with_db):
        tracker, session = tracker_with_db
        state = tracker._load_from_db("new_user")
        
        db_state = session.query(FlywheelState).filter_by(user_id="new_user").first()
        assert db_state is not None
        assert db_state.current_level == 1
    
    def test_scenario_completion_persisted(self, tracker_with_db):
        tracker, _ = tracker_with_db
        tracker.record_scenario_completion("user_persist", "content_calendar", "content_creator")
        
        db_state = _.query(FlywheelState).filter_by(user_id="user_persist").first()
        assert db_state.total_scenarios_completed == 1
    
    def test_level_upgrade_persisted(self, tracker_with_db):
        tracker, _ = tracker_with_db
        
        for i in range(12):
            tracker.record_scenario_completion(f"user_lv{i}", f"scenario_{i}", "content_creator")
            if i < 11:
                tracker.record_scenario_completion(f"user_lv{i}", f"scenario_{i}_alt", "digital_product")
        
        state = tracker.get_flywheel_state("user_lv11")
        assert state.current_level.value == 2
    
    def test_restart_preserves_data(self, tracker_with_db):
        """重启后数据不丢失"""
        tracker, session = tracker_with_db
        tracker.record_scenario_completion("persist_test", "content_calendar", "content_creator")
        
        new_tracker = FlywheelTrackerDB(db_session=session, engine=None)
        state = new_tracker.get_flywheel_state("persist_test")
        assert state.total_scenarios_completed == 1
```

---

## 五、外部适配器测试

```python
# tests/test_platform_adapters.py
import pytest
from opc_manager.platform_adapters import (
    PlatformType, PlatformAdapter, MockXiaohongshuAdapter,
    MockGumroadAdapter, AdapterFactory
)
import asyncio

class TestPlatformAdapterBase:
    """适配器基类接口测试"""
    
    def test_xiaohongshu_adapter_type(self):
        adapter = MockXiaohongshuAdapter()
        assert adapter.platform_type == PlatformType.XIAOHONGSHU
    
    def test_gumroad_adapter_type(self):
        adapter = MockGumroadAdapter()
        assert adapter.platform_type == PlatformType.GUMROAD

class TestMockXiaohongshuAdapter:
    """小红书Mock适配器测试"""
    
    @pytest.fixture
    def xhs_adapter(self):
        return MockXiaohongshuAdapter()
    
    @pytest.mark.asyncio
    async def test_fetch_hot_topics_default(self, xhs_adapter):
        """默认获取10条热点"""
        topics = await xhs_adapter.fetch_hot_topics(limit=10)
        assert len(topics) == 10
        for topic in topics:
            assert "title" in topic
            assert "heat" in topic
            assert "category" in topic
    
    @pytest.mark.asyncio
    async def test_fetch_hot_topics_filtered(self, xhs_adapter):
        """按分类过滤"""
        topics = await xhs_adapter.fetch_hot_topics(category="时尚", limit=5)
        for topic in topics:
            assert topic["category"] == "时尚"
    
    @pytest.mark.asyncio
    async def test_fetch_user_data(self, xhs_adapter):
        """获取用户数据"""
        data = await xhs_adapter.fetch_user_data({"cookie": "test"})
        assert "followers" in data
        assert "notes_count" in data
        assert data["followers"] > 0
    
    def test_validate_credentials_mock(self, xhs_adapter):
        """Mock模式凭据始终有效"""
        ok, msg = xhs_adapter.validate_credentials({})
        assert ok is True

class TestMockGumroadAdapter:
    """Gumroad Mock适配器测试"""
    
    @pytest.fixture
    def gumroad_adapter(self):
        return MockGumroadAdapter()
    
    @pytest.mark.asyncio
    async def test_fetch_sales_data(self, gumroad_adapter):
        """获取销售数据"""
        data = await gumroad_adapter.fetch_user_data({"token": "test"})
        assert "total_sales" in data
        assert "products_count" in data
        assert data["products_count"] >= 1

class TestAdapterFactory:
    """适配器工厂测试"""
    
    def test_get_mock_adapter(self):
        """获取Mock适配器"""
        adapter = AdapterFactory.get_adapter(PlatformType.XIAOHONGSHU, use_mock=True)
        assert isinstance(adapter, MockXiaohongshuAdapter)
    
    def test_real_adapter_not_implemented(self):
        """真实适配器未实现时抛出异常"""
        with pytest.raises(NotImplementedError):
            AdapterFactory.get_adapter(PlatformType.XIAOHONGSHU, use_mock=False)
    
    def test_caching(self):
        """适配器实例缓存"""
        a1 = AdapterFactory.get_adapter(PlatformType.GUMROAD)
        a2 = AdapterFactory.get_adapter(PlatformType.GUMROAD)
        assert a1 is a2
```

---

## 六、CI/CD Pipeline YAML

```yaml
# .github/workflows/ci-cd-v3.yml
name: OPC-Agents V3.0 CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:

env:
  PYTHON_VERSION: "3.10"

jobs:
  unit-tests:
    name: 单元测试
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio httpx
      
      - name: Run Phase 1+2 regression tests
        run: pytest tests/ -v --cov=opc_manager --cov-report=xml --tb=short
      
      - name: Run Phase 3 new tests
        run: pytest tests/test_web_api.py tests/test_llm_service.py tests/test_db_models.py tests/test_platform_adapters.py tests/test_flywheel_tracker_db.py -v --tb=short
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: unittests

  integration-tests:
    name: 集成测试
    needs: unit-tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: opc_agents_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U test"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run DB integration tests
        env:
          DATABASE_URL: postgresql://test:test@localhost/opc_agents_test
        run: pytest tests/integration/ -v --db-url=$DATABASE_URL --tb=short
      
      - name: Run API integration tests
        run: pytest tests/e2e/ -v -k "api" --tb=short

  code-quality:
    name: 代码质量检查
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install linters
        run: pip install flake8 mypy bandit black isort
      
      - name: Flake8 lint
        run: flake8 opc_manager/ web_app/ db_models/ --count --select=E9,F63,F7,F82 --show-source --statistics
      
      - name: Black format check
        run: black --check opc_manager/ web_app/
      
      - name: Bandit security scan
        run: bandit -r opc_manager/ -ll
  
  performance-benchmark:
    name: 性能基准测试
    needs: [unit-tests, integration-tests]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: pip install -r requirements.txt pytest-benchmark
      
      - name: Run benchmarks
        run: pytest tests/performance/ -v --benchmark-json=benchmark.json
      
      - name: Check regression
        run: python scripts/check_performance_regression.py benchmark.json || echo "Performance check completed"

  auto-release:
    name: 自动发布
    needs: [unit-tests, integration-tests, code-quality]
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Generate Changelog
        run: |
          echo "## Release $(git describe --tags)" > RELEASE_NOTES.md
          git log $(git describe --tags --abbrev=0)^..HEAD --pretty=format:"- %s (%an)" >> RELEASE_NOTES.md
      
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          body_path: RELEASE_NOTES.md
          files: |
            README.md
```

---

## 七、覆盖率目标

| 模块 | v2.2.0 覆盖率 | v3.0 目标 | 差距 | 新增测试数 |
|------|---------------|-----------|------|-----------|
| `scenario_engine_v2` | ~85% | 85% | - | 0（稳定） |
| `business_type_detector_v2` | ~90% | 90% | - | 0（稳定） |
| `flywheel_tracker` | ~80% | 88% | +8% | +8（DB扩展） |
| `persona_manager` | ~75% | 80% | +5% | +3（Web集成） |
| `llm_service` | N/A | 85% | 新增 | +12 |
| `web_app/routes` | N/A | 85% | 新增 | +15 |
| `db_models/models` | N/A | 90% | 新增 | +10 |
| `platform_adapters` | N/A | 85% | 新增 | +10 |
| **Overall** | **~82%** | **≥87%** | **+5%** | **+~58** |

---

## 八、回归测试策略

### 8.1 回归保护规则

```
Phase 3 开发期间必须遵守：

1. 每次代码提交前运行全量测试
2. Phase 1 的 23 个单元测试必须全部通过 ✅
3. Phase 1 的 15 个集成测试必须全部通过 ✅
4. Phase 2 的 27 个扩展测试必须全部通过 ✅
5. 新增测试必须全部通过 ✅
6. 总测试数 ≥ 110，总覆盖率 ≥ 87%

违反任何一条 → PR 不能合并
```

### 8.2 回归测试执行计划

| 触发时机 | 执行范围 | 通过标准 |
|---------|---------|---------|
| 每次 PR | 全量测试（110+） | 100% 通过 |
| 每日定时 | 全量 + 性能基准 | 100% 通过 + 无性能退化 |
| 发布前 | 全量 + 安全扫描 + E2E | 100% 通过 + 0 Critical |

---

**文档状态**：✅ 初稿完成 | ⏳ 待独立开发者评审可实现性 | ⏳ 待产品经理确认覆盖完整性 | ⏳ 待多角色共识

**下一步**：提交给独立开发者制定开发路线图
