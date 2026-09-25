import { create } from 'zustand';
import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
});

export interface Conversation {
  id: string;
  status: string;
  ai_enabled: boolean;
  contact_name: string;
  contact_phone: string;
  message_count: number;
  last_message_at: string | null;
  escalation_reason: string | null;
}

export interface Message {
  id: string;
  direction: 'INBOUND' | 'OUTBOUND';
  message_type: string;
  body: string | null;
  timestamp: string;
  status: string;
  is_voice_note: boolean;
}

interface AppState {
  conversations: Conversation[];
  activeConversation: string | null;
  messages: Message[];
  loading: boolean;
  
  fetchConversations: () => Promise<void>;
  fetchMessages: (id: string) => Promise<void>;
  sendMessage: (id: string, text: string) => Promise<void>;
}

export const useStore = create<AppState>((set, get) => ({
  conversations: [],
  activeConversation: null,
  messages: [],
  loading: false,

  fetchConversations: async () => {
    try {
      const res = await api.get<Conversation[]>('/conversations');
      set({ conversations: res.data });
    } catch (e) {
      console.error(e);
    }
  },

  fetchMessages: async (id: string) => {
    set({ loading: true, activeConversation: id });
    try {
      const res = await api.get<Message[]>(`/conversations/${id}/messages`);
      set({ messages: res.data, loading: false });
    } catch (e) {
      console.error(e);
      set({ loading: false });
    }
  },

  sendMessage: async (id: string, text: string) => {
    try {
      await api.post(`/conversations/${id}/reply`, { body: text });
      // Optimistic update
      const newMessage: Message = {
        id: Math.random().toString(),
        direction: 'OUTBOUND',
        message_type: 'TEXT',
        body: text,
        timestamp: new Date().toISOString(),
        status: 'QUEUED',
        is_voice_note: false
      };
      set({ messages: [...get().messages, newMessage] });
    } catch (e) {
      console.error(e);
    }
  }
}));
