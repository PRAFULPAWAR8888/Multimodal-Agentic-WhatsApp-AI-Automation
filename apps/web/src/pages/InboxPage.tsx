import { useEffect, useState, useRef } from 'react'
import { 
  Inbox, Search, Bot, User as UserIcon, Send, 
  CheckCheck, AlertCircle, Sparkles, RefreshCw
} from 'lucide-react'
import { apiClient } from '../services/api'
import type { Conversation } from '../services/conversations'

export default function InboxPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedConv, setSelectedConv] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<any[]>([])
  const [filter, setFilter] = useState<'all' | 'ai' | 'escalated'>('all')
  const [search, setSearch] = useState('')
  const [replyText, setReplyText] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const fetchConversations = async () => {
    try {
      const { data } = await apiClient.get('/conversations')
      setConversations(data)
      if (data.length > 0 && !selectedConv) {
        setSelectedConv(data[0])
      }
    } catch (err) {
      console.error('Failed to load conversations', err)
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
        } catch (err) {
          console.error('Failed to load messages', err)
        } finally {
          setLoadingMessages(false)
        }
      }
      fetchMessages()
    }
  }, [selectedConv?.id])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendReply = async (textToSend?: string) => {
    const text = textToSend || replyText
    if (!selectedConv || !text.trim() || sending) return
    setSending(true)
    try {
      await apiClient.post(`/conversations/${selectedConv.id}/reply`, { body: text })
      setReplyText('')
      // Refresh messages
      const { data } = await apiClient.get(`/conversations/${selectedConv.id}/messages`)
      setMessages(data)
      setSelectedConv(prev => prev ? { ...prev, ai_enabled: false } : null)
    } catch (err) {
      console.error('Failed to send reply', err)
      alert('Failed to send reply to WhatsApp.')
    } finally {
      setSending(false)
    }
  }

  const toggleAI = async () => {
    if (!selectedConv) return
    try {
      const newStatus = !selectedConv.ai_enabled
      await apiClient.post(`/conversations/${selectedConv.id}/toggle-ai`, { ai_enabled: newStatus })
      setSelectedConv({ ...selectedConv, ai_enabled: newStatus })
      setConversations(prev => prev.map(c => c.id === selectedConv.id ? { ...c, ai_enabled: newStatus } : c))
    } catch (err) {
      console.error('Failed to toggle AI', err)
    }
  }

  const filteredConversations = conversations.filter(conv => {
    if (filter === 'ai' && !conv.ai_enabled) return false
    if (filter === 'escalated' && conv.ai_enabled) return false
    const term = search.toLowerCase()
    return !term || 
      (conv.contact_name?.toLowerCase().includes(term) ?? false) ||
      (conv.contact_phone?.toLowerCase().includes(term) ?? false)
  })

  return (
    <div className="h-[calc(100vh-6.5rem)] flex flex-col md:flex-row border border-border rounded-2xl bg-card overflow-hidden shadow-sm animate-in fade-in duration-300">
      {/* Sidebar List */}
      <div className="w-full md:w-80 lg:w-96 border-r border-border flex flex-col h-full bg-background/50">
        <div className="p-4 border-b border-border space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Inbox className="h-5 w-5 text-primary" /> WhatsApp Live Inbox
            </h2>
            <button
              onClick={fetchConversations}
              className="p-1 text-muted-foreground hover:text-foreground rounded"
              title="Refresh"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search chat or phone..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-background border border-border rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1">
            {[
              { id: 'all', label: 'All' },
              { id: 'ai', label: '🤖 AI Active' },
              { id: 'escalated', label: '👤 Needs Human' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setFilter(tab.id as any)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  filter === tab.id 
                    ? 'bg-primary text-primary-foreground' 
                    : 'text-muted-foreground hover:bg-secondary'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto divide-y divide-border/50">
          {loading ? (
            <div className="p-6 text-center text-xs text-muted-foreground animate-pulse">
              Loading WhatsApp conversations...
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="p-6 text-center text-xs text-muted-foreground">
              No conversations found.
            </div>
          ) : (
            filteredConversations.map(conv => {
              const isSelected = selectedConv?.id === conv.id
              return (
                <button
                  key={conv.id}
                  onClick={() => setSelectedConv(conv)}
                  className={`w-full text-left p-3.5 transition-colors flex items-start gap-3 hover:bg-secondary/40 ${
                    isSelected ? 'bg-primary/10 border-l-4 border-l-primary' : ''
                  }`}
                >
                  <div className="h-10 w-10 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold text-sm shrink-0">
                    {conv.contact_name ? conv.contact_name[0].toUpperCase() : 'C'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-foreground truncate">
                        {conv.contact_name || conv.contact_phone}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {conv.last_message_at ? new Date(conv.last_message_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                    </div>
                    <p className="text-[11px] text-muted-foreground truncate mt-0.5">
                      {conv.contact_phone}
                    </p>
                    <div className="flex items-center gap-1.5 mt-1.5">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        conv.ai_enabled 
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' 
                          : 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                      }`}>
                        {conv.ai_enabled ? (
                          <><Bot className="h-2.5 w-2.5" /> AI Responding</>
                        ) : (
                          <><UserIcon className="h-2.5 w-2.5" /> Human Takeover</>
                        )}
                      </span>
                    </div>
                  </div>
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* Main Chat Pane */}
      <div className="flex-1 flex flex-col h-full bg-background">
        {selectedConv ? (
          <>
            {/* Chat Top Bar */}
            <div className="p-3.5 border-b border-border flex items-center justify-between bg-card z-10">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-full bg-whatsapp/20 text-whatsapp flex items-center justify-center font-bold text-sm">
                  {selectedConv.contact_name ? selectedConv.contact_name[0].toUpperCase() : 'C'}
                </div>
                <div>
                  <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                    {selectedConv.contact_name || selectedConv.contact_phone}
                    <span className="text-xs font-normal text-muted-foreground">
                      ({selectedConv.contact_phone})
                    </span>
                  </h3>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block"></span>
                    <span className="text-[11px] text-muted-foreground">WhatsApp Direct Session</span>
                  </div>
                </div>
              </div>

              {/* Takeover Control */}
              <div className="flex items-center gap-2">
                <button
                  onClick={toggleAI}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                    selectedConv.ai_enabled
                      ? 'bg-amber-500/10 text-amber-600 border-amber-500/30 hover:bg-amber-500/20'
                      : 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30 hover:bg-emerald-500/20'
                  }`}
                >
                  {selectedConv.ai_enabled ? (
                    <><AlertCircle className="h-3.5 w-3.5" /> Take Over (Pause AI)</>
                  ) : (
                    <><Bot className="h-3.5 w-3.5" /> Resume AI Automation</>
                  )}
                </button>
              </div>
            </div>

            {/* Chat Scroll Thread */}
            <div 
              className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#efeae2] dark:bg-slate-950/60"
            >
              {loadingMessages ? (
                <div className="p-8 text-center text-xs text-muted-foreground animate-pulse">
                  Loading message history...
                </div>
              ) : messages.length === 0 ? (
                <div className="bg-white/80 dark:bg-slate-900/80 text-muted-foreground text-xs p-3 rounded-xl text-center mx-auto max-w-sm shadow-sm">
                  No messages recorded in this conversation yet.
                </div>
              ) : (
                messages.map((msg, i) => {
                  const isInbound = msg.direction === 'inbound' || msg.direction === 'INBOUND'
                  return (
                    <div
                      key={msg.id || i}
                      className={`flex flex-col ${isInbound ? 'items-start' : 'items-end'}`}
                    >
                      <div
                        className={`max-w-[75%] rounded-xl px-3.5 py-2 shadow-sm text-sm relative ${
                          isInbound
                            ? 'bg-white text-slate-900 rounded-tl-none dark:bg-slate-900 dark:text-slate-100'
                            : 'bg-[#d9fdd3] text-slate-900 rounded-tr-none dark:bg-emerald-950 dark:text-emerald-100'
                        }`}
                      >
                        <p className="whitespace-pre-wrap leading-relaxed pb-2.5 text-xs sm:text-sm">
                          {msg.body}
                        </p>
                        <div className="flex items-center justify-end gap-1 text-[10px] text-muted-foreground mt-0.5">
                          <span>
                            {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                          </span>
                          {!isInbound && <CheckCheck className="h-3 w-3 text-blue-500" />}
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Smart Response Chips */}
            <div className="px-3 py-1.5 bg-card border-t border-border flex items-center gap-1.5 overflow-x-auto text-[11px]">
              <span className="text-muted-foreground font-medium flex items-center gap-1 shrink-0">
                <Sparkles className="h-3 w-3 text-primary" /> Suggestions:
              </span>
              {[
                'Hello! How can we assist your business today?',
                'We would love to schedule a discovery call for you.',
                'Our portfolio covers full stack web, mobile, and algorithmic trading.'
              ].map((chip, idx) => (
                <button
                  key={idx}
                  onClick={() => setReplyText(chip)}
                  className="px-2 py-0.5 bg-secondary hover:bg-primary/20 text-muted-foreground hover:text-foreground rounded-full truncate shrink-0 transition-colors"
                >
                  {chip}
                </button>
              ))}
            </div>

            {/* Composer */}
            <div className="p-3 bg-card border-t border-border flex items-center gap-2">
              <input
                type="text"
                placeholder={selectedConv.ai_enabled ? "AI is handling this chat. Type to reply and take over manually..." : "Type your message to customer..."}
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendReply()
                  }
                }}
                className="flex-1 px-4 py-2 bg-background border border-border rounded-xl text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
              <button
                onClick={() => handleSendReply()}
                disabled={!replyText.trim() || sending}
                className="p-2.5 bg-whatsapp text-white rounded-xl hover:bg-whatsapp/90 transition-colors disabled:opacity-50 shadow-sm"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
            <Inbox className="h-12 w-12 stroke-1 mb-2 text-muted-foreground/50" />
            <p className="font-semibold text-sm">Select a conversation from the sidebar</p>
            <p className="text-xs">Or wait for incoming customer messages over WhatsApp.</p>
          </div>
        )}
      </div>
    </div>
  )
}
