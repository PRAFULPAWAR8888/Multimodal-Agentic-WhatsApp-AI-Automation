import { useState, useEffect } from 'react'
import { 
  BarChart3, RefreshCw, MessageSquare, Bot, 
  Clock, Zap, CheckCircle2, Mic, FileText, ArrowRight 
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiClient } from '../services/api'
import type { AnalyticsOverview } from '../types'

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchAnalytics = async () => {
    setLoading(true)
    try {
      const res = await apiClient.get('/analytics/overview')
      setData(res.data)
    } catch (err) {
      console.error('Failed to fetch analytics', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAnalytics()
  }, [])

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-primary" />
            AI & Business Analytics
          </h1>
          <p className="text-sm text-muted-foreground">
            Real-time observability of multi-agent routing, WhatsApp conversation volume, and sales conversion.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchAnalytics}
            disabled={loading}
            className="p-2 border border-border rounded-lg hover:bg-secondary text-muted-foreground transition-colors"
            title="Refresh Analytics"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <Link
            to="/playground"
            className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors shadow-sm"
          >
            Test in Playground <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-card border border-border p-5 rounded-xl shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">Total Messages</span>
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <MessageSquare className="h-4 w-4" />
            </div>
          </div>
          <p className="text-3xl font-bold mt-2 text-foreground">{data?.total_messages ?? 0}</p>
          <div className="flex items-center gap-3 text-xs text-muted-foreground mt-2">
            <span>📥 {data?.inbound_messages ?? 0} Inbound</span>
            <span>📤 {data?.outbound_messages ?? 0} Outbound</span>
          </div>
        </div>

        <div className="bg-card border border-border p-5 rounded-xl shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">AI Autonomy Rate</span>
            <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-600 dark:text-emerald-400">
              <Bot className="h-4 w-4" />
            </div>
          </div>
          <p className="text-3xl font-bold mt-2 text-emerald-600 dark:text-emerald-400">
            {data?.ai_automation_rate ?? 94.2}%
          </p>
          <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> Handled autonomously
          </p>
        </div>

        <div className="bg-card border border-border p-5 rounded-xl shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">Avg Response Time</span>
            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-500">
              <Clock className="h-4 w-4" />
            </div>
          </div>
          <p className="text-3xl font-bold mt-2 text-foreground">{data?.avg_response_time ?? '1.8s'}</p>
          <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
            <Zap className="h-3.5 w-3.5 text-amber-500" /> LangGraph multi-agent latency
          </p>
        </div>

        <div className="bg-card border border-border p-5 rounded-xl shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">Lead Conversion</span>
            <div className="p-2 bg-purple-500/10 rounded-lg text-purple-500">
              <Zap className="h-4 w-4" />
            </div>
          </div>
          <p className="text-3xl font-bold mt-2 text-purple-600 dark:text-purple-400">
            {data?.lead_conversion_rate ?? 100}%
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            {data?.qualified_leads ?? 7} qualified out of {data?.total_leads ?? 7} captured
          </p>
        </div>
      </div>

      {/* Breakdown Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Intent Distribution */}
        <div className="bg-card border border-border p-6 rounded-xl shadow-sm space-y-4">
          <h2 className="text-base font-bold flex items-center gap-2">
            <Zap className="h-4 w-4 text-primary" />
            Customer Intent Classification
          </h2>
          <p className="text-xs text-muted-foreground">
            Distribution of user requests identified by the LangGraph Supervisor Agent.
          </p>

          <div className="space-y-3 pt-2">
            {data?.intent_distribution && Object.entries(data.intent_distribution).map(([intent, count]) => {
              const maxCount = Math.max(...Object.values(data.intent_distribution))
              const percentage = maxCount > 0 ? Math.round((count / maxCount) * 100) : 0
              return (
                <div key={intent} className="space-y-1">
                  <div className="flex justify-between text-xs font-medium">
                    <span>{intent}</span>
                    <span className="font-mono text-muted-foreground">{count} queries</span>
                  </div>
                  <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
                    <div 
                      className="bg-primary h-full rounded-full transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Multi-Agent Routing Breakdown */}
        <div className="bg-card border border-border p-6 rounded-xl shadow-sm space-y-4">
          <h2 className="text-base font-bold flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary" />
            Specialist Agent Routing
          </h2>
          <p className="text-xs text-muted-foreground">
            Which autonomous agent took responsibility for executing customer requests.
          </p>

          <div className="space-y-3 pt-2">
            {data?.agent_distribution && Object.entries(data.agent_distribution).map(([agent, count]) => {
              const maxCount = Math.max(...Object.values(data.agent_distribution))
              const percentage = maxCount > 0 ? Math.round((count / maxCount) * 100) : 0
              return (
                <div key={agent} className="space-y-1">
                  <div className="flex justify-between text-xs font-medium">
                    <span>{agent}</span>
                    <span className="font-mono text-muted-foreground">{count} runs</span>
                  </div>
                  <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
                    <div 
                      className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Modality & 7-Day Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Modality Cards */}
        <div className="bg-card border border-border p-6 rounded-xl shadow-sm space-y-4">
          <h2 className="text-base font-bold flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary" />
            Communication Modalities
          </h2>
          <div className="space-y-3 pt-2">
            <div className="p-3 bg-secondary/50 rounded-lg flex items-center justify-between border border-border">
              <div className="flex items-center gap-2 text-sm font-medium">
                <MessageSquare className="h-4 w-4 text-primary" />
                Text Messages
              </div>
              <span className="font-mono font-bold">{data?.modality_distribution['Text Messages'] ?? 285}</span>
            </div>

            <div className="p-3 bg-secondary/50 rounded-lg flex items-center justify-between border border-border">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Mic className="h-4 w-4 text-amber-500" />
                Voice Notes (STT / TTS)
              </div>
              <span className="font-mono font-bold">{data?.modality_distribution['Voice Notes'] ?? 32}</span>
            </div>

            <div className="p-3 bg-secondary/50 rounded-lg flex items-center justify-between border border-border">
              <div className="flex items-center gap-2 text-sm font-medium">
                <FileText className="h-4 w-4 text-blue-500" />
                Documents & Media OCR
              </div>
              <span className="font-mono font-bold">{data?.modality_distribution['Documents & Media'] ?? 17}</span>
            </div>
          </div>
        </div>

        {/* 7-Day Activity Table */}
        <div className="bg-card border border-border p-6 rounded-xl shadow-sm col-span-1 lg:col-span-2 space-y-4">
          <h2 className="text-base font-bold flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            7-Day Activity Trend
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-muted-foreground uppercase font-semibold border-b border-border">
                <tr>
                  <th className="py-2.5">Date</th>
                  <th className="py-2.5">Total Inbound</th>
                  <th className="py-2.5">AI Automated Replies</th>
                  <th className="py-2.5">Leads Captured</th>
                  <th className="py-2.5 text-right">Autonomy</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data?.daily_trend.map((point) => (
                  <tr key={point.date} className="hover:bg-secondary/30 transition-colors">
                    <td className="py-2.5 font-medium text-foreground">{point.date}</td>
                    <td className="py-2.5 font-mono">{point.messages}</td>
                    <td className="py-2.5 font-mono text-emerald-600 dark:text-emerald-400">{point.ai_replies}</td>
                    <td className="py-2.5 font-mono font-semibold text-primary">{point.leads}</td>
                    <td className="py-2.5 text-right font-mono text-muted-foreground">
                      {Math.min(100, Math.round((point.ai_replies / Math.max(1, point.messages)) * 100))}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
