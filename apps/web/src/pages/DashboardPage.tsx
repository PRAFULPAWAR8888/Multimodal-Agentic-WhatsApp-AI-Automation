import { MessageSquare, Bot, Users, Timer } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getConversations, type Conversation } from '../services/conversations'
export default function DashboardPage() {
  const stats = [
    { label: 'Total Conversations', value: '1,248', trend: '+12%', icon: MessageSquare, color: 'text-blue-500', border: 'border-blue-500/20' },
    { label: 'AI Resolved', value: '892', trend: '+24%', icon: Bot, color: 'text-whatsapp', border: 'border-whatsapp/20' },
    { label: 'Leads Captured', value: '156', trend: '+8%', icon: Users, color: 'text-purple-500', border: 'border-purple-500/20' },
    { label: 'Response Time', value: '1.2s', trend: '-5%', icon: Timer, color: 'text-orange-500', border: 'border-orange-500/20' },
  ]

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
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
    fetchConversations()
  }, [])

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-2">Welcome back. Here's what's happening with your AI assistant.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, i) => {
          const Icon = stat.icon
          return (
            <div key={i} className={`bg-card p-6 rounded-xl border ${stat.border} shadow-sm`}>
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
                  <h3 className="text-2xl font-bold mt-2">{stat.value}</h3>
                </div>
                <div className={`p-2 rounded-lg bg-background/50 ${stat.color}`}>
                  <Icon className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-4 flex items-center text-sm">
                <span className="text-success font-medium">{stat.trend}</span>
                <span className="text-muted-foreground ml-2">from last month</span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-card rounded-xl border border-border p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-semibold">Recent Conversations</h3>
            {loading ? (
              <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded-full animate-pulse">LOADING...</span>
            ) : (
              <span className="text-xs bg-success/10 text-success px-2 py-1 rounded-full">LIVE DATA</span>
            )}
          </div>
          <div className="space-y-4">
            {conversations.length === 0 && !loading && (
              <div className="text-center text-muted-foreground p-4">No recent conversations found.</div>
            )}
            {conversations.slice(0, 5).map((conv) => (
              <div key={conv.id} className="flex items-center justify-between p-4 rounded-lg bg-background/50 border border-border/50 hover:border-primary/50 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="h-10 w-10 rounded-full bg-secondary flex items-center justify-center">
                    <Users className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="font-medium">{conv.contact_name} ({conv.contact_phone})</p>
                    <p className="text-sm text-muted-foreground">Total messages: {conv.message_count}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded-md ${
                    conv.status === 'active' ? 'bg-success/10 text-success' : 
                    conv.status === 'escalated' ? 'bg-destructive/10 text-destructive' : 
                    'bg-muted text-muted-foreground'
                  }`}>
                    {conv.status.charAt(0).toUpperCase() + conv.status.slice(1)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {conv.last_message_at ? new Date(conv.last_message_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-card rounded-xl border border-border p-6">
          <h3 className="text-lg font-semibold mb-6">System Status</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm">WhatsApp API</span>
              <span className="text-xs bg-success/10 text-success px-2 py-1 rounded-md">Connected</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">OpenAI (LLM)</span>
              <span className="text-xs bg-success/10 text-success px-2 py-1 rounded-md">Active</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Faster Whisper</span>
              <span className="text-xs bg-success/10 text-success px-2 py-1 rounded-md">Ready</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Piper TTS</span>
              <span className="text-xs bg-success/10 text-success px-2 py-1 rounded-md">Ready</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
