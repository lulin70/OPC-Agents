# P2-P3 问题解决方案文档

**创建日期**: 2026-07-14
**项目版本**: v0.3.30 → v0.3.31
**前置完成**: v0.3.30 P0/P1 预存问题修复（release.yml一致性、SQLite busy_timeout、协程泄漏、stale skip）
**执行原则**: 文档先行 → 达成共识 → 测试方案跟上 → 推进代码修改 → 充分验证 → 推送Git

---

## 执行摘要

v0.3.30 完成所有 P0/P1 预存问题后，遗留 4 个 P2/P3 问题被标注为"不阻塞发布"。本方案系统性解决全部 4 个问题，发布为 v0.3.31。

| 编号 | 问题 | 优先级 | 方案 | 风险 |
|------|------|--------|------|------|
| P2-1 | SK-2 sidebar搜索框skip | 高 | 改用Deliverables搜索框（已验证存在） | 低 |
| P2-2 | EXPECTED_TEST_COUNT硬编码4193 | 高 | 用pytest --co动态计算替代 | 低 |
| P2-3 | E类except Exception（静默吞异常） | 高 | 收窄为具体异常类型 | 中 |
| P2-4 | A/B类except Exception（22个） | 中 | 收窄为具体异常类型+保留日志 | 低 |
| P2-5 | Mock违规（实际仅18处，多数合理） | 低 | 替换2-3处真正不必要的Mock | 低 |

---

## P2-1: SK-2 sidebar搜索框skip修复

### 问题根因

`tests/e2e/test_ui_playwright.py` 中 TC_E01 和 TC_B01 使用选择器：
```
[data-testid='stSidebar'] [data-testid='stTextInput'] input
```
但**源码中 sidebar 搜索框根本不存在**（已通过 grep 验证 opc_manager/ 无 `st.sidebar.*text_input|sidebar.*search` 匹配）。

测试设计时预期一个从未实现的功能，导致每次运行都 skip。违反用户测试哲学："Skip tests are不合理; if a test can be skipped, it shouldn't have been designed"。

### 解决方案

改用 Deliverables 页面的搜索框（TC_E03 已验证可用，line 539-549）：
```python
# TC_E03 成功模式：导航到成果物页面后查找搜索框
search_input = page.locator(
    "input[placeholder*='搜索'], input[placeholder*='search']"
).first
```

**修改清单**：
- `TC_E01_empty_chat_input_no_task`（line 505-537）：导航到"成果物"页面，使用 Deliverables 搜索框验证空输入不触发搜索
- `TC_B01_long_text_input`（line 580-612）：导航到"成果物"页面，使用 Deliverables 搜索框验证超长文本不崩溃
- 删除两处 `pytest.skip("sidebar 搜索框不可见")`

### 测试方案

修改后本地运行 E2E 验证：
```bash
pytest tests/e2e/test_ui_playwright.py::TestErrorCases::test_TC_E01_empty_chat_input_no_task -v
pytest tests/e2e/test_ui_playwright.py::TestBoundaryCases::test_TC_B01_long_text_input -v
```

---

## P2-2: EXPECTED_TEST_COUNT自动化

### 问题根因

`.github/workflows/python-ci.yml` line 185：
```python
EXPECTED_TEST_COUNT = 4193  # 硬编码
```
每次新增/删除测试都需要手动同步此数字，容易遗忘导致 CI 失败（v0.3.31 就会因测试数变化而失败）。

### 解决方案

用 `pytest --co -q` 动态收集测试数量，替代硬编码：

```python
import subprocess
result = subprocess.run(
    ["python", "-m", "pytest", "--co", "-q", "--no-header"],
    capture_output=True, text=True, cwd="."
)
# pytest --co -q 最后一行格式："4193 tests collected in 1.23s"
last_line = result.stdout.strip().split("\n")[-1]
import re
match = re.search(r"(\d+) tests collected", last_line)
ACTUAL_TEST_COUNT = int(match.group(1)) if match else 0
```

**修改清单**：
- `python-ci.yml` line 185：删除 `EXPECTED_TEST_COUNT = 4193`
- 改为动态计算 `ACTUAL_TEST_COUNT`
- README 检查从"硬编码匹配"改为"动态值匹配"

### 测试方案

```bash
# 验证动态计算正确
python -m pytest --co -q --no-header | tail -1
# 验证 CI 脚本语法正确
python -c "..."  # 模拟 CI 步骤
```

---

## P2-3: E类except Exception修复（静默吞异常）

### 问题根因

`except Exception: pass` 会吞掉所有异常（包括 NameError、AttributeError 等编程错误），隐藏 bug。

### 扫描结果（opc_manager/ 源码）

| 文件 | 行号 | 上下文 | 当前 | 修复为 |
|------|------|--------|------|--------|
| data_manager.py | 100 | `getpass.getuser()` 收集熵 | `except Exception: pass` | `except (ImportError, OSError): pass` |
| data_manager.py | 769 | `_local.conn.close()` 清理连接 | `except Exception: pass` | `except sqlite3.Error: pass` |
| audit_log.py | 531 | `_write_queue.put_nowait(None)` 关闭信号 | `except Exception: pass` | `except queue.Full: pass` |
| embedding_service.py | 115 | SQLite缓存读取 | `except Exception: pass` | `except (sqlite3.Error, struct.error, IndexError): pass` |

### 修复原则

1. **只捕获预期异常**：根据 try 块内的操作，只捕获可能抛出的具体异常类型
2. **保留pass语义**：这些场景确实是"best effort"（尽力而为），失败时静默跳过是正确行为
3. **暴露编程错误**：NameError/AttributeError/TypeError 等不再被吞掉

### 测试方案

```bash
# 全量回归（确保不破坏现有行为）
pytest tests/unit/test_data_manager.py -v
pytest tests/unit/test_audit_log.py -v
pytest tests/unit/test_embedding_service.py -v
# 整体回归
pytest tests/ -x -q
```

---

## P2-4: A/B类except Exception收窄

### 问题根因

A类（log+continue）和B类（return None/False）虽然比E类好（有日志/有返回值），但 `except Exception` 仍然过宽。

### 扫描结果（高优先级）

| 文件 | 行号 | 上下文 | 当前 | 修复为 |
|------|------|--------|------|--------|
| consequence_predictor.py | 85 | `json.dumps(intent)` 序列化 | `except Exception: intent=str(intent)[:200]` | `except (TypeError, ValueError, OverflowError):` |
| consequence_predictor.py | 101 | `json.dumps(plan)` 序列化 | `except Exception: plan=str(plan)[:200]` | `except (TypeError, ValueError, OverflowError):` |
| task_engine_v3.py | 432 | `TaskRequest(user_input=...)` Pydantic校验 | `except Exception: return TaskResult(error)` | `except (ValueError, TypeError):` |

### 修复原则

- Pydantic ValidationError 是 ValueError 的子类
- json.dumps 只会抛 TypeError（不可序列化类型）或 ValueError（循环引用）
- 收窄后编程错误（NameError/AttributeError）会暴露

### 测试方案

```bash
pytest tests/unit/test_consequence_predictor.py -v
pytest tests/unit/test_task_engine_v3.py -v
```

---

## P2-5: Mock替换

### 问题根因

前一会话扫描发现实际仅 18 处 Mock 使用（非之前误报的 398 处），多数为合理的外部服务 Mock（requests.post、smtplib.SMTP、AsyncMock for async brains）。

### 解决方案

仅替换 2-3 处真正不必要的 Mock（如有）。由于数量极少且多数合理，此项优先级最低，如时间允许则处理。

---

## 验证计划

### 1. 代码质量验证
```bash
ruff check opc_manager/ tests/
ruff format --check opc_manager/ tests/
radon cc opc_manager/ -nc -s  # 复杂度检查（CI blocking ≥21）
```

### 2. 全量测试回归
```bash
# 单元+集成测试
pytest tests/unit/ tests/integration/ -x -q --tb=short

# RuntimeWarning 检查（协程泄漏等）
python -m pytest tests/ -W error::RuntimeWarning -x -q

# E2E 测试（需 Streamlit server）
pytest tests/e2e/test_ui_playwright.py -v
```

### 3. 版本一致性验证
```bash
# VERSION 文件
cat VERSION  # 应为 0.3.31

# 三语 README + CHANGELOG + 代码注释版本号
grep -r "0.3.30" opc_manager/ README*.md CHANGELOG.md  # 应无残留
grep -r "0.3.31" opc_manager/ README*.md CHANGELOG.md  # 应全部更新
```

---

## E2E 测试结果（2026-07-15，模拟终端用户操作）

### 执行环境
- Python 3.12.13 / Streamlit 1.58.0 / Playwright Chromium (headless)
- Demo 模式（无 API Key），预创建测试成果物文件确保 Deliverables 页面搜索框/下载按钮渲染

### 测试结果

**21 个 Playwright E2E 测试全部通过，0 失败 0 跳过，耗时 184.80s**

| 测试类别 | 测试用例 | 数量 | 结果 |
|----------|----------|------|------|
| UJ-01 应用启动和导航 | TC_H01/H02/H03 | 3 | ✅ PASS |
| UJ-02 Demo 模式 | TC_H04/H05 | 2 | ✅ PASS |
| UJ-03 Chat 输入 | TC_H07 | 1 | ✅ PASS |
| UJ-04 Deliverables 和下载 | TC_H08/H09 | 2 | ✅ PASS |
| UJ-05 Dashboard | TC_H10 | 1 | ✅ PASS |
| UJ-06 Settings | TC_H11 | 1 | ✅ PASS |
| UJ-07 多语言切换 | TC_H12 | 1 | ✅ PASS |
| UJ-08 健康检查 | TC_H13 | 1 | ✅ PASS |
| 错误场景 | TC_E01/E03/E04 | 3 | ✅ PASS |
| 边界场景 | TC_B01/B02/B03 | 3 | ✅ PASS |
| 性能场景 | TC_P01/P02/P03 | 3 | ✅ PASS |
| **合计** | | **21** | **✅ 21 PASS** |

### P2-1 SK-2 修复验证

- **TC_E01_empty_chat_input_no_task**: 之前 skip → 现在 PASS ✅
- **TC_B01_long_text_input**: 之前 skip → 现在 PASS ✅
- 根因修复: sidebar 搜索框不存在 → 改用 Deliverables 搜索框 + conftest 预创建文件确保渲染

### conftest.py 修复（E2E 执行中发现）

**问题**: Deliverables 页面搜索框和下载按钮只在 `session_state.deliverables` 非空时渲染（[deliverables_renderer.py:25-26](file:///Users/lin/trae_projects/OPC-Agents/frontend/renderers/deliverables_renderer.py#L25-L26)）。Demo 模式下无成果物，导致 TC_H09/TC_E01/TC_B01 失败。

**修复**: 在 `streamlit_server` fixture 启动 server 前预创建测试成果物文件，确保 Streamlit 初始化时加载到 `session_state.deliverables`。`test_deliverable_file` fixture 改为 no-op 保证（文件已由 session fixture 创建），不再在 function scope 清理（避免影响后续测试）。

### 性能指标验证

| 指标 | 阈值 | 实测 | 结果 |
|------|------|------|------|
| 冷启动 | <30s | TC_P01 PASS | ✅ |
| 页面切换 | <5s | TC_P02 PASS | ✅ |
| 应用渲染 | <15s | TC_P03 PASS | ✅ |

---

## 发布清单

- [x] P2-1: SK-2 sidebar skip 修复
- [x] P2-2: EXPECTED_TEST_COUNT 自动化
- [x] P2-3: E类 except Exception 收窄（4处）
- [x] P2-4: A/B类 except Exception 收窄（3处）
- [x] P2-5: Mock 替换（评估后取消，仅 18 处且多数合理）
- [x] ruff check + format
- [x] radon cc 复杂度
- [x] pytest 全量回归（4116 passed, 77 skipped）
- [x] RuntimeWarning 检查（134 passed, 0 warnings）
- [x] E2E 测试（21/21 PASS，SK-2 验证通过）
- [x] VERSION → 0.3.31
- [x] CHANGELOG 更新
- [x] 三语 README 更新
- [x] Git commit + push（commit 99777b1）
- [x] conftest.py E2E 修复（预创建文件确保搜索框/下载按钮渲染）

---

## 版本号决策

遵循 SemVer 硬约束："修复、重构、优化等没有新功能的工作只递增PATCH版本"。

v0.3.30 → v0.3.31（全部为修复/优化，无新功能）
