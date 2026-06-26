# 测试覆盖率基线

> **文档状态**: Sprint 1 产出（已完成）
> **版本**: v0.3.0
> **日期**: 2026-06-19
> **负责角色**: Tester + DevOps
> **任务ID**: S1-T6 ✅
> **测量方法**: pytest-cov，排除E2E测试（依赖网络）

---

## 〇、测量说明

- **工具**: pytest-cov 7.1.0（pytest-cov>=4.1.0 in requirements-dev.txt）
- **范围**: opc_manager/ + frontend/
- **排除**: E2E测试（test_e2e_*.py）因依赖网络API，单独运行
- **超时**: 每个测试10秒超时，避免网络阻塞
- **日期**: 2026-06-19
- **运行命令**:
  ```
  PYTHONPATH=. pytest --cov=opc_manager --cov=frontend \
    --cov-report=term-missing --cov-report=json:coverage.json \
    --tb=no -q --timeout=10 \
    --ignore=tests/test_e2e_real.py \
    --ignore=tests/test_e2e_user_journeys.py \
    --ignore=tests/test_e2e_user_workflow.py \
    --ignore=tests/test_integration_e2e.py \
    --ignore=tests/test_wechat_e2e.py \
    -p no:cacheprovider
  ```

---

## 一、总覆盖率基线

| 指标 | 值 | 备注 |
|------|-----|------|
| 总覆盖率 | **62.87%** | 基线值，远超v0.3.0目标40% |
| opc_manager 覆盖率 | **68.00%** | 9688/14248 行 |
| frontend 覆盖率 | **48.10%** | 2377/4942 行 |
| 总行数 | 19190 | |
| 已覆盖行数 | 12065 | |
| 缺失行数 | 7125 | |
| 测试总数 | 2949 | 排除E2E |
| 通过数 | 2949 | exit code 0（全绿） |
| 失败数 | 0 | |
| 跳过数 | 0 | E2E已排除 |

---

## 二、模块覆盖率详情

### 2.1 核心模块（高优先级）

| 模块 | 覆盖率 | 状态 | 备注 |
|------|--------|------|------|
| consensus_engine.py | 98.71% (153/155) | ✅ 优秀 | 三贤者核心，覆盖完整 |
| intent_classifier.py | 100.00% (38/38) | ✅ 优秀 | Sprint 2 待扩展三路分类 |
| reflector_brain.py | 92.20% (260/282) | ✅ 优秀 | Sprint 2 待新增 predict_consequence |
| report_skill.py | 87.92% (131/149) | ✅ 良好 | 核心技能 |
| strategist_brain.py | 84.12% (302/359) | ✅ 良好 | 三贤者核心 |
| executor_brain.py | 80.41% (156/194) | ✅ 良好 | Sprint 2 待新增 express_opinion |
| agent_loop.py | 65.94% (242/367) | ⚠ 中等 | Sprint 2 并行化后需补测试 |
| task_lifecycle.py | 48.96% (47/96) | ⚠ 不足 | Sprint 2 Consensus前置后需补测试 |
| email_skill.py | 16.96% (39/230) | ❌ 严重不足 | **核心技能，需优先补测试** |
| finance_skill.py | 14.46% (24/166) | ❌ 严重不足 | **核心技能，需优先补测试** |

**关键发现**: 两个核心技能（email/finance）覆盖率严重不足（<20%），是 Sprint 2/3 测试补充的重点。

### 2.2 冻结模块（低优先级）

冻结技能的覆盖率不作为v0.3.0的关注重点，仅记录基线。

| 模块 | 覆盖率 | 状态 |
|------|--------|------|
| dashboard_skill.py | 92.93% (92/99) | 完全冻结 |
| tax_reminder_skill.py | 85.37% (105/123) | 完全冻结 |
| pricing_skill.py | 75.42% (89/118) | 完全冻结 |
| knowledge_skill.py | 68.55% (109/159) | 完全冻结 |
| proposal_skill.py | 68.97% (80/116) | 完全冻结 |
| competitor_skill.py | 58.06% (72/124) | 完全冻结 |
| invoice_skill.py | 57.89% (55/95) | 完全冻结 |
| calendar_skill.py | 51.03% (99/194) | 完全冻结 |
| social_skill.py | 36.68% (73/199) | 完全冻结 |
| task_skill.py | 29.92% (38/127) | 半冻结 |
| crm_skill.py | 12.97% (31/239) | 半冻结 |

---

## 三、零覆盖文件清单

以下文件在基线测量中覆盖率为0%，需要在后续Sprint中补充测试或评估是否删除：

| 文件 | 行数 | 优先级 | 计划 |
|------|------|--------|------|
| opc_manager/api/events.py | 55 | 中 | Sprint 2 评估：是否仍需要（事件API） |
| opc_manager/cli.py | 59 | 中 | Sprint 2 评估：CLI入口是否仍使用 |
| opc_manager/experimental/wechat_agent.py | 83 | 低 | experimental目录，可考虑删除 |

零覆盖文件总数：3（占文件总数比例低，基线健康）

---

## 四、v0.3.0 覆盖率目标

| 维度 | 基线 | v0.3.0目标 | 差距 | 状态 |
|------|------|-----------|------|------|
| 总覆盖率 | 62.87% | ≥40% | +22.87% | ✅ 已达标 |
| 核心技能覆盖率 | 见下 | ≥60% | — | ⚠ 部分达标 |
| 三贤者覆盖率 | 见下 | ≥50% | — | ✅ 已达标 |

### 核心技能细分

| 技能 | 基线 | v0.3.0目标 | 差距 | 行动 |
|------|------|-----------|------|------|
| email_skill | 16.96% | ≥60% | -43.04% | Sprint 2 优先补测试 |
| finance_skill | 14.46% | ≥60% | -45.54% | Sprint 2 优先补测试 |
| report_skill | 87.92% | ≥60% | +27.92% | ✅ 已达标 |

### 三贤者细分

| 模块 | 基线 | v0.3.0目标 | 差距 | 状态 |
|------|------|-----------|------|------|
| strategist_brain | 84.12% | ≥50% | +34.12% | ✅ |
| executor_brain | 80.41% | ≥50% | +30.41% | ✅ |
| reflector_brain | 92.20% | ≥50% | +42.20% | ✅ |
| consensus_engine | 98.71% | ≥50% | +48.71% | ✅ |
| agent_loop | 65.94% | ≥50% | +15.94% | ✅ |

---

## 五、CI集成

覆盖率已集成到CI（`.github/workflows/python-ci.yml`，2026-06-19更新）：

```yaml
- name: Coverage report
  if: matrix.python-version == '3.11'
  run: |
    PYTHONPATH=. pytest --cov=opc_manager --cov=frontend \
      --cov-report=xml:coverage.xml --cov-report=term \
      --tb=no -q --timeout=10 \
      --ignore=tests/test_e2e_real.py \
      --ignore=tests/test_e2e_user_journeys.py \
      --ignore=tests/test_e2e_user_workflow.py \
      --ignore=tests/test_integration_e2e.py \
      --ignore=tests/test_wechat_e2e.py \
      -p no:cacheprovider || true

- name: Upload coverage artifact
  if: matrix.python-version == '3.11'
  uses: actions/upload-artifact@v4
  with:
    name: coverage-report
    path: coverage.xml
    retention-days: 14
```

**规则**:
- 覆盖率不阻断CI（仅记录，`|| true` 兜底）
- 仅在 Python 3.11 矩阵运行（节省CI时间）
- coverage.xml 作为 artifact 上传，保留14天
- 每次提交不允许覆盖率下降（人工检查）
- v0.3.0发布前需达到≥40%（**已达标 62.87%**）

---

## 六、改进计划

### 6.1 Sprint 1 改进

- [x] 建立基线（本文档）— 2026-06-19 完成
- [x] CI集成覆盖率报告 — 2026-06-19 完成

### 6.2 Sprint 2 改进

- [ ] **email_skill 补测试**：从 16.96% → ≥60%（高优先级）
- [ ] **finance_skill 补测试**：从 14.46% → ≥60%（高优先级）
- [ ] 三贤者并行化后补充测试（agent_loop.py 新增并行路径）
- [ ] IntentClassifier 三路分类测试覆盖
- [ ] task_lifecycle.py Consensus前置后补测试

### 6.3 Sprint 3 改进

- [ ] 根据用户反馈补充测试
- [ ] 评估零覆盖文件（api/events.py, cli.py）是否删除
- [ ] 达到v0.3.0覆盖率目标（总覆盖率已达标，核心技能待补）

---

## 七、基线健康度评估

### 7.1 优势

1. **总覆盖率 62.87% 远超目标**：基线健康，无需大规模补测试
2. **三贤者核心模块覆盖优秀**：consensus_engine 98.71%，reflector 92.20%
3. **零覆盖文件仅3个**：代码质量高，无大量未测试代码
4. **2949测试全绿**：测试套件稳定

### 7.2 风险

1. **email_skill/finance_skill 覆盖率严重不足**：核心技能但测试稀少，存在回归风险
2. **frontend 覆盖率 48.10%**：低于后端，UI测试待加强
3. **task_lifecycle 48.96%**：Sprint 2 Consensus前置改造的核心模块，需先补测试再重构

### 7.3 结论

基线覆盖率整体健康，v0.3.0的40%目标已达成。Sprint 2 的重点是：
1. 补充 email_skill/finance_skill 测试（核心技能保障）
2. 三贤者并行化改造时同步补充测试
3. task_lifecycle 改造前先补测试（测试先行原则）

---

> **注**: 本文档数据由 `_extract_coverage.py` 脚本从 `coverage.json` 提取，测量时间 2026-06-19T18:09:09。
