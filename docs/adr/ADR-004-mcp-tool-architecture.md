# ADR-004: MCP Tool Architecture

## Status
Accepted

## Context
LLM Agents require tools to interact with external systems (DB, CRM, Knowledge Base, APIs). Managing these tools natively within LangChain/LangGraph can become disorganized and hard to share across agents.

## Decision
Adopt the **Model Context Protocol (MCP)** via the `fastmcp` Python library to expose tools as MCP servers. Agents will use an MCP client to list and invoke tools.

## Consequences
- **Pros:** Standardized protocol. Easy to add/remove tools without touching agent code. Built-in schema validation. Tool layer is entirely decoupled.
- **Cons:** Slight overhead in invoking tools via a protocol layer.

## Security Note
MCP is NOT a security boundary. Permission checks, RBAC validations, and workspace isolation MUST run in the backend before the tool executes. Tools will have designated risk levels (LOW/MEDIUM/HIGH).

## Tool Categories
- Knowledge Retrieval
- CRM Operations
- Calendar/Scheduling
- WhatsApp Messaging
- Analytics
