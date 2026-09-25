"""initial_schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # 2. Create enum types
    workspace_role_enum = sa.Enum('owner', 'admin', 'member', 'viewer', name='workspace_role_enum')
    conversation_status_enum = sa.Enum('active', 'paused', 'human_assigned', 'closed', 'escalated', name='conversation_status_enum')
    message_type_enum = sa.Enum('text', 'image', 'audio', 'video', 'document', 'sticker', 'location', 'reaction', 'unknown', name='message_type_enum')
    message_direction_enum = sa.Enum('inbound', 'outbound', name='message_direction_enum')
    message_status_enum = sa.Enum('received', 'queued', 'processing', 'sent', 'delivered', 'read', 'failed', name='message_status_enum')
    modality_enum = sa.Enum('text', 'voice', 'image', 'document', 'mixed', name='modality_enum')
    agent_type_enum = sa.Enum('supervisor', 'knowledge', 'sales', 'support', 'lead', 'media', 'voice', 'scheduling', 'crm', 'human_escalation', name='agent_type_enum')
    agent_run_status_enum = sa.Enum('pending', 'running', 'completed', 'failed', 'escalated', 'timed_out', name='agent_run_status_enum')
    knowledge_source_type_enum = sa.Enum('pdf', 'website', 'text', 'faq', 'product_catalog', 'policy', 'manual', 'csv', 'image', name='knowledge_source_type_enum')
    knowledge_source_status_enum = sa.Enum('pending', 'processing', 'active', 'failed', 'outdated', name='knowledge_source_status_enum')
    lead_status_enum = sa.Enum('new', 'contacted', 'qualified', 'proposal_sent', 'negotiation', 'won', 'lost', 'disqualified', name='lead_status_enum')
    lead_intent_enum = sa.Enum('purchase', 'inquiry', 'support', 'demo_request', 'pricing', 'partnership', 'other', name='lead_intent_enum')
    
    # Audit event types based on standard system operations
    audit_event_type_enum = sa.Enum(
        'user_login', 'user_logout', 'workspace_created', 'workspace_updated', 'workspace_deleted',
        'member_added', 'member_removed', 'member_role_changed',
        'agent_run_started', 'agent_run_completed', 'agent_run_failed',
        'knowledge_source_added', 'knowledge_source_updated', 'knowledge_source_deleted',
        'lead_created', 'lead_updated', 'lead_status_changed',
        'whatsapp_account_connected', 'whatsapp_account_disconnected',
        'security_alert', 'billing_update',
        name='audit_event_type_enum'
    )

    # 3. Create tables in dependency order

    # a. users table
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('is_superuser', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # b. workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('owner_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_workspaces_owner_id', 'workspaces', ['owner_id'])

    # c. workspace_members table
    op.create_table(
        'workspace_members',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', workspace_role_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_member')
    )
    op.create_index('ix_workspace_members_workspace_id', 'workspace_members', ['workspace_id'])
    op.create_index('ix_workspace_members_user_id', 'workspace_members', ['user_id'])

    # d. business_profiles table
    op.create_table(
        'business_profiles',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )

    # e. whatsapp_accounts table
    op.create_table(
        'whatsapp_accounts',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('phone_number', sa.String(50), nullable=False, unique=True),
        sa.Column('waba_id', sa.String(255), nullable=False),
        sa.Column('phone_number_id', sa.String(255), nullable=False),
        sa.Column('access_token', sa.String(1024), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_whatsapp_accounts_workspace_id', 'whatsapp_accounts', ['workspace_id'])

    # f. whatsapp_contacts table
    op.create_table(
        'whatsapp_contacts',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('wa_id', sa.String(50), nullable=False),
        sa.Column('profile_name', sa.String(255), nullable=True),
        sa.Column('phone_number', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('workspace_id', 'wa_id', name='uq_contact_workspace_wa_id')
    )
    op.create_index('ix_whatsapp_contacts_workspace_id', 'whatsapp_contacts', ['workspace_id'])
    op.create_index('ix_whatsapp_contacts_wa_id', 'whatsapp_contacts', ['wa_id'])

    # g. whatsapp_conversations table
    op.create_table(
        'whatsapp_conversations',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.UUID(as_uuid=True), sa.ForeignKey('whatsapp_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contact_id', sa.UUID(as_uuid=True), sa.ForeignKey('whatsapp_contacts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', conversation_status_enum, server_default='active', nullable=False),
        sa.Column('assigned_user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_whatsapp_conversations_workspace_id', 'whatsapp_conversations', ['workspace_id'])
    op.create_index('ix_whatsapp_conversations_account_id', 'whatsapp_conversations', ['account_id'])
    op.create_index('ix_whatsapp_conversations_contact_id', 'whatsapp_conversations', ['contact_id'])

    # h. whatsapp_messages table
    op.create_table(
        'whatsapp_messages',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', sa.UUID(as_uuid=True), sa.ForeignKey('whatsapp_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.UUID(as_uuid=True), sa.ForeignKey('whatsapp_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contact_id', sa.UUID(as_uuid=True), sa.ForeignKey('whatsapp_contacts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('wa_message_id', sa.String(255), nullable=False, unique=True),
        sa.Column('direction', message_direction_enum, nullable=False),
        sa.Column('type', message_type_enum, nullable=False),
        sa.Column('status', message_status_enum, nullable=False),
        sa.Column('content', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_whatsapp_messages_workspace_id', 'whatsapp_messages', ['workspace_id'])
    op.create_index('ix_whatsapp_messages_conversation_id', 'whatsapp_messages', ['conversation_id'])
    op.create_index('ix_whatsapp_messages_wa_message_id', 'whatsapp_messages', ['wa_message_id'])

    # i. agent_runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', sa.UUID(as_uuid=True), sa.ForeignKey('whatsapp_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trigger_message_id', sa.UUID(as_uuid=True), sa.ForeignKey('whatsapp_messages.id', ondelete='SET NULL'), nullable=True),
        sa.Column('agent_type', agent_type_enum, nullable=False),
        sa.Column('status', agent_run_status_enum, nullable=False),
        sa.Column('modality', modality_enum, server_default='text', nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_agent_runs_workspace_id', 'agent_runs', ['workspace_id'])
    op.create_index('ix_agent_runs_conversation_id', 'agent_runs', ['conversation_id'])

    # j. knowledge_sources table
    op.create_table(
        'knowledge_sources',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('type', knowledge_source_type_enum, nullable=False),
        sa.Column('status', knowledge_source_status_enum, server_default='pending', nullable=False),
        sa.Column('content_uri', sa.String(1024), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_knowledge_sources_workspace_id', 'knowledge_sources', ['workspace_id'])

    # k. document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_id', sa.UUID(as_uuid=True), sa.ForeignKey('knowledge_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_document_chunks_workspace_id', 'document_chunks', ['workspace_id'])
    op.create_index('ix_document_chunks_source_id', 'document_chunks', ['source_id'])
    # HNSW or IVFFlat index for embedding
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

    # l. leads table
    op.create_table(
        'leads',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contact_id', sa.UUID(as_uuid=True), sa.ForeignKey('whatsapp_contacts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', sa.UUID(as_uuid=True), sa.ForeignKey('whatsapp_conversations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', lead_status_enum, server_default='new', nullable=False),
        sa.Column('intent', lead_intent_enum, nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('custom_fields', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_leads_workspace_id', 'leads', ['workspace_id'])
    op.create_index('ix_leads_contact_id', 'leads', ['contact_id'])

    # m. audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', audit_event_type_enum, nullable=False),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('resource_type', sa.String(255), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_audit_logs_workspace_id', 'audit_logs', ['workspace_id'])
    op.create_index('ix_audit_logs_event_type', 'audit_logs', ['event_type'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('audit_logs')
    op.drop_table('leads')
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.drop_table('document_chunks')
    op.drop_table('knowledge_sources')
    op.drop_table('agent_runs')
    op.drop_table('whatsapp_messages')
    op.drop_table('whatsapp_conversations')
    op.drop_table('whatsapp_contacts')
    op.drop_table('whatsapp_accounts')
    op.drop_table('business_profiles')
    op.drop_table('workspace_members')
    op.drop_table('workspaces')
    op.drop_table('users')

    # Drop enums
    sa.Enum(name='audit_event_type_enum').drop(op.get_bind())
    sa.Enum(name='lead_intent_enum').drop(op.get_bind())
    sa.Enum(name='lead_status_enum').drop(op.get_bind())
    sa.Enum(name='knowledge_source_status_enum').drop(op.get_bind())
    sa.Enum(name='knowledge_source_type_enum').drop(op.get_bind())
    sa.Enum(name='agent_run_status_enum').drop(op.get_bind())
    sa.Enum(name='agent_type_enum').drop(op.get_bind())
    sa.Enum(name='modality_enum').drop(op.get_bind())
    sa.Enum(name='message_status_enum').drop(op.get_bind())
    sa.Enum(name='message_direction_enum').drop(op.get_bind())
    sa.Enum(name='message_type_enum').drop(op.get_bind())
    sa.Enum(name='conversation_status_enum').drop(op.get_bind())
    sa.Enum(name='workspace_role_enum').drop(op.get_bind())

    # We do NOT drop vector or uuid-ossp extensions automatically in downgrade, 
    # as they might be used by other schemas or applications.
