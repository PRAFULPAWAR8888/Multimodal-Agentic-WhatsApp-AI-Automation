# ADR-009: Tool Execution Security, Risk Classification, and Sandboxing

## Status
Accepted

## Context
In an agentic architecture, LLMs are granted the power to call tools to retrieve data or mutate external state (CRM updates, appointment bookings, outbound WhatsApp messaging). Unrestricted tool calling invites catastrophic risks: prompt injection via customer input tricking the model into unauthorized mutations, privilege escalation, or resource abuse.

## Decision
We implement a **Strict 5-Stage Tool Execution Gatekeeper**:

1. **Explicit Registry & Schema Validation**:
   - Every tool must be registered in the `ToolRegistry` with a strict Pydantic input schema and output schema.
   - LLM-generated arguments that do not pass Pydantic validation are rejected immediately.
2. **Agent Permission Scopes**:
   - Tools define `allowed_agents: list[AgentType]`. For example, only the `CRM Agent` can call `update_hubspot_contact()`; the `Knowledge Agent` cannot.
3. **Workspace RBAC Validation**:
   - The tool runner checks whether the calling tenant's workspace has enabled the specific integration/tool.
4. **Risk Classification & Human Approval Gate**:
   - **LOW Risk** (read-only): `search_knowledge()`, `check_calendar_availability()`. Auto-executed by the engine.
   - **MEDIUM Risk** (internal mutations): `create_lead()`, `update_contact_notes()`. Auto-executed with schema validation and parameter bounds checking.
   - **HIGH Risk** (external, financial, or irreversible): `book_calendar_appointment()`, `create_hubspot_deal()`, `send_outbound_broadcast()`. Requires explicit confirmation or human agent approval.
5. **Immutable Audit Logging**:
   - Every tool execution (including rejected attempts) logs an entry to the `audit_logs` table capturing `workspace_id`, `agent_id`, `tool_name`, `input_params`, `risk_level`, and execution outcome.

## Consequences
- **Pros**: Robust defense-in-depth against prompt injection and autonomous agent drift; complete auditability for compliance.
- **Cons**: Adds small computational validation latency (~2–5ms) prior to tool invocation.
