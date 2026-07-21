# OPC-Agents CI 与 Dependabot 配置更新

> **创建日期**: 2026-07-20
> **版本**: v0.5.1+ (CI 配置更新，非产品版本)
> **状态**: 已实施
> **触发事件**: 2026-07-20 关闭 5 个 dependabot PR 后的 7-Role 评估

## 1. 背景与动机

### 1.1 触发事件
2026-07-20 一次性关闭了 5 个 dependabot PR（#15/#17/#18/#19/#20），均为 dev 依赖的 patch/minor 更新。这些 PR 的 CI 全部 FAILURE，根因是 PR 基于旧代码（v0.5.0 遗留 mypy 25 errors）。

### 1.2 7-Role 评估发现的问题

| 优先级 | 问题 | 影响 |
|--------|------|------|
| P0 | black 版本严重不一致：CI pin `==24.8.0` vs requirements-dev.txt `>=26.3.1`（major 跨版本） | CI 可能 fail（black 26.x 格式与 24.x 不同） |
| P0 | ruff 版本不一致：CI pin `==0.15.21` vs requirements-dev.txt `>=0.15.22` | 本地/CI 行为漂移 |
| P1 | dependabot.yml 无 groups：每个依赖一个 PR | PR 噪音大，CI 重复跑 5 次 |
| P1 | dependabot.yml 无 ignore 规则：dev 依赖 patch/minor 也触发 PR | 刚才 5 个 PR 都是 dev 依赖 patch |
| P1 | dependabot.yml 无 security 配置：安全更新只在 weekly monday 检查 | 安全漏洞修复延迟最多 7 天 |
| P2 | CI 里重新 pin ruff/mypy/black，与 requirements-dev.txt 不一致 | 双重事实来源，容易漂移 |
| P2 | 无 concurrency 控制：同 PR 多次 push 排队跑多次 CI | 浪费 CI 资源 |

### 1.3 目标
- 根除双重事实来源（CI pin vs requirements-dev.txt）
- 减少 PR 噪音（dependabot 分组 + 忽略 dev 依赖 patch/minor）
- 安全更新每天检查（不延迟到 weekly）
- CI 资源优化（concurrency 取消旧运行）

## 2. 改动清单

### 2.1 `.github/dependabot.yml`
- **pip 生态**：添加 `groups`（dev-dependencies 分组）+ `ignore`（dev 依赖 patch/minor）+ `open-pull-requests-limit: 3`（从 5 降）
- **新增 pip 安全更新**：`schedule.interval: daily`，专门处理 security advisories
- **docker 生态**：保留 weekly，open-limit 降为 2
- **github-actions 生态**：保留 monthly

### 2.2 `.github/workflows/python-ci.yml`
- **移除 ruff/mypy/black 硬 pin**：直接用 requirements-dev.txt 安装的版本
- **添加 concurrency 控制**：同 PR 多次 push 取消旧运行
- **保留 mypy pin 在 requirements-dev.txt**：mypy 版本敏感，在 requirements-dev.txt 中 pin `mypy>=1.11.2,<1.12` 范围

### 2.3 `requirements-dev.txt`
- **mypy 添加上限 pin**：`mypy>=1.8.0` → `mypy>=1.11.2,<1.12`（避免 mypy 新版本引入新检查导致 CI fail）

## 3. Dependabot 新配置说明

### 3.1 分组策略（groups）
```yaml
groups:
  python-dev-dependencies:
    patterns:
      - "ruff"
      - "black"
      - "mypy"
      - "flake8"
      - "bandit"
      - "pip-audit"
      - "radon"
      - "types-*"
      - "pytest*"
      - "responses"
      - "httpx"
      - "psutil"
      - "playwright"
  python-production-dependencies:
    exclude-patterns:
      - "ruff"
      - "black"
      - "mypy"
      - "flake8"
      - "bandit"
      - "pip-audit"
      - "radon"
      - "types-*"
      - "pytest*"
      - "responses"
      - "httpx"
      - "psutil"
      - "playwright"
```

### 3.2 忽略策略（ignore）
```yaml
ignore:
  # dev 依赖的 patch/minor 更新忽略（major 仍会通知）
  - dependency-name: "ruff"
    update-types: ["version-update:semver-patch", "version-update:semver-minor"]
  - dependency-name: "black"
    update-types: ["version-update:semver-patch", "version-update:semver-minor"]
  - dependency-name: "mypy"
    update-types: ["version-update:semver-patch", "version-update:semver-minor"]
  - dependency-name: "flake8"
    update-types: ["version-update:semver-patch", "version-update:semver-minor"]
  - dependency-name: "bandit"
    update-types: ["version-update:semver-patch", "version-update:semver-minor"]
  - dependency-name: "pip-audit"
    update-types: ["version-update:semver-patch", "version-update:semver-minor"]
  - dependency-name: "radon"
    update-types: ["version-update:semver-patch", "version-update:semver-minor"]
  - dependency-name: "types-*"
    update-types: ["version-update:semver-patch", "version-update:semver-minor"]
  - dependency-name: "responses"
    update-types: ["version-update:semver-patch", "version-update:semver-minor"]
```

### 3.3 安全更新
```yaml
# 新增：pip 安全更新（每天检查 GHSA）
- package-ecosystem: "pip"
  directory: "/"
  schedule:
    interval: "daily"
  open-pull-requests-limit: 10
  allow:
    - dependency-type: "all"
  labels:
    - "security"
    - "dependencies"
    - "automated"
  reviewers:
    - "lulin70"
```

## 4. CI 新配置说明

### 4.1 移除硬 pin（使用 requirements-dev.txt 版本）
**改动前**：
```yaml
- name: Lint with ruff (blocking)
  run: |
    pip install ruff==0.15.21
    ruff check opc_manager/ frontend/ tests/ --exit-non-zero-on-fix

- name: Type check with mypy (blocking)
  run: |
    pip install mypy==1.11.2
    mypy opc_manager/ --ignore-missing-imports --follow-imports=silent

- name: Check formatting with Black
  run: |
    pip install black==24.8.0
    black --check --target-version py310 opc_manager/ frontend/ tests/
```

**改动后**：
```yaml
- name: Lint with ruff (blocking)
  # 使用 requirements-dev.txt 已安装的版本，避免双重事实来源
  run: ruff check opc_manager/ frontend/ tests/ --exit-non-zero-on-fix

- name: Type check with mypy (blocking)
  # 使用 requirements-dev.txt 已安装的版本（mypy>=1.11.2,<1.12）
  run: mypy opc_manager/ --ignore-missing-imports --follow-imports=silent

- name: Check formatting with Black
  # 使用 requirements-dev.txt 已安装的版本（black>=26.3.1）
  run: black --check --target-version py310 opc_manager/ frontend/ tests/
```

### 4.2 Concurrency 控制
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

效果：同 PR/同分支多次 push 时，自动取消旧的 CI 运行，只保留最新一次。

## 5. 验证方法

### 5.1 本地验证（push 前）
```bash
cd /Users/lin/trae_projects/OPC-Agents
pip install -r requirements-dev.txt --quiet
ruff check opc_manager/ frontend/ tests/ --exit-non-zero-on-fix
mypy opc_manager/ --ignore-missing-imports --follow-imports=silent
black --check --target-version py310 opc_manager/ frontend/ tests/
```

### 5.2 CI 验证（push 后）
- 观察下一次 CI 运行是否通过
- 观察下次 dependabot 是否生成更少的 PR（理论上应该只有 major 更新才生成）

## 6. 风险与回滚

### 6.1 风险
- **风险 1**：移除 CI 硬 pin 后，requirements-dev.txt 的 `>=` 约束可能安装新版本引入新检查
  - 缓解：mypy 添加上限 `<1.12`；ruff/black 的 minor 更新通常向后兼容
- **风险 2**：concurrency cancel-in-progress 可能取消正在跑的必要 CI
  - 缓解：只在同 ref 内取消，不同 PR/分支互不影响

### 6.2 回滚
如果 CI 失败：
1. revert 本次 commit
2. 恢复 CI 硬 pin
3. 调整 requirements-dev.txt 版本约束

## 7. Bandit 安全扫描修复（c91b292 后续修复）

### 7.1 问题
c91b292 push 后 CI 失败在 "Security scan with Bandit" 步骤。9 个 B608 (hardcoded_sql_expressions) 误报：
- 全部位于 `opc_manager/metrics_collector.py`
- 行号：527, 756, 773, 1085, 1110, 1131, 1155, 1180, 1217

### 7.2 根因分析
- B608 检测 f-string SQL 拼接，但这些位置的 `{table}` / `{score_col}` / `{where}` 都是内部常量（非用户输入）
- 参数值（start_date, end_date 等）全部使用 `?` 参数化查询
- 这是 B608 的典型误报（SQL 不支持表名作为参数，只能拼接）

### 7.3 修复
为 9 个位置添加 `# nosec B608 — <reason>` 标注，与 crm_skill.py:158 / knowledge_skill.py:129 等已有标注风格一致。

### 7.4 验证
```
bandit -r opc_manager/ -ii -ll
Test results:
    No issues identified.
exit code: 0
```

### 7.5 历史背景
v0.5.1 (cede546) 的 CI 失败在 "Check formatting with Black"（版本不一致），Bandit 步骤未执行。
c91b292 修复了 Black 版本统一问题，但暴露了之前被掩盖的 Bandit 遗留问题。
本次修复彻底解决了 Bandit 失败。

## 8. 参考文档
- [GitHub Dependabot 官方文档](https://docs.github.com/en/code-security/dependabot)
- [GitHub Actions concurrency 文档](https://docs.github.com/en/actions/using-jobs/using-concurrency)
- OPC-Agents project_memory: "pre-commit hooks版本陈旧是CI漂移的根本原因"
