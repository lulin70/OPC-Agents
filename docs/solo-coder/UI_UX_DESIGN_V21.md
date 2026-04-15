# OPC-Agents UI/UX 差异化设计方案 v2.1

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v2.1.0 | 2026-04-14 | UI设计师 | 基于6种业务类型设计差异化交互体验 | 待审核 |
| v2.0.0 | 2026-04-14 | UI设计师 | 初始版本，通用界面设计 | 已审核 |

---

## 一、设计理念

### 1.1 核心原则
**"巨头做基建，个体做场景"**

UI设计应该：
- ✅ **懂用户**：每种类型有不同的工作节奏和审美偏好
- ✅ **有个性**：不是千篇一律的SaaS界面
- ✅ **高效率**：减少操作步骤，信息密度适配
- ✅ **情感化**：通过视觉和动效传递人格温度

### 1.2 设计系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                   Design System V2.1                          │
│                                                             │
│  ┌─────────────┐                                           │
│  │ Foundation  │  基础层（所有类型共享）                    │
│  │             │  - Typography                             │
│  │             │  - Color Palette (6套主题色)              │
│  │             │  - Spacing & Grid                         │
│  │             │  - Components Library                     │
│  └──────┬──────┘                                           │
│         │                                                   │
│  ┌──────▼─────────────────────────────────────────────┐     │
│  │              Variant Layer (6种变体)                │     │
│  │                                                      │     │
│  │  🎬 Content    💰 Product   ⚡️ AI Tool              │     │
│  │     活泼多彩      商业蓝        科技黑               │     │
│  │                                                      │     │
│  │  💼 Consult    🛒 Ecommerce  🎨 Creative            │     │
│  │     专业沉稳      数据绿        灵感紫               │     │
│  │                                                      │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              Personalization Layer                    │     │
│  │          用户自定义 + 学习偏好 + A/B Test           │     │
│  └──────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、6种视觉风格定义

### 2.1 风格规格表

```yaml
# design-system/variants.yaml

variants:
  content_creator:
    name: "活力橙"
    color_palette:
      primary: "#FF6B35"      # 活力橙
      secondary: "#FF9F7F"    # 浅珊瑚
      accent: "#FFD700"       # 金色（爆款标记）
      background: "#FFF8F0"   # 暖白
      surface: "#FFFFFF"
      text_primary: "#2D3436"
      text_secondary: "#636E72"
    typography:
      heading_font: "Noto Sans SC"  # 圆润友好
      body_font: "Inter"
      style: "rounded"  # 圆角卡片
    components:
      card_radius: "16px"
      button_style: "pill-shaped"  # 胶囊按钮
      icon_style: "filled-colorful"
    layout:
      density: "spacious"  # 宽松留白
      information_density: "low"  # 信息密度低
      animation: "bouncy"  # 弹性动画
    
  digital_product:
    name: "商业蓝"
    color_palette:
      primary: "#4A90E2"      # 商务蓝
      secondary: "#A0C4FF"
      accent: "#00D084"       # 绿色（收入增长）
      background: "#F5F9FF"
      surface: "#FFFFFF"
    typography:
      heading_font: "DM Sans"
      body_font: "Inter"
      style: "sharp"
    components:
      card_radius: "8px"
      button_style: "rectangular"
      icon_style: "outline-minimal"
    layout:
      density: "balanced"
      information_density: "medium"
      animation: "smooth"
      
  ai_tool_builder:
    name: "科技黑"
    color_palette:
      primary: "#6C5CE7"      # 科技紫
      secondary: "#A29BFE"
      accent: "#00CEC9"       # 青色（终端感）
      background: "#1A1A2E"   # 深色背景！
      surface: "#16213E"
      text_primary: "#EAEAEA"
      text_secondary: "#A0A0A0"
    typography:
      heading_font: "JetBrains Mono"  # 等宽字体
      body_font: "Fira Code"
      style: "monospace-friendly"
    components:
      card_radius: "4px"
      button_style: "tech-border"
      icon_style: "line-technical"
    layout:
      density: "compact"
      information_density: "high"  # 高信息密度
      animation: "instant"  # 快速响应
      
  consultant:
    name: "专业灰"
    color_palette:
      primary: "#2D3436"      # 深灰
      secondary: "#636E72"
      accent: "#0984E3"       # 信任蓝
      background: "#FAFAFA"
      surface: "#FFFFFF"
    typography:
      heading_font: "Source Serif Pro"  # 衬线字体（专业感）
      body_font: "Source Sans Pro"
      style: "classic"
    components:
      card_radius: "2px"
      button_style: "minimal-outline"
      icon_style: "simple-line"
    layout:
      density: "structured"
      information_density: "medium-high"
      animation: "subtle"
      
  ecommerce:
    name: "数据绿"
    color_palette:
      primary: "#00B894"      # 成功绿
      secondary: "#55EFC4"
      accent: "#FD79A8"       # 粉色（促销）
      warning: "#FDCB6E"      # 黄色（库存预警）
      danger: "#FF7675"       # 红色（亏损）
      background: "#F0FFF4"
      surface: "#FFFFFF"
    typography:
      heading_font: "DIN Alternate"
      body_font: "Roboto"
      style: "data-driven"
    components:
      card_radius: "12px"
      button_style: "solid-prominent"
      icon_style: "chart-focused"
    layout:
      density: "data-rich"
      information_density: "very-high"  # 最高信息密度
      animation: "number-ticker"  # 数字滚动动画
      
  creative_work:
    name: "灵感紫"
    color_palette:
      primary: "#A55EEA"      # 创意紫
      secondary: "#D4A5FF"
      accent: "#FDCB6E"       # 暖黄（灵感）
      background: "#FAF5FF"
      surface: "#FFFFFF"
    typography:
      heading_font: "Playfair Display"  # 衬线艺术字体
      body_font: "Lato"
      style: "artistic"
    components:
      card_radius: "20px"
      button_style: "soft-shadow"
      icon_style: "artistic-filled"
    layout:
      density: "visual"
      information_density: "visual-low"  # 视觉优先
      animation: "elegant-fade"
```

---

## 三、关键页面差异设计

### 3.1 首页/对话中心

#### 内容创作者版
```
┌─────────────────────────────────────────────┐
│  🔥 今日热点 Top5                            │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐      │
│  │📈  │ │💄  │ │🎬  │ │📱  │ │✨  │      │
│  │春装 │ │美妆 │ │影视 │ │科技 │ │生活 │      │
│  └────┘ └────┘ └────┘ └────┘ └────┘      │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ 💬 对话区（大字体，emoji丰富）        │   │
│  │                                     │   │
│  │  🤖 嗨！今天有什么爆款想法？💡        │   │
│  │                                     │   │
│  │  [🎯 选题模式] [📅 日历模式] [📊 数据]  │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  📦 我的工作成果                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ 📝 日历  │ │ 📊 报告  │ │ 🎨 素材  │        │
│  │ 本周3篇  │ │ 涨粉128  │ │ 图片45张 │        │
│  └─────────┘ └─────────┘ └─────────┘        │
└─────────────────────────────────────────────┘
```

#### 电商运营者版
```
┌─────────────────────────────────────────────┐
│  📊 今日经营看板  [实时更新]                 │
│  ══════════════════════════════════════     │
│  GMV: ¥12,450  ↑12.3%  订单: 127单         │
│  ─────────────────────────────────          │
│  [▓▓▓▓▓▓▓▓▓▓▓] 月目标 68%               │
│                                             │
│  ⚠️ 库存预警                                │
│  ┌─────────────────────────────────────┐   │
│  │ 🔴 iPhone壳(黑) 仅23件 → 3天断货     │   │
│  │ 🟡 夏季T恤 库存偏高 → 建议促销        │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ 💬 对话区（数据密集型）               │   │
│  │                                     │   │
│  │  💰 老板好！今天的GMV目标多少？      │   │
│  │                                     │   │
│  │  [📦 选品] [📈 分析] [📋 客服] [⚙️设置] │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  📈 品类表现热力图                           │
│  ┌─────────────────────────────────────┐   │
│  │  热门图表 / 趋势线 / 排行榜          │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 3.2 Onboarding 流程

#### 类型选择页（关键页面）

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│        👋 欢迎使用 OPC-Agents                        │
│                                                     │
│   请选择最符合您的业务类型：                          │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │  🎬       │  │  💰       │  │  ⚡️       │          │
│  │ 内容创作  │  │ 数字产品  │  │ AI工具    │          │
│  │          │  │          │  │          │          │
│  │ "用内容   │  │ "一次制作  │  │ "AI加持   │          │
│  │  吸引粉丝" │  │ 反复销售"  │  │  自动化"  │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │  💼       │  │  🛒       │  │  🎨       │          │
│  │ 专业咨询  │  │ 电商运营  │  │ 创意生产  │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│                                                     │
│   💡 不确定？[做个快速测试] 来帮你判断              │
│                                                     │
│   [继续]                    [跳过，稍后设置]         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 3.3 人格切换指示器

```
顶部状态栏（全局显示）：

┌─────────────────────────────────────────────────────┐
│  [🎬 内容模式 ▾]  当前场景: 内容日历规划            │
│                      人格: 内容小助理 ✨            │
└─────────────────────────────────────────────────────┘

点击可展开菜单：
┌─────────────────────┐
│ 🔄 切换到其他模式    │
│ ├ 🎬 内容创作       │
│ ├ 💰 数字产品       │  ← 当前 ✓
│ ├ ⚡️ AI工具        │
│ ├ 💼 专业咨询       │
│ ├ 🛒 电商运营       │
│ └ 🎨 创意生产       │
│                     │
│ ⚙️ 自定义偏好...    │
└─────────────────────┘
```

---

## 四、响应式适配策略

### 4.1 设备断点

| 断点 | 适用设备 | 布局策略 |
|------|---------|---------|
| < 480px | 手机竖屏 | 单栏堆叠，底部导航 |
| 480-768px | 手机横屏/小平板 | 双列紧凑 |
| 768-1024px | 平板 | 侧边栏+主区域 |
| 1024-1440px | 笔记本 | 完整三栏布局 |
| > 1440px | 桌面/外接屏 | 宽松四栏+仪表盘 |

### 4.2 各类型移动端优化重点

| 类型 | 移动端核心功能 | 优化策略 |
|------|---------------|---------|
| 内容创作 | 快速记录灵感 | 语音输入 + 一键生成 |
| 数字产品 | 销售数据查看 | 卡片式KPI + 下拉刷新 |
| AI工具 | 反馈快速处理 | 滑动操作 + 批量标签 |
| 咨询 | 方案预览 | PDF原生渲染 |
| 电商 | 库存告警推送 | 通知优先 + 大按钮 |
| 创意 | 作品集展示 | 全屏画廊 + 手势导航 |

---

## 五、无障碍访问（Accessibility）

### 5.1 基础要求（所有类型）

- ✅ WCAG 2.1 AA级合规
- ✅ 键盘完全可操作
- ✅ 屏幕阅读器支持
- ✅ 色彩对比度 ≥ 4.5:1

### 5.2 特殊考虑

| 类型 | 特殊需求 | 解决方案 |
|------|---------|---------|
| 电商 | 数据表格复杂 | 简化视图 + 详细模式切换 |
| AI工具 | 代码块展示 | 等宽字体 + 语法高亮 |
| 内容创作 | 多媒体丰富 | Alt文本 + 字幕 |

---

## 六、设计交付物清单

### 6.1 必须产出

- [ ] 6套完整Design Token（Figma Variable）
- [ ] 关键页面Mockup（每个类型至少5个页面）
- [ ] 组件库更新（新增类型相关组件）
- [ ] 动效规范（6种动画风格）
- [ ] Onboarding流程原型（8-10屏）
- [ ] 响应式适配规范文档

### 6.2 可选产出

- [ ] Design System文档站
- [ ] 组件Storybook
- [ ] 用户测试脚本
- [ ] 开发交接文档

---

**文档状态**：✅ 初稿完成 | ⏳ 待产品经理确认用户体验要求 | ⏳ 待多角色共识

**下一步**：开始Figma原型设计和用户测试招募
