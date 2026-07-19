# ADR-005: LLM 后端多路径 fallback 架构设计

**版本**: v0.5.0-draft
**日期**: 2026-07-19
**状态**: 7-Role 共识
**决策者**: Architect Lead
**相关文档**:
- [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) §OKR-4 运营基础设施
- [ASSESSMENT_INITIAL_VISION_v0.4.0.md](../assessments/ASSESSMENT_INITIAL_VISION_v0.4.0.md) §5.6 真实 LLM 后端集成不完整
- [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) 基础版 LLM 调用路径与 A1/A3 硬约束
- [PARALLEL_SAGES_DESIGN.md](PARALLEL_SAGES_DESIGN.md) 三贤者并行投票架构
- 现有代码: [llm_service.py](../../opc_manager/llm_service.py) / [simple_llm_service.py](../../opc_manager/simple_llm_service.py) / [llm_cache.py](../../opc_manager/llm_cache.py) / [consensus_engine.py](../../opc_manager/consensus_engine.py)

---

## 1. 背景（Context）

### 1.1 v0.4.0 评估结论

[ASSESSMENT_INITIAL_VISION_v0.4.0.md](../assessments/ASSESSMENT_INITIAL_VISION_v0.4.0.md) §5.6 明确指出："真实 LLM 后端集成不完整"，列为 6 大欠缺之一（严重级别 P1，v0.5.0 必须处理）。具体表现为：

- D05 E2E 测试 `test_chinese_content_generation_real` 失败
- 根因：Ollama 未启动（`localhost:11434` Connection refused）
- 现有代码已支持 OpenAI、Ollama、Moka AI 接口路径，但缺统一 fallback 调度
- 三贤者系统（[consensus_engine.py](../../opc_manager/consensus_engine.py)）依赖稳定 LLM 后端，单点失败会导致共识门降级

### 1.2 现有代码基础

| 模块 | 路径 | 职责 | 不足 |
|------|------|------|------|
| `llm_service.py` | `opc_manager/llm_service.py` | 基础 LLM 调用封装（`LLMBackend` 抽象类、`OpenAIBackend`、`OllamaBackend`、`MokaBackend`） | 无 fallback 调度，单 backend 失败即整体失败 |
| `simple_llm_service.py` | `opc_manager/simple_llm_service.py` | 简化版 LLM 服务（`discover_llm_config` 自动发现 + 重试 + 熔断） | 仅按优先级选单个 backend，无运行时 fallback |
| `llm_cache.py` | `opc_manager/llm_cache.py` | LLM 调用缓存（TTL LRU + SQLite 持久化，60-80% 成本降低） | 缓存未命中时仍依赖单一 backend |
| `embedding_service.py` | `opc_manager/embedding_service.py` | 向量化处理 | 与本 ADR 无直接关系 |
| `consensus_engine.py` | `opc_manager/consensus_engine.py` | 三贤者并行投票 | 三贤者各自调用 LLM，缺统一入口导致重复失败 |

### 1.3 硬约束映射

本 ADR 必须遵守 [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) 中以下条款：

- **A1**: 三贤者系统必须采用并行投票架构（`asyncio.gather`），禁止串行流水线
- **A3**: DevSquad 被调用时优先尝试 LLM，LLM 不可用时才使用 MOCK
- **基础版 LLM 调用路径**: 用户本地 → 网关 `/api/v1/pro/relay/llm` → Moka AI（用户不持有 LLM API Key）
- **基础版标头**: 调用 AI 时必须携带 `X-AI-Call: true` 标头用于网关计费归属区分

### 1.4 问题陈述

- 用户安装 Ollama 门槛高，且 E2E 测试已证明单机 Ollama 不稳定
- 仅依赖 Moka AI 网关在用户本地无网络时无法工作
- 让用户手动选择 backend 违反"非技术用户可用"原则
- 三贤者系统若各自直连 backend，单点失败会拖累整个共识流程

## 2. 决策（Decision）

**采用统一 `LLMBackendManager` 作为三路径自动 fallback 调度入口，配合健康检查与缓存优先策略。**

### 2.1 三路径优先级与 fallback 策略

| 优先级 | Backend | 默认 URL | 适用场景 | 用户成本 |
|--------|---------|----------|----------|----------|
| 1（默认） | Ollama | `http://localhost:11434` | 用户零成本、隐私本地、离线可用 | 免费 |
| 2（fallback） | Moka AI 网关 | `https://gateway.promiselink.cn/api/v1/pro/relay/llm` | 基础版默认路径，用户不持有 API Key | 免费（网关计费） |
| 3（fallback） | OpenAI 兼容接口 | 用户自配 `base_url` + `api_key` | 高级用户可选 | 用户自付 |

### 2.2 Fallback 触发条件

| Backend | 触发 fallback 的错误条件 |
|---------|--------------------------|
| Ollama | Connection refused / 连接超时 10s / HTTP 5xx / 模型未加载 |
| Moka AI | HTTP 5xx / 请求超时 30s / 限流 429 / 网关 502/503 |
| OpenAI | 同 Moka AI |

### 2.3 自动 fallback 链

- 默认顺序：Ollama → Moka AI → OpenAI
- 用户可通过 `.env` 中 `LLM_BACKENDS=ollama,moka,openai` 自定义顺序
- 三路径都不可用时返回友好错误提示（不抛裸异常）

### 2.4 网关计费标头

基础版调用 Moka AI 网关时，HTTP 请求必须携带：

```
X-AI-Call: true
Authorization: Bearer <gateway_token>  # 由网关颁发，非用户 API Key
```

`X-AI-Call: true` 用于网关区分计费归属（基础版用户调用 vs 专业版用户调用），缺失会导致网关拒绝请求或错误计费。

## 3. 方案细节

### 3.1 LLMBackendManager 类设计

新增模块 `opc_manager/llm_backend_manager.py`（预计 ~300 行）作为统一调度入口。

```python
# opc_manager/llm_backend_manager.py (伪代码)

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import asyncio
import time
import logging
from .llm_cache import LLMCache
from .llm_service import LLMBackend, LLMResponse, LLMConfig

logger = logging.getLogger(__name__)


class BackendType(Enum):
    OLLAMA = "ollama"
    MOKA = "moka"
    OPENAI = "openai"


@dataclass
class LLMBackendConfig:
    """单个 backend 的配置"""
    backend_type: BackendType
    base_url: str
    api_key: Optional[str] = None
    model: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 2
    # 基础版网关专用
    requires_ai_call_header: bool = False
    gateway_token: Optional[str] = None


@dataclass
class BackendHealth:
    """单个 backend 的健康状态"""
    backend_type: BackendType
    healthy: bool = True
    consecutive_failures: int = 0
    last_check_ts: float = 0.0
    last_latency_ms: int = 0
    # unhealthy 后的下次重试探测时间
    next_probe_ts: float = 0.0


class LLMBackendManager:
    """统一 LLM 调度入口 — 三路径 fallback + 缓存优先 + 健康检查"""

    HEALTH_CHECK_INTERVAL_SEC = 60
    UNHEALTHY_THRESHOLD = 3
    UNHEALTHY_RETRY_INTERVAL_SEC = 300

    def __init__(
        self,
        backends: List[LLMBackendConfig],
        cache: Optional[LLMCache] = None,
    ) -> None:
        if not backends:
            raise ValueError("LLMBackendManager requires at least one backend")
        self._backends: List[LLMBackendConfig] = backends
        self._cache: Optional[LLMCache] = cache
        self._health: Dict[BackendType, BackendHealth] = {
            b.backend_type: BackendHealth(backend_type=b.backend_type) for b in backends
        }
        self._health_check_task: Optional[asyncio.Task] = None

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
        **kwargs: Any,
    ) -> LLMResponse:
        """统一调用入口 — 缓存优先，否则按优先级 fallback"""
        # 1. 缓存优先
        if self._cache is not None:
            cached = self._cache.get(prompt, model=self._primary_model())
            if cached is not None:
                logger.debug("[LLMBackendManager] Cache hit, skip backend call")
                return cached

        # 2. 按优先级 fallback
        last_error: Optional[Exception] = None
        for backend_cfg in self._backends:
            health = self._health[backend_cfg.backend_type]
            if not health.healthy and time.time() < health.next_probe_ts:
                logger.info(
                    "[LLMBackendManager] Skip unhealthy backend: %s",
                    backend_cfg.backend_type.value,
                )
                continue
            try:
                response = await self._try_backend(
                    backend_cfg, prompt, system_prompt, temperature, max_tokens
                )
                self._record_health(backend_cfg.backend_type, success=True,
                                    latency_ms=int(response.latency_ms))
                if self._cache is not None:
                    self._cache.set(prompt, response, model=self._primary_model())
                return response
            except Exception as e:
                last_error = e
                should_fb = self._should_fallback(e)
                self._record_health(backend_cfg.backend_type, success=False, latency_ms=0)
                logger.warning(
                    "[LLMBackendManager] Backend %s failed: %s (fallback=%s)",
                    backend_cfg.backend_type.value, e, should_fb,
                )
                if not should_fb:
                    raise
                # 否则继续尝试下一个 backend

        # 3. 三路径都失败
        raise LLMAllBackendsFailedError(
            "All LLM backends failed. Last error: {}".format(last_error)
        )

    async def _try_backend(
        self,
        backend_cfg: LLMBackendConfig,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """尝试单个 backend — 失败抛异常，由 call() 决定是否 fallback"""
        backend = self._build_backend(backend_cfg)
        headers = self._build_headers(backend_cfg)
        # asyncio.wait_for 强制超时
        return await asyncio.wait_for(
            backend.complete(prompt, system_prompt=system_prompt),
            timeout=backend_cfg.timeout_seconds,
        )

    def _should_fallback(self, error: Exception) -> bool:
        """判断错误是否应触发 fallback（vs 直接抛出）"""
        if isinstance(error, asyncio.TimeoutError):
            return True
        if isinstance(error, ConnectionError):
            return True
        # HTTP 5xx / 429 触发 fallback；4xx (除 429) 不触发
        msg = str(error).lower()
        if any(k in msg for k in ("5xx", "500", "502", "503", "504", "429", "refused")):
            return True
        return False

    def _record_health(
        self, backend: BackendType, success: bool, latency_ms: int
    ) -> None:
        """记录健康状态 — 连续 3 次失败标记 unhealthy"""
        health = self._health[backend]
        health.last_check_ts = time.time()
        health.last_latency_ms = latency_ms
        if success:
            health.consecutive_failures = 0
            health.healthy = True
            health.next_probe_ts = 0.0
        else:
            health.consecutive_failures += 1
            if health.consecutive_failures >= self.UNHEALTHY_THRESHOLD:
                health.healthy = False
                health.next_probe_ts = (
                    time.time() + self.UNHEALTHY_RETRY_INTERVAL_SEC
                )
                logger.warning(
                    "[LLMBackendManager] Backend %s marked unhealthy",
                    backend.value,
                )

    async def _health_check_loop(self) -> None:
        """后台心跳检测 — 每 60s 探测所有 backend"""
        while True:
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL_SEC)
            for cfg in self._backends:
                await self._probe_backend(cfg)

    async def _probe_backend(self, cfg: LLMBackendConfig) -> None:
        """轻量探测 — HEAD 请求 + 5s timeout"""
        try:
            # 实际实现使用 httpx.AsyncClient.head(url, timeout=5.0)
            await asyncio.wait_for(self._head_probe(cfg.base_url), timeout=5.0)
            self._record_health(cfg.backend_type, success=True, latency_ms=0)
        except Exception as e:
            self._record_health(cfg.backend_type, success=False, latency_ms=0)

    def _build_headers(self, cfg: LLMBackendConfig) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if cfg.requires_ai_call_header:
            headers["X-AI-Call"] = "true"
        if cfg.gateway_token:
            headers["Authorization"] = f"Bearer {cfg.gateway_token}"
        elif cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        return headers

    def _primary_model(self) -> str:
        return self._backends[0].model if self._backends else "unknown"

    def _build_backend(self, cfg: LLMBackendConfig) -> LLMBackend:
        """根据 BackendType 构建对应 LLMBackend 实例"""
        # 复用 llm_service.py 中已有的 OpenAIBackend / OllamaBackend / MokaBackend
        ...


class LLMAllBackendsFailedError(RuntimeError):
    """所有 backend 都失败的兜底异常"""
    pass
```

### 3.2 Fallback 流程图

```
                         用户请求 (prompt)
                              │
                              ▼
                  ┌───────────────────────┐
                  │  LLMBackendManager    │
                  │      .call()          │
                  └───────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │  1. 查询 LLMCache     │
                  │  (SQLite + TTL LRU)   │
                  └───────────────────────┘
                              │
                   命中 ──────┼────── 未命中
                    │                  │
                    ▼                  ▼
              返回缓存响应   ┌───────────────────────┐
                            │  2. 按优先级 fallback  │
                            └───────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │  P1: Ollama (localhost:11434)   │
                    │  healthy? ── no ── skip         │
                    └─────────────────────────────────┘
                                      │
                                try call
                              ──┬──────────┬──
                            成功│          │失败
                                ▼          ▼
                          返回响应   _should_fallback?
                                          │
                                   no ────┼──── yes
                                   │              │
                                   ▼              ▼
                                 抛异常   ┌─────────────────────────────────┐
                                         │  P2: Moka AI 网关              │
                                         │  + X-AI-Call: true 标头        │
                                         │  healthy? ── no ── skip        │
                                         └─────────────────────────────────┘
                                                  │
                                            try call
                                          ──┬──────────┬──
                                        成功│          │失败
                                            ▼          ▼
                                      返回响应   _should_fallback?
                                                      │
                                               no ────┼──── yes
                                               │              │
                                               ▼              ▼
                                             抛异常   ┌─────────────────────────────────┐
                                                     │  P3: OpenAI 兼容接口           │
                                                     │  (用户自配 base_url + api_key) │
                                                     │  healthy? ── no ── skip        │
                                                     └─────────────────────────────────┘
                                                              │
                                                        try call
                                                      ──┬──────────┬──
                                                    成功│          │失败
                                                        ▼          ▼
                                                  返回响应         │
                                                            ┌─────┴─────┐
                                                            │ 三路径都失败│
                                                            └───────────┘
                                                                  │
                                                                  ▼
                                                  LLMAllBackendsFailedError
                                                  + 友好错误提示引导用户

  后台并行任务:
  ┌────────────────────────────────────────────────┐
  │  _health_check_loop (每 60s 一次)              │
  │  ├─ Ollama   HEAD / 5s timeout                 │
  │  ├─ Moka AI  HEAD / 5s timeout                 │
  │  └─ OpenAI   HEAD / 5s timeout                 │
  │                                                │
  │  连续 3 次失败 → 标记 unhealthy → 跳过 5min    │
  │  5min 后自动重试探测恢复                       │
  └────────────────────────────────────────────────┘
```

### 3.3 健康检查机制

| 维度 | 策略 |
|------|------|
| 启动探测 | 进程启动时对每个 backend 发起 HEAD 请求（5s timeout），标记初始健康状态 |
| 心跳周期 | 每 60s 后台 `asyncio.Task` 探测所有 backend |
| 失败阈值 | 连续 3 次失败标记为 `unhealthy`，`call()` 跳过该 backend |
| 恢复探测 | `unhealthy` backend 每 5min（`UNHEALTHY_RETRY_INTERVAL_SEC=300`）重试一次探测 |
| 探测方式 | HEAD 请求（不发 prompt，不计费） |
| 并发安全 | `_health` 字典通过 `asyncio.Lock` 保护（单事件循环下天然安全） |

### 3.4 与现有组件集成

#### 3.4.1 与 `llm_cache.py` 集成

- `LLMBackendManager.call()` 入口先查缓存，命中则直接返回，不触发任何 backend 调用
- 缓存未命中且 backend 调用成功后，写回缓存（与 `LLMCache` 现有 TTL/LRU 逻辑对齐）
- 缓存 key 复用 `llm_cache.py` 现有的 `hashlib` 派生逻辑，避免破坏现有命中数据

#### 3.4.2 与三贤者系统（`consensus_engine.py`）集成

- 三贤者并行投票（`asyncio.gather`，满足硬约束 A1）各自调用 `LLMBackendManager.call()`
- 三贤者共享同一个 `LLMBackendManager` 单例，共享健康状态与缓存
- 任一贤者遇到 backend 失败时，由 `LLMBackendManager` 内部 fallback 处理，对 `ConsensusEngine` 透明
- 满足硬约束 A3：LLM 优先（含三路径 fallback），全部失败才抛 `LLMAllBackendsFailedError`，由 `ConsensusEngine` 决定是否降级到 MOCK

#### 3.4.3 与 `simple_llm_service.py` 集成

- `simple_llm_service.py` 简化为 `LLMBackendManager` 的轻量包装
- `discover_llm_config()` 保留，作为 `LLMBackendConfig` 列表的工厂方法
- 原有 `LLM_CALL_TIMEOUT`、`LLM_MAX_RETRIES`、`_CIRCUIT_BREAKER_THRESHOLD` 等常量被 `LLMBackendManager` 的配置项取代
- 对外 API 保持向后兼容，避免影响 53+ 导入站点

#### 3.4.4 与 `llm_service.py` 集成

- `LLMBackendManager` 复用 `llm_service.py` 中已有的 `OpenAIBackend`、`OllamaBackend`、`MokaBackend` 实现
- `_build_backend()` 根据 `BackendType` 返回对应子类实例
- 不修改 `llm_service.py` 的公共 API，仅作为其上层调度器

### 3.5 配置文件示例

`.env` 示例：

```dotenv
# LLM 后端优先级顺序（逗号分隔，从左到右优先级递减）
LLM_BACKENDS=ollama,moka,openai

# 优先级 1: 本地 Ollama（默认）
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT_SECONDS=10

# 优先级 2: Moka AI 网关（基础版默认路径，用户不持有 API Key）
MOKA_GATEWAY_URL=https://gateway.promiselink.cn
MOKA_GATEWAY_TOKEN=<由网关颁发>
MOKA_MODEL=moka/claude-sonnet-4-6
MOKA_TIMEOUT_SECONDS=30

# 优先级 3: OpenAI 兼容接口（高级用户可选）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=30

# 全局参数
LLM_TIMEOUT_DEFAULT=30
LLM_FALLBACK_MAX_RETRIES=2
LLM_HEALTH_CHECK_INTERVAL=60
LLM_UNHEALTHY_THRESHOLD=3
LLM_UNHEALTHY_RETRY_INTERVAL=300
```

`.env.example` 同步更新，标注每项配置的语义与默认值。

## 4. 替代方案（Alternatives）

| 方案 | 描述 | 决策 | 理由 |
|------|------|------|------|
| A. 仅使用 Ollama | 拒绝其他 backend | 拒绝 | 用户安装 Ollama 门槛高，D05 E2E 已证明不稳定 |
| B. 仅使用 Moka AI 网关 | 拒绝其他 backend | 拒绝 | 用户本地无网络时无法工作；增加网关负载；违反硬约束 A3（LLM 不可用才 MOCK，但单路径易"不可用"） |
| C. 让用户手动选择 backend | 启动时弹窗让用户选 | 拒绝 | 非技术用户不知道如何选择，违反"非技术用户可用"原则 |
| D. 自动 fallback 链（本 ADR） | Ollama → Moka AI → OpenAI | 采纳 | 用户无感切换 + 三路径保障 + 隐私优先（Ollama 默认）+ 零成本默认 |

## 5. 后果（Consequences）

### 5.1 正面后果

- **稳定性提升**: 三路径保障，单 backend 失败不再导致整体失败
- **隐私优先**: Ollama 默认本地，敏感 prompt 不出本机
- **零成本默认**: Ollama + Moka AI 网关组合对用户免费
- **三贤者稳定性**: 共享 `LLMBackendManager` 单例，三贤者并行投票不再各自承担单点失败风险
- **可观测性**: 健康状态与延迟数据可被 `monitoring.py` 采集，为 v0.5.0 商业指标埋点提供数据源

### 5.2 负面后果

- **新增模块**: `llm_backend_manager.py` 预计 ~300 行，需配套单元测试
- **健康检查机制**: 后台 `asyncio.Task` 需要正确生命周期管理（启停、取消）
- **配置复杂度**: `.env` 新增 10+ 配置项，需在 `.env.example` 与文档同步说明
- **网关依赖**: Moka AI 网关不可用时整个 fallback 链路退化到 Ollama + OpenAI

### 5.3 中性后果

- v0.6.0 可扩展更多 backend（Anthropic Claude / 本地 GGUF / 国产模型如 GLM、Qwen）
- 健康检查机制为未来接入 SLA 监控奠定基础
- 缓存优先策略与 `llm_cache.py` 现有 60-80% 成本降低效果叠加

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 三路径都不可用 | 用户无法使用 LLM 功能 | 返回友好错误提示 + 引导用户检查 Ollama 或网络；`ConsensusEngine` 降级到 MOCK（硬约束 A3） |
| Fallback 链导致延迟高 | 用户体验下降 | 缓存优先（命中即返回）+ 健康检查跳过 unhealthy backend + 各 backend 独立超时（Ollama 10s / Moka 30s） |
| 用户隐私泄露 | 合规风险 | Ollama 默认本地（隐私优先）；Moka AI 网关已启用 HTTPS 加密传输；不记录 prompt 内容到日志 |
| 健康检查任务泄漏 | 长期运行进程资源泄漏 | `LLMBackendManager` 提供 `close()` 方法取消后台任务；进程退出时正确清理 |
| 网关标头缺失导致计费错误 | 商业损失 | `X-AI-Call: true` 标头在 `_build_headers()` 中硬编码，单元测试验证 |
| 多 backend 并发调用缓存竞态 | 缓存数据不一致 | 复用 `llm_cache.py` 现有 `threading.RLock`；`asyncio` 单事件循环天然无并发写 |

## 7. 验证标准

### 7.1 功能验证

| # | 验证项 | 验证方法 | 通过标准 |
|---|--------|----------|----------|
| V1 | Ollama 可用时优先使用 Ollama | 启动 Ollama + 调用 `LLMBackendManager.call()` | 响应 `provider == LLMProvider.OLLAMA` |
| V2 | Ollama 不可用时自动 fallback 到 Moka AI | 停止 Ollama + 调用 | 响应 `provider == LLMProvider.MOKA`，日志记录 fallback |
| V3 | Moka AI 不可用时自动 fallback 到 OpenAI | 配置 OpenAI + 模拟 Moka 5xx | 响应 `provider == LLMProvider.OPENAI` |
| V4 | 三路径都不可用时返回友好错误 | 停止所有 backend + 调用 | 抛 `LLMAllBackendsFailedError`，错误消息含引导提示 |
| V5 | 健康检查每 60s 一次 | 启动后等待 65s + 检查 `_health` 状态 | `last_check_ts` 更新 |
| V6 | 连续 3 次失败标记 unhealthy | 模拟 backend 连续失败 3 次 | `health.healthy == False`，`call()` 跳过该 backend |
| V7 | unhealthy backend 每 5min 重试探测 | 标记 unhealthy + 等待 5min + 恢复 backend | `health.healthy == True` |
| V8 | 必须携带 X-AI-Call: true 标头 | 抓包检查 Moka AI 网关请求 | HTTP 请求头含 `X-AI-Call: true` |
| V9 | 缓存命中时不调用 backend | 预填缓存 + 调用 | backend `complete()` 不被调用 |
| V10 | 三贤者并行调用共享健康状态 | 三贤者同时调用 + 一个 backend 失败 | 仅触发一次健康状态更新，无重复探测 |

### 7.2 测试覆盖

- 单元测试覆盖率 ≥ 80%（`tests/unit/test_llm_backend_manager.py`）
- E2E 测试 `test_chinese_content_generation_real` 在 Ollama 未启动场景下通过（fallback 到 Moka AI）
- E2E 测试覆盖三路径都失败场景，验证友好错误提示

## 8. 实施计划

| 阶段 | 工作项 | 负责角色 | 预计工时 |
|------|--------|----------|----------|
| 1 | 创建 `opc_manager/llm_backend_manager.py` | Coder | 4h |
| 2 | 改造 `simple_llm_service.py` 为 `LLMBackendManager` 包装 | Coder | 2h |
| 3 | 改造 `consensus_engine.py` 三贤者调用入口 | Coder | 2h |
| 4 | 编写单元测试 `tests/unit/test_llm_backend_manager.py` | Tester | 3h |
| 5 | 修复 D05 E2E 测试 `test_chinese_content_generation_real` | Tester | 1h |
| 6 | 更新 `.env.example` 与 `HARD_CONSTRAINTS.md` 引用 | Coder | 1h |
| 7 | 7-Role 共识评审 | All | 1h |

## 9. 相关文档

- [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) §OKR-4 运营基础设施
- [ASSESSMENT_INITIAL_VISION_v0.4.0.md](../assessments/ASSESSMENT_INITIAL_VISION_v0.4.0.md) §5.6 真实 LLM 后端集成不完整
- [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) §2.4 A1/A3 硬约束 + 基础版 LLM 调用路径
- [PARALLEL_SAGES_DESIGN.md](PARALLEL_SAGES_DESIGN.md) 三贤者并行投票架构
- [ADR-001-IntentRouter-design.md](ADR-001-IntentRouter-design.md) 意图分类（与本 ADR 无直接依赖）
- [ADR-003-TaskEngineV3-design.md](ADR-003-TaskEngineV3-design.md) TaskEngineV3 内容生成 Mixin 将通过本 ADR 调用 LLM
- 现有代码:
  - [opc_manager/llm_service.py](../../opc_manager/llm_service.py)
  - [opc_manager/simple_llm_service.py](../../opc_manager/simple_llm_service.py)
  - [opc_manager/llm_cache.py](../../opc_manager/llm_cache.py)
  - [opc_manager/consensus_engine.py](../../opc_manager/consensus_engine.py)
  - [opc_manager/embedding_service.py](../../opc_manager/embedding_service.py)
