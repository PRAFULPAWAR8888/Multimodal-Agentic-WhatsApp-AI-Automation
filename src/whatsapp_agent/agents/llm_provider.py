"""
LLM Provider Abstraction.

Wraps the underlying LLM API with:
- Retry logic (tenacity) for rate limits and transient errors
- Token usage tracking
- Structured logging
- Provider abstraction interface compatibility

This is the primary LLM used for all agent reasoning.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any

from openai import AsyncOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from whatsapp_agent.config.settings import LLMProvider, get_settings
from whatsapp_agent.core.exceptions import (
    LLMContextLengthError,
    LLMError,
    LLMRateLimitError,
)
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


class LLMUsage:
    """Token usage tracking from an LLM response."""

    def __init__(self, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class LLMResponse:
    """Structured response from an LLM call."""

    def __init__(
        self,
        content: str,
        usage: LLMUsage,
        model: str,
        latency_ms: int,
        finish_reason: str,
    ) -> None:
        self.content = content
        self.usage = usage
        self.model = model
        self.latency_ms = latency_ms
        self.finish_reason = finish_reason  # 'stop' | 'length' | 'content_filter'


class BaseLLMProvider(ABC):
    """Abstract interface for all LLM providers."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        """Send a completion request to the LLM API."""
        pass

    @abstractmethod
    async def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[dict[str, Any], LLMUsage]:
        """Complete a request expecting a JSON response."""
    @abstractmethod
    async def complete_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[LLMResponse, list[dict[str, Any]]]:
        """Complete a request and optionally trigger tools."""
        pass

# Module-level singleton client
_openai_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Return or create the singleton AsyncOpenAI client."""
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_request_timeout,
            max_retries=0,  # We handle retries with tenacity for better control
        )
    return _openai_client


class OpenAILLMProvider(BaseLLMProvider):
    """
    OpenAI GPT LLM provider for all agent reasoning.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = get_openai_client()
        self._model = self._settings.openai_model
        self._max_tokens = self._settings.openai_max_tokens
        self._temperature = self._settings.openai_temperature

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history[-10:])

        messages.append({"role": "user", "content": user_message})

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        logger.debug(
            "llm_request",
            model=self._model,
            message_count=len(messages),
            temperature=kwargs["temperature"],
        )

        start_time = time.monotonic()
        try:
            response = await self._client.chat.completions.create(**kwargs)

        except RateLimitError as exc:
            logger.warning("llm_rate_limited", model=self._model, error=str(exc))
            raise LLMRateLimitError(
                f"OpenAI rate limit exceeded: {exc}",
                code="LLM_RATE_LIMIT",
            ) from exc

        except Exception as exc:
            error_str = str(exc).lower()
            if "context_length_exceeded" in error_str or "maximum context length" in error_str:
                raise LLMContextLengthError(
                    f"Prompt too long for {self._model}: {exc}",
                ) from exc

            logger.error("llm_error", model=self._model, error=str(exc))
            raise LLMError(f"OpenAI API call failed: {exc}") from exc

        latency_ms = round((time.monotonic() - start_time) * 1000)
        content = response.choices[0].message.content or ""
        finish_reason = response.choices[0].finish_reason or "stop"

        usage = LLMUsage(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            total_tokens=response.usage.total_tokens if response.usage else 0,
        )

        logger.info(
            "llm_response",
            model=self._model,
            finish_reason=finish_reason,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            latency_ms=latency_ms,
        )

        return LLMResponse(
            content=content,
            usage=usage,
            model=self._model,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
        )

    async def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[dict[str, Any], LLMUsage]:
        response = await self.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            conversation_history=conversation_history,
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError as exc:
            logger.error(
                "llm_json_parse_error",
                content_preview=response.content[:200],
                error=str(exc),
            )
            raise LLMError(
                f"LLM returned invalid JSON: {exc}",
                details={"raw_content": response.content[:500]},
            ) from exc

        return parsed, response.usage


    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
    async def complete_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> tuple[LLMResponse, list[dict[str, Any]]]:
        
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history[-10:])
        messages.append({"role": "user", "content": user_message})

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }

        start_time = time.monotonic()
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            logger.error("llm_tool_request_failed", error=str(exc))
            raise LLMError(f"LLM tool request failed: {exc}") from exc

        latency_ms = round((time.monotonic() - start_time) * 1000)
        choice = response.choices[0]
        
        llm_resp = LLMResponse(
            content=choice.message.content or "",
            usage=LLMUsage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            ),
            model=response.model,
            latency_ms=latency_ms,
            finish_reason=choice.finish_reason,
        )

        tool_calls_out = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls_out.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })

        return llm_resp, tool_calls_out


class OllamaLLMProvider(OpenAILLMProvider):
    """
    Ollama LLM provider using Ollama's OpenAI-compatible endpoint.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._model = self._settings.ollama_model
        
        base_url = self._settings.ollama_base_url
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
            
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key="ollama", # required but ignored by Ollama
            timeout=self._settings.openai_request_timeout,
            max_retries=0,
        )
        self._max_tokens = self._settings.openai_max_tokens
        self._temperature = self._settings.openai_temperature

class FallbackLLMProvider(BaseLLMProvider):
    """
    Tries the primary provider first, falls back to the secondary if it fails.
    """
    def __init__(self, primary: BaseLLMProvider, fallback: BaseLLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        try:
            return await self.primary.complete(system_prompt, user_message, conversation_history, temperature, max_tokens, response_format)
        except Exception as e:
            logger.warning("primary_llm_failed_using_fallback", error=str(e))
            return await self.fallback.complete(system_prompt, user_message, conversation_history, temperature, max_tokens, response_format)

    async def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[dict[str, Any], LLMUsage]:
        try:
            return await self.primary.complete_json(system_prompt, user_message, conversation_history)
        except Exception as e:
            logger.warning("primary_llm_failed_using_fallback", error=str(e))
            return await self.fallback.complete_json(system_prompt, user_message, conversation_history)

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[LLMResponse, list[dict[str, Any]]]:
        try:
            return await self.primary.complete_with_tools(system_prompt, user_message, tools, conversation_history)
        except Exception as e:
            logger.warning("primary_llm_failed_using_fallback", error=str(e))
            return await self.fallback.complete_with_tools(system_prompt, user_message, tools, conversation_history)


class MockLLMProvider(BaseLLMProvider):
    """
    Mock LLM provider for deterministic offline testing without API costs.
    """

    def __init__(self) -> None:
        self._model = "mock-llm"
        self.mock_response = "This is a mock text response."
        self.mock_json_response = {
            "intent": "inquiry",
            "confidence": 0.99,
            "reasoning": "Mock reasoning for testing",
            "escalate_to_human": False,
            "language": "en"
        }

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        usage = LLMUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        return LLMResponse(
            content=self.mock_response,
            usage=usage,
            model=self._model,
            latency_ms=10,
            finish_reason="stop",
        )

    async def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[dict[str, Any], LLMUsage]:
        usage = LLMUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        return self.mock_json_response, usage

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[LLMResponse, list[dict[str, Any]]]:
        """Mock tool calling — returns a text response with no tool calls."""
        usage = LLMUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        response = LLMResponse(
            content=self.mock_response,
            usage=usage,
            model=self._model,
            latency_ms=10,
            finish_reason="stop",
        )
        return response, []  # No tool calls in mock mode


class LLMGateway(BaseLLMProvider):
    """
    Governance wrapper around any LLM provider.
    Enforces request budgets and performs centralized logging/cost estimation.
    """
    def __init__(self, inner_provider: BaseLLMProvider) -> None:
        self.inner = inner_provider
        self.settings = get_settings()

    def _check_budget(self, system_prompt: str, user_message: str, history: list[dict[str, str]] | None, output_budget: int | None = None) -> None:
        if not self.settings.llm_enable_output_limit:
            return
            
        from whatsapp_agent.core.governance import TokenEstimator, GovernanceError, BudgetTracker
        
        # Estimate input tokens
        input_tokens = TokenEstimator.count_tokens(system_prompt) + TokenEstimator.count_tokens(user_message)
        
        # Estimate context tokens
        context_tokens = 0
        if history:
            for msg in history:
                context_tokens += TokenEstimator.count_tokens(msg.get("content", ""))
                
        # Combine
        expected_output = output_budget or self.settings.llm_normal_max_output_tokens
        total_estimated = input_tokens + context_tokens + expected_output
        
        budget = self.settings.llm_max_tokens_per_request
        
        if total_estimated > budget:
            logger.error("budget_exceeded", estimated=total_estimated, budget=budget)
            raise GovernanceError(f"Request exceeds token budget ({total_estimated} > {budget}). Reduce context or input.")
            
        # Also check global/session budgets
        BudgetTracker.check_budgets("demo_session", total_estimated)
        
    def _record_usage(self, usage: LLMUsage) -> None:
        from whatsapp_agent.core.governance import BudgetTracker
        if usage:
            BudgetTracker.add_usage("demo_session", usage.total_tokens)

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        self._check_budget(system_prompt, user_message, conversation_history, max_tokens)
        resp = await self.inner.complete(
            system_prompt, user_message, conversation_history, temperature, max_tokens, response_format
        )
        self._record_usage(resp.usage)
        return resp

    async def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[dict[str, Any], LLMUsage]:
        self._check_budget(system_prompt, user_message, conversation_history)
        parsed, usage = await self.inner.complete_json(system_prompt, user_message, conversation_history)
        self._record_usage(usage)
        return parsed, usage

    async def complete_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[LLMResponse, list[dict[str, Any]]]:
        self._check_budget(system_prompt, user_message, conversation_history)
        resp, tool_calls = await self.inner.complete_with_tools(system_prompt, user_message, tools, conversation_history)
        self._record_usage(resp.usage)
        return resp, tool_calls


# Module-level singleton for use in agents
_llm_provider: BaseLLMProvider | None = None


def get_llm_provider() -> BaseLLMProvider:
    """
    Return the singleton LLM provider wrapped in the Governance Gateway.
    """
    global _llm_provider
    if _llm_provider is None:
        primary = OpenAILLMProvider()
        fallback = OllamaLLMProvider()
        inner = FallbackLLMProvider(primary, fallback)
        _llm_provider = LLMGateway(inner)
        
    return _llm_provider
