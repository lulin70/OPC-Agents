import pytest
from opc_manager.wechat_gateway import WeChatGateway, WeChatMessage, WeChatMsgType, WeChatResponse

class TestWeChatGatewaySignature:
    def test_verify_signature_valid(self):
        gw = WeChatGateway(token="test_token_123")
        ts = "1234567890"
        nonce = "abc123"
        arr = sorted(["test_token_123", ts, nonce])
        sig = __import__('hashlib').sha1("".join(arr).encode()).hexdigest()
        assert gw.verify_signature(sig, ts, nonce) is True
    
    def test_verify_signature_invalid(self):
        gw = WeChatGateway(token="test_token")
        assert gw.verify_signature("wrong_sig", "123", "456") is False
    
    def test_verify_no_token_rejected(self):
        gw = WeChatGateway(token="")
        assert gw.verify_signature("", "", "") is False

class TestWeChatMessageParsing:
    SAMPLE_TEXT_XML = """<xml>
<ToUserName><![CDATA[toUser]]></ToUserName>
<FromUserName><![CDATA[fromUser]]></FromUserName>
<CreateTime>1348831860</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[帮我记一笔收入3000]]></Content>
<MsgId>1234567890123456</MsgId>
</xml>"""
    
    def test_parse_text_message(self):
        gw = WeChatGateway()
        msg = gw.parse_message(self.SAMPLE_TEXT_XML)
        assert msg is not None
        assert msg.msg_type == WeChatMsgType.TEXT
        assert msg.content == "帮我记一笔收入3000"
        assert msg.from_user == "fromUser"
        assert msg.to_user == "toUser"
    
    def test_parse_empty_returns_none(self):
        gw = WeChatGateway()
        assert gw.parse_message("") is None
        assert gw.parse_message("<invalid>") is None

class TestWeChatResponse:
    def test_response_to_xml(self):
        resp = WeChatResponse(content="操作成功")
        xml = resp.to_xml("userA", "userB")
        assert "userA" in xml
        assert "userB" in xml
        assert "操作成功" in xml

class TestConfirmationCard:
    def test_build_confirmation_card(self):
        card = WeChatGateway.build_confirmation_card(
            "记账确认",
            {"类型": "收入", "金额": "3000元", "时间": "今天"},
        )
        assert "记账确认" in card
        assert "收入" in card
        assert "3000元" in card
        assert "确认" in card

class TestHandleCallback:
    @pytest.mark.asyncio
    async def test_handle_with_handler(self):
        gw = WeChatGateway(token="test")
        handler_called = []
        
        async def mock_handler(msg):
            handler_called.append(msg)
            return WeChatResponse(content="收到: " + msg.content)
        
        gw.set_message_handler(mock_handler)
        
        xml = """<xml><ToUserName><![CDATA[t]]></ToUserName>
<FromUserName><![CDATA[f]]></FromUserName>
<CreateTime>1</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[hello]]></Content></xml>"""
        
        ts, nonce = "1", "1"
        arr = sorted(["test", ts, nonce])
        sig = __import__('hashlib').sha1("".join(arr).encode()).hexdigest()
        
        result = await gw.handle_callback({
            "signature": sig,
            "timestamp": ts,
            "nonce": nonce,
        }, xml)
        
        assert len(handler_called) == 1
        assert "收到: hello" in result
    
    @pytest.mark.asyncio
    async def test_handle_invalid_signature(self):
        gw = WeChatGateway(token="test_token_strict")
        result = await gw.handle_callback({"signature": "bad"}, "<xml/>")
        assert "invalid" in result
