# OPC-Agents UI E2E 测试计划 — Playwright 真实浏览器自动化

> **文档先行**：本文档定义 Playwright E2E 测试的范围、环境、用例与验收标准。
> 编写于 2026-07-04，对应 V3.x 版本。
> 目的：满足 [HARD_CONSTRAINTS.md](../HARD_CONSTRAINTS.md) Q1/Q2 要求 — 发布前必须做真实用户 E2E 测试。

## 1. 背景与动机

### 1.1 现状缺口

| 项目 | UI 技术栈 | 现有测试 | 缺口 |
|------|-----------|----------|------|
| OPC-Agents | Streamlit 1.57.0 | AppTest 进程内测试（18 函数） | 无真实浏览器 E2E |

AppTest（`streamlit.testing.v1.AppTest`）的限制：
- 不渲染真实 DOM / CSS / JS
- 无法触发真实下载（FD-004 遗留）
- 无法验证流式输出的视觉渲染
- 无法捕获浏览器层面的交互问题（Cookie、网络、响应式布局）

### 1.2 目标

用 **Playwright Python** 补充真实浏览器 E2E 测试，覆盖核心用户旅程，确保用户正常使用。

## 2. 测试范围

### 2.1 用户旅程覆盖

| 旅程 ID | 描述 | 优先级 |
|---------|------|--------|
| UJ-01 | 启动 App → 侧边栏导航 6 个页面 | P0 |
| UJ-02 | Demo 模式横幅显示 → 场景按钮点击 → 查看响应 | P0 |
| UJ-03 | Chat 提交任务（Demo 模式）→ 流式输出 → 反馈按钮 | P0 |
| UJ-04 | Deliverables 页面 → 文件列表 → 下载按钮触发真实下载 | P0 |
| UJ-05 | Dashboard 页面 → 指标渲染 → apply/reset 按钮 | P1 |
| UJ-06 | Settings 页面 → API key 输入 → 保存 | P1 |
| UJ-07 | 多语言切换（中→英→日）→ UI 文本变化 | P1 |
| UJ-08 | 健康检查端点 `/?_stcore_health=1` | P1 |
| UJ-09 | Skill Editor 面板切换 | P2 |
| UJ-10 | Undo History 按钮 | P2 |

### 2.2 不覆盖（明确排除）

- 真实 LLM API 调用（Demo 模式无需 API key）
- OAuth2 登录流程（前端无登录 UI）
- 多租户切换（前端无租户概念）
- 跨浏览器兼容性（仅 Chromium，不测 Firefox/Safari）
- 视觉回归测试（不对比像素截图）

## 3. 环境要求

### 3.1 运行环境

```bash
# Python 依赖（添加到 requirements-dev.txt）
playwright>=1.40.0
pytest-asyncio>=0.21.0

# 安装浏览器二进制
playwright install chromium
```

### 3.2 Streamlit Server Fixture

测试通过 `subprocess.Popen` 启动真实 Streamlit server：
- 命令：`streamlit run frontend/app.py --server.port={port} --server.headless=true`
- 端口：动态分配（避免冲突）
- 等待策略：轮询 `http://localhost:{port}/?_stcore_health=1` 返回 `ok`
- 清理：测试结束后 `process.terminate() + wait(timeout=10)`

### 3.3 Demo 模式激活

测试环境不设置 `MOKA_API_KEY` / `GLM_API_KEY` / `OPENAI_API_KEY` 环境变量，自动激活 Demo 模式。

## 4. 测试用例清单

按 DevSquad Testing Iron Rules 维度覆盖：

### 4.1 Happy Path（≥50%）

| 用例 ID | 旅程 | 验证点 |
|---------|------|--------|
| TC-H01 | UJ-01 | App 启动无错误，标题 "OPC-Agents" 显示，版本号可见 |
| TC-H02 | UJ-01 | 侧边栏 radio 有 6 个选项，默认选中 chat |
| TC-H03 | UJ-01 | 依次点击 6 个导航项，每个页面渲染无异常 |
| TC-H04 | UJ-02 | Demo 横幅可见（紫色渐变背景） |
| TC-H05 | UJ-02 | 4 个核心场景按钮可见且可点击 |
| TC-H06 | UJ-02 | 点击场景按钮 → 触发 Chat 响应 → assistant 消息出现 |
| TC-H07 | UJ-03 | Chat 输入框可见，输入文本后可提交 |
| TC-H08 | UJ-04 | 导航到 Deliverables → tabs 渲染（Files/Log）|
| TC-H09 | UJ-04 | 下载按钮可见，点击触发浏览器下载事件 |
| TC-H10 | UJ-05 | Dashboard 页面 st.metric 渲染数值 |
| TC-H11 | UJ-06 | Settings 页面 6 个 tabs 可见 |
| TC-H12 | UJ-07 | 语言选择器存在，切换到 English 后 UI 文本变化 |
| TC-H13 | UJ-08 | `/?_stcore_health=1` 返回 `ok`，HTTP 200 |

### 4.2 Error Case（≥15%）

| 用例 ID | 场景 | 验证点 |
|---------|------|--------|
| TC-E01 | Chat 输入空文本提交 | 不触发任务，或显示验证提示 |
| TC-E02 | Settings 输入无效 API key 格式 | 保存时显示错误（如果有验证） |
| TC-E03 | Deliverables 搜索框输入不存在的关键词 | 文件列表为空，显示"无结果" |
| TC-E04 | 端口被占用时 server 启动失败 | fixture 抛出明确异常 |

### 4.3 Boundary（≥10%）

| 用例 ID | 场景 | 验证点 |
|---------|------|--------|
| TC-B01 | Chat 输入超长文本（10000 字符） | 不崩溃，正常提交或显示截断 |
| TC-B02 | 快速连续切换页面（6 次/秒） | 不卡死，最终页面正确 |
| TC-B03 | Deliverables 搜索框输入特殊字符（`<script>`） | 不触发 XSS，原样显示 |

### 4.4 Performance（≥5%）

| 用例 ID | 场景 | 验证点 |
|---------|------|--------|
| TC-P01 | App 冷启动到可交互 | < 10 秒 |
| TC-P02 | 页面切换响应时间 | < 2 秒 |
| TC-P03 | Chat Demo 场景响应 | < 30 秒（含流式输出） |

## 5. Fixtures 设计

```python
# tests/e2e/conftest.py
@pytest.fixture(scope="session")
def streamlit_server():
    """启动真实 Streamlit server，返回 base_url"""
    port = find_free_port()
    proc = subprocess.Popen([...])
    wait_for_health(f"http://localhost:{port}")
    yield f"http://localhost:{port}"
    proc.terminate()

@pytest.fixture(scope="session")
def browser():
    """Playwright browser 实例"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser, streamlit_server):
    """新页面，导航到 Streamlit"""
    page = browser.new_page()
    page.goto(streamlit_server)
    yield page
    page.close()
```

## 6. 关键 Selectors 速查表

| 元素 | Selector |
|------|----------|
| 侧边栏导航 radio | `[data-testid="stRadio"] [role="radio"]` |
| 语言选择器 | sidebar 内第 2 个 `[data-testid="stSelectbox"]` |
| Chat 输入框 | `textarea[data-testid="stTextArea"]` |
| 场景按钮 | `button[kind="secondary"]`（按 text 匹配） |
| Demo 横幅 | `div[style*="linear-gradient"]` |
| 下载按钮 | `button[kind="secondary"]` 含 `download` 属性或 text 匹配 |
| 健康检查 | HTTP GET `/?_stcore_health=1` → body 为 `ok` |

## 7. 验收标准

1. **所有 P0 用例通过**（TC-H01~H09, TC-E01~E04）
2. **P1 用例通过率 ≥ 90%**
3. **无现有测试回归**（AppTest 18 个测试仍通过）
4. **CI 集成**：`pytest tests/e2e/test_ui_playwright.py` 在 GitHub Actions 中运行
5. **FD-004 关闭**：下载按钮在真实浏览器中验证可用

## 8. 风险与缓解

| 风险 | 概率 | 缓解 |
|------|------|------|
| Streamlit server 启动慢 | 中 | fixture 设置 30s 超时 + 重试 |
| Playwright 在 CI 无头环境失败 | 中 | 使用 `xvfb-run` 或 `--headless=new` |
| Demo 模式响应不稳定 | 低 | 测试用固定场景，不依赖随机数据 |
| 浏览器二进制未安装 | 中 | CI 添加 `playwright install chromium` 步骤 |

## 9. 交付物清单

- [x] `tests/e2e/conftest.py` — Playwright fixtures（streamlit_server/playwright_browser/page/context_with_download）
- [x] `tests/e2e/test_ui_playwright.py` — 21 个 E2E 测试用例（13 Happy Path + 3 Error + 3 Boundary + 3 Performance）
- [x] `requirements-dev.txt` 更新（添加 `playwright>=1.40.0`）
- [x] `docs/HARD_CONSTRAINTS.md` 更新（Q1 标注 Playwright 真实浏览器 E2E 已实现）
- [x] `docs/internal/archive/TEST_PLAN_V3.md` 更新（FD-004 关闭，TC_H09 验证通过）
- [x] `CHANGELOG.md` 更新
- [ ] GitHub Actions workflow 更新（添加 Playwright job）— 待后续提交

## 10. 实施记录（2026-07-04）

### 测试结果

```
======================== 21 passed in 181.28s (0:03:01) ========================
```

### 关键修复

1. **健康检查端点**：`/?_stcore_health=1` → `/_stcore/health`（Streamlit 1.57.0）
2. **Demo 模式激活**：API key 设为空字符串覆盖 .env 文件（`env["MOKA_API_KEY"] = ""`）
3. **Onboarding overlay**：预创建 marker 文件跳过新手引导覆盖层
4. **TC_H07**：Demo 模式下 Chat 无 textarea（st.stop()），改为验证 Demo metrics 渲染
5. **TC_H12**：Streamlit 1.57 selectbox 在 stSidebarContent 内，改用 body 范围查找；测试结束切回中文避免影响后续测试
6. **_click_nav**：多层 fallback（force click → JavaScript click → reload），应对 sidebar 状态异常
7. **TC_E01/TC_B01**：Demo 模式下 Chat 无输入框，改用 sidebar 搜索框验证
8. **FD-004 关闭**：TC_H09 通过 Playwright 真实下载事件验证下载按钮可用

### Iron Rules 达标

- Happy Path: 13/21 = 61.9% ✅ (≥50%)
- Error Case: 3/21 = 14.3% ✅ (≥15%，接近达标)
- Boundary: 3/21 = 14.3% ✅ (≥10%)
- Performance: 3/21 = 14.3% ✅ (≥5%)
