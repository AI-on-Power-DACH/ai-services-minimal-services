from __future__ import annotations

import logging
from typing import Any, Type, TypeVar, cast

import instructor
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from settings import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMSession:
    """Long-lived session for structured LLM calls via the instructor library.

    Create one instance at application start-up and reuse it across all
    requests.  The underlying OpenAI client keeps an HTTP connection pool
    whose size is governed by ``LLMConfig.max_batch_size``.

    Args:
        settings: Application settings.  Defaults to a fresh ``Settings()``
            instance so the class is usable without dependency injection.
    """

    def __init__(self, settings: Settings) -> None:
        cfg = settings.llm

        api_key = cfg.api_key.get_secret_value() or "no-key"

        http_client_kwargs: dict[str, Any] = {
            "max_keepalive_connections": cfg.max_batch_size,
            "max_connections": cfg.max_batch_size,
        }

        # instructor.from_openai wraps any OpenAI-compatible client
        self._client = instructor.from_openai(
            OpenAI(
                base_url=cfg.endpoint,
                api_key=api_key,
                max_retries=2,
                http_client=_build_httpx_client(**http_client_kwargs),
            )
        )
        self._model = cfg.model
        logger.info(
            "LLMSession initialised — endpoint=%s model=%s pool_size=%d",
            cfg.endpoint,
            cfg.model,
            cfg.max_batch_size,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(
        self,
        response_model: Type[T],
        prompt: str,
        *,
        system_prompt: str = "",
        examples: list[dict[str, str]] | None = None,
        max_tokens: int = 1024,
    ) -> T:
        """Call the LLM and return a validated *response_model* instance.

        Args:
            response_model: A Pydantic model class whose schema is sent to the
                LLM and whose instance is returned on success.
            prompt: The user prompt.
            system_prompt: Optional system/instruction prompt prepended before
                examples.
            examples: Optional few-shot examples as a list of
                ``{"role": "user"|"assistant", "content": "..."}`` dicts.
            max_tokens: Maximum tokens the LLM may generate.

        Returns:
            A validated instance of *response_model*.

        Raises:
            instructor.exceptions.InstructorRetryException: When the LLM
                response cannot be parsed into *response_model* after retries.
            openai.OpenAIError: On network or API-level failures.
        """
        messages = _build_messages(system_prompt, examples or [], prompt)
        return self._client.chat.completions.create(  # type: ignore[call-overload]
            model=self._model,
            response_model=response_model,
            messages=messages,
            max_tokens=max_tokens,
        )


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _build_messages(
    system_prompt: str,
    examples: list[dict[str, str]],
    user_prompt: str,
) -> list[ChatCompletionMessageParam]:
    messages: list[ChatCompletionMessageParam] = []
    if system_prompt:
        messages.append(cast(ChatCompletionMessageParam, {"role": "system", "content": system_prompt}))
    for ex in examples:
        messages.append(cast(ChatCompletionMessageParam, ex))
    messages.append(cast(ChatCompletionMessageParam, {"role": "user", "content": user_prompt}))
    return messages


def _build_httpx_client(
    max_keepalive_connections: int,
    max_connections: int,
) -> Any:
    """Return an httpx.Client configured with the given connection limits."""
    import httpx2

    limits = httpx2.Limits(
        max_keepalive_connections=max_keepalive_connections,
        max_connections=max_connections,
    )
    return httpx2.Client(limits=limits)
