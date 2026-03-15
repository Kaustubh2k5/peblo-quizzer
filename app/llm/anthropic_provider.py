import anthropic
from app.llm.base import BaseLLMProvider
from app.core.config import settings
from typing import Optional


class AnthropicProvider(BaseLLMProvider):
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.ANTHROPIC_MODEL

    async def generate(self, prompt: str, system: Optional[str] = None) -> str:
        kwargs = {"model": self.model, "max_tokens": 2048, "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system

        response = await self.client.messages.create(**kwargs)
        return response.content[0].text

    def provider_name(self) -> str:
        return f"anthropic/{self.model}"
