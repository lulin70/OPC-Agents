# Beta 快速启动指南

> **OPC-Agents v0.1.0-beta** — 告诉它你要什么，它直接做完交付文件

---

## 📋 前提条件

- Python 3.9+
- 至少一个 LLM API Key（推荐 MOKA）

## 🚀 安装（5分钟）

```bash
# 1. 克隆仓库
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents

# 2. 运行安装脚本
chmod +x install.sh && ./install.sh
```

安装脚本会自动：
- 创建 Python 虚拟环境
- 安装所有依赖
- 从 `.env.example` 创建 `.env` 配置文件

## 🔑 配置 API Key

编辑 `.env` 文件，填入你的 API Key：

```bash
# 必填 — 至少配置一个
MOKA_API_KEY=sk-your-moka-key-here       # 推荐，Claude Sonnet 4

# 可选 — 其他 LLM 提供商
GLM_API_KEY=your-glm-key-here            # 智谱 GLM-4
OPENAI_API_KEY=sk-your-openai-key-here   # OpenAI GPT-4o
```

**LLM 优先级**：MOKA > GLM > OpenAI > Ollama（本地）

> 💡 **获取 MOKA API Key**：访问 [moka-ai.com](https://moka-ai.com)，注册后即可获取

## 🏃 启动

```bash
chmod +x start.sh && ./start.sh
```

浏览器会自动打开 `http://localhost:8501`

> 💡 刷新页面会丢失对话历史，请留意页面提示

## 🎯 试用场景

在聊天框中输入以下示例，快速体验核心功能：

### 内容创作
```
帮我写一篇关于一人公司趋势的深度分析报告
```

### 市场调研
```
帮我调研2026年AI工具赛道的竞品格局
```

### 营销方案
```
帮我制定一个独立开发者的Q2营销方案
```

### 商业计划
```
帮我写一份AI咨询服务的商业计划书
```

### 产品分析
```
帮我分析Notion和Obsidian的差异化定位
```

### 数字产品
```
帮我设计一个AI写作助手的MVP方案
```

## 📂 交付文件

任务完成后，交付文件保存在 `deliverables/` 目录下，同时在页面左侧「交付文件库」中可预览和下载。

## ⚠️ 已知限制（Beta）

| 限制 | 说明 |
|------|------|
| 对话不持久 | 刷新页面会丢失历史，后续版本会支持持久化 |
| 设置面板 | 部分设置项标记为「即将支持」，暂不可用 |
| 并发任务 | 最多同时执行3个任务 |
| 搜索依赖 | 网络搜索需要稳定的网络环境 |

## 🐛 反馈与问题

- **Bug 报告**：[GitHub Issues](https://github.com/lulin70/OPC-Agents/issues)
- **功能建议**：[GitHub Discussions](https://github.com/lulin70/OPC-Agents/discussions)
- **紧急问题**：创建 Issue 并标记 `P0-critical`

## 🔧 故障排除

| 问题 | 解决方案 |
|------|----------|
| `ModuleNotFoundError` | 确认在项目根目录运行 `source venv/bin/activate` |
| `MOKA_API_KEY not found` | 检查 `.env` 文件是否在项目根目录，且已填入 API Key |
| 端口 8501 被占用 | `lsof -ti:8501 | xargs kill` 后重新启动 |
| 任务一直转圈 | 检查 API Key 是否有效，网络是否通畅 |
| 中文乱码 | 确认终端编码为 UTF-8 |

---

**感谢参与 Beta 测试！你的反馈直接影响产品方向。** 🚀
