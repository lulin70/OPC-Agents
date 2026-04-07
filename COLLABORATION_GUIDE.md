# OPC-Agents 协作工作流指南

> 本文档说明 OPC-Agents 项目的 Issue/PR 协作工作流，帮助贡献者高效参与项目开发。

## 📋 目录

- [版本号管理](#版本号管理)
- [Issue 工作流](#issue-工作流)
- [PR 工作流](#pr-工作流)
- [自动化流程](#自动化流程)
- [你需要主动设定的事项](#你需要主动设定的事项)

---

## 版本号管理

### 当前版本

**Version**: 0.0.1 (Initial Release)

### 版本文件

- **位置**: [`VERSION`](VERSION)
- **格式**: Semantic Versioning (MAJOR.MINOR.PATCH)
- **更新时机**: 每次发布新版本时

### 版本号规范

遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)：

- **MAJOR** (主版本号): 破坏性变更
- **MINOR** (次版本号): 向后兼容的功能增加
- **PATCH** (修订号): 向后兼容的问题修复

**示例**：
- `0.0.1` - 初始版本
- `0.1.0` - 第一个功能版本
- `1.0.0` - 正式版本

---

## Issue 工作流

### Issue 类型

项目提供 3 种 Issue 模板：

#### 1. 🐛 Bug 报告

**用途**: 报告软件缺陷或错误

**模板位置**: [`.github/ISSUE_TEMPLATE/bug_report.md`](.github/ISSUE_TEMPLATE/bug_report.md)

**必填内容**：
- Bug 描述
- 复现步骤
- 预期行为
- 环境信息（OS/Python 版本/OPC-Agents 版本）

**标签**: `bug`

#### 2. ✨ 功能请求

**用途**: 提出新功能建议或改进

**模板位置**: [`.github/ISSUE_TEMPLATE/feature_request.md`](.github/ISSUE_TEMPLATE/feature_request.md)

**必填内容**：
- 功能描述
- 动机说明
- 实现建议（可选）
- 验收标准
- 优先级选择

**标签**: `enhancement`

#### 3. 📝 文档改进

**用途**: 提出文档的改进建议

**模板位置**: [`.github/ISSUE_TEMPLATE/docs_improvement.md`](.github/ISSUE_TEMPLATE/docs_improvement.md)

**必填内容**：
- 文档类型
- 改进描述
- 问题位置
- 建议内容

**标签**: `documentation`

### Issue 生命周期

```
新建 (Open) → 标签 (Labeled) → 分配 (Assigned) → 进行中 (In Progress) → 
审查 (In Review) → 已完成 (Closed)
```

### 你需要主动做的事项

✅ **创建 Issue 时**：
1. 选择合适的模板
2. 填写完整信息（特别是复现步骤/验收标准）
3. 添加适当的标签
4. 如果有相关讨论，互相引用

✅ **评论 Issue 时**：
1. 确认问题或表示支持
2. 提供额外的上下文或解决方案
3. 如果是 Bug，确认是否能复现

---

## PR 工作流

### PR 模板

**模板位置**: [`.github/PULL_REQUEST_TEMPLATE/pull_request_template.md`](.github/PULL_REQUEST_TEMPLATE/pull_request_template.md)

### 变更类型

PR 模板提供 10 种变更类型：

| 类型 | Emoji | 说明 |
|------|-------|------|
| `🐛 Bug 修复` | 🐛 | 非破坏性变更，修复问题 |
| `✨ 新功能` | ✨ | 非破坏性变更，增加功能 |
| `⚠️ 破坏性变更` | ⚠️ | 需要更新主要版本号 |
| `📝 文档更新` | 📝 | 文档相关修改 |
| `🧪 测试` | 🧪 | 测试添加或更新 |
| `🔧 配置` | 🔧 | 配置文件变更 |
| `📦 依赖` | 📦 | 依赖更新 |
| `⚡ 性能优化` | ⚡ | 性能提升 |
| `🎨 代码风格` | 🎨 | 不影响功能的风格优化 |
| `♻️ 代码重构` | ♻️ | 代码重构 |
| `🚀 部署` | 🚀 | 部署相关 |

### PR 清单

提交 PR 前必须确认：

- [ ] 代码遵循项目风格（PEP 8）
- [ ] 已进行自测
- [ ] 已添加必要的测试用例
- [ ] 所有现有测试通过
- [ ] 已更新相关文档
- [ ] 提交信息清晰明确
- [ ] 没有引入新的警告或错误
- [ ] 已检查是否有冲突

### 分支命名规范

```
feature/xxx     - 新功能
fix/xxx         - Bug 修复
docs/xxx        - 文档更新
test/xxx        - 测试相关
refactor/xxx    - 代码重构
chore/xxx       - 构建/工具相关
```

### 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**示例**：
```
feat(context_manager): 增加经验库权重计算功能

- 实现 4 维度权重计算公式
- 添加时间衰减机制
- 增加使用频率统计

Closes #123
```

### 你需要主动做的事项

✅ **创建 PR 前**：
1. 确保有对应的 Issue（除非是小的修复）
2. 从 `main` 分支创建新分支
3. 在本地运行所有测试
4. 使用 Black 格式化代码
5. 使用 Flake8 检查代码

✅ **提交 PR 时**：
1. 完整填写 PR 模板
2. 关联对应的 Issue（`Fixes #123`）
3. 选择正确的变更类型
4. 提供测试说明
5. 标注影响范围

✅ **PR 审查中**：
1. 及时回应审查意见
2. 根据反馈修改代码
3. 解决所有冲突
4. 确保 CI 检查通过

---

## 自动化流程

### GitHub Actions Workflows

项目配置了 2 个自动化工作流：

#### 1. Python CI (`python-ci.yml`)

**触发条件**：
- Push 到 `main` 或 `develop` 分支
- Pull Request 到 `main` 或 `develop` 分支

**执行内容**：
- ✅ 多版本 Python 测试（3.9/3.10/3.11）
- ✅ Black 代码格式检查
- ✅ Flake8 代码规范检查
- ✅ Pytest 单元测试
- ✅ 测试覆盖率报告（Codecov）

**配置位置**: [`.github/workflows/python-ci.yml`](.github/workflows/python-ci.yml)

#### 2. Auto Label PR (`auto-label.yml`)

**触发条件**：
- Pull Request 打开/编辑/更新

**执行内容**：
- 🏷️ 根据 PR 标题自动添加标签
  - `feat` → `enhancement`
  - `fix` → `bug`
  - `docs` → `documentation`
  - `test` → `testing`
  - `refactor` → `refactoring`
  - `chore` → `chore`

- 🏷️ 根据修改文件自动添加标签
  - `.md` → `documentation`
  - `test/*.py` → `testing`
  - `*.yml/*.yaml` → `ci/cd`
  - `*.toml/*.txt` → `dependencies`

**配置位置**: [`.github/workflows/auto-label.yml`](.github/workflows/auto-label.yml)

---

## 你需要主动设定的事项

### 🎯 必须主动完成的事项

#### 1. **Git 用户信息配置**

```bash
git config --global user.name "Your Name"
git config --global user.email you@example.com
```

**原因**: 确保提交记录正确关联到你的 GitHub 账户

#### 2. **Fork 项目并克隆**

```bash
# GitHub 上 Fork 项目
git clone https://github.com/YOUR_USERNAME/OPC-Agents.git
cd OPC-Agents
```

#### 3. **配置上游远程仓库**

```bash
git remote add upstream https://github.com/lulin70/OPC-Agents.git
git fetch upstream
```

**原因**: 方便同步原项目的最新变更

#### 4. **安装开发依赖**

```bash
pip install pytest pytest-cov black flake8 mypy
```

#### 5. **本地测试环境**

确保在提交前运行：

```bash
# 运行测试
pytest

# 格式化代码
black opc_manager/ tests/

# 检查代码
flake8 opc_manager/ tests/
```

### ✅ 建议主动完成的事项

#### 1. **关注项目动态**

- Watch 项目，接收通知
- Star 项目，表示支持

#### 2. **参与 Issue 讨论**

- 确认 Bug 是否能复现
- 为功能请求投票
- 提供实现建议

#### 3. **帮助审查 PR**

- 检查代码质量
- 测试功能是否正常
- 提出建设性意见

#### 4. **维护文档**

- 发现文档问题及时报告
- 主动修正文档错误
- 补充缺失的说明

### ⚠️ 注意事项

#### 不要做的事项：

❌ 不要提交未经测试的代码
❌ 不要忽略 CI 检查失败
❌ 不要跳过代码格式化
❌ 不要提交与 Issue 无关的变更
❌ 不要在 PR 描述中留空
❌ 不要忽略审查意见

---

## 快速开始指南

### 第一次贡献

1. **选择一个 Issue**
   - 查看 [Good First Issues](https://github.com/lulin70/OPC-Agents/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
   - 或创建新的 Issue

2. **Fork 项目**
   ```bash
   git clone https://github.com/YOUR_USERNAME/OPC-Agents.git
   cd OPC-Agents
   ```

3. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **开发并测试**
   ```bash
   # 编写代码
   # 运行测试
   pytest
   
   # 格式化
   black opc_manager/
   ```

5. **提交变更**
   ```bash
   git add .
   git commit -m "feat: your feature description"
   ```

6. **推送并创建 PR**
   ```bash
   git push origin feature/your-feature-name
   # GitHub 上创建 PR
   ```

---

## 常见问题

### Q: 我的 PR 多久会被审查？

A: 通常在 48 小时内。如果超过这个时间，请在 Issue 中 @ 维护者。

### Q: 如何知道我的代码是否符合规范？

A: 运行 `black --check` 和 `flake8`，确保没有错误或警告。

### Q: 测试失败怎么办？

A: 查看失败原因，修复问题后重新提交。确保所有测试通过再推送。

### Q: 可以同时处理多个 Issue 吗？

A: 建议一次专注于一个 Issue，完成后再处理下一个。

### Q: 如何更新我的 PR？

A: 在本地分支修改后，重新 commit 并 push，PR 会自动更新。

---

## 联系方式

- **GitHub Issues**: [提交 Issue](https://github.com/lulin70/OPC-Agents/issues)
- **项目主页**: https://github.com/lulin70/OPC-Agents

---

**感谢你的贡献！** 🎉

让我们一起打造更好的 OPC-Agents！
