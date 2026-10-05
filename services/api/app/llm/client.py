"""DeepSeek client used by the optional receipt interpretation pipeline.

The optimizer does not import or call this module. Receipt callers validate
the returned structure before it reaches application data.

Degradation (CC8): if the key is missing, the model is disabled, or a call
fails, `acomplete()`/`complete()` return None and callers fall back to
templates.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from ..config import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around the DeepSeek (OpenAI-compatible) chat API."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None
        if settings.llm_enabled and settings.deepseek_api_key:
            # Imported lazily so the app runs fine without the openai package.
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def model(self) -> str:
        return self._settings.deepseek_model

    def complete(self, system: str, user: str, max_tokens: int = 512) -> Optional[str]:
        """Synchronous wrapper (kept for stubs/back-compat)."""
        try:
            return asyncio.run(
                self.acomplete(system, user, max_tokens=max_tokens,
                               timeout=self._settings.llm_timeout_s)
            )
        except RuntimeError:
            # Already inside an event loop (async serving path) - never call
            # complete() there; use acomplete() directly.
            return None

    async def acomplete(
        self,
        system: str,
        user: str,
        max_tokens: int = 256,
        timeout: Optional[float] = None,
        temperature: float = 0.3,
    ) -> Optional[str]:
        """Run one receipt-support call and return None when unavailable."""
        if self._client is None:
            return None
        t0 = time.monotonic()
        try:
            coro = self._client.chat.completions.create(
                model=self._settings.deepseek_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            resp = await asyncio.wait_for(coro, timeout=timeout) if timeout else await coro
            text = (resp.choices[0].message.content or "").strip() or None
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.info("DeepSeek acomplete ok in %.0f ms (model=%s)", elapsed_ms, self._settings.deepseek_model)
            return text
        except Exception as exc:  # network, auth, rate limit, timeout -> degrade
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.warning(
                "DeepSeek call failed after %.0f ms, falling back to template: %s",
                elapsed_ms, exc,
            )
            return None
