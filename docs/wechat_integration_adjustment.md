# 微信集成方案调整报告（ClawBot 插件版）

**日期**: 2026-04-14  
**主题**: 基于 OpenClaw 微信插件的集成方案

---

## 一、原方案 vs 新方案对比

### 1.1 原方案（iLink API）❌

**技术架构**:
```
用户微信 → 微信服务器 → iLink API → OPC-Agents
```

**特点**:
- 需要注册微信开放平台
- 需要创建 ClawBot 应用
- 使用 HTTP/JSON API 通信
- OPC-Agents 作为独立服务

**问题**:
- ❌ 这不是真正的 ClawBot 插件
- ❌ 这是企业微信的方案
- ❌ 与用户提供的截图不符

### 1.2 新方案（OpenClaw 插件）✅

**技术架构**:
```
用户微信 → OpenClaw 微信插件 → OpenClaw 核心 → OPC-Agents（AI 后端）
```

**特点**:
- ✅ 使用官方 ClawBot 插件
- ✅ 通过命令行安装：`npx -y @tencent-weixin/openclaw-weixin-cli@latest install`
- ✅ 通过二维码绑定
- ✅ OPC-Agents 作为 OpenClaw 的 AI 后端服务

---

## 二、新方案技术实现

### 2.1 核心架构

```
┌──────────────┐
│  用户微信    │
│  (手机版)    │
└──────┬───────┘
       │ 微信消息
       ▼
┌──────────────┐
│ OpenClaw 微信 │
│   插件       │
│ (本地运行)   │
└──────┬───────┘
       │ 本地 API
       ▼
┌──────────────┐
│ OpenClaw 核心 │
│   服务       │
└──────┬───────┘
       │ HTTP/RPC
       ▼
┌──────────────────────────────┐
│  OPC-Agents AI 后端服务      │
│  - 消息处理接口              │
│  - 对话管理接口              │
│  - 任务管理接口              │
└──────────────────────────────┘
```

### 2.2 安装步骤

#### Step 1: 安装 OpenClaw
```bash
# 安装 OpenClaw 核心
npm install -g @tencent-weixin/openclaw
```

#### Step 2: 安装微信插件
```bash
# 安装 ClawBot 微信插件
npx -y @tencent-weixin/openclaw-weixin-cli@latest install
```

#### Step 3: 配置 OPC-Agents 后端
```json
// ~/.openclaw/openclaw.json
{
  "ai_backend": {
    "enabled": true,
    "endpoint": "http://localhost:5009/api/wechat/ai",
    "api_key": "your_api_key"
  }
}
```

#### Step 4: 扫码绑定
1. 打开微信 → 我 → 设置
2. 关于微信 → 确认版本是 8.0.70+
3. 返回设置 → 插件 → 微信 ClawBot
4. 扫描二维码完成绑定

---

## 三、OPC-Agents 适配开发

### 3.1 需要开发的接口

#### 1. OpenClaw 适配层

**文件**: `opc_manager/openclaw_adapter.py`

```python
from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

# OpenClaw 适配路由
openclaw_bp = Blueprint('openclaw', __name__, url_prefix='/api/openclaw')

@openclaw_bp.route('/ai', methods=['POST'])
def handle_ai_request():
    """
    OpenClaw AI 后端接口
    
    接收 OpenClaw 转发的微信消息，返回 AI 响应
    """
    data = request.json
    
    # 解析 OpenClaw 消息格式
    message_type = data.get('type')  # 'text', 'image', 'file'
    content = data.get('content')
    user_id = data.get('user_id')
    
    logger.info(f"Received from OpenClaw: type={message_type}, user={user_id}")
    
    # 调用 OPC-Agents 处理
    if message_type == 'text':
        response = await process_text_message(user_id, content)
    elif message_type == 'image':
        response = await process_image_message(user_id, content)
    elif message_type == 'file':
        response = await process_file_message(user_id, content)
    else:
        response = {'type': 'text', 'content': '暂不支持此消息类型'}
    
    return jsonify(response)


async def process_text_message(user_id: str, content: str) -> dict:
    """处理文本消息"""
    # 1. 获取或创建对话
    conversation = conv_manager.get_or_create_conversation(
        user_id=user_id,
        channel='wechat'
    )
    
    # 2. 添加用户消息
    conv_manager.add_message(
        conversation_id=conversation.id,
        role='user',
        message_type='text',
        content=content
    )
    
    # 3. 调用总裁办处理
    response = await executive_office.process_message(content)
    
    # 4. 添加系统回复
    conv_manager.add_message(
        conversation_id=conversation.id,
        role='assistant',
        message_type='text',
        content=response['content']
    )
    
    # 5. 返回 OpenClaw 格式响应
    return {
        'type': 'text',
        'content': response['content']
    }


async def process_image_message(user_id: str, image_url: str) -> dict:
    """处理图片消息"""
    # 下载图片
    image_data = await download_image(image_url)
    
    # 调用视觉模型分析
    analysis = await vision_model.analyze(image_data)
    
    # 生成回复
    response_text = f"我已看到这张图片：{analysis.description}"
    
    return {
        'type': 'text',
        'content': response_text
    }


async def process_file_message(user_id: str, file_url: str) -> dict:
    """处理文件消息"""
    # 下载文件
    file_data = await download_file(file_url)
    
    # 解析文件内容
    if file_url.endswith('.txt'):
        content = file_data.decode('utf-8')
    elif file_url.endswith('.doc') or file_url.endswith('.docx'):
        content = await parse_docx(file_data)
    else:
        return {
            'type': 'text',
            'content': '暂不支持此文件格式'
        }
    
    # 总结文件内容
    summary = await summarize_text(content)
    
    return {
        'type': 'text',
        'content': f"文件摘要：{summary}"
    }
```

### 3.2 配置管理

**文件**: `config/openclaw_config.toml`

```toml
[openclaw]
enabled = true
endpoint = "http://localhost:5009/api/openclaw/ai"
api_key = "your_secret_key"
timeout = 30

[openclaw.features]
text = true
image = true
file = true
voice = false  # 暂不支持

[openclaw.models]
text_model = "qwen-2.5-72b"
vision_model = "qwen-vl-max"
```

### 3.3 消息格式转换

#### OpenClaw 消息格式
```json
{
  "type": "text",
  "content": "查询任务进度",
  "user_id": "wechat_user_123",
  "timestamp": 1713072000,
  "message_id": "msg_xxx"
}
```

#### OPC-Agents 响应格式
```json
{
  "type": "text",
  "content": "您的任务已完成 80%",
  "metadata": {
    "task_id": "task_123",
    "progress": 80
  }
}
```

---

## 四、开发工作量

### 4.1 后端开发

| 模块 | 工作量 | 说明 |
|------|--------|------|
| OpenClaw 适配器 | 1 天 | 消息格式转换、路由 |
| 消息处理 | 1 天 | 文本/图片/文件处理 |
| 配置管理 | 0.5 天 | 配置文件、API Key 管理 |
| 测试调试 | 0.5 天 | 与 OpenClaw 联调 |
| **总计** | **3 天** | - |

### 4.2 前端开发

| 模块 | 工作量 | 说明 |
|------|--------|------|
| 无 | 0 天 | OpenClaw 已提供完整 UI |
| **总计** | **0 天** | - |

### 4.3 总工作量

**3 天**（比原方案减少 1.5 天）

---

## 五、优势分析

### 5.1 与原方案对比

| 维度 | 原方案（iLink API） | 新方案（OpenClaw 插件） |
|------|-------------------|------------------------|
| **开发成本** | 4.5 天 | 3 天 ⬇️ |
| **用户门槛** | 需注册开放平台 | 只需安装插件 ✅ |
| **合规性** | ✅ 官方 API | ✅ 官方插件 |
| **功能丰富度** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **生态成熟度** | ⭐⭐⭐（新） | ⭐⭐⭐⭐（快速发展） |
| **维护成本** | 中 | 低 ✅ |
| **用户体验** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

### 5.2 核心优势

1. ✅ **开发更简单**: 无需处理复杂的 API 认证、Token 管理
2. ✅ **用户门槛更低**: 只需安装插件，无需注册开放平台
3. ✅ **功能更强大**: OpenClaw 已实现图片 OCR、文件解析等功能
4. ✅ **维护成本低**: OpenClaw 团队维护插件，我们只需关注 AI 后端
5. ✅ **快速上线**: 3 天即可完成开发

---

## 六、实施步骤

### Phase 2.4: 微信集成（OpenClaw 插件版）- 3 天

#### Day 1: OpenClaw 适配器开发
- [ ] 创建 `openclaw_adapter.py`
- [ ] 实现消息接收接口
- [ ] 实现消息格式转换
- [ ] 配置管理

#### Day 2: 消息处理集成
- [ ] 文本消息处理
- [ ] 图片消息处理
- [ ] 文件消息处理
- [ ] 与总裁办集成

#### Day 3: 测试与部署
- [ ] 安装 OpenClaw 和插件
- [ ] 配置 OPC-Agents 后端
- [ ] 联调测试
- [ ] 文档完善

---

## 七、用户操作指南

### 7.1 安装 OpenClaw

```bash
# 1. 安装 OpenClaw 核心
npm install -g @tencent-weixin/openclaw

# 2. 验证安装
openclaw --version
```

### 7.2 安装微信插件

```bash
# 安装 ClawBot 微信插件
npx -y @tencent-weixin/openclaw-weixin-cli@latest install
```

### 7.3 配置 OPC-Agents

1. 编辑 `~/.openclaw/openclaw.json`:
```json
{
  "ai_backend": {
    "enabled": true,
    "endpoint": "http://localhost:5009/api/openclaw/ai",
    "api_key": "your_secret_key"
  }
}
```

2. 重启 OpenClaw:
```bash
openclaw restart
```

### 7.4 绑定微信

1. 打开微信 → 我 → 设置
2. 关于微信 → 确认版本是 8.0.70+
3. 返回设置 → 插件 → 微信 ClawBot
4. 扫描二维码完成绑定

### 7.5 开始使用

在微信中搜索"OpenClaw"或"ClawBot"，发送消息即可与 OPC-Agents 交互。

---

## 八、技术验证

### 8.1 环境要求

- ✅ 微信版本：8.0.70+（iOS/Android）
- ✅ Node.js: 16+
- ✅ OpenClaw: 最新版
- ✅ OPC-Agents: 支持 OpenClaw 适配层

### 8.2 测试用例

#### 测试 1: 文本消息
```
用户：查询任务进度
预期：返回任务进度信息
```

#### 测试 2: 图片消息
```
用户：[发送图片]
预期：分析图片内容并回复
```

#### 测试 3: 文件消息
```
用户：[发送 .txt 文件]
预期：总结文件内容
```

---

## 九、风险与应对

### 9.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| OpenClaw 不稳定 | 低 | 中 | 关注官方更新，及时反馈 |
| 消息格式变更 | 低 | 中 | 适配层设计灵活，易扩展 |
| 功能限制 | 低 | 低 | 逐步实现，优先核心功能 |

### 9.2 应对措施

1. **关注官方动态**: 订阅 OpenClaw GitHub 仓库
2. **灵活适配**: 适配层设计考虑扩展性
3. **分阶段实施**: 先实现文本，再逐步增强

---

## 十、结论与建议

### 10.1 结论

✅ **新方案（OpenClaw 插件）完全可行**，且优于原方案

### 10.2 建议

1. **立即采用新方案**: OpenClaw 插件版
2. **快速实施**: 3 天完成开发
3. **持续优化**: 根据用户反馈增强功能

### 10.3 下一步

1. ✅ 确认采用 OpenClaw 插件方案
2. ⏳ 安装 OpenClaw 和插件
3. ⏳ 开发 OpenClaw 适配层
4. ⏳ 联调测试

---

**报告人**: AI 助理  
**日期**: 2026-04-14  
**版本**: 2.0（基于 OpenClaw 插件）  
**状态**: 🔄 等待确认
