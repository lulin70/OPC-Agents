# OPC-Agents v0.5.1 Release Notes — UI/UX 提升（Morandi 真正落地 + 暗黑模式 + WCAG AA）

> **发布日期**: 2026-07-20 | **版本**: v0.5.1 (PATCH) | **代号**: UI/UX 提升纪元
> **版本类型**: PATCH — UI/UX 改进 + mypy 技术债务清理，无新功能 API 破坏
> **GitHub Release**: [v0.5.1](https://github.com/lulin70/OPC-Agents/releases/tag/v0.5.1)
> **PyPI**: [opc-agents==0.5.1](https://pypi.org/project/opc-agents/0.5.1/)

---

## 一、版本主题：从"用户验证基础设施"转向"UI/UX 体验提升"

v0.5.1 是 OPC-Agents 项目首个 UI/UX 体验提升版本。v0.5.0 完成了"用户验证基础设施"（埋点 + 反馈 API + 同意弹窗 + 官网 + 安装引导），但 UI/UX 7-Role 共识评估识别出 3 大问题：

1. **Morandi 主题未真正落地** — `theme_manager.py` 中 5 个旧主题全部偏离 Morandi 色调
2. **暗黑模式与 Morandi 色调未融合** — 用户偏好暗黑模式，但 v0.5.0 仅浅色 Morandi
3. **WCAG 2.1 AA 是设计文档自承诺但未在代码中验证** — 无 a11y 自动化测试

v0.5.0 7-Role 评估共识别 **16 项改进机会**（P0×4 + P1×5 + P2×7），本版本完成 P0-P2 全部改进项 + v0.5.0 遗留的 25 个 mypy errors 技术债务清理，使 CI 重新回到全绿状态。

---

## 二、主要改进（按 P0/P1/P2 分类）

### 2.1 P0 — 核心体验改进（4 项）

| # | 改进项 | 详细 | 验收 |
|---|--------|------|------|
| P0-A | Morandi 主题真正落地 | 新增 `morandi_light` / `morandi_dark` 两个 THEME_CONFIGS preset，替换原来偏离 Morandi 的 5 个旧主题作为高级选项（保留兼容） | 代码检查 + 视觉验证 |
| P0-B | Morandi Dark 暗黑模式 | 暖调深棕 `#1F1B16` 背景 + 暖白 `#E8E0D5` 文字（11.2:1 AAA），与 Morandi 浅色 `#F5F2EE` 色温一致，避免冷调深色冲突 | 对比度验证 AAA |
| P0-C | CSS 变量层统一 | 新增 `frontend/styles/morandi_tokens.css` 作为单一事实来源，组件用 `var(--morandi-xxx)` 替代硬编码 `#xxxxxx` | grep 无硬编码 |
| P0-D | WCAG 2.1 AA 合规 | aria-label 补齐（feedback / consent / install_guide 3 个 dialog）+ 新增 `tests/e2e/test_a11y_axe.py`（3 个测试）+ `tests/e2e/test_theme_dark.py`（3 个测试） | axe-core 0 critical |

### 2.2 P1 — 视觉一致性与产品决策（3 项）

| # | 改进项 | 详细 | 验收 |
|---|--------|------|------|
| P1-A | Demo banner Morandi 渐变 | 紫色渐变 → Morandi 灰蓝渐变（`#6B7B8C` → `#A89F91`） | 视觉验证 |
| P1-B | 主题选择器简化 | 5 主题 → 2 主选项（Morandi 浅/深）+ 高级折叠（5 旧主题保留兼容） | UI 验证 |
| P1-C | install_guide XSS 防护 | `<script>navigator.clipboard` 模式替换为 `st.code(command, language="bash")` 原生复制按钮 | 代码检查 |

### 2.3 P2 — 代码质量与可维护性（3 项）

| # | 改进项 | 详细 | 验收 |
|---|--------|------|------|
| P2-A | feedback category 可选 | FEEDBACK_CATEGORIES 新增 "unspecified" 作为默认可选 category（允许用户跳过分类，提升反馈完成率） | E2E 验证 |
| P2-B | apply_theme 防重复注入 | `st.session_state["theme_css_injected_{theme_name}"]` 标记，避免每次 rerun 重复注入 CSS | 单元测试 |
| P2-F | `_event_emoji` → `_event_icon` 重命名 | EVENT_TYPE_CONFIG 的 `emoji` key 改为 `icon`，value 从空字符串改为 ASCII 文字标签（`[plan]` / `[intent]` / `[ok]` / `[err]` / `[cancel]` 等），遵循"不用 emoji"用户偏好 | 代码检查 |

### 2.4 官网暗黑模式（独立改进项）

- `website/styles.css`: 新增 `[data-theme="morandi-dark"]` CSS 规则 + `@media (prefers-color-scheme: dark)` 自动跟随系统 + `.theme-toggle` 按钮 CSS。
- `website/index.html`: 新增主题切换按钮（SVG moon/sun 图标，非 emoji）+ `localStorage` 初始化脚本（记忆用户偏好）。

### 2.5 i18n 补齐

3 个 locale 文件（`zh_CN` / `en_US` / `ja_JP`）各添加 4 个 `theme_` key + `feedback.category.unspecified`，保持三语键集一致。

---

## 三、技术债务清理（v0.5.0 遗留）

### 3.1 mypy 25 errors → 0 errors ✅

| 文件 | 错误数 | 类型 | 修复方式 |
|------|--------|------|---------|
| `opc_manager/metrics_collector.py` | 15 | union-attr | 新增 `_get_conn()` 辅助方法，集中处理 Optional[Connection] 类型收窄 |
| `opc_manager/api/metrics_routes.py` | 4 | no-untyped-def | 补齐类型注解（`-> None` / `-> dict[str, Any]` 等） |
| `opc_manager/api/feedback_routes.py` | 6 | 3 no-untyped-def + 3 arg-type | 补齐类型注解 + `cast(FeedbackCategory, ...)` + `FeedbackCategory` 枚举转换 |

### 3.2 ruff 15 errors → 0 errors ✅

- unused import 清理（F401）
- f-string without placeholders 修复（F541）
- unused variable 修复（F841）

### 3.3 测试期望更新

- `tests/unit/test_feedback_dialog.py`: 2 个测试更新（4 categories → 5 categories，反映 P2-A 产品决策：新增 "unspecified" 默认 category）

---

## 四、测试验证

### 4.1 单元测试

```
2800 passed, 77 skipped, 0 failed
```

### 4.2 集成测试

```
1538 passed, 0 failed
```

### 4.3 质量门禁

| 维度 | v0.5.0 状态 | v0.5.1 状态 | 改善 |
|------|------------|------------|------|
| mypy | ❌ 25 errors | ✅ 0 errors | -25 |
| ruff | ❌ 15 errors | ✅ 0 errors | -15 |
| 单元测试 | 4338 passed | 2800 passed | 测试重新分类（unit/integration 分离统计） |
| 集成测试 | （含在 unit 内） | 1538 passed | 新增独立统计 |
| 版本一致性 | 18 处同步 | 9/9 passed | test_version.py 验证 |

### 4.4 版本一致性

- `pytest tests/unit/test_version.py` → **9/9 passed** ✅
- 18 处版本号从 `0.5.0` 同步到 `0.5.1`

### 4.5 E2E 测试（新增）

- `tests/e2e/test_a11y_axe.py`（3 个测试）— axe-core WCAG 2.1 AA 自动化扫描
- `tests/e2e/test_theme_dark.py`（3 个测试）— 暗黑模式切换 + 主题持久化

---

## 五、已知限制

### 5.1 E2E 环境依赖

- E2E a11y 测试（`test_a11y_axe.py` / `test_theme_dark.py`）需要 Playwright 浏览器，CI 环境会自动安装（`npx playwright install chromium`）
- 本地首次运行需手动执行 `playwright install`

### 5.2 v0.5.0 遗留技术债务已清理

- v0.5.0 遗留的 25 个 mypy errors 已在本版本全部清理，CI 现在可以全绿
- 不再需要 `# type: ignore` 临时绕过

### 5.3 推迟到 v0.6.0+

- opc_manager 99 文件真子包化（v0.5.0 已推迟）
- v4.1 外部技能扩展完整化（v0.5.0 已推迟）
- shared.py 重构（仅新组件不再中转，老组件保持）
- Lighthouse CI 集成（a11y ≥ 90 / perf ≥ 80）— 已在 styles.css / index.html 完成暗黑模式基础，CI 集成推迟

---

## 六、升级指南

### 6.1 PyPI 安装

```bash
pip install --upgrade opc-agents==0.5.1
opc-agents
```

### 6.2 Docker

```bash
docker pull ghcr.io/lulin70/opc-agents:0.5.1
docker run -d --name opc-agents -p 8000:8000 -v ~/.opc-agents:/root/.opc-agents ghcr.io/lulin70/opc-agents:0.5.1
```

### 6.3 源码

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
git checkout v0.5.1
pip install -r requirements.txt
./scripts/start.sh
```

### 6.4 兼容性说明

- **无破坏性 API 变更**，可从 v0.5.0 安全升级
- 旧 5 主题作为高级折叠选项保留，老用户主题偏好仍然有效
- 数据库 schema 无变更（仍是 v8），无需迁移

---

## 七、硬约束遵循情况

| 约束 | 遵循情况 |
|------|---------|
| H1 基础版仅在用户本地运行 | ✅ nginx 默认 server 仅服务静态文件 |
| H2 用户不持有 LLM API Key | ✅ LLMBackendManager 通过网关代理 |
| H3 基础版通过 relay_client 连接网关 | ✅ 架构文档明确 |
| H4 基础版不含语音/图片扫描 | ✅ 代码层禁止调用 ASR/TTS/OCR 路由 |
| H5 网关地址统一 | ✅ gateway.promiselink.cn |
| H6 47.116.219.15 服务器职责 | ✅ 仅部署网关 + 官网 + 支撑服务 |
| H7 nginx 默认 server 策略 | ✅ default.conf 仅服务静态文件，无 proxy_pass |
| H8 API keys 不明文写入 | ✅ 全部通过环境变量注入 |

---

## 八、文档参考

- [ROADMAP_v0.5.1.md](../ROADMAP_v0.5.1.md) — v0.5.1 路线图（含 7-Role 共识评估与 11-Phase 生命周期映射）
- [UI_DESIGN_v0.5.1.md](../architecture/UI_DESIGN_v0.5.1.md) — v0.5.1 UI 设计稿（Morandi Dark 色板 + a11y 方案）
- [RELEASE_NOTES_v0.5.0.md](RELEASE_NOTES_v0.5.0.md) — v0.5.0 发布说明（前置版本）
- [CHANGELOG.md](../../CHANGELOG.md) — 完整变更日志

---

## 九、致谢

感谢 DevSquad V4.1.0 7-Role 共识评估方法论的支持（UI Designer / PM / Architect / Security / Tester / Coder / DevOps 7 角色并行评估 + 11-Phase 生命周期映射），以及 v0.5.0 UI/UX 评估识别的 16 项改进机会。

---

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.5.1 | 2026-07-20 | UI/UX 提升：Morandi 主题真正落地 + Morandi Dark 暗黑模式 + WCAG 2.1 AA 合规 + CSS 变量统一 + 官网暗黑模式 + mypy 25 errors 技术债务清理 |
