from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    """
    All LLM providers implement this interface.
    Swap providers by changing LLM_PROVIDER in .env — no business logic changes.
    """

    @abstractmethod
    async def generate(self, prompt: str, system: Optional[str] = None) -> str:
        """Send a prompt, return the text response."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...
