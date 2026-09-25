"""
LangGraph Agent State Definition.

This module defines the typed state dict that flows through the entire
multi-agent LangGraph workflow. Every node in the graph reads from and
writes to this state.

State is immutable within a node — nodes return partial updates.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """
    Shared state for the multi-agent LangGraph workflow.

    Flows through all agents: Supervisor → Specialized Agent → Tools → Response.

    Fields marked with Annotated[list, add_messages] use LangGraph's built-in
    message reducer that appends new messages rather than replacing the list.
    """

    # ── Identity & Routing ─────────────────────────────────────────────────────
    workspace_id: str
    """Tenant workspace ID. Used for all data isolation."""

    conversation_id: str
    """WhatsApp conversation ID (UUID string)."""

    message_id: str
    """WhatsApp message ID (UUID string) being processed."""

    agent_run_id: str
    """AgentRun record ID for tracking and audit."""

    contact_wa_id: str
    """WhatsApp ID (phone number) of the customer."""

    contact_name: str | None
    """Display name of the customer from WhatsApp profile."""

    # ── Input Modality ─────────────────────────────────────────────────────────
    input_modality: str
    """
    How the customer sent their message.
    Values: 'text' | 'voice' | 'image' | 'document' | 'mixed'
    """

    raw_text: str | None
    """Original text body of the message (for text messages)."""

    transcription: str | None
    """STT transcription result (for voice messages)."""

    image_analysis: str | None
    """Vision model description of image content (for image messages)."""

    document_text: str | None
    """Extracted text from document (for document messages)."""

    media_id: str | None
    """WhatsApp media ID if message contains media."""

    language_detected: str | None
    """BCP-47 language code detected from content (e.g. 'en', 'hi', 'mr')."""

    # ── Processed Input ────────────────────────────────────────────────────────
    effective_text: str | None
    """
    The final text the agent should reason over.
    For text: raw_text
    For voice: transcription
    For image: image_analysis (+ any transcription if voice in image)
    For document: document_text
    """

    # ── Conversation History ───────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
    """
    LangChain message history for the LLM context.
    Uses add_messages reducer — always appended, never replaced.
    """

    conversation_history: list[dict[str, Any]]
    """
    Recent conversation turns as plain dicts for context injection.
    Format: [{"role": "user"|"assistant", "content": "...", "timestamp": "..."}]
    Limited to last N turns based on BusinessProfile.ai_max_response_length.
    """

    # ── Supervisor Decisions ───────────────────────────────────────────────────
    intent: str | None
    """
    Customer intent detected by the supervisor.
    Values: 'inquiry' | 'purchase' | 'support' | 'lead_capture' |
            'knowledge_query' | 'scheduling' | 'media_analysis' |
            'voice_query' | 'crm_action' | 'human_escalation' | 'unknown'
    """

    confidence_score: float | None
    """Intent confidence score from 0.0 to 1.0."""

    routed_to_agent: str | None
    """
    Which specialized agent the supervisor routed to.
    Values match AgentType enum: 'knowledge' | 'sales' | 'support' |
    'lead' | 'media' | 'voice' | 'scheduling' | 'crm' | 'human_escalation'
    """

    # ── Agent Output ───────────────────────────────────────────────────────────
    response_text: str | None
    """Final text response to send to the customer via WhatsApp."""

    response_voice: bool
    """
    If True, convert response_text to OGG/Opus audio and send as voice note.
    Only True when customer sent a voice note (reciprocal modality).
    """

    rag_context: list[dict[str, Any]]
    """
    Retrieved document chunks used for grounded responses.
    Format: [{"content": "...", "source": "...", "score": 0.9}]
    """

    tool_calls_made: list[dict[str, Any]]
    """
    Audit trail of all tool calls made during this agent run.
    Format: [{"tool": "...", "args": {...}, "result": "...", "timestamp": "..."}]
    """

    # ── Escalation ─────────────────────────────────────────────────────────────
    escalation_required: bool
    """True if human agent takeover is required."""

    escalation_reason: str | None
    """Why escalation was triggered (for the human agent's context)."""

    escalation_transcript: str | None
    """Formatted conversation summary for the human agent."""

    # ── Business Context ───────────────────────────────────────────────────────
    business_profile: dict[str, Any] | None
    """
    BusinessProfile config for this workspace (loaded once per run).
    Contains: ai_persona_name, ai_persona_tone, ai_custom_instructions,
    ai_use_emoji, ai_max_response_length, escalation_keywords, etc.
    """

    # ── Metrics ────────────────────────────────────────────────────────────────
    started_at: str | None
    """ISO timestamp when this agent run started."""

    retrieval_latency_ms: int | None
    """Time taken for vector store retrieval in milliseconds."""

    model_latency_ms: int | None
    """Time taken for LLM completion in milliseconds."""

    prompt_tokens: int | None
    """LLM prompt token count."""

    completion_tokens: int | None
    """LLM completion token count."""

    # ── Error State ────────────────────────────────────────────────────────────
    error: str | None
    """Error message if the agent run failed. None = success."""

    retry_count: int
    """Number of retries attempted for this run."""


def create_initial_state(
    workspace_id: str,
    conversation_id: str,
    message_id: str,
    agent_run_id: str,
    contact_wa_id: str,
    contact_name: str | None,
    input_modality: str,
    raw_text: str | None = None,
    media_id: str | None = None,
) -> AgentState:
    """
    Create a fresh AgentState for a new agent run.

    Args:
        workspace_id: Tenant workspace ID.
        conversation_id: WhatsApp conversation UUID.
        message_id: Inbound WhatsApp message UUID.
        agent_run_id: AgentRun record UUID.
        contact_wa_id: Customer's WhatsApp ID (phone number).
        contact_name: Customer display name.
        input_modality: 'text' | 'voice' | 'image' | 'document'
        raw_text: Message text body (for text messages).
        media_id: WhatsApp media ID (for media messages).

    Returns:
        A fully initialized AgentState ready for the LangGraph workflow.
    """
    from datetime import timezone
    return AgentState(
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        message_id=message_id,
        agent_run_id=agent_run_id,
        contact_wa_id=contact_wa_id,
        contact_name=contact_name,
        input_modality=input_modality,
        raw_text=raw_text,
        media_id=media_id,
        transcription=None,
        image_analysis=None,
        document_text=None,
        language_detected=None,
        effective_text=raw_text,  # Will be updated by modality handler
        messages=[],
        conversation_history=[],
        intent=None,
        confidence_score=None,
        routed_to_agent=None,
        response_text=None,
        response_voice=False,
        rag_context=[],
        tool_calls_made=[],
        escalation_required=False,
        escalation_reason=None,
        escalation_transcript=None,
        business_profile=None,
        started_at=datetime.now(tz=timezone.utc).isoformat(),
        retrieval_latency_ms=None,
        model_latency_ms=None,
        prompt_tokens=None,
        completion_tokens=None,
        error=None,
        retry_count=0,
    )
