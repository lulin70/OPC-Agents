# OPC-Agents 安装配置总结

**日期**: 2026-04-04  
**状态**: ✅ 完整的用户安装方案已就绪

---

## 📊 现有安装方案

### ✅ 一键安装脚本

**文件**: [`install.sh`](file:///Users/lin/Documents/trae_projects/OPC-Agents/install.sh)

**功能**:
- ✅ 检查 Python 版本（需要 3.9+）
- ✅ 创建虚拟环境
- ✅ 安装依赖包（使用清华镜像加速）
- ✅ 创建配置文件（从 config.toml.sample 复制）
- ✅ 创建数据目录
- ✅ 可选：启动服务

**使用**:
```bash
chmod +x install.sh
./install.sh
```

---

### ✅ 启动脚本

**文件**: [`OPCstart.sh`](file:///Users/lin/Documents/trae_projects/OPC-Agents/OPCstart.sh)

**功能**:
- ✅ 清理旧进程
- ✅ 启动 Web 服务（端口 5009）
- ✅ 支持调试模式（--debug 参数）

**使用**:
```bash
./OPCstart.sh
# 或
./OPCstart.sh --debug
```

---

### ✅ 配置模板

**文件**: [`config.toml.sample`](file:///Users/lin/Documents/trae_projects/OPC-Agents/config.toml.sample)

**关键配置**:

#### 必填（至少一个）

**智谱 AI GLM**（推荐）:
```toml
[models.glm]
api_key = "your_glm_api_key"  # ← 用户需要填写
model = "glm-4.7"
```

**OpenAI**（国际用户）:
```toml
[models.openai]
api_key = "your_openai_api_key"
model = "gpt-4o"
```

#### 可选

**MCP GitHub 集成**:
```toml
[mcp_github]
enabled = true
github_token = "your_github_token"  # 提升 API 限制
```

**通知配置**:
```toml
[email]
enabled = true
smtp_username = "your_email@example.com"

[wechat]
enabled = true
webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
```

---

## 📚 文档资源

### ✅ 快速安装说明（面向客户）

**文件**: [`INSTALL.md`](file:///Users/lin/Documents/trae_projects/OPC-Agents/INSTALL.md)

**特点**:
- 📋 3 步快速开始
- 🎯 重点突出必填配置
- 💡 详细的 API Key 获取指南
- ❓ 常见问题解答
- ⏱️ 预计安装时间：3-5 分钟

**内容**:
- 一键安装步骤
- 配置说明（必填 + 可选）
- 手动安装备选方案
- 常见问题
- 获取帮助

---

### ✅ 完整安装指南

**文件**: [`docs/user_guides/INSTALLATION_GUIDE.md`](file:///Users/lin/Documents/trae_projects/OPC-Agents/docs/user_guides/INSTALLATION_GUIDE.md)

**特点**:
- 📖 详细的安装步骤
- 🔧 多种安装方法
- ⚙️ 完整配置说明
- 🎓 系统要求说明
- 🔍 安装验证

**内容**:
- 快速开始
- 一键安装脚本
- 手动安装步骤
- 配置说明（详细）
- 常见问题
- 获取帮助

---

### ✅ README 更新

**文件**: [`README.md`](file:///Users/lin/Documents/trae_projects/OPC-Agents/README.md)

**更新内容**:
- ✅ 一键安装（推荐）
- ✅ 手动安装（备选）
- ✅ API Key 配置指南
- ✅ 链接到详细文档

---

## 🎯 用户安装流程

### 推荐流程（3 步）

```
1. 运行安装脚本
   ./install.sh
   
2. 配置 API Key
   vim config.toml
   # 填写 GLM API Key
   
3. 启动服务
   ./OPCstart.sh
   
访问：http://localhost:5009
```

**预计时间**: 3-5 分钟

---

## 📋 关键信息配置指南

### 1. LLM 模型和 API Key

**推荐**: 智谱 AI GLM（国内可用，免费额度充足）

**获取步骤**:
1. 访问 https://open.bigmodel.cn/
2. 注册账号（手机号/邮箱）
3. 进入"控制台" → "API 密钥管理"
4. 点击"创建 API 密钥"
5. 复制密钥（`sk.` 开头）

**配置**:
```toml
[models.glm]
api_key = "sk.xxxxxxxxxxxxxxxxxxxxxxxx"  # ← 粘贴密钥
model = "glm-4.7"
```

**备选**: OpenAI、Anthropic、Google、Azure、本地模型

---

### 2. MCP GitHub 账户信息（可选）

**作用**: 搜索和安装外部技能，提升 API 限制

**获取 GitHub Token**:
1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 选择 scopes：勾选 `repo`
4. 生成 token
5. 复制 token（`ghp_` 开头）

**配置**:
```toml
[mcp_github]
enabled = true
github_token = "ghp_xxxxxxxxxxxxxxxxxxxx"  # ← 粘贴 Token
```

**效果**:
- 无 Token: 60 次/小时
- 有 Token: 5000 次/小时

---

### 3. 通知配置（可选）

**邮件通知**:
```toml
[email]
enabled = true
smtp_server = "smtp.gmail.com"
smtp_port = 587
smtp_username = "your_email@gmail.com"
smtp_password = "your_app_password"  # 应用专用密码
```

**获取应用专用密码**（Gmail）:
1. 访问 Google 账户设置
2. 安全性 → 两步验证
3. 应用专用密码
4. 生成密码
5. 复制密码

**企业微信**:
1. 创建企业微信应用
2. 获取 Webhook URL
3. 配置到文件

**钉钉**:
1. 创建钉钉机器人
2. 获取 access_token
3. 配置到文件

---

## ✅ 安装验证清单

```bash
# 1. Python 版本
python3 --version
# ✅ 应显示：Python 3.9.x 或更高

# 2. 依赖包
pip3 list | grep -E "requests|toml|flask"
# ✅ 应显示：requests, toml, flask

# 3. 配置文件
cat config.toml | grep api_key
# ✅ 应显示：已配置的 API Key

# 4. 启动服务
./OPCstart.sh
# ✅ 应显示：启动成功

# 5. 访问 Web 界面
# 浏览器打开：http://localhost:5009
# ✅ 应能看到对话界面
```

---

## 🎁 额外功能

### 数据目录结构

安装脚本自动创建：
```
data/
├── skills/
│   ├── installed/  # 已安装的技能
│   └── cache/      # 技能缓存
├── logs/           # 日志文件
└── config/         # 配置文件备份
```

### 虚拟环境

安装脚本自动创建 Python 虚拟环境：
```
venv/  # 独立的 Python 环境
```

**激活虚拟环境**:
```bash
source venv/bin/activate
```

---

## 📞 用户支持

### 文档资源

- 📖 [INSTALL.md](INSTALL.md) - 快速安装说明
- 📚 [INSTALLATION_GUIDE.md](docs/user_guides/INSTALLATION_GUIDE.md) - 完整安装指南
- 📄 [README.md](README.md) - 项目介绍
- 🏗️ [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) - 系统架构

### 常见问题

- ❓ Python 版本过低 → 安装 Python 3.9+
- ❓ 依赖安装失败 → 使用国内镜像
- ❓ 端口被占用 → 修改配置文件端口
- ❓ API Key 错误 → 检查密钥是否正确

### 获取帮助

- 📧 Email: support@example.com
- 💬 GitHub Issues: [提交问题](链接)
- 📖 在线文档：[查看文档](链接)

---

## 🎯 总结

### ✅ 已具备的安装方案

1. ✅ **一键安装脚本** - `install.sh`
2. ✅ **启动脚本** - `OPCstart.sh`
3. ✅ **配置模板** - `config.toml.sample`
4. ✅ **快速安装说明** - `INSTALL.md`
5. ✅ **完整安装指南** - `docs/user_guides/INSTALLATION_GUIDE.md`
6. ✅ **README 更新** - 清晰的安装步骤

### 🎯 用户安装体验

**简单**: 3 步完成安装  
**快速**: 3-5 分钟完成  
**友好**: 详细的配置指南  
**可靠**: 自动检查和错误处理  

### 📋 用户需要配置的关键信息

**必填**（至少一个）:
- ✅ LLM API Key（GLM/OpenAI 等）

**可选**:
- ✅ GitHub Token（提升 API 限制）
- ✅ 邮件服务器信息（邮件通知）
- ✅ 企业微信/钉钉 Webhook（即时通知）

---

**状态**: ✅ 完整的用户安装方案已就绪  
**更新日期**: 2026-04-04  
**版本**: 3.0.0
