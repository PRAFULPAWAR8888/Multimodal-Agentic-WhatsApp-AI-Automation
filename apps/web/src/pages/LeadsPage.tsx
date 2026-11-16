import { useState, useEffect } from 'react'
import { 
  Users, Search, Plus, RefreshCw, ExternalLink, 
  CheckCircle2, Clock, Trash2, ArrowUpRight
} from 'lucide-react'
import { apiClient } from '../services/api'
import type { CrmLead, LeadStats } from '../types'

export default function LeadsPage() {
  const [leads, setLeads] = useState<CrmLead[]>([])
  const [stats, setStats] = useState<LeadStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [syncingId, setSyncingId] = useState<string | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  
  // New Lead Form State
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    company: '',
    requirement: '',
    budget: '',
    intent: 'PURCHASE',
    status: 'NEW',
    lead_score: 75
  })
  const [submitting, setSubmitting] = useState(false)

  const fetchLeadsAndStats = async () => {
    setLoading(true)
    try {
      const [leadsRes, statsRes] = await Promise.all([
        apiClient.get('/leads'),
        apiClient.get('/leads/stats')
      ])
      setLeads(leadsRes.data)
      setStats(statsRes.data)
    } catch (err) {
      console.error('Failed to load leads', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLeadsAndStats()
  }, [])

  const handleSyncToCrm = async (leadId: string) => {
    setSyncingId(leadId)
    try {
      const res = await apiClient.post(`/leads/${leadId}/sync-crm`)
      if (res.data.status === 'success') {
        // Update lead locally
        setLeads(prev => prev.map(l => l.id === leadId ? {
          ...l, 
          crm_contact_id: res.data.crm_lead_id,
          crm_synced_at: res.data.synced_at
        } : l))
        // Refresh stats
        const statsRes = await apiClient.get('/leads/stats')
        setStats(statsRes.data)
      } else {
        alert(res.data.message || 'CRM Sync failed')
      }
    } catch (err) {
      console.error('Sync failed', err)
      alert('Failed to sync lead to Frappe CRM')
    } finally {
      setSyncingId(null)
    }
  }

  const handleStatusChange = async (leadId: string, newStatus: string) => {
    try {
      await apiClient.patch(`/leads/${leadId}`, { status: newStatus })
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status: newStatus } : l))
      const statsRes = await apiClient.get('/leads/stats')
      setStats(statsRes.data)
    } catch (err) {
      console.error('Failed to update status', err)
    }
  }

  const handleDelete = async (leadId: string) => {
    if (!confirm('Are you sure you want to delete this lead?')) return
    try {
      await apiClient.delete(`/leads/${leadId}`)
      setLeads(prev => prev.filter(l => l.id !== leadId))
      const statsRes = await apiClient.get('/leads/stats')
      setStats(statsRes.data)
    } catch (err) {
      console.error('Failed to delete lead', err)
    }
  }

  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      const res = await apiClient.post('/leads', formData)
      setLeads(prev => [res.data, ...prev])
      setIsModalOpen(false)
      setFormData({
        name: '',
        phone: '',
        email: '',
        company: '',
        requirement: '',
        budget: '',
        intent: 'PURCHASE',
        status: 'NEW',
        lead_score: 75
      })
      const statsRes = await apiClient.get('/leads/stats')
      setStats(statsRes.data)
    } catch (err) {
      console.error('Failed to create lead', err)
      alert('Failed to create lead. Please verify the form fields.')
    } finally {
      setSubmitting(false)
    }
  }

  const filteredLeads = leads.filter(lead => {
    const matchesStatus = statusFilter === 'ALL' || lead.status === statusFilter
    const term = search.toLowerCase()
    const matchesSearch = !term || 
      (lead.name?.toLowerCase().includes(term) ?? false) ||
      (lead.email?.toLowerCase().includes(term) ?? false) ||
      (lead.phone?.toLowerCase().includes(term) ?? false) ||
      (lead.company?.toLowerCase().includes(term) ?? false) ||
      (lead.requirement?.toLowerCase().includes(term) ?? false)
    return matchesStatus && matchesSearch
  })

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="h-6 w-6 text-primary" />
            CRM Leads & Pipeline
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage AI-captured prospects, qualification scores, and bidirectional Frappe Cloud CRM synchronization.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchLeadsAndStats}
            disabled={loading}
            className="p-2 border border-border rounded-lg hover:bg-secondary text-muted-foreground transition-colors"
            title="Refresh Leads"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg text-sm hover:bg-primary/90 transition-colors shadow-sm"
          >
            <Plus className="h-4 w-4" />
            New Lead
          </button>
        </div>
      </div>

      {/* Pipeline Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-card border border-border p-4 rounded-xl shadow-sm">
          <span className="text-xs font-semibold text-muted-foreground uppercase">Total Leads</span>
          <p className="text-2xl font-bold mt-1 text-foreground">{stats?.total_leads ?? leads.length}</p>
          <span className="text-xs text-primary flex items-center gap-1 mt-1">
            <ArrowUpRight className="h-3 w-3" /> WhatsApp AI Captured
          </span>
        </div>

        <div className="bg-card border border-border p-4 rounded-xl shadow-sm">
          <span className="text-xs font-semibold text-muted-foreground uppercase">Qualified</span>
          <p className="text-2xl font-bold mt-1 text-green-600 dark:text-green-400">
            {stats?.qualified_leads ?? leads.filter(l => l.status === 'QUALIFIED').length}
          </p>
          <span className="text-xs text-muted-foreground mt-1 block">High buying intent</span>
        </div>

        <div className="bg-card border border-border p-4 rounded-xl shadow-sm">
          <span className="text-xs font-semibold text-muted-foreground uppercase">Won Deals</span>
          <p className="text-2xl font-bold mt-1 text-primary">
            {stats?.won_leads ?? leads.filter(l => l.status === 'WON').length}
          </p>
          <span className="text-xs text-muted-foreground mt-1 block">Closed customers</span>
        </div>

        <div className="bg-card border border-border p-4 rounded-xl shadow-sm">
          <span className="text-xs font-semibold text-muted-foreground uppercase">Avg Score</span>
          <p className="text-2xl font-bold mt-1 text-foreground">
            {stats?.avg_lead_score ?? 75}/100
          </p>
          <span className="text-xs text-muted-foreground mt-1 block">AI qualification</span>
        </div>

        <div className="bg-card border border-border p-4 rounded-xl shadow-sm col-span-2 lg:col-span-1">
          <span className="text-xs font-semibold text-muted-foreground uppercase">Frappe CRM Synced</span>
          <p className="text-2xl font-bold mt-1 text-emerald-600 dark:text-emerald-400">
            {stats?.crm_synced_leads ?? leads.filter(l => Boolean(l.crm_contact_id)).length}
          </p>
          <span className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1 mt-1">
            <CheckCircle2 className="h-3 w-3" /> Live Frappe Cloud
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-card border border-border p-3 rounded-xl">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search leads by name, email, phone, company..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>

        <div className="flex items-center gap-1 overflow-x-auto w-full sm:w-auto">
          {['ALL', 'QUALIFIED', 'NEW', 'WON', 'LOST'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                statusFilter === status
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-secondary'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Leads Table */}
      <div className="border border-border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-secondary/50 text-muted-foreground text-xs uppercase font-semibold border-b border-border">
              <tr>
                <th className="py-3 px-4">Contact</th>
                <th className="py-3 px-4">Company & Requirement</th>
                <th className="py-3 px-4">Intent & Score</th>
                <th className="py-3 px-4">Pipeline Status</th>
                <th className="py-3 px-4">Frappe CRM Sync</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-muted-foreground animate-pulse">
                    Loading CRM leads...
                  </td>
                </tr>
              ) : filteredLeads.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-muted-foreground">
                    No leads found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredLeads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-secondary/20 transition-colors">
                    {/* Contact */}
                    <td className="py-3 px-4">
                      <div className="font-semibold text-foreground">{lead.name || 'Anonymous Lead'}</div>
                      <div className="text-xs text-muted-foreground">{lead.phone || 'No phone'}</div>
                      <div className="text-xs text-muted-foreground">{lead.email || 'No email'}</div>
                    </td>

                    {/* Company & Requirement */}
                    <td className="py-3 px-4 max-w-xs">
                      <div className="font-medium text-xs text-primary truncate">
                        {lead.company || 'Direct Client'}
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5" title={lead.requirement || ''}>
                        {lead.requirement || 'No specific requirement recorded'}
                      </p>
                      {lead.budget && (
                        <span className="inline-block mt-1 text-[10px] bg-secondary px-1.5 py-0.5 rounded text-foreground font-mono">
                          💰 {lead.budget}
                        </span>
                      )}
                    </td>

                    {/* Intent & Score */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5">
                        <span className="px-2 py-0.5 bg-primary/10 text-primary rounded-full text-xs font-medium">
                          {lead.intent || 'INQUIRY'}
                        </span>
                      </div>
                      <div className="mt-2 flex items-center gap-2">
                        <div className="w-16 bg-secondary h-1.5 rounded-full overflow-hidden">
                          <div 
                            className={`h-full ${
                              (lead.lead_score || 0) >= 80 ? 'bg-green-500' :
                              (lead.lead_score || 0) >= 60 ? 'bg-amber-500' : 'bg-gray-400'
                            }`}
                            style={{ width: `${Math.min(100, lead.lead_score || 50)}%` }}
                          />
                        </div>
                        <span className="text-[11px] font-mono text-muted-foreground">
                          {lead.lead_score || 50}%
                        </span>
                      </div>
                    </td>

                    {/* Pipeline Status */}
                    <td className="py-3 px-4">
                      <select
                        value={lead.status}
                        onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                        className="bg-background border border-border rounded px-2 py-1 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary"
                      >
                        <option value="NEW">NEW</option>
                        <option value="CONTACTED">CONTACTED</option>
                        <option value="QUALIFIED">QUALIFIED</option>
                        <option value="PROPOSAL_SENT">PROPOSAL SENT</option>
                        <option value="NEGOTIATION">NEGOTIATION</option>
                        <option value="WON">WON</option>
                        <option value="LOST">LOST</option>
                        <option value="DISQUALIFIED">DISQUALIFIED</option>
                      </select>
                      <div className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(lead.created_at).toLocaleDateString()}
                      </div>
                    </td>

                    {/* Frappe CRM Sync */}
                    <td className="py-3 px-4">
                      {lead.crm_contact_id ? (
                        <div className="flex flex-col gap-0.5">
                          <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            {lead.crm_contact_id}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            Frappe Cloud Synced
                          </span>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleSyncToCrm(lead.id)}
                          disabled={syncingId === lead.id}
                          className="flex items-center gap-1.5 px-2.5 py-1 bg-secondary hover:bg-primary/20 text-foreground hover:text-primary rounded text-xs font-medium transition-colors border border-border disabled:opacity-50"
                        >
                          <ExternalLink className={`h-3 w-3 ${syncingId === lead.id ? 'animate-spin' : ''}`} />
                          {syncingId === lead.id ? 'Pushing...' : 'Sync to Frappe'}
                        </button>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleDelete(lead.id)}
                        className="p-1.5 text-muted-foreground hover:text-destructive rounded transition-colors"
                        title="Delete Lead"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Lead Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-card border border-border w-full max-w-lg rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <Users className="h-5 w-5 text-primary" />
                Add New Prospect Lead
              </h3>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="text-muted-foreground hover:text-foreground text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateLead} className="space-y-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Full Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. John Doe"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="w-full mt-1 px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Phone Number</label>
                  <input
                    type="text"
                    placeholder="+91 98765 43210"
                    value={formData.phone}
                    onChange={(e) => setFormData({...formData, phone: e.target.value})}
                    className="w-full mt-1 px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Email Address</label>
                  <input
                    type="email"
                    placeholder="john@example.com"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    className="w-full mt-1 px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Company / Location</label>
                  <input
                    type="text"
                    placeholder="Acme Corp"
                    value={formData.company}
                    onChange={(e) => setFormData({...formData, company: e.target.value})}
                    className="w-full mt-1 px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Budget</label>
                  <input
                    type="text"
                    placeholder="e.g. $5,000 or ₹2,00,000"
                    value={formData.budget}
                    onChange={(e) => setFormData({...formData, budget: e.target.value})}
                    className="w-full mt-1 px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">Project Requirement / Scope</label>
                <textarea
                  rows={2}
                  placeholder="Need custom mobile application with WhatsApp automation..."
                  value={formData.requirement}
                  onChange={(e) => setFormData({...formData, requirement: e.target.value})}
                  className="w-full mt-1 px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-border">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-border rounded-lg text-sm hover:bg-secondary transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg text-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {submitting ? 'Saving...' : 'Create Lead'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
