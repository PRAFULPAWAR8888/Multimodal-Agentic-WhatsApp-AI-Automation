export interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
}

export interface Workspace {
  id: string
  name: string
  slug: string
  plan: string
}

export interface WorkspaceMember {
  id: string
  workspace_id: string
  user_id: string
  role: 'owner' | 'admin' | 'member'
}

export enum ConversationStatus {
  ACTIVE = 'active',
  PENDING = 'pending',
  RESOLVED = 'resolved',
  ESCALATED = 'escalated'
}

export enum MessageType {
  TEXT = 'text',
  IMAGE = 'image',
  DOCUMENT = 'document',
  AUDIO = 'audio',
  VIDEO = 'video',
  LOCATION = 'location',
  CONTACT = 'contact',
  INTERACTIVE = 'interactive',
  TEMPLATE = 'template',
  SYSTEM = 'system'
}

export enum MessageDirection {
  INBOUND = 'inbound',
  OUTBOUND = 'outbound'
}

export interface WhatsAppConversation {
  id: string
  workspace_id: string
  contact_number: string
  contact_name?: string
  status: ConversationStatus
  last_message_at: string
  created_at: string
}

export interface WhatsAppMessage {
  id: string
  conversation_id: string
  message_id: string
  direction: MessageDirection
  type: MessageType
  content: any
  status: string
  created_at: string
}

export interface Lead {
  id: string
  workspace_id: string
  conversation_id: string
  name?: string
  phone_number: string
  status: string
  extracted_data: Record<string, any>
  created_at: string
}

export interface AgentRun {
  id: string
  workspace_id: string
  conversation_id: string
  status: string
  input_data: Record<string, any>
  output_data?: Record<string, any>
  created_at: string
}

export interface ApiResponse<T> {
  data: T
}

export interface CrmLead {
  id: string
  workspace_id: string
  name?: string
  phone?: string
  email?: string
  company?: string
  requirement?: string
  product_interest?: string
  budget?: string
  timeline?: string
  intent?: string
  lead_score?: number
  status: string
  crm_contact_id?: string
  crm_deal_id?: string
  crm_synced_at?: string
  qualified_at?: string
  notes?: string
  created_at: string
  updated_at: string
}

export interface LeadStats {
  total_leads: number
  qualified_leads: number
  won_leads: number
  new_leads: number
  crm_synced_leads: number
  avg_lead_score: number
  status_breakdown: Record<string, number>
  intent_breakdown: Record<string, number>
}

export interface AnalyticsOverview {
  total_messages: number
  inbound_messages: number
  outbound_messages: number
  total_conversations: number
  active_conversations: number
  ai_automation_rate: number
  avg_response_time: string
  total_leads: number
  qualified_leads: number
  won_leads: number
  lead_conversion_rate: number
  intent_distribution: Record<string, number>
  agent_distribution: Record<string, number>
  modality_distribution: Record<string, number>
  daily_trend: Array<{
    date: string
    messages: number
    ai_replies: number
    leads: number
  }>
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}
