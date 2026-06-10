## OPC-Agents v0.2.0 前端架构审查与测试方案制定

### 项目背景
OPC-Agents 是一个 AI 驱动的「一人公司」助手系统，使用 Streamlit (Python) 构建前端。
当前前端存在严重的架构问题，导致用户报告了大量 bug。

### 已知问题清单（按严重度排序）
1. NameError 系列性爆发：_render_deliverables_list / _render_audit_log_page / _show_onboarding_overlay / _render_quick_undo_button 等 4 个函数因定义在调用点之后而报错
2. 缺失导入：_render_quick_undo_button、_get_phase_from_event 从 shared.py 导入但遗漏
3. 页面路由崩溃：语言切换后 if/elif 链用翻译值匹配导致所有非中文页面空白
4. i18n 不完整：1913 行 app.py 中有 609 处硬编码中文字符串，marketplace_page.py 有 50+ 处硬编码日文/中文混杂
5. 两套语言系统互不联动：settings 页有独立语言选择器(仅中英)，sidebar 有另一套(含日语)
6. Streamlit 多页面干扰：pages/ 目录被自动检测为多页应用，显示英文链接
7. app.py 巨型单体文件：1913 行，17 个函数混在一起，if/elif 路由链 6 层

### 当前架构数据
- app.py: 1913 行, 17 个函数, 609 处硬编码字符串
- components/: 8 个组件文件 (shared.py 1023行, undo_panel.py 1173行, timeline_view.py 1140行)
- page_modules/: 3 个页面文件 (dashboard 862行, settings 675行, marketplace 543行)
- i18n.py: 约 370 个翻译键/语言 (zh_CN/en_US/ja_JP)
- 测试: 约 1700+ 测试用例

### 需要输出

**Architect 角色请完成：**
1. 深入分析当前架构的所有结构性问题（不限于已知 bug）
2. 提出架构整理方案文档（包含目标目录结构、模块职责划分、依赖关系图）
3. 给出分阶段实施计划（每阶段的风险评估和回滚方案）
4. 评估重构对现有功能的影响范围

**Tester 角色请完成：**
1. 分析当前测试覆盖的盲区（哪些功能没有测试？哪些场景没覆盖？）
2. 提出优化后的测试方案（需要新增哪些测试？用什么策略？）
3. 设计一套可以防止 NameError / 缺失导入 / 硬编码字符串类 bug 回归的测试机制
4. 提出浏览器端自动化测试方案（如果适用）

请用中文输出完整方案文档。
