"""CRM Skill 覆盖率补充测试

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
- PromiseLink 集成（v1.0.0 批次 1.3 解冻新增）：
  _get_client / _map_dormant_entity / _promiselink_dormant / _promiselink_stage /
  get_silent_customers 集成分支 / lifecycle_tracker 全分支

数据库使用临时目录 (OPC_DATA_DIR=tmp_path)，不污染真实数据。
PromiseLink 相关用例使用最小替身客户端，不发真实网络请求。
"""

import pytest

import opc_manager.crm_skill as crm_skill
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
    lifecycle_tracker,
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


# ---------------------------------------------------------------------------
# PromiseLink 集成（v1.0.0 批次 1.3 解冻新增）
# ---------------------------------------------------------------------------


class _FakeState:
    def __init__(self, value: str):
        self.value = value


class _FakeResult:
    def __init__(self, success: bool, state: str, data=None):
        self.success = success
        self.state = _FakeState(state)
        self.data = data


class _FakeClient:
    """crm_skill 用到的 PromiseLinkClient 最小替身（无网络）。"""

    def __init__(self, state="AVAILABLE", result=None, raise_on=""):
        self._state = _FakeState(state)
        self._result = result
        self._raise_on = raise_on
        self.calls = []

    def state(self):
        return self._state

    def list_dormant_entities(self, min_days):
        self.calls.append(("list_dormant_entities", min_days))
        if self._raise_on == "list_dormant_entities":
            raise RuntimeError("boom")
        return self._result

    def get_entity_stage_info(self, entity_id):
        self.calls.append(("get_entity_stage_info", entity_id))
        if self._raise_on == "get_entity_stage_info":
            raise RuntimeError("boom")
        return self._result


def _inject_client(monkeypatch, client):
    """把 crm_skill 的模块级工厂替换为返回指定替身客户端。"""
    monkeypatch.setattr(crm_skill, "_get_client", lambda: client)


class TestGetClientFactory:
    def test_disabled_by_default(self, monkeypatch):
        """Verify: 未设置 PROMISELINK_ENABLED 时客户端为 DISABLED。"""
        monkeypatch.delenv("PROMISELINK_ENABLED", raising=False)
        monkeypatch.delenv("PROMISELINK_BASE_URL", raising=False)
        monkeypatch.delenv("PROMISELINK_TOKEN", raising=False)
        assert crm_skill._get_client().state().value == "DISABLED"

    def test_enabled_without_config_is_unconfigured(self, monkeypatch):
        """Verify: 开启但缺 base_url/token 时为 UNCONFIGURED。"""
        monkeypatch.setenv("PROMISELINK_ENABLED", "true")
        monkeypatch.delenv("PROMISELINK_BASE_URL", raising=False)
        monkeypatch.delenv("PROMISELINK_TOKEN", raising=False)
        assert crm_skill._get_client().state().value == "UNCONFIGURED"


class TestMapDormantEntity:
    def test_whitelist_only(self):
        """Verify: 仅映射白名单字段，未知字段不透传。"""
        mapped = crm_skill._map_dormant_entity(
            {
                "entity_id": "e1",
                "name": "张三",
                "reactivation_score": 0.78,
                "icebreaker_topic": "上次聊到的展会",
                "secret_internal_field": "不应出现",
            }
        )
        assert mapped["entity_id"] == "e1"
        assert mapped["reactivation_score"] == 0.78
        assert mapped["icebreaker_topic"] == "上次聊到的展会"
        assert "secret_internal_field" not in mapped

    def test_non_dict_item(self):
        """Verify: 非 dict 载荷原样放入 raw，不抛异常。"""
        assert crm_skill._map_dormant_entity("oops") == {"raw": "oops"}


class TestGetSilentCustomersIntegration:
    def test_local_keys_intact_when_disabled(self, temp_db, monkeypatch):
        """Verify: 集成关闭时本地四键语义不变，且显式给出 DISABLED。"""
        _seed_customer(name="张三")
        dm.execute_write(
            "UPDATE customers SET last_contact=? WHERE name=?",
            ("2020-01-01T00:00:00", "张三"),
        )
        _inject_client(monkeypatch, _FakeClient(state="DISABLED"))
        result = get_silent_customers()
        assert result["success"] is True
        assert result["count"] == 1
        assert result["silent_days"] == 30
        assert result["promiselink_state"] == "DISABLED"
        assert "promiselink" not in result
        assert "source" not in result

    def test_unconfigured_state_reported(self, temp_db, monkeypatch):
        """Verify: 未配置时显式给出 UNCONFIGURED。"""
        _inject_client(monkeypatch, _FakeClient(state="UNCONFIGURED"))
        result = get_silent_customers()
        assert result["promiselink_state"] == "UNCONFIGURED"

    def test_available_appends_mapped_entities(self, temp_db, monkeypatch):
        """Verify: 可用时追加 promiselink 列表与 source，且 min_days 透传。"""
        client = _FakeClient(
            state="AVAILABLE",
            result=_FakeResult(
                True,
                "AVAILABLE",
                data=[
                    {
                        "entity_id": "e1",
                        "name": "李四",
                        "dormant_days": 92,
                        "reactivation_score": 0.78,
                        "icebreaker_topic": "展会",
                    }
                ],
            ),
        )
        _inject_client(monkeypatch, client)
        result = get_silent_customers(days=45)
        assert result["source"] == "promiselink"
        assert result["promiselink"][0]["name"] == "李四"
        assert result["promiselink"][0]["reactivation_score"] == 0.78
        assert result["silent_days"] == 45
        assert client.calls == [("list_dormant_entities", 45)]

    def test_available_with_empty_payload(self, temp_db, monkeypatch):
        """Verify: 可用但无沉默实体时返回空列表（不报错）。"""
        _inject_client(
            monkeypatch,
            _FakeClient(
                state="AVAILABLE", result=_FakeResult(True, "AVAILABLE", data=None)
            ),
        )
        result = get_silent_customers()
        assert result["promiselink"] == []
        assert result["source"] == "promiselink"

    def test_available_but_request_degrades(self, temp_db, monkeypatch):
        """Verify: 请求失败时给出 DEGRADED，本地结果仍可用。"""
        _inject_client(
            monkeypatch,
            _FakeClient(state="AVAILABLE", result=_FakeResult(False, "DEGRADED")),
        )
        result = get_silent_customers()
        assert result["success"] is True
        assert result["promiselink_state"] == "DEGRADED"

    def test_schema_mismatch_reported(self, temp_db, monkeypatch):
        """Verify: schema 不匹配时显式给出 SCHEMA_MISMATCH。"""
        _inject_client(
            monkeypatch,
            _FakeClient(
                state="AVAILABLE", result=_FakeResult(False, "SCHEMA_MISMATCH")
            ),
        )
        result = get_silent_customers()
        assert result["promiselink_state"] == "SCHEMA_MISMATCH"

    def test_client_factory_raises_degrades(self, temp_db, monkeypatch):
        """Verify: 工厂本身抛异常时不冒泡，降级为 DEGRADED。"""

        def _boom():
            raise RuntimeError("factory down")

        monkeypatch.setattr(crm_skill, "_get_client", _boom)
        result = get_silent_customers()
        assert result["success"] is True
        assert result["promiselink_state"] == "DEGRADED"


class TestSilentDaysSince:
    def test_empty_returns_zero(self):
        assert crm_skill._silent_days_since("") == 0

    def test_unparsable_returns_zero(self):
        assert crm_skill._silent_days_since("not-a-date") == 0

    def test_old_date_counts_days(self):
        assert crm_skill._silent_days_since("2020-01-01T00:00:00") > 1000


class TestLifecycleTracker:
    def test_by_customer_id(self, temp_db):
        """Verify: 本地生命周期视图字段齐全。"""
        cid = _seed_customer(name="张三", company="测试公司")
        result = lifecycle_tracker(customer_id=cid)
        assert result["success"] is True
        assert result["customer_id"] == cid
        assert result["name"] == "张三"
        assert result["company"] == "测试公司"
        assert result["status"] == "potential"
        assert result["stage"] == "潜在客户"
        assert result["deal_count"] == 0
        assert result["follow_up_count"] == 0
        assert result["silent_days"] == 0

    def test_by_name(self, temp_db):
        """Verify: 按姓名可查到生命周期视图。"""
        _seed_customer(name="李四")
        result = lifecycle_tracker(name="李四")
        assert result["success"] is True
        assert result["name"] == "李四"

    def test_missing_args(self, temp_db):
        """Verify: 未给 ID/姓名时返回错误。"""
        result = lifecycle_tracker()
        assert result["success"] is False
        assert "请提供" in result["error"]

    def test_not_found(self, temp_db):
        """Verify: 客户不存在时返回错误。"""
        result = lifecycle_tracker(customer_id="no-such-id")
        assert result["success"] is False

    def test_counts_and_stage_reflect_data(self, temp_db):
        """Verify: 合作/跟进计数与状态映射正确。"""
        cid = _seed_customer(name="张总")
        add_deal(cid, "首单合作", amount=1000, status="closed_won")
        add_follow_up(cid, "回访一次")
        result = lifecycle_tracker(customer_id=cid)
        assert result["deal_count"] == 1
        assert result["follow_up_count"] == 1
        assert result["status"] == "first_deal"
        assert result["stage"] == "首次合作"

    @pytest.mark.parametrize(
        "status,label",
        [
            ("potential", "潜在客户"),
            ("first_deal", "首次合作"),
            ("active", "活跃"),
            ("silent", "沉默"),
            ("lost", "流失"),
        ],
    )
    def test_stage_label_covers_all_statuses(self, temp_db, status, label):
        """Verify: 5 个受约束状态各有对应中文阶段标签。"""
        cid = _seed_customer(name="王五")
        assert update_customer_status(cid, status)["success"]
        result = lifecycle_tracker(customer_id=cid)
        assert result["status"] == status
        assert result["stage"] == label

    def test_no_entity_id_skips_promiselink(self, temp_db, monkeypatch):
        """Verify: 不传 entity_id 时不触碰 PromiseLink（无网络副作用）。"""
        cid = _seed_customer(name="张三")
        client = _FakeClient(
            state="AVAILABLE", result=_FakeResult(True, "AVAILABLE", {})
        )
        _inject_client(monkeypatch, client)
        result = lifecycle_tracker(customer_id=cid)
        assert "promiselink_stage" not in result
        assert "promiselink_state" not in result
        assert client.calls == []

    def test_entity_id_with_integration_disabled(self, temp_db, monkeypatch):
        """Verify: 传 entity_id 但集成关闭时显式给出 DISABLED。"""
        cid = _seed_customer(name="张三")
        _inject_client(monkeypatch, _FakeClient(state="DISABLED"))
        result = lifecycle_tracker(customer_id=cid, entity_id="e1")
        assert result["promiselink_state"] == "DISABLED"
        assert "promiselink_stage" not in result

    def test_entity_id_available_appends_stage(self, temp_db, monkeypatch):
        """Verify: 集成可用时追加 promiselink_stage 原始载荷。"""
        cid = _seed_customer(name="张三")
        payload = {"stage": "active", "since": "2026-01-01"}
        client = _FakeClient(
            state="AVAILABLE", result=_FakeResult(True, "AVAILABLE", data=payload)
        )
        _inject_client(monkeypatch, client)
        result = lifecycle_tracker(customer_id=cid, entity_id="e1")
        assert result["promiselink_stage"] == payload
        assert client.calls == [("get_entity_stage_info", "e1")]

    def test_entity_id_available_but_request_fails(self, temp_db, monkeypatch):
        """Verify: 请求失败时给出显式状态，本地视图不受影响。"""
        cid = _seed_customer(name="张三")
        _inject_client(
            monkeypatch,
            _FakeClient(
                state="AVAILABLE", result=_FakeResult(False, "SCHEMA_MISMATCH")
            ),
        )
        result = lifecycle_tracker(customer_id=cid, entity_id="e1")
        assert result["success"] is True
        assert result["promiselink_state"] == "SCHEMA_MISMATCH"

    def test_entity_id_client_raises_degrades(self, temp_db, monkeypatch):
        """Verify: 客户端抛异常时不冒泡，降级为 DEGRADED。"""
        cid = _seed_customer(name="张三")
        _inject_client(
            monkeypatch,
            _FakeClient(state="AVAILABLE", raise_on="get_entity_stage_info"),
        )
        result = lifecycle_tracker(customer_id=cid, entity_id="e1")
        assert result["success"] is True
        assert result["promiselink_state"] == "DEGRADED"
