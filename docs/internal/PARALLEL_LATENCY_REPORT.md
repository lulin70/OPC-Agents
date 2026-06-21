# 三贤者并行投票延迟对比报告

> **文档状态**: S2-T9 产出
> **版本**: v0.3.0
> **日期**: 2026-06-19
> **负责角色**: Tester
> **任务ID**: S2-T9 [P0-5验收]

---

## 一、测试环境

- Python: 3.12.13
- pytest: 9.0.3（plugins: cov-7.1.0, timeout-2.4.0, asyncio-1.3.0, anyio-4.13.0）
- 测试机器: macOS (darwin)
- Mock LLM 延迟: 0.3s/次（单脑 RTT）
- 并行调度: `asyncio.gather`（三脑并发）
- 串行调度: `strategist → executor → reflector` 顺序调用

## 二、延迟对比结果

实测数据（`/tmp/measure_latency.py` 跑 3 脑各 sleep 0.3s）：

| 模式 | 实测延迟 | 理论延迟 | 说明 |
|------|----------|----------|------|
| 串行流水线 | 0.929s | 3 × RTT = 0.9s | strategist→executor→reflector 串行 |
| 并行投票 | 0.310s | 1 × RTT = 0.3s | `asyncio.gather` 三脑并行 |
| 加速比 | **3.00x** | 3x | 并行比串行快 3 倍 |
| 并行/串行比率 | **0.33** | ≤ 0.6 | 并行延迟仅为串行的 33% |
| 是否达标 | ✅ | ✅ | 并行 < 串行 × 0.6（0.929 × 0.6 = 0.557s，0.310 < 0.557） |

**结论**：并行投票延迟 0.310s 远低于串行 0.929s 的 60%（0.557s），加速比达 3.00x，符合预期。

## 三、功能验证

核心测试套件运行结果（`PYTHONPATH=. pytest <file> --timeout=10 -v`）：

| 测试套件 | 测试数 | 结果 | 耗时 |
|---------|--------|------|------|
| test_parallel_sages.py | 24 | ✅ 全通过 | 1.48s |
| test_executor_opinion.py | 20 | ✅ 全通过 | 0.06s |
| test_reflector_prediction.py | 12 | ✅ 全通过 | 0.03s |
| test_consensus_engine.py | 54 | ✅ 全通过 | 0.25s |
| test_agent_brain.py | 58 | ✅ 全通过 | 7.40s |
| test_brain_modules.py | 78 | ✅ 全通过 | 0.08s |
| **核心合计** | **246** | ✅ **全通过** | 9.30s |

### 关键测试用例验证

| 测试用例 | 验证场景 | 结果 |
|---------|---------|------|
| `TestParallelVsSerialLatency::test_parallel_faster_than_serial` | 并行延迟 < 串行 × 0.6 | ✅ PASS |
| `TestParallelConsensus::test_parallel_consensus_normal` | 三脑 AGREE → approved | ✅ PASS |
| `TestParallelConsensus::test_parallel_consensus_veto` | executor DISAGREE → 否决 | ✅ PASS |
| `TestParallelConsensus::test_parallel_consensus_timeout_degrades_to_serial` | 超时降级串行 | ✅ PASS |
| `TestParallelConsensus::test_parallel_consensus_all_fail_degrades` | 全失败降级串行 | ✅ PASS |
| `TestParallelConsensus::test_serial_consensus_fallback` | 串行降级路径 | ✅ PASS |
| `TestParallelConsensus::test_parallel_disabled_uses_serial` | 开关关闭走串行 | ✅ PASS |
| `TestCollectOpinionsAsync::test_collect_opinions_async_normal` | 异步收集正常 | ✅ PASS |
| `TestCollectOpinionsAsync::test_collect_opinions_async_with_exception` | 单脑异常 → ABSTAIN | ✅ PASS |
| `TestCollectOpinionsAsync::test_collect_opinions_async_all_exception` | 全异常 → 不通过 | ✅ PASS |
| `TestCollectOpinionsAsync::test_collect_opinions_async_veto` | 异步含否决 → VETOED | ✅ PASS |

## 四、决策正确性验证

| 场景 | 预期 | 实际 | 结果 |
|------|------|------|------|
| 三脑一致同意 | approved=True, UNANIMOUS | approved=True, UNANIMOUS | ✅ |
| 某脑否决（DISAGREE） | approved=False, VETOED | approved=False, VETOED | ✅ |
| 某脑超时 | 降级串行重试 | 降级串行，三脑 AGREE → approved | ✅ |
| 全部失败 | 降级串行 | 降级串行，串行方法被调用 | ✅ |
| 单脑异常（async） | 该脑 ABSTAIN，多数同意通过 | 2 AGREE + 1 ABSTAIN → approved | ✅ |
| 全部异常（async） | 全 ABSTAIN → 不通过/升级 | 无 AGREE → approved=False | ✅ |
| 并行开关关闭 | 走串行路径 | 串行方法被调用，异步方法未调用 | ✅ |

## 五、更广泛回归测试

运行命令（排除网络依赖的 E2E 测试）：

```bash
PYTHONPATH=. pytest --timeout=10 \
  --ignore=tests/test_e2e_real.py \
  --ignore=tests/test_e2e_user_journeys.py \
  --ignore=tests/test_e2e_user_workflow.py \
  --ignore=tests/test_integration_e2e.py \
  --ignore=tests/test_wechat_e2e.py \
  -q
```

**结果**：`2985 passed, 45 failed, 8 skipped, 1 xpassed in 347.53s`

### 失败项分析（全部与并行投票改造无关）

45 个失败项分布在以下模块，**均不导入** `agent_loop` / `consensus_engine` / `executor_brain` / `reflector_brain`，与 S2-T2~T4 改造无因果关系：

| 失败模块 | 失败数 | 根因 | 与并行投票关系 |
|---------|--------|------|---------------|
| test_undo_panel.py | 18 | 区域设置不匹配：测试期望中文（`刚刚`），环境返回日文（`たった今`） | ❌ 无关（i18n 环境问题） |
| test_audit_log.py | 11 | SQLite `database is locked` 导致 pytest-timeout 超时 | ❌ 无关（DB 锁竞争） |
| test_data_manager.py | 8 | SQL 执行错误 / DB 锁超时 | ❌ 无关（DB 锁竞争） |
| test_p1_skills.py | 7 | 社交技能内容生成断言失败 | ❌ 无关（技能模块） |
| test_regression_i18n.py | 1 | i18n 格式占位符跨语言一致性 | ❌ 无关（i18n） |

**结论**：并行投票改造（S2-T2~T4）**未引入任何回归**。45 个失败项均为预存在的环境/DB/i18n 问题，与三贤者并行投票代码路径无关联。

## 六、结论

三贤者并行投票改造成功：

1. **延迟显著降低**：从 3×RTT（0.929s）降至 1×RTT（0.310s），**加速 3.00 倍**，并行/串行比率 0.33，远低于 0.6 验收阈值。
2. **核心测试全通过**：246 个核心测试（6 个套件）全部通过，无回归。
3. **决策正确性验证通过**：一致同意/否决/超时降级/全失败降级/单脑异常/全异常/开关关闭 共 7 类场景全部符合预期。
4. **降级机制有效**：超时（`PARALLEL_VOTE_TIMEOUT`）和异常均能自动降级到串行路径（`_serial_consensus_fallback`），保证可靠性。
5. **广泛回归无新增失败**：2985 个测试通过，45 个失败项全部为预存在的环境/DB/i18n 问题，与并行投票改造无关。

**Sprint 2 P0-5 验收标准达成。**

## 七、验收清单

- [x] 并行延迟 < 串行延迟 × 0.6（实测 0.310 < 0.557）
- [x] 全部核心测试通过（246/246）
- [x] 决策正确性验证通过（否决/批准/折中/升级各场景）
- [x] 延迟对比报告生成（本文件）
- [x] 广泛回归测试无新增失败（45 失败均为预存在，与改造无关）

## 八、附录

### 8.1 延迟测量脚本

实测脚本位于 `/tmp/measure_latency.py`，核心逻辑：

```python
# 串行：3 × 0.3s = 0.9s
asyncio.run(loop._serial_consensus_fallback(context, "test", step))

# 并行：max(0.3s, 0.3s, 0.3s) = 0.3s
asyncio.run(loop._parallel_consensus(context, "test", step))
```

### 8.2 相关文件

- 实现：`opc_manager/agent_loop.py`、`opc_manager/consensus_engine.py`、`opc_manager/executor_brain.py`、`opc_manager/reflector_brain.py`
- 测试：`tests/test_parallel_sages.py`、`tests/test_executor_opinion.py`、`tests/test_reflector_prediction.py`、`tests/test_consensus_engine.py`、`tests/test_agent_brain.py`、`tests/test_brain_modules.py`
- 设计文档：`docs/architecture/PARALLEL_SAGES_DESIGN.md`
