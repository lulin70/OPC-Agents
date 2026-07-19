# OPC-Agents v0.5.0 Release Notes

> **发布日期**: 2026-07-19 | **版本**: v0.5.0 (Beta) | **代号**: 用户验证纪元
> **GitHub Release**: [v0.5.0](https://github.com/lulin70/OPC-Agents/releases/tag/v0.5.0)
> **PyPI**: [opc-agents==0.5.0](https://pypi.org/project/opc-agents/0.5.0/)

---

## 一、版本主题：从"质量巩固"转向"用户验证"

v0.5.0 是 OPC-Agents 项目从工程优化阶段转向真实用户验证阶段的关键 MINOR 版本。v0.4.0 完成了"产品功能闭环"（199/200 E2E 通过、83% 覆盖率、0 mypy 错误），但 `ASSESSMENT_INITIAL_VISION_v0.4.0.md` 评估显示项目"达到了技术初心，但未达到产品初心"——0 真实用户、5 大商业指标 0 数据、产品定位内在矛盾未解决。

v0.5.0 聚焦三大支柱：**种子用户验证基础设施 + 产品定位矛盾解决 + 运营基础设施**，为 v0.6.0+ 的 PMF 验证做好数据采集、反馈渠道、官网部署的完整准备。

---

## 二、4 个 OKR 完成情况

### OKR-1: 种子用户验证基础设施

| KR | 完成情况 |
|----|---------|
| KR1.1 5 大商业指标采集埋点 | ✅ 完成（metrics_collector.py 906 行，6 个 record_xxx 方法） |
| KR1.2 3 大体验指标问卷 API | ✅ 完成（feedback API 7 个端点 + 9 个 Pydantic 模型） |
| KR1.3 用户反馈评分 UI | ✅ 完成（feedback_dialog.py 211 行，5 星 + 分类 + 文字框） |
| KR1.4 数据采集同意弹窗 | ✅ 完成（consent_dialog.py 192 行，4 个复选框 + 0600 权限） |
| KR1.5 LLM 后端多路径稳定 | ✅ 完成（llm_backend_manager.py 862 行，三路 fallback + 健康检查） |

### OKR-2: 商业指标数据采集

| KR | 完成情况 |
|----|---------|
| KR2.1 DB 迁移 v8 | ✅ 完成（v8_metrics.py 429 行，5 张表 + 20 索引 + 6 视图 + 5 脱敏视图） |
| KR2.2 数据采集埋点架构 ADR-004 | ✅ 完成（476 行） |
| KR2.3 MetricsCollector 技术设计 | ✅ 完成（708 行） |
| KR2.4 反馈 API 完整设计 | ✅ 完成（993 行） |

### OKR-3: 产品定位矛盾解决

| KR | 完成情况 |
|----|---------|
| KR3.1 POSITIONING_RESOLUTION.md | ✅ 完成（518 行，5-Why 根因 + 三层解决方案） |
| KR3.2 PRD_V4.1.md | ✅ 完成（821 行，5 P0 技能 + 解冻路径 + §1.5 当前阶段） |
| KR3.3 SKILL_FREEZE_LIST 更新指引 | ✅ 完成（基于种子用户反馈的分阶段解冻） |

### OKR-4: 运营基础设施

| KR | 完成情况 |
|----|---------|
| KR4.1 官网部署 | ✅ 完成（nginx 配置 + 静态文件 + 部署脚本 + GitHub workflow） |
| KR4.2 安装流程可走通 | ✅ 完成（非技术用户图文版安装指南 1193 行） |
| KR4.3 真实生产环境架构 | ✅ 完成（DEPLOYMENT_ARCHITECTURE.md 600 行 + H1-H8 硬约束） |
| KR4.4 用户反馈渠道 | ✅ 完成（应用内反馈 API + GitHub Issues + 邮箱） |

---

## 三、新增功能与组件

### 3.1 核心代码模块（4 个，~8000 行）

| 模块 | 文件 | 行数 | 覆盖率 | 测试数 |
|------|------|------|--------|--------|
| MetricsCollector | `opc_manager/metrics_collector.py` | 906+扩展 | 87% | 50 |
| LLMBackendManager | `opc_manager/llm_backend_manager.py` | 862 | 84% | 54 |
| 反馈 API | `opc_manager/api_server.py` + `api/` | 770 | 83% | 19 |
| UI 组件 | `frontend/components/{feedback,consent,install}*.py` | 526 | 97% | 51 |

**总计 174 个测试全部通过，核心模块覆盖率 86%**（超过 80% 目标）。

### 3.2 DB 迁移

- `opc_manager/migrations/v8_metrics.py`（429 行）
- 5 张新表：`metrics_activation` / `metrics_upgrade` / `metrics_flywheel` / `metrics_payment` / `metrics_experience`
- 20 个索引、1 个触发器、6 个汇总视图、5 个脱敏视图
- 事务性迁移（BEGIN + 失败 ROLLBACK + 备份恢复）

### 3.3 官网部署（12 个文件，2853 行）

| 类别 | 文件 | 说明 |
|------|------|------|
| nginx 配置 | `deploy/nginx/nginx.conf` + 3 个 sites-available | 三 server 块（官网/网关/默认），H7 硬约束强制 |
| 官网静态文件 | `website/index.html` + `styles.css` + `404.html` | Morandi 配色，响应式，无 emoji |
| 部署脚本 | `deploy/scripts/deploy-website.sh` + `healthcheck.sh` | rsync + nginx reload + 5 端点健康检查 + 企业微信告警 |
| GitHub workflow | `.github/workflows/website-deploy.yml` | push 触发自动部署 + 失败创建 issue |

### 3.4 文档（11 个，~7000 行）

| 文档 | 行数 | 用途 |
|------|------|------|
| `docs/product-manager/PRD_V4.1.md` | 821 | PRD 升级版（5 P0 技能 + 解冻路径） |
| `docs/spec/POSITIONING_RESOLUTION.md` | 518 | 定位矛盾解决方案 |
| `docs/architecture/ADR-004-metrics-collection-design.md` | 476 | 埋点架构决策 |
| `docs/architecture/ADR-005-llm-backend-fallback-design.md` | 558 | LLM fallback 架构决策 |
| `docs/architecture/DEPLOYMENT_ARCHITECTURE.md` | 600 | 部署架构设计 |
| `docs/architecture/TECH_DESIGN_metrics_implementation.md` | 708 | MetricsCollector 技术设计 |
| `docs/architecture/API_DESIGN_feedback_and_metrics.md` | 993 | 反馈 API 设计 |
| `docs/architecture/DDL_metrics_v8.md` | 700 | 完整 DDL + 迁移脚本 |
| `docs/architecture/UI_DESIGN_v0.5.0.md` | 700 | UI 原型设计 |
| `docs/architecture/SECURITY_REVIEW_v0.5.0.md` | 551 | 安全审查报告 |
| `tests/uat/UAT_TEST_PLAN_v0.5.0.md` | 595 | UAT 测试计划 |
| `tests/test_cases/TEST_CASES_v0.5.0.md` | 614 | 144 个测试用例 |
| `docs/guides/INSTALL_GUIDE_NON_TECHNICAL.md` | 1193 | 非技术用户图文版安装指南 |

---

## 四、安全与合规

### 4.1 法律法规合规

- 《个人信息保护法》6 法条全覆盖
- GDPR 6 条款（如有海外用户）
- 《数据安全法》2 法条
- 《网络安全法》2 法条

### 4.2 STRIDE 威胁建模

6 项全覆盖：Spoofing / Tampering / Repudiation / Information Disclosure / DoS / EoP

### 4.3 Prompt Injection 防护

26 模式检测清单（21 现有 + 5 新增反馈专用），所有反馈 API 端点强制检测。

### 4.4 数据安全

- 用户业务数据本地 SQLite，云端不接收不存储
- 网关日志仅记录元数据，禁止记录请求体与响应体
- API Key 通过环境变量注入，禁止明文写入任何文件
- 数据采集需用户明确同意（4 个复选框，前 3 个默认 True，反馈内容默认 False）

---

## 五、测试结果

### 5.1 单元 + 集成测试

```
4338 passed, 77 skipped, 0 failed in 75.27s
```

### 5.2 E2E 测试

| 测试类别 | 通过 | 失败 | 备注 |
|---------|------|------|------|
| 用户旅程 | 24/24 | 0 | 1.95s |
| 用户工作流 | 8/8 | 0 | - |
| 集成 E2E | 26/26 | 0 | - |
| Docker 部署 | 37/37 | 0 | - |
| 启动脚本 | 31/31 | 0 | - |
| 真实搜索+LLM | 22/24 | 2 | 环境问题（网络超时 + Ollama 未启动） |
| Playwright UI | 21/21 | 0 | 186.45s |
| **总计** | **169/171** | **2** | **99% 通过率** |

### 5.3 覆盖率

| 模块 | 覆盖率 |
|------|--------|
| MetricsCollector | 87% |
| LLMBackendManager | 84% |
| 反馈 API | 83% |
| UI 组件 | 97% |
| **核心模块总计** | **86%**（超过 80% 目标） |

### 5.4 质量门禁

| 维度 | 状态 |
|------|------|
| ruff | ✅ All checks passed |
| mypy | ✅ 0 errors |
| bandit | ✅ No issues |
| radon cc | ✅ 无 D+ 函数 |
| 版本一致性 | ✅ 18 处版本号同步 |

---

## 六、硬约束遵循情况

| 约束 | 遵循情况 |
|------|---------|
| H1 基础版仅在用户本地运行 | ✅ nginx 默认 server 仅服务静态文件，禁止代理应用容器 |
| H2 用户不持有 LLM API Key | ✅ LLMBackendManager 通过网关代理，用户仅持 License Key |
| H3 基础版通过 relay_client 连接网关 | ✅ 架构文档明确 |
| H4 基础版不含语音/图片扫描 | ✅ 代码层禁止调用 ASR/TTS/OCR 路由 |
| H5 网关地址统一 | ✅ gateway.promiselink.cn |
| H6 47.116.219.15 服务器职责 | ✅ 仅部署网关 + 官网 + 支撑服务 |
| H7 nginx 默认 server 策略 | ✅ default.conf 仅服务静态文件，无 proxy_pass |
| H8 API keys 不明文写入 | ✅ 全部通过环境变量注入 |

---

## 七、已知问题与限制

### 7.1 环境相关（非代码回归）

- `test_e2e_real.py::TestRealSearch::test_english_search_returns_results` — 网络搜索超时（ConnectTimeout）
- `test_e2e_real.py::TestRealFullPipeline::test_chinese_content_generation_real` — Ollama 未启动 + 搜索超时

### 7.2 推迟到 v0.6.0+

- opc_manager 99 文件真子包化（P2）
- v4.1 外部技能扩展完整化（P1）
- SEC-5-02 MCP HTTPS 强制（P1）
- SEC-5-06 外部技能审计完整（P1）
- 飞轮数据闭环真实流转（P3）

### 7.3 待种子用户验证（W9-W12）

- 5-10 名种子用户招募
- 6 大用户类型 PMF 早期信号
- 5 大商业指标 + 3 大体验指标首次数据
- task_manager / crm 解冻决策

---

## 八、升级指南

### 8.1 PyPI 安装

```bash
pip install --upgrade opc-agents==0.5.0
opc-agents
```

### 8.2 Docker

```bash
docker pull ghcr.io/lulin70/opc-agents:0.5.0
docker run -d --name opc-agents -p 8000:8000 -v ~/.opc-agents:/root/.opc-agents ghcr.io/lulin70/opc-agents:0.5.0
```

### 8.3 源码

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
git checkout v0.5.0
pip install -r requirements.txt
./scripts/start.sh
```

### 8.4 非技术用户

请阅读 [INSTALL_GUIDE_NON_TECHNICAL.md](../guides/INSTALL_GUIDE_NON_TECHNICAL.md)（图文版，30 分钟完成安装）。

---

## 九、下一步（W9-W12）

| 周次 | 主要工作 |
|------|---------|
| W9 | 种子用户招募 + 安装 + 首日使用 |
| W10 | 1 周试用中期回顾 + 深度访谈 |
| W11 | 2 周试用结束 + PMF 信号初步判断 |
| W12 | v0.5.0 终期回顾 + UAT 报告 + v0.6.0 路线图 |

详见 [SEED_USER_VALIDATION_PLAN.md](../spec/SEED_USER_VALIDATION_PLAN.md)。

---

## 十、致谢

感谢 DevSquad V4.1.0 7-Role 共识评估方法论的支持，以及所有为 v0.5.0 贡献的种子用户（即将招募）。

---

## 十一、相关文档

- [ROADMAP_v0.5.0.md](../ROADMAP_v0.5.0.md) — 完整路线图
- [ASSESSMENT_INITIAL_VISION_v0.4.0.md](../assessments/ASSESSMENT_INITIAL_VISION_v0.4.0.md) — v0.4.0 评估
- [POSITIONING_RESOLUTION.md](../spec/POSITIONING_RESOLUTION.md) — 定位矛盾解决
- [DEPLOYMENT_ARCHITECTURE.md](../architecture/DEPLOYMENT_ARCHITECTURE.md) — 部署架构
- [INSTALL_GUIDE_NON_TECHNICAL.md](../guides/INSTALL_GUIDE_NON_TECHNICAL.md) — 非技术用户安装指南

---

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.5.0 | 2026-07-19 | 初始版本，用户验证纪元 |
