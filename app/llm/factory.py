from app.llm.base import BaseLLMProvider
from app.core.config import settings


def get_llm_provider() -> BaseLLMProvider:
    """
    Returns the active LLM provider based on LLM_PROVIDER env var.
    Change LLM_PROVIDER in .env to switch — no code changes needed.
    """
    provider = settings.LLM_PROVIDER

    if provider == "nvidia":
        from app.llm.nvidia_provider import NvidiaProvider
        return NvidiaProvider()
    elif provider == "openai":
        from app.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    elif provider == "gemini":
        from app.llm.gemini_provider import GeminiProvider
        return GeminiProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Choose: nvidia, openai, anthropic, gemini")
