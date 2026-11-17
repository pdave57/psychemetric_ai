"""LLM provider interface, OpenAI adapter, and NullLLM circuit-breaker fallback."""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class BaseLLM(ABC):
    """Abstract interface for LLM completions."""

    @abstractmethod
    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 500) -> str:
        """Produce completion text."""
        pass


class NullLLM(BaseLLM):
    """Deterministic fallback when LLM is unconfigured, disabled, or circuit-broken."""

    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 500) -> str:
        logger.info("NullLLM called: returning deterministic framework guidance.")
        return (
            "Your reflective temperament pattern reflects your self-reported tendencies. "
            "Please review your quantitative scores for detailed insights."
        )


class OpenAILLM(BaseLLM):
    """Adapter for OpenAI-compatible APIs such as OpenRouter and OpenAI."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"
        self.model = model or (
            os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
            if self.provider == "openrouter"
            else os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        )
        self.base_url = base_url or (
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            if self.provider == "openrouter"
            else None
        )
        self.fallback = NullLLM()

    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 500) -> str:
        if not self.api_key:
            logger.warning("No OpenAI/OpenRouter API key detected; using NullLLM fallback.")
            return self.fallback.generate(prompt, system, max_tokens)

        try:
            from openai import OpenAI

            client_kwargs = {"api_key": self.api_key, "timeout": 15.0}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url

            client = OpenAI(**client_kwargs)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            completion_kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.3,
            }
            if self.provider == "openrouter":
                completion_kwargs["extra_headers"] = {
                    "HTTP-Referer": os.getenv("APP_URL", "https://localhost"),
                    "X-Title": "PsychemetreAI",
                }

            resp = client.chat.completions.create(**completion_kwargs)
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM completion failed: {e}; falling back to NullLLM")
            return self.fallback.generate(prompt, system, max_tokens)


def get_llm() -> BaseLLM:
    """Return the configured LLM adapter or a deterministic fallback."""
    if os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"):
        return OpenAILLM()
    return NullLLM()
