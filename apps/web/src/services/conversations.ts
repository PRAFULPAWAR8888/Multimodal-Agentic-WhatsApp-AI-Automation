import { apiClient } from './api'

export interface Conversation {
  id: string
  status: string
  ai_enabled: boolean
  contact_name: string
  contact_phone: string
  message_count: number
  last_message_at: string | null
  escalation_reason: string | null
}

export const getConversations = async (): Promise<Conversation[]> => {
  const { data } = await apiClient.get('/conversations')
  return data
}
