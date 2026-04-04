# OPC-Agents 安装指南

**版本**: 3.0.0  
**更新日期**: 2026-04-04  
**适用系统**: macOS / Linux / Windows (WSL)

---

## 📋 目录

- [快速开始（推荐）](#快速开始推荐)
- [一键安装脚本](#一键安装脚本)
- [手动安装步骤](#手动安装步骤)
- [配置说明](#配置说明)
- [常见问题](#常见问题)

---

## 🚀 快速开始（推荐）

### 方法 1：一键安装脚本（最简单）

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/OPC-Agents.git
cd OPC-Agents

# 2. 运行一键安装脚本
chmod +x install.sh
./install.sh

# 3. 配置 API 密钥
vim config.toml

# 4. 启动服务
./OPCstart.sh
```

**访问**: http://localhost:5009

---

## 🔧 一键安装脚本

### macOS / Linux

```bash
#!/bin/bash
# install.sh 已包含在项目中

# 功能:
# ✅ 检查 Python 版本（需要 3.9+）
# ✅ 创建虚拟环境
# ✅ 安装依赖包
# ✅ 创建配置文件
# ✅ 创建数据目录
# ✅ 可选：启动服务
```

**运行**:
```bash
chmod +x install.sh
./install.sh
```

### Windows (PowerShell)

```powershell
# 1. 检查 Python 版本
python --version

# 2. 创建虚拟环境
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. 安装依赖
pip install -r requirements.txt

# 4. 创建配置文件
Copy-Item config.toml.sample config.toml

# 5. 编辑配置
notepad config.toml

# 6. 启动服务
python web_interface\app.py
```

---

## 📝 手动安装步骤

### 步骤 1：检查系统要求

**Python 版本**: 3.9 或更高

```bash
python3 --version
```

**系统依赖**:
- ✅ git（用于克隆仓库和安装技能）
- ✅ pip3（Python 包管理器）

### 步骤 2：克隆仓库

```bash
git clone https://github.com/your-org/OPC-Agents.git
cd OPC-Agents
```

### 步骤 3：创建虚拟环境（推荐）

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
.\venv\Scripts\activate
```

### 步骤 4：安装依赖

**方法 1：使用 requirements.txt（如果有）**
```bash
pip install -r requirements.txt
```

**方法 2：手动安装核心依赖**
```bash
pip3 install requests toml flask ddgs
```

**方法 3：使用国内镜像加速**
```bash
pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 步骤 5：创建配置文件

```bash
cp config.toml.sample config.toml
```

### 步骤 6：编辑配置文件

```bash
vim config.toml
```

**必填配置**（至少配置一个）:

#### 选项 1：智谱 AI GLM（推荐，国内可用）

```toml
[models.glm]
api_key = "your_glm_api_key"  # ← 替换为你的密钥
base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
model = "glm-4.7"
```

**获取 GLM API Key**:
1. 访问 https://open.bigmodel.cn/
2. 注册/登录账号
3. 进入控制台 → API 密钥管理
4. 创建 API 密钥
5. 复制密钥到配置文件

#### 选项 2：OpenAI（国际用户）

```toml
[models.openai]
api_key = "your_openai_api_key"  # ← 替换为你的密钥
base_url = "https://api.openai.com/v1/chat/completions"
model = "gpt-4o"
```

**获取 OpenAI API Key**:
1. 访问 https://platform.openai.com/
2. 注册/登录账号
3. 进入 API Keys 页面
4. 创建新的 API 密钥
5. 复制密钥到配置文件

#### 选项 3：其他模型（可选）

系统支持多种模型，配置方式类似：
- Anthropic (Claude)
- Google (Gemini)
- Azure OpenAI
- 本地模型（Ollama 等）

### 步骤 7：创建数据目录

```bash
mkdir -p data/skills/installed
mkdir -p data/skills/cache
mkdir -p data/logs
mkdir -p data/config
```

### 步骤 8：启动服务

**方法 1：使用启动脚本（推荐）**
```bash
chmod +x OPCstart.sh
./OPCstart.sh
```

**方法 2：直接运行**
```bash
python3 web_interface/app.py
```

**方法 3：调试模式**
```bash
python3 web_interface/app.py --debug
```

### 步骤 9：访问系统

打开浏览器访问：**http://localhost:5009**

---

## ⚙️ 配置说明

### 核心配置

#### 1. AI 模型配置（必填）

**至少配置一个模型**，推荐配置 GLM（国内可用）：

```toml
[models]
default = "glm"  # 默认使用的模型

[models.glm]
api_key = "your_glm_api_key"
base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
model = "glm-4.7"

# 备用模型（可选）
[models.openai]
api_key = "your_openai_api_key"
model = "gpt-4o"
```

#### 2. MCP GitHub 集成（可选，推荐）

用于搜索和安装外部技能：

```toml
[mcp_github]
enabled = true
max_results = 10

# GitHub Token（可选，提升 API 限制）
# 无 Token: 60 次/小时
# 有 Token: 5000 次/小时
github_token = "your_github_token"
```

**获取 GitHub Token**:
1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 选择 scopes：`repo`（私有仓库访问）
4. 生成 token
5. 复制 token 到配置文件

#### 3. 通知配置（可选）

**邮件通知**:
```toml
[email]
enabled = true
smtp_server = "smtp.gmail.com"
smtp_port = 587
smtp_username = "your_email@gmail.com"
smtp_password = "your_app_password"  # 应用专用密码
```

**企业微信**:
```toml
[wechat]
enabled = true
webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
```

**钉钉**:
```toml
[dingtalk]
enabled = true
webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
```

#### 4. 财务配置（可选）

```toml
[finance]
monthly_budget = 100.0  # 月预算（元）
alert_threshold = 80.0  # 达到 80% 时告警
currency = "CNY"
```

#### 5. 服务器配置（可选）

```toml
[server]
host = "0.0.0.0"  # 监听地址
port = 5009       # 端口号
debug = false     # 生产环境设为 false
```

---

## 🔍 常见问题

### Q1: Python 版本过低

**错误**: `Python 3.8 or lower is not supported`

**解决**:
```bash
# macOS (使用 Homebrew)
brew install python@3.9

# Ubuntu/Debian
sudo apt update
sudo apt install python3.9 python3.9-venv

# 使用 pyenv 管理多版本
curl https://pyenv.run | bash
pyenv install 3.9.18
pyenv global 3.9.18
```

### Q2: 依赖安装失败

**错误**: `Could not find a version that satisfies the requirement`

**解决**:
```bash
# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或逐个安装
pip3 install requests toml flask ddgs
```

### Q3: 端口被占用

**错误**: `Address already in use`

**解决**:
```bash
# 检查端口占用
lsof -i :5009

# 杀死占用端口的进程
kill -9 <PID>

# 或修改配置文件中的端口
[server]
port = 5010
```

### Q4: API Key 配置错误

**错误**: `Invalid API key` 或 `Unauthorized`

**解决**:
1. 检查 config.toml 中的 API Key 是否正确
2. 确保没有多余的空格或引号
3. 检查 API Key 是否已过期
4. 确认账户余额充足

### Q5: 无法访问 GitHub

**错误**: `Connection timed out` 或 `Rate limit exceeded`

**解决**:
```toml
# 配置 GitHub Token 提升限制
[mcp_github]
github_token = "your_github_token"

# 或使用代理
export https_proxy=http://proxy-server:port
```

### Q6: 虚拟环境问题

**错误**: `venv module not found`

**解决**:
```bash
# Ubuntu/Debian
sudo apt install python3-venv

# macOS
brew install python

# 不使用虚拟环境（不推荐）
pip3 install -r requirements.txt --user
```

### Q7: 权限问题

**错误**: `Permission denied`

**解决**:
```bash
# 添加执行权限
chmod +x install.sh OPCstart.sh

# 或使用 sudo（谨慎）
sudo ./install.sh
```

---

## 📞 获取帮助

### 文档资源

- [README.md](README.md) - 项目介绍
- [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) - 系统架构
- [CODE_MAP.md](CODE_MAP.md) - 代码地图

### 支持渠道

- 📧 Email: support@example.com
- 💬 Discord: [加入社区](链接)
- 📖 文档：[在线文档](链接)

---

## ✅ 安装验证

安装完成后，运行以下命令验证：

```bash
# 1. 检查 Python 版本
python3 --version
# 输出：Python 3.9.x 或更高

# 2. 检查依赖包
pip3 list | grep -E "requests|toml|flask"
# 应显示已安装的包

# 3. 检查配置文件
cat config.toml | grep api_key
# 应显示已配置的 API Key

# 4. 启动服务
./OPCstart.sh
# 应显示 "启动成功"

# 5. 访问 Web 界面
# 浏览器打开 http://localhost:5009
# 应能看到总裁办对话界面
```

---

## 🎯 下一步

安装完成后，建议：

1. **配置 API Key** - 至少配置一个模型（GLM/OpenAI 等）
2. **测试对话** - 在总裁办页面发送一条消息
3. **创建任务** - 尝试创建一个简单任务
4. **探索功能** - 浏览各个页面了解功能
5. **配置通知** - 根据需要配置邮件/微信通知

---

**安装指南版本**: 3.0.0  
**最后更新**: 2026-04-04  
**维护者**: OPC-Agents 团队
