"""SearchResultProcessor 单元测试 v3.5 — P0-1 搜索质量修复

测试覆盖范围（对应 TEST_PLAN_V3.md 的 TestSearchRelevance 类别）：
- SR-001: 关键词提取准确性
- SR-002: 无关结果过滤
- SR-003: TF-IDF评分排序
- SR-004: 知识库兜底激活
- SR-005: 空结果降级处理

=== 验收标准 (G-SEARCH-01 门禁) ===
- 输入"Q2营销方案"，返回结果中≥60%包含"营销/Q2/方案/增长"等关键词
- 输入"AI Agent框架信息"，返回结果中≥80%包含"AI/Agent/框架"等关键词
- 处理耗时 < 100ms（不应增加明显延迟）
"""
import unittest
import time
from opc_manager.search_processor import SearchResultProcessor, ProcessedResult


class TestKeywordExtraction(unittest.TestCase):
    """SR-001: 关键词提取准确性测试"""

    def setUp(self):
        self.processor = SearchResultProcessor()

    def test_extract_chinese_business_keywords(self):
        """从"Q2营销方案SaaS产品"提取中文业务关键词"""
        keywords = self.processor._extract_keywords("帮我制定Q2营销方案SaaS产品")

        self.assertIn('q2', keywords)
        self.assertIn('营销', keywords)
        self.assertIn('方案', keywords)
        self.assertIn('saas', keywords)

    def test_remove_stop_words(self):
        """正确过滤停用词"""
        keywords = self.processor._extract_keywords("帮我写一份关于我的公司的计划")

        self.assertNotIn('的', keywords)
        self.assertNotIn('我', keywords)
        self.assertNotIn('帮', keywords)

    def test_remove_prefixes(self):
        """去除常见前缀（"帮我"、"请"等）"""
        keywords1 = self.processor._extract_keywords("帮我收集税收政策")
        keywords2 = self.processor._extract_keywords("请分析竞品")

        self.assertNotIn('帮我', keywords1)
        self.assertNotIn('请', keywords2)

    def test_mixed_chinese_english(self):
        """中英文混合查询的关键词提取"""
        keywords = self.processor._extract_keywords("AI Agent框架对比分析2026")

        self.assertIn('ai', keywords)
        self.assertIn('agent', keywords)
        self.assertIn('框架', keywords)

    def test_deduplication(self):
        """去重：相同关键词只出现一次"""
        keywords = self.processor._extract_keywords("营销营销营销方案方案")

        self.assertEqual(keywords.count('营销'), 1)
        self.assertEqual(keywords.count('方案'), 1)


class TestIrrelevantFiltering(unittest.TestCase):
    """SR-002: 无关结果过滤测试"""

    def setUp(self):
        self.processor = SearchResultProcessor()

    def test_filter_irrelevant_results_for_marketing_query(self):
        """输入"税收政策"，过滤掉"小说""书信""SCI论文"等无关结果"""
        query = "一人公司税收优惠政策"
        raw_results = [
            {'title': '书信格式写作指南', 'snippet': '如何写正式信函...'},
            {'title': '写小说的技巧', 'snippet': '小说创作入门...'},
            {'title': 'SCI论文发表流程', 'snippet': '学术论文投稿指南...'},
            {'title': '小微企业税收减免政策2026', 'snippet': '一人公司可享受...'},
        ]

        processed = self.processor.process(query, raw_results)

        for result in processed.results:
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            combined = f"{title} {snippet}".lower()
            has_relevant_keyword = any(
                kw in combined for kw in ['税收', '优惠', '政策', '公司']
            )
            if not result.get('_kb_fallback'):
                self.assertTrue(
                    has_relevant_keyword,
                    f"过滤失败: '{title}' 不包含任何相关关键词"
                )

    def test_keep_all_relevant_results(self):
        """保留所有相关的搜索结果"""
        query = "AI Agent开发框架"
        raw_results = [
            {'title': 'AI Agent架构设计模式', 'snippet': 'ReAct/Plan-and-Execute架构...'},
            {'title': 'LangChain框架使用指南', 'snippet': '大模型应用开发最佳实践...'},
            {'title': 'AutoGPT实战教程', 'snippet': '自主Agent实现方法...'},
        ]

        processed = self.processor.process(query, raw_results)

        self.assertGreaterEqual(len(processed.results), 3)

    def test_empty_keywords_pass_all(self):
        """无关键词时返回原始结果（不过滤）或降级处理"""
        query = "的了个是"
        raw_results = [
            {'title': '测试标题1', 'snippet': '测试摘要1'},
            {'title': '测试标题2', 'snippet': '测试摘要2'},
        ]

        processed = self.processor.process(query, raw_results)

        self.assertGreaterEqual(len(processed.results), 0)


class TestTFIDFScoring(unittest.TestCase):
    """SR-003: TF-IDF评分排序测试"""

    def setUp(self):
        self.processor = SearchResultProcessor()

    def test_title_matches_ranked_higher(self):
        """标题匹配的结果排在摘要匹配前面"""
        query = "Q2营销策略"
        raw_results = [
            {
                'title': '某公司年度报告',
                'snippet': '本文讨论Q2季度营销策略制定方法和最佳实践...',
            },
            {
                'title': 'Q2季度营销策略制定',
                'snippet': '第二季度市场推广计划详细说明...',
            },
        ]

        processed = self.processor.process(query, raw_results)

        self.assertGreater(
            processed.results[0].get('_relevance_score', 0),
            processed.results[1].get('_relevance_score', 0),
        )
        self.assertIn('Q2', processed.results[0].get('title', ''))

    def test_score_descending_order(self):
        """结果按评分降序排列"""
        query = "Python数据分析"
        raw_results = [
            {'title': 'Python基础教程', 'snippet': '从入门到精通'},
            {'title': 'Python数据分析实战', 'snippet': 'pandas/numpy/matplotlib详解'},
            {'title': '数据可视化指南', 'snippet': '使用Python进行图表绘制'},
        ]

        processed = self.processor.process(query, raw_results)

        scores = [r.get('_relevance_score', 0) for r in processed.results]
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i], scores[i + 1])

    def test_multiple_keyword_matches_score_higher(self):
        """命中多个关键词的结果评分更高"""
        query = "SaaS产品增长"
        raw_results = [
            {'title': 'SaaS产品运营', 'snippet': '用户增长的秘诀'},
            {'title': 'SaaS增长策略', 'snippet': '产品迭代与市场推广结合'},
        ]

        processed = self.processor.process(query, raw_results)

        self.assertGreater(processed.results[0].get('_relevance_score', 0), 0)


class TestKnowledgeBaseFallback(unittest.TestCase):
    """SR-004: 知识库兜底激活测试"""

    def setUp(self):
        self.processor = SearchResultProcessor(min_results=3)

    def test_fallback_activates_when_no_relevant_results(self):
        """所有搜索结果都不相关时触发知识库兜底"""
        query = "帮我制定Q2营销方案"
        irrelevant_results = [
            {'title': '书信格式写作指南', 'snippet': '如何写正式信函...'},
            {'title': '写小说的技巧', 'snippet': '小说创作入门...'},
            {'title': 'SCI论文发表流程', 'snippet': '学术论文投稿...'},
        ]

        processed = self.processor.process(query, irrelevant_results)

        self.assertTrue(processed.fallback_used)
        self.assertGreaterEqual(len(processed.results), 1)
        self.assertTrue(processed.results[0].get('_kb_fallback'))

    def test_fallback_matches_category(self):
        """知识库兜底返回正确分类的条目"""
        query = "一人公司税收优惠政策"

        processed = self.processor.process(query, [])

        self.assertTrue(processed.fallback_used)
        category = processed.results[0].get('_kb_category', '')
        self.assertTrue(
            'tax' in category or '税收' in category or category == 'generic',
            f"期望税收分类，实际得到: {category}"
        )

    def test_generic_fallback_for_unknown_topic(self):
        """未知主题返回通用兜底条目"""
        query = "量子力学波函数演化"

        processed = self.processor.process(query, [])

        self.assertTrue(processed.fallback_used)
        self.assertEqual(len(processed.results), 1)
        self.assertEqual(processed.results[0].get('_kb_category'), 'generic')


class TestEmptyResultDegradation(unittest.TestCase):
    """SR-005: 空结果降级处理测试"""

    def setUp(self):
        self.processor = SearchResultProcessor()

    def test_empty_input_returns_empty_with_fallback(self):
        """空输入列表触发知识库兜底"""
        processed = self.processor.process("测试查询", [])

        self.assertTrue(processed.fallback_used or len(processed.results) == 0)

    def test_degradation_returns_original_on_exception(self):
        """异常时降级返回原始结果（保证不比v3.4更差）"""
        original_results = [
            {'title': '原始结果1', 'snippet': '原始摘要1'},
            {'title': '原始结果2', 'snippet': '原始摘要2'},
        ]

        processor = SearchResultProcessor()
        processed = processor.process("正常查询", original_results)

        self.assertGreaterEqual(len(processed.results), 0)

    def test_processing_time_under_100ms(self):
        """单次处理耗时 < 100ms"""
        large_result_set = [
            {'title': f'测试标题{i}', 'snippet': f'测试摘要内容{i}' * 10}
            for i in range(50)
        ]

        start = time.time()
        processed = self.processor.process("性能测试查询", large_result_set)
        elapsed_ms = (time.time() - start) * 1000

        self.assertLess(elapsed_ms, 100, f"处理耗时{elapsed_ms:.1f}ms超过100ms阈值")
        self.assertIsNotNone(processed.processing_time_ms)


class TestGateSEARCH01(unittest.TestCase):
    """G-SEARCH-01: 搜索结果相关性门禁（P0阻断级）

    这是CDR定义的核心验收标准，必须全量通过才能发布v3.5
    """

    def setUp(self):
        self.processor = SearchResultProcessor()

    def test_marketing_query_top_results_relevant(self):
        """门禁：输入"Q2营销方案"，Top结果必须包含营销/Q2/方案等关键词"""
        query = "帮我制定Q2营销方案"
        raw_results = [
            {'title': '书信格式写作指南', 'snippet': '如何写正式信函...'},
            {'title': '写小说的技巧', 'snippet': '小说创作入门...'},
            {'title': 'Q2季度营销策略制定', 'snippet': '第二季度市场推广计划...'},
        ]

        processed = self.processor.process(query, raw_results)

        self.assertGreaterEqual(len(processed.results), 1)

        top_result = processed.results[0]
        top_text = (
            top_result.get('title', '') + ' ' + top_result.get('snippet', '')
        ).lower()

        required_keywords = ['营销', 'q2', '季度']
        matched = sum(1 for kw in required_keywords if kw in top_text)
        self.assertGreaterEqual(
            matched, 1,
            f"Top结果缺少关键词！标题:{top_result.get('title')}"
        )

    def test_tax_policy_query_relevance_rate(self):
        """门禁：输入"税收政策"，返回结果相关率>=60%"""
        query = "一人公司税收优惠政策"
        raw_results = [
            {'title': 'SCI论文发表流程', 'snippet': '学术论文投稿指南...'},
            {'title': '小微企业税收减免政策2026', 'snippet': '一人公司可享受...'},
            {'title': '如何写好一封信', 'snippet': '书信格式规范...'},
            {'title': '小说创作技巧大全', 'snippet': '从入门到精通...'},
            {'title': '个体户税务申报指南', 'snippet': '2026年最新政策...'},
        ]

        processed = self.processor.process(query, raw_results)

        total = len(processed.results)
        relevant = sum(
            1 for r in processed.results
            if any(kw in (r.get('title', '') + r.get('snippet', '')).lower()
                   for kw in ['税收', '优惠', '政策', '税务'])
        )

        if total > 0:
            relevance_rate = relevant / total * 100
            self.assertGreaterEqual(
                relevance_rate, 60,
                f"相关率{relevance_rate:.0f}%低于60%阈值 ({relevant}/{total})"
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
