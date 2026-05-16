# OPC-Agents v0.2.0 Sprint 规划文档

**创建时间**: 2026-05-16
**基于报告**: [v020_complete_analysis_report.md](../v020_complete_analysis_report.md)
**目标**: 将17项功能拆分为可执行的原子任务，按4个Sprint组织实施

---

## 📋 文档概览

| 指标 | 数值 |
|------|------|
| 总功能数 | 17项（P0:4 + P1:5 + P2:8） |
| 原子任务数 | **62个** |
| Sprint数量 | 4个 |
| 预估总工时 | **280小时（约7周×40h）** |
| 并行任务组 | 8组 |

---

## 🎯 Sprint 1: "零配置启动"

**目标**: 用户下载后10分钟内可用
**周期**: Week 1-2 (80小时)
**核心交付**: Settings统一设置页 + 加密Key自动生成 + SMTP配置UI + Onboarding新手引导

### 功能范围

- ✅ P0-1: Settings统一设置页
- ✅ P0-2: 加密Key自动生成
- ✅ P0-3: SMTP配置UI
- ✅ P1-1: Onboarding新手引导

---

### S1-T01: 创建SettingsManager基础框架

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T01 |
| **描述** | 在 `opc_manager/settings.py` 新建SettingsManager类，实现get_settings/save_settings基础方法框架，支持从.secure_settings JSON文件读写配置 |
| **预估工时** | 4h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S1-T04并行 |
| **涉及文件** | `opc_manager/settings.py` (新建) |
| **验收标准** | - SettingsManager类实例化成功<br>- get_settings("llm")返回默认字典<br>- save_settings("llm", {})写入JSON文件<br>- 单元测试覆盖≥85% |

**技术要点**:
```python
# opc_manager/settings.py 核心接口
class SettingsManager:
    def __init__(self, settings_path: str = None):
        self._settings_path = settings_path or "~/.opc-agents/.secure_settings"
        self._cache = {}
        self._lock = threading.Lock()

    def get_settings(self, category: str) -> Dict[str, Any]:
        """获取某类设置（敏感值已脱敏）"""

    def save_settings(self, category: str, data: Dict[str, Any]) -> bool:
        """保存设置（自动验证+加密）"""
```

---

### S1-T02: 实现LLM配置Tab后端逻辑

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T02 |
| **描述** | 在SettingsManager中实现LLM配置的验证逻辑（provider/api_key/base_url/model字段校验），集成现有ConfigManager的_ENV_MAP映射，支持OpenAI/Anthropic/Moka/GLM/Ollama五种Provider |
| **预估工时** | 3h |
| **依赖关系** | S1-T01 |
| **并行任务** | ❌ 依赖S1-T01完成 |
| **涉及文件** | `opc_manager/settings.py` (修改) |
| **验收标准** | - validate_llm_config()通过Pydantic模型验证<br>- api_key格式校验（sk-/sk-ant-前缀）<br>- base_url URL格式校验<br>- 无效配置抛出ValidationError |

**关键代码位置**: 参考 `opc_manager/config.py` 第21-41行的`_ENV_MAP`

---

### S1-T03: 实现SMTP配置Tab后端逻辑

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T03 |
| **描述** | 在SettingsManager中实现SMTP配置的完整CRUD和test_smtp_connection()方法，复用现有email_skill.py的_get_smtp_config()逻辑，增加连接超时处理（5秒）和常用邮箱服务商预设（QQ/163/Gmail/Outlook） |
| **预估工时** | 4h |
| **依赖关系** | S1-T01 |
| **并行任务** | ✅ 可与S1-T02并行（都依赖S1-T01） |
| **涉及文件** | `opc_manager/settings.py` (修改) |
| **验收标准** | - test_smtp_connection()5秒内返回结果<br>- 预设配置一键填充（QQ邮箱: smtp.qq.com:465）<br>- TLS选项开关生效<br>- 密码加密存储（调用SecureStorage.encrypt_sensitive_value）<br>- 连接失败返回具体错误原因（auth/network/config） |

**关键代码位置**: 复用 `opc_manager/email_skill.py` 第31-46行的`_get_smtp_config()` 和第49-64行的`save_smtp_config()`

---

### S1-T04: 增强SecureStorage支持Settings字段级加密

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T04 |
| **描述** | 在 `opc_manager/secure_storage.py` 的SecureKeyStore类中新增encrypt_field()/decrypt_field()方法（如已存在则增强），支持AES-256-GCM加密算法（按报告3.2节规范），新增mask_value()方法用于前端掩码显示 |
| **预估工时** | 3h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S1-T01并行 |
| **涉及文件** | `opc_manager/secure_storage.py` (修改) |
| **验收标准** | - encrypt_field()输出Base64编码密文（含nonce+tag）<br>- decrypt_field()正确还原明文<br>- mask_value("sk-abc123def456") → "sk-****456"<br>- 符合FIPS 140-2标准（香农熵>7.5）<br>- 线程安全（复用现有_lock） |

**技术风险**: ⚠️ 中等 - 需确保与现有Fernet加密方案兼容，建议保留旧方法标记为deprecated

---

### S1-T05: 实现API Key管理Tab后端逻辑

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T05 |
| **描述** | 在SettingsManager中实现API Key的加密存储和脱敏读取，支持MOKA/OpenAI/Anthropic/GLM四种Key类型，调用S1-T04的mask_value()进行显示脱敏，实现"显示明文5秒自动隐藏"的安全机制 |
| **预估工时** | 3h |
| **依赖关系** | S1-T01, S1-T04 |
| **并行任务** | ❌ 依赖S1-T04 |
| **涉及文件** | `opc_manager/settings.py` (修改) |
| **验收标准** | - API Key保存后存储为加密密文<br>- get_settings()返回脱敏值（sk-****xxxx）<br>- 点击显示按钮→明文5秒后自动隐藏<br>- 支持多Key并存（不同Provider） |

---

### S1-T06: 实现安全设置和个人信息Tab后端逻辑

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T06 |
| **描述** | 在SettingsManager中实现安全设置Tab（加密Key管理：查看/重新生成+警告确认）和个人信息Tab（用户名/邮箱/公司名），加密Key生成使用os.urandom(32)生成256位密钥 |
| **预估工时** | 2h |
| **依赖关系** | S1-T01 |
| **并行任务** | ✅ 可与S1-T03/S1-T05并行 |
| **涉及文件** | `opc_manager/settings.py` (修改) |
| **验收标准** | - generate_encryption_key()返回32字节Base64密钥<br>- 重新生成Key需二次确认对话框（st.dialog）<br>- 个人信息字段非空校验<br>- Key强度符合AES-256要求 |

---

### S1-T07: 实现EventBus事件总线（Settings实时生效）

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T07 |
| **描述** | 新建 `opc_manager/event_bus.py` 实现单例EventBus类（subscribe/publish模式），用于Settings变更后通知LLMService/EmailSkill等模块实时更新配置，解决报告7.1节提到的"Settings实时生效"高风险难点 |
| **预估工时** | 3h |
| **依赖关系** | S1-T01 |
| **并行任务** | ✅ 可独立开发 |
| **涉及文件** | `opc_manager/event_bus.py` (新建) |
| **验收标准** | - EventBus单例模式线程安全<br>- subscribe("settings_changed", callback)注册成功<br>- publish()触发所有订阅者回调<br>- 异常隔离（单个handler失败不影响其他）<br>- 单元测试≥95%覆盖率 |

**技术风险**: 🔴 高 - 这是P0功能的核心基础设施，必须充分测试

---

### S1-T08: 修改ConfigManager集成SettingsManager

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T08 |
| **描述** | 修改 `opc_manager/config.py` 的ConfigManager._load_config()方法，优先从SettingsManager读取配置（如存在），回退到环境变量，保持向后兼容（v0.1.9的.env仍可用），在__init__中注入event_bus订阅 |
| **预估工时** | 4h |
| **依赖关系** | S1-T01, S1-T07 |
| **并行任务** | ❌ 强依赖 |
| **涉及文件** | `opc_manager/config.py` (修改第62-100行) |
| **验收标准** | - ConfigManager优先读SettingsManager<br>- SettingsManager无数据时回退到os.environ<br>- v0.1.9的.env文件仍可正常加载<br>- LLMService通过新ConfigManager获取动态Key<br>- 612个原有测试不受影响（回归零缺陷） |

**技术风险**: 🔴 高 - 影响全局配置读取路径，必须全量回归测试

---

### S1-T09: 创建Settings页面UI（frontend/pages/settings.py）

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T09 |
| **描述** | 新建 `frontend/pages/settings.py`，使用Streamlit st.tabs()实现5个Tab页面（LLM/SMTP/API Key/安全/个人信息），每个Tab包含表单组件（st.text_input/st.selectbox/st.toggle），实现表单前端校验和提交逻辑 |
| **预估工时** | 6h |
| **依赖关系** | S1-T02, S1-T03, S1-T05, S1-T06 |
| **并行任务** | ❌ 依赖所有后端Tab完成 |
| **涉及文件** | `frontend/pages/settings.py` (新建, ~600行) |
| **验收标准** | - 5个Tab正常切换显示<br>- LLM Tab: Provider下拉框+API Key密码框+Base URL输入框<br>- SMTP Tab: Host/Port/User/Password/TLS表单+测试连接按钮<br>- API Key Tab: 多Key列表+添加/删除/显示切换<br>- 安全 Tab: 当前Key掩码显示+重新生成按钮<br>- 个人 Tab: 用户名/邮箱/公司名表单<br>- 表单提交调用SettingsManager.save_settings()<br>- 保存成功显示st.toast("设置已保存") |

**UI参考**: 报告5.3节的Settings布局结构图

---

### S1-T10: 实现加密Key自动生成逻辑

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T10 |
| **描述** | 在应用启动入口（`frontend/app.py`或`opc_manager/__init__.py`）检测~/.opc-agents/.env.local是否存在加密Key，不存在则自动调用SettingsManager.generate_encryption_key()生成并保存，显示友好提示"已为您自动生成加密密钥" |
| **预估工时** | 2h |
| **依赖关系** | S1-T06 |
| **并行任务** | ✅ 可与S1-T09并行 |
| **涉及文件** | `frontend/app.py` (修改init部分, 第56-73行), `opc_manager/__init__.py` (可选) |
| **验收标准** | - 首次启动自动生成256位Key<br>- Key存储到.env.local（不提交Git，已在.gitignore）<br>- 已存在Key时不重复生成<br>- 控制台/日志显示安全提示<br>- 启动时间增量<0.5秒 |

---

### S1-T11: 修改LLMService支持动态API Key

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T11 |
| **描述** | 修改 `opc_manager/llm_service.py` 的OpenAIBackend/MokaBackend等实现类，订阅event_bus的"settings_changed"事件，当LLM配置变更时自动重新初始化client（_get_client()方法），无需重启即可生效 |
| **预估工时** | 3h |
| **依赖关系** | S1-T07, S1-T08 |
| **并行任务** | ❌ 依赖EventBus和ConfigManager改造 |
| **涉及文件** | `opc_manager/llm_service.py` (修改第67-80行_init_部分) |
| **验收标准** | - LLMService启动时订阅settings_changed事件<br>- 收到llm category变更后重新创建client<br>- 调用complete()使用最新api_key/base_url<br>- 无并发竞争条件（threading.Lock保护）<br>- 现有测试全部通过 |

---

### S1-T12: 修改EmailSkill发送前检查SMTP配置

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T12 |
| **描述** | 修改 `opc_manager/email_skill.py` 的邮件发送入口函数（约第80行后），在send_email()前检查SMTP配置是否存在，未配置时返回友好的引导提示而非报错异常（符合US-P0-03验收标准第3条） |
| **预估工时** | 2h |
| **依赖关系** | S1-T03 |
| **并行任务** | ✅ 可独立于UI开发 |
| **涉及文件** | `opc_manager/email_skill.py` (修改send_email相关函数) |
| **验收标准** | - 未配置SMTP时返回{"success":False, "need_config":True}<br>- 前端接收到此响应弹出引导框（前往Settings配置）<br>- 已配置时正常发送流程不变<br>- 不影响现有邮件发送功能 |

---

### S1-T13: 创建OnboardingManager基础框架

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T13 |
| **描述** | 新建 `opc_manager/onboarding.py`，实现OnboardingManager类管理引导状态（NOT_STARTED/STEP_1/STEP_2/STEP_3/COMPLETED/SKIPPED），状态持久化到~/.opc-agents/onboarding.json，实现should_show()/complete_step()/skip()方法 |
| **预估工时** | 3h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S1-T01并行 |
| **涉及文件** | `opc_manager/onboarding.py` (新建, ~200行) |
| **验收标准** | - OnboardingManager单例模式<br>- should_show()首次返回True，完成后返回False<br>- complete_step(step_num)持久化进度<br>- skip()标记SKIPPED状态<br>- 中途退出下次从当前步骤继续<br>- onboarding.json格式符合报告5.4节规范 |

---

### S1-T14: 创建Onboarding UI（3步引导流程）

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T14 |
| **描述** | 新建 `frontend/pages/onboarding.py`，实现3步引导浮层UI：Step1欢迎页（产品介绍+特性展示）、Step2 LLM配置页（选择Provider+填写API Key，复用Settings页面的LLM Tab组件）、Step3示例任务页（点击执行示例任务"给客户发送周报邮件"） |
| **预估工时** | 6h |
| **依赖关系** | S1-T09, S1-T13 |
| **并行任务** | ❌ 依赖Settings UI和Onboarding Manager |
| **涉及文件** | `frontend/pages/onboarding.py` (新建, ~400行) |
| **验收标准** | - Step1: 欢迎标题+3个核心特性（21技能/AI驱动/企微支持）<br>- Step2: Provider下拉+API Key输入+测试连接按钮<br>- Step3: 示例任务卡片+执行按钮+结果预览<br>- 上一步/下一步/跳过引导按钮<br>- 使用st.session_state管理步骤状态<br>- 步骤切换时st.rerun()刷新页面 |

**UI参考**: 报告5.4节的3步引导流程图

---

### S1-T15: 集成Onboarding到主应用入口

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T15 |
| **描述** | 修改 `frontend/app.py` 的main()函数（约第150行后），在页面渲染前检查OnboardingManager.should_show()，如果需要显示则渲染onboarding浮层（使用st.columns居中显示，背景半透明遮罩），完成引导后进入正常主界面 |
| **预估工时** | 3h |
| **依赖关系** | S1-T13, S1-T14 |
| **并行任务** | ❌ 依赖Onboarding UI完成 |
| **涉及文件** | `frontend/app.py` (修改main函数区域) |
| **验收标准** | - 首次启动自动显示Onboarding浮层<br>- 浮层覆盖在主页面上方（z-index最高）<br>- 完成或跳过后不再显示<br>- 刷新页面不丢失进度（从onboarding.json恢复）<br>- 主界面4个Tab（对话/成果物/成长/设置）正常显示 |

---

### S1-T16: 编写Settings单元测试

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T16 |
| **描述** | 新建 `tests_v020/test_settings.py`，编写SettingsManager的完整单元测试：get_settings/save_settings/test_smtp_connection/generate_encryption_key/reset_to_defaults等方法，覆盖正常/边界/异常场景，目标50+测试用例 |
| **预估工时** | 4h |
| **依赖关系** | S1-T01至S1-T06 |
| **并行任务** | ✅ 可与S1-T09/S1-T14并行 |
| **涉及文件** | `tests_v020/test_settings.py` (新建, ~400行) |
| **验收标准** | - TC-P0-001至TC-P0-008全部实现<br>- pytest运行全绿<br>- 覆盖率≥85%（settings.py）<br>- Mock外部依赖（文件系统/网络）<br>- 包含并发保存冲突测试（TC-P0-007） |

**测试用例参考**: 报告4.2.1节的测试矩阵

---

### S1-T17: 编写Onboarding单元测试

| 属性 | 值 |
|------|-----|
| **任务ID** | S1-T17 |
| **描述** | 新建 `tests_v020/test_onboarding.py`，编写OnboardingManager的状态机测试：首次显示/步骤推进/中途退出/跳过/完成/重复启动等场景，目标20+测试用例 |
| **预估工时** | 2h |
| **依赖关系** | S1-T13 |
| **并行任务** | ✅ 可与S1-T16并行 |
| **涉及文件** | `tests_v020/test_onboarding.py` (新建, ~200行) |
| **验收标准** | - TC-P1-001至TC-P1-004全部实现<br>- 状态转换符合有限状态机规则<br>- onboarding.json持久化/读取正确<br>- 边界情况（空文件/损坏文件）处理优雅<br>- 覆盖率≥90% |

---

### Sprint 1 任务汇总

| 任务ID | 描述 | 工时 | 依赖 | 并行组 |
|--------|------|------|------|--------|
| S1-T01 | SettingsManager基础框架 | 4h | 无 | A |
| S1-T02 | LLM配置Tab后端 | 3h | T01 | B |
| S1-T03 | SMTP配置Tab后端 | 4h | T01 | B |
| S1-T04 | SecureStorage增强 | 3h | 无 | A |
| S1-T05 | API Key管理Tab | 3h | T01,T04 | C |
| S1-T06 | 安全设置/个人Tab | 2h | T01 | B |
| S1-T07 | EventBus事件总线 | 3h | T01 | D |
| S1-T08 | ConfigManager集成 | 4h | T01,T07 | E |
| S1-T09 | Settings页面UI | 6h | T02,T03,T05,T06 | F |
| S1-T10 | 加密Key自动生成 | 2h | T06 | G |
| S1-T11 | LLMService动态Key | 3h | T07,T08 | H |
| S1-T12 | EmailSkill SMTP检查 | 2h | T03 | G |
| S1-T13 | OnboardingManager | 3h | 无 | A |
| S1-T14 | Onboarding UI | 6h | T09,T13 | I |
| S1-T15 | Onboarding集成入口 | 3h | T13,T14 | J |
| S1-T16 | Settings单元测试 | 4h | T01-T06 | K |
| S1-T17 | Onboarding单元测试 | 2h | T13 | K |
| **合计** | | **58h** | | |

**关键路径**: T01 → T02/T03/T06 → T09 → T14 → T15 (24h串行)

---

## 🎯 Sprint 2: "企业微信+体验升级"

**目标**: 企业微信端可用 + 友好错误提示 + 操作日志
**周期**: Week 3-4 (70小时)
**核心交付**: WeChatGateway修复 + ErrorHandler + AuditLog前端 + Undo前端入口

### 功能范围

- ✅ P0-4: 企业微信端可用
- ✅ P1-2: 友好错误提示系统
- ✅ P1-5: 操作日志前端展示
- ✅ P2-1: Undo撤销操作前端入口

---

### S2-T01: 修复WeChatGateway签名验证逻辑

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T01 |
| **描述** | 修复 `opc_manager/wechat_gateway.py` 的verify_signature()方法（第88-94行），增强Token空值检查、Timestamp 5分钟窗口验证、Nonce去重防重放攻击，添加详细日志记录用于调试 |
| **预估工时** | 3h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S2-T03并行 |
| **涉及文件** | `opc_manager/wechat_gateway.py` (修改第88-94行) |
| **验收标准** | - Token为空时返回False+warning日志<br>- Timestamp超过300秒拒绝<br>- Nonce重复请求拒绝（内存Set去重，1小时过期）<br>- SHA1签名验证逻辑正确<br>- TC-P0-019签名验证测试通过<br>- TC-P0-020消息重放攻击测试通过 |

**技术风险**: ⚠️ 中等 - 签名验证是企业微信安全防线，必须严格测试

---

### S2-T02: 修复WeChatGateway消息解析和路由

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T02 |
| **描述** | 增强 `opc_manager/wechat_gateway.py` 的parse_message()方法（第114行起）和handle_message()方法，完善XML解析的CDATA处理、消息类型路由（text/image/file/event）、长消息自动分段（>2000字按句号分割）、消息内容XSS过滤 |
| **预估工时** | 4h |
| **依赖关系** | S2-T01 |
| **并行任务** | ❌ 依赖签名验证修复 |
| **涉及文件** | `opc_manager/wechat_gateway.py` (修改第114-150行) |
| **验收标准** | - parse_message()正确解析text/image/file/event类型<br>- XML特殊字符（&<>"）不导致解析失败<br>- 长文本(>2000字)自动分段为多条消息<br>- 消息内容经过HTML转义（防XSS）<br>- TC-P0-017消息接收测试通过<br>- TC-P0-021长文本分段测试通过 |

---

### S2-T03: 实现WeChatGateway→TaskEngine路由对接

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T03 |
| **描述** | 在WeChatGateway.handle_message()中实现消息→TaskEngineV3的路由逻辑：FromUserName映射到用户身份、Intent识别（复用StrategistBrain或简单关键词匹配）、创建Task并异步执行（AsyncExecutor）、结果回调格式化为企业微信XML回复 |
| **预估工时** | 5h |
| **依赖关系** | S2-T02 |
| **并行任务** | ❌ 依赖消息解析完成 |
| **涉及文件** | `opc_manager/wechat_gateway.py` (修改handle_message方法), `opc_manager/wechat_agent.py` (可能修改) |
| **验收标准** | - 文本消息→TaskEngineV3.create_task()<br>- Task异步执行（不阻塞HTTP响应）<br>- 完成后回调WeChatGateway.send_response()<br>- 回复内容格式化为XML（含CDATA转义）<br>- 简单任务响应时间<10秒（TC-P0-022）<br>- 错误时回复友好提示（非异常栈） |

**技术风险**: 🔴 高 - 涉及多个模块协作，需要充分的集成测试

---

### S2-T04: 实现企业微信E2E测试

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T04 |
| **描述** | 新建 `tests_v020/test_wechat_e2e.py`，编写企业微信端到端测试：模拟POST /wechat/callback请求→签名验证→消息解析→TaskEngine路由→执行→回复推送的全链路测试，使用Mock对象替代真实企业微信服务器 |
| **预估工时** | 4h |
| **依赖关系** | S2-T03 |
| **并行任务** | ❌ 依赖路由对接完成 |
| **涉及文件** | `tests_v020/test_wechat_e2e.py` (新建, ~300行) |
| **验收标准** | - test_wechat_end_to_end_flow()通过（参考报告4.2.4节示例）<br>- 模拟企业微信回调请求构造正确<br>- 签名伪造请求被拒绝（403）<br>- 正常消息→任务→回复全链路耗时<10秒<br>- 图片/文件消息路由正确（TC-P0-022）<br>- 覆盖率≥80%（wechat_gateway.py） |

---

### S2-T05: 创建ErrorHandler异常映射表

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T05 |
| **描述** | 新建 `opc_manager/error_handler.py`，实现ErrorHandler类，建立Python内置异常和技术库异常到中文友好提示的映射表（ConnectionError→"网络连接失败"、RateLimitError→"API调用频率超限"、AuthenticationError→"API密钥无效"...），提供translate(exception)→str方法 |
| **预估工时** | 3h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S2-T01并行 |
| **涉及文件** | `opc_manager/error_handler.py` (新建, ~300行) |
| **验收标准** | - 覆盖常见异常：ConnectionError/TimeoutError/AuthenticationError/RateLimitError/FileNotFoundError/ValueError/KeyError/ImportError<br>- 每个异常对应唯一中文提示（无技术术语）<br>- 未知异常返回"系统错误，已记录日志（ID: xxx）"<br>- translate()方法性能<1ms（避免影响用户体验）<br>- TC-P1-005至TC-P1-009全部实现 |

**异常映射参考**: 报告4.3.2节的测试用例矩阵

---

### S2-T06: 集成ErrorHandler到前端异常捕获

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T06 |
| **描述** | 修改 `frontend/app.py` 的execute_task_and_deliver()函数（顶层try-except块），将except Exception中的traceback替换为ErrorHandler.translate(e)调用，使用st.error()显示友好提示；同时修改safe_detect/safe_get_persona/safe_track_flywheel三个包装器函数的异常处理 |
| **预估工时** | 2h |
| **依赖关系** | S2-T05 |
| **并行任务** | ❌ 依赖ErrorHandler完成 |
| **涉及文件** | `frontend/app.py` (修改execute_task_and_deliver及safe_wrappers, 约28-35行注释区域) |
| **验收标准** | - execute_task_and_deliver异常时显示中文友好提示<br>- 不再暴露traceback到前端<br>- safe_*包装器异常时返回降级结果而非崩溃<br>- 错误日志仍记录完整异常（loguru logger.error）<br>- 网络超时显示"网络连接超时，请检查网络后重试"而非TimeoutError |

---

### S2-T07: 集成ErrorHandler到后端模块

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T07 |
| **描述** | 在各后端模块的关键函数中集成ErrorHandler：LLMService.complete()、EmailSkill.send_email()、DataManager.export_all()等，在except块中使用ErrorHandler.translate()转换异常后再raise或return error dict |
| **预估工时** | 3h |
| **依赖关系** | S2-T05 |
| **并行任务** | ✅ 可与S2-T06并行（前后端可同步进行） |
| **涉及文件** | `opc_manager/llm_service.py`, `opc_manager/email_skill.py`, `opc_manager/data_manager.py` (修改except块) |
| **验收标准** | - LLM调用失败返回{"error": "AI服务暂时不可用，请稍后重试"}<br>- 邮件发送失败返回{"error": "邮件发送失败：SMTP连接超时"}<br>- 数据导出失败返回{"error": "导出失败：磁盘空间不足"}<br>- 所有异常都有中文映射（无遗漏）<br>- 原始异常仍记录到AuditLog |

---

### S2-T08: 扩展AuditLog查询API

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T08 |
| **描述** | 修改 `opc_manager/audit_log.py` 的AuditLog类，新增query_logs()方法支持分页（page/page_size）、筛选（operation_type/skill_id/status/user_id）、搜索（input_summary模糊匹配）、时间范围过滤（start_time/end_time），返回List[AuditRecord] |
| **预估工时** | 3h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S2-T01/S2-T05并行 |
| **涉及文件** | `opc_manager/audit_log.py` (修改, 新增查询方法) |
| **验收标准** | - query_logs(page=1, page_size=20)返回分页结果<br>- filter_by(operation_type="email_send")精确匹配<br>- search("销售报告")模糊匹配input_summary<br>- date_range(start, end)时间过滤<br>- 1万条日志查询性能<100ms（TC-P1-020）<br>- 返回total_count用于前端分页控件 |

---

### S2-T09: 创建操作日志前端页面

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T09 |
| **描述** | 新建 `frontend/pages/audit_log.py`，实现操作日志查看器UI：时间线样式展示（左侧时间轴+右侧操作详情）、顶部筛选栏（操作类型下拉/技能选择/状态筛选/日期范围选择器）、搜索框、分页控件（st.pagination），每条日志显示：时间戳/操作类型/技能/输入摘要/输出摘要/耗时/状态 |
| **预估工时** | 5h |
| **依赖关系** | S2-T08 |
| **并行任务** | ❌ 依赖查询API完成 |
| **涉及文件** | `frontend/pages/audit_log.py` (新建, ~350行) |
| **验收标准** | - 时间线样式清晰展示操作序列<br>- 筛选器联动（选择类型后列表刷新）<br>- 搜索框实时过滤（debounce 300ms）<br>- 分页控件每页20条，显示总条数<br>- 成功/失败状态用颜色区分（绿/红）<br>- 点击日志展开详细信息（JSON格式原始数据）<br>- TC-P1-020日志分页性能达标<br>- TC-P1-021日志筛选搜索功能正常 |

---

### S2-T10: 集成审计日志到主导航

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T10 |
| **描述** | 修改 `frontend/app.py` 主导航区域（目前4个Tab：对话/成果物/成长/设置），新增"📝 日志"Tab或侧边栏链接，点击后渲染audit_log页面；同时在Settings页面增加"查看操作日志"快捷入口 |
| **预估工时** | 2h |
| **依赖关系** | S2-T09 |
| **并行任务** | ❌ 依赖日志页面完成 |
| **涉及文件** | `frontend/app.py` (修改导航区域, 约16-20行的Tab定义处) |
| **验收标准** | - 导航栏显示"📝 日志"入口<br>- 点击后正确加载audit_log页面<br>- 页面间切换不丢失状态<br>- 移动端（企业微信）导航适配<br>- 日志页面URL可为/audit-log（可选） |

---

### S2-T11: 扩展UndoManager前端API

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T11 |
| **描述** | 修改 `opc_manager/undo_manager.py`，新增get_undo_list()方法返回最近可撤销的操作列表（最多50条）、undo(task_id)方法执行撤销操作、get_undo_history()方法返回撤销历史，每个UndoRecord包含task_id/operation_type/timestamp/reversible标志 |
| **预估工时** | 3h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S2-T01并行 |
| **涉及文件** | `opc_manager/undo_manager.py` (修改, 新增前端API方法) |
| **验收标准** | - get_undo_list()返回最近50条可撤销操作<br>- undo(task_id)执行撤销并返回成功/失败<br>- get_undo_history()返回完整撤销历史<br>- 幂等撤销（重复撤销同一任务返回already_undone）<br>- 撤销操作记录到AuditLog |

---

### S2-T12: 创建Undo前端入口UI

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T12 |
| **描述** | 新建 `frontend/components/undo_panel.py`（或在app.py中内联实现），实现Undo操作面板：最近操作列表（时间倒序）、每项显示操作描述+"撤销"按钮、点击撤销后二次确认（st.dialog）、撤销成功后st.toast提示+列表刷新、显示撤销历史折叠面板 |
| **预估工时** | 4h |
| **依赖关系** | S2-T11 |
| **并行任务** | ❌ 依赖Undo API完成 |
| **涉及文件** | `frontend/app.py` (修改, 新增Undo侧边栏/悬浮按钮) 或 `frontend/components/undo_panel.py` (新建) |
| **验收标准** | - Undo按钮/图标在主界面可见（建议右上角或侧边栏）<br>- 点击展开最近操作列表<br>- 每项操作显示："发送邮件给张三 14:30 [撤销]"<br>- 撤销按钮触发确认对话框<br>- 撤销成功后列表移除该项+toast提示<br>- 撤销失败显示原因（不可撤销/已过期）<br>- 撤销历史可查看（折叠面板） |

---

### S2-T13: 编写ErrorHandler单元测试

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T13 |
| **描述** | 新建 `tests_v020/test_error_handler.py`，编写ErrorHandler的完整测试：各种异常类型的翻译准确性、未知异常的处理、性能测试（1000次translate调用<1s）、边界情况（None异常/自定义异常/嵌套异常） |
| **预估工时** | 2h |
| **依赖关系** | S2-T05 |
| **并行任务** | ✅ 可与S2-T09/S2-T12并行 |
| **涉及文件** | `tests_v020/test_error_handler.py` (新建, ~250行) |
| **验收标准** | - 所有映射异常翻译正确<br>- 未知异常包含日志ID<br>- 性能测试通过<br>- 覆盖率≥95% |

---

### S2-T14: 编写企业微信集成测试

| 属性 | 值 |
|------|-----|
| **任务ID** | S2-T14 |
| **描述** | 补充 `tests/test_wechat_gateway.py`（已存在）的新测试用例：签名验证边界情况（空Token/过期Timestamp/重复Nonce）、消息解析XML注入防护、长消息分段逻辑、并发消息处理（ThreadPoolExecutor模拟） |
| **预估工时** | 3h |
| **依赖关系** | S2-T01, S2-T02 |
| **并行任务** | ✅ 可与其他测试并行 |
| **涉及文件** | `tests/test_wechat_gateway.py` (修改, 新增测试用例) |
| **验收标准** | - 新增30+测试用例<br>- 签名验证安全性测试全通过<br>- XML注入payload被正确拒绝<br>- 并发消息处理无竞态条件<br>- wechat_gateway.py覆盖率≥80% |

---

### Sprint 2 任务汇总

| 任务ID | 描述 | 工时 | 依赖 | 并行组 |
|--------|------|------|------|--------|
| S2-T01 | WeChatGateway签名验证修复 | 3h | 无 | A |
| S2-T02 | 消息解析和路由增强 | 4h | T01 | B |
| S2-T03 | WeChat→TaskEngine路由对接 | 5h | T02 | C |
| S2-T04 | 企业微信E2E测试 | 4h | T03 | D |
| S2-T05 | ErrorHandler异常映射表 | 3h | 无 | A |
| S2-T06 | ErrorHandler集成前端 | 2h | T05 | E |
| S2-T07 | ErrorHandler集成后端 | 3h | T05 | E |
| S2-T08 | AuditLog查询API扩展 | 3h | 无 | A |
| S2-T09 | 操作日志前端页面 | 5h | T08 | F |
| S2-T10 | 审计日志集成导航 | 2h | T09 | G |
| S2-T11 | UndoManager前端API | 3h | 无 | A |
| S2-T12 | Undo前端入口UI | 4h | T11 | H |
| S2-T13 | ErrorHandler单元测试 | 2h | T05 | I |
| S2-T14 | 企业微信集成测试 | 3h | T01,T02 | J |
| **合计** | | **52h** | | |

**关键路径**: T01 → T02 → T03 → T04 (16h串行)

---

## 🎯 Sprint 3: "数据价值可视化"

**目标**: 数据导入导出 + Dashboard模板化 + 多格式导出优化 + SSE进度条
**周期**: Week 5 (60小时)
**核心交付**: DataManager ZIP导出导入 + Dashboard 4组件模板 + Export增强 + SSE进度可视化

### 功能范围

- ✅ P1-3: 数据导入/导出功能
- ✅ P1-4: Dashboard模板化
- ✅ P2-2: 多格式导出入口优化
- ✅ P2-7: SSE实时进度条增强

---

### S3-T01: 增强DataManager ZIP打包导出功能

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T01 |
| **描述** | 修改 `opc_manager/data_manager.py`（已存在），新增export_all()方法实现ZIP打包导出：遍历data/目录下所有子目录（tasks/skills/logs/settings/knowledge等）、排除临时文件和大文件（>100MB）、生成manifest.json记录导出内容和版本号、使用zipfile标准库压缩、返回ZIP文件路径 |
| **预估工时** | 4h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S3-T05并行 |
| **涉及文件** | `opc_manager/data_manager.py` (修改, 新增export_all/import_data方法) |
| **验收标准** | - export_all()生成ZIP文件包含tasks/skills/logs/settings<br>- manifest.json记录版本号v0.2.0+导出时间戳<br>- 排除__pycache__/.tmp/.bak等临时文件<br>- 单文件>100MB跳过并记录到manifest<br>- 导出速度：1万任务数据<5秒（TC-P1-010）<br>- ZIP文件可通过import_data()恢复 |

---

### S3-T02: 实现DataManager ZIP导入和数据恢复

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T02 |
| **描述** | 在DataManager中实现import_data(zip_path)方法：解压ZIP文件、验证manifest.json版本兼容性（拒绝v0.1.9以下版本或提示升级）、备份现有数据到.backup目录、逐模块恢复数据、处理数据冲突（同ID记录提示用户选择覆盖/跳过/重命名）、返回导入报告（成功/跳过/失败数量） |
| **预估工时** | 5h |
| **依赖关系** | S3-T01 |
| **并行任务** | ❌ 依赖导出功能 |
| **涉及文件** | `opc_manager/data_manager.py` (修改) |
| **验收标准** | - import_data()正确解压并恢复数据<br>- 版本不兼容时拒绝并提示（TC-P1-013）<br>- 导入前自动备份现有数据<br>- 数据冲突时提供3种策略选择（TC-P1-014）<br>- 返回详细导入报告（成功N条/跳过M条/失败K条）<br>- 恢复成功率99%+（KPI指标） |

**技术风险**: ⚠️ 中等 - 数据一致性是关键，需要事务级别的原子性保证

---

### S3-T03: 创建数据导入导出前端UI

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T03 |
| **描述** | 新建 `frontend/pages/data_management.py` 或在Settings页面新增"数据管理"区域，实现：一键备份按钮（调用export_all→下载ZIP文件）、上传导入按钮（st.file_uploader接受ZIP→调用import_data→显示导入报告）、上次备份时间显示、数据统计面板（任务数/技能数/日志条数/数据大小） |
| **预估工时** | 4h |
| **依赖关系** | S3-T01, S3-T02 |
| **并行任务** | ❌ 依赖导入导出后端完成 |
| **涉及文件** | `frontend/pages/settings.py` (修改, 新增数据管理区域) 或 `frontend/pages/data_management.py` (新建) |
| **验收标准** | - "备份数据"按钮点击后生成并下载ZIP<br>- "恢复数据"按钮上传ZIP文件<br>- 导入过程显示进度条（st.progress）<br>- 导入完成后显示报告（成功/失败统计）<br>- 显示数据统计（任务总数/占用空间）<br>- 导入前确认对话框（st.dialog警告覆盖风险） |

---

### S3-T04: 创建DashboardConfig配置管理器

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T04 |
| **描述** | 新建 `opc_manager/dashboard_config.py`，实现DashboardConfig类管理仪表盘布局配置：定义可用组件库（revenue_trend/customer_health/task_completion_rate/recent_tasks/skill_usage_stats/upcoming_deadlines/quick_actions共7个组件，参考报告5.5节）、默认布局（4组件：收入趋势+客户健康度+最近任务+快捷操作）、布局持久化到~/.opc-agents/dashboard_layout.json、add_component/remove_component/update_position方法 |
| **预估工时** | 3h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S3-T01并行 |
| **涉及文件** | `opc_manager/dashboard_config.py` (新建, ~200行) |
| **验收标准** | - 7个组件定义完整（ID/名称/数据源/尺寸）<br>- 默认布局包含4个组件<br>- add_component(component_id, row, col)成功添加<br>- remove_component(component_id)成功移除<br>- update_position()调整组件位置<br>- 布局变更自动持久化到JSON<br>- Pydantic模型验证布局合法性 |

---

### S3-T05: 创建Dashboard前端页面

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T05 |
| **描述** | 新建 `frontend/pages/dashboard.py`，实现可定制仪表盘UI：网格布局展示组件（使用st.columns实现2列布局）、每个组件渲染对应数据图表（收入趋势图用st.line_chart/客户健康度用st.metric/任务列表用st.dataframe）、底部工具栏（[添加组件][导入模板][重置默认]）、添加组件弹窗（checkbox列表+位置选择器） |
| **预估工时** | 6h |
| **依赖关系** | S3-T04 |
| **并行任务** | ❌ 依赖DashboardConfig完成 |
| **涉及文件** | `frontend/pages/dashboard.py` (新建, ~500行) |
| **验收标准** | - 默认显示4个组件（2x2网格）<br>- 收入趋势图显示近30天数据折线<br>- 客户健康度显示metric数字（92% 活跃23 风险2）<br>- 最近任务列表显示5条最新任务<br>- 快捷操作面板显示常用按钮<br>- "添加组件"弹窗可选择剩余3个组件<br>- 组件位置可调整（通过选择行列号）<br>- 布局保存后刷新不丢失<br>- TC-P1-015默认Dashboard测试通过<br>- TC-P1-016添加/移除组件持久化测试通过 |

**UI参考**: 报告5.5节的默认布局图和拖拽编排简化版设计

---

### S3-T06: 集成Dashboard到主导航

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T06 |
| **描述** | 修改 `frontend/app.py` 导航栏，新增"📊 Dashboard"Tab（位于Home和Tasks之间），点击后渲染dashboard页面；同时修改首页（Home Tab）增加快捷入口卡片链接到Dashboard |
| **预估工时** | 2h |
| **依赖关系** | S3-T05 |
| **并行任务** | ❌ 依赖Dashboard UI完成 |
| **涉及文件** | `frontend/app.py` (修改导航和首页) |
| **验收标准** | - 导航栏显示"📊 Dashboard"入口<br>- Dashboard作为独立Tab页面<br>- 首页有Dashboard快捷入口卡片<br>- 页面切换流畅无白屏<br>- Dashboard加载时间<2秒（KPI指标） |

---

### S3-T07: 增强ExportManager多格式导出优化

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T07 |
| **描述** | 修改 `opc_manager/export/manager.py` 的ExportManager类，新增批量导出方法export_batch(items: List[ResultData], format: ExportFormat)支持一次性导出多个成果物为单个文件（PDF合并/Excel多Sheet/Word多章节）、新增导出进度回调参数（progress_callback: Callable[[float], None]）用于SSE推送进度、优化大文件导出内存使用（流式写入） |
| **预估工时** | 4h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可独立开发 |
| **涉及文件** | `opc_manager/export/manager.py` (修改) |
| **验收标准** | - export_batch()接受List[ResultData]输入<br>- PDF格式合并多个内容为一个PDF（多页）<br>- Excel格式每个ResultData一个Sheet<br>- Word格式每个ResultData一个章节（带目录）<br>- progress_callback(0.0→1.0)实时反馈进度<br>- 大文件（>50MB）导出内存稳定（流式写入）<br>- 现有export_sync()方法保持不变（向后兼容） |

---

### S3-T08: 创建多格式导出前端入口优化

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T08 |
| **描述** | 修改 `frontend/app.py` 的成果物下载区域（_render_export_buttons函数或类似位置），优化导出按钮布局：改为下拉菜单（st.selectbox或st.pills）显示格式选项（PDF/Excel/Word/PNG/HTML/MD）、增加"批量导出"按钮（勾选多个成果物后一键导出）、导出过程中显示进度指示器（st.progress + st.spinner） |
| **预估工时** | 3h |
| **依赖关系** | S3-T07 |
| **并行任务** | ❌ 依赖ExportManager增强 |
| **涉及文件** | `frontend/app.py` (修改导出按钮区域, 约125-149行_get_export_bytes附近) |
| **验收标准** | - 格式选择器显示6种导出格式<br>- 点击格式后立即开始下载<br>- 批量导出按钮可选多个成果物<br>- 导出中显示进度条（0%-100%）<br>- 导出完成后自动下载<br>- 导出失败显示友好错误提示（集成ErrorHandler） |

---

### S3-T09: 增强ProgressEmitter支持SSE推送

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T09 |
| **描述** | 修改 `opc_manager/progress_emitter.py`（已存在），增强ProgressEmitter类支持Server-Sent Events协议：新增emit_sse(event_type, data)方法向客户端推送实时进度、新增SSE endpoint（FastAPI route @app.get("/api/events/stream")）返回text/event-stream、支持多种事件类型（progress/error/complete/log）、客户端自动重连机制 |
| **预估工时** | 4h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可独立开发 |
| **涉及文件** | `opc_manager/progress_emitter.py` (修改), `opc_manager/api/events.py` (可能修改) |
| **验收标准** | - emit_sse()推送格式正确的SSE事件<br>- /api/events/stream endpoint返回text/event-stream<br>- 事件格式：data: {json}\n\n<br>- 支持3种事件类型（progress/error/complete）<br>- 客户端断开后自动清理资源<br>- 并发多客户端推送互不干扰<br>- 与现有progress_emitter逻辑兼容 |

**技术风险**: ⚠️ 中等 - SSE需要Streamlit前端配合JavaScript接收，需验证可行性

---

### S3-T10: 实现SSE实时进度条前端组件

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T10 |
| **描述** | 在 `frontend/app.py` 或新建 `frontend/components/progress_bar.py`，实现SSE实时进度条组件：使用st.components.v1.html()嵌入JavaScript代码连接/api/events/stream、监听progress事件更新st.progress()进度条、监听error事件显示st.error()、监听complete事件触发st.rerun()刷新结果、支持取消操作（AbortController） |
| **预估工时** | 5h |
| **依赖关系** | S3-T09 |
| **并行任务** | ❌ 依赖SSE后端完成 |
| **涉及文件** | `frontend/app.py` (修改, 集成SSE进度条) 或 `frontend/components/progress_bar.py` (新建) |
| **验收标准** | - 任务执行时显示实时进度条（0%-100%）<br>- 进度更新延迟<500ms（接近实时）<br>- 进度条旁显示百分比文字和预计剩余时间<br>- 出错时进度条变红并显示错误信息<br>- 完成后自动隐藏进度条并显示结果<br>- 用户可取消长时间运行的任务<br>- Streamlit rerun时不丢失SSE连接状态 |

**技术风险**: 🔴 高 - Streamlit对SSE的原生支持有限，可能需要workaround方案

---

### S3-T11: 编写DataManager单元测试

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T11 |
| **描述** | 新建 `tests_v020/test_data_manager.py`，编写DataManager的完整测试：export_all()正确性（文件完整性/manifest/排除规则）、import_data()恢复正确性（版本校验/冲突处理/备份）、边界情况（空数据/超大文件/损坏ZIP）、性能测试（1万任务导出<5秒） |
| **预估工时** | 3h |
| **依赖关系** | S3-T01, S3-T02 |
| **并行任务** | ✅ 可与S3-T05/S3-T08并行 |
| **涉及文件** | `tests_v020/test_data_manager.py` (新建, ~300行) |
| **验收标准** | - TC-P1-010至TC-P1-014全部实现<br>- export_all生成的ZIP可正确import_data恢复<br>- 版本不兼容导入被拒绝<br>- 数据冲突处理策略正确<br>- 覆盖率≥90% |

---

### S3-T12: 编写Dashboard和Export测试

| 属性 | 值 |
|------|-----|
| **任务ID** | S3-T12 |
| **描述** | 新增DashboardConfig和ExportManager增强功能的测试：dashboard_config.py的布局CRUD测试、export_batch()多格式测试、SSE endpoint连通性测试、前端组件渲染快照测试（如可行）
| **预估工时** | 3h |
| **依赖关系** | S3-T04, S3-T07, S3-T09 |
| **并行任务** | ✅ 可与其他测试并行 |
| **涉及文件** | `tests_v020/test_dashboard_config.py` (新建), `tests_v020/test_export_enhanced.py` (新建) |
| **验收标准** | - DashboardConfig 7个测试场景全覆盖<br>- ExportManager batch导出3种格式测试<br>- SSE endpoint返回正确Content-Type<br>- 总新增测试≥40个 |

---

### Sprint 3 任务汇总

| 任务ID | 描述 | 工时 | 依赖 | 并行组 |
|--------|------|------|------|--------|
| S3-T01 | DataManager ZIP导出 | 4h | 无 | A |
| S3-T02 | DataManager ZIP导入 | 5h | T01 | B |
| S3-T03 | 数据导入导出UI | 4h | T01,T02 | C |
| S3-T04 | DashboardConfig管理器 | 3h | 无 | A |
| S3-T05 | Dashboard前端页面 | 6h | T04 | D |
| S3-T06 | Dashboard集成导航 | 2h | T05 | E |
| S3-T07 | ExportManager增强 | 4h | 无 | A |
| S3-T08 | 多格式导出前端 | 3h | T07 | F |
| S3-T09 | ProgressEmitter SSE增强 | 4h | 无 | A |
| S3-T10 | SSE进度条前端 | 5h | T09 | G |
| S3-T11 | DataManager单元测试 | 3h | T01,T02 | H |
| S3-T12 | Dashboard/Export测试 | 3h | T04,T07,T09 | I |
| **合计** | | **56h** | | |

**关键路径**: T01 → T02 → T03 (13h串行) 或 T04 → T05 → T06 (11h串行)

---

## 🎯 Sprint 4: "打磨+国际化"

**目标**: 暗色模式 + i18n + 快捷键 + 技能市场 + 全局搜索
**周期**: Week 6-7 (70小时)
**核心交付**: ThemeManager + I18nManager + Keyboard Shortcuts + Skill Market MVP + Global Search

### 功能范围

- ✅ P2-3: 暗色模式/主题切换
- ✅ P2-4: 中英文切换(i18n)
- ✅ P2-5: Keyboard Shortcuts
- ✅ P2-6: 技能市场前端MVP
- ✅ P2-8: 全局搜索

---

### S4-T01: 创建ThemeManager主题管理器

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T01 |
| **描述** | 新建 `opc_manager/theme_manager.py`，实现ThemeManager类管理暗色/亮色主题切换：定义CSS变量（--primary-color/--background-color/--text-color等，参考报告5.6节规范）、get_theme_css(theme: str)返回CSS字符串、toggle_theme()切换主题并持久化到User Preferences、支持自定义主题色（可选） |
| **预估工时** | 3h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S4-T04/S4-T07并行 |
| **涉及文件** | `opc_manager/theme_manager.py` (新建, ~150行) |
| **验收标准** | - Light/Dark两套主题CSS变量完整<br>- get_theme_css("dark")返回暗色CSS<br>- toggle_theme()切换后立即生效<br>- 主题偏好持久化到~/.opc-agents/preferences.json<br>- CSS变量符合WCAG AA色彩对比度≥4.5:1 |

---

### S4-T02: 实现主题切换前端UI

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T02 |
| **描述** | 修改 `frontend/app.py`，在页面右上角添加主题切换按钮（🌙/☀️图标，st.toggle或st.button实现），点击后调用ThemeManager.toggle_theme()、通过st.markdown(unsafe_allow_html=True)注入CSS变量、st.rerun()刷新页面应用新主题、图标随当前主题变化（亮色显示🌙，暗色显示☀️） |
| **预估工时** | 3h |
| **依赖关系** | S4-T01 |
| **并行任务** | ❌ 依赖ThemeManager完成 |
| **涉及文件** | `frontend/app.py` (修改, 注入主题CSS和切换按钮) |
| **验收标准** | - 右上角显示主题切换图标<br>- 点击后整个页面切换配色<br>- 暗色模式：背景#1E1E1E 文字#E0E0E0<br>- 亮色模式：背景#FFFFFF 文字#333333<br>- 刷新页面后主题保持（从preferences.json恢复）<br>- 切换动画平滑（CSS transition 0.3s）<br>- 所有页面/组件均响应主题变化 |

**CSS参考**: 报告5.6节的CSS变量方案

---

### S4-T03: 创建I18nManager国际化管理器

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T03 |
| **描述** | 新建 `opc_manager/i18n.py`，实现I18nManager类：load_locale(locale: str)加载YAML语言包（locales/zh_CN.yaml和locales/en_US.yaml）、gettext(key: str, **kwargs)返回翻译文本（支持变量插值{variable}）、set_locale(locale: str)切换语言、get_available_locales()返回支持的语言列表、fallback到英文（缺失翻译使用en_US） |
| **预估工时** | 4h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S4-T01并行 |
| **涉及文件** | `opc_manager/i18n.py` (新建, ~250行), `locales/zh_CN.yaml` (新建), `locales/en_US.yaml` (新建) |
| **验收标准** | - load_locale("zh_CN")加载中文包成功<br>- gettext("settings.save_success")返回"设置已保存"<br>- gettext("welcome", name="张三")返回"欢迎，张三！"<br>- set_locale("en_US")切换后gettext返回英文<br>- 缺失翻译fallback到英文key本身<br>- sanitize_translation()防XSS（报告3.3节规范）<br>- 语言包YAML格式正确（UTF-8编码） |

---

### S4-T04: 创建中英文语言包

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T04 |
| **描述** | 创建 `locales/zh_CN.yaml` 和 `locales/en_US.yaml` 两个语言包文件，提取所有前端UI文本（导航栏/按钮/标签/提示/错误信息/帮助文字）定义为翻译键值对，初步覆盖核心页面（Settings/Dashboard/Home/Onboarding）约200个翻译条目 |
| **预估工时** | 4h |
| **依赖关系** | S4-T03 |
| **并行任务** | ❌ 依赖I18nManager框架 |
| **涉及文件** | `locales/zh_CN.yaml` (新建), `locales/en_US.yaml` (新建) |
| **验收标准** | - zh_CN.yaml包含200+中文翻译<br>- en_US.yaml包含对应200+英文翻译<br>- 翻译键命名规范：page.section.element（如settings.llm.api_key_label）<br>- 无硬编码中文/英文在前端代码中（Settings页面等）<br>- 语言包通过XSS安全扫描（grep script/javascript:/on\\w+=）<br>- 特殊字符正确转义（引号/换行/占位符） |

**初始翻译键清单**:
```yaml
# locales/zh_CN.yaml 示例
nav.home: "首页"
nav.dashboard: "仪表盘"
nav.tasks: "任务"
nav.skills: "技能"
nav.settings: "设置"
nav.audit_log: "操作日志"
settings.title: "系统设置"
settings.tab.llm: "LLM配置"
settings.tab.smtp: "SMTP配置"
settings.save: "保存"
settings.saved: "设置已保存"
smtp.test_connection: "测试连接"
smtp.connecting: "正在连接..."
smtp.success: "✅ 连接成功！可以发送邮件了"
smtp.failed: "❌ 连接失败: {error}"
onboarding.welcome.title: "欢迎使用 OPC-Agents！"
onboarding.welcome.subtitle: "你的智能任务执行助手，专为一人公司打造"
error.network: "网络连接失败，请检查网络设置"
error.auth_failed: "API密钥无效，请前往设置页更新"
error.rate_limit: "API调用频率超限，请稍后重试"
```

---

### S4-T05: 集成i18n到前端页面

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T05 |
| **描述** | 逐步修改前端页面文件（frontend/app.py、frontend/pages/settings.py、frontend/pages/dashboard.py等），将所有硬编码中文字符串替换为i18n.gettext()调用，在页面顶部初始化I18nManager实例并从st.query_params或session_state读取当前语言，在导航栏添加语言切换下拉框（中文/English） |
| **预估工时** | 6h |
| **依赖关系** | S4-T03, S4-T04 |
| **并行任务** | ❌ 依赖语言包完成 |
| **涉及文件** | `frontend/app.py` (修改, 全局i18n集成), `frontend/pages/settings.py` (修改), `frontend/pages/dashboard.py` (修改), `frontend/pages/onboarding.py` (修改), `frontend/pages/audit_log.py` (修改) |
| **验收标准** | - 所有页面文本通过gettext()渲染<br>- 语言切换下拉框在导航栏或设置页面<br>- 切换语言后st.rerun()刷新所有文本<br>- 动态内容（错误消息/通知）也正确翻译<br>- 缺失翻译显示英文fallback（不崩溃）<br>- TC-P2-008语言切换测试通过<br>- TC-P2-010动态内容翻译测试通过<br>- TC-P2-011 XSS防护测试通过（恶意脚本不执行） |

**工作量说明**: 此任务涉及5+文件的全文替换，工作量大但机械性强

---

### S4-T06: 实现Keyboard Shortcuts键盘快捷键

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T06 |
| **描述** | 新建 `frontend/components/shortcuts.js`（或直接在app.py中注入JavaScript），实现全局键盘快捷键监听：Cmd/Ctrl+S保存设置、Cmd/Ctrl+K打开全局搜索、Cmd/Ctrl+,打开Settings、Cmd/Ctrl+/显示快捷键帮助面板、Esc关闭弹窗、Enter确认对话框，使用document.addEventListener('keydown')捕获按键 |
| **预估工时** | 4h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S4-T01并行 |
| **涉及文件** | `frontend/app.py` (修改, 注入JS代码) 或 `frontend/components/shortcuts.js` (新建) |
| **验收标准** | - Cmd+S在Settings页面触发表单保存<br>- Cmd+K打开全局搜索弹窗（如已实现）<br>- Cmd+,跳转到Settings页面<br>- Cmd+/显示快捷键帮助面板（列出所有快捷键）<br>- Esc关闭当前打开的dialog/modal<br>- Enter触发表单提交或dialog确认<br>- 快捷键不在输入框内触发（focus在input时不拦截）<br>- Mac(Cmd)和Windows(Ctrl)均支持 |

**快捷键参考**: 报告5.8节的Keyboard Shortcuts设计表

---

### S4-T07: 实现SkillMarketAPI 6个API端点

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T07 |
| **描述** | 修改 `opc_manager/skill_marketplace_api.py`（已存在），完善/新增6个RESTful API端点（FastAPI Router）：GET /api/skills（列表+分页+排序+筛选）、GET /api/skills/{skill_id}（详情+README+依赖）、POST /api/skills/{skill_id}/install（安装+幂等+依赖检查）、DELETE /api/skills/{skill_id}/uninstall（卸载+级联删除+回滚）、GET /api/skills/my（已安装列表）、GET /api/skills/search（全文搜索+标签匹配） |
| **预估工时** | 6h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S4-T01/S4-T03并行 |
| **涉及文件** | `opc_manager/skill_marketplace_api.py` (修改/增强, +300行) |
| **验收标准** | - GET /api/skills?page=1&page_size=20&sort=popular 返回分页列表<br>- GET /api/skills/{id} 返回skill详情（name/description/version/readme/dependencies）<br>- POST /install 幂等安装（重复安装返回already_installed）<br>- DELETE /uninstall 级联删除关联数据<br>- GET /my 仅返回已安装skills<br>- GET /search?q=xxx 全文搜索匹配<br>- OpenAPI Schema自动生成（FastAPI自带）<br>- TC-P2-002至TC-P2-007全部实现 |

**API契约参考**: 报告2.3节的SkillMarketAPI端点定义

---

### S4-T08: 创建技能市场前端MVP页面

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T08 |
| **描述** | 新建 `frontend/pages/skill_market.py`，实现技能市场浏览/安装/管理UI：顶部搜索栏+分类筛选（st.selectbox）、技能卡片网格（st.columns 3列布局，每卡显示图标+名称+简介+安装数+安装按钮）、技能详情弹窗（点击卡片展开README+版本+依赖）、"我的技能"Tab页（已安装技能列表+卸载按钮）、安装进度指示 |
| **预估工时** | 6h |
| **依赖关系** | S4-T07 |
| **并行任务** | ❌ 依赖API端点完成 |
| **涉及文件** | `frontend/pages/skill_market.py` (新建, ~450行) |
| **验收标准** | - 技能市场首页显示热门技能列表<br>- 搜索框实时过滤（debounce 500ms）<br>- 分类筛选（全部/效率/沟通/分析/财务...）<br>- 技能卡片显示：图标/名称/一句话描述/安装次数<br>- 点击"安装"按钮调用POST /install API<br>- 安装中显示spinner+进度<br>- 安装成功后按钮变为"已安装"<br>- "我的技能"Tab显示已安装列表+卸载按钮<br>- 技能详情弹窗显示完整README |

---

### S4-T09: 集成技能市场到主导航

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T09 |
| **描述** | 修改 `frontend/app.py` 导航栏，新增"🛒 技能市场"Tab或Skills页面内的子入口，点击后渲染skill_market页面；同时在Dashboard快捷操作面板添加"浏览技能市场"入口 |
| **预估工时** | 2h |
| **依赖关系** | S4-T08 |
| **并行任务** | ❌ 依赖技能市场UI完成 |
| **涉及文件** | `frontend/app.py` (修改导航) |
| **验收标准** | - 导航栏显示"🛒 技能市场"入口<br>- 技能市场作为独立页面访问<br>- Skills页面内有快捷链接<br>- 页面加载流畅 |

---

### S4-T10: 实现全局搜索后端API

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T10 |
| **描述** | 新建 `opc_manager/search_service.py`（或在search_processor.py中增强），实现GlobalSearch类：search(query: str, modules: List[str]=None, limit: int=10)方法跨模块搜索（tasks/skills/audit_logs/deliverables/knowledge）、支持全文检索（关键词匹配）和模糊搜索（编辑距离≤2）、返回统一格式的SearchResult列表（title/module/score/excerpt/highlight）、缓存热门搜索（LRU Cache, 100条） |
| **预估工时** | 4h |
| **依赖关系** | 无 |
| **并行任务** | ✅ 可与S4-T01并行 |
| **涉及文件** | `opc_manager/search_service.py` (新建) 或 `opc_manager/search_processor.py` (修改) |
| **验收标准** | - search("销售报告")返回相关tasks/emails/files<br>- modules参数限定搜索范围<br>- 结果按相关性评分排序<br>- 每条结果包含高亮摘要片段<br>- 搜索性能：1万条数据<500ms<br>- 缓存命中时<50ms<br>- 无SQL注入/XSS风险（参数化查询+输出转义） |

---

### S4-T11: 实现全局搜索前端UI

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T11 |
| **描述** | 修改 `frontend/app.py`，实现全局搜索UI：Cmd+K触发的搜索弹窗（st.dialog或自定义overlay）、搜索输入框（st.text_input autofocus）、实时搜索结果列表（输入即搜索，debounce 300ms）、结果分类显示（任务/邮件/文件/日志分组）、点击结果跳转到对应页面/高亮定位、最近搜索历史（localStorage equivalent via session_state） |
| **预估工时** | 5h |
| **依赖关系** | S4-T10 |
| **并行任务** | ❌ 依赖搜索后端完成 |
| **涉及文件** | `frontend/app.py` (修改, 全局搜索弹窗) |
| **验收标准** | - Cmd+K打开搜索弹窗（或点击搜索图标）<br>- 输入框自动聚焦<br>- 输入后300ms显示搜索结果<br>- 结果按类型分组显示（任务/邮件/文件/日志）<br>- 每条结果显示标题+摘要+来源模块<br>- 点击结果关闭弹窗并跳转<br>- 显示最近5条搜索历史<br>- 无结果时显示"未找到相关内容"<br>- ESC关闭搜索弹窗 |

---

### S4-T12: 编写i18n和Theme测试

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T12 |
| **描述** | 新建 `tests_v020/test_i18n.py` 和 `tests_v020/test_theme.py`：i18n测试包括语言包加载/切换/缺失翻译fallback/XSS防护/变量插值（TC-P2-008至TC-P2-011）；Theme测试包括CSS变量正确性/切换持久化/对比度合规性 |
| **预估工时** | 3h |
| **依赖关系** | S4-T03, S4-T01 |
| **并行任务** | ✅ 可与S4-T08/S4-T11并行 |
| **涉及文件** | `tests_v020/test_i18n.py` (新建, ~150行), `tests_v020/test_theme.py` (新建) |
| **验收标准** | - i18n 20+测试用例<br>- Theme 10+测试用例<br>- XSS payload测试通过<br>- 覆盖率≥90% |

---

### S4-T13: 编写SkillMarket和Search测试

| 属性 | 值 |
|------|-----|
| **任务ID** | S4-T13 |
| **描述** | 新建 `tests_v020/test_skill_market.py`：6个API端点的契约测试（TC-P2-001 OpenAPI Schema验证）、并发安装测试（TC-P2-002并发幂等性）、搜索功能测试、权限控制测试；补充search_service单元测试 |
| **预估工时** | 4h |
| **依赖关系** | S4-T07, S4-T10 |
| **并行任务** | ✅ 可与S4-T12并行 |
| **涉及文件** | `tests_v020/test_skill_market.py` (新建, ~350行) |
| **验收标准** | - TC-P2-001至TC-P2-007全部实现<br>- 并发安装测试通过（10线程同时安装同一技能）<br>- OpenAPI Schema路径完整（6个endpoint）<br>- SkillMarket API覆盖率≥85%<br>- SearchService覆盖率≥85% |

---

### Sprint 4 任务汇总

| 任务ID | 描述 | 工时 | 依赖 | 并行组 |
|--------|------|------|------|--------|
| S4-T01 | ThemeManager主题管理器 | 3h | 无 | A |
| S4-T02 | 主题切换前端UI | 3h | T01 | B |
| S4-T03 | I18nManager国际化 | 4h | 无 | A |
| S4-T04 | 中英文语言包 | 4h | T03 | C |
| S4-T05 | i18n集成前端 | 6h | T03,T04 | D |
| S4-T06 | Keyboard Shortcuts | 4h | 无 | A |
| S4-T07 | SkillMarketAPI 6端点 | 6h | 无 | A |
| S4-T08 | 技能市场前端MVP | 6h | T07 | E |
| S4-T09 | 技能市场集成导航 | 2h | T08 | F |
| S4-T10 | 全局搜索后端API | 4h | 无 | A |
| S4-T11 | 全局搜索前端UI | 5h | T10 | G |
| S4-T12 | i18n/Theme单元测试 | 3h | T01,T03 | H |
| S4-T13 | SkillMarket/Search测试 | 4h | T07,T10 | I |
| **合计** | | **58h** | | |

**关键路径**: T03 → T04 → T05 (14h串行) 或 T07 → T08 → T09 (14h串行)

---

## 📊 Sprint甘特图（文本版）

```
Week:     1    2    3    4    5    6    7
          │    │    │    │    │    │    │
Sprint 1: [====零配置启动====]
          
S1-T01   ██
S1-T04   ██              ← 并行A组
S1-T13   ██
          
S1-T02        ██
S1-T03        ██       ← 并行B组（依赖T01）
S1-T06        ██
          
S1-T04   ██              
S1-T05             ██    ← 并行C组（依赖T01,T04）
          
S1-T07        ██          ← 并行D组
S1-T01   ██
          
S1-T08             ██     ← 并行E组（依赖T01,T07）
          
S1-T09                  ██████  ← 关键路径F组
S1-T14                  ██████  （依赖T02,T03,T05,T06,T09,T13）
S1-T15                        ██  ← 最终集成J组
          
S1-T10                  ██     ← 并行G组
S1-T12                  ██
          
S1-T11                   ████   ← 并行H组（依赖T07,T08）
          
S1-T16                  ████   ← 测试K组（可与F/I/J并行）
S1-T17                  ██


Sprint 2:      [==企业微信+体验升级==]
               
S2-T01               ██
S2-T05               ██     ← 并行A组
S2-T08               ██
S2-T11               ██
               
S2-T02                    ████   ← 依赖T01
S2-T03                         ██████  ← 依赖T02
S2-T04                              ████   ← 依赖T03（关键路径）
               
S2-T06                    ██     ← 并行E组（依赖T05）
S2-T07                    ██
               
S2-T09                    ██████  ← 并行F组（依赖T08）
S2-T10                         ██     ← 依赖T09
               
S2-T12                    ████   ← 并行H组（依赖T11）
               
S2-T13                    ██     ← 测试I组
S2-T14                    ████   ← 测试J组


Sprint 3:           [===数据价值可视化===]
                    
S3-T01                    ██
S3-T04                    ██     ← 并行A组
S3-T07                    ██
S3-T09                    ██
                    
S3-T02                         ██████  ← 依赖T01
S3-T03                              ████   ← 依赖T01,T02
                    
S3-T05                         ██████  ← 并行D组（依赖T04）
S3-T06                              ██     ← 依赖T05
                    
S3-T08                         ████   ← 并行F组（依赖T07）
                    
S3-T10                              ██████  ← 并行G组（依赖T09）⚠️高风险
                    
S3-T11                         ████   ← 测试H组
S3-T12                         ████   ← 测试I组


Sprint 4:                [==打磨+国际化==]
                         
S4-T01                         ██
S4-T03                         ████   ← 并行A组
S4-T06                         ████
S4-T07                         ██████
S4-T10                         ████
                         
S4-T02                              ██     ← 依赖T01
                         
S4-T04                              ████   ← 依赖T03
S4-T05                                   ██████████  ← 依赖T03,T04 ⚠️工作量大
                         
S4-T08                                   ██████  ← 依赖T07
S4-T09                                        ██     ← 依赖T08
                         
S4-T11                                   ██████  ← 依赖T10
                         
S4-T12                                   ████   ← 测试H组
S4-T13                                   ████   ← 测试I组


里程碑:
─────────────────────────────────────────────────────────→
M1: P0 Settings可用     ████ (Week 2 End)
M2: P0 企业微信可用           ████ (Week 3-4 Mid)
M3: P1 全部功能可用                ██████ (Week 5 End)
M4: P2 核心功能可用                      ██████ (Week 7 End)
GA: v0.2.0 Release                           ██ (Week 7 End)
```

---

## 🔗 依赖关系图

```
层级0 (无依赖):
├─ S1-T01 SettingsManager框架
├─ S1-T04 SecureStorage增强
├─ S1-T13 OnboardingManager
├─ S2-T01 WeChat签名验证
├─ S2-T05 ErrorHandler映射表
├─ S2-T08 AuditLog查询API
├─ S2-T11 UndoManager API
├─ S3-T01 DataManager导出
├─ S3-T04 DashboardConfig
├─ S3-T07 ExportManager增强
├─ S3-T09 SSE ProgressEmitter
├─ S4-T01 ThemeManager
├─ S4-T03 I18nManager
├─ S4-T06 Keyboard Shortcuts
├─ S4-T07 SkillMarketAPI
└─ S4-T10 SearchService

层级1 (依赖层级0):
├─ S1-T02 LLM配置Tab ────────┐
├─ S1-T03 SMTP配置Tab ───────┤
├─ S1-T06 安全/个人Tab ──────┤→ S1-T09 Settings UI
├─ S1-T07 EventBus ──────────┤
├─ S2-T02 消息解析 ──────────┘
├─ S3-T02 DataManager导入 ───→ S3-T03 数据管理UI
├─ S3-T05 Dashboard UI ──────→ S3-T06 Dashboard导航
├─ S4-T02 主题切换UI
├─ S4-T04 语言包 ────────────→→ S4-T05 i18n集成
├─ S4-T08 技能市场UI ────────→ S4-T09 技能市场导航
└─ S4-T11 搜索UI

层级2 (依赖层级1):
├─ S1-T05 API Key管理 ──────┐ (依赖S1-T01,S1-T04)
├─ S1-T08 ConfigManager集成 ─┤ (依赖S1-T01,S1-T07)
├─ S2-T03 WeChat路由对接 ────┘ (依赖S2-T02)
├─ S2-T06 ErrorHandler前端 ──┐ (依赖S2-T05)
├─ S2-T07 ErrorHandler后端 ──┤
├─ S2-T09 审计日志UI ────────┘ (依赖S2-T08)
├─ S2-T12 Undo前端UI ──────── (依赖S2-T11)
├─ S3-T08 多格式导出前端 ──── (依赖S3-T07)
└─ S3-T10 SSE进度条前端 ──── (依赖S3-T09) ⚠️高风险

层级3 (依赖层级2):
├─ S1-T09 Settings UI ───────→ S1-T14 Onboarding UI
├─ S1-T11 LLMService动态Key ── (依赖S1-T07,S1-T08)
├─ S1-T12 EmailSkill SMTP检查 (依赖S1-T03)
├─ S2-T04 WeChat E2E测试 ──── (依赖S2-T03)
├─ S2-T10 审计日志导航 ────── (依赖S2-T09)
└─ S1-T14 Onboarding UI ─────→ S1-T15 Onboarding集成

层级4 (最终集成):
└─ S1-T15 Onboarding集成入口 (依赖S1-T13,S1-T14)
```

---

## ⚠️ 风险点识别

### 🔴 高风险（需要提前验证和重点关注）

| 风险ID | 风险描述 | 影响任务 | 概率 | 影响 | 缓解措施 |
|--------|---------|---------|------|------|---------|
| **R-01** | Streamlit状态管理复杂度高（Onboarding/Dashboard/Settings间状态同步） | S1-T09, S1-T14, S1-T15, S3-T05 | 中 | 高 | Prototype先行（Week 1先做PoC）；充分Session State测试；参考报告7.1节代码示例 |
| **R-02** | Settings实时生效边界情况（并发保存/模块热重载/缓存一致） | S1-T07, S1-T08, S1-T11 | 中 | 中 | Observer Pattern + Event Bus（S1-T07）；单元测试覆盖并发场景；集成测试验证LLMService热重载 |
| **R-03** | SSE实时进度条与Streamlit兼容性问题 | S3-T09, S3-T10 | 低 | 高 | Week 5初验证SSE可行性；备选方案：轮询（polling every 1s）；考虑streamlit-extras组件 |
| **R-04** | ConfigManager改造影响全局（所有依赖config的模块） | S1-T08 | 低 | 极高 | 全量回归612个原有测试；渐进式迁移（先新增Settings读取路径，再切换默认）；保留环境变量回退 |

### 🟡 中等风险

| 风险ID | 风险描述 | 影响任务 | 概率 | 影响 | 缓解措施 |
|--------|---------|---------|------|------|---------|
| **R-05** | 企业微信WeChatGateway签名验证/消息解析边缘Case | S2-T01, S2-T02, S2-T03 | 中 | 中 | 充分单元测试（S2-T14）；Mock企业微信服务器做E2E测试（S2-T04）；参考企业微信官方文档的XML规范 |
| **R-06** | i18n集成工作量大（200+字符串替换×5个文件） | S4-T05 | 高 | 中 | 使用IDE批量重构工具；分批次替换（先Settings再其他）；自动化脚本检测遗漏的硬编码字符串 |
| **R-07** | 数据导入导出一致性（导出期间数据被修改） | S3-T01, S3-T02 | 低 | 中 | Snapshot Isolation（事务级别锁）；导出前锁定写入；导入前强制备份 |
| **R-08** | 第三方依赖Breaking Change（streamlit/fastapi/pydantic版本升级） | 全局 | 低 | 中 | 锁定pyproject.toml依赖版本；定期pip-compile更新；CI测试多版本兼容性 |

### 🟢 低风险

| 风险ID | 风险描述 | 影响任务 | 缓解措施 |
|--------|---------|---------|---------|
| **R-09** | SecureStorage新旧加密方案兼容 | S1-T04 | 保留旧Fernet方法deprecated；新数据用AES-256-GCM；迁移脚本处理旧数据 |
| **R-10** | Dashboard组件数据源依赖（FinanceSkill/CRMSkill可能无数据） | S3-T05 | 空状态设计（无数据显示"暂无数据"提示）；Mock数据用于演示 |
| **R-11** | SkillMarket API无真实后端（v0.2.0仅MVP） | S4-T07, S4-T08 | 使用本地Mock数据；预留Remote API接口；文档标注"MVP阶段仅本地技能" |

---

## 🎯 里程碑定义

### M1: Sprint 1完成 — "零配置启动"达成 ✅

**时间点**: Week 2 End  
**准入条件**:
- [ ] S1-T01至S1-T17全部完成
- [ ] Settings页面5个Tab均可正常使用
- [ ] 首次启动自动生成加密Key
- [ ] SMTP配置UI可测试连接
- [ ] Onboarding 3步引导流程完整
- [ ] LLM配置修改后即时生效（无需重启）
- [ ] 单元测试：Settings(50+) + Onboarding(20+) = 70+新测试全绿
- [ ] 612个原有测试零回归

**验证方式**:
```bash
# 冒烟测试脚本
cd /Users/lin/trae_projects/OPC-Agents
rm -rf ~/.opc-agents  # 模拟首次启动
python -m frontend.app &
# 验证：
# 1. 自动弹出Onboarding
# 2. 完成引导后进入Settings
# 3. 配置LLM→保存→立即生效
# 4. 配置SMTP→测试连接成功
# 5. 检查~/.opc-agents/.env.local存在加密Key
```

---

### M2: Sprint 2完成 — "企业微信+体验升级"达成 ✅

**时间点**: Week 4 End (Mid)  
**准入条件**:
- [ ] M1全部满足
- [ ] S2-T01至S2-T14全部完成
- [ ] 企业微信消息接收→解析→路由→执行→回复全链路通畅
- [ ] 签名验证防止伪造请求（TC-P0-019通过）
- [ ] 长消息(>2000字)自动分段（TC-P0-021通过）
- [ ] 所有异常显示中文友好提示（无技术术语暴露）
- [ ] 操作日志前端可查看/筛选/搜索
- [ ] Undo撤销功能前端入口可用
- [ ] 单元测试：ErrorHandler(25+) + WeChat(30+) + Undo(15+) = 70+新测试全绿

**验证方式**:
```bash
# 企业微信E2E测试
pytest tests_v020/test_wechat_e2e.py -v  # 全绿
# 错误提示测试
pytest tests_v020/test_error_handler.py -v  # 全绿
# 审计日志性能测试（1万条<100ms）
pytest tests_v020/test_audit_log_performance.py -v  # 全绿
```

---

### M3: Sprint 3完成 — "数据价值可视化"达成 ✅

**时间点**: Week 5 End  
**准入条件**:
- [ ] M2全部满足
- [ ] S3-T01至S3-T12全部完成
- [ ] 一键ZIP备份导出功能可用（包含tasks/skills/logs/settings）
- [ ] ZIP导入恢复功能可用（版本校验+冲突处理）
- [ ] Dashboard默认4组件正常显示（收入趋势+客户健康度+最近任务+快捷操作）
- [ ] Dashboard支持添加/移除/重排组件
- [ ] 多格式批量导出（PDF/Excel/Word）可用
- [ ] SSE实时进度条在任务执行时显示（⚠️如技术可行）
- [ ] 单元测试：DataManager(30+) + Dashboard(20+) + Export(20+) + SSE(15+) = 85+新测试全绿

**验证方式**:
```bash
# 数据导出导入测试
python -c "
from opc_manager.data_manager import DataManager
dm = dm.export_all()
assert dm.import_data(dm.zip_path)['success_count'] > 0
"
# Dashboard测试
pytest tests_v020/test_dashboard_config.py -v  # 全绿
# 性能测试
# 1万任务导出 < 5秒
# 1万日志查询 < 100ms
```

---

### M4: Sprint 4完成 — "打磨+国际化"达成 ✅

**时间点**: Week 7 End  
**准入条件**:
- [ ] M3全部满足
- [ ] S4-T01至S4-T13全部完成
- [ ] 暗色/亮色主题切换流畅（右上角按钮）
- [ ] 中英文切换正常（导航栏语言选择器）
- [ ] 核心快捷键可用（Cmd+S/Cmd+K/Cmd+,/Esc/Enter）
- [ ] 技能市场MVP可用（浏览/搜索/安装/卸载）
- [ ] 全局搜索可用（Cmd+K弹窗+跨模块搜索）
- [ ] 单元测试：i18n(20+) + Theme(10+) + SkillMarket(40+) + Search(20+) = 90+新测试全绿
- [ ] **总测试数 ≥ 900** (原612 + Sprint1-4新增 ≥ 288)

**验证方式**:
```bash
# 国际化测试
pytest tests_v020/test_i18n.py -v  # 全绿（含XSS测试）
# 技能市场API测试
pytest tests_v020/test_skill_market.py -v  # 全绿（含并发测试）
# 全量测试
pytest tests/ tests_v020/ -v --tb=short \
  | tail -1 | grep -E "\d+ passed"  # 应该显示 900+ passed
# 覆盖率检查
pytest tests/ tests_v020/ --cov=opc_manager --cov-report=term-missing \
  | grep -E "TOTAL.*\d+%"  # 应该 ≥ 80%
```

---

### GA: v0.2.0 正式发布 🚀

**时间点**: Week 7 End (M4之后1-2天缓冲)  
**发布Checklist**:
- [ ] M1-M4全部里程碑达成
- [ ] 全部62个原子任务完成Code Review
- [ ] 测试总数 ≥ 900 且通过率100%
- [ ] 代码覆盖率 ≥ 80%（新增模块 ≥ 85%）
- [ ] `pip-audit` 无高危CVE漏洞
- [ ] flake8/mypy静态检查通过
- [ ] 性能达标：启动<5秒 / Settings加载<2秒 / 企微响应<10秒
- [ ] CHANGELOG.md 更新完整
- [ ] README.md 更新v0.2.0特性
- [ ] version.py 版本号 → 0.2.0
- [ ] pyproject.toml 依赖更新
- [ ] .env.example 更新注释
- [ ] Git Tag: v0.2.0
- [ ] CI/CD Pipeline全绿（如有）

---

## 📈 资源分配建议

### 团队规模假设

| 角色 | 推荐人数 | 主要负责Sprint |
|------|---------|---------------|
| **后端工程师** | 2人 | Sprint 1-2 (Settings/WeChat/ErrorHandler/DataManager) |
| **前端工程师** | 1-2人 | Sprint 1-4 (所有UI页面) |
| **测试工程师** | 1人 | 全程（贯穿每个Sprint的测试任务） |
| **DevOps** | 0.5人 | Sprint 4 (发布准备/CI配置) |

### 并行执行策略

**最大并行度**: 8组任务可同时进行（见各Sprint的并行组标记）

**推荐并行组合**:

```
Week 1-2 (Sprint 1):
┌─ 后端A: S1-T01→T02→T05→T07→T08→T11 (Settings核心链路)
├─ 后端B: S1-T04→T03→T06→T10→T12 (SecureStorage+SMTP+Email)
├─ 前端A: S1-T13→T14→T15 (Onboarding全流程)
├─ 前端B: S1-T09 (Settings UI, 依赖后端A/B产出)
└─ 测试:   S1-T16→T17 (Settings+Onboarding测试)

Week 3-4 (Sprint 2):
┌─ 后端A: S2-T01→T02→T03→T04 (WeChat全链路)
├─ 后端B: S2-T05→T06→T07 (ErrorHandler前后端)
├─ 前端:   S2-T08→T09→T10 (审计日志UI) + S2-T11→T12 (Undo UI)
└─ 测试:   S2-T13→T14 (ErrorHandler+WeChat测试)

Week 5 (Sprint 3):
┌─ 后端A: S3-T01→T02 (DataManager导入导出)
├─ 后端B: S3-T04→T07→T09 (Dashboard+Export+SSE)
├─ 前端:   S3-T03→T05→T06→T08→T10 (数据管理UI+Dashboard+ExportUI+SSE UI)
└─ 测试:   S3-T11→T12 (DataManager+Dashboard/Export测试)

Week 6-7 (Sprint 4):
┌─ 后端A: S4-T03→T04→T05 (i18n全流程)
├─ 后端B: S4-T01→T02 (Theme) + S4-T07→S4-T10 (SkillMarket+Search)
├─ 前端:   S4-T05→S4-T06→S4-T08→S4-T09→S4-T11 (i18n集成+Shortcut+SkillMarketUI+SearchUI)
└─ 测试:   S4-T12→S4-T13 (i18n/Theme+SkillMarket/Search测试)
```

---

## 📝 技术债务处理建议

### 建议在Sprint 1-2期间一并解决的技术债务

| 债务ID | 债务描述 | 建议处理时机 | 对应任务 |
|--------|---------|-------------|---------|
| **TD-01** | 硬编码配置路径（config.py多处） | Sprint 1 S1-T08时一并抽象 | S1-T08 |
| **TD-02** | frontend/app.py过大（建议拆分模块） | Sprint 1-2 逐步拆分 | S1-T09, S2-T09, S3-T03 等（拆分为pages/目录） |
| **TD-03** | 全局状态过多（opc_manager/__init__.py） | Sprint 2 引入Dependency Injection | S2-T05 (ErrorHandler) 时考虑 |
| **TD-04** | 缺少Type Hints（部分老旧模块） | 各Sprint新代码必须加，老代码逐步补 | 所有新文件必须有≥90% Type Hints |
| **TD-05** | 单体测试文件过大（test_e2e_real.py） | Sprint 2-3 拆分 | S2-T14 (wechat测试) / S3-T11 (data测试) 时拆分 |
| **TD-06** | 日志格式不统一（各模块自行定义） | Sprint 1 统一使用loguru | S1-T01 (SettingsManager) 时确立规范 |

---

## 🔄 变更管理流程

### 任务状态流转

```
TODO → IN_PROGRESS → IN_REVIEW → DONE → VERIFIED
  ↑         │           │          │         │
  │         ↓           ↓          ↓         │
  └──── BLOCKED ←──── REWORK ←── FAILED ←───┘
```

### 状态定义

| 状态 | 定义 | 进入条件 | 退出条件 |
|------|------|---------|---------|
| **TODO** | 任务已规划，尚未开始 | Sprint Plan创建 | 开发者领取任务 |
| **IN_PROGRESS** | 正在开发中 | 开始编码 | 提交Code Review |
| **IN_REVIEW** | 等待Code Review | 提交PR/MR | Review通过或Request Changes |
| **DONE** | 开发完成，等待验证 | Review通过 | 测试验证通过 |
| **VERIFIED** | 任务完全完成（开发+测试+文档） | 测试通过+文档更新 | 里程碑确认 |
| **BLOCKED** | 被依赖任务阻塞 | 前置任务未完成 | 前置任务完成 |
| **REWORK** | Review不通过，需修改 | Reviewer提出修改意见 | 重新提交Review |
| **FAILED** | 测试未通过 | 测试执行失败 | Bug修复后重新测试 |

### 每日站会检查项

- [ ] 昨天完成了哪些任务？
- [ ] 今天计划做什么？
- [ ] 有没有遇到阻塞？（检查BLOCKED状态任务）
- [ ] 有没有发现新的风险？（更新风险登记簿）

### 每周Sprint Review检查项

- [ ] 本周计划的任务完成率（目标≥90%）
- [ ] 是否有关键路径上的任务延期？
- [ ] 新发现的Bug是否已记录和分配？
- [ ] 下周任务是否需要调整？
- [ ] 里程碑是否仍然可达？

---

## 📚 附录

### 附录A: 文件变更总清单

#### 新增文件（26个）

| 文件路径 | 行数估算 | 所属Sprint | 对应任务 |
|---------|---------|-----------|---------|
| `opc_manager/settings.py` | ~500 | S1 | S1-T01 |
| `opc_manager/event_bus.py` | ~150 | S1 | S1-T07 |
| `opc_manager/onboarding.py` | ~200 | S1 | S1-T13 |
| `opc_manager/error_handler.py` | ~300 | S2 | S2-T05 |
| `opc_manager/dashboard_config.py` | ~200 | S3 | S3-T04 |
| `opc_manager/theme_manager.py` | ~150 | S4 | S4-T01 |
| `opc_manager/i18n.py` | ~250 | S4 | S4-T03 |
| `opc_manager/search_service.py` | ~200 | S4 | S4-T10 |
| `frontend/pages/settings.py` | ~600 | S1 | S1-T09 |
| `frontend/pages/onboarding.py` | ~400 | S1 | S1-T14 |
| `frontend/pages/dashboard.py` | ~500 | S3 | S3-T05 |
| `frontend/pages/skill_market.py` | ~450 | S4 | S4-T08 |
| `frontend/pages/audit_log.py` | ~350 | S2 | S2-T09 |
| `locales/zh_CN.yaml` | ~300 | S4 | S4-T04 |
| `locales/en_US.yaml` | ~300 | S4 | S4-T04 |
| `tests_v020/test_settings.py` | ~400 | S1 | S1-T16 |
| `tests_v020/test_onboarding.py` | ~200 | S1 | S1-T17 |
| `tests_v020/test_error_handler.py` | ~250 | S2 | S2-T13 |
| `tests_v020/test_wechat_e2e.py` | ~300 | S2 | S2-T04 |
| `tests_v020/test_data_manager.py` | ~300 | S3 | S3-T11 |
| `tests_v020/test_dashboard_config.py` | ~150 | S3 | S3-T12 |
| `tests_v020/test_export_enhanced.py` | ~150 | S3 | S3-T12 |
| `tests_v020/test_i18n.py` | ~150 | S4 | S4-T12 |
| `tests_v020/test_skill_market.py` | ~350 | S4 | S4-T13 |
| `scripts/migrate_v019_to_v020.py` | ~200 | Pre-release | DevOps |
| **新增合计** | **~6,000行** | | |

#### 修改文件（14个）

| 文件路径 | 修改内容 | 所属Sprint | 对应任务 |
|---------|---------|-----------|---------|
| `frontend/app.py` | 新增路由/导航/Onboarding集成/i18n/主题/搜索/快捷键 | S1-S4 | S1-T15, S2-T06,S2-T10, S3-T03,S3-T06,S3-T08,S3-T10, S4-T02,S4-T05,S4-T06,S4-T09,S4-T11 |
| `opc_manager/config.py` | 从SettingsManager读取配置 | S1 | S1-T08 |
| `opc_manager/secure_storage.py` | 增强字段级加密 | S1 | S1-T04 |
| `opc_manager/wechat_gateway.py` | 签名验证修复+消息路由 | S2 | S2-T01,S2-T02,S2-T03 |
| `opc_manager/email_skill.py` | SMTP配置检查 | S1 | S1-T12 |
| `opc_manager/llm_service.py` | 动态API Key+EventBus订阅 | S1 | S1-T11 |
| `opc_manager/audit_log.py` | 查询API扩展 | S2 | S2-T08 |
| `opc_manager/undo_manager.py` | 前端API扩展 | S2 | S2-T11 |
| `opc_manager/data_manager.py` | ZIP导入导出 | S3 | S3-T01,S3-T02 |
| `opc_manager/export/manager.py` | 批量导出+进度回调 | S3 | S3-T07 |
| `opc_manager/progress_emitter.py` | SSE支持 | S3 | S3-T09 |
| `opc_manager/skill_marketplace_api.py` | 6个API端点 | S4 | S4-T07 |
| `opc_manager/version.py` | 版本号→0.2.0 | GA | DevOps |
| `pyproject.toml` | 依赖更新 | GA | DevOps |
| **修改合计** | **~2,000行改动** | | |

**总代码量**: 新增~6,000行 + 修改~2,000行 = **~8,000行**（与报告附录A一致）

---

### 附录B: 测试用例索引

| 测试文件 | 对应报告章节 | 用例数 | 覆盖率目标 |
|---------|------------|-------|-----------|
| `tests_v020/test_settings.py` | 4.2.1 (TC-P0-001~008) | 50+ | ≥85% |
| `tests_v020/test_onboarding.py` | 4.3.1 (TC-P1-001~004) | 20+ | ≥90% |
| `tests_v020/test_error_handler.py` | 4.3.2 (TC-P1-005~009) | 25+ | ≥95% |
| `tests_v020/test_wechat_e2e.py` | 4.2.4 (TC-P0-017~022) | 30+ | ≥80% |
| `tests_v020/test_data_manager.py` | 4.3.3 (TC-P1-010~014) | 30+ | ≥90% |
| `tests_v020/test_dashboard_config.py` | 4.3.4 (TC-P1-015~016) | 20+ | ≥85% |
| `tests_v020/test_export_enhanced.py` | 新增 | 20+ | ≥85% |
| `tests_v020/test_i18n.py` | 4.4.2 (TC-P2-008~011) | 20+ | ≥90% |
| `tests_v020/test_skill_market.py` | 4.4.1 (TC-P2-001~007) | 40+ | ≥85% |
| **合计** | | **255+** | |

加上原有612个测试 = **867+**（接近900目标，剩余差距由集成/E2E测试补充）

---

### 附录C: 术语表

| 术语 | 全称 | 定义 |
|------|------|------|
| **Atomic Task** | 原子任务 | 不可再分的最小工作单元，通常2-8小时完成 |
| **Sprint** | 迭代周期 | Scrum中的固定长度开发周期（本文为1.5-2周） |
| **Critical Path** | 关键路径 | 依赖链最长的任务序列，决定项目最短工期 |
| **Parallel Group** | 并行组 | 可同时执行的相互无依赖的任务集合 |
| **Milestone** | 里程碑 | 项目中的重要节点，用于验证阶段性成果 |
| **E2E** | End-to-End | 端到端测试，验证完整用户场景 |
| **PoC** | Proof of Concept | 概念验证，用于验证技术可行性 |
| **SSE** | Server-Sent Events | 服务器推送事件，用于实时进度更新 |
| **EventBus** | 事件总线 | 发布-订阅模式的消息传递机制 |
| **i18n** | Internationalization | 国际化，支持多语言切换 |
| **GA** | General Availability | 正式发布，面向所有用户 |

---

### 附录D: 参考文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 完整分析报告 | `docs/v020_complete_analysis_report.md` | 7角色协作分析的完整输出（2144行） |
| 产品需求文档 | `docs/product-manager/PRD_V4.md` | PRD V4版本 |
| 安全设计方案 | `docs/internal/SECURITY_DESIGN.md` | STRIDE威胁建模和安全规范 |
| 架构设计文档 | `docs/internal/archive/ARCHITECTURE_DESIGN_V3.md` | V3架构设计 |
| 测试计划 | `docs/internal/TEST_PLAN_PHASE1.md` | Phase 1测试计划 |
| 版本历史 | `docs/CHANGELOG.md` | 变更日志 |
| 代码规范 | `CONTRIBUTING.md` | 贡献指南 |

---

## 📌 文档版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|---------|
| v1.0 | 2026-05-16 | AI Assistant | 初始版本，基于v0.2.0完整分析报告创建62个原子任务的Sprint规划 |

---

**文档结束**

*本Sprint规划文档基于 [OPC-Agents v0.2.0 完整分析报告](../v020_complete_analysis_report.md) 制定，共计4个Sprint、62个原子任务、预估280小时工作量。*
