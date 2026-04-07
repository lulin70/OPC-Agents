# Phase 2 微信集成方案决策报告

**日期**: 2026-04-14  
**主题**: 确定微信集成技术方案

---

## 一、决策背景

用户需求：
1. **Phase 2 推进**: 用户在自己电脑前的场景（Web 界面）- ✅ 已批准
2. **微信集成**: 客户在外想了解最新动向的场景（移动端）

用户特别提到："微信新推出的插件可以支持 claw"

---

## 二、方案对比

### 2.1 候选方案

| 方案 | 用户端 | 合规性 | 开发成本 | 推荐度 |
|------|--------|--------|----------|--------|
| **ClawBot 插件** | 个人微信 | ✅ 官方 iLink 协议 | 4.5 天 | ⭐⭐⭐⭐⭐ |
| 企业微信 | 企业微信 App | ✅ 官方 API | 3 天 | ⭐⭐⭐⭐ |
| 微信公众号 | 个人微信 | ✅ 官方 API | 4 天 | ⭐⭐ |
| 微信小程序 | 个人微信 | ✅ 官方 API | 26 天 | ⭐⭐ |

### 2.2 核心对比维度

#### 用户体验
- **ClawBot**: ⭐⭐⭐⭐⭐ - 使用日常微信，无需安装额外 App
- **企业微信**: ⭐⭐⭐ - 需安装企业微信 App
- **微信公众号**: ⭐⭐⭐⭐ - 需关注公众号
- **微信小程序**: ⭐⭐⭐⭐⭐ - 原生体验

#### 开发可行性
- **ClawBot**: ⭐⭐⭐⭐ - iLink 协议简单，但生态较新
- **企业微信**: ⭐⭐⭐⭐⭐ - 生态成熟，文档完善
- **微信公众号**: ⭐⭐⭐ - 需企业资质
- **微信小程序**: ⭐⭐ - 开发成本高

#### 合规性
- **ClawBot**: ✅ 官方支持，无封号风险
- **企业微信**: ✅ 官方支持，无封号风险
- **微信公众号**: ✅ 官方支持
- **微信小程序**: ✅ 官方支持

---

## 三、决策结果

### 3.1 推荐方案：ClawBot 插件

**理由**:
1. ✅ **最符合用户需求**: "客户在外想了解最新动向"，个人微信最自然
2. ✅ **用户体验最佳**: 无需安装企业微信，使用日常微信即可
3. ✅ **合规安全**: 官方 iLink 协议（2026-03-22 新发布），无封号风险
4. ✅ **功能强大**: 支持文本、图片、语音、视频、位置等多种消息
5. ✅ **开发可行**: 4.5 天工作量，可接受

### 3.2 备选方案：企业微信

**触发条件**:
- ⚠️ ClawBot 插件资质审核不通过
- ⚠️ 免费额度不足
- ⚠️ 文档不完善导致开发困难

**优势**:
- ✅ 生态成熟，文档完善
- ✅ 完全免费，无调用限制
- ✅ 支持群聊机器人

---

## 四、技术架构

### 4.1 ClawBot 集成架构

```
┌──────────────┐
│  用户微信    │
│  (个人微信)  │
└──────┬───────┘
       │ 消息
       ▼
┌──────────────┐
│  微信服务器  │
└──────┬───────┘
       │ iLink 协议
       ▼
┌──────────────────────────────┐
│  OPC-Agents 微信集成模块     │
│  - ClawBotController        │
│  - WeChatMessageHandler     │
│  - WeChatNotificationSender │
│  - AccessTokenManager       │
└──────┬───────────────────────┘
       │ 内部 API
       ▼
┌──────────────────────────────┐
│  OPC-Agents 核心系统         │
│  - ConversationManager      │
│  - NotificationManager      │
│  - ExecutiveOffice          │
└──────────────────────────────┘
```

### 4.2 核心 API

#### iLink 协议端点
```bash
# 获取消息更新（轮询）
GET https://api.weixin.qq.com/ilink/bot/getupdates
  ?access_token=ACCESS_TOKEN
  &offset=0
  &limit=10
  &timeout=30

# 发送消息
POST https://api.weixin.qq.com/ilink/bot/sendmessage
Content-Type: application/json

{
  "to_user": "openid_xxx",
  "type": "text",
  "text": {
    "content": "您好，这是 OPC-Agents 的自动回复"
  }
}
```

### 4.3 数据库设计

```sql
-- 微信用户绑定表
CREATE TABLE wechat_users (
    id TEXT PRIMARY KEY,
    opc_user_id TEXT NOT NULL,
    wechat_openid TEXT NOT NULL,
    wechat_unionid TEXT,
    nickname TEXT,
    avatar_url TEXT,
    bound_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP,
    UNIQUE(opc_user_id),
    UNIQUE(wechat_openid)
);

-- 微信消息记录表
CREATE TABLE wechat_messages (
    id TEXT PRIMARY KEY,
    wechat_openid TEXT NOT NULL,
    message_id TEXT NOT NULL,
    update_id INTEGER,
    message_type TEXT NOT NULL,
    content TEXT,
    direction TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (wechat_openid) REFERENCES wechat_users(wechat_openid)
);
```

---

## 五、实施计划

### Phase 2.4: 微信集成（ClawBot）- 1 周

#### Day 1: 基础架构
- 注册微信开放平台账号
- 创建 ClawBot 应用
- 获取 app_id 和 app_secret
- 数据库表设计
- 配置管理

#### Day 2-3: 后端开发
- ClawBotController（iLink API 集成）
- WeChatMessageHandler（消息解析与处理）
- WeChatNotificationSender（通知推送）
- 用户绑定功能
- Access Token 管理（自动刷新）

#### Day 4: 消息类型支持
- 文本消息
- 图片消息
- 语音消息（可选）
- 图文消息（通知推送用）

#### Day 5: 测试与部署
- 单元测试
- 集成测试（与微信服务器联调）
- 部署到服务器
- 配置 iLink API 参数

#### Day 6-7: 缓冲时间
- Bug 修复
- 性能优化
- 文档完善
- 用户体验优化

---

## 六、风险评估

### 6.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| ClawBot 资质审核 | 中 | 高 | 准备备选方案（企业微信） |
| 免费额度不足 | 低 | 中 | 评估付费方案或切换企业微信 |
| 文档不完善 | 中 | 中 | 联系微信技术支持，社区调研 |
| iLink API 不稳定 | 低 | 中 | 重试机制，错误监控 |

### 6.2 应对措施

1. **并行准备企业微信方案**: 如 ClawBot 不可行，立即切换
2. **分阶段实施**: 先实现基础功能，再逐步增强
3. **充分测试**: 与微信服务器充分联调

---

## 七、预期收益

### 7.1 用户价值

1. **便捷性**: 无需打开 Web，微信即可交互
2. **实时性**: 即时接收通知和推送
3. **易用性**: 使用日常微信，降低学习成本
4. **多样性**: 支持语音、图片等多种交互

### 7.2 商业价值

1. **用户增长**: 降低使用门槛
2. **用户留存**: 提升用户体验
3. **差异化竞争**: 微信集成是竞争优势

---

## 八、决策确认

### 8.1 决策者
- **提案**: AI 助理
- **审核**: 产品经理
- **批准**: 用户

### 8.2 批准状态

- [ ] 用户批准
- [ ] 产品经理批准
- [ ] 架构师批准

### 8.3 下一步

1. ✅ **方案确认**: ClawBot 插件（个人微信 + iLink 协议）
2. ⏳ **注册微信开放平台**: 用户操作
3. ⏳ **创建 ClawBot 应用**: 获取配置信息
4. ⏳ **开始 Phase 2.4 开发**

---

**报告人**: AI 助理  
**日期**: 2026-04-14  
**版本**: 1.0
