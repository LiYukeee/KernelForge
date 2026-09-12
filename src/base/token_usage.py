"""LangChain callback utilities for provider-reported token usage."""

from __future__ import annotations

import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _token_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    count = int(value)
    return count if count >= 0 else None


def _first_token_count(*values: Any) -> int | None:
    for value in values:
        count = _token_count(value)
        if count is not None:
            return count
    return None


def _sum_optional(values: Iterable[int | None]) -> int | None:
    available = [value for value in values if value is not None]
    return sum(available) if available else None


@dataclass(frozen=True)
class TokenUsage:
    """Aggregated usage for one or more completed LLM calls."""

    llm_calls: int = 0
    usage_reported_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_hit_tokens: int | None = None
    cache_miss_tokens: int | None = None
    cache_creation_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_hit_reported_calls: int = 0
    cache_miss_reported_calls: int = 0
    cache_creation_reported_calls: int = 0
    reasoning_reported_calls: int = 0
    models: tuple[str, ...] = ()

    @classmethod
    def combine(cls, usages: Iterable[TokenUsage]) -> TokenUsage:
        """Combine stage or round usage without treating unavailable details as zero."""
        items = list(usages)
        return cls(
            llm_calls=sum(item.llm_calls for item in items),
            usage_reported_calls=sum(item.usage_reported_calls for item in items),
            input_tokens=sum(item.input_tokens for item in items),
            output_tokens=sum(item.output_tokens for item in items),
            total_tokens=sum(item.total_tokens for item in items),
            cache_hit_tokens=_sum_optional(
                item.cache_hit_tokens for item in items
            ),
            cache_miss_tokens=_sum_optional(
                item.cache_miss_tokens for item in items
            ),
            cache_creation_tokens=_sum_optional(
                item.cache_creation_tokens for item in items
            ),
            reasoning_tokens=_sum_optional(
                item.reasoning_tokens for item in items
            ),
            cache_hit_reported_calls=sum(
                item.cache_hit_reported_calls for item in items
            ),
            cache_miss_reported_calls=sum(
                item.cache_miss_reported_calls for item in items
            ),
            cache_creation_reported_calls=sum(
                item.cache_creation_reported_calls for item in items
            ),
            reasoning_reported_calls=sum(
                item.reasoning_reported_calls for item in items
            ),
            models=tuple(sorted({model for item in items for model in item.models})),
        )


class TokenUsageCallback(BaseCallbackHandler):
    """Collect normalized usage and DeepSeek-compatible raw cache counters."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._usages: list[TokenUsage] = []

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Record one completed model call."""
        del kwargs
        try:
            generation = response.generations[0][0]
        except (AttributeError, IndexError, TypeError):
            generation = None

        message = (
            generation.message
            if isinstance(generation, ChatGeneration)
            and isinstance(generation.message, AIMessage)
            else None
        )
        usage = _mapping(message.usage_metadata if message is not None else None)
        input_details = _mapping(usage.get("input_token_details"))
        output_details = _mapping(usage.get("output_token_details"))

        llm_output = _mapping(getattr(response, "llm_output", None))
        raw_usage = _mapping(llm_output.get("token_usage"))
        prompt_details = _mapping(raw_usage.get("prompt_tokens_details"))
        completion_details = _mapping(raw_usage.get("completion_tokens_details"))

        input_tokens = _first_token_count(
            usage.get("input_tokens"),
            raw_usage.get("prompt_tokens"),
            raw_usage.get("input_tokens"),
        )
        output_tokens = _first_token_count(
            usage.get("output_tokens"),
            raw_usage.get("completion_tokens"),
            raw_usage.get("output_tokens"),
        )
        total_tokens = _first_token_count(
            usage.get("total_tokens"),
            raw_usage.get("total_tokens"),
        )
        if (
            total_tokens is None
            and input_tokens is not None
            and output_tokens is not None
        ):
            total_tokens = input_tokens + output_tokens

        cache_hit_tokens = _first_token_count(
            input_details.get("cache_read"),
            raw_usage.get("prompt_cache_hit_tokens"),
            prompt_details.get("cached_tokens"),
        )
        cache_miss_tokens = _first_token_count(
            raw_usage.get("prompt_cache_miss_tokens")
        )
        if (
            cache_miss_tokens is None
            and input_tokens is not None
            and cache_hit_tokens is not None
            and cache_hit_tokens <= input_tokens
        ):
            cache_miss_tokens = input_tokens - cache_hit_tokens
        cache_creation_tokens = _first_token_count(
            input_details.get("cache_creation"),
            prompt_details.get("cache_write_tokens"),
        )
        reasoning_tokens = _first_token_count(
            output_details.get("reasoning"),
            completion_details.get("reasoning_tokens"),
        )

        response_metadata = _mapping(
            message.response_metadata if message is not None else None
        )
        model = next(
            (
                value
                for value in (
                    response_metadata.get("model_name"),
                    response_metadata.get("model"),
                    llm_output.get("model_name"),
                )
                if isinstance(value, str) and value
            ),
            None,
        )
        usage_reported = any(
            value is not None for value in (input_tokens, output_tokens, total_tokens)
        )
        item = TokenUsage(
            llm_calls=1,
            usage_reported_calls=int(usage_reported),
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            total_tokens=total_tokens or 0,
            cache_hit_tokens=cache_hit_tokens,
            cache_miss_tokens=cache_miss_tokens,
            cache_creation_tokens=cache_creation_tokens,
            reasoning_tokens=reasoning_tokens,
            cache_hit_reported_calls=int(cache_hit_tokens is not None),
            cache_miss_reported_calls=int(cache_miss_tokens is not None),
            cache_creation_reported_calls=int(cache_creation_tokens is not None),
            reasoning_reported_calls=int(reasoning_tokens is not None),
            models=(model,) if model is not None else (),
        )
        with self._lock:
            self._usages.append(item)

    def snapshot(self) -> TokenUsage:
        """Return an immutable aggregate of all calls observed so far."""
        with self._lock:
            return TokenUsage.combine(self._usages)
