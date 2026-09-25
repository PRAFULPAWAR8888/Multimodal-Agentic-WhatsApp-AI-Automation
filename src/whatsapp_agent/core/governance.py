"""
LLM Token & Context Governance Layer.

Centralizes token counting, context selection, and budget management to
prevent unnecessary token usage and enforce input/output size limits.
"""
from __future__ import annotations

import logging
from typing import Any
import tiktoken
from pydantic import BaseModel

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import AppError

logger = logging.getLogger(__name__)


class GovernanceError(AppError):
    """Raised when a governance policy rejects a request."""
    pass


class TokenEstimator:
    """Estimates token counts using tiktoken (OpenAI tokenizer)."""
    
    _encoding = None
    
    @classmethod
    def get_encoding(cls) -> tiktoken.Encoding:
        if cls._encoding is None:
            settings = get_settings()
            try:
                # Get exact encoding for model, or fallback to o200k_base (gpt-4o)
                cls._encoding = tiktoken.encoding_for_model(settings.openai_model)
            except KeyError:
                cls._encoding = tiktoken.get_encoding("o200k_base")
        return cls._encoding

    @classmethod
    def count_tokens(cls, text: str) -> int:
        """Count tokens in a text string."""
        if not text:
            return 0
        return len(cls.get_encoding().encode(text))

    @classmethod
    def truncate_to_tokens(cls, text: str, max_tokens: int) -> str:
        """Truncate text to a maximum number of tokens."""
        if not text or max_tokens <= 0:
            return ""
        
        encoding = cls.get_encoding()
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
            
        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)


class InputGuardResult(BaseModel):
    """Result of the input guard evaluation."""
    is_valid: bool
    text: str
    rejection_reason: str | None = None
    estimated_tokens: int = 0
    word_count: int = 0
    was_truncated: bool = False


class InputSizeGuard:
    """Enforces word and token limits on user inputs."""
    
    @staticmethod
    def evaluate(text: str) -> InputGuardResult:
        """
        Evaluate input text against configured limits.
        If it exceeds limits, apply the configured oversize action.
        """
        if not text:
            return InputGuardResult(is_valid=True, text="")
            
        settings = get_settings()
        
        if not settings.llm_enable_input_limit:
            return InputGuardResult(
                is_valid=True, 
                text=text, 
                estimated_tokens=TokenEstimator.count_tokens(text),
                word_count=len(text.split())
            )
            
        # 1. Measure
        word_count = len(text.split())
        estimated_tokens = TokenEstimator.count_tokens(text)
        
        # 2. Check if it violates limits
        violates_word_limit = word_count > settings.llm_max_input_words
        violates_token_limit = estimated_tokens > settings.llm_max_input_tokens
        
        if not violates_word_limit and not violates_token_limit:
            return InputGuardResult(
                is_valid=True,
                text=text,
                estimated_tokens=estimated_tokens,
                word_count=word_count
            )
            
        # 3. Handle violations according to configured action
        action = settings.llm_oversize_action.lower()
        
        logger.warning(
            "input_limit_exceeded", 
            words=word_count, 
            tokens=estimated_tokens,
            action=action
        )
        
        if action == "reject":
            return InputGuardResult(
                is_valid=False,
                text="",
                rejection_reason="Your message is too long. Please send it in smaller parts.",
                estimated_tokens=estimated_tokens,
                word_count=word_count
            )
        elif action == "truncate":
            # Determine which limit was hit first and truncate accordingly
            if violates_token_limit:
                truncated_text = TokenEstimator.truncate_to_tokens(text, settings.llm_max_input_tokens)
            else:
                # Word truncation
                truncated_text = " ".join(text.split()[:settings.llm_max_input_words])
                
            return InputGuardResult(
                is_valid=True,
                text=truncated_text,
                estimated_tokens=TokenEstimator.count_tokens(truncated_text),
                word_count=len(truncated_text.split()),
                was_truncated=True
            )
        else:
            # Fallback to reject if action is unknown or summarize is not implemented for input
            return InputGuardResult(
                is_valid=False,
                text="",
                rejection_reason="Message size exceeds allowed limits.",
                estimated_tokens=estimated_tokens,
                word_count=word_count
            )

class ContextManager:
    """Manages conversational context sizing according to budget."""

    @staticmethod
    def filter_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Takes a list of past messages (oldest to newest) and returns a subset
        that fits within the configured LLM context token/word budget.
        
        Prioritizes:
        1. System prompt (assumed added later by agents)
        2. Current user message (assumed handled by InputSizeGuard separately)
        3. Most recent historical messages
        """
        settings = get_settings()
        if not settings.llm_enable_context_limit or not messages:
            return messages

        max_tokens = settings.llm_context_max_tokens
        
        filtered_messages = []
        current_tokens = 0
        
        # Iterate backwards (newest to oldest)
        for msg in reversed(messages):
            # Message format is typically {"role": "user", "content": "..."}
            content = msg.get("content", "")
            if not content:
                continue
                
            msg_tokens = TokenEstimator.count_tokens(content)
            
            # If adding this entire message exceeds the budget
            if current_tokens + msg_tokens > max_tokens:
                action = settings.llm_context_overflow_action.lower()
                
                if action == "truncate":
                    # We can truncate the oldest message that fits partially
                    remaining_tokens = max_tokens - current_tokens
                    if remaining_tokens > 10:  # Only if we can fit a meaningful chunk
                        truncated_content = TokenEstimator.truncate_to_tokens(content, remaining_tokens)
                        truncated_msg = {**msg, "content": truncated_content}
                        filtered_messages.append(truncated_msg)
                        logger.warning("context_message_truncated", tokens_kept=remaining_tokens)
                
                # Stop processing older messages
                break
                
            # Fits perfectly
            filtered_messages.append(msg)
            current_tokens += msg_tokens

        # Reverse back to chronological order (oldest to newest)
        filtered_messages.reverse()
        
        logger.debug(
            "context_history_filtered", 
            original_count=len(messages), 
            filtered_count=len(filtered_messages),
            estimated_tokens=current_tokens
        )
        return filtered_messages

class ResponseBudgetManager:
    """Assigns output token budgets based on conversational intent."""
    
    @staticmethod
    def get_output_budget(intent: str) -> int:
        """
        Return the configured max_tokens for a given intent.
        SHORT: greetings, simple questions
        DETAILED: analysis, scheduling, summaries
        NORMAL: everything else
        """
        settings = get_settings()
        
        short_intents = {"greeting", "thanks", "bye"}
        detailed_intents = {"media_analysis", "knowledge_query", "crm_action"}
        
        if intent in short_intents:
            return settings.llm_short_max_output_tokens
        elif intent in detailed_intents:
            return settings.llm_detailed_max_output_tokens
            
        return settings.llm_normal_max_output_tokens

from collections import defaultdict
from datetime import datetime, date

class BudgetTracker:
    """In-memory tracker for demo session and daily token budgets."""
    
    _daily_usage: dict[date, int] = defaultdict(int)
    _session_usage: dict[str, int] = defaultdict(int)

    @classmethod
    def add_usage(cls, session_id: str, total_tokens: int) -> None:
        today = datetime.utcnow().date()
        cls._daily_usage[today] += total_tokens
        if session_id:
            cls._session_usage[session_id] += total_tokens

    @classmethod
    def check_budgets(cls, session_id: str, estimated_tokens: int) -> None:
        settings = get_settings()
        today = datetime.utcnow().date()
        
        # Check Daily
        if settings.llm_enable_cost_estimation:
            current_daily = cls._daily_usage[today]
            if current_daily + estimated_tokens > settings.llm_max_tokens_per_day:
                raise GovernanceError(f"Daily demo token budget exceeded ({current_daily} + {estimated_tokens} > {settings.llm_max_tokens_per_day}).")
                
        # Check Session
        if settings.llm_enable_session_budget and session_id:
            current_session = cls._session_usage[session_id]
            if current_session + estimated_tokens > settings.llm_max_tokens_per_session:
                raise GovernanceError(f"Session token budget exceeded ({current_session} + {estimated_tokens} > {settings.llm_max_tokens_per_session}).")


