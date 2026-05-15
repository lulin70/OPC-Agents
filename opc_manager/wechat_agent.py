import logging
from typing import Optional

from .wechat_gateway import WeChatGateway, WeChatMessage, WeChatResponse, WeChatMsgType
from .agent_loop import AgentLoop
from .confirmer import ConfirmationRequest, ConfirmationResult

logger = logging.getLogger(__name__)


class WeChatAgentBridge:
    def __init__(self, agent_loop: AgentLoop,
                 token: str = "", encoding_aes_key: str = "", corp_id: str = ""):
        self.agent_loop = agent_loop
        self.gateway = WeChatGateway(token=token,
                                     encoding_aes_key=encoding_aes_key,
                                     corp_id=corp_id)
        self.gateway.set_message_handler(self._on_message)

    async def _on_message(self, msg: WeChatMessage) -> WeChatResponse:
        if msg.msg_type == WeChatMsgType.TEXT:
            return await self._handle_text_message(msg)
        elif msg.msg_type == WeChatMsgType.VOICE:
            content = msg.recognition or msg.content or "[语音消息]"
            return await self._run_agent(content, msg.from_user)
        elif msg.msg_type == WeChatMsgType.IMAGE:
            return WeChatResponse(content="图片已收到，暂不支持图片处理")
        elif msg.msg_type == WeChatMsgType.EVENT:
            if msg.event_type == "subscribe":
                return WeChatResponse(content="欢迎关注！发送您的需求即可开始使用。")
            elif msg.event_type == "unsubscribe":
                return WeChatResponse(content="")
            return WeChatResponse(content="")
        else:
            return WeChatResponse(content=f"暂不支持的消息类型: {msg.msg_type.value}")

    async def _handle_text_message(self, msg: WeChatMessage) -> WeChatResponse:
        content = msg.content.strip()
        if not content:
            return WeChatResponse(content="请输入有效内容")

        result = await self._run_agent(content, msg.from_user)
        return result

    async def _run_agent(self, user_input: str, session_id: str) -> WeChatResponse:
        try:
            loop_result = await self.agent_loop.run(
                user_input=user_input,
                session_id=session_id
            )
            return self._format_response(loop_result)
        except Exception as e:
            logger.error("AgentLoop execution error for wechat user %s: %s", session_id, e)
            return WeChatResponse(content=f"处理出错: {str(e)[:100]}")

    def _format_response(self, result: dict) -> WeChatResponse:
        if not result.get("success"):
            if result.get("confirmation_required"):
                card = WeChatGateway.build_confirmation_card(
                    title="操作确认",
                    params={
                        "类型": result.get("intent_type", "未知"),
                        "目标": result.get("goal", "")[:80],
                        "置信度": f"{result.get('confidence', 0):.0%}",
                    },
                )
                return WeChatResponse(content=card)
            error_msg = result.get("error") or result.get("message", "执行失败")
            return WeChatResponse(content=error_msg[:500])

        message = result.get("message", "")
        results = result.get("results", [])
        if results and results[-1].get("success"):
            last_data = results[-1].get("data", {})
            if isinstance(last_data, dict):
                content = last_data.get("content", "") or last_data.get("analysis_result", "")
                if content:
                    return WeChatResponse(content=str(content)[:500])
            elif isinstance(last_data, str):
                return WeChatResponse(content=str(last_data)[:500])

        return WeChatResponse(content=message or "操作完成")

    def setup_confirm_callback(self):
        async def wechat_confirm_callback(request: ConfirmationRequest) -> ConfirmationResult:
            card_content = WeChatGateway.build_confirmation_card(
                title="操作确认",
                params={
                    "类型": request.intent_type,
                    "目标": request.goal[:80],
                    "置信度": f"{request.confidence:.0%}",
                    "风险等级": request.risk_level.value,
                    **{k: str(v)[:50] for k, v in request.extracted_params.items() if v},
                },
            )
            logger.info("WeChat confirmation card generated for session %s:\n%s",
                        request.session_id, card_content)
            return ConfirmationResult(confirmed=False, method="wechat_card")

        original_check = self.agent_loop.confirmer.check_confirmation

        async def wrapped_check(session_id: str, intent_type: str,
                                goal: str, confidence: float,
                                params: dict = None,
                                confirm_callback=None) -> ConfirmationResult:
            return await original_check(
                session_id=session_id,
                intent_type=intent_type,
                goal=goal,
                confidence=confidence,
                params=params,
                confirm_callback=wechat_confirm_callback,
            )

        self.agent_loop.confirmer.check_confirmation = wrapped_check

    async def handle_callback(self, query_params: dict, body: str) -> str:
        return await self.gateway.handle_callback(query_params, body)

    def verify_url(self, signature: str, timestamp: str, nonce: str,
                   echostr: str) -> Optional[str]:
        if self.gateway.verify_signature(signature, timestamp, nonce):
            return echostr
        return None
