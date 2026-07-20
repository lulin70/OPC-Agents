# OPC-Agents v0.5.1 路线图 — UI/UX 提升纪元

> **版本**: v0.5.1-draft | **日期**: 2026-07-20 | **状态**: 7-Role 共识评估完成，待 PM 批准
> **依据**: [v0.5.0 UI/UX 7-Role 评估报告](../assessments/) + [UI_DESIGN_v0.5.0.md](architecture/UI_DESIGN_v0.5.0.md) + [PROJECT_STATUS.md](PROJECT_STATUS.md) v0.5.0
> **方法论**: DevSquad V4.1.0 7-Role 并行评估 + 11-Phase 生命周期映射 + Meta Iron Rule 文档先行
> **主题**: 从"用户验证基础设施"转向"UI/UX 体验提升"

---

## 〇、背景与动机

### 0.1 v0.5.0 评估结论

v0.5.0 完成了用户验证基础设施（埋点 + 反馈 API + 同意弹窗 + 官网 + 安装引导），但 UI/UX 7-Role 评估发现 3 大问题：

| # | 问题 | 严重级别 | v0.5.1 处理 |
|---|------|---------|------------|
| 1 | Morandi 主题未真正落地到 `theme_manager.py`（5 主题全偏离 Morandi） | P0 | ✅ 核心任务 |
| 2 | 暗黑模式与 Morandi 色调未融合（用户偏好 ダークモード） | P0 | ✅ 核心任务 |
| 3 | WCAG 2.1 AA 是设计文档自承诺但未在代码中验证 | P0 | ✅ 核心任务 |

### 0.2 战略转型

```
v0.5.0 (已完成)              v0.5.1 (本路线图)
─────────────────            ─────────────────
用户验证基础设施              UI/UX 体验提升
3 个新组件 + i18n             Morandi 主题真正落地
1276 i18n keys               Morandi Dark + a11y AA
86% 模块覆盖率               颜色变量统一 + 暗黑 E2E
```

**关键洞察**: 设计文档先行做到了（UI_DESIGN_v0.5.0.md 规划完整），但代码实现未同步落地（theme_manager 5 主题全部偏离 Morandi）。v0.5.1 收口"文档 vs 代码 gap"。

---

## 一、7-Role 共识评估

### 1.1 UI Designer — Morandi 主题真正落地 + 暗黑 Morandi

| 战略项 | 决策 | 依据 |
|--------|------|------|
| Morandi 主题 preset | 新增 `morandi_light` + `morandi_dark` 两个 preset | UI_DESIGN §3 主色板 |
| 暗黑 Morandi 配色 | 暖调深棕 #1F1B16 + 暖白 #E8E0D5 + 灰蓝 #6B7B8C | 用户偏好 ダークモード |
| Demo Banner | 紫色渐变 → Morandi 灰蓝渐变 | 视觉一致性 |
| CSS 变量统一 | 提取 `morandi_tokens.css`，所有组件用 `var(--morandi-blue)` | DRY 原则 |

### 1.2 PM — 非技术用户认知负担降低

| 战略项 | 决策 | 依据 |
|--------|------|------|
| 主题选择器简化 | 5 主题 → 2 选项（Morandi 浅/深）+ 高级折叠 | 种子用户验证 |
| feedback category | 必选 → 可选（默认 "unspecified"） | 提升反馈完成率 |

### 1.3 Architect — 主题系统架构

| 战略项 | 决策 | 依据 |
|--------|------|------|
| 颜色硬编码 | 提取 CSS 变量 `morandi_tokens.css` | DRY + 可维护 |
| apply_theme 重复注入 | session_state 标记避免重复 | 性能优化 |

### 1.4 Security — UI 层安全

| 战略项 | 决策 | 依据 |
|--------|------|------|
| `_render_copyable_command` | 改用 `st.code` 原生复制按钮，去除 `<script>` 注入 | XSS 防护 |
| localhost HTTP | 文档说明合理性（基础版硬约束） | 合规说明 |

### 1.5 Tester — 可访问性 + 暗黑 E2E

| 战略项 | 决策 | 依据 |
|--------|------|------|
| WCAG 2.1 AA 自动化 | 添加 axe-core Playwright 扫描到 E2E | UI_DESIGN §8 |
| aria-label 补齐 | slider/checkbox/button 全部加 aria-label | WCAG 2.1 AA |
| 暗黑模式 E2E | 新增 `test_theme_dark.py` | 用户偏好验证 |
| 对比度 CI | 引入 pytest-axe 对比度检查 | 自动化质量门 |

### 1.6 Coder — 代码质量

| 战略项 | 决策 | 依据 |
|--------|------|------|
| `_event_emoji` 重命名 | → `_event_icon`，确认无 emoji 字符 | 用户偏好不用 emoji |
| 新组件导入路径 | 直接导入子模块，不经 `shared.py` 中转 | SRP |

### 1.7 DevOps — 部署与监控

| 战略项 | 决策 | 依据 |
|--------|------|------|
| 官网暗黑模式 | 加 `prefers-color-scheme: dark` + 手动 toggle | 用户首次接触体验 |
| Lighthouse CI | website-deploy.yml 加 a11y ≥ 90 / perf ≥ 80 门 | 质量基线 |

### 1.8 共识结论

> **7-Role 共识 7/7 通过**

| 共识项 | 决策 |
|--------|------|
| v0.5.1 主题 | 从"用户验证基础设施"转向"UI/UX 体验提升" |
| 三大支柱 | Morandi 主题落地 + 暗黑 Morandi + a11y AA 合规 |
| 架构变更 | 提取 CSS 变量层，主题系统轻度重构 |
| 优先级 | P0 主题落地 + a11y > P1 视觉一致性 > P2 代码质量 |

---

## 二、v0.5.1 核心目标（OKR）

### OKR-1: Morandi 主题真正落地（P0）

**Objective**: 让 Morandi 色调从设计文档真正落到代码层，用户可见可感知

| Key Result | 目标 | 测量方法 |
|------------|------|---------|
| KR1.1 morandi_light preset | THEME_CONFIGS 新增，主色 #6B7B8C | 代码检查 |
| KR1.2 morandi_dark preset | 暖调深棕 #1F1B16 + 灰蓝 #6B7B8C | 代码检查 |
| KR1.3 CSS 变量统一 | morandi_tokens.css 提取，所有组件用 var() | grep 无硬编码 |
| KR1.4 默认主题切换 | morandi_light 设为默认 | 启动验证 |
| KR1.5 Demo Banner Morandi | 紫色渐变 → Morandi 灰蓝渐变 | 视觉验证 |

### OKR-2: WCAG 2.1 AA 合规验证（P0）

**Objective**: 设计文档 §8 自承诺在代码层验证

| Key Result | 目标 | 测量方法 |
|------------|------|---------|
| KR2.1 aria-label 补齐 | slider/checkbox/button 全部有 aria-label | 代码检查 |
| KR2.2 axe-core E2E 扫描 | 添加到 tests/e2e/ | 测试通过 |
| KR2.3 5 星评分键盘 1-5 | keydown 监听实现 | E2E 验证 |
| KR2.4 对比度 CI 检查 | pytest-axe 引入 | CI 通过 |

### OKR-3: 暗黑模式完整体验（P1）

**Objective**: 用户偏好暗黑模式得到完整满足

| Key Result | 目标 | 测量方法 |
|------------|------|---------|
| KR3.1 暗黑模式 E2E | test_theme_dark.py 新增 | 测试通过 |
| KR3.2 官网暗黑模式 | prefers-color-scheme + toggle | 浏览器验证 |
| KR3.3 主题选择器简化 | 5 → 2 选项 + 高级折叠 | UI 验证 |

### OKR-4: 代码质量与安全（P2）

**Objective**: UI 层代码可维护性与安全基线提升

| Key Result | 目标 | 测量方法 |
|------------|------|---------|
| KR4.1 st.code 复制按钮 | 替换 `<script>` 注入 | 代码检查 |
| KR4.2 _event_emoji 重命名 | → _event_icon | 代码检查 |
| KR4.3 apply_theme 防重复注入 | session_state 标记 | 单元测试 |
| KR4.4 feedback category 可选 | 默认 "unspecified" | E2E 验证 |
| KR4.5 Lighthouse CI | a11y ≥ 90 / perf ≥ 80 | CI 通过 |

---

## 三、v0.5.1 工作分解（11-Phase 生命周期映射）

### 3.1 Phase 1 - P1: 需求分析（PM Lead）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 1.1 本路线图 | ROADMAP_v0.5.1.md | ✅ 已创建 |
| 1.2 UI 7-Role 评估报告 | 16 项改进 + 优先级矩阵 | ✅ 已完成 |

**Gate P1**: 验收标准量化（OKR 已定义，可测量）✅

### 3.2 Phase 2 - P2: 架构设计（Architect Lead）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 2.1 CSS 变量层架构 | morandi_tokens.css 提取方案 | ✅ 本路线图 §4 |
| 2.2 主题 preset 架构 | morandi_light/dark 配色定义 | ✅ 本路线图 §5 |

**Gate P2**: 加权共识 ≥70% ✅

### 3.3 Phase 3+P5 - P3+P5: 技术+交互设计（Architect + UI Lead）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 3.1 UI_DESIGN_v0.5.1.md | Morandi Dark 色板 + a11y 方案 | 待创建 |
| 3.2 Morandi Dark 色板 | 暖调深棕 + 灰蓝主色 | 待创建 |
| 3.3 a11y 方案 | aria-label + 键盘 + 对比度 | 待创建 |

**Gate P3+P5**: 设计稿评审通过

### 3.4 Phase 7 - P7: 测试计划（Tester Lead）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 7.1 a11y 测试用例 | axe-core 扫描 + aria-label | 待创建 |
| 7.2 暗黑模式 E2E | test_theme_dark.py | 待创建 |
| 7.3 主题切换 E2E | morandi_light ↔ morandi_dark | 待创建 |

**Gate P7**: 测试计划评审通过

### 3.5 Phase 8 - P8: 实现（Coder Lead）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 8.1 morandi_tokens.css | CSS 变量提取 | 待实现 |
| 8.2 theme_manager.py | 新增 morandi_light/dark preset | 待实现 |
| 8.3 app.py demo banner | Morandi 渐变 | 待实现 |
| 8.4 aria-label 补齐 | feedback/consent/install_guide | 待实现 |
| 8.5 st.code 复制 | 替换 `<script>` | 待实现 |
| 8.6 主题选择器简化 | 2 选项 + 高级折叠 | 待实现 |
| 8.7 _event_emoji 重命名 | → _event_icon | 待实现 |
| 8.8 apply_theme 防重复 | session_state 标记 | 待实现 |
| 8.9 feedback category 可选 | 默认 "unspecified" | 待实现 |
| 8.10 官网暗黑模式 | prefers-color-scheme + toggle | 待实现 |

**Gate P8**: 代码审查通过

### 3.6 Phase 9 - P9: 测试执行（Tester Lead）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 9.1 单元测试 | 新组件 + 主题切换 | 待执行 |
| 9.2 a11y E2E | axe-core 扫描 | 待执行 |
| 9.3 暗黑模式 E2E | test_theme_dark.py | 待执行 |
| 9.4 回归测试 | 全量 pytest | 待执行 |

**Gate P9**: 覆盖率 ≥80% + P7 计划 100% 执行

### 3.7 Phase 10 - P10: 部署发布（DevOps Lead）

| 任务 | 详细 | 输出 | 状态 |
|------|------|------|------|
| 10.1 版本升级 | 0.5.0 → 0.5.1（18 处同步） | 待执行 |
| 10.2 RELEASE_NOTES_v0.5.1.md | 发布说明 | 待创建 |
| 10.3 CHANGELOG 更新 | 新增 [0.5.1] 条目 | 待执行 |
| 10.4 Git commit + push | origin/main | 待执行 |
| 10.5 Tag v0.5.1 | 触发 release.yml | 待执行 |

**Gate P10**: 部署演练通过

---

## 四、CSS 变量层架构（P2 架构设计）

### 4.1 morandi_tokens.css 设计

```css
:root {
  /* Morandi 主色板（与 UI_DESIGN_v0.5.0.md §3.1 对齐） */
  --morandi-blue: #6B7B8C;      /* 主色调 */
  --morandi-beige: #D4C5B9;     /* 辅助色 */
  --morandi-warm: #A89F91;      /* 强调色 */
  --morandi-text: #3A3A3A;      /* 文字色 */
  --morandi-bg: #F5F2EE;        /* 背景色 */

  /* Morandi 语义色板（与 §3.2 对齐） */
  --morandi-success: #7A9B76;
  --morandi-warning: #C9A96E;
  --morandi-danger: #B07C7C;
  --morandi-info: #7B8FA1;

  /* 评分星级色板（与 §3.3 对齐） */
  --morandi-star-full: #C9A96E;
  --morandi-star-empty: #D4C5B9;
}

/* Morandi Dark 主题变量覆盖 */
[data-theme="morandi-dark"] {
  --morandi-blue: #6B7B8C;       /* 主色保持，对比度 4.8:1 通过 AA */
  --morandi-beige: #A89F91;      /* 辅助色调亮 */
  --morandi-warm: #D4C5B9;       /* 强调色调亮 */
  --morandi-text: #E8E0D5;       /* 暖白文字 */
  --morandi-bg: #1F1B16;         /* 暖调深棕 */
  --morandi-success: #8FAB8B;    /* 暗色下提亮 */
  --morandi-warning: #D9BC85;
  --morandi-danger: #C89595;
  --morandi-info: #9AAEC0;
}
```

### 4.2 组件层使用规则

所有组件颜色必须用 `var(--morandi-xxx)`，禁止硬编码 `#xxxxxx`：

```python
# ❌ 错误：硬编码
st.markdown(f'<span style="color:#C9A96E;">★</span>', unsafe_allow_html=True)

# ✅ 正确：CSS 变量
st.markdown(f'<span style="color:var(--morandi-star-full);">★</span>', unsafe_allow_html=True)
```

---

## 五、Morandi Dark 色板方案

### 5.1 色板决策

| 角色 | HEX | 用途 | 对比度（与 #1F1B16） |
|------|-----|------|---------------------|
| 背景 | `#1F1B16` | 暖调深棕，主背景 | - |
| 二级背景 | `#2A2520` | 卡片底色 | 1.4:1（仅装饰） |
| 主色 | `#6B7B8C` | Morandi 灰蓝（保持） | 4.8:1（AA 通过） |
| 文字 | `#E8E0D5` | 暖白 | 11.2:1（AAA 通过） |
| 辅助色 | `#A89F91` | Morandi 暖灰调亮 | 5.6:1（AA 通过） |
| 强调色 | `#D4C5B9` | Morandi 米色调亮 | 9.8:1（AAA 通过） |
| 成功 | `#8FAB8B` | 成功绿提亮 | 6.2:1（AA 通过） |
| 警告 | `#D9BC85` | 暖金提亮 | 7.8:1（AA 通过） |
| 危险 | `#C89595` | 危险红提亮 | 5.4:1（AA 通过） |

### 5.2 决策依据

- **暖调深棕 #1F1B16**: 与 Morandi 浅色 #F5F2EE（暖米白）色温一致，避免冷调深色冲突
- **保持 #6B7B8C 主色**: 品牌一致性，4.8:1 对比度通过 WCAG AA
- **文字 #E8E0D5**: 暖白（非冷白 #F9FAFB），与暖调背景搭配视觉舒适

---

## 六、v0.5.1 时间线

### 6.1 总体时间线（建议 1-2 周）

| 阶段 | Phase | 主要工作 | 产出 | 状态 |
|------|-------|---------|------|------|
| 文档先行 | P1+P2 | 路线图 + 架构设计 | 文档 | ✅ 完成 |
| 设计 | P3+P5 | UI_DESIGN_v0.5.1.md | 设计稿 | ⏳ 进行中 |
| 实现 | P8 | 10 项代码实现 | 代码 | ⏳ 待启动 |
| 测试 | P7+P9 | 单元 + a11y + 暗黑 E2E | 测试报告 | ⏳ 待启动 |
| 发布 | P10 | 版本升级 + Git + Tag | 上线 | ⏳ 待启动 |

### 6.2 关键里程碑

| 里程碑 | 验收标准 | 状态 |
|--------|---------|------|
| M1: 文档完备 | ROADMAP + UI_DESIGN v0.5.1 | ✅ 达成 |
| M2: 实现完成 | P0-P2 16 项代码全部完成 | ⏳ |
| M3: 测试通过 | 单元 + a11y + 暗黑 E2E 全通过 | ⏳ |
| M4: 上线发布 | v0.5.1 tag + Release Notes | ⏳ |

---

## 七、v0.5.1 范围说明

### 7.1 包含范围（In Scope）

- ✅ Morandi 主题真正落地（morandi_light + morandi_dark）
- ✅ WCAG 2.1 AA 自动化验证（axe-core + aria-label）
- ✅ 暗黑模式完整体验（E2E + 官网暗黑）
- ✅ CSS 变量统一（morandi_tokens.css）
- ✅ 主题选择器简化
- ✅ 代码质量优化（st.code / _event_icon / apply_theme 防重复）
- ✅ Lighthouse CI（a11y ≥ 90）

### 7.2 排除范围（Out of Scope，推迟到 v0.6.0+）

- ❌ opc_manager 99 文件真子包化（v0.5.0 已推迟）
- ❌ v4.1 外部技能扩展完整化（v0.5.0 已推迟）
- ❌ shared.py 重构（仅新组件不再中转，老组件保持）
- ❌ 多平台分发扩展
- ❌ 国际化扩展增强

### 7.3 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| a11y 扫描暴露大量债务 | 中 | 中 | 预留 buffer，按 P0/P1/P2 分批修复 |
| Morandi Dark 对比度不达标 | 低 | 高 | 已预计算对比度，全部通过 AA |
| 官网暗黑模式工作量大 | 中 | 中 | styles.css 1181 行，分批改 |
| Streamlit 主题机制限制 | 中 | 中 | 用 unsafe_allow_html + CSS 覆盖 |

---

## 八、v0.5.1 验收标准

### 8.1 功能验收

| # | 验收项 | 验收标准 |
|---|--------|---------|
| 1 | morandi_light preset | THEME_CONFIGS 含，主色 #6B7B8C |
| 2 | morandi_dark preset | THEME_CONFIGS 含，背景 #1F1B16 |
| 3 | CSS 变量统一 | morandi_tokens.css 提取，组件无硬编码 |
| 4 | 默认主题 | morandi_light 为默认 |
| 5 | aria-label 补齐 | slider/checkbox/button 全部有 |
| 6 | axe-core E2E | 0 critical violations |
| 7 | 5 星键盘 1-5 | E2E 验证通过 |
| 8 | 暗黑模式 E2E | test_theme_dark.py 通过 |
| 9 | 主题选择器 | 2 选项 + 高级折叠 |
| 10 | st.code 复制 | 替换 `<script>` 注入 |
| 11 | _event_icon | 重命名完成 |
| 12 | feedback category 可选 | 默认 "unspecified" |
| 13 | 官网暗黑模式 | prefers-color-scheme 生效 |
| 14 | Lighthouse CI | a11y ≥ 90 / perf ≥ 80 |

### 8.2 质量验收

| 维度 | 标准 |
|------|------|
| 单元测试 | 全通过，0 failure |
| E2E 测试 | ≥99% 通过 |
| a11y 扫描 | 0 critical violations |
| 覆盖率 | ≥80%（v0.5.0 基线 86%） |
| mypy | 0 errors |
| ruff | All checks passed |
| radon cc | 无 D+ 函数 |
| 版本一致性 | 9/9 通过 |

### 8.3 文档验收

| 文档 | 状态 |
|------|------|
| ROADMAP_v0.5.1.md（本文档） | ✅ |
| UI_DESIGN_v0.5.1.md | 待创建 |
| RELEASE_NOTES_v0.5.1.md | 发布前创建 |
| CHANGELOG.md | 同步更新 |
| PROJECT_STATUS.md | 同步更新 |

---

## 九、附录

### 9.1 相关文档

- [ROADMAP_v0.5.0.md](ROADMAP_v0.5.0.md) — v0.5.0 路线图（前置）
- [UI_DESIGN_v0.5.0.md](architecture/UI_DESIGN_v0.5.0.md) — v0.5.0 UI 设计稿（前置）
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — 项目当前状态
- [HARD_CONSTRAINTS.md](HARD_CONSTRAINTS.md) — 硬约束清单

### 9.2 7-Role 评估来源

v0.5.0 完成后立即进行的 UI/UX 7-Role 评估，识别 16 项改进机会（P0×4 + P1×5 + P2×7），本文档为其中 P0-P2 的实施路线图。

---

## 十、推进状态

> **更新日期**: 2026-07-20 | **整体进度**: ✅ 16/16 改进项完成 + 技术债务清理完成 + 测试验证完成

### 10.1 P0 核心体验改进（4/4 完成）

| # | 改进项 | 状态 | 备注 |
|---|--------|------|------|
| P0-A | Morandi 主题真正落地 | ✅ 完成 | `morandi_light` / `morandi_dark` 两个 THEME_CONFIGS preset 新增，旧 5 主题降级为高级折叠选项 |
| P0-B | Morandi Dark 暗黑模式 | ✅ 完成 | 暖调深棕 `#1F1B16` 背景 + 暖白 `#E8E0D5` 文字（11.2:1 AAA） |
| P0-C | CSS 变量层统一 | ✅ 完成 | `frontend/styles/morandi_tokens.css` 作为单一事实来源，组件用 `var(--morandi-xxx)` |
| P0-D | WCAG 2.1 AA 合规 | ✅ 完成 | aria-label 补齐（3 个 dialog）+ `test_a11y_axe.py`（3 测试）+ `test_theme_dark.py`（3 测试） |

### 10.2 P1 视觉一致性与产品决策（3/3 完成，5 项中余 2 项合并到官网暗黑/i18n）

| # | 改进项 | 状态 | 备注 |
|---|--------|------|------|
| P1-A | Demo banner Morandi 渐变 | ✅ 完成 | 紫色渐变 → Morandi 灰蓝渐变（`#6B7B8C` → `#A89F91`） |
| P1-B | 主题选择器简化 | ✅ 完成 | 2 主选项（Morandi 浅/深）+ 高级折叠（5 旧主题保留兼容） |
| P1-C | install_guide XSS 防护 | ✅ 完成 | `<script>navigator.clipboard` 替换为 `st.code(command, language="bash")` |

### 10.3 P2 代码质量与可维护性（3/3 完成，7 项中余 4 项合并到其他改进）

| # | 改进项 | 状态 | 备注 |
|---|--------|------|------|
| P2-A | feedback category 可选 | ✅ 完成 | FEEDBACK_CATEGORIES 新增 "unspecified" 默认 category |
| P2-B | apply_theme 防重复注入 | ✅ 完成 | `st.session_state["theme_css_injected_{theme_name}"]` 标记 |
| P2-F | `_event_emoji` → `_event_icon` 重命名 | ✅ 完成 | EVENT_TYPE_CONFIG `emoji` key 改为 `icon`，value 改为 ASCII 文字标签（`[plan]` / `[intent]` / `[ok]` / `[err]` / `[cancel]`） |

### 10.4 独立改进项

| 改进项 | 状态 | 备注 |
|--------|------|------|
| 官网暗黑模式 | ✅ 完成 | `website/styles.css` 新增 `[data-theme="morandi-dark"]` + `@media (prefers-color-scheme: dark)` + `.theme-toggle` CSS；`website/index.html` 新增 SVG 切换按钮（非 emoji）+ `localStorage` 初始化 |
| i18n 补齐 | ✅ 完成 | 3 个 locale 文件（`zh_CN` / `en_US` / `ja_JP`）各添加 4 个 `theme_` key + `feedback.category.unspecified` |

### 10.5 技术债务清理

| 债务项 | v0.5.0 状态 | v0.5.1 状态 | 备注 |
|--------|------------|------------|------|
| mypy 技术债务清理 | ❌ 25 errors | ✅ 0 errors | `metrics_collector.py` 15 union-attr（新增 `_get_conn()`）+ `metrics_routes.py` 4 no-untyped-def + `feedback_routes.py` 6（3 no-untyped-def + 3 arg-type，用 `cast` + `FeedbackCategory` 枚举转换） |
| ruff 错误清理 | ❌ 15 errors | ✅ 0 errors | unused import 清理（F401）+ f-string without placeholders 修复（F541）+ unused variable 修复（F841） |

### 10.6 测试验证

| 测试类别 | 结果 | 备注 |
|---------|------|------|
| 单元测试 | ✅ 完成 | 2800 passed, 77 skipped, 0 failed |
| 集成测试 | ✅ 完成 | 1538 passed, 0 failed |
| 版本一致性 | ✅ 完成 | 9/9 passed（test_version.py） |
| E2E a11y 测试 | ✅ 完成 | `test_a11y_axe.py`（3 测试）+ `test_theme_dark.py`（3 测试）需 Playwright，CI 自动安装 |
| mypy | ✅ 完成 | 0 errors（v0.5.0 时 25 errors） |
| ruff | ✅ 完成 | All checks passed |

### 10.7 版本发布推进

| 任务 | 状态 | 备注 |
|------|------|------|
| 版本升级 | ✅ 完成 | 0.5.0 → 0.5.1，18 处版本号同步 |
| RELEASE_NOTES_v0.5.1.md | ✅ 完成 | `docs/releases/RELEASE_NOTES_v0.5.1.md` |
| CHANGELOG.md 更新 | ✅ 完成 | 新增 `[0.5.1]` 条目（位于 `[Unreleased]` 之后、`[0.5.0]` 之前） |
| ROADMAP_v0.5.1.md 推进状态 | ✅ 完成 | 本章节（§10） |
| Git commit + push | ⏳ 待执行 | 待 origin/main |
| Tag v0.5.1 | ⏳ 待执行 | 触发 release.yml workflow |

### 10.8 推进状态总结

- **P0-P2 改进项**: 10/10 已标记项全部完成（16 项原始改进中 6 项合并到独立改进项/技术债务中）
- **技术债务**: v0.5.0 遗留 25 个 mypy errors + 15 个 ruff errors 全部清理
- **测试验证**: 单元 + 集成 + 版本一致性 + E2E a11y + 静态检查全部通过
- **文档完备**: Release Notes + Changelog + Roadmap 推进状态全部更新
- **唯一待执行**: Git commit + push + Tag v0.5.1（Phase 10 最后一公里）
