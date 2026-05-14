# OPC-Agents API 文档

> 版本: v0.1.8 | 最后更新: 2026-05-14

本文档列出 OPC-Agents 所有公开API，按模块分组。每个API包含函数签名、参数说明和返回值格式。

---

## 目录

- [data_manager — 数据管理](#data_manager--数据管理)
- [intent_types — 意图类型](#intent_types--意图类型)
- [protocols — Protocol接口](#protocols--protocol接口)
- [email_skill — 邮件技能](#email_skill--邮件技能)
- [finance_skill — 财务技能](#finance_skill--财务技能)
- [task_skill — 待办技能](#task_skill--待办技能)
- [crm_skill — CRM技能](#crm_skill--crm技能)
- [social_skill — 社媒技能](#social_skill--社媒技能)
- [proposal_skill — 报价技能](#proposal_skill--报价技能)
- [invoice_skill — 发票技能](#invoice_skill--发票技能)
- [report_skill — 报告技能](#report_skill--报告技能)
- [calendar_skill — 日程技能](#calendar_skill--日程技能)
- [competitor_skill — 竞品技能](#competitor_skill--竞品技能)
- [pricing_skill — 定价技能](#pricing_skill--定价技能)
- [tax_reminder_skill — 税务提醒技能](#tax_reminder_skill--税务提醒技能)
- [dashboard_skill — 看板技能](#dashboard_skill--看板技能)
- [knowledge_skill — 知识库技能](#knowledge_skill--知识库技能)
- [skill_marketplace — 技能市场](#skill_marketplace--技能市场)
- [user_profile — 用户画像](#user_profile--用户画像)

---

## data_manager — 数据管理

> 模块路径: `opc_manager.data_manager`

SQLite统一存储层，提供数据库初始化、查询、写入、事务、加密和偏好管理。

### `init_db()`

初始化数据库，创建所有表结构，执行迁移和种子数据。

```python
def init_db() -> None
```

**返回值**: 无

---

### `execute_query(sql, params)`

执行SQL查询，返回结果列表。

```python
def execute_query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `sql` | `str` | SQL查询语句 |
| `params` | `tuple` | 查询参数（防SQL注入） |

**返回值**: `List[Dict[str, Any]]` — 查询结果行列表，每行为字典

---

### `execute_write(sql, params)`

执行SQL写入操作（INSERT/UPDATE/DELETE），返回影响行数。

```python
def execute_write(sql: str, params: tuple = ()) -> int
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `sql` | `str` | SQL写入语句 |
| `params` | `tuple` | 写入参数 |

**返回值**: `int` — 总变更行数

---

### `execute_transaction(statements)`

在事务中执行多条SQL语句，任一失败则全部回滚。

```python
def execute_transaction(statements: List[tuple]) -> bool
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `statements` | `List[tuple]` | SQL语句列表，每项为 `(sql, params)` 元组 |

**返回值**: `bool` — 事务是否成功

---

### `gen_id()`

生成16位唯一ID（基于UUID4截取）。

```python
def gen_id() -> str
```

**返回值**: `str` — 16位唯一标识符

---

### `encrypt_field(plaintext)`

使用AES(Fernet)加密敏感字段。**必须设置 `OPC_ENCRYPTION_KEY` 环境变量**，否则抛出 `RuntimeError`。

```python
def encrypt_field(plaintext: str) -> str
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `plaintext` | `str` | 明文字符串 |

**返回值**: `str` — 加密后的字符串（空输入返回空字符串）

**异常**: `RuntimeError` — 当 `OPC_ENCRYPTION_KEY` 未设置时抛出，拒绝使用默认密钥加密

---

### `decrypt_field(ciphertext)`

解密AES(Fernet)加密的字段。

```python
def decrypt_field(ciphertext: str) -> Optional[str]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `ciphertext` | `str` | 加密字符串 |

**返回值**: `Optional[str]` — 解密后的明文（空输入返回空字符串，解密失败返回 `None`）

---

### `get_preference(key, default)`

获取用户偏好值。

```python
def get_preference(key: str, default: str = "") -> str
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `key` | `str` | 偏好键名 |
| `default` | `str` | 默认值 |

**返回值**: `str` — 偏好值或默认值

---

### `set_preference(key, value)`

设置用户偏好值。

```python
def set_preference(key: str, value: str) -> None
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `key` | `str` | 偏好键名 |
| `value` | `str` | 偏好值 |

**返回值**: 无

---

### `backup_db()`

备份数据库文件，保留最近7个备份。

```python
def backup_db() -> Optional[str]
```

**返回值**: `Optional[str]` — 备份文件路径，失败返回 `None`

---

### `_ensure_db(func)`

装饰器，确保数据库已初始化后再执行被装饰函数。

```python
def _ensure_db(func: Callable) -> Callable
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `func` | `Callable` | 被装饰的函数 |

**返回值**: `Callable` — 包装后的函数，调用前自动执行 `init_db()`

---

## intent_types — 意图类型

> 模块路径: `opc_manager.intent_types`

意图类型的唯一事实来源（SSOT），提供枚举、关键词映射、步骤映射和技能映射。

### `IntentType`

意图类型枚举，包含所有支持的意图分类。

```python
class IntentType(Enum):
    UNKNOWN = "unknown"
    ANALYSIS = "analysis"
    CREATION = "creation"
    OPERATION = "operation"
    SEARCH = "search"
    NOTIFICATION = "notification"
    COMBINED = "combined"
    EMAIL = "email"
    FINANCE = "finance"
    TASK = "task"
    CRM = "crm"
    SOCIAL = "social"
    PROPOSAL = "proposal"
    INVOICE = "invoice"
    REPORT = "report"
    CALENDAR = "calendar"
    COMPETITOR = "competitor"
    PRICING = "pricing"
    TAX_REMINDER = "tax_reminder"
    DASHBOARD = "dashboard"
    KNOWLEDGE = "knowledge"
    EXTENDED_SKILL = "extended_skill"
```

---

### `INTENT_KEYWORDS`

意图类型到触发关键词的映射表。

```python
INTENT_KEYWORDS: Dict[IntentType, List[str]]
```

**用途**: 策略脑通过关键词匹配确定用户意图类型。每个 `IntentType` 对应一组中文触发关键词。

---

### `INTENT_STEP_MAP`

意图类型到执行步骤的映射表。

```python
INTENT_STEP_MAP: Dict[IntentType, Tuple[str, str]]
```

**返回值**: 每项为 `(skill_id, step_name)` 元组，例如 `IntentType.EMAIL → ("email", "邮件管理")`

---

### `SKILL_INTENT_MAP`

技能ID到意图类型的反向映射表。

```python
SKILL_INTENT_MAP: Dict[str, IntentType]
```

**用途**: 从技能ID反查对应的意图类型，用于技能注册和路由。

---

## protocols — Protocol接口

> 模块路径: `opc_manager.protocols`

Protocol接口定义和NullProvider降级模式，确保外部依赖不可用时系统仍能正常运行。

### `LLMServiceProtocol`

LLM服务协议接口，扩展自 `LLMProvider`，增加 `analyze` 方法。

```python
@runtime_checkable
class LLMServiceProtocol(Protocol):
    def is_available(self) -> bool: ...
    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> Optional[str]: ...
    def analyze(self, text: str, **kwargs) -> Optional[Dict[str, Any]]: ...
```

| 方法 | 返回类型 | 说明 |
|------|---------|------|
| `is_available()` | `bool` | LLM服务是否可用 |
| `generate(prompt, system_prompt, **kwargs)` | `Optional[str]` | 生成文本 |
| `analyze(text, **kwargs)` | `Optional[Dict[str, Any]]` | 分析文本，返回结构化结果 |

---

### `LLMProvider`

基础LLM协议接口。

```python
@runtime_checkable
class LLMProvider(Protocol):
    def is_available(self) -> bool: ...
    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> Optional[str]: ...
```

---

### `NullLLMProvider`

LLM不可用时的降级提供者，`is_available()` 返回 `False`，`generate()` 返回 `None`。

---

### Provider获取函数

| 函数 | 返回类型 | 说明 |
|------|---------|------|
| `get_llm_provider()` | `LLMProvider` | 获取LLM提供者（不可用则返回NullLLMProvider） |
| `get_search_provider()` | `SearchProvider` | 获取搜索提供者 |
| `get_secure_provider()` | `SecureProvider` | 获取安全存储提供者 |
| `get_monitor_provider()` | `MonitorProvider` | 获取监控提供者 |

---

## email_skill — 邮件技能

> 模块路径: `opc_manager.email_skill`

SMTP邮件发送、模板管理和发送历史。

### `send_email(to, subject, body, cc, template_name)`

发送邮件，支持频率限制和大小限制。

```python
def send_email(to: str, subject: str, body: str,
               cc: str = "", template_name: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `to` | `str` | 收件人邮箱地址 |
| `subject` | `str` | 邮件主题 |
| `body` | `str` | 邮件正文（最大50KB） |
| `cc` | `str` | 抄送地址（可选） |
| `template_name` | `str` | 使用的模板名称（可选） |

**返回值**:
```json
{"success": true, "message": "邮件已发送至 xxx", "id": "abc123"}
// 或
{"success": false, "error": "错误描述"}
```

**限制**: 每日最多100封，同一收件人1小时内最多3封

---

### `send_email_async(to, subject, body, cc, template_name)`

异步发送邮件，非阻塞版本。

```python
async def send_email_async(to: str, subject: str, body: str,
                           cc: str = "", template_name: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `to` | `str` | 收件人邮箱地址 |
| `subject` | `str` | 邮件主题 |
| `body` | `str` | 邮件正文（最大50KB） |
| `cc` | `str` | 抄送地址（可选） |
| `template_name` | `str` | 使用的模板名称（可选） |

**返回值**: 与 `send_email` 相同

---

### `execute_goal(goal, _context, **kwargs)`

邮件技能统一委托入口，根据目标文本自动路由到对应操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"发邮件给xxx"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

### `render_template(name, variables)`

渲染邮件模板，替换模板变量。

```python
def render_template(name: str, variables: Dict[str, str]) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 模板名称 |
| `variables` | `Dict[str, str]` | 模板变量键值对 |

**返回值**:
```json
{"success": true, "subject": "渲染后主题", "body": "渲染后正文"}
// 或
{"success": false, "error": "模板不存在/变量未替换"}
```

---

### `create_template(name, subject, body, variables)`

创建或替换邮件模板。

```python
def create_template(name: str, subject: str, body: str, variables: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 模板名称 |
| `subject` | `str` | 邮件主题模板 |
| `body` | `str` | 邮件正文模板 |
| `variables` | `str` | 变量列表（逗号分隔） |

**返回值**: `{"success": bool, "message": str}`

---

### `list_templates()`

列出所有邮件模板。

```python
def list_templates() -> List[Dict[str, Any]]
```

**返回值**: 模板列表，每项包含 `name`, `subject`, `variables`

---

### `list_email_history(limit)`

列出邮件发送历史。

```python
def list_email_history(limit: int = 20) -> List[Dict[str, Any]]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `limit` | `int` | 返回条数（默认20） |

**返回值**: 邮件历史列表，每项包含 `id`, `to_addr`, `subject`, `status`, `template_name`, `created_at`

---

### `save_smtp_config(config)`

保存SMTP配置，密码自动加密存储。

```python
def save_smtp_config(config: Dict[str, Any]) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `Dict[str, Any]` | SMTP配置（host, port, username, password, ssl, from_addr） |

**返回值**: `{"success": bool, "message": str}`

---

## finance_skill — 财务技能

> 模块路径: `opc_manager.finance_skill`

收支记录、月度报表和趋势分析。

### `record_income(amount, source, category, date, note)`

记录一笔收入。

```python
def record_income(amount: float, source: str, category: str = "咨询费",
                  date: str = "", note: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `amount` | `float` | 金额（必须>0） |
| `source` | `str` | 收入来源 |
| `category` | `str` | 分类（默认"咨询费"） |
| `date` | `str` | 日期（YYYY-MM-DD，默认今天） |
| `note` | `str` | 备注 |

**返回值**: `{"success": bool, "id": str, "message": str}`

---

### `record_expense(amount, source, category, date, note)`

记录一笔支出。

```python
def record_expense(amount: float, source: str, category: str = "其他支出",
                   date: str = "", note: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `amount` | `float` | 金额（必须>0） |
| `source` | `str` | 支出来源 |
| `category` | `str` | 分类（默认"其他支出"） |
| `date` | `str` | 日期（YYYY-MM-DD，默认今天） |
| `note` | `str` | 备注 |

**返回值**: `{"success": bool, "id": str, "message": str}`

---

### `get_monthly_report(year_month)`

生成月度财务报告。

```python
def get_monthly_report(year_month: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `year_month` | `str` | 年月（YYYY-MM，默认当月） |

**返回值**:
```json
{
  "success": true,
  "year_month": "2026-05",
  "income": 10000.00,
  "expense": 5000.00,
  "profit": 5000.00,
  "income_change": 1000.00,
  "expense_change": -500.00,
  "income_by_category": {"咨询费": 8000.00, "培训费": 2000.00},
  "expense_by_category": {"工具订阅": 3000.00, "税费": 2000.00}
}
```

---

### `get_trend(months)`

获取近N个月的收支趋势。

```python
def get_trend(months: int = 6) -> List[Dict[str, Any]]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `months` | `int` | 月数（默认6） |

**返回值**: 月度趋势列表，每项包含 `year_month`, `income`, `expense`, `profit`

---

### `parse_amount_from_text(text)`

从自然语言文本中解析金额。

```python
def parse_amount_from_text(text: str) -> Optional[float]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | `str` | 包含金额的文本 |

**返回值**: `Optional[float]` — 解析出的金额，无法解析返回 `None`

---

### `execute_goal(goal, _context, **kwargs)`

财务技能统一委托入口，根据目标文本自动路由到收入/支出/报表/趋势等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"记一笔收入3000元"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## task_skill — 待办技能

> 模块路径: `opc_manager.task_skill`

待办任务创建、完成和查询。

### `create_task(title, description, priority, due_date, tags)`

创建待办任务。

```python
def create_task(title: str, description: str = "", priority: int = 2,
                due_date: str = "", tags: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `title` | `str` | 任务标题（必填） |
| `description` | `str` | 任务描述 |
| `priority` | `int` | 优先级（0=P0紧急, 1=P1重要, 2=P2普通, 3=P3低） |
| `due_date` | `str` | 截止日期（YYYY-MM-DD） |
| `tags` | `str` | 标签 |

**返回值**: `{"success": bool, "id": str, "message": str}`

---

### `complete_task(task_id, title_keyword)`

完成待办任务（按ID或标题关键词匹配）。

```python
def complete_task(task_id: str = "", title_keyword: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | `str` | 任务ID |
| `title_keyword` | `str` | 标题关键词（task_id为空时使用） |

**返回值**: `{"success": bool, "message": str}`

---

### `list_tasks(status, due_date, priority_max, limit)`

列出待办任务，支持多条件筛选。

```python
def list_tasks(status: str = "", due_date: str = "", priority_max: int = -1,
               limit: int = 50) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | `str` | 状态筛选（pending/in_progress/done/cancelled） |
| `due_date` | `str` | 截止日期上限 |
| `priority_max` | `int` | 优先级上限（-1表示不限） |
| `limit` | `int` | 返回条数（默认50） |

**返回值**: `{"success": bool, "tasks": List, "count": int}`

---

### `get_today_tasks()`

获取今日待办任务（含逾期未完成的）。

```python
def get_today_tasks() -> Dict[str, Any]
```

**返回值**: `{"success": bool, "tasks": List, "count": int}`

---

### `execute_goal(goal, _context, **kwargs)`

待办技能统一委托入口，根据目标文本自动路由到创建/完成/列表/今日待办等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"帮我创建一个待办"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## crm_skill — CRM技能

> 模块路径: `opc_manager.crm_skill`

客户关系管理，支持敏感字段加密存储。

### `add_customer(name, company, title, phone, email, source, tags)`

添加客户，手机号和邮箱自动加密存储。

```python
def add_customer(name: str, company: str = "", title: str = "",
                 phone: str = "", email: str = "", source: str = "",
                 tags: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 客户姓名（必填） |
| `company` | `str` | 公司名称 |
| `title` | `str` | 职位 |
| `phone` | `str` | 手机号（加密存储） |
| `email` | `str` | 邮箱（加密存储） |
| `source` | `str` | 来源 |
| `tags` | `str` | 标签 |

**返回值**: `{"success": bool, "id": str, "message": str}`

---

### `get_customer(customer_id, name)`

查询客户详情（含合作记录），敏感字段自动解密。

```python
def get_customer(customer_id: str = "", name: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `customer_id` | `str` | 客户ID |
| `name` | `str` | 客户姓名（模糊匹配） |

**返回值**: `{"success": bool, "customer": Dict}` — customer包含客户信息和deals列表

---

### `search_customers(company, tags, status, source)`

多条件搜索客户。

```python
def search_customers(company: str = "", tags: str = "",
                     status: str = "", source: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `company` | `str` | 公司名称（模糊匹配） |
| `tags` | `str` | 标签（逗号分隔） |
| `status` | `str` | 状态（potential/first_deal/active/silent/lost） |
| `source` | `str` | 来源 |

**返回值**: `{"success": bool, "customers": List, "count": int}`

---

### `add_deal(customer_id, description, amount, date, status)`

添加合作记录。closed_won时自动触发：客户状态更新 + 收入记录（CRM→Finance协作）。

```python
def add_deal(customer_id: str, description: str, amount: float = 0,
             date: str = "", status: str = "negotiating") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `customer_id` | `str` | 客户ID |
| `description` | `str` | 合作描述 |
| `amount` | `float` | 金额 |
| `date` | `str` | 日期（默认今天） |
| `status` | `str` | 状态（negotiating/closed_won/closed_lost） |

**返回值**: `{"success": bool, "id": str, "message": str}`

---

### `get_silent_customers(days)`

获取沉默客户列表（超过N天未联系）。

```python
def get_silent_customers(days: int = 30) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `days` | `int` | 沉默天数阈值（默认30） |

**返回值**: `{"success": bool, "customers": List, "count": int, "silent_days": int}`

---

### `get_customer_stats()`

获取客户统计概览。

```python
def get_customer_stats() -> Dict[str, Any]
```

**返回值**:
```json
{
  "success": true,
  "total": 50,
  "potential": 20,
  "first_deal": 10,
  "active": 15,
  "silent": 3,
  "lost": 2
}
```

---

### `execute_goal(goal, _context, **kwargs)`

CRM技能统一委托入口，根据目标文本自动路由到添加客户/查询/搜索/合作记录/沉默客户等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"添加客户张三"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## social_skill — 社媒技能

> 模块路径: `opc_manager.social_skill`

5大平台内容生成和草稿管理。

### `generate_content(platform, topic, key_points, tone)`

生成社媒内容并保存为草稿。

```python
def generate_content(platform: str, topic: str, key_points: str = "",
                     tone: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `platform` | `str` | 平台（小红书/公众号/推特/微博/知乎） |
| `topic` | `str` | 主题 |
| `key_points` | `str` | 要点（顿号分隔） |
| `tone` | `str` | 语气风格（默认按平台风格） |

**返回值**: `{"success": bool, "id": str, "platform": str, "title": str, "body": str, "tags": List, "status": "draft", "publish_guide": str}`

---

### `list_drafts(platform)`

列出未发布的草稿内容。

```python
def list_drafts(platform: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `platform` | `str` | 按平台筛选（可选） |

**返回值**: `{"success": bool, "drafts": List, "count": int}`

---

### `mark_published(content_id)`

标记内容为已发布。

```python
def mark_published(content_id: str) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `content_id` | `str` | 内容ID |

**返回值**: `{"success": bool, "message": str}`

---

### `execute_goal(goal, _context, **kwargs)`

社媒技能统一委托入口，根据目标文本自动路由到内容生成/草稿列表/标记发布等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"帮我写一篇小红书"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## proposal_skill — 报价技能

> 模块路径: `opc_manager.proposal_skill`

服务报价单生成和管理。

### `create_proposal(client_name, service_type, items, valid_days, note)`

创建报价单，自动生成Markdown文档。

```python
def create_proposal(client_name: str, service_type: str = "通用",
                    items: List[Dict[str, Any]] = None,
                    valid_days: int = 30,
                    note: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `client_name` | `str` | 客户名称（必填） |
| `service_type` | `str` | 服务类型（咨询/培训/设计/开发/通用） |
| `items` | `List[Dict]` | 服务项目列表（为空时使用模板） |
| `valid_days` | `int` | 有效天数（默认30） |
| `note` | `str` | 备注 |

**返回值**: `{"success": bool, "id": str, "total": float, "valid_until": str, "markdown": str}`

---

### `list_proposals(status)`

列出报价单。

```python
def list_proposals(status: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | `str` | 状态筛选（draft/sent/accepted/rejected/expired） |

**返回值**: `{"success": bool, "proposals": List, "count": int}`

---

### `update_proposal_status(proposal_id, status)`

更新报价单状态。

```python
def update_proposal_status(proposal_id: str, status: str) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `proposal_id` | `str` | 报价单ID |
| `status` | `str` | 新状态（draft/sent/accepted/rejected/expired） |

**返回值**: `{"success": bool, "message": str}`

---

### `execute_goal(goal, _context, **kwargs)`

报价技能统一委托入口，根据目标文本自动路由到创建报价/列表/状态更新等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"帮我给客户做报价单"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## invoice_skill — 发票技能

> 模块路径: `opc_manager.invoice_skill`

发票生成和税务日历查询。

### `create_invoice(client_name, amount, item, tax_rate, invoice_type)`

创建发票，自动计算税额。

```python
def create_invoice(client_name: str, amount: float, item: str = "服务费",
                   tax_rate: float = 0.06, invoice_type: str = "增值税普通发票") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `client_name` | `str` | 客户名称（必填） |
| `amount` | `float` | 金额（必须>0） |
| `item` | `str` | 开票项目 |
| `tax_rate` | `float` | 税率（默认0.06即6%） |
| `invoice_type` | `str` | 发票类型 |

**返回值**: `{"success": bool, "id": str, "invoice_no": str, "amount": float, "tax_amount": float, "total_with_tax": float, "markdown": str}`

---

### `list_invoices(status)`

列出发票。

```python
def list_invoices(status: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | `str` | 状态筛选（pending/paid/cancelled） |

**返回值**: `{"success": bool, "invoices": List, "count": int}`

---

### `get_tax_calendar(month)`

获取税务日历。

```python
def get_tax_calendar(month: int = 0) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `month` | `int` | 月份（0=当月） |

**返回值**: `{"success": bool, "current_month": int, "this_month": List, "next_month": List}`

---

### `execute_goal(goal, _context, **kwargs)`

发票技能统一委托入口，根据目标文本自动路由到创建发票/列表/税务日历等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"帮我开一张发票"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## report_skill — 报告技能

> 模块路径: `opc_manager.report_skill`

周报/月报/年报自动生成，聚合多技能数据。

### `generate_weekly_report(week_note)`

生成周报。

```python
def generate_weekly_report(week_note: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `week_note` | `str` | 本周备注 |

**返回值**: `{"success": bool, "report_type": "weekly", "period": str, "filepath": str, "markdown": str}`

---

### `generate_monthly_report(year_month)`

生成月度经营报告。

```python
def generate_monthly_report(year_month: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `year_month` | `str` | 年月（YYYY-MM，默认当月） |

**返回值**: `{"success": bool, "report_type": "monthly", "period": str, "filepath": str, "markdown": str}`

---

### `generate_annual_report(year)`

生成年度经营报告。

```python
def generate_annual_report(year: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `year` | `str` | 年份（默认今年） |

**返回值**: `{"success": bool, "report_type": "annual", "period": str, "filepath": str, "markdown": str}`

---

### `execute_goal(goal, _context, **kwargs)`

报告技能统一委托入口，根据目标文本自动路由到周报/月报/年报生成。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"帮我生成周报"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## calendar_skill — 日程技能

> 模块路径: `opc_manager.calendar_skill`

日程事件管理和提醒。

### `add_event(title, date, time_str, duration_min, description, reminder_min, repeat)`

添加日程事件。

```python
def add_event(title: str, date: str, time_str: str = "",
              duration_min: int = 60, description: str = "",
              reminder_min: int = 15, repeat: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `title` | `str` | 日程标题（必填） |
| `date` | `str` | 日期（YYYY-MM-DD，必填） |
| `time_str` | `str` | 时间（HH:MM） |
| `duration_min` | `int` | 时长（分钟，默认60） |
| `description` | `str` | 描述 |
| `reminder_min` | `int` | 提前提醒分钟数（默认15） |
| `repeat` | `str` | 重复规则 |

**返回值**: `{"success": bool, "id": str, "message": str, "reminder": str}`

---

### `get_day_schedule(date)`

获取某天的日程安排。

```python
def get_day_schedule(date: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `date` | `str` | 日期（YYYY-MM-DD，默认今天） |

**返回值**: `{"success": bool, "date": str, "events": List, "count": int}`

---

### `get_week_schedule(start_date)`

获取一周日程。

```python
def get_week_schedule(start_date: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `start_date` | `str` | 周起始日期（默认本周一） |

**返回值**: `{"success": bool, "start_date": str, "days": List}`

---

### `cancel_event(event_id)`

取消日程事件。

```python
def cancel_event(event_id: str) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `event_id` | `str` | 事件ID |

**返回值**: `{"success": bool, "message": str}`

---

### `get_upcoming_reminders(minutes_ahead)`

获取即将到来的提醒。

```python
def get_upcoming_reminders(minutes_ahead: int = 60) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `minutes_ahead` | `int` | 提前分钟数（默认60） |

**返回值**: `{"success": bool, "reminders": List, "count": int}` — 每项含 `minutes_until`

---

### `execute_goal(goal, _context, **kwargs)`

日程技能统一委托入口，根据目标文本自动路由到添加事件/日程查询/取消/提醒等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"帮我安排明天下午3点开会"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## competitor_skill — 竞品技能

> 模块路径: `opc_manager.competitor_skill`

竞品监控、动态记录和分析报告。

### `add_competitor(name, url, keywords, note)`

添加竞品监控对象。

```python
def add_competitor(name: str, url: str = "", keywords: str = "",
                   note: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 竞品名称（必填） |
| `url` | `str` | 竞品网址 |
| `keywords` | `str` | 关注关键词 |
| `note` | `str` | 备注 |

**返回值**: `{"success": bool, "id": str, "message": str}`

---

### `list_competitors()`

列出所有竞品（含动态数和最近更新时间）。

```python
def list_competitors() -> Dict[str, Any]
```

**返回值**: `{"success": bool, "competitors": List, "count": int}`

---

### `record_snapshot(competitor_id, changes, source)`

记录竞品动态快照。

```python
def record_snapshot(competitor_id: str, changes: str = "",
                    source: str = "手动记录") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `competitor_id` | `str` | 竞品ID |
| `changes` | `str` | 变更描述 |
| `source` | `str` | 信息来源 |

**返回值**: `{"success": bool, "message": str, "snapshot_count": int}`

---

### `get_competitor_report(competitor_id)`

生成竞品分析报告。不传competitor_id则生成总览报告。

```python
def get_competitor_report(competitor_id: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `competitor_id` | `str` | 竞品ID（空=总览） |

**返回值**: `{"success": bool, "competitor": str, "markdown": str}`

---

### `remove_competitor(competitor_id)`

移除竞品（级联删除动态记录）。

```python
def remove_competitor(competitor_id: str) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `competitor_id` | `str` | 竞品ID |

**返回值**: `{"success": bool, "message": str}`

---

### `execute_goal(goal, _context, **kwargs)`

竞品技能统一委托入口，根据目标文本自动路由到添加竞品/列表/动态记录/分析报告等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"帮我监控竞品A"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## pricing_skill — 定价技能

> 模块路径: `opc_manager.pricing_skill`

4种定价方法、行业基准费率和定价建议。

### `calculate_pricing(method, service_type, cost, hours, market_avg, level)`

按指定方法计算定价。

```python
def calculate_pricing(method: str, service_type: str = "通用",
                      cost: float = 0, hours: float = 0,
                      market_avg: float = 0, level: str = "mid") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `method` | `str` | 定价方法（成本定价/价值定价/竞争定价/小时费率） |
| `service_type` | `str` | 服务类型（咨询/设计/开发/培训/通用） |
| `cost` | `float` | 成本（成本/价值定价法必填） |
| `hours` | `float` | 工时（小时费率法必填） |
| `market_avg` | `float` | 市场均价（竞争定价法必填） |
| `level` | `str` | 级别（junior/mid/senior/expert） |

**返回值**: `{"success": bool, "method": str, "formula": str, "price": float, "detail": Dict}`

---

### `get_hourly_benchmarks(service_type)`

获取行业小时费率基准。

```python
def get_hourly_benchmarks(service_type: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `service_type` | `str` | 服务类型（空=全部） |

**返回值**: `{"success": bool, "rates": Dict}` — 按级别(junior/mid/senior/expert)列出费率

---

### `suggest_pricing(service_type, cost, hours)`

综合多种方法给出定价建议。

```python
def suggest_pricing(service_type: str = "通用", cost: float = 0,
                    hours: float = 0) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `service_type` | `str` | 服务类型 |
| `cost` | `float` | 成本 |
| `hours` | `float` | 工时 |

**返回值**: `{"success": bool, "service_type": str, "suggestions": List}`

---

### `save_pricing_record(name, method, price, note)`

保存定价记录。

```python
def save_pricing_record(name: str, method: str, price: float,
                        note: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 记录名称（必填） |
| `method` | `str` | 使用的定价方法 |
| `price` | `float` | 定价（必须>0） |
| `note` | `str` | 备注 |

**返回值**: `{"success": bool, "id": str, "message": str}`

---

### `execute_goal(goal, _context, **kwargs)`

定价技能统一委托入口，根据目标文本自动路由到定价计算/基准查询/建议/记录保存等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"帮我算一下咨询怎么定价"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## tax_reminder_skill — 税务提醒技能

> 模块路径: `opc_manager.tax_reminder_skill`

税务截止日提醒和完成跟踪。

### `check_upcoming_deadlines(days_ahead)`

检查即将到来的税务截止日。

```python
def check_upcoming_deadlines(days_ahead: int = 30) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `days_ahead` | `int` | 提前天数（默认30） |

**返回值**: `{"success": bool, "check_date": str, "upcoming": List, "count": int}` — 每项含 `days_remaining` 和 `urgency`

---

### `create_reminder(task, deadline, tax_type, amount_estimate)`

创建税务提醒。

```python
def create_reminder(task: str, deadline: str, tax_type: str = "增值税",
                    amount_estimate: float = 0) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `task` | `str` | 提醒任务（必填） |
| `deadline` | `str` | 截止日期（YYYY-MM-DD，必填） |
| `tax_type` | `str` | 税种（默认"增值税"） |
| `amount_estimate` | `float` | 预估金额 |

**返回值**: `{"success": bool, "id": str, "message": str}`

---

### `complete_reminder(reminder_id)`

完成税务提醒。

```python
def complete_reminder(reminder_id: str) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `reminder_id` | `str` | 提醒ID |

**返回值**: `{"success": bool, "message": str}`

---

### `get_tax_checklist(month)`

获取月度税务清单（含完成状态）。

```python
def get_tax_checklist(month: int = 0) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `month` | `int` | 月份（0=当月） |

**返回值**: `{"success": bool, "month": int, "checklist": List, "total": int, "completed": int}`

---

### `execute_goal(goal, _context, **kwargs)`

税务提醒技能统一委托入口，根据目标文本自动路由到截止日检查/创建提醒/完成/清单等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"检查近期税务截止日"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## dashboard_skill — 看板技能

> 模块路径: `opc_manager.dashboard_skill`

经营数据仪表盘，聚合财务/CRM/待办数据。

### `get_overview()`

获取经营概览（本月财务+客户+待办）。

```python
def get_overview() -> Dict[str, Any]
```

**返回值**:
```json
{
  "success": true,
  "date": "2026-05-14",
  "finance": {"month_income": 10000, "month_expense": 5000, "month_profit": 5000},
  "crm": {"total_customers": 50, "active_customers": 15, "silent_customers": 3},
  "tasks": {"pending": 8, "overdue": 2}
}
```

---

### `get_finance_dashboard(months)`

获取财务仪表盘（含趋势和最佳/最差月份）。

```python
def get_finance_dashboard(months: int = 6) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `months` | `int` | 统计月数（默认6） |

**返回值**: `{"success": bool, "total_income": float, "total_expense": float, "avg_monthly_income": float, "best_month": Dict, "worst_month": Dict, "trend": List}`

---

### `get_crm_dashboard()`

获取CRM仪表盘。

```python
def get_crm_dashboard() -> Dict[str, Any]
```

**返回值**: `{"success": bool, "total": int, "by_status": Dict, "silent_customers": int, "silent_list": List}`

---

### `get_task_dashboard()`

获取待办仪表盘（含逾期任务）。

```python
def get_task_dashboard() -> Dict[str, Any]
```

**返回值**: `{"success": bool, "total": int, "by_status": Dict, "by_priority": Dict, "overdue_count": int, "overdue_tasks": List}`

---

### `generate_dashboard_report()`

生成完整看板报告（Markdown文件）。

```python
def generate_dashboard_report() -> Dict[str, Any]
```

**返回值**: `{"success": bool, "filepath": str, "markdown": str}`

---

### `execute_goal(goal, _context, **kwargs)`

看板技能统一委托入口，根据目标文本自动路由到概览/财务/CRM/待办仪表盘或报告生成。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"看一下经营数据"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## knowledge_skill — 知识库技能

> 模块路径: `opc_manager.knowledge_skill`

知识文章CRUD、分类和搜索。

### `create_article(title, content, tags, category)`

创建知识文章。

```python
def create_article(title: str, content: str, tags: str = "",
                   category: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `title` | `str` | 标题（必填） |
| `content` | `str` | 内容（必填） |
| `tags` | `str` | 标签（顿号分隔） |
| `category` | `str` | 分类 |

**返回值**: `{"success": bool, "id": str, "message": str, "word_count": int}`

---

### `get_article(article_id)`

获取文章详情。

```python
def get_article(article_id: str) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `article_id` | `str` | 文章ID |

**返回值**: `{"success": bool, "article": Dict}`

---

### `update_article(article_id, title, content, tags, category)`

更新文章（仅更新传入的非空字段）。

```python
def update_article(article_id: str, title: str = "", content: str = "",
                   tags: str = "", category: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `article_id` | `str` | 文章ID |
| `title` | `str` | 新标题 |
| `content` | `str` | 新内容 |
| `tags` | `str` | 新标签 |
| `category` | `str` | 新分类 |

**返回值**: `{"success": bool, "message": str}`

---

### `delete_article(article_id)`

删除文章。

```python
def delete_article(article_id: str) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `article_id` | `str` | 文章ID |

**返回值**: `{"success": bool, "message": str}`

---

### `search_articles(query, tags, category)`

搜索知识文章（支持关键词、标签、分类组合筛选）。

```python
def search_articles(query: str = "", tags: str = "",
                    category: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `query` | `str` | 搜索关键词（匹配标题/内容/标签） |
| `tags` | `str` | 标签筛选（顿号分隔） |
| `category` | `str` | 分类筛选 |

**返回值**: `{"success": bool, "articles": List, "count": int}`

---

### `list_categories()`

列出所有分类及文章数。

```python
def list_categories() -> Dict[str, Any]
```

**返回值**: `{"success": bool, "categories": List, "count": int}` — 每项含 `name` 和 `count`

---

### `get_stats()`

获取知识库统计。

```python
def get_stats() -> Dict[str, Any]
```

**返回值**: `{"success": bool, "total": int, "total_words": int, "categories": int}`

---

### `execute_goal(goal, _context, **kwargs)`

知识库技能统一委托入口，根据目标文本自动路由到创建/获取/更新/删除/搜索文章等操作。

```python
def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `goal` | `str` | 用户目标文本（如"帮我写一篇知识笔记"） |
| `_context` | `SkillContext` | 技能上下文（可选） |

**返回值**: `Dict[str, Any]` — 委托到具体操作函数的返回值

---

## skill_marketplace — 技能市场

> 模块路径: `opc_manager.skill_marketplace`

外部技能搜索、安装和MCP服务发现。

### `ExternalSkillMarketplace.search_skills(query, category)`

搜索外部技能（本地+远程注册表）。

```python
def search_skills(self, query: str, category: str = "") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `query` | `str` | 搜索关键词 |
| `category` | `str` | 分类筛选 |

**返回值**: `{"success": bool, "query": str, "results": List, "total": int}` — 每项含 `source_type`（local/remote）和 `trust_level`

---

### `ExternalSkillMarketplace.install_skill(skill_id, source)`

安装外部技能（含安全校验和信任等级评估）。

```python
def install_skill(self, skill_id: str, source: str = "opc_official") -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `skill_id` | `str` | 技能ID |
| `source` | `str` | 来源（opc_official/github/mcp_hub） |

**返回值**: `{"success": bool, "skill_id": str, "trust_level": str, "message": str}`

---

### `ExternalSkillMarketplace.uninstall_skill(skill_id)`

卸载外部技能。

```python
def uninstall_skill(self, skill_id: str) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `skill_id` | `str` | 技能ID |

**返回值**: `{"success": bool, "skill_id": str, "message": str}`

---

### `ExternalSkillMarketplace.list_installed()`

列出已安装的外部技能。

```python
def list_installed(self) -> Dict[str, Any]
```

**返回值**: `{"success": bool, "skills": List, "total": int}`

---

### `ExternalSkillMarketplace.search_mcp_servers(query)`

搜索MCP协议服务器。

```python
def search_mcp_servers(self, query: str) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `query` | `str` | 搜索关键词 |

**返回值**: `{"success": bool, "query": str, "results": List, "total": int}` — 每项含 `capabilities` 和 `trust_level`

---

### `ExternalSkillMarketplace.connect_mcp(server_url, capabilities)`

连接MCP服务器（强制HTTPS，自动发现工具）。

```python
def connect_mcp(self, server_url: str, capabilities: List[str] = None) -> Dict[str, Any]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `server_url` | `str` | MCP服务器URL（必须HTTPS） |
| `capabilities` | `List[str]` | 期望的能力列表（可选） |

**返回值**: `{"success": bool, "server_id": str, "capabilities": List, "tools_discovered": int, "message": str}`

---

## user_profile — 用户画像

> 模块路径: `opc_manager.user_profile`

用户交互记录、偏好管理和智能推荐。

### `UserProfile.record_interaction(intent_type, goal, skill_used, result_success, user_feedback)`

记录一次交互日志。

```python
def record_interaction(self, intent_type: str, goal: str, skill_used: str,
                       result_success: bool, user_feedback: str = "") -> None
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `intent_type` | `str` | 意图类型 |
| `goal` | `str` | 用户目标 |
| `skill_used` | `str` | 使用的技能 |
| `result_success` | `bool` | 是否成功 |
| `user_feedback` | `str` | 用户反馈 |

**返回值**: 无

---

### `UserProfile.get_preferred_skills(intent_type)`

获取指定意图类型下最常使用的技能。

```python
def get_preferred_skills(self, intent_type: str) -> List[str]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `intent_type` | `str` | 意图类型 |

**返回值**: `List[str]` — 按使用频率降序排列的技能列表（最多10个）

---

### `UserProfile.get_usage_patterns()`

获取用户使用模式分析。

```python
def get_usage_patterns(self) -> Dict[str, Any]
```

**返回值**:
```json
{
  "total_interactions": 100,
  "top_skills": [{"skill": "email", "count": 30}],
  "top_intents": [{"intent": "operation", "count": 40}],
  "success_rate": 0.85,
  "peak_hours": [9, 10, 14, 15, 20]
}
```

---

### `UserProfile.get_skill_recommendations()`

获取技能推荐（基于失败意图和未知意图分析）。

```python
def get_skill_recommendations(self) -> List[Dict[str, Any]]
```

**返回值**: 推荐列表，每项含 `type`（failed_intent/unknown_intent）、`suggestion`

---

### `UserProfile.record_preference(key, value)`

记录用户偏好。

```python
def record_preference(self, key: str, value: str) -> None
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `key` | `str` | 偏好键名 |
| `value` | `str` | 偏好值 |

**返回值**: 无

---

### `UserProfile.get_preference(key, default)`

获取用户偏好。

```python
def get_preference(self, key: str, default: str = "") -> str
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `key` | `str` | 偏好键名 |
| `default` | `str` | 默认值 |

**返回值**: `str` — 偏好值或默认值
