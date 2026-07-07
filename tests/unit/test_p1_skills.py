import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSocialSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from opc_manager.data_manager import init_db, _local

        # 重置数据库状态，确保每个测试类获得干净连接
        if hasattr(_local, "conn") and _local.conn:
            try:
                _local.conn.close()
            except Exception:
                pass
            _local.conn = None
        import opc_manager.data_manager as dm

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

    @unittest.skip("social_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
    def test_generate_content_xiaohongshu(self):
        from opc_manager.social_skill import generate_content, PLATFORMS

        result = generate_content("小红书", "自由职业时间管理")
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "小红书")
        self.assertIn("title", result)
        self.assertIn("body", result)
        self.assertIn("tags", result)
        self.assertEqual(result["status"], "draft")
        self.assertIn("publish_guide", result)
        self.assertLessEqual(len(result["body"]), PLATFORMS["小红书"]["max_body"])

    @unittest.skip("social_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
    def test_generate_content_gongzhonghao(self):
        from opc_manager.social_skill import generate_content, PLATFORMS

        result = generate_content(
            "公众号", "一人公司税务规划", "增值税、个税、企业所得税"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "公众号")
        self.assertIn("深度解析", result["title"])
        self.assertLessEqual(len(result["body"]), PLATFORMS["公众号"]["max_body"])

    @unittest.skip("social_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
    def test_generate_content_twitter(self):
        from opc_manager.social_skill import generate_content, PLATFORMS

        result = generate_content("推特", "AI工具推荐", "效率提升、自动化")
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "推特")
        self.assertEqual(result["title"], "")
        self.assertLessEqual(len(result["body"]), PLATFORMS["推特"]["max_body"])

    @unittest.skip("social_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
    def test_generate_content_weibo(self):
        from opc_manager.social_skill import generate_content, PLATFORMS

        result = generate_content("微博", "创业心得")
        self.assertTrue(result["success"])
        self.assertIn("#", result["body"])
        self.assertLessEqual(len(result["body"]), PLATFORMS["微博"]["max_body"])

    @unittest.skip("social_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
    def test_generate_content_zhihu(self):
        from opc_manager.social_skill import generate_content, PLATFORMS

        result = generate_content("知乎", "一人公司如何获客")
        self.assertTrue(result["success"])
        self.assertIn("实战经验", result["title"])
        self.assertLessEqual(len(result["body"]), PLATFORMS["知乎"]["max_body"])

    def test_generate_content_unsupported_platform(self):
        from opc_manager.social_skill import generate_content

        result = generate_content("抖音", "测试")
        self.assertFalse(result["success"])
        self.assertIn("不支持的平台", result["error"])

    def test_list_drafts_empty(self):
        from opc_manager.social_skill import list_drafts

        result = list_drafts()
        self.assertTrue(result["success"])

    @unittest.skip("social_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
    def test_mark_published(self):
        from opc_manager.social_skill import generate_content, mark_published

        gen = generate_content("小红书", "测试发布")
        content_id = gen["id"]

        result = mark_published(content_id)
        self.assertTrue(result["success"])

    def test_mark_published_nonexistent(self):
        from opc_manager.social_skill import mark_published

        result = mark_published("nonexistent_id")
        self.assertFalse(result["success"])

    def test_platforms_config_completeness(self):
        from opc_manager.social_skill import PLATFORMS

        required_keys = {"max_body", "style"}
        for name, cfg in PLATFORMS.items():
            self.assertTrue(required_keys.issubset(cfg.keys()), f"{name} missing keys")


@unittest.skip("proposal_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
class TestProposalSkill(unittest.TestCase):
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

    def test_create_proposal_default(self):
        from opc_manager.proposal_skill import create_proposal

        result = create_proposal("张总")
        self.assertTrue(result["success"])
        self.assertIn("id", result)
        self.assertIn("markdown", result)
        self.assertIn("张总", result["markdown"])
        self.assertIn("报价单", result["message"])

    def test_create_proposal_with_service_type(self):
        from opc_manager.proposal_skill import create_proposal

        result = create_proposal("李总", service_type="开发")
        self.assertTrue(result["success"])
        self.assertIn("开发", result["markdown"])

    def test_create_proposal_with_items(self):
        from opc_manager.proposal_skill import create_proposal

        items = [
            {"name": "需求分析", "quantity": 1, "unit": "次", "price": 5000},
            {"name": "开发实施", "quantity": 10, "unit": "人天", "price": 2000},
        ]
        result = create_proposal("王总", items=items)
        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 25000)

    def test_create_proposal_empty_client(self):
        from opc_manager.proposal_skill import create_proposal

        result = create_proposal("")
        self.assertFalse(result["success"])
        self.assertIn("不能为空", result["error"])

    def test_create_proposal_valid_days(self):
        from opc_manager.proposal_skill import create_proposal

        result = create_proposal("赵总", valid_days=15)
        self.assertTrue(result["success"])
        self.assertIn("valid_until", result)

    def test_list_proposals_empty(self):
        from opc_manager.proposal_skill import list_proposals

        result = list_proposals()
        self.assertTrue(result["success"])

    def test_update_proposal_status(self):
        from opc_manager.proposal_skill import create_proposal, update_proposal_status

        created = create_proposal("测试客户")
        pid = created["id"]
        result = update_proposal_status(pid, "sent")
        self.assertTrue(result["success"])

    def test_update_proposal_invalid_status(self):
        from opc_manager.proposal_skill import update_proposal_status

        result = update_proposal_status("any_id", "invalid_status")
        self.assertFalse(result["success"])
        self.assertIn("无效状态", result["error"])

    def test_service_templates_completeness(self):
        from opc_manager.proposal_skill import SERVICE_TEMPLATES

        required = {"咨询", "培训", "设计", "开发", "通用"}
        self.assertTrue(required.issubset(set(SERVICE_TEMPLATES.keys())))
        for name, tpl in SERVICE_TEMPLATES.items():
            self.assertIn("items", tpl)
            for item in tpl["items"]:
                self.assertIn("name", item)
                self.assertIn("unit", item)

    def test_markdown_rendering(self):
        from opc_manager.proposal_skill import create_proposal

        items = [{"name": "测试服务", "quantity": 2, "unit": "次", "price": 1000}]
        result = create_proposal("MD客户", items=items)
        md = result["markdown"]
        self.assertIn("| 序号 |", md)
        self.assertIn("¥2000.00", md)
        self.assertIn("合计", md)


@unittest.skip("invoice_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
class TestInvoiceSkill(unittest.TestCase):
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

    def test_create_invoice(self):
        from opc_manager.invoice_skill import create_invoice

        result = create_invoice("张总", 5000)
        self.assertTrue(result["success"])
        self.assertIn("invoice_no", result)
        self.assertEqual(result["amount"], 5000)
        self.assertAlmostEqual(result["tax_amount"], 300.0)
        self.assertAlmostEqual(result["total_with_tax"], 5300.0)
        self.assertIn("markdown", result)

    def test_create_invoice_custom_tax_rate(self):
        from opc_manager.invoice_skill import create_invoice

        result = create_invoice("李总", 10000, tax_rate=0.13)
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["tax_amount"], 1300.0)
        self.assertAlmostEqual(result["total_with_tax"], 11300.0)

    def test_create_invoice_zero_amount(self):
        from opc_manager.invoice_skill import create_invoice

        result = create_invoice("王总", 0)
        self.assertFalse(result["success"])
        self.assertIn("大于0", result["error"])

    def test_create_invoice_negative_amount(self):
        from opc_manager.invoice_skill import create_invoice

        result = create_invoice("王总", -100)
        self.assertFalse(result["success"])

    def test_create_invoice_empty_client(self):
        from opc_manager.invoice_skill import create_invoice

        result = create_invoice("  ", 5000)
        self.assertFalse(result["success"])
        self.assertIn("不能为空", result["error"])

    def test_invoice_number_format(self):
        from opc_manager.invoice_skill import create_invoice

        result = create_invoice("赵总", 3000)
        self.assertTrue(result["success"])
        self.assertTrue(result["invoice_no"].startswith("OPC"))

    def test_list_invoices_empty(self):
        from opc_manager.invoice_skill import list_invoices

        result = list_invoices()
        self.assertTrue(result["success"])

    def test_tax_calendar_current_month(self):
        from opc_manager.invoice_skill import get_tax_calendar

        result = get_tax_calendar()
        self.assertTrue(result["success"])
        self.assertIn("this_month", result)
        self.assertIn("next_month", result)
        self.assertGreater(len(result["this_month"]), 0)

    def test_tax_calendar_specific_month(self):
        from opc_manager.invoice_skill import get_tax_calendar

        result = get_tax_calendar(4)
        self.assertTrue(result["success"])
        self.assertEqual(result["current_month"], 4)
        self.assertTrue(
            any("企业所得税" in e.get("type", "") for e in result["this_month"])
        )

    def test_tax_calendar_12_months(self):
        from opc_manager.invoice_skill import TAX_CALENDAR

        months = {e["month"] for e in TAX_CALENDAR}
        self.assertEqual(months, set(range(1, 13)))

    def test_markdown_rendering(self):
        from opc_manager.invoice_skill import create_invoice

        result = create_invoice("MD客户", 8000)
        md = result["markdown"]
        self.assertIn("发票号码", md)
        self.assertIn("价税合计", md)


class TestReportSkill(unittest.TestCase):
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

    @patch("opc_manager.report_skill.list_tasks")
    @patch("opc_manager.report_skill.get_customer_stats")
    @patch("opc_manager.report_skill.get_silent_customers")
    def test_generate_weekly_report(self, mock_silent, mock_crm, mock_tasks):
        mock_tasks.return_value = {
            "tasks": [
                {"title": "完成方案", "status": "done", "priority_label": "P1"},
                {
                    "title": "待开会",
                    "status": "pending",
                    "priority_label": "P2",
                    "due_date": "2025-05-16",
                },
            ]
        }
        mock_crm.return_value = {"total": 5, "active": 3}
        mock_silent.return_value = {"count": 1}

        from opc_manager.report_skill import generate_weekly_report

        result = generate_weekly_report("本周重点推进方案")
        self.assertTrue(result["success"])
        self.assertIn("markdown", result)
        self.assertIn("周报", result["markdown"])
        self.assertIn("本周重点推进方案", result["markdown"])
        self.assertIn("完成方案", result["markdown"])

    @patch("opc_manager.report_skill.get_trend")
    @patch("opc_manager.report_skill.get_monthly_report")
    @patch("opc_manager.report_skill.get_customer_stats")
    @patch("opc_manager.report_skill.get_silent_customers")
    def test_generate_monthly_report(
        self, mock_silent, mock_crm, mock_finance, mock_trend
    ):
        mock_finance.return_value = {
            "success": True,
            "income": 30000,
            "expense": 10000,
            "profit": 20000,
            "income_change": "+10%",
            "expense_change": "-5%",
            "income_by_category": {"咨询费": 20000, "培训费": 10000},
            "expense_by_category": {"工具订阅": 5000, "差旅": 5000},
        }
        mock_crm.return_value = {"total": 8, "active": 5, "potential": 2, "silent": 1}
        mock_silent.return_value = {"count": 1}
        mock_trend.return_value = [
            {
                "year_month": "2025-03",
                "income": 25000,
                "expense": 9000,
                "profit": 16000,
            },
            {
                "year_month": "2025-04",
                "income": 28000,
                "expense": 9500,
                "profit": 18500,
            },
        ]

        from opc_manager.report_skill import generate_monthly_report

        result = generate_monthly_report("2025-05")
        self.assertTrue(result["success"])
        self.assertIn("月度经营报告", result["markdown"])
        self.assertIn("30000", result["markdown"])

    @patch("opc_manager.report_skill.get_monthly_report")
    @patch("opc_manager.report_skill.get_customer_stats")
    def test_generate_annual_report(self, mock_crm, mock_finance):
        mock_finance.side_effect = lambda ym: (
            {
                "success": True,
                "income": 30000 * int(ym.split("-")[1]) % 5,
                "expense": 10000,
                "profit": 20000,
            }
            if int(ym.split("-")[1]) % 3 == 0
            else {"success": True, "income": 0, "expense": 0, "profit": 0}
        )
        mock_crm.return_value = {"total": 10, "active": 6, "lost": 1}

        from opc_manager.report_skill import generate_annual_report

        result = generate_annual_report("2025")
        self.assertTrue(result["success"])
        self.assertIn("年度经营报告", result["markdown"])

    @patch("opc_manager.report_skill.list_tasks")
    @patch("opc_manager.report_skill.get_customer_stats")
    @patch("opc_manager.report_skill.get_silent_customers")
    def test_weekly_report_file_saved(self, mock_silent, mock_crm, mock_tasks):
        mock_tasks.return_value = {"tasks": []}
        mock_crm.return_value = {"total": 0, "active": 0}
        mock_silent.return_value = {"count": 0}

        from opc_manager.report_skill import generate_weekly_report

        result = generate_weekly_report()
        self.assertTrue(result["success"])


@unittest.skip("calendar_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
class TestCalendarSkill(unittest.TestCase):
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

    def test_add_event(self):
        from opc_manager.calendar_skill import add_event

        result = add_event("项目评审", "2025-05-20", "14:00")
        self.assertTrue(result["success"])
        self.assertIn("id", result)
        self.assertIn("项目评审", result["message"])

    def test_add_event_with_reminder(self):
        from opc_manager.calendar_skill import add_event

        result = add_event("客户会议", "2025-05-21", "10:00", reminder_min=30)
        self.assertTrue(result["success"])
        self.assertIn("30分钟提醒", result["reminder"])

    def test_add_event_empty_title(self):
        from opc_manager.calendar_skill import add_event

        result = add_event("", "2025-05-20")
        self.assertFalse(result["success"])
        self.assertIn("不能为空", result["error"])

    def test_add_event_invalid_date(self):
        from opc_manager.calendar_skill import add_event

        result = add_event("测试", "2025/05/20")
        self.assertFalse(result["success"])
        self.assertIn("日期格式无效", result["error"])

    def test_get_day_schedule(self):
        from opc_manager.calendar_skill import add_event, get_day_schedule

        add_event("上午会议", "2099-01-22", "09:00")
        add_event("下午评审", "2099-01-22", "15:00")
        result = get_day_schedule("2099-01-22")
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["count"], 2)
        self.assertEqual(result["events"][0]["time"], "09:00")

    def test_get_day_schedule_empty(self):
        from opc_manager.calendar_skill import get_day_schedule

        result = get_day_schedule("2099-12-31")
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_get_week_schedule(self):
        from opc_manager.calendar_skill import add_event, get_week_schedule

        add_event("周会", "2025-05-19", "10:00")
        result = get_week_schedule("2025-05-19")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["days"]), 7)

    def test_cancel_event(self):
        from opc_manager.calendar_skill import add_event, cancel_event

        created = add_event("取消测试", "2025-05-23", "11:00")
        event_id = created["id"]
        result = cancel_event(event_id)
        self.assertTrue(result["success"])

    def test_cancel_nonexistent_event(self):
        from opc_manager.calendar_skill import cancel_event

        result = cancel_event("nonexistent_id")
        self.assertFalse(result["success"])

    def test_parse_date_from_text(self):
        from opc_manager.utils import parse_date_from_text
        from datetime import datetime, timedelta

        today = time.strftime("%Y-%m-%d")
        self.assertEqual(parse_date_from_text("今天开会"), today)

        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        self.assertEqual(parse_date_from_text("明天"), tomorrow)

        result = parse_date_from_text("2025年6月15日")
        self.assertEqual(result, "2025-06-15")

        result = parse_date_from_text("2025-12-25")
        self.assertEqual(result, "2025-12-25")

    def test_get_upcoming_reminders_no_events(self):
        from opc_manager.calendar_skill import get_upcoming_reminders

        result = get_upcoming_reminders()
        self.assertTrue(result["success"])


class TestSkillRegistryP1(unittest.TestCase):
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

    def test_social_skill_registered(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skill = registry.get_skill("social_publish")
        self.assertIsNotNone(skill)
        self.assertIn("小红书", skill.intent_keywords)

    def test_proposal_skill_removed(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        # proposal skill was removed in v0.3.4 (frozen skills cleanup)
        self.assertIsNone(registry.get_skill("proposal"))

    def test_invoice_skill_registered(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skill = registry.get_skill("invoice")
        self.assertIsNotNone(skill)
        self.assertIn("发票", skill.intent_keywords)

    def test_report_skill_registered(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skill = registry.get_skill("report")
        self.assertIsNotNone(skill)
        self.assertIn("周报", skill.intent_keywords)

    def test_calendar_skill_removed(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        # calendar skill was removed in v0.3.4 (frozen skills cleanup)
        self.assertIsNone(registry.get_skill("calendar"))

    def test_total_skill_count(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        self.assertGreaterEqual(len(registry.skills), 16)

    def test_find_by_intent_social(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skills = registry.find_by_intent("帮我发小红书")
        skill_ids = [s.skill_id for s in skills]
        self.assertIn("social_publish", skill_ids)

    def test_find_by_intent_proposal_removed(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skills = registry.find_by_intent("给张总出个报价")
        skill_ids = [s.skill_id for s in skills]
        # proposal skill removed in v0.3.4; intent no longer maps to a skill
        self.assertNotIn("proposal", skill_ids)

    def test_find_by_intent_invoice(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skills = registry.find_by_intent("开一张发票")
        skill_ids = [s.skill_id for s in skills]
        self.assertIn("invoice", skill_ids)

    def test_find_by_intent_report(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skills = registry.find_by_intent("生成本周周报")
        skill_ids = [s.skill_id for s in skills]
        self.assertIn("report", skill_ids)

    def test_find_by_intent_calendar_removed(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        skills = registry.find_by_intent("安排明天会议")
        skill_ids = [s.skill_id for s in skills]
        # calendar skill removed in v0.3.4; intent no longer maps to a skill
        self.assertNotIn("calendar", skill_ids)

    @unittest.skip("social_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
    def test_execute_social(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        result = registry._execute_social("帮我发小红书关于时间管理")
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "小红书")

    def test_execute_social_no_platform(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        result = registry._execute_social("帮我发个帖子")
        self.assertFalse(result["success"])
        self.assertIn("平台", result["error"])

    def test_execute_invoice_no_amount(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        result = registry._execute_invoice("给张开发票")
        self.assertFalse(result["success"])
        self.assertIn("金额", result["error"])

    def test_execute_report_weekly(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        with (
            patch("opc_manager.report_skill.list_tasks", return_value={"tasks": []}),
            patch(
                "opc_manager.report_skill.get_customer_stats",
                return_value={"total": 0, "active": 0},
            ),
            patch(
                "opc_manager.report_skill.get_silent_customers",
                return_value={"count": 0},
            ),
        ):
            result = registry._execute_report("生成本周周报")
        self.assertTrue(result["success"])

    @unittest.skip("calendar_skill 已冻结 v0.3.0, 见 SKILL_FREEZE_LIST.md")
    def test_execute_calendar_add(self):
        from opc_manager.skill_registry import SkillRegistry

        registry = SkillRegistry(register_builtins=True)
        result = registry._execute_calendar("帮我安排明天项目评审")
        self.assertTrue(result["success"])


class TestIntentTypeP1(unittest.TestCase):
    def test_social_intent_exists(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "SOCIAL"))
        self.assertEqual(IntentType.SOCIAL.value, "social")

    def test_proposal_intent_exists(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "PROPOSAL"))
        self.assertEqual(IntentType.PROPOSAL.value, "proposal")

    def test_invoice_intent_exists(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "INVOICE"))
        self.assertEqual(IntentType.INVOICE.value, "invoice")

    def test_report_intent_exists(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "REPORT"))
        self.assertEqual(IntentType.REPORT.value, "report")

    def test_calendar_intent_exists(self):
        from opc_manager.strategist_brain import IntentType

        self.assertTrue(hasattr(IntentType, "CALENDAR"))
        self.assertEqual(IntentType.CALENDAR.value, "calendar")

    def test_intent_count(self):
        from opc_manager.strategist_brain import IntentType

        self.assertGreaterEqual(len(IntentType), 16)

    def test_intent_keywords_p1(self):
        from opc_manager.strategist_brain import StrategistBrain, IntentType

        brain = StrategistBrain()
        keywords = brain.intent_keywords
        self.assertIn(IntentType.SOCIAL, keywords)
        self.assertIn(IntentType.PROPOSAL, keywords)
        self.assertIn(IntentType.INVOICE, keywords)
        self.assertIn(IntentType.REPORT, keywords)
        self.assertIn(IntentType.CALENDAR, keywords)


if __name__ == "__main__":
    unittest.main()
