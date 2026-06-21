# 技能冻结清单

> **文档状态**: Sprint 1 产出
> **版本**: v0.3.0
> **日期**: 2026-06-19
> **负责角色**: PM
> **任务ID**: S1-T2
> **依据**: [CORE_SKILLS_ACCEPTANCE.md](CORE_SKILLS_ACCEPTANCE.md)

---

## 〇、冻结原则

1. **不删除代码**: 冻结技能代码保留，仅标记 `[FROZEN v0.3.0]`
2. **不主动维护**: 冻结技能不接受新功能、不优化性能
3. **UI隐藏**: 技能市场不显示冻结技能
4. **保留可活性**: 满足复活条件时可解冻
5. **依赖安全**: 冻结前确认无核心技能依赖被破坏

---

## 一、核心技能（保留，不冻结）

| 技能 | 文件 | 状态 | 说明 |
|------|------|------|------|
| email | `email_skill.py` | ✅ 活跃 | "说一句话发邮件" |
| finance | `finance_skill.py` | ✅ 活跃 | "说一句话记账" |
| report | `report_skill.py` | ✅ 活跃 | "说一句话生成报告" |

---

## 二、半冻结技能（代码保留，被核心技能依赖）

> 这些技能被核心技能（email/report）依赖，不能完全冻结。
> 标记为"半冻结"：被引用的方法保持可用，其余方法不维护。

| 技能 | 文件 | 依赖方 | 被引用方法 | 冻结状态 |
|------|------|--------|-----------|---------|
| crm | `crm_skill.py` | email_skill, report_skill | `get_customer`, `get_customer_stats`, `get_silent_customers` | 🔶 半冻结 |
| task | `task_skill.py` | report_skill | `list_tasks` | 🔶 半冻结 |

### 半冻结规则

- 被引用方法（上表）保持可用且有测试覆盖
- 其余方法标记 `# [FROZEN v0.3.0]` 但不删除
- 不新增功能，不优化非被引用方法
- 如核心技能重构去除依赖，可转为完全冻结

---

## 三、完全冻结技能（11个 → 实际9个完全冻结）

> 以下技能无核心技能依赖，可完全冻结。

| # | 技能 | 文件 | 当前功能 | 冻结理由 | 复活条件 |
|---|------|------|---------|---------|---------|
| 1 | calendar | `calendar_skill.py` | 日历事件管理 | 非一人公司高频需求 | 用户反馈需要日程管理 |
| 2 | competitor | `competitor_skill.py` | 竞品分析 | 非高频，价值未验证 | 用户反馈需要竞品监控 |
| 3 | dashboard | `dashboard_skill.py` | 仪表盘 | 依赖crm/task，但本身非核心 | 用户反馈需要可视化 |
| 4 | invoice | `invoice_skill.py` | 发票管理 | 依赖tax_reminder，低频 | 用户反馈需要开票 |
| 5 | knowledge | `knowledge_skill.py` | 知识库 | 非高频，MemoryBridge已覆盖核心 | 用户反馈需要知识管理 |
| 6 | pricing | `pricing_skill.py` | 定价策略 | 非高频，价值未验证 | 用户反馈需要定价建议 |
| 7 | proposal | `proposal_skill.py` | 方案生成 | 依赖invoice，低频 | 用户反馈需要方案撰写 |
| 8 | social | `social_skill.py` | 社交媒体 | 非一人公司核心需求 | 用户反馈需要社媒管理 |
| 9 | tax_reminder | `tax_reminder_skill.py` | 税务提醒 | 低频，被invoice依赖 | 用户反馈需要税务提醒 |

### 冻结技能间的依赖链

```
invoice_skill → tax_reminder_skill (两者都冻结，依赖链内部自洽)
proposal_skill → invoice_skill (两者都冻结，依赖链内部自洽)
task_skill → calendar_skill (task半冻结，calendar完全冻结)
  ⚠️ 注意: task_skill:43 from calendar_skill import add_event
  → task_skill半冻结，其list_tasks方法不依赖calendar，安全
dashboard_skill → crm_skill + task_skill (dashboard完全冻结，依赖不影响)
```

---

## 四、依赖关系图

```
核心技能（保留）:
  email_skill ──→ crm_skill.get_customer (半冻结)
  report_skill ──→ crm_skill.get_customer_stats, get_silent_customers (半冻结)
  report_skill ──→ task_skill.list_tasks (半冻结)
  report_skill ──→ finance_skill.get_monthly_report, get_trend (核心)

冻结技能（内部依赖自洽）:
  invoice_skill → tax_reminder_skill (都冻结)
  proposal_skill → invoice_skill (都冻结)
  dashboard_skill → crm_skill + task_skill (dashboard冻结，依赖不破坏)
```

---

## 五、冻结执行方案（S1-T3）

### 5.1 完全冻结技能（9个）处理

对以下9个文件，在文件顶部添加冻结标记：

```python
"""[FROZEN v0.3.0] This skill is frozen and not actively maintained.

Frozen on: 2026-06-19
Reason: v0.3.0 product focus contraction (13→3 core skills)
Revival: See docs/spec/SKILL_FREEZE_LIST.md for revival conditions

Original docstring:
<原docstring>
"""
```

文件清单:
1. `calendar_skill.py`
2. `competitor_skill.py`
3. `dashboard_skill.py`
4. `invoice_skill.py`
5. `knowledge_skill.py`
6. `pricing_skill.py`
7. `proposal_skill.py`
8. `social_skill.py`
9. `tax_reminder_skill.py`

### 5.2 半冻结技能（2个）处理

对以下2个文件，在文件顶部添加半冻结标记，并标注被引用方法：

```python
"""[SEMI-FROZEN v0.3.0] Partially frozen — only referenced methods maintained.

Frozen on: 2026-06-19
Maintained methods (referenced by core skills):
  - get_customer (referenced by email_skill)
  - get_customer_stats (referenced by report_skill)
  - get_silent_customers (referenced by report_skill)
Other methods are frozen and not actively maintained.
Revival: See docs/spec/SKILL_FREEZE_LIST.md
"""
```

文件清单:
1. `crm_skill.py` — 维护 `get_customer`, `get_customer_stats`, `get_silent_customers`
2. `task_skill.py` — 维护 `list_tasks`

### 5.3 skill_registry.py 处理

在 `skill_registry.py` 中为冻结技能添加 `frozen=True` 标记：

```python
# 完全冻结
SkillMeta(id="calendar", ..., frozen=True, frozen_date="2026-06-19"),
SkillMeta(id="competitor", ..., frozen=True, frozen_date="2026-06-19"),
# ... 其余9个

# 半冻结
SkillMeta(id="crm", ..., frozen="semi", frozen_date="2026-06-19"),
SkillMeta(id="task", ..., frozen="semi", frozen_date="2026-06-19"),
```

### 5.4 技能市场UI处理

在技能市场页面过滤冻结技能：

```python
# frontend/page_modules/_marketplace_page.py
active_skills = [s for s in all_skills if not s.get("frozen")]
```

### 5.5 skill_executors.py 处理

`skill_executors.py` 中引用了所有技能的 `execute_goal`。冻结后：
- 完全冻结技能的 `execute_goal` 调用保留（不删除），但添加日志警告
- 半冻结技能的 `execute_goal` 正常工作
- 不影响核心3技能的执行

---

## 六、复活条件

| 技能 | 复活条件 | 复活优先级 |
|------|---------|-----------|
| calendar | ≥2个用户反馈需要日程管理 | 中 |
| competitor | ≥2个用户反馈需要竞品监控 | 低 |
| dashboard | ≥2个用户反馈需要可视化仪表盘 | 中 |
| invoice | ≥2个用户反馈需要开票功能 | 低 |
| knowledge | ≥2个用户反馈需要知识管理 | 低 |
| pricing | ≥2个用户反馈需要定价建议 | 低 |
| proposal | ≥2个用户反馈需要方案撰写 | 低 |
| social | ≥2个用户反馈需要社媒管理 | 低 |
| tax_reminder | ≥2个用户反馈需要税务提醒 | 低 |

**复活流程**:
1. PM 确认满足复活条件
2. 移除 `[FROZEN]` 标记
3. 更新 skill_registry `frozen=False`
4. 技能市场重新显示
5. 补充测试覆盖

---

## 七、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 冻结技能被隐藏引用导致import错误 | 低 | 高 | S1-T3前已grep依赖，确认无破坏 |
| 半冻结技能被引用方法有bug | 中 | 中 | S1-T5 E2E测试覆盖核心路径 |
| 用户反馈需要冻结技能 | 中 | 低 | 复活流程明确，可快速解冻 |

---

## 八、验收标准

- [ ] 9个完全冻结技能文件有 `[FROZEN v0.3.0]` 标记
- [ ] 2个半冻结技能文件有 `[SEMI-FROZEN v0.3.0]` 标记
- [ ] skill_registry.py 中冻结标记生效
- [ ] 技能市场UI不显示完全冻结技能
- [ ] 半冻结技能的被引用方法仍可用
- [ ] 现有测试100%通过（冻结不破坏功能）
- [ ] PRD_V4.md 标记完成

---

> **下一步**: S1-T3 Coder 基于本清单执行代码冻结。
