import { useEffect, useState } from 'react'
import { MessageSquare, Search, Bot, User, Send } from 'lucide-react'
import { getConversations, type Conversation } from '../services/conversations'
import { apiClient } from '../services/api'

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedConv, setSelectedConv] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<any[]>([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [replyText, setReplyText] = useState('')

  const fetchConversations = async () => {
    try {
      const data = await getConversations()
      setConversations(data)
    } catch (error) {
      console.error('Failed to fetch conversations', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchConversations()
  }, [])

  useEffect(() => {
    if (selectedConv) {
      const fetchMessages = async () => {
        setLoadingMessages(true)
        try {
          const { data } = await apiClient.get(`/conversations/${selectedConv.id}/messages`)
          setMessages(data)
        } catch (error) {
          console.error('Failed to fetch messages', error)
        } finally {
          setLoadingMessages(false)
        }
      }
      fetchMessages()
    }
  }, [selectedConv])

  const handleSendReply = async () => {
    if (!selectedConv || !replyText.trim()) return
    try {
      await apiClient.post(`/conversations/${selectedConv.id}/reply`, { body: replyText })
      setReplyText('')
      // Refresh messages
      const { data } = await apiClient.get(`/conversations/${selectedConv.id}/messages`)
      setMessages(data)
      
      // Update local AI state
      setSelectedConv({...selectedConv, ai_enabled: false})
    } catch (error) {
      console.error('Failed to send reply', error)
    }
  }

  const toggleAI = async () => {
    if (!selectedConv) return
    try {
      const newStatus = !selectedConv.ai_enabled
      await apiClient.post(`/conversations/${selectedConv.id}/toggle-ai`, { ai_enabled: newStatus })
      setSelectedConv({...selectedConv, ai_enabled: newStatus})
      fetchConversations() // update list too
    } catch (error) {
      console.error('Failed to toggle AI', error)
    }
  }

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col md:flex-row border border-border rounded-xl bg-card overflow-hidden animate-in fade-in duration-500 shadow-sm">
      {/* Sidebar List */}
      <div className="w-full md:w-1/3 border-r border-border flex flex-col h-full bg-background/30">
        <div className="p-4 border-b border-border">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-primary" /> Conversations
          </h2>
          <div className="mt-4 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input 
              type="text" 
              placeholder="Search contacts..." 
              className="w-full pl-9 pr-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loading ? (
            <div className="p-4 text-center text-sm text-muted-foreground animate-pulse">Loading conversations...</div>
          ) : conversations.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">No conversations yet.</div>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => setSelectedConv(conv)}
                className={`w-full text-left p-3 rounded-lg transition-colors flex flex-col gap-1 ${
                  selectedConv?.id === conv.id ? 'bg-primary/10 border border-primary/20' : 'hover:bg-muted/50 border border-transparent'
                }`}
              >
                <div className="flex justify-between items-center w-full">
                  <span className="font-semibold text-sm">{conv.contact_name}</span>
                  <span className="text-xs text-muted-foreground">
                    {conv.last_message_at ? new Date(conv.last_message_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}
                  </span>
                </div>
                <div className="flex justify-between items-center w-full mt-1">
                  <span className="text-xs text-muted-foreground truncate w-2/3">{conv.contact_phone}</span>
                  <div className="flex items-center gap-2">
                    {conv.status === 'escalated' && (
                      <span className="h-2 w-2 rounded-full bg-destructive"></span>
                    )}
                    <Bot className={`h-3 w-3 ${conv.ai_enabled ? 'text-success' : 'text-muted-foreground'}`} />
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col h-full bg-background/10">
        {selectedConv ? (
          <>
            <div className="p-4 border-b border-border flex justify-between items-center bg-card">
              <div>
                <h3 className="font-bold text-lg">{selectedConv.contact_name}</h3>
                <p className="text-sm text-muted-foreground">{selectedConv.contact_phone}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${selectedConv.status === 'escalated' ? 'bg-destructive/10 text-destructive' : 'bg-secondary text-secondary-foreground'}`}>
                  {selectedConv.status.toUpperCase()}
                </span>
                <button 
                  onClick={toggleAI}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    selectedConv.ai_enabled 
                      ? 'bg-success/10 text-success hover:bg-success/20' 
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  }`}
                >
                  <Bot className="h-4 w-4" />
                  {selectedConv.ai_enabled ? 'AI Active' : 'AI Paused'}
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {loadingMessages ? (
                <div className="text-center text-sm text-muted-foreground animate-pulse">Loading messages...</div>
              ) : messages.length === 0 ? (
                <div className="text-center text-sm text-muted-foreground">No messages found for this conversation.</div>
              ) : (
                messages.map((msg) => {
                  const isOutbound = msg.direction === 'outbound'
                  return (
                    <div key={msg.id} className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[70%] p-3 rounded-2xl ${
                        isOutbound 
                          ? 'bg-primary text-primary-foreground rounded-tr-sm' 
                          : 'bg-secondary text-secondary-foreground rounded-tl-sm'
                      }`}>
                        <p className="text-sm">{msg.body}</p>
                        <div className={`text-[10px] mt-1 ${isOutbound ? 'text-primary-foreground/70' : 'text-muted-foreground'} flex justify-end`}>
                          {new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            <div className="p-4 border-t border-border bg-card">
              {selectedConv.ai_enabled && (
                <div className="mb-2 text-xs text-warning bg-warning/10 p-2 rounded flex justify-between items-center">
                  <span>AI is currently active. Sending a message will pause AI.</span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendReply()}
                  placeholder="Type a message..."
                  className="flex-1 px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
                <button 
                  onClick={handleSendReply}
                  disabled={!replyText.trim()}
                  className="p-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <Send className="h-5 w-5" />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground">
            <MessageSquare className="h-12 w-12 mb-4 opacity-20" />
            <p>Select a conversation to start messaging</p>
          </div>
        )}
      </div>
    </div>
  )
}
