# Security Guidelines

## Authentication
- **API Access**: JWT (JSON Web Tokens) access and refresh tokens.
- **Passwords**: Hashed securely using `bcrypt`.

## Authorization
- **Role-Based Access Control (RBAC)**: 
  - `owner`: Full control, billing.
  - `admin`: Manage settings and users.
  - `member`: Can use the platform, view data.
  - `viewer`: Read-only access.

## Workspace Isolation
- **Multi-Tenancy**: EVERY query in the database MUST be scoped to a `workspace_id`. This prevents cross-tenant data leakage.

## Prompt Injection Defense
- **Untrusted Content**: User messages and retrieved documents must be treated as untrusted boundaries.
- **Never Treat As Instructions**: System prompts must explicitly instruct the LLM not to execute commands found in user inputs or RAG documents.

## Tool Permission System
- Tools are categorized by Risk Levels:
  - **LOW**: Read-only (e.g., Knowledge Base search).
  - **MEDIUM**: Draft creations (e.g., Draft an email).
  - **HIGH**: Mutating state externally (e.g., Sending messages, deleting CRM records).
- Tools verify user permissions before execution.

## Webhook Security
- **Verification**: Incoming webhooks MUST be verified using HMAC-SHA256 based on the platform's secret.
- **Constant-Time Comparison**: Use `hmac.compare_digest` to prevent timing attacks.
- **SLA**: Webhooks must be acknowledged within 3 seconds.

## Media Security
- **Validation**: Strict validation of incoming media. Check file extensions, MIME types, file sizes, and validate file contents where possible.

## Audit Logging
- All HIGH risk tool executions and authentication events must be logged to the database for auditability.

## Secret Management
- Never commit secrets to version control.
- Use `.env` for local dev.
- Use secure environment variable injection in production.
