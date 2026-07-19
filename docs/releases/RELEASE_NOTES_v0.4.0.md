# Release Notes — OPC-Agents v0.4.0

> **发布日期**: 2026-07-18
> **版本**: v0.4.0 (Beta)
> **上一版本**: v0.3.36 (2026-07-18)
> **SemVer 类型**: MINOR — 测试质量里程碑 + 架构改进 + 安全告警清零
> **许可证**: MIT
> **仓库**: [lulin70/OPC-Agents](https://github.com/lulin70/OPC-Agents)

---

## 一、发布摘要

v0.4.0 是 OPC-Agents Beta 阶段的首个 MINOR 版本，标志着项目从"功能扩展期"进入"质量巩固期"。本版本完成 4 项关键里程碑：T7 Mock 反模式系列正式关闭、bandit B608 安全告警清零、tool_system.py Facade 拆分完成、大文件 SRP 评估完成。D05 E2E 真实用户模拟测试 199/200 通过（99.5%），发布门控通过。

| 维度 | v0.3.36 | v0.4.0 | 变化 |
|------|---------|--------|------|
| 测试用例总数 | 4241 | 4241 | 持平（无新功能，质量巩固） |
| 全量测试通过 | 4164 passed + 77 skipped | 4164 passed + 77 skipped | ✅ 持平 |
| E2E 测试通过 | 183/184 + 1 skip | 199/200 + 0 skip | +16 用例（新增 e2e 子集） |
| mypy 错误 | 0 | 0 | ✅ 持平 |
| flake8 违规 | 0 | 0 | ✅ 持平 |
| radon cc D+ 函数 | 0 | 0 | ✅ 持平 |
| bandit B608 告警 | 5 处误报 | 0 | ✅ 清零（nosec 注释） |
| Mock 反模式 | T7 进行中 | T7 关闭 | ✅ 42 处替换完成 |
| 全量覆盖率 | 83% | 83% | 持平 |

---

## 二、新增功能

### 2.1 工程规范文档

- **Mock 分类判定标准**（[docs/spec/MOCK_CLASSIFICATION_GUIDE.md](../spec/MOCK_CLASSIFICATION_GUIDE.md)）
  - 7 类 Mock 分类（streamlit/@patch.object/@patch.dict/外部服务/assert_called/局部MagicMock/PropertyMock）
  - 反模式 vs 必要 Mock 对照表
  - 新增测试 Mock 自检清单（7 项）
  - T7 系列关闭总结 + 监控机制

### 2.2 SRP 评估文档化

- **3 个大文件 SRP 评估结论**（[docs/PROJECT_STATUS.md](../PROJECT_STATUS.md) § 6 Phase 3）
  - `data_manager.py` (790 行) — 非 God Class，单一职责"数据管理层"
  - `task_engine_v3_executors.py` (788 行) — 非 God Class，Mixin 拆分产物
  - `task_orchestrator.py` (774 行) — 非 God Class，任务编排职责内聚
  - 基于 project_memory 教训"SRP 而非行数阈值"（52 候选 1.9% 命中率）

---

## 三、改进

### 3.1 安全 — bandit B608 误报清零

5 处 bandit B608（SQL 注入）误报添加 `# nosec B608` 注释，告警清零：

| 文件 | 行号 | 安全模式说明 |
|------|------|------------|
| `opc_manager/crm_skill.py` | 158 | 列名来自 `_CRM_WHERE_COLUMNS` 白名单，值参数化 |
| `opc_manager/knowledge_skill.py` | 129 | 列名来自 `_KNOWLEDGE_UPDATEABLE_COLUMNS` 白名单，值参数化 |
| `opc_manager/knowledge_skill.py` | 183 | `where_clause` 使用固定模板 + `?` 占位符 |
| `opc_manager/task_skill.py` | 141 | 列名来自 `_TASK_WHERE_COLUMNS` 白名单，值参数化 |
| `opc_manager/user_profile.py` | 202 | 列名来自 `allowed` 白名单，值参数化 |

验证：`bandit -ll -ii opc_manager/` → No issues identified + EXIT_CODE=0 ✅

### 3.2 架构 — tool_system.py Facade 拆分确认

`tool_system.py` 已完成 Facade 模式拆分（v0.3.x 系列累计完成，v0.4.0 文档化确认）：

| 模块 | 行数 | 覆盖率 | 职责 |
|------|------|--------|------|
| `tool_system.py` | 222 | — | Facade（`class ToolSystem(ToolRegistry, FileSystemHandlers, SmtpHandlers, CommandHandlers)`） |
| `tool_registry.py` | 130 | 99% | 工具注册中心 |
| `tool_handlers_fs.py` | 91 | 100% | 文件系统处理器 |
| `tool_handlers_smtp.py` | 70 | 100% | SMTP 邮件处理器 |
| `tool_handlers_cmd.py` | 33 | 85% | 命令执行处理器 |
| `tool_audit_logger.py` | 119 | 84% | 审计日志器 |

### 3.3 测试质量 — T7 Mock 反模式系列正式关闭

T7 系列（v0.3.33 → v0.3.36）累计完成 5 文件 42 处 Mock 替换：

| 版本 | 阶段 | 文件数 | 替换数 |
|------|------|--------|--------|
| v0.3.33 | T7 计划制定 | 0 | 0 |
| v0.3.34 | T7 第 1 批推迟 | 0 | 0 |
| v0.3.35 | T7 第 1 批实施 | 4 | 36 |
| v0.3.36 | T7 第 2 批实施 + 关闭 | 1 | 6 |
| **合计** | — | **5** | **42** |

**校准说明**: 原估计 ~311 处替换，实际 42 处（-86%）。剩余 56 文件 532 处经评估为必要 Mock（测试隔离/分支控制/外部服务/assert_called 断言依赖）。

---

## 四、修复

无新增 bug 修复（v0.3.36 已完成 SQLite 锁根治 + mypy 15→0 + email/finance 覆盖率 100%）。

---

## 五、E2E 验证（D05 v0.4.0 重跑）

### 5.1 测试结果

| 测试类别 | 通过/总数 | 耗时 | 备注 |
|---------|----------|------|------|
| 用户旅程（test_e2e_user_journeys.py） | 24/24 | 1.95s | mocked LLM + 单例重置 |
| Playwright 真实浏览器（test_ui_playwright.py） | 21/21 | 186s | 真实 Streamlit + Chromium headless |
| Docker 部署（test_docker_deployment.py） | 37/37 | — | Docker 容器构建+运行 |
| 真实搜索（test_e2e_real.py） | 24/25 | — | 1 失败：环境问题（Ollama 未启动） |
| 其他 E2E | 93/93 | — | integration/start_script/ui_e2e_apptest |
| **总计** | **199/200** | **407.98s** | **99.5% 通过率** |

### 5.2 已知失败（环境问题，非代码回归）

- **测试**: `test_e2e_real.py::TestRealFullPipeline::test_chinese_content_generation_real`
- **失败原因**: Ollama 未启动（`localhost:11434` Connection refused）+ 搜索超时（15s timeout）
- **断言**: `assertGreater(len(result.content), 200)` 实际 137
- **根因**: 真实 LLM 调用失败导致内容生成质量不达标
- **修复方案**: 启动 Ollama 服务后重跑（非代码问题）

---

## 六、质量门禁

| 门禁 | 状态 | 命令 |
|------|------|------|
| pytest 全量 | ✅ 4164 passed + 77 skipped + 0 failed | `pytest --ignore=tests/e2e --cov=opc_manager -q` |
| E2E 全量 | ✅ 199/200 通过（1 环境失败） | `pytest tests/e2e/ -q --timeout=300` |
| mypy | ✅ 0 issues | `MYPYPATH=src mypy -p opc_manager` |
| flake8 | ✅ 0 violations | `flake8 opc_manager/ tests/` |
| ruff | ✅ All checks passed | `ruff check .` |
| radon cc | ✅ 无 D+ 函数 | `radon cc -s -n D opc_manager/` |
| bandit | ✅ No issues identified | `bandit -ll -ii opc_manager/` |
| 版本一致性 | ✅ test_version.py 9 passed | `pytest tests/unit/test_version.py` |

---

## 七、版本同步清单

以下 8 处版本号已从 `0.3.36` 同步到 `0.4.0`：

- [x] `VERSION`
- [x] `opc_manager/version.py`
- [x] `opc_manager/mcp_protocol.py`（如有引用）
- [x] `pyproject.toml`
- [x] `Dockerfile`（ARG VERSION）
- [x] `README.md` / `README-EN.md` / `README-JP.md`
- [x] `CHANGELOG.md`（新增 [0.4.0] 段）
- [x] `docs/PROJECT_STATUS.md`

---

## 八、升级须知

### 8.1 兼容性

- **Python**: ≥ 3.10（无变化）
- **依赖**: 无新增依赖
- **数据库 schema**: 无变化（`_db_version = 7` 保持）
- **API**: 无 breaking change

### 8.2 升级步骤

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 安装依赖（无变化，可跳过）
pip install -r requirements.txt

# 3. 验证版本
python -c "from opc_manager.version import __version__; print(__version__)"
# 应输出: 0.4.0

# 4. 运行全量测试（可选）
pytest --ignore=tests/e2e -q
```

---

## 九、下个版本计划（v0.4.1 / v0.5.0）

### v0.4.1（PATCH，规划中）

- 待定（根据用户反馈）

### v0.5.0（MINOR，架构演进）

- `data_manager.py` 可选拆分为 `encryption.py` + `migrations.py` + `data_manager.py` 3 个子模块
- `task_orchestrator.py` 可选提取 `ConsensusChecker` 类
- 大文件 SRP 评估结果记入 ROADMAP

---

## 十、致谢

感谢所有参与 v0.4.0 开发和测试的成员（DevSquad 7-role 协作）。

---

**下载**: [GitHub Release](https://github.com/lulin70/OPC-Agents/releases/tag/v0.4.0)
**文档**: [README.md](../../README.md) | [CHANGELOG.md](../../CHANGELOG.md) | [PROJECT_STATUS.md](../PROJECT_STATUS.md)
**反馈**: [Issues](https://github.com/lulin70/OPC-Agents/issues)
