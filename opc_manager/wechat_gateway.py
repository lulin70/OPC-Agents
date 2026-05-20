import hashlib
import base64
import json
import time
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class WeChatMsgType(Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    LOCATION = "location"
    LINK = "link"
    EVENT = "event"


@dataclass
class WeChatMessage:
    msg_id: str
    from_user: str
    to_user: str
    create_time: int
    msg_type: WeChatMsgType
    content: str = ""
    media_id: str = ""
    pic_url: str = ""
    format: str = ""
    recognition: str = ""
    event_type: str = ""
    event_key: str = ""
    raw_xml: str = ""


@dataclass
class WeChatResponse:
    msg_type: str = "text"
    content: str = ""
    media_id: str = ""

    def to_xml(self, to_user: str, from_user: str) -> str:
        escaped_content = self._escape_cdata(self.content)
        return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{escaped_content}]]></Content>
</xml>"""

    @staticmethod
    def _escape_cdata(text: str) -> str:
        return text.replace("]]>", "]]&gt;")


class WeChatGateway:
    def __init__(self, token: str = "", encoding_aes_key: str = "", corp_id: str = ""):
        self.token = token or ""
        self.encoding_aes_key = encoding_aes_key or ""
        self.corp_id = corp_id or ""
        self._aes_key = None
        self._message_handler: Optional[Callable] = None

        if self.encoding_aes_key:
            self._init_aes_key()

    def _init_aes_key(self):
        try:
            from Crypto.Cipher import AES

            try:
                key = base64.b64decode(self.encoding_aes_key + "=")
            except Exception as e:
                logger.debug("[WeChatGateway] AES key decode (padded) failed: %s", e)
                key = base64.b64decode(self.encoding_aes_key)
            self._aes_key = key[:32]
            iv = key[32:48] if len(key) >= 48 else key[16:32]
            self._iv = iv
        except ImportError:
            logger.warning("pycryptodome not installed, encryption disabled")
            self._aes_key = None
        except Exception as e:
            logger.error("Failed to decode AES key: %s", e)
            self._aes_key = None

    def verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        if not self.token:
            logger.warning(
                "WeChatGateway: token is empty, signature verification rejected"
            )
            return False
        arr = sorted([self.token, timestamp, nonce])
        sha = hashlib.sha1("".join(arr).encode()).hexdigest()
        return sha == signature

    def decrypt_message(self, encrypted_msg: str) -> str:
        if not self._aes_key or not encrypted_msg:
            return encrypted_msg
        try:
            from Crypto.Cipher import AES

            enc = base64.b64decode(encrypted_msg)
            random = enc[:16]
            msg_len = int.from_bytes(enc[16:20], "big")
            ciphertext = enc[20 : 20 + msg_len]
            cipher = AES.new(self._aes_key, AES.MODE_CBC, iv=self._iv)
            decrypted = cipher.decrypt(ciphertext)
            pkcs7_pad = decrypted[-1]
            content = decrypted[:-pkcs7_pad] if 0 < pkcs7_pad <= 32 else decrypted
            return content.decode("utf-8", errors="ignore").lstrip("\x00")
        except Exception as e:
            logger.error("Decrypt failed: %s", e)
            return encrypted_msg

    def parse_message(self, xml_body: str) -> Optional[WeChatMessage]:
        try:
            root = ET.fromstring(xml_body)
            msg = WeChatMessage(
                msg_id=root.findtext("MsgID") or root.findtext("MsgId") or "",
                from_user=root.findtext("FromUserName") or "",
                to_user=root.findtext("ToUserName") or "",
                create_time=int(root.findtext("CreateTime") or "0"),
                msg_type=WeChatMsgType(root.findtext("MsgType") or "text"),
                raw_xml=xml_body,
            )
            msg.content = root.findtext("Content") or ""
            msg.media_id = root.findtext("MediaId") or ""
            msg.pic_url = root.findtext("PicUrl") or ""
            msg.format = root.findtext("Format") or ""
            msg.recognition = root.findtext("Recognition") or ""

            event_node = root.find("Event")
            if event_node is not None and event_node.text:
                msg.event_type = event_node.text
                msg.msg_type = WeChatMsgType.EVENT
                msg.event_key = root.findtext("EventKey") or ""
            return msg
        except ET.ParseError as e:
            logger.error("Parse XML failed: %s", e)
            return None

    def set_message_handler(
        self, handler: Callable[[WeChatMessage], Awaitable[WeChatResponse]]
    ):
        self._message_handler = handler

    async def handle_callback(self, query_params: Dict[str, str], body: str) -> str:
        signature = query_params.get("signature", "")
        timestamp = query_params.get("timestamp", "")
        nonce = query_params.get("nonce", "")
        encrypt_type = query_params.get("encrypt_type", "")

        if not self.verify_signature(signature, timestamp, nonce):
            return "error: invalid signature"

        if encrypt_type == "aes":
            decrypted = self.decrypt_message(body.strip())
        else:
            decrypted = body

        msg = self.parse_message(decrypted)
        if not msg:
            return "success"

        if msg.msg_type == WeChatMsgType.EVENT and msg.event_type in (
            "subscribe",
            "unsubscribe",
        ):
            return "success"

        if self._message_handler:
            response = await self._message_handler(msg)
            return response.to_xml(msg.to_user, msg.from_user)

        return "success"

    @staticmethod
    def build_confirmation_card(
        title: str, params: dict, confirm_text="确认", cancel_text="取消"
    ) -> str:
        lines = [f"📋 {title}", ""]
        for k, v in params.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        lines.append(f"✅ {confirm_text}  |  ❌ {cancel_text}")
        return "\n".join(lines)
