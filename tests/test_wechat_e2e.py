"""
Enterprise WeChat E2E Integration Tests for OPC-Agents v0.2.0

Tests the complete message flow:
User Message → WeChatGateway.verify_signature → decrypt → parse
→ WeChatAgentBridge._on_message → _run_agent → AgentLoop.run
→ _format_response → WeChatResponse.to_xml → return to user

Coverage:
- Gateway layer (6 tests)
- Bridge layer (8 tests)
- Bridge+AgentLoop integration (8 tests)
- Full E2E flow (5 tests)
Total: 27+ tests
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from opc_manager.experimental.wechat_gateway import (
    WeChatGateway,
    WeChatMessage,
    WeChatResponse,
    WeChatMsgType,
)
from opc_manager.experimental.wechat_agent import WeChatAgentBridge
from opc_manager.confirmer import ConfirmationRequest, ConfirmationResult, RiskLevel

# ============================================================================
# Part 1: Gateway Layer Tests (补充test_wechat_gateway.py缺失的用例)
# ============================================================================


class TestGatewayEncryptedMessage:
    """测试加密消息完整流程"""

    @pytest.mark.asyncio
    async def test_handle_callback_with_encrypted_msg(self):
        """加密消息完整处理流程"""
        gw = WeChatGateway(token="test_token", encoding_aes_key="dummy_key_for_test")
        handler_called = []

        async def mock_handler(msg):
            handler_called.append(msg)
            return WeChatResponse(content="收到加密消息")

        gw.set_message_handler(mock_handler)

        xml = """<xml>
<ToUserName><![CDATA[toUser]]></ToUserName>
<FromUserName><![CDATA[fromUser]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[hello]]></Content>
</xml>"""

        ts, nonce = "1234567890", "abc123"
        arr = sorted(["test_token", ts, nonce])
        sig = __import__("hashlib").sha1("".join(arr).encode()).hexdigest()

        result = await gw.handle_callback(
            {"signature": sig, "timestamp": ts, "nonce": nonce, "encrypt_type": "aes"},
            xml,
        )

        assert len(handler_called) == 1
        assert "收到加密消息" in result

    @pytest.mark.asyncio
    async def test_handle_callback_with_plain_text(self):
        """明文消息处理流程"""
        gw = WeChatGateway(token="test")
        handler_called = []

        async def mock_handler(msg):
            handler_called.append(msg)
            return WeChatResponse(content="收到明文")

        gw.set_message_handler(mock_handler)

        xml = """<xml><ToUserName><![CDATA[t]]></ToUserName>
<FromUserName><![CDATA[f]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[plain text]]></Content></xml>"""

        ts, nonce = "1", "1"
        arr = sorted(["test", ts, nonce])
        sig = __import__("hashlib").sha1("".join(arr).encode()).hexdigest()

        result = await gw.handle_callback(
            {"signature": sig, "timestamp": ts, "nonce": nonce}, xml
        )

        assert len(handler_called) == 1
        assert "收到明文" in result

    @pytest.mark.asyncio
    async def test_handle_callback_no_handler(self):
        """无handler时返回success"""
        gw = WeChatGateway(token="test")

        xml = """<xml><ToUserName><![CDATA[t]]></ToUserName>
<FromUserName><![CDATA[f]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[test]]></Content></xml>"""

        ts, nonce = "1", "1"
        arr = sorted(["test", ts, nonce])
        sig = __import__("hashlib").sha1("".join(arr).encode()).hexdigest()

        result = await gw.handle_callback(
            {"signature": sig, "timestamp": ts, "nonce": nonce}, xml
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_handle_callback_event_subscribe(self):
        """关注事件处理"""
        gw = WeChatGateway(token="test")

        xml = """<xml><ToUserName><![CDATA[t]]></ToUserName>
<FromUserName><![CDATA[f]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[event]]></MsgType>
<Event><![CDATA[subscribe]]></Event></xml>"""

        ts, nonce = "1", "1"
        arr = sorted(["test", ts, nonce])
        sig = __import__("hashlib").sha1("".join(arr).encode()).hexdigest()

        result = await gw.handle_callback(
            {"signature": sig, "timestamp": ts, "nonce": nonce}, xml
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_handle_callback_invalid_signature(self):
        """签名失败返回error"""
        gw = WeChatGateway(token="secure_token")
        result = await gw.handle_callback(
            {"signature": "invalid_sig", "timestamp": "1", "nonce": "1"}, "<xml/>"
        )
        assert "error" in result.lower() or "invalid" in result.lower()


class TestGatewayConfirmationCard:
    """测试确认卡片格式"""

    def test_build_confirmation_card_full(self):
        """完整参数的确认卡片"""
        card = WeChatGateway.build_confirmation_card(
            title="操作确认",
            params={"类型": "收入", "金额": "3000元", "时间": "今天", "备注": "测试"},
            confirm_text="确认执行",
            cancel_text="放弃操作",
        )
        assert "操作确认" in card
        assert "类型: 收入" in card
        assert "金额: 3000元" in card
        assert "确认执行" in card
        assert "放弃操作" in card

    def test_build_confirmation_card_empty_params(self):
        """空参数的确认卡片"""
        card = WeChatGateway.build_confirmation_card(title="空确认", params={})
        assert "空确认" in card
        assert "确认" in card


# ============================================================================
# Part 2: Bridge Layer Tests (完全缺失的新测试)
# ============================================================================


class TestBridgeInitialization:
    """测试Bridge初始化"""

    def test_bridge_init(self):
        """正确初始化gateway和agent_loop引用"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(
            agent_loop=mock_agent_loop,
            token="test_token",
            encoding_aes_key="aes_key",
            corp_id="corp_id",
        )

        assert bridge.agent_loop is mock_agent_loop
        assert bridge.gateway is not None
        assert bridge.gateway.token == "test_token"
        assert bridge.gateway._message_handler is not None
        assert bridge._original_check_confirmation is None
        assert bridge._confirm_callback_wrapper is None

    def test_bridge_init_defaults(self):
        """使用默认参数初始化"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop)

        assert bridge.gateway.token == ""
        assert bridge.gateway.encoding_aes_key == ""


class TestBridgeMessageRouting:
    """测试消息路由"""

    @pytest.mark.asyncio
    async def test_on_text_message(self):
        """文本消息路由到_run_agent"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.return_value = {
            "success": True,
            "message": "处理完成",
            "results": [{"success": True, "data": {"content": "文本回复"}}],
        }

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        msg = WeChatMessage(
            msg_id="1",
            from_user="user1",
            to_user="bot",
            create_time=1234567890,
            msg_type=WeChatMsgType.TEXT,
            content="你好",
        )

        response = await bridge._on_message(msg)

        assert response.content == "文本回复"
        mock_agent_loop.run.assert_called_once_with(
            user_input="你好", session_id="user1"
        )

    @pytest.mark.asyncio
    async def test_on_voice_message(self):
        """语音消息使用recognition字段"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.return_value = {
            "success": True,
            "results": [{"success": True, "data": {"content": "语音识别结果"}}],
        }

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        msg = WeChatMessage(
            msg_id="2",
            from_user="user2",
            to_user="bot",
            create_time=1234567890,
            msg_type=WeChatMsgType.VOICE,
            recognition="语音转文字内容",
        )

        response = await bridge._on_message(msg)

        mock_agent_loop.run.assert_called_once_with(
            user_input="语音转文字内容", session_id="user2"
        )

    @pytest.mark.asyncio
    async def test_on_voice_message_fallback_to_content(self):
        """语音消息无recognition时使用content"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.return_value = {
            "success": True,
            "results": [{"success": True, "data": {"content": "fallback"}}],
        }

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        msg = WeChatMessage(
            msg_id="3",
            from_user="user3",
            to_user="bot",
            create_time=1234567890,
            msg_type=WeChatMsgType.VOICE,
            content="content_fallback",
        )

        response = await bridge._on_message(msg)

        mock_agent_loop.run.assert_called_once_with(
            user_input="content_fallback", session_id="user3"
        )

    @pytest.mark.asyncio
    async def test_on_image_message(self):
        """图片返回暂不支持提示"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        msg = WeChatMessage(
            msg_id="4",
            from_user="user4",
            to_user="bot",
            create_time=1234567890,
            msg_type=WeChatMsgType.IMAGE,
            media_id="img_123",
        )

        response = await bridge._on_message(msg)

        assert "暂不支持" in response.content
        mock_agent_loop.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_event_subscribe(self):
        """关注返回欢迎语"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        msg = WeChatMessage(
            msg_id="5",
            from_user="user5",
            to_user="bot",
            create_time=1234567890,
            msg_type=WeChatMsgType.EVENT,
            event_type="subscribe",
        )

        response = await bridge._on_message(msg)

        assert "欢迎" in response.content
        mock_agent_loop.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_event_unsubscribe(self):
        """取关返回空"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        msg = WeChatMessage(
            msg_id="6",
            from_user="user6",
            to_user="bot",
            create_time=1234567890,
            msg_type=WeChatMsgType.EVENT,
            event_type="unsubscribe",
        )

        response = await bridge._on_message(msg)

        assert response.content == ""

    @pytest.mark.asyncio
    async def test_on_unsupported_type(self):
        """未知类型返回提示"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        msg = WeChatMessage(
            msg_id="7",
            from_user="user7",
            to_user="bot",
            create_time=1234567890,
            msg_type=WeChatMsgType.VIDEO,
        )

        response = await bridge._on_message(msg)

        assert "暂不支持" in response.content
        assert "video" in response.content

    @pytest.mark.asyncio
    async def test_on_empty_content(self):
        """空内容返回提示"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        msg = WeChatMessage(
            msg_id="8",
            from_user="user8",
            to_user="bot",
            create_time=1234567890,
            msg_type=WeChatMsgType.TEXT,
            content="   ",
        )

        response = await bridge._on_message(msg)

        assert "有效内容" in response.content
        mock_agent_loop.run.assert_not_called()


# ============================================================================
# Part 3: Bridge + AgentLoop 集成测试 (核心！)
# ============================================================================


class TestBridgeAgentIntegration:
    """Bridge与AgentLoop集成测试"""

    @pytest.mark.asyncio
    async def test_run_agent_success(self):
        """Agent正常执行返回结果"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.return_value = {
            "success": True,
            "task_id": "task_001",
            "session_id": "session_001",
            "results": [
                {
                    "step_id": "step_1",
                    "success": True,
                    "data": {"content": "查询完成：本月收入50000元"},
                }
            ],
            "message": "执行完成",
        }

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        result = await bridge._run_agent("查询本月收入", "user_001")

        assert result.content == "查询完成：本月收入50000元"
        mock_agent_loop.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_agent_failure(self):
        """Agent异常返回错误信息"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.side_effect = RuntimeError("数据库连接超时")

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        result = await bridge._run_agent("测试输入", "user_error")

        assert "抱歉" in result.content or "错误" in result.content
        assert "数据库连接超时" not in result.content  # 确保不泄露内部错误

    @pytest.mark.asyncio
    async def test_run_agent_confirmation_required(self):
        """需要确认时返回确认卡片"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.return_value = {
            "success": False,
            "confirmation_required": True,
            "intent_type": "FINANCE",
            "goal": "删除账单记录",
            "confidence": 0.65,
        }

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        result = await bridge._run_agent("删除账单", "user_confirm")

        assert "操作确认" in result.content
        assert "FINANCE" in result.content
        assert "删除账单记录" in result.content
        assert "65%" in result.content

    @pytest.mark.asyncio
    async def test_format_response_success_data_dict(self):
        """成功结果格式化为微信文本（dict数据）"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        result = {
            "success": True,
            "results": [{"success": True, "data": {"content": "分析报告已生成"}}],
        }

        response = bridge._format_response(result)
        assert response.content == "分析报告已生成"

    @pytest.mark.asyncio
    async def test_format_response_success_data_str(self):
        """成功结果格式化为微信文本（字符串数据）"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        result = {"success": True, "results": [{"success": True, "data": "纯文本结果"}]}

        response = bridge._format_response(result)
        assert response.content == "纯文本结果"

    @pytest.mark.asyncio
    async def test_format_response_confirmation_card(self):
        """确认请求转为卡片"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        result = {
            "success": False,
            "confirmation_required": True,
            "intent_type": "EMAIL",
            "goal": "发送邮件给客户",
            "confidence": 0.72,
        }

        response = bridge._format_response(result)
        assert "操作确认" in response.content
        assert "EMAIL" in response.content

    @pytest.mark.asyncio
    async def test_format_response_error_truncation(self):
        """错误信息截断到500字"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        long_error = "x" * 1000
        result = {"success": False, "error": long_error}

        response = bridge._format_response(result)
        assert len(response.content) <= 500

    @pytest.mark.asyncio
    async def test_format_response_long_content_truncation(self):
        """超长内容截断到500字"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        long_content = "y" * 800
        result = {
            "success": True,
            "results": [{"success": True, "data": {"content": long_content}}],
        }

        response = bridge._format_response(result)
        assert len(response.content) <= 500


class TestSetupConfirmCallback:
    """测试回调设置机制"""

    def test_setup_confirm_callback_saves_original(self):
        """回调设置保存原始方法"""
        mock_agent_loop = MagicMock()
        mock_confirmer = MagicMock()
        mock_agent_loop.confirmer = mock_confirmer

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        bridge.setup_confirm_callback()

        assert bridge._original_check_confirmation is not None
        assert bridge._confirm_callback_wrapper is not None

    @pytest.mark.asyncio
    async def test_setup_confirm_callback_wrapper_execution(self):
        """wrapper正确执行并返回ConfirmationResult"""
        mock_agent_loop = MagicMock()
        mock_confirmer = MagicMock()
        mock_agent_loop.confirmer = mock_confirmer

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        bridge.setup_confirm_callback()

        wrapper = bridge._confirm_callback_wrapper
        request = ConfirmationRequest(
            session_id="sess_1",
            intent_type="TEST",
            goal="测试目标",
            confidence=0.5,
            risk_level=RiskLevel.MEDIUM,
        )

        result = await wrapper(request)

        assert isinstance(result, ConfirmationResult)
        assert result.confirmed is False
        assert result.method == "wechat_card"

    def test_setup_confirm_callback_replaces_method(self):
        """设置回调后agent_loop方法被替换为wrapper"""
        original_method = MagicMock()
        mock_agent_loop = MagicMock()
        mock_confirmer = MagicMock()
        mock_confirmer.check_confirmation = original_method
        mock_agent_loop.confirmer = mock_confirmer

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        bridge.setup_confirm_callback()

        assert mock_agent_loop.confirmer.check_confirmation is not original_method
        assert callable(mock_agent_loop.confirmer.check_confirmation)

    @pytest.mark.asyncio
    async def test_setup_confirm_callback_wrapper_delegates(self):
        """wrapper正确委托给原始方法并注入wechat回调"""
        call_record = []

        async def original_check(
            session_id,
            intent_type,
            goal,
            confidence,
            params=None,
            confirm_callback=None,
        ):
            call_record.append(
                {
                    "session_id": session_id,
                    "intent_type": intent_type,
                    "has_callback": confirm_callback is not None,
                }
            )
            return ConfirmationResult(confirmed=True, method="auto")

        mock_agent_loop = MagicMock()
        mock_confirmer = MagicMock()
        mock_confirmer.check_confirmation = original_check
        mock_agent_loop.confirmer = mock_confirmer

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        bridge.setup_confirm_callback()

        result = await mock_agent_loop.confirmer.check_confirmation(
            session_id="sess_test", intent_type="TEST", goal="测试", confidence=0.8
        )

        assert len(call_record) == 1
        assert call_record[0]["has_callback"] is True  # 确认注入了回调
        assert result.confirmed is True


# ============================================================================
# Part 4: 全链路端到端测试
# ============================================================================


class TestFullFlowE2E:
    """完整消息流E2E测试"""

    @pytest.mark.asyncio
    async def test_full_flow_text_message(self):
        """完整文本消息E2E（mock AgentLoop）"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.return_value = {
            "success": True,
            "task_id": "task_e2e_1",
            "session_id": "user_e2e",
            "results": [
                {
                    "step_id": "step_1",
                    "skill_id": "analysis",
                    "success": True,
                    "data": {"content": "E2E测试成功：已处理您的请求"},
                }
            ],
            "message": "执行完成",
        }

        bridge = WeChatAgentBridge(
            agent_loop=mock_agent_loop,
            token="e2e_token",
            encoding_aes_key="",
            corp_id="",
        )

        query_params = {"signature": "", "timestamp": "1", "nonce": "1"}
        body = """<xml>
<ToUserName><![CDATA[bot]]></ToUserName>
<FromUserName><![CDATA[user_e2e]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[E2E完整测试]]></Content>
<MsgId>e2e_msg_1</MsgId>
</xml>"""

        ts, nonce = "1", "1"
        arr = sorted(["e2e_token", ts, nonce])
        query_params["signature"] = (
            __import__("hashlib").sha1("".join(arr).encode()).hexdigest()
        )

        result = await bridge.handle_callback(query_params, body)

        assert "E2E测试成功" in result
        assert "<xml>" in result
        assert "user_e2e" in result
        assert "bot" in result
        mock_agent_loop.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_flow_voice_message(self):
        """完整语音消息E2E"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.return_value = {
            "success": True,
            "results": [{"success": True, "data": {"content": "语音消息已处理"}}],
        }

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="voice_test")

        query_params = {"signature": "", "timestamp": "2", "nonce": "2"}
        body = """<xml>
<ToUserName><![CDATA[bot]]></ToUserName>
<FromUserName><![CDATA[user_voice]]></FromUserName>
<CreateTime>2</CreateTime>
<MsgType><![CDATA[voice]]></MsgType>
<Recognition><![CDATA[语音转文字测试]]></Recognition>
<MediaId><![CDATA[media_123]]></MediaId>
<MsgId>voice_msg_1</MsgId>
</xml>"""

        ts, nonce = "2", "2"
        arr = sorted(["voice_test", ts, nonce])
        query_params["signature"] = (
            __import__("hashlib").sha1("".join(arr).encode()).hexdigest()
        )

        result = await bridge.handle_callback(query_params, body)

        assert "语音消息已处理" in result
        mock_agent_loop.run.assert_called_once_with(
            user_input="语音转文字测试", session_id="user_voice"
        )

    @pytest.mark.asyncio
    async def test_full_flow_with_encryption(self):
        """加密消息完整E2E"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.return_value = {
            "success": True,
            "results": [{"success": True, "data": {"content": "加密消息处理完成"}}],
        }

        bridge = WeChatAgentBridge(
            agent_loop=mock_agent_loop,
            token="enc_token",
            encoding_aes_key="enc_key_test",
        )

        query_params = {
            "signature": "",
            "timestamp": "3",
            "nonce": "3",
            "encrypt_type": "aes",
        }
        body = """<xml>
<ToUserName><![CDATA[bot]]></ToUserName>
<FromUserName><![CDATA[user_enc]]></FromUserName>
<CreateTime>3</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[加密测试]]></Content>
</xml>"""

        ts, nonce = "3", "3"
        arr = sorted(["enc_token", ts, nonce])
        query_params["signature"] = (
            __import__("hashlib").sha1("".join(arr).encode()).hexdigest()
        )

        result = await bridge.handle_callback(query_params, body)

        assert "加密消息处理完成" in result

    def test_verify_url_echostr(self):
        """URL验证回显echostr"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="verify_token")

        ts, nonce = "999", "nonce_xyz"
        echostr = "echostr_test_123"
        arr = sorted(["verify_token", ts, nonce])
        sig = __import__("hashlib").sha1("".join(arr).encode()).hexdigest()

        result = bridge.verify_url(sig, ts, nonce, echostr)

        assert result == echostr

    def test_verify_url_invalid_returns_none(self):
        """URL验证失败返回None"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="secure")

        result = bridge.verify_url("wrong", "1", "1", "echo")

        assert result is None


class TestEdgeCases:
    """边界情况和异常场景"""

    @pytest.mark.asyncio
    async def test_handle_callback_malformed_xml(self):
        """畸形XML返回success"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        ts, nonce = "1", "1"
        arr = sorted(["test", ts, nonce])
        sig = __import__("hashlib").sha1("".join(arr).encode()).hexdigest()

        result = await bridge.handle_callback(
            {"signature": sig, "timestamp": ts, "nonce": nonce}, "not_xml_at_all"
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_run_agent_empty_result(self):
        """Agent返回空结果时的处理"""
        mock_agent_loop = AsyncMock()
        mock_agent_loop.run.return_value = {}

        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")
        result = await bridge._run_agent("test", "user_empty")

        assert result.content == "执行失败"

    @pytest.mark.asyncio
    async def test_format_response_no_results(self):
        """无results字段的响应格式化"""
        mock_agent_loop = MagicMock()
        bridge = WeChatAgentBridge(agent_loop=mock_agent_loop, token="test")

        result = {"success": True, "message": "自定义消息"}
        response = bridge._format_response(result)

        assert response.content == "自定义消息"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
