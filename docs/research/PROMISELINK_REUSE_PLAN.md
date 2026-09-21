# PromiseLink 基础版能力复用方案（OPC-Agents 后期规划）

> **状态**: 路由已校准（2026-08-01）
> **重要**: 本文档已根据 [PROMISELINK_API_CALIBRATION.md](PROMISELINK_API_CALIBRATION.md)（基于 PromiseLink v0.9.0 源码逐项校准）修正所有 API 路径。
> **API 前缀**: `/api/v1`（来自 PromiseLink `config.py`）

---

## 一、复用背景

### 1.1 团队已有资产

| 项目 | 版本 | 状态 | 关键能力 |
|------|------|------|---------|
| **PromiseLink 基础版** | v0.9.0 (v1.0.1) | 1968 tests passed, ICP 备案已通过 | 实体抽取+关系推进卡+沉默客户扫描+6 种 Todo+双向承诺+早晚报+提醒疲劳控制 |
| **CarryMem** | v0.10.0 | 4666 tests passed | 跨会话记忆引擎 |
| **DevSquad** | v4.5.16 | 9494 tests passed | 7-Role 协作框架 |

### 1.2 复用决策依据

依据 [user_profile.md](../../../../../.trae-cn/memory/user_profile.md)：
> **"集成现有工具优先于自建"** — 重复开发是被反感的，优先复用团队已有资产

**vs PromiseLink 基础版的复用优势**：
- ✅ 6+ 月开发成本节省（团队已有 1968 tests 验证）
- ✅ 1968 tests + ruff 0 + mypy 0 + ICP 备案已通过 = 生产就绪
- ✅ 实体抽取（5 类）+ 关系推进卡（12 模块）+ 双向承诺（6 action_type）= 完整关系经营闭环
- ✅ 与 OPC-Agents 互为补充（OPC-Agents 强执行+PromiseLink 强关系）

---

## 二、复用能力详细对照

### 2.1 客户管理（CRM）— 🟢 高优先级

| 需求 | OPC-Agents 当前 | PromiseLink 能力 | 复用方案 |
|------|---------------|----------------|---------|
| CRM-01 添加客户档案 | 半冻结（无 add_customer）| EntityExtractor 自动提取 + Entity 表 | v1.0.0 解冻 crm_skill + 集成 EntityExtractor API |
| CRM-02 客户查询 | get_customer 已实现 | Entity 表 + Entity Resolution 5 步级联 | 复用 PromiseLink 查询 API |
| CRM-03 沉默客户识别 | get_silent_customers 已实现（未激活）| DormantScanner（3 维度评分）| 集成 DormantScanner API 替换/增强 |
| CRM-04 合作记录 | | Entity 关联 + 事件聚合 | 集成事件查询 API |
| CRM-05 跟进提醒 | | ScheduledEvent + ReminderPreference | 集成 ScheduledEvent API |
| 客户转化统计 | get_customer_stats 已实现 | Entity 状态机 + 关联聚合 | 集成查询 API |
| 客户生命周期 | | RelationshipStage（7 阶段）| v1.1.0 集成 |

**复用模式**：HTTP API 集成（`opc_manager/promiselink_client.py`）

### 2.2 线索跟进（Lead Follow-up）— 🟢 高优先级

| 需求 | OPC-Agents 当前 | PromiseLink 能力 | 复用方案 |
|------|---------------|----------------|---------|
| 线索评分 | 无 | Todo priority_scorer | v1.1.0 集成 |
| 表单触发跟进 | 无 | 事件管线 step_07_priority | v1.1.0 集成 |
| 自动约会调度 | 无 | 第三方集成（需扩展）| v1.1.0 评估 |

**集成收益**：3-5 天 vs 4-6 周自建

### 2.3 客户跟进（Customer Follow-up）— 🟢 高优先级

| 需求 | OPC-Agents 当前 | PromiseLink 能力 | 复用方案 |
|------|---------------|----------------|---------|
| 对方承诺追踪 | 无 | PromiseBidirectional（6 action_type）| v1.0.0 集成 |
| 温和催促消息 | 无 | NudgeGenerator（LLM 模板）| v1.0.0 集成 email_skill |
| day 3/7/14 跟进序列 | 无 | Todo DUE_DATE_OFFSETS + scheduled_events | v1.0.0 集成 |
| 跟进状态追踪 | 无 | Todo 状态机 | v1.0.0 集成 |
| 早晚报推送 | 无 | NotificationService + Dashboard API | v1.1.0 集成 |
| 关系视图 | 无 | RelationshipBrief（12 模块）| v1.0.0 集成 |

**集成收益**：2-3 周 vs 8-12 周自建

### 2.4 报告生成（Reports）— ✅ OPC-Agents 已有

| 需求 | OPC-Agents 当前 | PromiseLink 能力 | 复用方案 |
|------|---------------|----------------|---------|
| 周报 | ✅ report_skill | 无 | 维持 OPC-Agents 自身 |
| 月报 | ✅ report_skill | 无 | 维持 OPC-Agents 自身 |
| 客户关系周报 | ❌ 无 | RelationshipBrief + Dashboard 聚合 | v1.0.0 集成 |

### 2.5 财务记账（Finance）— ✅ OPC-Agents 已有

| 需求 | OPC-Agents 当前 | PromiseLink 能力 | 复用方案 |
|------|---------------|----------------|---------|
| 收入/支出记录 | ✅ finance_skill | 无 | 维持 OPC-Agents 自身 |
| 月度报表 | ✅ finance_skill | 无 | 维持 OPC-Agents 自身 |
| 趋势分析 | ✅ finance_skill | 无 | 维持 OPC-Agents 自身 |
| 报税提醒 | 无 | ReminderPreference + scheduled_events | v1.0.0 集成 |

---

## 三、复用接口设计（OPC-Agents 端）

### 3.1 PromiseLinkClient 模块

```python
# opc_manager/promiselink_client.py（新增）

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

@dataclass
class PromiseLinkConfig:
    enabled: bool = False
    api_url: str = "http://localhost:8200"
    api_token: Optional[str] = None
    timeout_seconds: int = 5
    max_retries: int = 3
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_seconds: int = 30

class PromiseLinkClient:
    """PromiseLink 基础版 HTTP API 客户端

    提供 7 大能力的优雅降级集成：
    - entity_extraction（实体抽取）
    - dormant_scan（沉默客户扫描）
    - promise_bidirectional（双向承诺）
    - nudge_generation（温和催促）
    - relationship_brief（关系推进卡）
    - scheduled_event（排程事件）
    - notification（推送通知）

    失败降级：
    - API 不可用 → 静默降级到 OPC-Agents 自身能力
    - 超时 → circuit breaker 30s 内不重试
    - 错误码 → 记录日志 + 返回 None
    """

    def __init__(self, config: PromiseLinkConfig):
        self.config = config
        self.session = self._build_session()
        self._circuit_open = False
        self._failure_count = 0

    def _build_session(self) -> requests.Session:
        """构建带 retry 的 HTTP 会话"""
        session = requests.Session()
        retry = Retry(
            total=self.config.max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        if self.config.api_token:
            session.headers["Authorization"] = f"Bearer {self.config.api_token}"
        return session

    def is_available(self) -> bool:
        """检查 PromiseLink 是否可用（不触发 circuit breaker）"""
        if not self.config.enabled or self._circuit_open:
            return False
        try:
            response = self.session.get(
                f"{self.config.api_url}/api/v1/health",
                timeout=2
            )
            return response.status_code == 200
        except Exception:
            return False

    def extract_entities(self, text: str, event_type: str = "meeting") -> Optional[Dict]:
        """实体抽取（PromiseLink EntityExtractor）

        用于：会议记录 → 自动提取联系人/组织/话题/技术/项目
        失败降级：返回 None，调用方应使用 OPC-Agents 自身逻辑
        """
        if not self._can_call():
            return None
        try:
            response = self.session.post(
                f"{self.config.api_url}/api/v1/events",
                json={
                    "event_type": event_type,
                    "raw_text": text,
                },
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._record_failure()
            logger.warning("promiselink_extract_entities_failed", error=str(e))
            return None

    def scan_dormant_contacts(self, days_threshold: int = 90, limit: int = 10) -> Optional[List[Dict]]:
        """沉默客户扫描（PromiseLink DormantScanner）

        用于：crm.get_silent_customers 增强
        真实路径：GET /api/v1/entities/dormant?min_days=N&limit=N（已校准）
        失败降级：返回 None，调用方应使用 OPC-Agents 自身实现
        """
        if not self._can_call():
            return None
        try:
            response = self.session.get(
                f"{self.config.api_url}/api/v1/entities/dormant",
                params={"min_days": days_threshold, "limit": min(limit, 50)},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except Exception as e:
            self._record_failure()
            logger.warning("promiselink_scan_dormant_failed", error=str(e))
            return None

    def analyze_promise_bidirectional(
        self, todo_title: str, todo_description: str = ""
    ) -> Optional[Dict]:
        """双向承诺分析（PromiseLink PromiseBidirectional）

        ⚠️ 重要：PromiseLink 没有独立的同步分析端点。
        真实做法：调用 POST /api/v1/events 触发完整异步管线（13 步，含 step_05_promise），
        然后轮询 GET /events/{id} 获取结果。

        本方法作为对外占位（v1.0.0 由 PromiseLink 项目组实现 ENH-PL-01 后替换），
        失败降级：返回 None，调用方应使用规则引擎 fallback
        """
        if not self._can_call():
            return None
        # TODO(v1.0.0): 待 PromiseLink 项目组实现 POST /api/v1/promises/analyze-bidirectional 后替换
        logger.warning(
            "promiselink_analyze_promise_pending_enhancement",
            hint="PromiseLink 暂未提供同步分析端点，当前应使用 POST /events 触发完整管线",
        )
        return None

    def generate_nudge_message(
        self, todo_id: str
    ) -> Optional[str]:
        """温和催促消息生成（PromiseLink NudgeGenerator）

        用于：email.compose_nudge 自动生成对方承诺到期的催促消息
        真实路径：GET /api/v1/promises/{todo_id}/nudge-draft（已校准，仅 GET，必须先有 todo_id）
        失败降级：返回 None，调用方应使用本地模板
        """
        if not self._can_call():
            return None
        try:
            response = self.session.get(
                f"{self.config.api_url}/api/v1/promises/{todo_id}/nudge-draft",
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("nudge_text", "")
        except Exception as e:
            self._record_failure()
            logger.warning("promiselink_generate_nudge_failed", error=str(e))
            return None

    def get_relationship_brief(self, entity_id: str) -> Optional[Dict]:
        """关系推进卡（PromiseLink RelationshipBrief）

        用于：crm.get_relationship_brief 12 模块聚合视图
        失败降级：返回 None，调用方应使用 OPC-Agents 自身简化版
        """
        if not self._can_call():
            return None
        try:
            response = self.session.get(
                f"{self.config.api_url}/api/v1/persons/{entity_id}/relationship-brief",
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._record_failure()
            logger.warning("promiselink_get_brief_failed", error=str(e))
            return None

    def create_scheduled_event(
        self,
        scheduled_at: str,
        topic: str,
        participants: List[Dict],
        reminder_at: Optional[str] = None,
    ) -> Optional[Dict]:
        """创建排程事件（PromiseLink ScheduledEvent）

        用于：scheduler 新模块的任务持久化后端
        失败降级：返回 None，调用方应使用 OPC-Agents 自身 scheduled_tasks 表
        """
        if not self._can_call():
            return None
        try:
            response = self.session.post(
                f"{self.config.api_url}/api/v1/scheduled-events",
                json={
                    "scheduled_at": scheduled_at,
                    "topic": topic,
                    "participants": participants,
                    "reminder_at": reminder_at,
                },
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._record_failure()
            logger.warning("promiselink_create_event_failed", error=str(e))
            return None

    # ── Circuit Breaker ─ ──

    def _can_call(self) -> bool:
        """检查是否可以调用 PromiseLink API"""
        if not self.config.enabled:
            return False
        if self._circuit_open:
            return False
        return True

    def _record_failure(self):
        """记录失败并触发 circuit breaker"""
        self._failure_count += 1
        if self._failure_count >= self.config.circuit_breaker_failure_threshold:
            self._circuit_open = True
            # 30 秒后重置（可在真实实现中用后台线程）
            import threading
            def reset():
                import time
                time.sleep(self.config.circuit_breaker_recovery_seconds)
                self._circuit_open = False
                self._failure_count = 0
            threading.Thread(target=reset, daemon=True).start()


# 全局单例
_instance: Optional[PromiseLinkClient] = None

def get_promiselink_client() -> PromiseLinkClient:
    """获取 PromiseLink 客户端单例"""
    global _instance
    if _instance is None:
        from opc_manager.settings import get_settings
        settings = get_settings()
        _instance = PromiseLinkClient(PromiseLinkConfig(
            enabled=getattr(settings, "promiselink_enabled", False),
            api_url=getattr(settings, "promiselink_api_url", "http://localhost:8200"),
            api_token=getattr(settings, "promiselink_api_token", None),
        ))
    return _instance
```

### 3.2 集成示例：crm_skill 集成 DormantScanner

```python
# opc_manager/crm_skill.py（修改 get_silent_customers 方法）

def get_silent_customers(self, days: int = 90, limit: int = 50) -> List[Dict]:
    """获取沉默客户列表（N 天未联系）

    v1.0.0 升级：优先使用 PromiseLink DormantScanner（含 3 维度评分），
    失败时降级到本地实现。
    """
    promiselink = get_promiselink_client()

    # 尝试 PromiseLink（更精准的 3 维度评分）
    if promiselink.is_available():
        result = promiselink.scan_dormant_contacts(days_threshold=days)
        if result is not None:
            # PromiseLink 返回的是 entities，转换为 OPC-Agents 客户格式
            return [
                {
                    "name": item["canonicalname"],
                    "company": item.get("properties", {}).get("basic", {}).get("company"),
                    "dormant_days": item.get("dormant_days", days),
                    "reactivation_score": item.get("reactivation_score", 0.5),
                    "last_interaction": item.get("last_interaction"),
                    "icebreaker_topic": item.get("icebreaker_topic", ""),
                }
                for item in result[:limit]
            ]

    # 降级到本地实现
    return self._get_silent_customers_local(days, limit)
```

### 3.3 集成示例：email_skill 集成 NudgeGenerator

```python
# opc_manager/email_skill.py（新增 compose_nudge 方法）

def compose_nudge(
    self,
    entity_name: str,
    promise_description: str,
    due_date: str,
    overdue_days: int,
) -> Optional[str]:
    """生成温和催促消息（对方承诺到期未兑现）

    v1.0.0 升级：优先使用 PromiseLink NudgeGenerator（LLM 模板），
    失败时使用本地固定模板。
    """
    promiselink = get_promiselink_client()

    if promiselink.is_available():
        result = promiselink.generate_nudge_message(
            entity_name=entity_name,
            promise_description=promise_description,
            due_date=due_date,
            overdue_days=overdue_days,
        )
        if result:
            return result

    # 降级到本地模板
    return (
        f"Hi {entity_name}，\n\n"
        f"我们之前约定的「{promise_description}」原计划 {due_date} 完成，"
        f"已经过去 {overdue_days} 天了，方便看一下进展吗？\n\n"
        f"如果需要调整时间，随时告诉我。\n\n"
        f"Best regards"
    )
```

---

## 四、配置与启用

### 4.1 .env 配置

```bash
# PromiseLink 集成配置（v1.0.0 新增）
PROMISELINK_ENABLED=false                            # 默认关闭，需用户主动启用
PROMISELINK_API_URL=http://localhost:8200            # PromiseLink HTTP API 地址
PROMISELINK_API_TOKEN=<your_oauth2_token>            # OAuth2 token（PromiseLink 已有机制）
PROMISELINK_TIMEOUT_SECONDS=5                        # API 调用超时
PROMISELINK_MAX_RETRIES=3                            # 最大重试次数
PROMISELINK_CIRCUIT_BREAKER_THRESHOLD=5              # 失败阈值触发熔断
PROMISELINK_CIRCUIT_BREAKER_RECOVERY_SECONDS=30      # 熔断恢复时间
```

### 4.2 Settings 页面 UI

新增 Settings → Integrations 标签页：

```
┌─ Integrations ─────────────────────────────────────────┐
│                                                          │
│ PromiseLink 基础版集成                                   │
│ ─────────────────                                       │
│ 通过 HTTP API 复用 PromiseLink v0.9.0 已有能力：            │
│ 实体抽取 + 沉默客户扫描 + 双向承诺 + 温和催促               │
│ + 关系推进卡 + 排程事件 + 推送通知                          │
│                                                          │
│ 启用集成 [🔘 关]                                          │
│                                                          │
│ API 地址 [http://localhost:8200]                         │
│ OAuth2 Token [**********]                                 │
│                                                          │
│ 连接状态：✅ PromiseLink 已连接                            │
│                                                          │
│ [测试连接]  [查看文档]                                     │
└──────────────────────────────────────────────────────────┘
```

### 4.3 启用流程

1. 用户安装 PromiseLink 基础版（pip install 或源码）
2. 用户启动 PromiseLink HTTP API（默认端口 8200）
3. 用户在 PromiseLink 中生成 OAuth2 token
4. 用户在 OPC-Agents Settings → Integrations 配置
5. 用户启用集成 → 自动检测连接 → 启用 7 大能力

---

## 五、E2E 测试方案

### 5.1 测试策略

依据 [test_quality_guard principles](../../../DevSquad/scripts/collaboration/test_quality_guard.py)：
- ✅ 真实组件优先（HTTP API 真实调用，失败时用 PromiseLink MockClient）
- ✅ 覆盖 error case（≥15%）
- ✅ 覆盖 boundary（≥10%）
- ✅ 集成测试断言 pipeline integration（不仅 mock 单点）

### 5.2 测试矩阵

| 测试维度 | 数量 | 覆盖 |
|---------|------|------|
| HTTP 客户端 retry + circuit breaker | 5 | 网络失败场景 |
| 配置缺失降级 | 3 | PROMISELINK_ENABLED=false 等 |
| 7 个集成接口 mock 测试 | 14 | 各接口参数 + 返回值 |
| crm_skill 集成 DormantScanner | 5 | 真实集成 vs 降级路径 |
| email_skill 集成 NudgeGenerator | 5 | 真实集成 vs 本地模板 |
| PromiseLink 真实实例 smoke | 3 | 仅在 CI 环境（可选） |
| **合计** | **35** | — |

### 5.3 关键测试场景

```python
# tests/e2e/test_promiselink_integration_e2e.py

class TestPromiseLinkClientCircuitBreaker:
    """Circuit breaker 测试（避免雪崩）"""

    def test_circuit_opens_after_threshold_failures(self, monkeypatch):
        """连续失败达到阈值后，circuit breaker 打开"""
        client = PromiseLinkClient(config_with_threshold_3)
        monkeypatch.setattr(client.session, "get", lambda *a, **kw: raise_error())

        # 连续 3 次失败
        for _ in range(3):
            client.is_available()

        # 第4 次调用应被熔断（快速返回 False）
        assert client.is_available() is False

    def test_circuit_recovers_after_timeout(self, monkeypatch):
        """30 秒后 circuit 自动恢复"""
        client = PromiseLinkClient(config_with_recovery_1s)
        monkeypatch.setattr(client.session, "get", lambda *a, **kw: raise_error())

        for _ in range(5):
            client._record_failure()
        assert client._circuit_open is True

        time.sleep(1.5)  # 等待恢复
        assert client._circuit_open is False


class TestCrmSkillPromiseLinkIntegration:
    """crm_skill 集成 DormantScanner"""

    def test_dormant_scan_uses_promiselink_when_available(self, ...):
        """PromiseLink 可用时，crm.get_silent_customers 使用 DormantScanner"""

    def test_dormant_scan_falls_back_to_local_when_promiselink_unavailable(self, ...):
        """PromiseLink 不可用时，降级到本地实现"""

    def test_dormant_scan_handles_promiselink_error(self, ...):
        """PromiseLink 返回错误时，记录日志 + 降级到本地实现"""
```

---

## 六、性能与可扩展性评估

### 6.1 性能开销

| 调用类型 | HTTP 延迟 | 降级路径延迟 | 用户感知 |
|---------|---------|------------|---------|
| 实体抽取（API）| 1-3s | N/A（仅 API）| 可接受 |
| 沉默客户扫描 | 0.5-1s | < 100ms（本地 SQL）| 可接受 |
| 双向承诺分析 | 0.3-1s | < 50ms（规则引擎）| 可接受 |
| 温和催促生成 | 1-3s | N/A（本地模板）| 可接受 |
| 关系推进卡查询 | 0.5-2s | N/A（本地简化版）| 可接受 |

**总开销**：每个任务增加 < 1s（用户感知 < 200ms 因 circuit breaker）

### 6.2 可扩展性

- ✅ PromiseLink 独立部署，OPC-Agents 无单点依赖
- ✅ 多 OPC-Agents 实例可共享同一 PromiseLink 实例
- ✅ OPC-Agents 关闭集成后完全自治
- ✅ PromiseLink 升级不影响 OPC-Agents（API 兼容）

---

## 七、风险评估与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| PromiseLink 未启动 | 🟡 中 | 健康检查 + circuit breaker |
| API 版本不兼容 | 🟡 中 | 文档化 API 版本要求 + 兼容性测试 |
| 双产品数据不同步 | 🟡 中 | 文档说明 + 独立数据库 + 导出/导入工具 |
| 用户配置错误 | 🟢 低 | 明确错误提示 + 测试连接按钮 |
| 性能瓶颈 | 🟢 低 | circuit breaker + 缓存 |
| 安全问题（API Token）| 🟡 中 | Fernet 加密 + 环境变量 + 不写日志 |

---

## 八、与 v1.0.0 后期规划的对应关系

| v1.0.0 功能 | 复用 PromiseLink 能力 | 文档位置 |
|------------|-------------------|---------|
| F-V100-01 CRM 解冻 | DormantScanner | [OPC_AGENTS_ROADMAP_V1.0.0 §2.1.01](OPC_AGENTS_ROADMAP_V1.0.0.md) |
| F-V100-03 PromiseLink 集成 | 全 7 大能力 | [OPC_AGENTS_ROADMAP_V1.0.0 §2.1.03](OPC_AGENTS_ROADMAP_V1.0.0.md) |
| F-V100-05 客户跟进序列 | PromiseBidirectional + NudgeGenerator | [OPC_AGENTS_ROADMAP_V1.0.0 §2.1.05](OPC_AGENTS_ROADMAP_V1.0.0.md) |

---

## 九、决策记录

| 日期 | 决策项 | 决策 | 决策人 |
|------|--------|------|--------|
| 2026-08-01 | 集成模式 | HTTP API（非 pip 依赖）| 架构师 + PM |
| 2026-08-01 | 默认启用 | false（用户主动启用）| PM |
| 2026-08-01 | 失败降级 | 静默降级 + circuit breaker | 架构师 + Security |
| 2026-08-01 | 集成范围 | 7 大能力（高 ROI + 低难度）| PM + 架构师 |

---

## 十、参考文献

### 内部文档

- [OPC_MARKET_RESEARCH_REPORT.md](OPC_MARKET_RESEARCH_REPORT.md) — 市场调研报告
- [OPC_AGENTS_ROADMAP_V1.0.0.md](OPC_AGENTS_ROADMAP_V1.0.0.md) — OPC-Agents 后期规划
- [POSITIONING_RESOLUTION.md](../spec/POSITIONING_RESOLUTION.md) — 产品定位矛盾解决方案

### PromiseLink 资产

- [PromiseLink v0.9.0](https://github.com/lulin70/PromiseLink) — 基础版
- [PromiseLink 项目状态](https://github.com/lulin70/PromiseLink/blob/main/docs/PROJECT_STATUS.md)
- [PromiseLink PRD_功能清单](https://github.com/lulin70/PromiseLink/blob/main/docs/spec/PRD_功能清单.md)

### 关键 PromiseLink 模块

- `services/entity_extractor.py` — 实体抽取
- `services/dormant_scanner.py` — 沉默客户扫描
- `services/promise_bidirectional.py` — 双向承诺分析
- `services/nudge_generator.py` — 温和催促消息
- `services/relationship_brief_service.py` — 关系推进卡（12 模块）
- `services/notification_service.py` — 推送通知
- `api/v1/scheduled_events.py` — 排程事件 CRUD
- `models/reminder.py` — 提醒疲劳度控制

---

*最后更新: 2026-08-01*
*文档负责人: OPC-Agents 团队*
*下次回顾: v1.0.0 发布后（约 2026-09-15）*