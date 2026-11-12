"""LLM provider interface, OpenAI adapter, and NullLLM circuit-breaker fallback."""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

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
    """Adapter for OpenAI models with error trapping and graceful fallback."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.fallback = NullLLM()

    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 500) -> str:
        if not self.api_key:
            logger.warning("No OPENAI_API_KEY detected; using NullLLM fallback.")
            return self.fallback.generate(prompt, system, max_tokens)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, timeout=15.0)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI completion failed: {e}; falling back to NullLLM")
            return self.fallback.generate(prompt, system, max_tokens)


def get_llm() -> BaseLLM:
    """Return default configured LLM or NullLLM."""
    if os.getenv("OPENAI_API_KEY"):
        return OpenAILLM()
    return NullLLM()
