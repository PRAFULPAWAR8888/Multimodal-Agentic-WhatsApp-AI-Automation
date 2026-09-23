# ADR-007: Multi-Tenancy and Data Isolation Architecture

## Status
Accepted

## Context
The platform is designed to serve multiple businesses (tenants), each managing its own WhatsApp Business accounts, customer contacts, conversations, knowledge bases, agent personas, and CRM credentials. Cross-tenant data leakage is a critical security vulnerability and would violate data privacy laws (GDPR, DPDP).

## Decision
We implement a **shared-database, shared-schema multi-tenancy model** with mandatory `workspace_id` scoping at the application repository layer.

1. **Entity Association**: Every tenant-owned database table (`whatsapp_accounts`, `whatsapp_conversations`, `whatsapp_messages`, `knowledge_sources`, `document_chunks`, `leads`, `audit_logs`, `agent_runs`) contains a non-nullable foreign key column:
   ```sql
   workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE
   ```
2. **Repository Boundary**: All database query abstractions (Repositories/Services) enforce `workspace_id` filtering as a required argument. Direct unfiltered queries from API handlers are strictly forbidden.
3. **Session Context**: The authenticated user's active `workspace_id` is extracted from the JWT token and injected via FastAPI dependency injection into every request state.
4. **Automated Tenant Isolation Tests**: A dedicated test suite will attempt cross-tenant reads and mutations (e.g., Tenant A querying Tenant B's conversations) to ensure 403/404 isolation is always maintained.

## Consequences
- **Pros**: Low infrastructure cost, straightforward migrations via Alembic, high resource utilization across small and medium business tenants.
- **Cons**: Requires continuous developer diligence to ensure `workspace_id` is never omitted in query filters.

## Alternatives Considered
- **Database-per-tenant**: Extreme operational overhead, complex connection pooling, prohibitive cost on small servers.
- **Schema-per-tenant (PostgreSQL schemas)**: Complex migration management across hundreds of schemas; difficult connection pool sharing.
