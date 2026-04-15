# OPC-Agents 测试策略与覆盖计划 v2.1

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v2.1.0 | 2026-04-14 | 测试专家 | 基于9个新场景和6种人格制定全面测试计划 | 待审核 |
| v2.0.0 | 2026-04-07 | 测试专家 | 初始版本，3场景基础测试 | 已审核 |

---

## 一、测试范围总览

### 1.1 新增测试维度

```
v2.0 测试范围（3场景）
├── 场景匹配测试
├── 工作流执行测试
└── 基础功能回归

v2.1 测试范围（9场景 + 6人格 + 飞轮）
├── 场景引擎测试（9个场景 × 4层深度）
│   ├── 意图识别准确率
│   ├── 工作流完整性
│   ├── 异常路径覆盖
│   └── 性能基准
├── 人格系统测试（6种变体 × 5个维度）
│   ├── 人格切换正确性
│   ├── 对话风格一致性
│   ├── 专业术语准确性
│   ├── 个性化效果
│   └── 边界情况
├── 业务类型检测测试
├── 飞轮机制测试
├── 外部集成测试
└── E2E端到端测试（6类用户完整旅程）
```

### 1.2 测试金字塔

```
                    /\
                   /  \        E2E Tests (10%)
                  /────\       - 6类用户完整旅程
                 /  集成  \     - 跨模块流程
                /   测试    \
               /────────────\    Integration Tests (20%)
              /   场景引擎    \   - API接口测试
             /   人格系统      \  - 数据库交互
            /   工作流引擎      \ - 外部API Mock
           /────────────────────\
          /                      \
         /       Unit Tests       \  (70%)
        /    - 场景匹配算法         \
       /     - 工作流步骤执行         \
      /      - 人格配置加载            \
     /       - 标签计算逻辑             \
    /──────────────────────────────────\
```

---

## 二、场景引擎测试用例

### 2.1 content_calendar（内容日历）测试

```python
class TestContentCalendarScenario:
    """内容日历规划场景测试"""
    
    def test_trigger_phrase_matching(self):
        """触发词匹配测试"""
        test_cases = [
            ("帮我规划下周的内容日历", True, 0.95),
            ("下周发什么", True, 0.90),
            ("选题建议", True, 0.85),
            ("今天天气不错", False, 0.05),
            ("写一份报告", False, 0.15),  # 不应匹配到此场景
        ]
        
        for input_text, expected_match, min_confidence in test_cases:
            result = scenario_engine.process(input_text, context)
            assert result.matched == expected_match
            if expected_match:
                assert result.confidence >= min_confidence
    
    def test_workflow_execution_normal(self):
        """正常工作流执行测试"""
        input_data = {
            "user_input": "帮我规划下周的小红书内容",
            "platforms": ["小红书", "抖音"],
            "time_range": "next_week",
            "preferences": ["时尚", "生活方式"]
        }
        
        result = scenario_engine.execute("content_calendar", input_data)
        
        assert result.status == "completed"
        assert len(result.deliverable["topics"]) >= 10  # 至少10个选题
        assert result.deliverable["calendar"] is not None
        assert result.execution_time < 30  # < 30秒
        
    def test_workflow_no_hotspot_fallback(self):
        """无热点数据时的降级处理"""
        # Mock: 热点API返回空
        with mock_hotspot_api_returning_empty():
            result = scenario_engine.execute("content_calendar", {...})
            
        assert result.status == "completed"
        assert "基于历史数据" in result.deliverable["note"]
        assert "建议手动补充" in result.suggestion
    
    def test_multi_platform_scheduling(self):
        """多平台排期逻辑测试"""
        input_data = {
            "platforms": ["小红书", "抖音", "B站", "公众号"],
            "posting_frequency": {
                "小红书": "daily",
                "抖音": "daily",
                "B站": "weekly",
                "公众号": "weekly"
            }
        }
        
        result = scenario_engine.execute("content_calendar", input_data)
        calendar = result.deliverable["calendar"]
        
        # 验证：小红书和抖音应该每天都有内容
        xiaohongshu_posts = [item for item in calendar if item.platform == "小红书"]
        douyin_posts = [item for item in calendar if item.platform == "抖音"]
        assert len(xiaohongshu_posts) >= 5  # 至少5天
        assert len(douyin_posts) >= 5
        
    def test_performance_benchmark(self):
        """性能基准测试"""
        import time
        
        start = time.time()
        for _ in range(100):
            scenario_engine.process("帮我规划下周的内容日历", context)
        avg_time = (time.time() - start) / 100
        
        assert avg_time < 0.5  # 平均响应时间 < 500ms
```

### 2.2 feedback_analysis（用户反馈分析）测试

```python
class TestFeedbackAnalysis:
    """用户反馈分析场景测试"""
    
    def test_sentiment_classification_accuracy(self):
        """情感分类准确率测试（目标 >90%）"""
        test_feedback = [
            ("这个功能太棒了！", "positive"),
            ("很好用，推荐给大家", "positive"),
            ("经常崩溃，很失望", "negative"),
            ("希望能增加导出功能", "suggestion"),
            ("还可以吧，一般般", "neutral"),
        ]
        
        correct = 0
        for text, expected_sentiment in test_feedback:
            result = sentiment_analyzer.classify(text)
            if result.sentiment == expected_sentiment:
                correct += 1
        
        accuracy = correct / len(test_feedback)
        assert accuracy >= 0.90
    
    def test_topic_clustering_quality(self):
        """主题聚类质量测试"""
        feedback_batch = [
            "导出功能太慢了",
            "导出PDF经常失败",
            "希望能支持Excel导出",
            "界面太丑了",
            "颜色搭配不合理",
            "字体太小看不清",
            "价格太贵了",
            "学生党负担不起",
            "有没有优惠活动",
        ]
        
        clusters = topic_clusterer.cluster(feedback_batch)
        
        # 预期聚类：
        # Cluster 1: 导出相关 (3条)
        # Cluster 2: UI/设计相关 (3条)
        # Cluster 3: 价格相关 (3条)
        
        assert len(clusters) == 3
        for cluster in clusters:
            assert len(cluster.items) >= 2  # 每个簇至少2条
    
    def test_priority_scoring_rice(self):
        """RICE优先级评分测试"""
        features = [
            {"name": "导出优化", "reach": 100, "impact": 5, "confidence": 0.8, "effort": 3},
            {"name": "暗色模式", "reach": 50, "impact": 3, "confidence": 0.9, "effort": 2},
            {"name": "多语言", "reach": 20, "impact": 4, "confidence": 0.7, "effort": 5},
        ]
        
        scored = rice_scorer.calculate(features)
        
        # RICE = (R × I × C) / E
        # 导出优化: (100×5×0.8)/3 = 133.3
        # 暗色模式: (50×3×0.9)/2 = 67.5
        # 多语言: (20×4×0.7)/5 = 11.2
        
        assert scored[0].score > scored[1].score > scored[2].score
```

---

## 三、人格系统测试

### 3.1 人格切换测试矩阵

| 测试项 | 内容型 | 产品型 | AI工具型 | 咨询型 | 电商型 | 创意型 |
|--------|-------|-------|---------|-------|-------|-------|
| 触发词识别 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 风格一致性 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 术语准确性 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| Emoji使用 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 对话节奏 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

### 3.2 关键测试用例

```python
class TestPersonaSwitching:
    """人格切换测试"""
    
    def test_auto_detection_accuracy(self):
        """自动检测准确率（目标 >85%）"""
        test_cases = [
            ("帮我规划小红书内容", "content_creator"),
            ("帮我把课程打包上架", "digital_product"),
            ("分析一下用户反馈", "ai_tool_builder"),
            ("起草一份咨询方案", "consultant"),
            ("分析上周销售数据", "ecommerce"),
            ("整理设计项目交付物", "creative_work"),
        ]
        
        correct = 0
        for input_text, expected_type in test_cases:
            detected = type_detector.detect(input_text)
            if detected == expected_type:
                correct += 1
        
        accuracy = correct / len(test_cases)
        assert accuracy >= 0.85
    
    def test_manual_override(self):
        """手动切换测试"""
        # 用户明确指定类型
        result = persona_manager.get_persona(
            user_id="test_user",
            explicit_type="ecommerce",
            context={"input": "随便聊聊"}
        )
        
        assert result.variant_id == "ecommerce"
        assert "GMV" in result.greeting or "老板好" in result.greeting
    
    def test_style_consistency(self):
        """风格一致性测试（同一会话中不突变）"""
        conversation = [
            "帮我选品",
            "这个怎么样",
            "再看看别的",
        ]
        
        personas = []
        for msg in conversation:
            persona = persona_manager.get_persona(
                user_id="test_user",
                context={"input": msg, "history": conversation[:conversation.index(msg)]}
            )
            personas.append(persona.variant_id)
        
        # 所有消息应返回同一人格（除非用户主动切换）
        assert len(set(personas)) == 1
    
    def test_vocabulary_domain_specificity(self):
        """领域术语测试"""
        domain_terms = {
            "content_creator": ["种草", "爆款", "涨粉"],
            "digital_product": ["LTV", "转化率", "漏斗"],
            "ai_tool_builder": ["API", "Latency", "Scalability"],
            "consultant": ["痛点", "ROI", "KPI"],
            "ecommerce": ["GMV", "客单价", "动销率"],
            "creative_work": ["Moodboard", "Typography", "Visual Hierarchy"],
        }
        
        for biz_type, terms in domain_terms.items():
            persona = persona_manager.load_persona(biz_type)
            response = persona.generate_response("测试")
            
            # 应包含至少一个领域术语（或确认该场景不需要）
            has_domain_term = any(term in response for term in terms)
            # 注意：不是每句回复都必须有术语，但整体风格应匹配
```

---

## 四、E2E端到端测试（6类用户旅程）

### 4.1 测试场景定义

```python
class TestEndToEndJourneys:
    """6类用户的完整使用旅程测试"""
    
    @pytest.mark.e2e_content_creator
    def test_journey_content_creator_new_user(self):
        """
        内容创作者 - 新用户首次使用 journey
        
        Steps:
        1. 注册/登录 → 选择业务类型（内容创作）
        2. 系统激活内容型人格 + 3个核心场景
        3. 用户首次对话："帮我规划下周内容"
        4. 系统引导完善画像（平台/粉丝量/领域）
        5. 生成内容日历
        6. 用户调整后确认
        7. 系统记录偏好
        8. 推送每日热点（次日早9点）
        """
        # 实现完整旅程验证...
        pass
    
    @pytest.mark.e2e_ecommerce
    def test_journey_ecommerce_power_user(self):
        """
        电商运营者 - 重度用户飞轮 journey
        
        Steps:
        1. 用户已使用30天+，活跃度高
        2. 触发飞轮升级（单→双类型）
        3. 系统推荐：电商+内容组合
        4. 用户解锁跨类型工作流
        5. 执行"电商数据分析→内容选题"联动
        6. 查看飞轮健康仪表盘
        7. 达成"全生态飞轮"成就
        """
        pass
    
    # ... 其他4类用户旅程测试
```

### 4.2 性能基准测试

| 场景 | P50响应时间 | P95响应时间 | P99响应时间 | 错误率 |
|------|-----------|-----------|-----------|--------|
| 场景识别 | 200ms | 400ms | 800ms | <0.1% |
| 工作流启动 | 500ms | 1s | 2s | <0.5% |
| 完整工作流执行 | 10s | 30s | 60s | <1% |
| 人格切换 | 100ms | 200ms | 400ms | <0.01% |

---

## 五、自动化测试基础设施

### 5.1 CI/CD Pipeline

```yaml
# .github/workflows/test-v21.yml

name: OPC-Agents V2.1 Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=opc_manager --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
  
  integration-tests:
    needs: unit-tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: opc_agents_test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        run: pytest tests/integration/ -v --db-url=postgresql://test:test@localhost/opc_agents_test
  
  e2e-scenarios:
    needs: integration-tests
    runs-on: ubuntu-latest
    strategy:
      matrix:
        business-type: [content_creator, digital_product, ai_tool_builder, 
                        consultant, ecommerce, creative_work]
    steps:
      - uses: actions/checkout@v3
      - name: Run E2E tests for ${{ matrix.business-type }}
        run: pytest tests/e2e/ -v -k "${{ matrix.business-type }}"
  
  performance-benchmark:
    needs: e2e-scenarios
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run performance tests
        run: pytest tests/performance/ -v --benchmark-json=benchmark.json
      - name: Check performance regression
        run: python scripts/check_performance_regression.py benchmark.json
```

---

## 六、测试覆盖率目标

| 模块 | 目标覆盖率 | 当前覆盖率 | 差距 |
|------|-----------|-----------|------|
| scenario_engine | 90% | 75% | +15% |
| persona_system | 85% | 60% | +25% |
| workflow_engine | 88% | 80% | +8% |
| tag_system | 85% | 70% | +15% |
| data_sources | 80% | 40% | +40% |
| **Overall** | **87%** | **72%** | **+15%** |

---

## 七、后续行动项

- [ ] 完成9个新场景的单元测试编写
- [ ] 搭建外部API Mock服务
- [ ] 建立6种人格的回复语料库用于对比测试
- [ ] 实现性能基准自动化检测
- [ ] 设置E2E测试环境（含真实数据脱敏）

---

**文档状态**：✅ 初稿完成 | ⏳ 待独立开发者评审可实现性 | ⏳ 待多角色共识

**下一步**：开始实现Phase 1 MVP的核心测试用例
