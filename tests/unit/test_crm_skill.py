"""CRM Skill 覆盖率补充测试

目标：将 crm_skill.py 覆盖率从 14.8% 提升到 ≥70%
验证 P2 重构（execute_goal D(26)→C(13) 拆分的辅助函数）

覆盖范围：
- _clean_name_from_goal — 名称清理（纯函数）
- _handle_follow_up — 跟进意图
- _handle_search — 查找意图
- _handle_deal — 成交意图
- _handle_add_customer — 添加客户意图
- execute_goal — 分发路由（7 分支）
- add_customer / get_customer / search_customers — 基础 CRUD
- add_deal / get_silent_customers / get_customer_stats — 业务查询
- add_follow_up / get_follow_ups — 跟进管理
- update_customer_status — 状态更新
- _parse_customer_from_text — 文本解析
- undo_add_customer / undo_add_deal / undo_add_follow_up — 撤销操作

数据库使用临时目录 (OPC_DATA_DIR=tmp_path)，不污染真实数据。
"""

import pytest

import opc_manager.data_manager as dm
from opc_manager.crm_skill import (
    _clean_name_from_goal,
    _handle_add_customer,
    _handle_deal,
    _handle_follow_up,
    _handle_search,
    _parse_customer_from_text,
    add_customer,
    add_deal,
    add_follow_up,
    execute_goal,
    get_customer,
    get_customer_stats,
    get_follow_ups,
    get_silent_customers,
    search_customers,
    undo_add_customer,
    undo_add_deal,
    undo_add_follow_up,
    update_customer_status,
)
from opc_manager.tool_system import AuditLogger

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """临时数据库环境，每个测试独立隔离。"""
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    monkeypatch.setenv("OPC_DATA_DIR", str(db_dir))
    monkeypatch.setenv("OPC_ENCRYPTION_KEY", "test-key-for-encryption-32chars!!")

    _orig_initialized = dm._db_initialized
    _orig_data_dir = dm.DATA_DIR
    _orig_db_path = dm.DB_PATH

    dm.DATA_DIR = str(db_dir)
    dm.DB_PATH = str(db_dir / "opc_data.db")
    dm._db_initialized = False
    if hasattr(dm._local, "conn") and dm._local.conn is not None:
        try:
            dm._local.conn.close()
        except Exception:
            pass
        dm._local.conn = None

    orig_log_file = AuditLogger._log_file
    AuditLogger._log_file = str(tmp_path / "audit.jsonl")

    yield db_dir

    if hasattr(dm._local, "conn") and dm._local.conn is not None:
        try:
            dm._local.conn.close()
        except Exception:
            pass
        dm._local.conn = None
    dm._db_initialized = _orig_initialized
    dm.DATA_DIR = _orig_data_dir
    dm.DB_PATH = _orig_db_path
    AuditLogger._log_file = orig_log_file


def _seed_customer(name="张三", company="测试公司", phone="13800138000"):
    """辅助：插入一条客户记录并返回 ID。"""
    result = add_customer(name=name, company=company, phone=phone)
    assert result["success"], f"Failed to seed customer: {result}"
    return result["id"]


# ---------------------------------------------------------------------------
# _clean_name_from_goal (纯函数，无需 DB)
# ---------------------------------------------------------------------------


class TestCleanNameFromGoal:
    def test_removes_single_keyword(self):
        """Verify: single keyword removal from goal text."""
        result = _clean_name_from_goal("跟进张总", ["跟进"])
        assert result == "张总"

    def test_removes_multiple_keywords(self):
        """Verify: multiple keywords removed in sequence."""
        result = _clean_name_from_goal(
            "帮我跟进张总的客户", ["跟进", "帮我", "的", "客户"]
        )
        assert result == "张总"

    def test_strips_punctuation(self):
        """Verify: Chinese punctuation stripped from result."""
        result = _clean_name_from_goal("跟进张总，。、的", ["跟进"])
        assert result == "张总"

    def test_empty_goal(self):
        """Verify: empty goal returns empty string."""
        result = _clean_name_from_goal("", ["跟进"])
        assert result == ""

    def test_no_matching_keywords(self):
        """Verify: no matching keywords returns original text stripped."""
        result = _clean_name_from_goal("张三", ["跟进"])
        assert result == "张三"


# ---------------------------------------------------------------------------
# _parse_customer_from_text
# ---------------------------------------------------------------------------


class TestParseCustomerFromText:
    def test_parse_phone_email_company(self):
        """Verify: phone, email, company extracted from text."""
        text = "添加客户张三，电话13800138000，邮箱zs@test.com，公司：ABC科技"
        result = _parse_customer_from_text(text)
        assert result["phone"] == "13800138000"
        assert result["email"] == "zs@test.com"
        assert result["company"] == "ABC科技"
        assert "张三" in result["name"]

    def test_parse_source_and_tags(self):
        """Verify: source and tags extracted from text."""
        text = "添加客户李四，来源：展会，标签：VIP"
        result = _parse_customer_from_text(text)
        assert result["source"] == "展会"
        assert result["tags"] == "VIP"

    def test_parse_name_only(self):
        """Verify: name extracted when only name provided."""
        text = "添加客户王五"
        result = _parse_customer_from_text(text)
        assert "王五" in result["name"]
        assert result["phone"] == ""
        assert result["email"] == ""

    def test_parse_no_phone(self):
        """Verify: empty phone when no phone pattern in text."""
        result = _parse_customer_from_text("添加客户赵六")
        assert result["phone"] == ""


# ---------------------------------------------------------------------------
# add_customer
# ---------------------------------------------------------------------------


class TestAddCustomer:
    def test_add_success(self, temp_db):
        """Verify: customer added successfully with valid data."""
        result = add_customer(name="张三", company="ABC公司", phone="13800138000")
        assert result["success"]
        assert "id" in result
        assert "张三" in result["message"]

    def test_add_empty_name_fails(self, temp_db):
        """Verify: empty name rejected."""
        result = add_customer(name="")
        assert not result["success"]
        assert "不能为空" in result["error"]

    def test_add_invalid_phone_fails(self, temp_db):
        """Verify: invalid phone format rejected."""
        result = add_customer(name="张三", phone="123")
        assert not result["success"]
        assert "手机号格式无效" in result["error"]

    def test_add_invalid_email_fails(self, temp_db):
        """Verify: invalid email format rejected."""
        result = add_customer(name="张三", email="not-an-email")
        assert not result["success"]
        assert "邮箱格式无效" in result["error"]

    def test_add_international_phone(self, temp_db):
        """Verify: international phone format accepted."""
        result = add_customer(name="John", phone="+1234567890")
        assert result["success"]

    def test_add_without_company(self, temp_db):
        """Verify: customer added without company, message format adapts."""
        result = add_customer(name="李四")
        assert result["success"]
        assert "李四" in result["message"]
        assert "(" not in result["message"]


# ---------------------------------------------------------------------------
# get_customer
# ---------------------------------------------------------------------------


class TestGetCustomer:
    def test_get_by_id(self, temp_db):
        """Verify: customer retrieved by ID."""
        cid = _seed_customer(name="张三")
        result = get_customer(customer_id=cid)
        assert result["success"]
        assert result["customer"]["name"] == "张三"

    def test_get_by_name(self, temp_db):
        """Verify: customer retrieved by name (LIKE match)."""
        _seed_customer(name="张三丰")
        result = get_customer(name="张三")
        assert result["success"]
        assert "张三丰" in result["customer"]["name"]

    def test_get_not_found(self, temp_db):
        """Verify: non-existent customer returns error."""
        result = get_customer(name="不存在的人")
        assert not result["success"]
        assert "未找到" in result["error"]

    def test_get_no_params(self, temp_db):
        """Verify: no params returns error asking for ID or name."""
        result = get_customer()
        assert not result["success"]
        assert "请提供" in result["error"]

    def test_get_with_deals(self, temp_db):
        """Verify: customer result includes associated deals."""
        cid = _seed_customer(name="张三")
        add_deal(cid, "测试合作", amount=1000)
        result = get_customer(customer_id=cid)
        assert result["success"]
        assert len(result["customer"]["deals"]) == 1


# ---------------------------------------------------------------------------
# search_customers
# ---------------------------------------------------------------------------


class TestSearchCustomers:
    def test_search_empty(self, temp_db):
        """Verify: empty search returns all customers."""
        _seed_customer(name="张三")
        result = search_customers()
        assert result["success"]
        assert result["count"] >= 1

    def test_search_by_company(self, temp_db):
        """Verify: search by company name filters correctly."""
        add_customer(name="张三", company="ABC科技")
        add_customer(name="李四", company="XYZ集团")
        result = search_customers(company="ABC")
        assert result["success"]
        assert result["count"] == 1
        assert result["customers"][0]["name"] == "张三"

    def test_search_by_status(self, temp_db):
        """Verify: search by status filters correctly."""
        cid = _seed_customer(name="张三")
        update_customer_status(cid, "active")
        result = search_customers(status="active")
        assert result["success"]
        assert all(c["status"] == "active" for c in result["customers"])


# ---------------------------------------------------------------------------
# add_deal
# ---------------------------------------------------------------------------


class TestAddDeal:
    def test_add_deal_success(self, temp_db):
        """Verify: deal added successfully."""
        cid = _seed_customer(name="张三")
        result = add_deal(cid, "测试合作", amount=5000)
        assert result["success"]
        assert "测试合作" in result["message"]

    def test_add_deal_closed_won_updates_status(self, temp_db):
        """Verify: closed_won deal updates customer status to first_deal."""
        cid = _seed_customer(name="张三")
        add_deal(cid, "成交", amount=3000, status="closed_won")
        customer = get_customer(customer_id=cid)
        assert customer["customer"]["status"] == "first_deal"

    def test_add_deal_closed_won_active_customer(self, temp_db):
        """Verify: closed_won on active customer keeps active status."""
        cid = _seed_customer(name="张三")
        update_customer_status(cid, "active")
        add_deal(cid, "再次成交", amount=5000, status="closed_won")
        customer = get_customer(customer_id=cid)
        assert customer["customer"]["status"] == "active"

    def test_add_deal_transaction_failure(self, temp_db):
        """Verify: deal with invalid customer_id handled gracefully."""
        result = add_deal("nonexistent-id", "测试", amount=100)
        assert not result["success"]


# ---------------------------------------------------------------------------
# get_silent_customers
# ---------------------------------------------------------------------------


class TestGetSilentCustomers:
    def test_get_silent_customers_empty(self, temp_db):
        """Verify: no silent customers in fresh DB."""
        result = get_silent_customers()
        assert result["success"]
        assert result["count"] == 0

    def test_get_silent_customers_found(self, temp_db):
        """Verify: silent customers detected with old last_contact."""
        _seed_customer(name="张三")
        # Force old last_contact date
        dm.execute_write(
            "UPDATE customers SET last_contact=? WHERE name=?",
            ("2020-01-01T00:00:00", "张三"),
        )
        result = get_silent_customers()
        assert result["success"]
        assert result["count"] >= 1


# ---------------------------------------------------------------------------
# update_customer_status
# ---------------------------------------------------------------------------


class TestUpdateCustomerStatus:
    def test_update_valid_status(self, temp_db):
        """Verify: valid status update succeeds."""
        cid = _seed_customer(name="张三")
        result = update_customer_status(cid, "active")
        assert result["success"]

    def test_update_invalid_status(self, temp_db):
        """Verify: invalid status rejected."""
        cid = _seed_customer(name="张三")
        result = update_customer_status(cid, "invalid_status")
        assert not result["success"]
        assert "无效状态" in result["error"]


# ---------------------------------------------------------------------------
# get_customer_stats
# ---------------------------------------------------------------------------


class TestGetCustomerStats:
    def test_stats_empty(self, temp_db):
        """Verify: stats on empty DB returns zeros."""
        result = get_customer_stats()
        assert result["success"]
        assert result["total"] == 0

    def test_stats_with_data(self, temp_db):
        """Verify: stats correctly count customers by status."""
        _seed_customer(name="张三")
        cid2 = _seed_customer(name="李四")
        update_customer_status(cid2, "active")
        result = get_customer_stats()
        assert result["success"]
        assert result["total"] == 2
        assert result["potential"] == 1
        assert result["active"] == 1


# ---------------------------------------------------------------------------
# add_follow_up / get_follow_ups
# ---------------------------------------------------------------------------


class TestFollowUps:
    def test_add_follow_up_success(self, temp_db):
        """Verify: follow-up record added successfully."""
        cid = _seed_customer(name="张三")
        result = add_follow_up(cid, "电话沟通")
        assert result["success"]
        assert "电话沟通" in result["message"]

    def test_add_follow_up_empty_customer_id(self, temp_db):
        """Verify: empty customer ID rejected."""
        result = add_follow_up("", "内容")
        assert not result["success"]
        assert "不能为空" in result["error"]

    def test_add_follow_up_empty_content(self, temp_db):
        """Verify: empty content rejected."""
        cid = _seed_customer(name="张三")
        result = add_follow_up(cid, "")
        assert not result["success"]
        assert "不能为空" in result["error"]

    def test_get_follow_ups(self, temp_db):
        """Verify: follow-ups retrieved for a customer."""
        cid = _seed_customer(name="张三")
        add_follow_up(cid, "第一次跟进")
        add_follow_up(cid, "第二次跟进")
        result = get_follow_ups(cid)
        assert result["success"]
        assert result["count"] == 2

    def test_get_follow_ups_empty_id(self, temp_db):
        """Verify: empty customer ID rejected in get_follow_ups."""
        result = get_follow_ups("")
        assert not result["success"]
        assert "不能为空" in result["error"]


# ---------------------------------------------------------------------------
# _handle_follow_up
# ---------------------------------------------------------------------------


class TestHandleFollowUp:
    def test_follow_up_existing_customer(self, temp_db):
        """Verify: follow-up added for existing customer by name."""
        _seed_customer(name="张总")
        result = _handle_follow_up("跟进张总")
        assert result["success"]
        assert "跟进张总" in result.get("message", "")

    def test_follow_up_nonexistent_customer(self, temp_db):
        """Verify: follow-up for non-existent customer returns error."""
        result = _handle_follow_up("跟进不存在的人")
        assert not result["success"]
        assert "请指定客户名称" in result["error"]

    def test_follow_up_no_name(self, temp_db):
        """Verify: follow-up with only keyword returns error."""
        result = _handle_follow_up("跟进")
        assert not result["success"]
        assert "请指定客户名称" in result["error"]


# ---------------------------------------------------------------------------
# _handle_search
# ---------------------------------------------------------------------------


class TestHandleSearch:
    def test_search_existing_customer(self, temp_db):
        """Verify: search finds existing customer by name."""
        _seed_customer(name="张三")
        result = _handle_search("帮我查张三的联系方式")
        assert result["success"]
        assert "张三" in result["customer"]["name"]

    def test_search_nonexistent(self, temp_db):
        """Verify: search for non-existent customer returns error."""
        result = _handle_search("帮我查不存在的人的联系方式")
        assert not result["success"]

    def test_search_no_name(self, temp_db):
        """Verify: search with only keywords returns error."""
        result = _handle_search("帮我查的联系方式")
        assert not result["success"]
        assert "请提供客户姓名" in result["error"]


# ---------------------------------------------------------------------------
# _handle_deal
# ---------------------------------------------------------------------------


class TestHandleDeal:
    def test_deal_existing_customer(self, temp_db):
        """Verify: deal recorded for existing customer with amount."""
        _seed_customer(name="张总")
        result = _handle_deal("张总成交了3000")
        assert result["success"]
        assert "合作记录已添加" in result.get("message", "")

    def test_deal_nonexistent_customer(self, temp_db):
        """Verify: deal for non-existent customer returns error."""
        result = _handle_deal("不存在的人成交了5000")
        assert not result["success"]
        assert "请指定客户名称" in result["error"]

    def test_deal_no_name(self, temp_db):
        """Verify: deal with only keywords returns error."""
        result = _handle_deal("成交了3000")
        assert not result["success"]
        assert "请指定客户名称" in result["error"]


# ---------------------------------------------------------------------------
# _handle_add_customer
# ---------------------------------------------------------------------------


class TestHandleAddCustomer:
    def test_add_customer_with_phone(self, temp_db):
        """Verify: customer added with phone number from text."""
        result = _handle_add_customer("添加客户张三，电话13800138000")
        assert result["success"]
        assert "张三" in result["message"]

    def test_add_customer_no_name(self, temp_db):
        """Verify: add customer without name returns error."""
        result = _handle_add_customer("添加客户")
        assert not result["success"]
        assert "请提供客户姓名" in result["error"]

    def test_add_customer_with_full_info(self, temp_db):
        """Verify: customer added with full info from text."""
        result = _handle_add_customer(
            "添加客户李四，电话13900139000，邮箱ls@test.com，公司：XYZ公司"
        )
        assert result["success"]


# ---------------------------------------------------------------------------
# execute_goal (分发路由)
# ---------------------------------------------------------------------------


class TestExecuteGoal:
    def test_dispatch_follow_up(self, temp_db):
        """Verify: execute_goal routes 跟进 to _handle_follow_up."""
        _seed_customer(name="张总")
        result = execute_goal("跟进张总")
        assert result["success"]

    def test_dispatch_silent_customers(self, temp_db):
        """Verify: execute_goal routes 沉默 to get_silent_customers."""
        result = execute_goal("查看沉默客户")
        assert result["success"]
        assert "customers" in result

    def test_dispatch_stats(self, temp_db):
        """Verify: execute_goal routes 统计 to get_customer_stats."""
        result = execute_goal("统计多少客户")
        assert result["success"]
        assert "total" in result

    def test_dispatch_search(self, temp_db):
        """Verify: execute_goal routes 查 to _handle_search."""
        _seed_customer(name="张三")
        result = execute_goal("查张三")
        assert result["success"]

    def test_dispatch_deal(self, temp_db):
        """Verify: execute_goal routes 成交 to _handle_deal."""
        _seed_customer(name="张总")
        result = execute_goal("张总成交了2000")
        assert result["success"]

    def test_dispatch_add_customer(self, temp_db):
        """Verify: execute_goal routes 添加客户 to _handle_add_customer."""
        result = execute_goal("添加客户王五，电话13800138000")
        assert result["success"]

    def test_dispatch_default_search(self, temp_db):
        """Verify: execute_goal default falls through to search_customers."""
        _seed_customer(name="张三")
        result = execute_goal("随便看看")
        assert result["success"]
        assert "customers" in result


# ---------------------------------------------------------------------------
# Undo functions
# ---------------------------------------------------------------------------


class TestUndoFunctions:
    def test_undo_add_customer_by_id(self, temp_db):
        """Verify: customer deleted by ID."""
        cid = _seed_customer(name="张三")
        result = undo_add_customer(customer_id=cid)
        assert result["success"]
        verify = get_customer(customer_id=cid)
        assert not verify["success"]

    def test_undo_add_customer_latest(self, temp_db):
        """Verify: latest customer deleted when no ID provided."""
        _seed_customer(name="张三")
        cid2 = _seed_customer(name="李四")
        result = undo_add_customer()
        assert result["success"]
        verify = get_customer(customer_id=cid2)
        assert not verify["success"]

    def test_undo_add_deal_by_id(self, temp_db):
        """Verify: deal deleted by ID."""
        cid = _seed_customer(name="张三")
        deal_result = add_deal(cid, "测试合作", amount=1000)
        result = undo_add_deal(deal_id=deal_result["id"])
        assert result["success"]

    def test_undo_add_deal_latest(self, temp_db):
        """Verify: latest deal deleted when no ID provided."""
        cid = _seed_customer(name="张三")
        add_deal(cid, "测试合作", amount=1000)
        result = undo_add_deal()
        assert result["success"]

    def test_undo_add_follow_up_by_id(self, temp_db):
        """Verify: follow-up deleted by ID."""
        cid = _seed_customer(name="张三")
        fu_result = add_follow_up(cid, "测试跟进")
        result = undo_add_follow_up(follow_up_id=fu_result["id"])
        assert result["success"]

    def test_undo_add_follow_up_latest(self, temp_db):
        """Verify: latest follow-up deleted when no ID provided."""
        cid = _seed_customer(name="张三")
        add_follow_up(cid, "测试跟进")
        result = undo_add_follow_up()
        assert result["success"]

    def test_undo_add_deal_no_records(self, temp_db):
        """Verify: undo deal with no records succeeds (no-op)."""
        result = undo_add_deal()
        assert result["success"]
