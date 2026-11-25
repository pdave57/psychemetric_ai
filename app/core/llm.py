"""LLM provider interface, OpenAI adapter, and NullLLM circuit-breaker fallback."""

import asyncio
import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Size of each chunk yielded by the default (non-streaming) stream fallback so
# clients can render a typing effect even when the LLM adapter itself does not
# stream tokens.
_STREAM_CHUNK_CHARS = 24


def _text_chunks(text: str, size: int = _STREAM_CHUNK_CHARS):
    """Yield *text* in small slices so a consumer can render a streaming effect."""
    for i in range(0, len(text), size):
        yield text[i : i + size]


class BaseLLM(ABC):
    """Abstract interface for LLM completions."""

    @abstractmethod
    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 500) -> str:
        """Produce completion text."""
        pass

    async def stream_generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
    ) -> AsyncGenerator[str, None]:
        """Stream completion text as text chunks.

        The default implementation slices the synchronous ``generate`` output so
        every LLM adapter can participate in streaming UIs. Subclasses backed by
        streaming APIs should override this to yield real tokens.
        """
        text = self.generate(prompt, system, max_tokens)
        for chunk in _text_chunks(text):
            yield chunk
            await asyncio.sleep(0)


class NullLLM(BaseLLM):
    """Deterministic fallback when LLM is unconfigured, disabled, or circuit-broken."""

    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 500) -> str:
        logger.info("NullLLM called: returning deterministic framework guidance.")
        return (
            "Your reflective temperament pattern reflects your self-reported tendencies. "
            "Please review your quantitative scores for detailed insights."
        )

    async def stream_generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
    ) -> AsyncGenerator[str, None]:
        """Yield the deterministic text slice-by-slice with a short pause."""
        text = self.generate(prompt, system, max_tokens)
        for chunk in _text_chunks(text):
            yield chunk
            await asyncio.sleep(0.02)


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
                    "X-Title": "AgenblueAI",
                }

            resp = client.chat.completions.create(**completion_kwargs)
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM completion failed: {e}; falling back to NullLLM")
            return self.fallback.generate(prompt, system, max_tokens)

    async def stream_generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
    ) -> AsyncGenerator[str, None]:
        """Stream real completion tokens from the OpenAI-compatible API."""
        if not self.api_key:
            async for chunk in NullLLM().stream_generate(prompt, system, max_tokens):
                yield chunk
            return

        try:
            from openai import AsyncOpenAI

            client_kwargs = {"api_key": self.api_key, "timeout": 30.0}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url

            client = AsyncOpenAI(**client_kwargs)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            completion_kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.3,
                "stream": True,
            }
            if self.provider == "openrouter":
                completion_kwargs["extra_headers"] = {
                    "HTTP-Referer": os.getenv("APP_URL", "https://localhost"),
                    "X-Title": "PsychemetreAI",
                }

            stream = await client.chat.completions.create(**completion_kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"LLM streaming failed: {e}; falling back to NullLLM")
            async for chunk in NullLLM().stream_generate(prompt, system, max_tokens):
                yield chunk


def get_llm() -> BaseLLM:
    """Return the configured LLM adapter or a deterministic fallback."""
    if os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"):
        return OpenAILLM()
    return NullLLM()
