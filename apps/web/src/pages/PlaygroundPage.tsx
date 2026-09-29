import { useState, useRef, useEffect } from 'react'
import { Send, Image as ImageIcon, Mic, Bot, User, Loader2, Sparkles, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { apiClient } from '../services/api'

type Message = {
  id: string
  text: string
  sender: 'user' | 'ai'
  timestamp: Date
  metadata?: {
    intent?: string
    latency_ms?: number
    routed_agent?: string
  }
}

export default function PlaygroundPage() {
  const { workspace } = useAuthStore()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || !workspace?.id || loading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      text: input.trim(),
      sender: 'user',
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      // For now, we mock the webhook payload since this is a playground.
      // In a real implementation, this might hit a dedicated /playground/chat endpoint
      // that returns synchronous metadata, rather than an async webhook.
      const response = await apiClient.post(`/workspaces/${workspace.id}/playground/chat`, {
        message: userMessage.text,
        sender_id: 'playground_user'
      })

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.data.response_text,
        sender: 'ai',
        timestamp: new Date(),
        metadata: {
          intent: response.data.intent,
          latency_ms: response.data.latency_ms,
          routed_agent: response.data.routed_agent
        }
      }
      setMessages(prev => [...prev, aiMessage])
    } catch (err: any) {
      const errorMsg = err.response?.data?.message || 'Failed to get response'
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        text: `Error: ${errorMsg}`,
        sender: 'ai',
        timestamp: new Date()
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] max-w-6xl mx-auto gap-6 lg:flex-row">
      
      {/* Phone Simulator Container */}
      <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-900 border border-border rounded-3xl overflow-hidden shadow-2xl relative max-w-md mx-auto w-full">
        {/* Phone Header */}
        <div className="bg-whatsapp text-white p-4 flex items-center gap-3 shadow-md z-10">
          <div className="h-10 w-10 bg-white/20 rounded-full flex items-center justify-center">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <h2 className="font-bold">AI Assistant</h2>
            <p className="text-xs text-white/80 flex items-center gap-1">
              <span className="h-2 w-2 bg-green-300 rounded-full inline-block"></span>
              Online
            </p>
          </div>
        </div>

        {/* Chat Area (WhatsApp Background) */}
        <div 
          className="flex-1 overflow-y-auto p-4 space-y-4 bg-[url('https://static.whatsapp.net/rsrc.php/v3/yl/r/r2_yqN1G6Xh.png')] bg-repeat"
          style={{ backgroundColor: '#efeae2' }}
        >
          {messages.length === 0 && (
            <div className="bg-[#ffeecd] text-[#54656f] text-xs p-2 rounded-lg text-center mx-auto max-w-[80%] shadow-sm mb-4">
              <Sparkles className="h-3 w-3 inline mr-1" />
              Messages to this chat are secured with AI. Send a message to test your Assistant.
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div 
                className={`max-w-[85%] rounded-lg p-2 shadow-sm relative ${
                  msg.sender === 'user' 
                    ? 'bg-[#d9fdd3] text-[#111b21] rounded-tr-none' 
                    : 'bg-white text-[#111b21] rounded-tl-none'
                }`}
              >
                <p className="text-sm pb-3 whitespace-pre-wrap">{msg.text}</p>
                <span className="text-[10px] text-gray-500 absolute bottom-1 right-2">
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              
              {/* Metadata badge for AI responses */}
              {msg.metadata && (
                <div className="mt-1 flex items-center gap-2 text-[10px] font-mono text-muted-foreground bg-card/80 px-2 py-0.5 rounded-full border border-border backdrop-blur-sm">
                  <span>{msg.metadata.latency_ms}ms</span>
                  <span>•</span>
                  <span className="text-primary">{msg.metadata.intent}</span>
                  <span>•</span>
                  <span>{msg.metadata.routed_agent}</span>
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="flex items-start">
              <div className="bg-white rounded-lg rounded-tl-none p-3 shadow-sm flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-xs italic">AI is typing...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="bg-slate-100 p-2 flex items-center gap-2">
          <button className="p-2 text-gray-500 hover:text-gray-700 transition-colors">
            <ImageIcon className="h-6 w-6" />
          </button>
          <form onSubmit={handleSend} className="flex-1 flex">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type a message"
              className="flex-1 py-2 px-4 rounded-full border-none focus:ring-0 text-sm shadow-sm"
              disabled={loading}
            />
          </form>
          {input.trim() ? (
            <button 
              onClick={handleSend}
              disabled={loading}
              className="p-2 bg-whatsapp text-white rounded-full hover:bg-whatsapp/90 transition-colors shadow-sm disabled:opacity-50"
            >
              <Send className="h-5 w-5 ml-0.5" />
            </button>
          ) : (
            <button className="p-2 text-gray-500 hover:text-gray-700 transition-colors">
              <Mic className="h-6 w-6" />
            </button>
          )}
        </div>
      </div>

      {/* Analytics / Side Panel */}
      <div className="flex-1 flex flex-col gap-4">
        <div className="bg-card border border-border p-6 rounded-xl shadow-sm">
          <h2 className="text-lg font-bold flex items-center gap-2 mb-4">
            <Sparkles className="h-5 w-5 text-primary" />
            Playground Analytics
          </h2>
          <p className="text-sm text-muted-foreground mb-6">
            Test how your AI agent behaves in real-time. Watch the routing logic, intent detection, and response generation speed.
          </p>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-secondary/50 p-4 rounded-lg border border-border">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mb-1">Average Latency</p>
              <p className="text-2xl font-bold">
                {messages.filter(m => m.metadata?.latency_ms).length > 0 
                  ? Math.round(messages.filter(m => m.metadata?.latency_ms).reduce((acc, m) => acc + (m.metadata?.latency_ms || 0), 0) / messages.filter(m => m.metadata?.latency_ms).length)
                  : 0} ms
              </p>
            </div>
            <div className="bg-secondary/50 p-4 rounded-lg border border-border">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold mb-1">Total Messages</p>
              <p className="text-2xl font-bold">{messages.length}</p>
            </div>
          </div>

          <div className="mt-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex gap-3 text-destructive">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <div className="text-sm">
              <p className="font-bold mb-1">Mock Endpoint Notice</p>
              <p>The backend endpoint <code>/workspaces/{"{id}"}/playground/chat</code> must be implemented to return synchronous JSON for this UI to function fully.</p>
            </div>
          </div>
        </div>
      </div>
      
    </div>
  )
}
