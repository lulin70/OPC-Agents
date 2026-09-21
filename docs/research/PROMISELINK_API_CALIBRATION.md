# PromiseLink v0.9.0 HTTP API 路由校准报告（实际源码版）

> **校准日期**: 2026-08-01
> **校准依据**: PromiseLink 源码逐行核对（`src/promiselink/main.py` + `src/promiselink/api/v1/*.py`）
> **校准人**: OPC-Agents 团队
> **关联文档**: [PROMISELINK_REUSE_PLAN.md](PROMISELINK_REUSE_PLAN.md)（已根据本报告修正路径）
> **API 前缀**: `/api/v1`（来自 `config.py`）

---

## 一、校准结论概览

按实测源码，PROMISELINK_REUSE_PLAN 中**有 3 个路由不存在**，必须改用其他等价接口：

| 旧规划路径 | 真实路径 | 差异 |
|----------|---------|------|
| `GET /api/v1/entities?dormant_days=...` | `GET /api/v1/entities/dormant?min_days=...` | 路径错误，参数名 `min_days` |
| `POST /api/v1/todos/analyze-bidirectional` | `POST /api/v1/events`（全管线异步执行）| 不存在独立同步分析端点 |
| `POST /api/v1/nudges/generate` | `GET /api/v1/promises/{todo_id}/nudge-draft` | 路径完全不同 + 仅 GET，且必须先有 todo_id |

另外，旧规划遗漏了 3 个非常适合 OPC-Agents 复用的端点，本报告补齐。

---

## 二、PromiseLink v0.9.0 完整路由清单（67 个端点，全部已验证）

### 2.1 健康与监控（4 个）

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| GET | `/api/v1/health` | 基础健康检查 | ✅ 集成前探活 |
| GET | `/api/v1/health/db` | 数据库健康检查 | ⚠️ 调试用 |
| GET | `/api/v1/health/full` | 完整健康检查（含业务指标）| ⚠️ 调试用 |
| GET | `/api/v1/metrics` | Prometheus 指标 | ❌ 不复用 |

### 2.2 认证（3 个）

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| POST | `/api/v1/auth/login` | 邮箱密码登录 | ✅ token 获取 |
| POST | `/api/v1/auth/auto` | 自动登录（已登录态）| ✅ token 刷新 |
| POST | `/api/v1/auth/wechat/login` | 微信小程序登录 | ❌ 不复用 |

### 2.3 事件（4 个）

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| POST | `/api/v1/events` | 创建事件（触发完整管线）| ✅ **核心：实体抽取入口** |
| POST | `/api/v1/events/upload` | 上传文件事件 | ⚠️ 仅在需要上传时 |
| GET | `/api/v1/events/{event_id}` | 获取事件详情 | ✅ **核心：管线结果查询** |
| DELETE | `/api/v1/events/{event_id}` | 删除事件 | ⚠️ 治理用 |

**管线执行机制**（重要）：
- POST `/events` 创建事件后，**后台异步执行 13 步管线**（step_01_verify → step_13_complete）
- 客户端需轮询 GET `/events/{event_id}` 获取处理结果
- 包含实体抽取、承诺分析、Todo 生成、提醒通知等
- 不存在"同步触发实体抽取"的端点（必须走完整管线）

### 2.4 实体（9 个）— **客户管理复用**

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| GET | `/api/v1/entities` | 实体列表（分页 + 搜索 + 过滤）| ✅ **核心：CRM 列表** |
| GET | `/api/v1/entities/dormant` | **沉默客户扫描**（3 维度评分）| ✅ **核心：CRM-03** |
| GET | `/api/v1/entities/duplicates` | 重复实体检测 | ✅ 去重场景 |
| GET | `/api/v1/entities/{entity_id}` | 实体详情 | ✅ **核心：CRM-02** |
| PATCH | `/api/v1/entities/{entity_id}` | 更新实体 | ✅ CRM 字段更新 |
| DELETE | `/api/v1/entities/{entity_id}` | 删除实体 | ⚠️ 治理用 |
| POST | `/api/v1/entities/{entity_id}/confirm` | 确认实体 | ✅ 用户纠偏 |
| POST | `/api/v1/entities/{target_id}/merge` | 合并实体 | ✅ 同人识别 |
| GET | `/api/v1/entities/{entity_id}/history` | 实体历史 | ✅ CRM 时间线 |
| GET | `/api/v1/entities/{entity_id}/stage-info` | 关系阶段 | ✅ 客户生命周期 |
| GET | `/api/v1/entities/stage-map` | 阶段元数据 | ✅ 阶段字典 |
| GET | `/api/v1/entities/{entity_id}/credit-score` | 信用分 | ⚠️ 信用评分 |
| GET | `/api/v1/entities/credit-scores` | 信用分列表 | ⚠️ 信用排名 |

**沉默客户扫描真实参数**（纠正旧规划）：
```http
GET /api/v1/entities/dormant?limit=10&offset=0&min_days=60
```

返回字段（来自 `DormantContactItem`）：
```json
{
  "entity_id": "uuid",
  "name": "string",
  "company": "string|null",
  "dormant_days": 92,
  "reactivation_score": 0.78,
  "last_interaction": "2026-05-01T10:00:00Z|null",
  "last_event_summary": "string|null",
  "reason": "string",
  "icebreaker_topic": "string",
  "pending_their_promises": 0,
  "relationship_stage": "unknown|..."
}
```

### 2.5 关联（2 个）

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| GET | `/api/v1/associations` | 实体间关系列表 | ✅ 关系图谱 |
| GET | `/api/v1/associations/{association_id}` | 单个关系 | ✅ |

### 2.6 Todo（6 个）— **任务系统复用**

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| GET | `/api/v1/todos` | Todo 列表（按类型/状态/优先级过滤）| ✅ **核心：任务管理** |
| GET | `/api/v1/todos/pending-confirmations` | 待确认 Todo | ✅ 待办确认 |
| GET | `/api/v1/todos/{todo_id}` | Todo 详情 | ✅ |
| PATCH | `/api/v1/todos/{todo_id}` | 更新 Todo | ✅ |
| DELETE | `/api/v1/todos/{todo_id}` | 删除 Todo | ⚠️ 治理用 |
| PATCH | `/api/v1/todos/{todo_id}/confirm` | 确认/拒绝 Todo | ✅ 用户纠偏 |

**6 种 Todo 类型**（已在使用）：
- `promise` — 承诺
- `followup` — 跟进
- `help` — 帮助请求
- `care` — 关心问候
- `cooperation_signal` — 合作信号
- `risk` — 风险预警

### 2.7 Dashboard（7 个）

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| GET | `/api/v1/dashboard` | 今日 summary（兼容旧前端）| ✅ 早晚报 |
| GET | `/api/v1/dashboard/summary` | Dashboard 聚合 | ✅ |
| GET | `/api/v1/dashboard/day-view` | 单日视图 | ✅ |
| GET | `/api/v1/dashboard/range-view` | 时间段视图 | ✅ |
| GET | `/api/v1/dashboard/morning-brief` | **每日晨间摘要** | ✅ **核心：早报** |
| GET | `/api/v1/dashboard/supply-demand` | 供需匹配 | ⚠️ 业务模式 |
| GET | `/api/v1/dashboard/relationship-health` | 关系健康度 | ✅ 客户洞察 |
| GET | `/api/v1/dashboard/care-reminders` | **关怀提醒** | ✅ **核心：温情提醒** |

### 2.8 关系推进卡（4 个）— **核心复用**

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| GET | `/api/v1/persons/{entity_id}/relationship-brief` | 单人关系简报 | ✅ **核心：CRM 详情** |
| GET | `/api/v1/persons/{entity_id}/relationship-brief/aggregated` | **12 模块聚合视图** | ✅ **核心：UI 视图** |
| GET | `/api/v1/relationship-briefs` | 推进卡列表 | ✅ 推进卡列表 |
| PATCH | `/api/v1/relationship-briefs/{brief_id}` | 更新推进卡（含乐观锁）| ✅ 用户编辑 |

**12 模块聚合视图字段**（来自 `_MODULE_META`）：
```
basic_info, relationship_stage, last_interaction, interaction_freq,
open_promises, their_concerns, my_contributions, cooperation_signals,
risk_flags, next_actions, strength_score, notes
```

### 2.9 需求输入（1 个）

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| POST | `/api/v1/demands` | 提交需求（触发 F-E4 供需匹配）| ❌ 业务模式不同 |

### 2.10 承诺（4 个）— **核心复用**

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| GET | `/api/v1/promises` | 承诺列表（my/their 双视角）| ✅ **核心：承诺管理** |
| PATCH | `/api/v1/promises/{todo_id}/fulfillment` | 更新兑现状态 | ✅ |
| GET | `/api/v1/promises/stats` | **承诺统计** | ✅ **核心：双视角统计** |
| GET | `/api/v1/promises/{todo_id}/nudge-draft` | **温和催促消息草稿** | ✅ **核心：nudge 生成** |

**催促消息真实调用方式**（纠正旧规划）：
```http
GET /api/v1/promises/{todo_id}/nudge-draft
```

注意：
- 必须是 **GET**，不是 POST
- 必须先有 `todo_id`，不能直接传 entity_name
- 仅对 `action_type == "their_promise"` 的 Todo 有效
- 返回 `{ "todo_id": "...", "nudge_text": "...", "is_fallback": false }`

**承诺统计字段**（来自 `PromiseStatsResponse`）：
```json
{
  "total": 12,
  "my_promises": { "pending": 3, "fulfilled": 5, "overdue": 1, "expired": 0 },
  "their_promises": { "pending": 2, "fulfilled": 1, "overdue": 0, "expired": 0 },
  "fulfillment_rate": 0.5
}
```

### 2.11 提醒（5 个）

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| GET | `/api/v1/reminders/daily` | **每日提醒列表** | ✅ **核心：提醒推送** |
| POST | `/api/v1/reminders/{todo_id}/action` | 单条提醒操作（完成/延后/忽略）| ✅ |
| POST | `/api/v1/reminders/batch-action` | 批量操作 | ✅ |
| GET | `/api/v1/reminders/preferences` | 提醒偏好 | ✅ **核心：疲劳度配置** |
| PATCH | `/api/v1/reminders/preferences` | 更新提醒偏好 | ✅ |

**提醒偏好字段**（默认）：
- `preferred_times`: `["09:00", "20:00"]`
- `fatigue_threshold`: 5
- `quiet_hours_start`: `"22:00"`
- `quiet_hours_end`: `"08:00"`

### 2.12 排程事件（7 个）— **核心复用**

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| POST | `/api/v1/scheduled-events` | 创建排程事件 | ✅ **核心：定时任务后端** |
| GET | `/api/v1/scheduled-events` | 排程列表 | ✅ |
| GET | `/api/v1/scheduled-events/{id}` | 单个排程 | ✅ |
| PATCH | `/api/v1/scheduled-events/{id}` | 更新排程 | ✅ |
| DELETE | `/api/v1/scheduled-events/{id}` | 删除排程 | ✅ |
| POST | `/api/v1/scheduled-events/{id}/record` | 记录排程执行结果 | ✅ |
| POST | `/api/v1/scheduled-events/{id}/cancel` | 取消排程 | ✅ |

**`/api/v1/scheduled-events` 创建请求**（来自 `ScheduledEventCreateRequest`）：
```json
{
  "scheduled_at": "2026-09-15T14:00:00+08:00",
  "topic": "与张总讨论新项目合作",
  "participants": [{"name": "张总", "company": "ABC科技", "entity_id": "uuid?"}],
  "location": "望京SOHO",
  "event_type": "meeting|call|manual",
  "reminder_at": "2026-09-15T13:00:00+08:00",
  "metadata": {}
}
```

### 2.13 隐私与导出（3 个）

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| DELETE | `/api/v1/user-data` | 删除用户全部数据 | ⚠️ 治理用 |
| GET | `/api/v1/data-summary` | 数据汇总 | ⚠️ |
| GET | `/api/v1/export/{user_id}` | 导出用户数据 | ✅ 用户数据可携带 |

### 2.14 配对（3 个）

| 方法 | 路径 | 用途 | OPC-Agents 复用 |
|------|------|------|---------------|
| POST | `/api/v1/pair/init` | 初始化配对 | ❌ 不复用 |
| GET | `/api/v1/pair/status` | 配对状态 | ❌ |
| POST | `/api/v1/pair/activate` | 激活配对 | ❌ |

---

## 三、旧规划路径修正映射表

| 旧规划路径（错误）| 真实路径（正确）| 用途 |
|----------------|--------------|------|
| `GET /api/v1/entities?dormant_days=N` | `GET /api/v1/entities/dormant?min_days=N` | 沉默客户扫描 |
| `POST /api/v1/todos/analyze-bidirectional` | `POST /api/v1/events`（异步管线）| 触发承诺分析 |
| `POST /api/v1/nudges/generate` | `GET /api/v1/promises/{todo_id}/nudge-draft` | 催促消息生成 |

### 3.1 沉默客户扫描调用示例（修正版）

```python
# opc_manager/promiselink_client.py（修正）

def scan_dormant_contacts(self, days_threshold: int = 90, limit: int = 10) -> Optional[List[Dict]]:
    """沉默客户扫描（PromiseLink DormantScanner）

    用于：crm.get_silent_customers 增强
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
```

### 3.2 双向承诺分析调用方式（修正版）

**事实**：PromiseLink 没有"输入文本同步分析"的端点。

**正确做法**：POST `/api/v1/events` 创建事件，后台异步执行 13 步管线（含 step_05_promise），轮询 GET `/events/{id}` 获取结果。

```python
async def analyze_promise_from_text(self, text: str, source: str = "opc_agents") -> Optional[Dict]:
    """从文本分析双向承诺（通过 PromiseLink 完整管线）

    异步管线：POST /events → BackgroundTasks → 13 步管线
    返回 todo_id 列表（含 action_type 字段）
    """
    if not self._can_call():
        return None
    try:
        # Step 1: 创建事件
        response = self.session.post(
            f"{self.config.api_url}/api/v1/events",
            json={
                "event_type": "manual",
                "source": source,
                "title": text[:200],
                "raw_text": text[:8000],
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        event_id = response.json()["event"]["id"]

        # Step 2: 轮询等待管线完成
        return await self._poll_pipeline_result(event_id, max_wait_seconds=30)

    except Exception as e:
        self._record_failure()
        logger.warning("promiselink_analyze_promise_failed", error=str(e))
        return None

async def _poll_pipeline_result(self, event_id: str, max_wait_seconds: int = 30) -> Dict:
    """轮询事件管线结果（每 2 秒一次）"""
    import asyncio
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        response = self.session.get(
            f"{self.config.api_url}/api/v1/events/{event_id}",
            timeout=self.config.timeout_seconds,
        )
        if response.status_code == 200:
            data = response.json()
            status = data.get("processing_status", "pending")
            if status in ("completed", "failed"):
                return data
        await asyncio.sleep(2)
    raise TimeoutError(f"Pipeline not completed within {max_wait_seconds}s")
```

### 3.3 催促消息生成调用方式（修正版）

**事实**：GET 而非 POST，必须先有 todo_id。

```python
def generate_nudge_message(self, todo_id: str) -> Optional[str]:
    """温和催促消息生成（PromiseLink NudgeGenerator）

    用于：email.compose_nudge 自动生成对方承诺到期的催促消息
    注意：必须先在 PromiseLink 创建 todo 才能调用
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
```

---

## 四、旧规划遗漏的关键端点（建议补充）

### 4.1 必须补充（高价值）

| 端点 | 用途 | 优先级 |
|------|------|--------|
| `GET /api/v1/promises/stats` | 承诺双视角统计（my/their 履约率）| 🔴 P0 |
| `GET /api/v1/dashboard/morning-brief` | 每日晨间摘要（早报核心）| 🔴 P0 |
| `GET /api/v1/dashboard/care-reminders` | 关怀提醒（温情提醒核心）| 🔴 P0 |
| `GET /api/v1/reminders/daily` | 每日提醒列表（含疲劳度控制）| 🔴 P0 |
| `GET /api/v1/reminders/preferences` | 提醒偏好配置 | 🟡 P1 |
| `GET /api/v1/persons/{entity_id}/relationship-brief/aggregated` | 12 模块聚合视图 | 🔴 P0 |
| `GET /api/v1/dashboard/relationship-health` | 关系健康度 | 🟡 P1 |
| `GET /api/v1/scheduled-events` | 排程事件列表（支持 status/时间过滤）| 🔴 P0 |

### 4.2 可选补充（中价值）

| 端点 | 用途 | 优先级 |
|------|------|--------|
| `GET /api/v1/entities/{entity_id}/stage-info` | 客户关系阶段 | 🟢 P2 |
| `GET /api/v1/export/{user_id}` | 数据可携带导出 | 🟢 P2 |
| `GET /api/v1/entities/duplicates` | 重复实体检测 | 🟢 P2 |
| `POST /api/v1/events` | 触发完整管线（含承诺分析）| 🟡 P1 |

---

## 五、推荐集成接口清单（v1.0.0 修订版）

按"客户管理 / 客户跟进 / 定时任务 / 报告"四大场景列出**已确认存在**的 9 个核心端点：

### 5.1 客户管理（5 个端点）

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/v1/entities` | GET | CRM 客户列表 |
| `/api/v1/entities/{entity_id}` | GET | 客户详情 |
| `/api/v1/entities/dormant` | GET | 沉默客户 |
| `/api/v1/entities/{entity_id}/stage-info` | GET | 关系阶段 |
| `/api/v1/persons/{entity_id}/relationship-brief/aggregated` | GET | 12 模块视图 |

### 5.2 客户跟进（3 个端点）

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/v1/todos` | GET | 任务列表 |
| `/api/v1/promises` | GET | 承诺列表 |
| `/api/v1/promises/{todo_id}/nudge-draft` | GET | 催促消息草稿 |
| `/api/v1/promises/stats` | GET | 履约统计 |

### 5.3 定时任务（1 个端点）

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/v1/scheduled-events` | POST/GET | 创建/查询排程事件 |

### 5.4 报告/摘要（3 个端点）

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/v1/dashboard/morning-brief` | GET | 每日晨间摘要 |
| `/api/v1/dashboard/care-reminders` | GET | 关怀提醒 |
| `/api/v1/reminders/daily` | GET | 每日提醒 |

**总计 12 个核心端点**（已 100% 确认存在），均已纳入 [PROMISELINK_REUSE_PLAN.md](PROMISELINK_REUSE_PLAN.md) 修订版。

---

## 六、希望 PromiseLink 项目组增强的 10 项提案

### 6.1 高优先级（必须）

#### ENH-PL-01：承诺分析的同步端点（用于 OPC-Agents email_skill 实时调用）

**问题**：当前 POST `/events` 触发异步管线，无法在用户"发邮件前评估承诺方向"时同步使用。

**建议**：新增端点：
```http
POST /api/v1/promises/analyze-bidirectional
Content-Type: application/json

{
  "title": "对方答应 9 月 15 日前交付初稿",
  "description": "补充技术细节",
  "related_entity": "张总"
}

Response 200:
{
  "action_type": "their_promise",
  "confidence": 0.85,
  "evidence_quote": "对方答应",
  "related_entity_id": "uuid|null"
}
```

**使用场景**：OPC-Agents email.compose_followup 调用，实时判断当前待办是"我承诺"还是"对方承诺"。

#### ENH-PL-02：催促消息的 POST 版本（无 todo_id 直接生成）

**问题**：当前 GET `/promises/{todo_id}/nudge-draft` 必须先创建 todo，无法用于"实时起草催收邮件"。

**建议**：新增端点：
```http
POST /api/v1/promises/nudge-draft
Content-Type: application/json

{
  "entity_name": "张总",
  "promise_description": "交付初稿",
  "due_date": "2026-09-15",
  "overdue_days": 3
}

Response 200:
{
  "nudge_text": "Hi 张总...",
  "is_fallback": false
}
```

**使用场景**：OPC-Agents email.compose_nudge 实时生成温和催促消息。

#### ENH-PL-03：实体抽取的轻量同步端点

**问题**：POST `/events` 触发完整 13 步管线（30 秒+），对 OPC-Agents "实时从一段文字提取客户名" 场景过重。

**建议**：新增端点：
```http
POST /api/v1/entities/extract-quick
Content-Type: application/json

{
  "raw_text": "今天和张总（ABC科技 CEO）开会...",
  "hint_type": "person"
}

Response 200:
{
  "persons": [{"name": "张总", "company": "ABC科技", "title": "CEO", "confidence": 0.92}],
  "extraction_took_seconds": 2.1
}
```

**使用场景**：OPC-Agents 用户粘贴会议纪要 → 实时显示提取的客户列表（无需走完整管线）。

### 6.2 中优先级（推荐）

#### ENH-PL-04：CRM 标准字段映射

**问题**：PromiseLink Entity 用 `properties.basic.company/title/phone/email`，OPC-Agents CRM 用平铺字段 `customer.company/title/phone/email`。

**建议**：新增端点或字段：
```http
GET /api/v1/entities/{entity_id}/crm-export

Response 200:
{
  "name": "张总",
  "company": "ABC科技",
  "title": "CEO",
  "phone": "13800138000",
  "email": "zhang@abc.com",
  "source": "card_save",
  "first_contact_date": "2026-08-01",
  "last_interaction_date": "2026-09-10",
  "relationship_stage": "active"
}
```

**使用场景**：OPC-Agents 导出客户档案到本地 CRM。

#### ENH-PL-05：定时任务的 cron 表达式支持

**问题**：当前 ScheduledEvent 只支持单次 `scheduled_at`，OPC-Agents 需要"每周一 9:00 复定时"。

**建议**：扩展 ScheduledEvent：
```http
POST /api/v1/scheduled-events
Content-Type: application/json

{
  "schedule_type": "recurring",
  "cron_expression": "0 9 * * 1",
  "topic": "每周生成营销周报",
  "action_payload": {"task_type": "report_weekly", "params": {...}},
  "next_run_at": "2026-09-15T09:00:00+08:00"
}
```

**使用场景**：OPC-Agents scheduler 直接复用为后端。

#### ENH-PL-06：批量承诺统计

**问题**：当前 `/promises/stats` 返回全量聚合，OPC-Agents 需要按客户/时间段筛选。

**建议**：扩展 stats 端点：
```http
GET /api/v1/promises/stats?entity_id=xxx&since=2026-09-01
```

**使用场景**：在客户详情页显示"过去 30 天此客户的双向承诺情况"。

#### ENH-PL-07：跨实体关联查询

**问题**：当前 `/associations` 列出所有关联，但无"按实体查询对方"接口。

**建议**：新增端点：
```http
GET /api/v1/persons/{entity_id}/associations?role=partner|client|friend
```

**使用场景**：OPC-Agents 客户详情页显示"此人的人脉网络"。

### 6.3 低优先级（可选）

#### ENH-PL-08：Webhook 机制

**问题**：当前定时事件的状态变化（pending → overdue → completed）OPC-Agents 只能轮询。

**建议**：新增端点：
```http
POST /api/v1/webhooks/subscribe
Content-Type: application/json

{
  "callback_url": "https://opc-agents.example.com/webhook/promiselink",
  "events": ["scheduled_event.overdue", "promise.fulfilled", "entity.created"]
}
```

**使用场景**：PromiseLink 状态变更实时推送到 OPC-Agents。

#### ENH-PL-09：OPC-Agents 用户身份标识

**问题**：OPC-Agents 用户可能与 PromiseLink 用户不同（如 OPC-Agents 服务多账号）。

**建议**：在 ScheduledEvent / Promise 上加 `external_user_id` 字段（可选），允许 OPC-Agents 传入映射 ID。

#### ENH-PL-10：批量事件接口

**问题**：当前 POST `/events` 一次一个，OPC-Agents scheduler 批量触发多个任务时开销大。

**建议**：新增端点：
```http
POST /api/v1/events/batch
Content-Type: application/json

{
  "events": [{...}, {...}, ...]
}
```

---

## 七、HTTP 错误码与失败降级规范

### 7.1 错误码处理建议

| 状态码 | 含义 | OPC-Agents 处理 |
|--------|------|---------------|
| 200/201 | 成功 | 正常处理 |
| 400 | 参数错误 | 记录错误 + 降级（不重试）|
| 401 | 未认证 | token 失效 → 重新登录 |
| 403 | 权限不足 | 降级到本地能力 |
| 404 | 资源不存在 | 记录 + 降级 |
| 409 | 冲突（乐观锁）| 重新获取最新数据 |
| 422 | 业务校验失败 | 提示用户 + 降级 |
| 429 | 限流 | retry with backoff（指数退避）|
| 500+ | 服务器错误 | 触发 circuit breaker |
| timeout | 网络超时 | 触发 circuit breaker |

### 7.2 限流处理

PromiseLink 端通过 `rate_limit_dependency` 限流：
- 401/403 → 立即降级
- 429 → 等待 Retry-After 秒数后重试
- 连续失败 → 触发 OPC-Agents 端 circuit breaker

---

## 八、本报告变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-01 | 初版创建：67 个端点逐项校准 + 10 项增强需求 |

---

## 九、参考

- [PROMISELINK_REUSE_PLAN.md](PROMISELINK_REUSE_PLAN.md) — 复用方案（已根据本报告修正路径）
- [OPC_AGENTS_ROADMAP_V1.0.0.md](OPC_AGENTS_ROADMAP_V1.0.0.md) — OPC-Agents 后期规划
- PromiseLink 源码：`/Users/lin/trae_projects/PromiseLink/src/promiselink/`

---

*最后更新: 2026-08-01*
*校准负责人: OPC-Agents 团队*
*下次校准: PromiseLink v0.10.0 发布后（约 2026-09-15）*