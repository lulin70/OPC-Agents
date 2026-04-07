# Git 版本控制策略

## 📋 原则

作为产品，Git 仓库应该包含**可复用的产品代码和核心文档**，不包含**用户数据、过程性文件和敏感信息**。

---

## ✅ 应该放入 Git 的内容

### 1. 核心代码
- ✅ 所有 Python 源代码（`.py`）
- ✅ 前端代码（HTML、CSS、JS）
- ✅ 测试代码（`tests/`）
- ✅ 配置文件模板（`*.sample`）

### 2. 核心文档
- ✅ README.md / README-EN.md（产品说明）
- ✅ 架构文档（`docs/architecture/`）
- ✅ 部署指南（`docs/deployment_guide.md`）
- ✅ 用户手册（`docs/系统用户手册.md`）
- ✅ API 文档（`docs/API 文档.md`）
- ✅ 变更日志（`docs/CHANGELOG.md`）

### 3. 配置和依赖
- ✅ `requirements.txt`（依赖清单）
- ✅ `config.toml.sample`（配置模板）
- ✅ `.github/`（GitHub Actions、Issue 模板）
- ✅ `LICENSE`（开源协议）

### 4. 工作流定义
- ✅ 场景引擎配置（`opc_manager/scenario_engine.py`）
- ✅ 人格化配置（`config/president_office_persona.py`）
- ✅ 标签系统配置（`config/task_tags.py`）

### 5. 数据库迁移
- ✅ SQL 迁移脚本（`migrations/`）

---

## ❌ 不应该放入 Git 的内容

### 1. 用户数据
- ❌ 数据库文件（`*.db`, `*.db-shm`, `*.db-wal`）
- ❌ 用户上传的文件
- ❌ 任务执行产生的数据（`task_workspaces/`）
- ❌ 会话历史数据

### 2. 敏感信息
- ❌ API 密钥
- ❌ 密码
- ❌ 实际配置文件（`config.toml`，应该使用 `config.toml.sample`）
- ❌ `.env` 文件

### 3. 过程性文档
- ❌ 日报（`docs/phase1_dayX_report.md`）
- ❌ 临时会议记录
- ❌ 过程性决策文档（`docs/*_plan.md`）
- ❌ 微信集成过程文档（`docs/wechat_*.md`）

### 4. 构建产物
- ❌ `__pycache__/`
- ❌ `*.pyc`
- ❌ `reports/`（测试报告）
- ❌ `test_results.xml`

### 5. 环境相关
- ❌ 虚拟环境（`venv/`, `env/`）
- ❌ IDE 配置（`.vscode/`, `.idea/`）
- ❌ 本地日志（`logs/`, `*.log`）

---

## 📝 .gitignore 更新说明

已更新 `.gitignore` 文件，包含以下规则：

```gitignore
# 数据库文件
*.db
*.db-shm
*.db-wal
*.sqlite
*.sqlite3

# 过程文档
docs/phase1_*.md
docs/phase2_*.md
docs/wechat_*.md
docs/*_report.md
docs/*_plan.md
docs/*_summary.md

# 测试报告
reports/
test_results.xml

# 缓存和临时文件
__pycache__/
*.pyc
*.cache

# 环境配置
.env
config.toml
venv/
```

---

## 🧹 建议清理的文件列表

以下文件已经在 Git 中，但建议移除：

### 过程性文档（21 个文件）
```
docs/phase1_day5_report.md
docs/phase1_day6_report.md
docs/phase1_day7_report.md
docs/phase1_implementation_plan.md
docs/phase1_summary_report.md
docs/phase2_decision_report.md
docs/phase2_implementation_plan.md
docs/phase2_launch_report.md
docs/phase2_task_tracker.md
docs/phase2_wechat_decision.md
docs/wechat_implementation_complete.md
docs/wechat_integration_adjustment.md
docs/wechat_integration_feasibility.md
docs/wechat_integration_final.md
docs/wechat_integration_lightweight.md
docs/wechat_integration_pairing.md
docs/wechat_integration_progress.md
docs/documentation_update_summary.md
docs/progress_report_*.md
```

### 测试报告（3 个文件）
```
reports/test_report_summary.md
reports/test_results.xml
tests/integration/test_results.txt
```

### 数据库文件（3 个文件）
```
data_storage/opc_agents.db
data_storage/opc_agents.db-shm
data_storage/opc_agents.db-wal
```

---

## 🔧 清理步骤

要清理已提交的文件，执行以下命令：

```bash
# 1. 从 Git 历史中移除文件（但保留本地文件）
git rm --cached docs/phase1_*.md
git rm --cached docs/phase2_*.md
git rm --cached docs/wechat_*.md
git rm --cached docs/*_report.md
git rm --cached docs/*_plan.md
git rm --cached docs/*_summary.md
git rm --cached reports/
git rm --cached test_results.xml
git rm --cached data_storage/*.db*

# 2. 提交更改
git commit -m "chore: 清理过程性文件和用户数据，符合产品化规范"

# 3. 推送到远程
git push origin main
```

---

## 📊 对比表

| 文件类型 | 示例 | 是否提交 | 原因 |
|---------|------|---------|------|
| 源代码 | `*.py`, `*.js`, `*.html` | ✅ 是 | 产品核心 |
| 配置模板 | `config.toml.sample` | ✅ 是 | 帮助用户部署 |
| 实际配置 | `config.toml` | ❌ 否 | 包含敏感信息 |
| 数据库结构 | `migrations/*.sql` | ✅ 是 | 版本控制 |
| 数据库文件 | `*.db` | ❌ 否 | 用户数据 |
| README | `README.md` | ✅ 是 | 产品文档 |
| 日报 | `phase1_day1_report.md` | ❌ 否 | 过程文档 |
| 测试代码 | `tests/*.py` | ✅ 是 | 质量保证 |
| 测试报告 | `test_results.xml` | ❌ 否 | 构建产物 |
| 依赖清单 | `requirements.txt` | ✅ 是 | 部署必需 |
| 虚拟环境 | `venv/` | ❌ 否 | 本地环境 |

---

## 🎯 最佳实践

1. **配置管理**：提交 `.sample` 模板，实际配置通过环境变量或本地文件
2. **数据库**：只提交迁移脚本，数据文件本地生成
3. **文档**：只提交最终产品文档，过程文档本地保留
4. **敏感信息**：使用 `.env` 文件，绝不提交
5. **定期清理**：每个版本发布前清理过程性文件

---

## 📚 参考

- [Git 最佳实践](https://github.com/git-guides)
- [GitHub 开源项目规范](https://opensource.guide/)
- [十二要素应用](https://12factor.net/zh_cn/)
