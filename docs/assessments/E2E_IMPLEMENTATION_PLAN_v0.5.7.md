# OPC-Agents v0.5.7 E2E 测试补齐实施计划

> **创建时间**: 2026-07-30 | **对应评估**: [E2E_REVIEW_v0.5.7.md](E2E_REVIEW_v0.5.7.md) | **版本**: v0.5.7 → v0.5.8+
> **目标**: 补齐 9 个 P0 阻断问题 + 12 个 P1 体验问题，将 E2E 综合评分从 5.0/10 提升至 8.0/10
> **原则**: 文档先行 + 外科手术式修改 + 测试 Iron Rules + Goal-Driven Execution

---

## 一、实施目标与范围

### 1.1 核心目标

| 目标 | 当前状态 | 目标状态 | 验收指标 |
|------|---------|---------|---------|
| 真实模式 E2E 覆盖率 | 0% | ≥80% | Chat 全链路 + 3 个 P0 技能 + Settings 全流程通过 |
| 数据库隔离 | 无 | 100% | E2E 不写入真实 `data/opc_data.db` |
| 视觉回归 | 无 | baseline 建立 | 4 个核心页面有 screenshot baseline |
| 响应式覆盖 | 1 viewport | 4 viewports | 手机/平板/桌面/FHD 全通过 |
| 安全 E2E | 23% | ≥60% | 认证 + 注入 + XSS 强化为强覆盖 |
| CI 独立 E2E job | 无 | 有 | E2E 独立 job + rerunfailures + artifact |
| 综合评分 | 5.0/10 | 8.0/10 | 7 角色平均分 ≥8.0 |

### 1.2 不在范围内

- 不重构现有测试文件结构（Sprint 6 后再考虑目录重组）
- 不引入 axe-core 库（保持手写 JS 扫描，避免新依赖）
- 不补 Firefox/WebKit 跨浏览器测试（P2 长尾）
- 不修改 `chat_router.py` 等源码（仅补测试，不改功能）

---

## 二、Sprint 分解

### Sprint 1: P0 快速阻断修复（4-6h）

**目标**: 修复 3 个低工作量高影响的 P0，消除数据污染和虚假通过风险。

#### 工作项 1.1: Playwright E2E 数据库隔离（GAP-P0-7，1-2h）

**问题**: `conftest.py` 的 `streamlit_server` fixture 未重定向 `OPC_DATA_DIR`，E2E 期间写入真实 `data/opc_data.db`。

**实现方案**:
```python
# conftest.py streamlit_server fixture 中添加
import tempfile
from pathlib import Path

# 在 env 字典中添加
e2e_data_dir = Path(tempfile.gettempdir()) / f"opc_e2e_data_{os.getpid()}"
e2e_data_dir.mkdir(parents=True, exist_ok=True)
env["OPC_DATA_DIR"] = str(e2e_data_dir)
env["OPC_WORKSPACE"] = str(e2e_data_dir)  # 确保完整隔离

# finally 中清理
import shutil
if e2e_data_dir.exists():
    shutil.rmtree(e2e_data_dir, ignore_errors=True)
```

**验收标准**:
- [ ] E2E 运行后 `data/opc_data.db` 不被修改（用 `git status` 验证）
- [ ] E2E 运行后 `/tmp/opc_e2e_data_*` 目录被清理
- [ ] 所有现有 E2E 测试仍通过

#### 工作项 1.2: 修复条件断言虚假通过（GAP-P1-11，0.5h）

**问题**: `test_e2e_user_journeys.py:716` 中 `if records and records[0].get("output_summary"):` 不满足时脱敏检查被静默跳过。

**实现方案**:
```python
# 修改前
if records and records[0].get("output_summary"):
    summary = records[0]["output_summary"]
    assert "sk-12345" not in summary
    assert "REDACTED" in summary

# 修改后
assert records, "审计记录不应为空"
assert records[0].get("output_summary"), "output_summary 不应为空"
summary = records[0]["output_summary"]
assert "sk-12345" not in summary, f"审计日志泄露敏感信息: {summary}"
assert "REDACTED" in summary, f"审计日志未脱敏: {summary}"
```

**验收标准**:
- [ ] 条件断言改为直接断言
- [ ] 测试仍通过（说明数据确实满足条件）
- [ ] 若数据不满足，测试明确失败而非静默跳过

#### 工作项 1.3: Docker 真实部署 E2E（GAP-P0-6，3-4h）

**问题**: `test_docker_deployment.py` 仅静态文件检查，无 `docker run` + 健康检查 + 端口访问验证。

**实现方案**: 新增 `tests/e2e/test_docker_run_e2e.py`
```python
"""Docker 真实部署 E2E 测试.

验证 Dockerfile 构建产物可运行、健康检查通过、端口可访问.
"""
import subprocess
import time
import urllib.request
import pytest

@pytest.mark.slow  # 标记为慢测试，CI 可选择性跳过
class TestDockerRunE2E:
    def test_docker_build_succeeds(self):
        """验证 docker build 成功."""
        result = subprocess.run(
            ["docker", "build", "-t", "opc-e2e-test", "."],
            capture_output=True, text=True, timeout=300
        )
        assert result.returncode == 0, f"docker build 失败: {result.stderr[-500:]}"

    def test_docker_run_health_check(self):
        """验证容器启动后健康检查通过."""
        # 启动容器
        proc = subprocess.Popen(
            ["docker", "run", "--rm", "-p", "8501:8501", "opc-e2e-test"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            # 等待健康检查通过（最多 60s）
            deadline = time.time() + 60
            while time.time() < deadline:
                try:
                    req = urllib.request.Request("http://127.0.0.1:8501/_stcore/health")
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        if resp.status == 200 and resp.read().decode().strip() == "ok":
                            return  # 健康检查通过
                except Exception:
                    pass
                time.sleep(2)
            pytest.fail("容器健康检查 60s 内未通过")
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    def test_docker_run_homepage_accessible(self):
        """验证容器首页可访问."""
        # 同上启动容器，验证 http://127.0.0.1:8501/ 返回 200
        ...
```

**验收标准**:
- [ ] `docker build` 成功
- [ ] 容器启动后 60s 内 `/_stcore/health` 返回 `ok`
- [ ] 首页 `http://127.0.0.1:8501/` 返回 200
- [ ] 测试标记 `@pytest.mark.slow`，CI 可选跳过

---

### Sprint 2: P0 核心价值流（16-20h）

**目标**: 补齐产品核心价值流 E2E（真实模式 Chat + P0 技能 + Settings），解决"首问即流失"风险。

#### 工作项 2.1: 真实模式 Chat 全链路 E2E（GAP-P0-1，8-10h）

**问题**: Playwright E2E 全部在 Demo 模式，`chat_router.py` 在 Demo 模式调用 `st.stop()` 跳过输入框。

**实现方案**:

1. **新增 conftest fixture `streamlit_server_with_mock_llm`**（2-3h）:
```python
@pytest.fixture(scope="session")
def streamlit_server_with_mock_llm():
    """启动带 Mock LLM 的 Streamlit server（模拟真实模式）.

    - 设置 MOKA_API_KEY 为测试 key（激活真实模式渲染）
    - Mock LLM 后端返回固定响应
    - 走完整 Chat 渲染流程（输入框可见、提交、轮询、成果物）
    """
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    
    env = os.environ.copy()
    env["MOKA_API_KEY"] = "test-key-for-e2e"  # 激活真实模式
    env["OPC_MOCK_LLM"] = "true"  # 新增环境变量，让 LLM 后端走 Mock
    env["OPC_DATA_DIR"] = str(e2e_data_dir)  # 数据隔离
    # ... 其余同 streamlit_server
    
    # 启动 server
    ...
```

2. **新增 `test_chat_real_mode_e2e.py`**（6-7h）:
```python
"""真实模式 Chat 全链路 E2E 测试.

覆盖产品核心价值流: 输入 → 提交 → 轮询 → 成果物 → 下载 → 反馈.
"""
class TestChatRealModeFullJourney:
    def test_input_box_visible_in_real_mode(self, page_real_mode):
        """验证真实模式下 Chat 输入框可见（非 Demo 模式 st.stop）."""
        page_real_mode.goto(streamlit_server_with_mock_llm)
        input_box = page_real_mode.locator("[data-testid='stTextArea'] textarea")
        expect(input_box).to_be_visible(timeout=15000)

    def test_submit_prompt_shows_progress(self, page_real_mode):
        """验证提交 prompt 后显示进度提示."""
        # 输入 prompt
        page_real_mode.locator("textarea").fill("帮我写Q2营销方案")
        page_real_mode.locator("button:has-text('发送')").click()
        # 验证进度提示出现
        progress = page_real_mode.locator("[data-testid='stSpinner']")
        expect(progress).to_be_visible(timeout=10000)

    def test_deliverable_rendered_after_completion(self, page_real_mode):
        """验证任务完成后成果物渲染."""
        # 提交 prompt + 等待完成
        ...
        # 验证成果物区域出现
        deliverable = page_real_mode.locator("[data-testid='stMarkdown']").filter(has_text="成果物")
        expect(deliverable).to_be_visible(timeout=60000)

    def test_download_button_triggers_download(self, page_real_mode, context_with_download):
        """验证下载按钮触发文件下载."""
        ...

    def test_feedback_buttons_visible(self, page_real_mode):
        """验证反馈按钮（good/bad）可见."""
        ...

    def test_suggestion_panel_shown_after_completion(self, page_real_mode):
        """验证智能建议面板在任务完成后显示."""
        ...
```

**验收标准**:
- [ ] 真实模式下 Chat 输入框可见
- [ ] 提交 prompt 后进度提示出现
- [ ] 任务完成后成果物渲染
- [ ] 下载按钮触发文件下载
- [ ] 反馈按钮（good/bad）可见
- [ ] 智能建议面板显示

#### 工作项 2.2: P0 技能 E2E（GAP-P0-2，6-8h）

**问题**: email/finance/report 三个 P0 技能被 `@patch.object(TaskEngineV3, "execute")` 整体 mock。

**实现方案**: 新增 `tests/e2e/test_p0_skills_e2e.py`
```python
"""P0 技能真实执行 E2E 测试.

不 mock TaskEngineV3.execute，用 Mock SMTP + 真实 DB 验证技能真实执行.
"""
class TestEmailSkillE2E:
    def test_email_send_via_mock_smtp(self, mock_smtp_server):
        """验证 email 技能通过 Mock SMTP 真实发送."""
        # 配置 SMTP 指向 mock_smtp_server
        # 输入 "帮我发邮件给客户"
        # 验证 mock_smtp_server 收到邮件
        # 验证审计日志记录
        # 验证频率限制生效

class TestFinanceSkillE2E:
    def test_income_recording_updates_dashboard(self, isolated_db):
        """验证 finance 技能记账后 Dashboard 指标更新."""
        # 输入 "帮我记一笔收入5000元"
        # 验证 DB 写入 income 表
        # 切换到 Dashboard 页面
        # 验证指标显示更新后的数值

class TestReportSkillE2E:
    def test_report_generation_creates_file(self, isolated_db):
        """验证 report 技能生成报告文件."""
        # 输入 "生成本月月报"
        # 验证文件生成到 deliverables/ 目录
        # 验证 Deliverables 页面显示新文件
```

**验收标准**:
- [ ] email 技能通过 Mock SMTP 真实发送
- [ ] finance 技能记账后 DB 写入 + Dashboard 更新
- [ ] report 技能生成报告文件 + Deliverables 列表更新

#### 工作项 2.3: Settings 配置生效流程 E2E（GAP-P0-3，4-6h）

**问题**: 6 个 Settings tab 仅验证 tabs 可见，配置表单提交/连接测试/生效流程零覆盖。

**实现方案**: 新增 `tests/e2e/test_settings_e2e.py`
```python
class TestSettingsConfigE2E:
    def test_llm_tab_config_save_and_persist(self, page):
        """验证 LLM tab 配置保存并持久化."""
        _click_nav(page, "设置")
        # 点击 LLM tab
        # 填入 API Key
        # 点击保存
        # 刷新页面
        # 验证 API Key 已保存（脱敏显示）

    def test_smtp_tab_test_connection_button(self, page, mock_smtp_server):
        """验证 SMTP tab 测试连接按钮."""
        ...

    def test_api_keys_tab_encrypted_storage(self, page):
        """验证 API Keys tab 加密存储."""
        ...

    def test_security_tab_encryption_settings(self, page):
        """验证 Security tab 加密设置."""
        ...

    def test_profile_tab_persona_switch(self, page):
        """验证 Profile tab 人设切换."""
        ...

    def test_backup_tab_backup_restore(self, page, isolated_db):
        """验证 Backup tab 备份恢复."""
        ...
```

**验收标准**:
- [ ] 6 个 Settings tab 表单提交可用
- [ ] 配置保存后刷新仍存在
- [ ] LLM tab 测试连接按钮可用
- [ ] SMTP tab 测试发送按钮可用

---

### Sprint 3: P0 安全 + UI（12-16h）

**目标**: 补齐 API 鉴权 + 视觉回归 + 响应式 E2E，解决安全盲区和移动端布局风险。

#### 工作项 3.1: API Server E2E + 鉴权（GAP-P0-5，4-6h）

**实现方案**: 新增 `tests/e2e/test_api_server_e2e.py`
```python
"""API Server 真实 HTTP 端点 E2E 测试."""
class TestAPIServerE2E:
    def test_feedback_endpoint_accepts_valid_request(self, api_server):
        """验证 feedback 端点接受有效请求."""
        response = httpx.post(f"{api_server}/api/v1/feedback", json={...})
        assert response.status_code == 200
        # Side-Effect: 验证 DB 写入
        ...

    def test_metrics_endpoint_returns_data(self, api_server):
        """验证 metrics 端点返回数据."""
        ...

    def test_unauthorized_request_rejected(self, api_server):
        """验证未授权请求被拒绝（需先添加鉴权中间件）."""
        ...
```

**前置条件**: 需先为 FastAPI 添加鉴权中间件（`X-API-Key` 头校验），这是源码修改，需单独评估。

**验收标准**:
- [ ] API 端点真实 HTTP 请求通过
- [ ] Side-Effect 验证（DB 写入）
- [ ] 未授权请求返回 401

#### 工作项 3.2: 响应式 viewport 参数化测试（GAP-P0-8，2-3h）

**实现方案**: 新增 `tests/e2e/test_responsive_e2e.py`
```python
"""响应式布局 E2E 测试."""
VIEWPORTS = [
    {"name": "mobile_se", "width": 375, "height": 667},
    {"name": "tablet_ipad", "width": 768, "height": 1024},
    {"name": "desktop", "width": 1280, "height": 800},
    {"name": "fhd", "width": 1920, "height": 1080},
]

@pytest.fixture(params=VIEWPORTS, ids=[v["name"] for v in VIEWPORTS])
def viewport_page(request, playwright_browser, streamlit_server):
    context = playwright_browser.new_context(viewport=request.param)
    page = context.new_page()
    page.goto(streamlit_server)
    yield page
    context.close()

class TestResponsiveLayout:
    def test_sidebar_visible_on_all_viewports(self, viewport_page):
        """验证侧边栏在所有 viewport 可见."""
        sidebar = viewport_page.locator("[data-testid='stSidebar']")
        expect(sidebar).to_be_visible()

    def test_no_horizontal_scroll_on_mobile(self, viewport_page, request):
        """验证手机端无水平滚动."""
        if request.node.callspec.params["name"] != "mobile_se":
            pytest.skip("仅手机端")
        scroll_width = viewport_page.evaluate("document.body.scrollWidth")
        client_width = viewport_page.evaluate("document.body.clientWidth")
        assert scroll_width <= client_width, "手机端出现水平滚动"

    def test_chat_input_visible_on_mobile(self, viewport_page, request):
        """验证手机端 Chat 输入框可见."""
        ...
```

**验收标准**:
- [ ] 4 个 viewport 全通过
- [ ] 手机端无水平滚动
- [ ] 所有 viewport 侧边栏可见

#### 工作项 3.3: 视觉回归 baseline（GAP-P0-9，3-4h）

**实现方案**: 新增 `tests/e2e/test_visual_regression.py`
```python
"""视觉回归测试."""
class TestVisualRegression:
    def test_homepage_light_theme(self, page, streamlit_server):
        """首页浅色主题 baseline."""
        page.goto(streamlit_server)
        page.wait_for_selector("[data-testid='stAppViewContainer']")
        expect(page).to_have_screenshot("homepage_light.png", max_diff_pixel_ratio=0.01)

    def test_dashboard_page(self, page, streamlit_server):
        """Dashboard 页面 baseline."""
        _click_nav(page, "Dashboard")
        expect(page).to_have_screenshot("dashboard.png", max_diff_pixel_ratio=0.01)

    def test_settings_page(self, page, streamlit_server):
        """Settings 页面 baseline."""
        _click_nav(page, "设置")
        expect(page).to_have_screenshot("settings.png", max_diff_pixel_ratio=0.01)

    def test_deliverables_page(self, page, streamlit_server):
        """Deliverables 页面 baseline."""
        _click_nav(page, "成果物")
        expect(page).to_have_screenshot("deliverables.png", max_diff_pixel_ratio=0.01)
```

**验收标准**:
- [ ] 4 个核心页面有 baseline 截图
- [ ] baseline 存入 `tests/e2e/__screenshots__/`
- [ ] UI 变更时测试失败（检测到差异）

---

### Sprint 4: P0 收尾 + P1 体验（20-24h）

**目标**: 补齐 Chat 错误恢复 UI + 注入测试 + 全主题 + 全页面无障碍。

#### 工作项 4.1: Chat 错误恢复 UI E2E（GAP-P0-4，3-4h）

**实现方案**: 新增 `tests/e2e/test_chat_error_recovery_e2e.py`
```python
class TestChatErrorRecovery:
    def test_timeout_error_shows_friendly_message(self, page_real_mode, mock_llm_timeout):
        """验证 timeout 错误显示友好提示."""
        ...

    def test_connection_error_shows_retry_button(self, page_real_mode, mock_llm_connection_error):
        """验证 connection 错误显示重试按钮."""
        ...

    def test_api_key_error_shows_config_hint(self, page_real_mode, mock_llm_api_key_error):
        """验证 api_key 错误显示配置提示."""
        ...

    def test_rate_limit_error_shows_wait_hint(self, page_real_mode, mock_llm_rate_limit):
        """验证 rate_limit 错误显示等待提示."""
        ...

    def test_server_error_shows_contact_support(self, page_real_mode, mock_llm_500):
        """验证 500 错误显示联系支持."""
        ...
```

#### 工作项 4.2: 注入测试（GAP-P1-2，2-3h）

**实现方案**: 新增 `tests/e2e/test_injection_e2e.py`
```python
class TestInjectionE2E:
    def test_sql_injection_in_search(self, page):
        """验证搜索框 SQL 注入防护."""
        page.locator("[data-testid='stTextInput'] input").fill("' OR 1=1 --")
        # 验证无 SQL 错误泄露

    def test_path_traversal_in_input(self, page):
        """验证路径穿越防护."""
        ...

    def test_command_injection_in_input(self, page):
        """验证命令注入防护."""
        ...
```

#### 工作项 4.3: 全主题 + 全页面无障碍（GAP-P1-7/8，4-6h）

**实现方案**: 参数化 `test_a11y_axe.py`
```python
PAGES = ["对话", "成果物", "Dashboard", "成长", "技能市场", "设置"]

@pytest.mark.parametrize("page_name", PAGES)
def test_a11y_per_page(page, page_name):
    """每个页面都做 WCAG AA 扫描."""
    _click_nav(page, page_name)
    _wait_for_streamlit_content(page)
    missing = page.evaluate(_SCAN_INTERACTIVES_JS)
    assert not missing
    violations = page.evaluate(_CONTRAST_SCAN_JS)
    assert not [v for v in violations if v["ratio"] < 4.5]

THEMES = ["light", "dark", "sunset", "forest", "ocean", "morandi_light", "morandi_dark"]

@pytest.mark.parametrize("theme", THEMES)
def test_theme_contrast_aa(page, theme):
    """每个主题都做 WCAG AA 对比度验证."""
    _select_theme_via_sidebar(page, theme)
    violations = page.evaluate(_CONTRAST_SCAN_JS)
    assert not [v for v in violations if v["ratio"] < 4.5]
```

---

### Sprint 5: P1 CI 优化（6-8h）

**目标**: E2E 独立 CI job + 重试机制 + 失败 artifact 上传。

#### 工作项 5.1: E2E 独立 CI job（GAP-P1-9，2-3h）

**实现方案**: 修改 `.github/workflows/python-ci.yml`
```yaml
jobs:
  test:
    # 现有 test job 保留，但移除 E2E step
    ...
  
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: test  # 单测过再跑 E2E 节省资源
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11"]  # 仅 3.11 跑 E2E
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      - run: |
          pip install -r requirements.txt -r requirements-dev.txt
          pip install -e .
      - run: playwright install chromium --with-deps
      - run: PYTHONPATH=. pytest tests/e2e/ --tb=short -v --timeout=120 --reruns=2 --reruns-delay=5
      - if: failure()
        uses: actions/upload-artifact@v7
        with:
          name: e2e-failure-artifacts
          path: |
            /tmp/opc_streamlit_e2e.log
            test-results.xml
            e2e-output.txt
```

#### 工作项 5.2: pytest-rerunfailures（GAP-P1-9，1h）

**实现方案**: `requirements-dev.txt` 添加 `pytest-rerunfailures>=14.0`

#### 工作项 5.3: artifact 上传（GAP-P1-10，1-2h）

已在 5.1 中实现。

---

### Sprint 6: P2 长尾（12-16h）

**目标**: 日文布局 + ARIA + 键盘陷阱 + 边界场景。

（详见评估报告 GAP-P2-1~10，此处略）

---

## 三、验收标准

### 3.1 每个 Sprint 的验收门禁

| Sprint | 验收门禁 |
|--------|---------|
| Sprint 1 | E2E 不污染真实数据 + 无虚假通过 + Docker 部署可运行 |
| Sprint 2 | 真实模式 Chat 全链路 E2E 通过 + 3 个 P0 技能 E2E 通过 + Settings 全流程通过 |
| Sprint 3 | API 未授权访问被拒 + 4 viewport 通过 + 视觉回归 baseline 建立 |
| Sprint 4 | Chat 错误恢复 UI 5 种错误通过 + 注入测试通过 + 7 主题 × 7 页面无障碍通过 |
| Sprint 5 | E2E 独立 CI job + 重试机制 + 失败 artifact 可查 |
| Sprint 6 | 日文布局 + ARIA + 键盘陷阱 + 边界场景通过 |

### 3.2 最终验收指标

- [ ] E2E 综合评分从 5.0/10 提升至 8.0/10
- [ ] 9 个 P0 问题全部解决
- [ ] 12 个 P1 问题全部解决
- [ ] 真实模式 E2E 覆盖率 ≥80%
- [ ] CI E2E job 独立 + 重试 + artifact
- [ ] 无 flaky test（连续 3 次 CI 全绿）

---

## 四、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Mock LLM 方案设计复杂 | 中 | Sprint 2 延期 | 先调研 chat_router.py 的 LLM 调用点，设计最小 Mock 方案 |
| FastAPI 鉴权修改影响现有 API | 中 | Sprint 3 延期 | 鉴权中间件向后兼容（默认允许 localhost） |
| 视觉回归 baseline 平台相关 | 高 | CI 失败 | baseline 仅本地生成，CI 标记 `@pytest.mark.skip(reason="平台相关")` |
| Docker E2E 在 CI 慢 | 中 | CI 超时 | 标记 `@pytest.mark.slow`，CI 可选跳过 |
| E2E 套件耗时过长 | 中 | CI 超时 | 仅 Python 3.11 跑 E2E + 并行化（pytest-xdist） |

---

## 五、文档同步清单

每个 Sprint 完成后必须同步更新：

| 文档 | 更新内容 |
|------|---------|
| `CHANGELOG.md` | 新增版本记录（Added: E2E 测试） |
| `README.md` × 3 | 测试数更新（三语同步） |
| `docs/PROJECT_STATUS.md` | E2E 覆盖率更新 |
| `docs/assessments/E2E_REVIEW_v0.5.7.md` | 标记已解决项 |
| `VERSION` + `opc_manager/version.py` | Patch 版本递增 |
| `docs/TECH_DEBT.md` | 记录 E2E 技术债清理 |

---

## 六、版本号规划

| Sprint | 版本 | 类型 | 说明 |
|--------|------|------|------|
| Sprint 1 | 0.5.8 | PATCH | CI 修复 + 数据隔离 + 条件断言 |
| Sprint 2 | 0.6.0 | MINOR | 真实模式 E2E（新功能：E2E 测试套件） |
| Sprint 3 | 0.6.1 | PATCH | 安全 + UI E2E |
| Sprint 4 | 0.6.2 | PATCH | P1 体验 E2E |
| Sprint 5 | 0.6.3 | PATCH | CI 优化 |
| Sprint 6 | 0.6.4 | PATCH | P2 长尾 |

**注**: 用户要求"只能升 Patch 版本"，但 Sprint 2 新增 E2E 测试套件属于新功能，按 SemVer 应升 MINOR。需与用户确认。

---

## 七、推进原则

1. **文档先行**: 每个 Sprint 开始前先更新本文档，完成后标记已完成
2. **外科手术式修改**: 只改必要的文件，不重构无关代码
3. **测试 Iron Rules**: 遵守 DevSquad Iron Rule 1-6（文档先行/失败报告/维度完整/Side-Effect/User Journey/E2E Release Gate）
4. **Goal-Driven**: 每个 Sprint 都有明确验收标准，未达标不进入下一 Sprint
5. **诚实评估**: 不修改测试断言来通过测试，发现源码 bug 立即报告

---

**计划完成**。等待用户确认后开始 Sprint 1 实施。
