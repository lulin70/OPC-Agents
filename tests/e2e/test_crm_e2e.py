"""CRM 技能真实链路 E2E 测试（v1.0.0 批次 1.3 解冻）.

模拟一个真实运营人员的工作闭环：
    录入新客户 → 查客户 → 记录合作（首单）→ 跟进回访 → 识别沉默客户
    → 看漏斗统计 → 看单个客户生命周期 → 撤销误操作
全程使用真实技能函数 + 真实 SQLite（隔离到 tmp_path），不 mock 技能内部逻辑；
自然语言入口统一走 execute_goal（与用户实际说出口的话一致）。

PromiseLink 集成路径使用**真实 PromiseLinkClient + httpx.MockTransport**：
真实走完客户端状态机 / 有界重试 / schema 校验 / DTO 白名单映射 / 熔断，
但不发真实网络请求（外部网络边界是唯一被替换的部分）。

Iron Rule 遵守:
- Rule 4 (Side-Effect): 断言 DB 落库、敏感字段加密、审计日志、财务收入记录
- Rule 5 (User Journey): 以用户自然语言目标驱动，不直接调内部私有函数
- Rule 6 (E2E Release Gate): 真实组件优先；Mock 仅用于外部网络边界
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest

import opc_manager.crm_skill as crm_skill
import opc_manager.data_manager as dm
from opc_manager.crm_skill import (
    add_deal,
    execute_goal,
    get_customer,
    get_customer_stats,
    get_follow_ups,
    get_silent_customers,
    lifecycle_tracker,
    search_customers,
    undo_add_deal,
    update_customer_status,
)
from opc_manager.promiselink_client import PromiseLinkClient
from opc_manager.utils import SECONDS_PER_DAY

pytestmark = pytest.mark.e2e

OLD_CONTACT = "2020-01-01T00:00:00"

# ============================================================
# Fixtures：真实 DB + 审计日志隔离
# ============================================================


@pytest.fixture
def crm_env(tmp_path, monkeypatch):
    """隔离的真实 CRM 运行环境（真实 SQLite，不污染 data/opc_data.db）。

    - OPC_DATA_DIR / OPC_ENCRYPTION_KEY 重定向
    - data_manager 模块级状态复位（避免上一用例的连接残留）
    - AuditLogger 指向临时 jsonl
    - 默认关闭 PromiseLink（PROMISELINK_ENABLED 未设置）
    """
    from opc_manager.tool_audit_logger import AuditLogger

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("OPC_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OPC_ENCRYPTION_KEY", "test-e2e-key-for-isolated-crm-db")
    monkeypatch.delenv("PROMISELINK_ENABLED", raising=False)
    monkeypatch.delenv("PROMISELINK_BASE_URL", raising=False)
    monkeypatch.delenv("PROMISELINK_TOKEN", raising=False)

    orig_data_dir = dm.DATA_DIR
    orig_db_path = dm.DB_PATH
    orig_initialized = dm._db_initialized
    dm.DATA_DIR = str(data_dir)
    dm.DB_PATH = str(data_dir / "opc_data.db")
    dm._db_initialized = False
    if getattr(dm._local, "conn", None) is not None:
        try:
            dm._local.conn.close()
        except Exception:
            pass
        dm._local.conn = None

    orig_log_file = AuditLogger._log_file
    audit_log_file = str(logs_dir / "audit.jsonl")
    AuditLogger.configure(audit_log_file)

    dm.init_db()

    yield {
        "data_dir": str(data_dir),
        "audit_log_file": audit_log_file,
    }

    if getattr(dm._local, "conn", None) is not None:
        try:
            dm._local.conn.close()
        except Exception:
            pass
        dm._local.conn = None
    dm.DATA_DIR = orig_data_dir
    dm.DB_PATH = orig_db_path
    dm._db_initialized = orig_initialized
    AuditLogger.configure(orig_log_file)


@pytest.fixture
def audit_events(crm_env):
    """读取审计日志中的 event_type 列表。"""

    def _read() -> List[str]:
        path = Path(crm_env["audit_log_file"])
        if not path.exists():
            return []
        return [
            json.loads(line)["event_type"]
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    return _read


# ============================================================
# 辅助：真实 PromiseLinkClient + MockTransport（仅替换网络边界）
# ============================================================


def _mock_client(handler, **kwargs: Any) -> PromiseLinkClient:
    """构造真实客户端，transport 换成 MockTransport（无真实网络）。"""
    return PromiseLinkClient(
        base_url="http://promiselink.test",
        token="e2e-token",
        enabled=True,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _seconds: None,
        **kwargs,
    )


def _inject_client(monkeypatch, client: PromiseLinkClient) -> None:
    monkeypatch.setattr(crm_skill, "_get_client", lambda: client)


DORMANT_ITEM = {
    "entity_id": "ent-001",
    "name": "李总",
    "company": "远方科技",
    "dormant_days": 92,
    "reactivation_score": 0.78,
    "last_interaction": "2026-05-01T10:00:00Z",
    "last_event_summary": "上次聊到展会",
    "reason": "超过 90 天未互动",
    "icebreaker_topic": "上次聊到的行业展会",
    "pending_their_promises": 0,
    "relationship_stage": "cooperating",
    "internal_debug_field": "不应透传",
}


def _dormant_ok(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/api/v1/entities/dormant"
    assert request.url.params.get("min_days") is not None
    assert request.headers["Authorization"] == "Bearer e2e-token"
    return httpx.Response(200, json=[DORMANT_ITEM])


def _stage_ok(payload: Dict[str, Any]):
    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/entities/ent-001/stage-info"
        return httpx.Response(200, json=payload)

    return _handler


def _always(status_code: int):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "boom"})

    return _handler


def _seed_customer(name: str, company: str = "", phone: str = "") -> str:
    result = execute_goal(f"添加客户{name}，电话{phone}，公司{company}")
    assert result["success"], result
    return result["id"]


# ============================================================
# 链路 1：新客户从录入到首单
# ============================================================


class TestJourneyNewCustomerToFirstDeal:
    def test_01_record_new_customer_by_natural_language(self, crm_env):
        """Verify: 用户说一句自然语言即可录入客户，且返回可用的客户 ID。"""
        result = execute_goal("添加客户张三，电话13800138000，公司远方科技")
        assert result["success"] is True
        assert result["id"]

    def test_02_new_customer_is_searchable(self, crm_env):
        """Verify: 录入后立即可被检索到。"""
        _seed_customer("张三", company="远方科技", phone="13800138000")
        found = search_customers(company="远方")
        assert found["success"] is True
        assert found["count"] == 1
        assert found["customers"][0]["name"] == "张三"

    def test_03_customer_detail_decrypts_contact(self, crm_env):
        """Verify: 详情页读到的是解密后的真实手机号（而非密文）。"""
        cid = _seed_customer("张三", phone="13800138000")
        detail = get_customer(customer_id=cid)
        assert detail["success"] is True
        assert detail["customer"]["phone"] == "13800138000"

    def test_04_phone_stored_encrypted_at_rest(self, crm_env):
        """Verify: 落库的手机号是密文（Side-Effect：真实 DB 列内容）。"""
        cid = _seed_customer("张三", phone="13800138000")
        rows = dm.execute_query("SELECT phone FROM customers WHERE id=?", (cid,))
        stored = rows[0]["phone"]
        assert stored and stored != "13800138000"

    def test_05_deal_recorded_by_natural_language(self, crm_env):
        """Verify: 用户说「成交了」即记录合作并升级客户状态。"""
        _seed_customer("张总", company="远方科技", phone="13800138000")
        result = execute_goal("张总成交了3000")
        assert result["success"] is True
        assert "合作记录已添加" in result["message"]

    def test_06_first_deal_promotes_customer_status(self, crm_env):
        """Verify: 首单后客户状态由 potential 升为 first_deal。"""
        cid = _seed_customer("张总", phone="13800138000")
        execute_goal("张总成交了3000")
        assert get_customer(customer_id=cid)["customer"]["status"] == "first_deal"

    def test_07_second_deal_promotes_to_active(self, crm_env):
        """Verify: 二次成交后状态升为 active（漏斗继续推进）。"""
        cid = _seed_customer("张总", phone="13800138000")
        add_deal(cid, "首单", amount=1000, status="closed_won")
        add_deal(cid, "二单", amount=2000, status="closed_won")
        assert get_customer(customer_id=cid)["customer"]["status"] == "active"

    def test_08_deal_writes_finance_income_record(self, crm_env):
        """Verify: 成交同时自动落一条财务收入（跨技能副作用）。"""
        cid = _seed_customer("张总", phone="13800138000")
        add_deal(cid, "首单合作", amount=3000, status="closed_won")
        rows = dm.execute_query(
            "SELECT * FROM finance_records WHERE type='income' AND amount=3000"
        )
        assert len(rows) == 1
        assert rows[0]["note"] or rows[0]["source"] is not None

    def test_09_audit_log_records_customer_and_deal(self, crm_env, audit_events):
        """Verify: 审计日志留痕（录入 + 合作两条事件）。"""
        cid = _seed_customer("张总", phone="13800138000")
        add_deal(cid, "首单合作", amount=3000, status="closed_won")
        events = audit_events()
        assert "crm_customer_added" in events
        assert "crm_deal_added" in events

    def test_10_lifecycle_view_after_first_deal(self, crm_env):
        """Verify: 首单后生命周期视图反映 1 单合作 + 首次合作阶段。"""
        cid = _seed_customer("张总", phone="13800138000")
        add_deal(cid, "首单合作", amount=3000, status="closed_won")
        view = lifecycle_tracker(customer_id=cid)
        assert view["success"] is True
        assert view["deal_count"] == 1
        assert view["status"] == "first_deal"
        assert view["stage"] == "首次合作"


# ============================================================
# 链路 2：跟进回访与沉默客户唤醒
# ============================================================


class TestJourneyFollowUpAndSilentCustomers:
    def test_11_follow_up_by_natural_language(self, crm_env):
        """Verify: 用户说「跟进张三」即写入跟进记录。"""
        _seed_customer("张三", phone="13800138000")
        result = execute_goal("跟进张三")
        assert result["success"] is True
        assert "跟进记录已添加" in result["message"]

    def test_12_follow_up_is_listed(self, crm_env):
        """Verify: 跟进记录可回查。"""
        cid = _seed_customer("张三", phone="13800138000")
        execute_goal("跟进张三")
        follow_ups = get_follow_ups(cid)
        assert follow_ups["success"] is True
        assert follow_ups["count"] == 1

    def test_13_follow_up_refreshes_last_contact(self, crm_env):
        """Verify: 跟进后 last_contact 被刷新，客户不再算沉默。"""
        cid = _seed_customer("张三", phone="13800138000")
        dm.execute_write(
            "UPDATE customers SET last_contact=? WHERE id=?", (OLD_CONTACT, cid)
        )
        assert get_silent_customers()["count"] == 1
        execute_goal("跟进张三")
        assert get_silent_customers()["count"] == 0

    def test_14_silent_customer_detected_by_natural_language(self, crm_env):
        """Verify: 用户问「哪些客户很久没联系」→ 走真实沉默扫描。"""
        cid = _seed_customer("张三", phone="13800138000")
        dm.execute_write(
            "UPDATE customers SET last_contact=? WHERE id=?", (OLD_CONTACT, cid)
        )
        result = execute_goal("哪些客户很久没联系了")
        assert result["success"] is True
        assert result["count"] == 1

    def test_15_silent_scan_ignores_lost_customers(self, crm_env):
        """Verify: 已流失客户不再进入沉默唤醒队列。"""
        cid = _seed_customer("张三", phone="13800138000")
        dm.execute_write(
            "UPDATE customers SET last_contact=? WHERE id=?", (OLD_CONTACT, cid)
        )
        assert update_customer_status(cid, "lost")["success"]
        assert get_silent_customers()["count"] == 0

    def test_16_silent_threshold_is_configurable(self, crm_env):
        """Verify: 阈值可调（3 天未联系：按 7 天算不算沉默，按 2 天算沉默）。"""
        cid = _seed_customer("张三", phone="13800138000")
        three_days_ago = time.strftime(
            "%Y-%m-%dT%H:%M:%S",
            time.localtime(time.time() - 3 * SECONDS_PER_DAY),
        )
        dm.execute_write(
            "UPDATE customers SET last_contact=? WHERE id=?", (three_days_ago, cid)
        )
        assert get_silent_customers(days=7)["count"] == 0
        assert get_silent_customers(days=2)["count"] == 1

    def test_17_lifecycle_counts_follow_ups(self, crm_env):
        """Verify: 生命周期视图统计跟进次数。"""
        cid = _seed_customer("张三", phone="13800138000")
        execute_goal("跟进张三")
        execute_goal("跟进张三")
        assert lifecycle_tracker(customer_id=cid)["follow_up_count"] == 2


# ============================================================
# 链路 3：漏斗统计与生命周期视图
# ============================================================


class TestJourneyStatsAndLifecycle:
    def test_18_stats_reflect_funnel(self, crm_env):
        """Verify: 统计视图按状态给出漏斗分布。"""
        _seed_customer("张三", phone="13800138000")
        cid2 = _seed_customer("李四", phone="13800138001")
        add_deal(cid2, "首单", amount=1000, status="closed_won")
        stats = get_customer_stats()
        assert stats["success"] is True
        assert stats["total"] == 2
        assert stats["potential"] == 1
        assert stats["first_deal"] == 1

    def test_19_stats_by_natural_language(self, crm_env):
        """Verify: 用户问「我有多少客户」→ 走真实统计。"""
        _seed_customer("张三", phone="13800138000")
        result = execute_goal("我有多少客户")
        assert result["success"] is True
        assert result["total"] == 1

    def test_20_lifecycle_by_name(self, crm_env):
        """Verify: 不记得 ID 时可用姓名查生命周期。"""
        _seed_customer("李四", phone="13800138001")
        view = lifecycle_tracker(name="李四")
        assert view["success"] is True
        assert view["name"] == "李四"

    def test_21_lifecycle_requires_identifier(self, crm_env):
        """Verify: 未提供 ID/姓名时给出可操作错误。"""
        view = lifecycle_tracker()
        assert view["success"] is False
        assert "请提供" in view["error"]

    def test_22_lifecycle_unknown_customer(self, crm_env):
        """Verify: 客户不存在时明确报错，不返回空壳。"""
        view = lifecycle_tracker(customer_id="no-such-id")
        assert view["success"] is False
        assert "未找到客户" in view["error"]

    def test_23_lifecycle_silent_days_tracks_last_contact(self, crm_env):
        """Verify: 沉默天数与 last_contact 一致。"""
        cid = _seed_customer("张三", phone="13800138000")
        dm.execute_write(
            "UPDATE customers SET last_contact=? WHERE id=?", (OLD_CONTACT, cid)
        )
        assert lifecycle_tracker(customer_id=cid)["silent_days"] > 1000

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
    def test_24_to_28_lifecycle_stage_labels(self, crm_env, status, label):
        """Verify: 5 个合法状态各有对应中文阶段标签。"""
        cid = _seed_customer("王五", phone="13800138002")
        assert update_customer_status(cid, status)["success"]
        view = lifecycle_tracker(customer_id=cid)
        assert view["status"] == status
        assert view["stage"] == label

    def test_29_invalid_status_rejected(self, crm_env):
        """Verify: 非法状态被拒绝，不会污染数据。"""
        cid = _seed_customer("王五", phone="13800138002")
        result = update_customer_status(cid, "not-a-status")
        assert result["success"] is False
        assert get_customer(customer_id=cid)["customer"]["status"] == "potential"


# ============================================================
# 链路 4：误操作撤销
# ============================================================


class TestJourneyUndo:
    def test_30_undo_latest_deal(self, crm_env):
        """Verify: 误记的合作可撤销。"""
        cid = _seed_customer("张总", phone="13800138000")
        add_deal(cid, "误记合作", amount=999)
        assert undo_add_deal()["success"] is True
        assert lifecycle_tracker(customer_id=cid)["deal_count"] == 0


# ============================================================
# 链路 5：PromiseLink 集成（真实客户端 + MockTransport）
# ============================================================


class TestPromiseLinkIntegration:
    def test_31_disabled_by_default_keeps_local_capability(self, crm_env):
        """Verify: 未启用集成时本地能力完整，并显式给出 DISABLED。"""
        cid = _seed_customer("张三", phone="13800138000")
        dm.execute_write(
            "UPDATE customers SET last_contact=? WHERE id=?", (OLD_CONTACT, cid)
        )
        result = get_silent_customers()
        assert result["count"] == 1
        assert result["promiselink_state"] == "DISABLED"
        assert "promiselink" not in result

    def test_32_enabled_but_unconfigured_reports_state(self, crm_env, monkeypatch):
        """Verify: 启用但缺 base_url/token → UNCONFIGURED（不静默、不打网络）。"""
        monkeypatch.setenv("PROMISELINK_ENABLED", "true")
        result = get_silent_customers()
        assert result["promiselink_state"] == "UNCONFIGURED"

    def test_33_available_returns_mapped_dormant_entities(self, crm_env, monkeypatch):
        """Verify: 集成可用时追加唤醒分/破冰主题等字段。"""
        _inject_client(monkeypatch, _mock_client(_dormant_ok))
        result = get_silent_customers(days=90)
        assert result["source"] == "promiselink"
        assert result["count"] == 0  # 本地无沉默客户
        assert result["promiselink"][0]["reactivation_score"] == 0.78
        assert result["promiselink"][0]["icebreaker_topic"] == "上次聊到的行业展会"

    def test_34_dormant_mapping_whitelist(self, crm_env, monkeypatch):
        """Verify: 只映射白名单字段，未声明的内部字段不透传。"""
        _inject_client(monkeypatch, _mock_client(_dormant_ok))
        mapped = get_silent_customers(days=90)["promiselink"][0]
        assert "internal_debug_field" not in mapped
        assert set(mapped) == {
            "entity_id",
            "name",
            "company",
            "dormant_days",
            "reactivation_score",
            "icebreaker_topic",
            "relationship_stage",
            "last_interaction",
            "reason",
        }

    def test_35_dormant_uses_min_days_query_param(self, crm_env, monkeypatch):
        """Verify: 用户给的阈值真实传到 /entities/dormant?min_days=N。"""
        seen: List[Optional[str]] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.params.get("min_days"))
            return httpx.Response(200, json=[])

        _inject_client(monkeypatch, _mock_client(_handler))
        get_silent_customers(days=45)
        assert seen == ["45"]

    def test_36_dormant_schema_mismatch_is_explicit(self, crm_env, monkeypatch):
        """Verify: 响应契约不匹配 → SCHEMA_MISMATCH，本地结果不受影响。"""
        _inject_client(
            monkeypatch,
            _mock_client(lambda request: httpx.Response(200, json={"items": []})),
        )
        result = get_silent_customers()
        assert result["success"] is True
        assert result["promiselink_state"] == "SCHEMA_MISMATCH"

    def test_37_dormant_server_error_degrades_after_retries(self, crm_env, monkeypatch):
        """Verify: 5xx 经有界重试后降级为 DEGRADED，且确实重试过。"""
        attempts: List[int] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            return httpx.Response(500, json={"detail": "boom"})

        _inject_client(monkeypatch, _mock_client(_handler, max_retries=2))
        result = get_silent_customers()
        assert result["promiselink_state"] == "DEGRADED"
        assert len(attempts) == 3  # 首次 + 2 次重试

    def test_38_circuit_opens_and_stops_calling_network(self, crm_env, monkeypatch):
        """Verify: 连续失败后熔断，后续调用不再打网络（fail-fast）。"""
        attempts: List[int] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            return httpx.Response(500, json={"detail": "boom"})

        client = _mock_client(_handler, max_retries=0)
        _inject_client(monkeypatch, client)

        states = [get_silent_customers()["promiselink_state"] for _ in range(6)]
        assert states[:5] == ["DEGRADED"] * 5
        assert states[5] == "CIRCUIT_OPEN"
        assert len(attempts) == 5  # 熔断后第 6 次未发起请求

    def test_39_stage_info_available_appends_payload(self, crm_env, monkeypatch):
        """Verify: 传 entity_id 且集成可用时追加真实 stage-info 载荷。"""
        cid = _seed_customer("张三", phone="13800138000")
        payload = {"stage": "cooperating", "since": "2026-01-01", "score": 0.9}
        _inject_client(monkeypatch, _mock_client(_stage_ok(payload)))
        view = lifecycle_tracker(customer_id=cid, entity_id="ent-001")
        assert view["promiselink_stage"] == payload
        assert view["deal_count"] == 0  # 本地视图不受影响

    def test_40_stage_info_without_entity_id_never_calls_network(
        self, crm_env, monkeypatch
    ):
        """Verify: 不传 entity_id 时完全不触碰 PromiseLink。"""
        cid = _seed_customer("张三", phone="13800138000")
        calls: List[str] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            return httpx.Response(200, json={})

        _inject_client(monkeypatch, _mock_client(_handler))
        view = lifecycle_tracker(customer_id=cid)
        assert calls == []
        assert "promiselink_stage" not in view
        assert "promiselink_state" not in view

    def test_41_stage_info_disabled_reports_state(self, crm_env, monkeypatch):
        """Verify: 集成关闭时显式给出 DISABLED，本地视图仍完整。"""
        cid = _seed_customer("张三", phone="13800138000")
        _inject_client(
            monkeypatch,
            PromiseLinkClient(
                base_url="http://promiselink.test", token="t", enabled=False
            ),
        )
        view = lifecycle_tracker(customer_id=cid, entity_id="ent-001")
        assert view["success"] is True
        assert view["promiselink_state"] == "DISABLED"
        assert view["stage"] == "潜在客户"

    def test_42_stage_info_server_error_reports_degraded(self, crm_env, monkeypatch):
        """Verify: stage-info 失败降级为 DEGRADED，不影响本地字段。"""
        cid = _seed_customer("张三", phone="13800138000")
        _inject_client(monkeypatch, _mock_client(_always(503), max_retries=0))
        view = lifecycle_tracker(customer_id=cid, entity_id="ent-001")
        assert view["success"] is True
        assert view["promiselink_state"] == "DEGRADED"
        assert view["name"] == "张三"

    def test_43_no_token_leaked_into_result(self, crm_env, monkeypatch):
        """Verify: 客户端凭证绝不出现在技能返回值中（安全护栏）。"""
        _inject_client(monkeypatch, _mock_client(_dormant_ok))
        result = get_silent_customers(days=90)
        assert "e2e-token" not in json.dumps(result, ensure_ascii=False, default=str)
