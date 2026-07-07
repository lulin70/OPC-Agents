# OPC-Agents 硬约束清单（永不削减）

> **来源**: [Skill 生态借鉴分析](research/SKILL_ECOSYSTEM_RESEARCH.md) P0 改进项
> **理念**: 借鉴 [Ponytail](https://github.com/DietrichGebert/ponytail) 的"永不削减"硬约束边界
> **最后更新**: 2026-07-07 | **版本**: v0.3.4

---

## 1. 设计理念

Ponytail 的七层"懒惰阶梯"决策模型允许在编码层面极致精简，但明确划定了**永不削减的硬约束边界**：

> "Not lazy about: understanding the problem, input validation at trust boundaries,
> error handling that prevents data loss, security, accessibility,
> the calibration real hardware needs."

OPC-Agents 采纳同一理念：**简化可以，但以下约束永不妥协**。违反任一约束即阻塞发布，不得以"迭代速度"、"临时方案"、"YAGNI"为由削减。

---

## 2. 永不削减清单

### 2.1 安全类（Security — 永不妥协）

| # | 约束 | Rationale | 执行机制 | 状态 |
|---|------|-----------|----------|------|
| S1 | 密码存储必须使用带 salt 的 PBKDF2-HMAC-SHA256，禁止裸 SHA-256 | 裸 SHA-256 易被彩虹表破解；PBKDF2 + salt 抗暴力枚举 | `tests/test_auth.py` 验证；CI mypy 阻塞 | ✅ |
| S2 | 哈希比较必须使用 `hmac.compare_digest`，禁止 `==` | `==` 比较存在时序侧信道泄漏 | `tests/test_skill_marketplace.py` 验证 | ✅ |
| S3 | prompt injection 检测到后必须阻断 LLM 调用并模板降级 | 仅检测不阻断 = 形同虚设；阻断式降级才是防御 | `tests/test_input_validator.py` 验证阻断行为 | ✅ |
| S4 | 禁止在 localStorage 明文存储敏感信息（如 poc_secret） | 浏览器存储可被 XSS 读取 | 前端代码审查 | ✅ |
| S5 | PoC secret 不得在 staging 环境使用默认值 | 默认值 = 无认证 | 部署检查清单 | ✅ |

### 2.2 信任边界类（Trust Boundary Input Validation）

| # | 约束 | Rationale | 执行机制 | 状态 |
|---|------|-----------|----------|------|
| T1 | 用户输入/API 入口必须经 InputValidator 校验（21+ 模式 prompt injection 检测） | 信任边界是防御起点；未校验输入 = 注入入口 | `InputValidator` 前置于所有 LLM 调用 | ✅ |
| T2 | 专业版路由需 API Key 验证 | 无认证 = 公开服务被滥用 | 路由中间件 | ✅ |
| T3 | 测试中 API key 有效性必须进行轻量验证调用 | `is_available()` 仅检查存在性；无效 key 导致测试假失败 | `setUpClass` 轻量调用 | ✅ |

### 2.3 防数据丢失类（Error Handling That Prevents Data Loss）

| # | 约束 | Rationale | 执行机制 | 状态 |
|---|------|-----------|----------|------|
| D1 | `dispatcher.py` 在生产模式下 `_rbac is None` 时必须 fail-closed | fail-open = 无权限检查即放行 = 安全漏洞 | 单元测试验证 `RuntimeError` | ✅ |
| D2 | 共识门在关键决策失败时必须安全降级，禁止 fail-open 直接执行 | fail-open = 绕过共识 = 单点决策风险 | `ConsensusEngine` 降级路径测试 | ✅ |
| D3 | `encrypt_field` 失败时 fail-closed（加密失败不返回明文） | 加密失败返回明文 = 数据泄漏 | `tests/test_encryption.py` | ✅ |
| D4 | 审计日志链式哈希（prev_hash → current_hash），防篡改 | 无链式哈希 = 审计日志可被篡改 | `verify_chain()` + DB 迁移 v7 | ✅ |

### 2.4 架构类（Architecture — 不可变决策）

| # | 约束 | Rationale | 执行机制 | 状态 |
|---|------|-----------|----------|------|
| A1 | 三贤者系统必须采用并行投票架构（`asyncio.gather`），禁止串行流水线 | 串行 = 3×RTT 累加延迟；并行 = 1×RTT（取最慢） | 架构审查 + `tests/test_consensus.py` | ✅ |
| A2 | ConsensusEngine 必须作为核心决策机制**前置**介入所有关键决策点 | 后置补救 = 错误已执行；前置 = 阻止错误执行 | 关键决策点代码审查 | ✅ |
| A3 | DevSquad 被调用时优先尝试 LLM，LLM 不可用时才使用 MOCK | 默认 MOCK = 永远不验证真实路径 | `LLMBackend` fallback 逻辑 | ✅ |

### 2.5 构建可复现类（Reproducible Build）

| # | 约束 | Rationale | 执行机制 | 状态 |
|---|------|-----------|----------|------|
| B1 | 项目必须包含依赖锁文件（`requirements.lock`）以确保构建可复现 | 无锁文件 = 依赖漂移 = "在我机器上能跑" | CI 验证 lock 文件存在 | ✅ |
| B2 | `requirements.lock` 禁止包含 SSH 私有仓库依赖，必须用 PyPI 或 HTTPS+token | SSH 依赖 = CI/新环境无 key 即失败 | `tests/test_requirements.py` | ✅ |
| B3 | `release.yml` 必须包含 `publish-pypi` job 以完成 PyPI 包发布 | 无 PyPI publish = `pip install` 不可用 = 发布链路断裂 | CI workflow 检查 | ✅ |
| B4 | CI/CD jobs 必须包含 `timeout-minutes` 配置 | 无 timeout = 挂起 job 占用 runner 无限等待 | CI lint 检查 | ✅ |

### 2.6 测试质量类（Test Quality — 不可削弱）

| # | 约束 | Rationale | 执行机制 | 状态 |
|---|------|-----------|----------|------|
| Q1 | 发布前必须完成模拟真实用户使用的 E2E 测试 | 单元测试不覆盖集成路径；E2E = 真实用户视角 | `SKIP_E2E` 默认 "0"（不跳过）+ Playwright 真实浏览器 E2E（`tests/e2e/test_ui_playwright.py`，21 用例覆盖启动/导航/Chat/Deliverables 下载/Dashboard/Settings/多语言/健康检查） | ✅ |
| Q2 | E2E 测试默认不跳过（`SKIP_E2E` 默认值为 "0"） | 全局跳过 = 死测试陷阱；默认运行 = 暴露真实问题 | 环境变量检查 | ✅ |
| Q3 | 所有 async 函数必须包含返回类型注解（注解率 ≥80%） | 无注解 = 类型不可推断 = mypy 0 errors 的假象 | AST 检查 `node.returns is not None` | ✅ (87.5%) |
| Q4 | CI mypy 检查必须为阻塞状态（exit code 非零即失败） | mypy 非阻塞 = 类型错误被忽略 | CI workflow `continue-on-error: false` | ✅ |
| Q5 | 测试必须优先使用真实组件而非 Mock，尤其当 API 需要底层对象 | Mock = 测试 Mock 而非测试代码；715 处 Mock 是技术债 | 代码审查 + `TestQualityGuard` | ⏳ |

### 2.7 版本一致性类（Version Consistency）

| # | 约束 | Rationale | 执行机制 | 状态 |
|---|------|-----------|----------|------|
| V1 | 版本号必须在所有位置（VERSION 文件、README、代码注释）保持一致 | 不一致 = 用户安装错误版本 | `tests/test_version.py` + 三语 README CI | ✅ |
| V2 | 项目必须包含 `PROJECT_STATUS.md` 文档 | 无状态文档 = 真实进度不可追溯 | 文件存在检查 | ✅ |
| V3 | `mcp_server.py` 必须保持一致的模块/测试计数（149/2861） | 计数漂移 = SKILL.md 与实际不符 | `tests/test_mcp_server.py` | ✅ |

### 2.8 部署类（Deployment）

| # | 约束 | Rationale | 执行机制 | 状态 |
|---|------|-----------|----------|------|
| P1 | 项目必须包含 `scripts/start.sh` 一键启动脚本 | 非技术人员无法手动启动多步骤 | 文件存在 + `tests/test_start_script.py` | ✅ |
| P2 | CORS 必须包含 `https://promiselink.cn` | 缺失 = 前端跨域被拒 | `api_server.py` 配置检查 | ✅ |
| P3 | Nginx 配置必须设置 `server_name promiselink.cn` 并启用 HTTPS | 无 HTTPS = 通信明文 = 中间人攻击 | 部署检查清单 | ✅ |
| P4 | 前端生产配置必须启用 API URL 和正确代理端口 | 缺失 = 前端无法连接后端 | 构建配置检查 | ✅ |
| P5 | `coverage.json` 和 `coverage.xml` 必须加入 `.gitignore` | 生成文件误提交 = 仓库污染 | `.gitignore` 检查 | ✅ |

---

## 3. Ponytail 七层决策模型（参考）

DevSquad Worker 在编码前应执行以下检查，停在第一个能解答的层级：

```
1. 这真的需要构建吗？（YAGNI）
2. 代码库中已存在？复用它。
3. 标准库已提供？用它。
4. 平台原生功能已覆盖？用它。
5. 已安装的依赖能解决？用它。
6. 能用一行实现？就写一行。
7. 最后才写能工作的最小代码。
```

**但以上 7 层不适用于本清单中的硬约束** — 硬约束永不因"简化"而削减。

---

## 4. 根因修复规则（来自 Ponytail）

> "Bug fix = root cause, not symptom. grep 出你改动函数的所有调用者，在共享函数里一次性修。"

**执行要求**：
1. 修复 bug 前，`grep -r "function_name"` 找出所有调用者
2. 如果是共享函数的 bug，在函数内一次性修复（而非每个调用点打补丁）
3. 禁止"改测试适配 bug" — 测试是质量守门员，不是通过率装饰

---

## 5. 与 agentskills.io 标准的对齐

OPC-Agents 的 `SKILL.md`（DevSquad 技能定义）已接近 agentskills.io 开放标准：

| 标准字段 | DevSquad 当前 | 改进方向 |
|----------|---------------|----------|
| `name` | ✅ 有 | — |
| `description` | ✅ 有（含触发关键词） | — |
| `license` | ❌ 缺 | 补充 MIT |
| `compatibility` | ❌ 缺 | 补充 "Requires Python ≥3.10" |
| `metadata` | ❌ 缺 | 补充 author/version |
| `allowed-tools` | ❌ 缺 | 可选，暂不强制 |

---

## 6. 约束变更流程

硬约束不可随意增删。变更需：

1. **提案**: 在 `docs/spec/` 提交约束变更提案，含 rationale
2. **评审**: 七角色共识（至少 architect + security + tester 三票同意）
3. **记录**: 更新本文档 + `project_memory.md` + `PROJECT_STATUS.md` 第 7 节
4. **追溯**: 在 `CHANGELOG.md` 记录变更原因和影响

---

## 7. 参考资料

- [Skill 生态借鉴分析](research/SKILL_ECOSYSTEM_RESEARCH.md) — 完整研究文档
- [Ponytail 深度拆解](https://juejin.cn/post/7654760228148330531)
- [agentskills.io 规范](https://raw.githubusercontent.com/agentskills/agentskills/main/docs/specification.mdx)
- [PROJECT_STATUS.md 第 7 节](PROJECT_STATUS.md) — 硬约束清单（简版）
