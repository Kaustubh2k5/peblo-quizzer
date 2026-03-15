import google.generativeai as genai
from app.llm.base import BaseLLMProvider
from app.core.config import settings
from typing import Optional


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.model_name = settings.GEMINI_MODEL

    async def generate(self, prompt: str, system: Optional[str] = None) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = await self.model.generate_content_async(full_prompt)
        return response.text

    def provider_name(self) -> str:
        return f"gemini/{self.model_name}"
