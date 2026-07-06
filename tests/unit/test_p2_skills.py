import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@unittest.skip("competitor_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
class TestCompetitorSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from opc_manager.data_manager import init_db
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False
        init_db()

    @classmethod
    def tearDownClass(cls):
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False

    def test_add_competitor(self):
        from opc_manager.competitor_skill import add_competitor

        result = add_competitor("竞品A", url="https://a.com", keywords="AI、SaaS")
        self.assertTrue(result["success"])
        self.assertIn("竞品A", result["message"])

    def test_add_competitor_empty_name(self):
        from opc_manager.competitor_skill import add_competitor

        result = add_competitor("")
        self.assertFalse(result["success"])

    def test_list_competitors_empty(self):
        from opc_manager.competitor_skill import list_competitors

        result = list_competitors()
        self.assertTrue(result["success"])

    def test_list_competitors_with_data(self):
        from opc_manager.competitor_skill import add_competitor, list_competitors

        add_competitor("竞品B")
        result = list_competitors()
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_record_snapshot(self):
        from opc_manager.competitor_skill import add_competitor, record_snapshot

        created = add_competitor("竞品C")
        cid = created["id"]
        result = record_snapshot(cid, "发布了新功能")
        self.assertTrue(result["success"])

    def test_record_snapshot_nonexistent(self):
        from opc_manager.competitor_skill import record_snapshot

        result = record_snapshot("nonexistent", "test")
        self.assertFalse(result["success"])

    def test_get_competitor_report_all(self):
        from opc_manager.competitor_skill import get_competitor_report

        result = get_competitor_report()
        self.assertTrue(result["success"])
        self.assertIn("markdown", result)

    def test_remove_competitor(self):
        from opc_manager.competitor_skill import add_competitor, remove_competitor

        created = add_competitor("待删除竞品")
        cid = created["id"]
        result = remove_competitor(cid)
        self.assertTrue(result["success"])


@unittest.skip("pricing_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
class TestPricingSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from opc_manager.data_manager import init_db
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False
        init_db()

    @classmethod
    def tearDownClass(cls):
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False

    def test_calculate_cost_pricing(self):
        from opc_manager.pricing_skill import calculate_pricing

        result = calculate_pricing("成本定价", cost=5000)
        self.assertTrue(result["success"])
        self.assertEqual(result["price"], 6500.0)

    def test_calculate_value_pricing(self):
        from opc_manager.pricing_skill import calculate_pricing

        result = calculate_pricing("价值定价", cost=5000)
        self.assertTrue(result["success"])
        self.assertEqual(result["price"], 18750.0)

    def test_calculate_competition_pricing(self):
        from opc_manager.pricing_skill import calculate_pricing

        result = calculate_pricing("竞争定价", market_avg=8000)
        self.assertTrue(result["success"])
        self.assertEqual(result["price"], 8000.0)

    def test_calculate_hourly_pricing(self):
        from opc_manager.pricing_skill import calculate_pricing

        result = calculate_pricing(
            "小时费率", service_type="咨询", hours=10, level="senior"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["price"], 10000.0)

    def test_calculate_invalid_method(self):
        from opc_manager.pricing_skill import calculate_pricing

        result = calculate_pricing("随机定价")
        self.assertFalse(result["success"])

    def test_calculate_cost_pricing_no_cost(self):
        from opc_manager.pricing_skill import calculate_pricing

        result = calculate_pricing("成本定价")
        self.assertFalse(result["success"])

    def test_get_hourly_benchmarks(self):
        from opc_manager.pricing_skill import get_hourly_benchmarks

        result = get_hourly_benchmarks("咨询")
        self.assertTrue(result["success"])
        self.assertIn("junior", result["rates"])
        self.assertIn("senior", result["rates"])

    def test_get_all_benchmarks(self):
        from opc_manager.pricing_skill import get_hourly_benchmarks

        result = get_hourly_benchmarks()
        self.assertTrue(result["success"])
        self.assertIn("all_rates", result)

    def test_suggest_pricing(self):
        from opc_manager.pricing_skill import suggest_pricing

        result = suggest_pricing(service_type="开发", cost=5000, hours=10)
        self.assertTrue(result["success"])
        self.assertGreater(len(result["suggestions"]), 0)

    def test_suggest_pricing_no_input(self):
        from opc_manager.pricing_skill import suggest_pricing

        result = suggest_pricing()
        self.assertTrue(result["success"])

    def test_save_pricing_record(self):
        from opc_manager.pricing_skill import save_pricing_record

        result = save_pricing_record("咨询服务", "成本定价", 6500)
        self.assertTrue(result["success"])

    def test_pricing_methods_completeness(self):
        from opc_manager.pricing_skill import PRICING_METHODS

        required = {"成本定价", "价值定价", "竞争定价", "小时费率"}
        self.assertTrue(required.issubset(set(PRICING_METHODS.keys())))


@unittest.skip("tax_reminder_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
class TestTaxReminderSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from opc_manager.data_manager import init_db
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False
        init_db()

    @classmethod
    def tearDownClass(cls):
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False

    def test_check_upcoming_deadlines(self):
        from opc_manager.tax_reminder_skill import check_upcoming_deadlines

        result = check_upcoming_deadlines(days_ahead=365)
        self.assertTrue(result["success"])
        self.assertIn("upcoming", result)

    def test_create_reminder(self):
        from opc_manager.tax_reminder_skill import create_reminder

        result = create_reminder("增值税申报", "2025-06-15", tax_type="增值税")
        self.assertTrue(result["success"])

    def test_create_reminder_empty_task(self):
        from opc_manager.tax_reminder_skill import create_reminder

        result = create_reminder("", "2025-06-15")
        self.assertFalse(result["success"])

    def test_create_reminder_invalid_date(self):
        from opc_manager.tax_reminder_skill import create_reminder

        result = create_reminder("测试", "2025/06/15")
        self.assertFalse(result["success"])

    def test_complete_reminder(self):
        from opc_manager.tax_reminder_skill import create_reminder, complete_reminder

        created = create_reminder("个税申报", "2025-06-30", tax_type="个税")
        rid = created["id"]
        result = complete_reminder(rid)
        self.assertTrue(result["success"])

    def test_complete_nonexistent_reminder(self):
        from opc_manager.tax_reminder_skill import complete_reminder

        result = complete_reminder("nonexistent")
        self.assertFalse(result["success"])

    def test_list_reminders(self):
        from opc_manager.tax_reminder_skill import list_reminders

        result = list_reminders()
        self.assertTrue(result["success"])

    def test_get_tax_checklist(self):
        from opc_manager.tax_reminder_skill import get_tax_checklist

        result = get_tax_checklist(month=4)
        self.assertTrue(result["success"])
        self.assertGreater(result["total"], 0)

    def test_urgency_levels(self):
        from opc_manager.tax_reminder_skill import _urgency_level

        self.assertEqual(_urgency_level(1), "紧急")
        self.assertEqual(_urgency_level(5), "重要")
        self.assertEqual(_urgency_level(10), "关注")
        self.assertEqual(_urgency_level(20), "提前准备")


@unittest.skip("dashboard_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
class TestDashboardSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from opc_manager.data_manager import init_db
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False
        init_db()

    @classmethod
    def tearDownClass(cls):
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False

    @patch("opc_manager.dashboard_skill.list_tasks")
    @patch("opc_manager.dashboard_skill.get_silent_customers")
    @patch("opc_manager.dashboard_skill.get_customer_stats")
    @patch("opc_manager.dashboard_skill.get_monthly_report")
    def test_get_overview(self, mock_finance, mock_crm, mock_silent, mock_tasks):
        mock_finance.return_value = {"income": 30000, "expense": 10000, "profit": 20000}
        mock_crm.return_value = {"total": 10, "active": 5}
        mock_silent.return_value = {"count": 2}
        mock_tasks.return_value = {
            "tasks": [
                {"title": "待办A", "status": "pending", "due_date": "2025-01-01"},
            ]
        }

        from opc_manager.dashboard_skill import get_overview

        result = get_overview()
        self.assertTrue(result["success"])
        self.assertEqual(result["finance"]["month_income"], 30000)
        self.assertEqual(result["crm"]["total_customers"], 10)
        self.assertEqual(result["tasks"]["pending"], 1)

    @patch("opc_manager.dashboard_skill.get_trend")
    def test_get_finance_dashboard(self, mock_trend):
        mock_trend.return_value = [
            {
                "year_month": "2025-04",
                "income": 30000,
                "expense": 10000,
                "profit": 20000,
            },
            {
                "year_month": "2025-05",
                "income": 35000,
                "expense": 12000,
                "profit": 23000,
            },
        ]

        from opc_manager.dashboard_skill import get_finance_dashboard

        result = get_finance_dashboard(2)
        self.assertTrue(result["success"])
        self.assertEqual(result["total_income"], 65000)

    @patch("opc_manager.dashboard_skill.get_silent_customers")
    @patch("opc_manager.dashboard_skill.get_customer_stats")
    def test_get_crm_dashboard(self, mock_stats, mock_silent):
        mock_stats.return_value = {
            "total": 8,
            "active": 4,
            "potential": 2,
            "silent": 1,
            "lost": 1,
        }
        mock_silent.return_value = {"count": 1, "customers": []}

        from opc_manager.dashboard_skill import get_crm_dashboard

        result = get_crm_dashboard()
        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 8)

    @patch("opc_manager.dashboard_skill.list_tasks")
    def test_get_task_dashboard(self, mock_tasks):
        mock_tasks.return_value = {
            "tasks": [
                {
                    "title": "任务A",
                    "status": "pending",
                    "priority": 0,
                    "due_date": "2025-01-01",
                },
                {"title": "任务B", "status": "done", "priority": 1},
            ]
        }

        from opc_manager.dashboard_skill import get_task_dashboard

        result = get_task_dashboard()
        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 2)

    @patch("opc_manager.dashboard_skill.get_task_dashboard")
    @patch("opc_manager.dashboard_skill.get_crm_dashboard")
    @patch("opc_manager.dashboard_skill.get_finance_dashboard")
    @patch("opc_manager.dashboard_skill.get_overview")
    def test_generate_dashboard_report(
        self, mock_overview, mock_finance, mock_crm, mock_tasks
    ):
        mock_overview.return_value = {
            "success": True,
            "date": "2025-05-14",
            "finance": {
                "month_income": 30000,
                "month_expense": 10000,
                "month_profit": 20000,
            },
            "crm": {
                "total_customers": 10,
                "active_customers": 5,
                "silent_customers": 2,
            },
            "tasks": {"pending": 3, "overdue": 1},
        }
        mock_finance.return_value = {
            "success": True,
            "trend": [
                {
                    "year_month": "2025-05",
                    "income": 30000,
                    "expense": 10000,
                    "profit": 20000,
                }
            ],
        }
        mock_crm.return_value = {"success": True, "total": 10, "by_status": {}}
        mock_tasks.return_value = {
            "success": True,
            "total": 5,
            "overdue_count": 0,
            "overdue_tasks": [],
        }

        from opc_manager.dashboard_skill import generate_dashboard_report

        result = generate_dashboard_report()
        self.assertTrue(result["success"])
        self.assertIn("markdown", result)
        self.assertIn("看板", result["markdown"])


@unittest.skip("knowledge_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
class TestKnowledgeSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from opc_manager.data_manager import init_db
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False
        init_db()

    @classmethod
    def tearDownClass(cls):
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False

    def test_create_article(self):
        from opc_manager.knowledge_skill import create_article

        result = create_article(
            "AI工具推荐", "推荐5个AI工具...", tags="AI、工具", category="技术"
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["word_count"], 0)

    def test_create_article_empty_title(self):
        from opc_manager.knowledge_skill import create_article

        result = create_article("", "内容")
        self.assertFalse(result["success"])

    def test_create_article_empty_content(self):
        from opc_manager.knowledge_skill import create_article

        result = create_article("标题", "")
        self.assertFalse(result["success"])

    def test_get_article(self):
        from opc_manager.knowledge_skill import create_article, get_article

        created = create_article("测试文章", "测试内容", tags="测试")
        aid = created["id"]
        result = get_article(aid)
        self.assertTrue(result["success"])
        self.assertEqual(result["article"]["title"], "测试文章")

    def test_get_article_nonexistent(self):
        from opc_manager.knowledge_skill import get_article

        result = get_article("nonexistent")
        self.assertFalse(result["success"])

    def test_update_article(self):
        from opc_manager.knowledge_skill import create_article, update_article

        created = create_article("待更新", "原始内容")
        aid = created["id"]
        result = update_article(aid, title="已更新", tags="新标签")
        self.assertTrue(result["success"])

    def test_delete_article(self):
        from opc_manager.knowledge_skill import create_article, delete_article

        created = create_article("待删除", "内容")
        aid = created["id"]
        result = delete_article(aid)
        self.assertTrue(result["success"])

    def test_search_articles(self):
        from opc_manager.knowledge_skill import create_article, search_articles

        create_article("Python技巧", "Python编程技巧合集", category="编程")
        result = search_articles(query="Python")
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_search_by_category(self):
        from opc_manager.knowledge_skill import create_article, search_articles

        create_article("设计规范", "UI设计规范", category="设计")
        result = search_articles(category="设计")
        self.assertTrue(result["success"])

    def test_list_categories(self):
        from opc_manager.knowledge_skill import list_categories

        result = list_categories()
        self.assertTrue(result["success"])

    def test_get_stats(self):
        from opc_manager.knowledge_skill import get_stats

        result = get_stats()
        self.assertTrue(result["success"])
        self.assertIn("total", result)


class TestSkillRegistryP2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from opc_manager.data_manager import init_db
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False
        init_db()

    @classmethod
    def tearDownClass(cls):
        import opc_manager.data_manager as dm

        if hasattr(dm._local, "conn") and dm._local.conn:
            try:
                dm._local.conn.close()
            except Exception:
                pass
            dm._local.conn = None
        dm._db_initialized = False

    def test_competitor_skill_registered(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skill = registry.get_skill("competitor_watch")
        self.assertIsNotNone(skill)
        self.assertIn("竞品", skill.intent_keywords)

    def test_pricing_skill_registered(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skill = registry.get_skill("pricing")
        self.assertIsNotNone(skill)
        self.assertIn("定价", skill.intent_keywords)

    def test_tax_reminder_skill_registered(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skill = registry.get_skill("tax_reminder")
        self.assertIsNotNone(skill)
        self.assertIn("税务提醒", skill.intent_keywords)

    def test_dashboard_skill_registered(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skill = registry.get_skill("dashboard")
        self.assertIsNotNone(skill)
        self.assertIn("看板", skill.intent_keywords)

    def test_knowledge_skill_registered(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skill = registry.get_skill("knowledge_mgmt")
        self.assertIsNotNone(skill)
        self.assertIn("知识库", skill.intent_keywords)

    def test_total_skill_count(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        self.assertGreaterEqual(len(registry.skills), 21)

    @unittest.skip("competitor_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
    def test_execute_competitor_add(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        result = registry._execute_competitor("帮我添加竞品飞书")
        self.assertTrue(result["success"])

    def test_execute_pricing_suggest(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        result = registry._execute_pricing("定价建议")
        self.assertTrue(result["success"])

    def test_execute_tax_reminder_check(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        result = registry._execute_tax_reminder("税务提醒")
        self.assertTrue(result["success"])

    def test_execute_dashboard_overview(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        with (
            patch(
                "opc_manager.dashboard_skill.get_monthly_report",
                return_value={"income": 0, "expense": 0, "profit": 0},
            ),
            patch(
                "opc_manager.dashboard_skill.get_customer_stats",
                return_value={"total": 0, "active": 0},
            ),
            patch(
                "opc_manager.dashboard_skill.get_silent_customers",
                return_value={"count": 0},
            ),
            patch("opc_manager.dashboard_skill.list_tasks", return_value={"tasks": []}),
        ):
            result = registry._execute_dashboard("看板")
        self.assertTrue(result["success"])

    def test_execute_knowledge_search(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        result = registry._execute_knowledge("搜索AI")
        self.assertTrue(result["success"])


class TestIntentTypeP2(unittest.TestCase):
    def test_competitor_intent(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "COMPETITOR"))
        self.assertEqual(IntentType.COMPETITOR.value, "competitor")

    def test_pricing_intent(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "PRICING"))
        self.assertEqual(IntentType.PRICING.value, "pricing")

    def test_tax_reminder_intent(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "TAX_REMINDER"))
        self.assertEqual(IntentType.TAX_REMINDER.value, "tax_reminder")

    def test_dashboard_intent(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "DASHBOARD"))
        self.assertEqual(IntentType.DASHBOARD.value, "dashboard")

    def test_knowledge_intent(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "KNOWLEDGE"))
        self.assertEqual(IntentType.KNOWLEDGE.value, "knowledge")

    def test_intent_count(self):
        from opc_manager.strategist_brain import IntentType

        self.assertGreaterEqual(len(IntentType), 21)

    def test_intent_keywords_p2(self):
        from opc_manager.strategist_brain import StrategistBrain, IntentType

        brain = StrategistBrain()
        keywords = brain.intent_keywords
        self.assertIn(IntentType.COMPETITOR, keywords)
        self.assertIn(IntentType.PRICING, keywords)
        self.assertIn(IntentType.TAX_REMINDER, keywords)
        self.assertIn(IntentType.DASHBOARD, keywords)
        self.assertIn(IntentType.KNOWLEDGE, keywords)


if __name__ == "__main__":
    unittest.main()
