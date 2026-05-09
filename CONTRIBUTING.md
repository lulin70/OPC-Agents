# 贡献指南

感谢你为 OPC-Agents 项目做出贡献！本文档将指导你如何参与项目的开发。

## 📋 目录

- [行为准则](#行为准则)
- [开发环境设置](#开发环境设置)
- [开发流程](#开发流程)
- [代码风格](#代码风格)
- [提交规范](#提交规范)
- [测试要求](#测试要求)
- [文档要求](#文档要求)

---

## 行为准则

本项目采用 Contributor Covenant 行为准则。我们期望所有贡献者都能保持专业和尊重的态度。

## 开发环境设置

### 1. Fork 项目

在 GitHub 上 Fork 本项目到你的账户。

### 2. 克隆项目

```bash
git clone https://github.com/YOUR_USERNAME/OPC-Agents.git
cd OPC-Agents
```

### 3. 创建虚拟环境

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
.\venv\Scripts\activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 安装开发依赖（如果有）

```bash
pip install pytest pytest-cov black flake8 mypy
```

## 开发流程

### 1. 创建 Issue

在开始开发之前，请先创建一个 Issue 描述你要解决的问题或提出的新功能。

- 🐛 [Bug 报告模板](.github/ISSUE_TEMPLATE/bug_report.md)
- ✨ [功能请求模板](.github/ISSUE_TEMPLATE/feature_request.md)
- 📝 [文档改进模板](.github/ISSUE_TEMPLATE/docs_improvement.md)

### 2. 创建分支

从 `main` 分支创建你的功能分支：

```bash
git checkout -b feature/your-feature-name
# 或者修复 bug
git checkout -b fix/bug-fix-name
```

**分支命名规范：**

- `feature/xxx` - 新功能
- `fix/xxx` - Bug 修复
- `docs/xxx` - 文档更新
- `test/xxx` - 测试相关
- `refactor/xxx` - 代码重构
- `chore/xxx` - 构建/工具相关

### 3. 进行开发

按照代码风格要求编写代码，并确保：

- 代码有适当的注释
- 遵循项目的架构设计
- 不破坏现有功能

### 4. 运行测试

```bash
# 运行所有测试
PYTHONPATH=. pytest tests/ -v

# 运行特定测试
PYTHONPATH=. pytest tests/your_test.py -v

# 查看测试覆盖率
PYTHONPATH=. pytest --cov=opc_manager --cov-report=html
```

### 5. 提交变更

```bash
git add .
git commit -m "type: description"
```

### 6. 推送到远程

```bash
git push origin feature/your-feature-name
```

### 7. 创建 Pull Request

在 GitHub 上创建 Pull Request，并填写 [PR 模板](.github/PULL_REQUEST_TEMPLATE/pull_request_template.md)。

## 代码风格

### Python 代码规范

- 遵循 [PEP 8](https://pep8.org/) 规范
- 使用 4 个空格缩进
- 最大行宽 100 字符
- 使用有意义的变量名和函数名

### 代码格式化

我们使用 Black 进行代码格式化：

```bash
# 安装 Black
pip install black

# 格式化代码
black opc_manager/
black tests/

# 检查格式
black --check opc_manager/
```

### 代码检查

使用 Flake8 进行代码检查：

```bash
# 安装 Flake8
pip install flake8

# 运行检查
flake8 opc_manager/
flake8 tests/
```

### 类型检查（可选）

使用 MyPy 进行类型检查：

```bash
# 安装 MyPy
pip install mypy

# 运行类型检查
mypy opc_manager/
```

## 提交规范

我们遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

### 提交格式

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### 提交类型

- `feat` - 新功能
- `fix` - Bug 修复
- `docs` - 文档更新
- `style` - 代码风格（不影响代码功能）
- `refactor` - 代码重构
- `test` - 测试相关
- `chore` - 构建/工具相关

### 提交示例

```
feat(context_manager): 增加经验库权重计算功能

- 实现 4 维度权重计算公式
- 添加时间衰减机制
- 增加使用频率统计

Closes #123
```

```
fix(task_executor): 修复任务上下文传递错误

修复了后续 Agent 无法获取前序 Agent 产出物内容的问题。

Fixes #456
```

## 测试要求

### 单元测试

- 每个新功能都应该有对应的单元测试
- 测试覆盖率应该保持在 80% 以上
- 测试应该独立且可重复

### 测试命名

```python
def test_<function>_<scenario>_<expected_result>():
    # 示例
    def test_calculate_weight_high_confidence_returns_high_weight():
        pass
```

### 集成测试

对于涉及多个模块的功能，应该编写集成测试。

## 文档要求

### 代码注释

- 公共函数和类必须有文档字符串
- 复杂逻辑必须有注释说明
- 使用中文注释（与项目保持一致）

### 文档更新

如果你的 PR 包含以下变更，请更新相应文档：

- 新功能 → 更新 README 和相关文档
- API 变更 → 更新 API 文档
- 配置变更 → 更新配置说明
- 架构变更 → 更新架构文档

### 文档格式

- 使用 Markdown 格式
- 遵循现有文档的结构和风格
- 添加适当的代码示例

## Pull Request 流程

1. **填写 PR 模板**：完整填写 [PR 模板](.github/PULL_REQUEST_TEMPLATE/pull_request_template.md)
2. **代码审查**：项目维护者会审查代码
3. **持续集成**：确保所有 CI 检查通过
4. **解决反馈**：根据审查反馈进行修改
5. **合并**：审查通过后合并到 main 分支

## 发布流程

### 版本号规范

我们遵循 [Semantic Versioning](https://semver.org/)：

- **MAJOR.MINOR.PATCH** (例如：0.0.1)
- MAJOR - 破坏性变更
- MINOR - 向后兼容的功能增加
- PATCH - 向后兼容的问题修复

### 发布清单

发布新版本前，请确保：

- [ ] 更新 [VERSION](VERSION) 文件
- [ ] 更新 README 中的版本号
- [ ] 更新 [docs/CHANGELOG.md](docs/CHANGELOG.md)
- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] 代码已格式化
- [ ] 创建 Git Tag

## 常见问题

### Q: 我如何开始贡献？

A: 从简单的 Issue 开始，例如文档改进或小的 bug 修复。熟悉项目后再处理更复杂的任务。

### Q: 我的 PR 多久会被审查？

A: 我们会尽力在 48 小时内审查 PR。如果超过这个时间，请在 Issue 中 @ 维护者。

### Q: 我可以添加新功能吗？

A: 当然！请先创建 Issue 讨论你的想法，确认后再开始开发。

### Q: 如何运行测试？

A: 运行 `PYTHONPATH=. pytest tests/ -v` 即可运行所有测试。详细信息请参考 [测试要求](#测试要求)。

## 联系方式

- **GitHub Issues**: [提交 Issue](https://github.com/lulin70/OPC-Agents/issues)
- **Email**: [项目维护者邮箱]

## 贡献者名单

感谢所有为 OPC-Agents 做出贡献的开发者！

🎉 **再次感谢你的贡献！**
