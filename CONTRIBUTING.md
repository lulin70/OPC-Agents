# 贡献指南

感谢你对 OPC-Agents 项目的关注！本指南将帮助你了解如何参与项目贡献。

## 项目愿景

OPC-Agents 致力于为一人公司（One Person Company）提供企业级的 AI 代理协作能力。我们相信，通过开源社区的共同努力，可以让更多个人和小团队获得原本只有大型企业才能拥有的智能代理系统。

## 如何贡献

### 1. 报告问题

如果你发现了 bug 或有功能建议，请通过 GitHub Issues 提交：

- 使用清晰的标题描述问题
- 提供复现步骤（如果是 bug）
- 说明你的使用场景和期望行为
- 标注相关标签：`bug`、`feature`、`documentation`、`question`

### 2. 提交代码

#### 准备工作

1. **Fork 仓库**到你的 GitHub 账号
2. **克隆你的 Fork**：
   ```bash
   git clone https://github.com/YOUR_USERNAME/OPC-Agents.git
   cd OPC-Agents
   ```
3. **添加上游仓库**：
   ```bash
   git remote add upstream https://github.com/original-owner/OPC-Agents.git
   ```
4. **创建分支**：
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/issue-description
   ```

#### 开发规范

- **Python 代码风格**：遵循 PEP 8
- **文档字符串**：为函数和类添加 docstring
- **类型提示**：鼓励使用类型注解
- **注释**：复杂逻辑需要注释说明

#### 提交前检查

```bash
# 运行测试
python -m pytest tests/

# 检查代码风格
flake8 *.py

# 确保没有语法错误
python -m py_compile *.py
```

#### 提交信息规范

使用清晰的提交信息格式：

```
类型: 简短描述（50字以内）

详细说明（可选，72字换行）

关联 Issue: #123
```

类型包括：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式调整（不影响功能）
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建/工具相关

### 3. Pull Request 流程

1. **推送分支**：
   ```bash
   git push origin feature/your-feature-name
   ```

2. **创建 PR**：
   - 标题清晰描述变更内容
   - 填写 PR 模板中的各项信息
   - 关联相关 Issue

3. **代码审查**：
   - 维护者会在 48 小时内进行初步审查
   - 根据反馈进行修改
   - 确保 CI 检查通过

4. **合并**：
   - 通过审查后，维护者会合并你的 PR
   - 感谢你的贡献！

## 开发环境搭建

### 基本要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
# 或
pip install requests toml flask
```

### 配置文件

```bash
cp config.toml.sample config.toml
# 编辑 config.toml，填入你的 API 密钥
```

### 启动开发服务器

```bash
# 方式一：使用启动脚本
chmod +x OPCstart.sh
./OPCstart.sh

# 方式二：手动启动
python web_interface.py
```

访问 `http://localhost:5007` 查看 Web 界面。

## 贡献领域

我们特别欢迎以下方面的贡献：

### 高优先级

- **A2A 协议完善**：增强与其他 Agent 系统的互操作性
- **性能优化**：降低 Token 消耗，提高响应速度
- **测试覆盖**：为核心模块添加单元测试和集成测试
- **文档完善**：API 文档、使用教程、最佳实践

### 中等优先级

- **新代理类型**：针对特定行业的专业代理
- **Web 界面改进**：UI/UX 优化、移动端适配
- **更多模型支持**：集成新的 LLM 提供商
- **HR 功能增强**：更完善的代理生命周期管理

### 探索性

- **多语言支持**：国际化和本地化
- **插件系统**：允许第三方扩展
- **可视化工具**：代理协作流程可视化
- **数据分析**：代理性能和使用模式分析

## 代码结构

```
OPC-Agents/
├── opc_manager.py          # 核心管理器
├── communication_manager.py # 通信管理
├── web_interface.py        # Web 界面
├── auto_optimizer.py       # 自动优化
├── a2a_protocol.py         # A2A 协议实现
├── a2a_integration.py      # A2A 集成
├── hr_enhancement.py       # HR 生命周期
├── opc_skill.py            # 技能
└── official_agents/        # 官方代理定义
```

## 社区规范

### 行为准则

- 保持尊重和建设性的沟通
- 欢迎新手，耐心解答问题
- 接受不同的观点和技术选择
- 专注于技术讨论，避免无关话题

### 决策流程

- 日常维护由核心维护者决定
- 重大变更通过 GitHub Discussions 讨论
- 社区反馈是决策的重要参考

## 许可证说明

通过向本项目提交贡献，你同意你的贡献将在 Apache License 2.0 下发布。详见 [LICENSE](./LICENSE) 文件。

## 联系方式

- **GitHub Issues**: 技术问题和功能建议
- **GitHub Discussions**: 一般性讨论和想法分享
- **Email**: [待添加]

## 致谢

感谢所有为 OPC-Agents 做出贡献的开发者！

---

**新手友好标签**：如果你是第一次参与开源项目，可以查找带有 `good first issue` 标签的 Issue，这些任务相对简单，适合入门。
