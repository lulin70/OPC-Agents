"""
LLM Service Layer - Multi-backend abstraction and unified entry point
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum
import asyncio
import time
import json
import logging
from datetime import datetime
from .utils import get_llm_async_semaphore
from .config import LLM_PROVIDERS

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    MOKA = "moka"
    OPENAI = "openai"
    GLM = "glm"
    OLLAMA = "ollama"


@dataclass
class LLMResponse:
    content: str
    provider: LLMProvider
    model: str
    usage: Dict[str, int]
    latency_ms: float
    raw_response: Any = None


@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.MOKA
    model: str = "moka/claude-sonnet-4-6"
    api_key: Optional[str] = None
    base_url: Optional[str] = LLM_PROVIDERS["moka"]
    max_tokens: int = 500
    temperature: float = 0.3
    timeout_seconds: float = 60.0
    max_retries: int = 2
    cost_budget_daily: float = 5.0


class LLMBackend(ABC):
    """LLM backend abstract interface"""

    @abstractmethod
    async def complete(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> LLMResponse:
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        pass

    @abstractmethod
    def estimate_cost(self, prompt: str) -> float:
        pass


class OpenAIBackend(LLMBackend):
    """OpenAI API backend implementation"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client: Any = None

    async def _get_client(self) -> Any:
        if self.client is None:
            try:
                import openai

                self.client = openai.AsyncOpenAI(
                    api_key=self.config.api_key, base_url=self.config.base_url
                )
            except ImportError:
                raise RuntimeError(
                    "openai package not installed. Run: pip install openai"
                )
        return self.client

    async def complete(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> LLMResponse:
        start = time.time()
        client = await self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            sem = get_llm_async_semaphore()
            async with sem:
                response = await client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    timeout=self.config.timeout_seconds,
                )
            latency_ms = (time.time() - start) * 1000
            return LLMResponse(
                content=response.choices[0].message.content,
                provider=LLMProvider.OPENAI,
                model=self.config.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                latency_ms=latency_ms,
                raw_response=response,
            )
        except Exception as e:
            logger.error("OpenAI API call failed: %s", e)
            raise

    def validate_config(self) -> bool:
        return bool(self.config.api_key and len(self.config.api_key) > 10)

    def estimate_cost(self, prompt: str) -> float:
        estimated_tokens = len(prompt) / 4
        if "gpt-4" in self.config.model:
            return estimated_tokens * 0.00003 / 1000
        elif "gpt-3.5" in self.config.model:
            return estimated_tokens * 0.0000015 / 1000
        return estimated_tokens * 0.000002 / 1000


class OllamaBackend(LLMBackend):
    """Local Ollama backend implementation"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or LLM_PROVIDERS["ollama"]

    async def complete(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> LLMResponse:
        start = time.time()
        import httpx

        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        sem = get_llm_async_semaphore()
        async with sem:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()

        latency_ms = (time.time() - start) * 1000
        return LLMResponse(
            content=data.get("response", ""),
            provider=LLMProvider.OLLAMA,
            model=self.config.model,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0)
                + data.get("eval_count", 0),
            },
            latency_ms=(
                latency_ms
                if "total_duration" not in data
                else data.get("total_duration", 0) / 1_000_000
            ),
        )

    def validate_config(self) -> bool:
        import httpx

        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception as e:
            logger.debug("[LLMService] Health check failed: %s", e)
            return False

    def estimate_cost(self, prompt: str) -> float:
        return 0.0


class UsageTracker:
    """Token usage tracker"""

    def __init__(self, daily_budget: float):
        self.daily_budget = daily_budget
        self.daily_usage: Dict[str, Dict] = {}

    def record(self, user_id: str, usage: dict, cost_usd: float = 0.0) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.daily_usage:
            self.daily_usage[today] = {"tokens": 0, "cost": 0.0, "calls": 0}

        self.daily_usage[today]["tokens"] += usage.get("total_tokens", 0)
        self.daily_usage[today]["calls"] += 1
        self.daily_usage[today]["cost"] += cost_usd

    def is_budget_exceeded(self) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.daily_usage.get(today, {}).get("cost", 0.0) >= self.daily_budget

    def get_report(self, user_id: Optional[str] = None) -> dict:
        return {"daily": dict(self.daily_usage), "budget": self.daily_budget}


class LLMService:
    """LLM service unified entry point"""

    BACKEND_MAP = {
        LLMProvider.MOKA: OpenAIBackend,
        LLMProvider.OPENAI: OpenAIBackend,
        LLMProvider.GLM: OpenAIBackend,
        LLMProvider.OLLAMA: OllamaBackend,
    }

    DETECT_SYSTEM_PROMPT = """你是一个业务类型分类专家。根据用户的输入，判断其属于以下哪种一人公司类型：

选项：
- content_creator: 内容创作者（写文章、做视频、自媒体）
- digital_product: 数字产品开发者（卖课程、电子书、模板、SaaS）
- ai_tool_builder: AI工具开发者（做API、插件、自动化工具）
- consultant: 专业咨询顾问（企业培训、1v1咨询、方案设计）
- ecommerce: 电商运营者（卖实物商品、闲鱼、抖音小店）
- creative_work: 创意工作者（设计师、摄影师、翻译、插画）

【重要】必须严格返回JSON格式，不要添加任何markdown标记、代码块或其他文字。
格式：{"business_type": "类型", "confidence": 0.95, "reasoning": "原因"}
示例：{"business_type": "digital_product", "confidence": 0.92, "reasoning": "用户提到在线课程平台和编程课程销售"}"""

    PERSONA_SYSTEM_TEMPLATE = """你是{display_name}。
语气：{tone}
专业领域：{expertise}
回复要求：简洁、有温度、带适当emoji。每条回复不超过200字。"""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.backend = self._create_backend(self.config.provider)
        self.usage_tracker = UsageTracker(config.cost_budget_daily if config else 5.0)

    def _create_backend(self, provider: LLMProvider) -> LLMBackend:
        backend_cls = self.BACKEND_MAP.get(provider)
        if backend_cls is None:
            logger.warning("Unknown LLM provider: %s, falling back to MOKA", provider)
            backend_cls = OpenAIBackend
        return backend_cls(self.config)

    async def detect_business_type_by_llm(
        self, user_input: str, history: Optional[list] = None, max_retries: int = 2
    ) -> dict:
        """Detect business type using LLM

        Args:
            user_input: User input text
            history: Conversation history (optional)
            max_retries: Maximum retry count

        Returns:
            Dictionary containing business_type, confidence, reasoning
        """
        for attempt in range(max_retries + 1):
            try:
                response = await self.backend.complete(
                    user_input, self.DETECT_SYSTEM_PROMPT
                )
                self.usage_tracker.record("detect", response.usage, 0)

                # Clean response content (remove possible markdown markers)
                content = response.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                # Attempt to parse JSON
                parsed = json.loads(content)

                # Validate required fields
                if "business_type" not in parsed:
                    raise ValueError("Missing business_type field")

                return {
                    "business_type": parsed.get("business_type", "unknown"),
                    "confidence": float(parsed.get("confidence", 0.0)),
                    "reasoning": parsed.get("reasoning", ""),
                    "provider": response.provider.value,
                    "model": response.model,
                    "attempt": attempt + 1,
                }

            except json.JSONDecodeError as e:
                logger.warning(
                    f"JSON decode failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                if attempt == max_retries:
                    return {
                        "business_type": "unknown",
                        "confidence": 0.0,
                        "reasoning": f"LLM返回格式异常: {str(e)}",
                        "raw_response": (
                            response.content if "response" in locals() else None
                        ),
                    }
                # Wait a bit before retrying
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(
                    f"LLM detection failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                if attempt == max_retries:
                    return {
                        "business_type": "unknown",
                        "confidence": 0.0,
                        "reasoning": f"错误: {str(e)}",
                    }
                await asyncio.sleep(0.5)

        # Should not reach here
        return {"business_type": "unknown", "confidence": 0.0, "reasoning": "未知错误"}

    async def generate_persona_response(
        self, user_input: str, persona_config: dict, context: Optional[dict] = None
    ) -> str:
        """Generate stylized response based on persona configuration"""
        tone = persona_config.get("style_overrides", {}).get("tone", "专业温暖")
        expertise_list = persona_config.get("expertise_tags", [])
        display_name = persona_config.get("display_name", "智能助理")
        expertise = ", ".join(expertise_list[:3]) if expertise_list else "通用领域"

        system_prompt = self.PERSONA_SYSTEM_TEMPLATE.format(
            display_name=display_name,
            tone=tone,
            expertise=expertise,
        )

        try:
            response = await self.backend.complete(user_input, system_prompt)
            self.usage_tracker.record("persona", response.usage, 0)
            return response.content
        except Exception as e:
            logger.warning("Persona generation failed: %s", e)
            return f"抱歉，暂时无法生成风格化回复。（{type(e).__name__}）"

    def switch_provider(self, new_provider: LLMProvider, **overrides: Any) -> None:
        """Dynamically switch LLM backend"""
        new_config = LLMConfig(
            **{**self.config.__dict__, "provider": new_provider, **overrides}
        )
        self.backend = self._create_backend(new_provider)
        self.config = new_config

    def get_usage_report(self) -> dict:
        """Get usage report"""
        return self.usage_tracker.get_report()
