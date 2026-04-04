# OPC-Agents 快速安装说明

**3 分钟快速开始** | **一键安装** | **简单配置**

---

## 🚀 快速开始（3 步完成）

### 步骤 1：下载并安装

```bash
# 克隆项目
git clone https://github.com/your-org/OPC-Agents.git
cd OPC-Agents

# 运行一键安装脚本
chmod +x install.sh
./install.sh
```

**安装过程**:
- ✅ 自动检查 Python 版本
- ✅ 自动创建虚拟环境
- ✅ 自动安装依赖
- ✅ 自动创建配置文件

---

### 步骤 2：配置 API 密钥（必填）

打开配置文件：
```bash
vim config.toml
```

**只需配置一行**（智谱 AI GLM，推荐）：
```toml
[models.glm]
api_key = "sk.xxxxxxxxxxxxxxxxxxxxxxxx"  # ← 替换为你的 API Key
model = "glm-4.7"
```

**如何获取 GLM API Key**:
1. 访问：https://open.bigmodel.cn/
2. 注册账号（支持手机号/邮箱）
3. 进入"控制台" → "API 密钥管理"
4. 点击"创建 API 密钥"
5. 复制密钥（`sk.`开头）到配置文件

**保存退出**:
```bash
:wq  # 在 vim 中按 Esc，然后输入 :wq 回车
```

---

### 步骤 3：启动服务

```bash
./OPCstart.sh
```

**访问系统**:
打开浏览器，访问：**http://localhost:5009**

**完成！** 🎉

---

## 📋 关键配置说明

### 必填配置（至少一个）

#### 智谱 AI GLM（推荐，国内可用）

```toml
[models.glm]
api_key = "sk.xxxxxxxxxxxxxxxxxxxxxxxx"  # ← 必填
model = "glm-4.7"
```

**价格**: 免费额度充足，个人使用足够

---

### 可选配置

#### 1. MCP GitHub 集成（推荐）

用于搜索和安装外部技能：

```toml
[mcp_github]
enabled = true
github_token = "ghp_xxxxxxxxxxxxxxxxxxxx"  # ← 可选，提升 API 限制
```

**如何获取 GitHub Token**:
1. 访问：https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 选择 scopes：勾选 `repo`
4. 生成 token
5. 复制 token（`ghp_`开头）到配置文件

**作用**: 将 API 限制从 60 次/小时提升到 5000 次/小时

---

#### 2. 通知配置（可选）

**邮件通知**:
```toml
[email]
enabled = true
smtp_username = "your_email@gmail.com"
smtp_password = "your_app_password"
```

**企业微信**:
```toml
[wechat]
enabled = true
webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
```

---

## 🔧 手动安装（备选）

如果一键安装脚本无法运行，可以手动安装：

### macOS / Linux

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip3 install requests toml flask ddgs

# 3. 创建配置文件
cp config.toml.sample config.toml

# 4. 编辑配置
vim config.toml

# 5. 启动服务
python3 web_interface/app.py
```

### Windows (PowerShell)

```powershell
# 1. 创建虚拟环境
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install requests toml flask ddgs

# 3. 创建配置文件
Copy-Item config.toml.sample config.toml

# 4. 编辑配置
notepad config.toml

# 5. 启动服务
python web_interface\app.py
```

---

## ❓ 常见问题

### Q: 安装脚本报错 "Permission denied"

**解决**:
```bash
chmod +x install.sh
./install.sh
```

---

### Q: Python 版本过低

**要求**: Python 3.9 或更高

**检查版本**:
```bash
python3 --version
```

**升级**:
- macOS: `brew install python@3.9`
- Ubuntu: `sudo apt install python3.9 python3.9-venv`
- Windows: 从 https://www.python.org/downloads/ 下载

---

### Q: 依赖安装失败

**使用国内镜像加速**:
```bash
pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

### Q: 端口被占用

**错误**: `Address already in use`

**解决**:
```bash
# 杀死占用端口的进程
lsof -ti:5009 | xargs kill -9

# 或修改配置文件中的端口
[server]
port = 5010
```

---

### Q: API Key 配置错误

**检查**:
1. API Key 是否正确复制（包含 `sk.` 前缀）
2. 是否有空格或引号
3. 账户余额是否充足

**测试**:
```bash
# 访问智谱 AI 控制台
https://open.bigmodel.cn/
```

---

## 📞 获取帮助

### 文档

- [完整安装指南](docs/user_guides/INSTALLATION_GUIDE.md)
- [README](README.md) - 项目介绍
- [使用指南](docs/user_guides/) - 详细教程

### 支持

- 📧 Email: support@example.com
- 💬 问题反馈：[GitHub Issues](链接)

---

## ✅ 验证安装

```bash
# 1. 检查 Python 版本
python3 --version
# 应显示：Python 3.9.x 或更高

# 2. 启动服务
./OPCstart.sh
# 应显示：启动成功

# 3. 访问 Web 界面
# 浏览器打开：http://localhost:5009
# 应能看到对话界面
```

---

## 🎯 下一步

1. ✅ **配置 API Key** - 编辑 `config.toml`
2. ✅ **启动服务** - `./OPCstart.sh`
3. ✅ **测试对话** - 发送一条消息给总裁办
4. ✅ **创建任务** - 尝试创建一个简单任务

**开始使用吧！** 🚀

---

**版本**: 3.0.0  
**最后更新**: 2026-04-04  
**预计安装时间**: 3-5 分钟
