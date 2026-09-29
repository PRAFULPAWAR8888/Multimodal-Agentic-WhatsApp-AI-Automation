import { useState, useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'
import { apiClient } from '../services/api'
import { Save, Loader2, AlertCircle } from 'lucide-react'

export default function SettingsPage() {
  const { workspace } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const [formData, setFormData] = useState({
    business_name: '',
    business_description: '',
    ai_persona_name: '',
    ai_persona_role: '',
    ai_persona_tone: '',
    ai_response_language: 'en',
    ai_max_response_length: 300,
    ai_use_emoji: true,
    ai_custom_instructions: '',
    ai_restrictions: '',
    escalation_keywords_json: ['human', 'agent', 'support', 'help'],
  })

  useEffect(() => {
    if (!workspace?.id) return

    const fetchProfile = async () => {
      setLoading(true)
      try {
        const response = await apiClient.get(`/workspaces/${workspace.id}`)
        if (response.data.business_profile) {
          setFormData((prev) => ({
            ...prev,
            ...response.data.business_profile,
          }))
        }
      } catch (err: any) {
        setError(err.response?.data?.message || 'Failed to load business profile')
      } finally {
        setLoading(false)
      }
    }
    fetchProfile()
  }, [workspace])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target as any
    if (type === 'checkbox') {
      setFormData((prev) => ({ ...prev, [name]: (e.target as HTMLInputElement).checked }))
    } else if (name === 'escalation_keywords_json') {
      setFormData((prev) => ({ ...prev, [name]: value.split(',').map((s: string) => s.trim()) }))
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspace?.id) return

    setSaving(true)
    setError(null)
    setSuccessMsg(null)

    try {
      await apiClient.patch(`/workspaces/${workspace.id}/business-profile`, formData)
      setSuccessMsg('Business profile saved successfully!')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to save profile')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">AI Persona & Settings</h1>
        <p className="text-muted-foreground mt-1">Configure how the AI represents your business on WhatsApp.</p>
      </div>

      {error && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-md flex items-center gap-3">
          <AlertCircle className="h-5 w-5" />
          <p className="text-sm font-medium">{error}</p>
        </div>
      )}

      {successMsg && (
        <div className="bg-whatsapp/10 text-whatsapp p-4 rounded-md flex items-center gap-3 border border-whatsapp/20">
          <Save className="h-5 w-5" />
          <p className="text-sm font-medium">{successMsg}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8 bg-card border border-border p-6 rounded-xl shadow-sm">
        {/* Core Identity */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold border-b border-border pb-2">Business Identity</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Business Name</label>
              <input
                type="text"
                name="business_name"
                value={formData.business_name}
                onChange={handleChange}
                className="w-full p-2 rounded-md border border-input bg-background"
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Business Description</label>
              <input
                type="text"
                name="business_description"
                value={formData.business_description}
                onChange={handleChange}
                className="w-full p-2 rounded-md border border-input bg-background"
                placeholder="We sell premium coffee beans..."
              />
            </div>
          </div>
        </div>

        {/* AI Persona */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold border-b border-border pb-2">AI Persona</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Agent Name</label>
              <input
                type="text"
                name="ai_persona_name"
                value={formData.ai_persona_name}
                onChange={handleChange}
                className="w-full p-2 rounded-md border border-input bg-background"
                placeholder="e.g. Sarah"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Role</label>
              <input
                type="text"
                name="ai_persona_role"
                value={formData.ai_persona_role}
                onChange={handleChange}
                className="w-full p-2 rounded-md border border-input bg-background"
                placeholder="e.g. Sales Assistant"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Tone</label>
              <input
                type="text"
                name="ai_persona_tone"
                value={formData.ai_persona_tone}
                onChange={handleChange}
                className="w-full p-2 rounded-md border border-input bg-background"
                placeholder="e.g. Friendly & Professional"
              />
            </div>
          </div>
          
          <div className="space-y-2">
            <label className="text-sm font-medium">Custom Instructions</label>
            <textarea
              name="ai_custom_instructions"
              value={formData.ai_custom_instructions}
              onChange={handleChange}
              rows={3}
              className="w-full p-2 rounded-md border border-input bg-background font-mono text-sm"
              placeholder="e.g. Always greet with 'Namaste'. Mention our weekend sale."
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-destructive">Strict Restrictions (Guardrails)</label>
            <textarea
              name="ai_restrictions"
              value={formData.ai_restrictions}
              onChange={handleChange}
              rows={2}
              className="w-full p-2 rounded-md border border-input bg-background font-mono text-sm"
              placeholder="e.g. Never promise discounts over 10%. Never mention competitors."
            />
          </div>
        </div>

        {/* Configuration */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold border-b border-border pb-2">Behavior Configuration</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Response Length (Tokens)</label>
              <input
                type="number"
                name="ai_max_response_length"
                value={formData.ai_max_response_length}
                onChange={handleChange}
                className="w-full p-2 rounded-md border border-input bg-background"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Response Language Code</label>
              <input
                type="text"
                name="ai_response_language"
                value={formData.ai_response_language}
                onChange={handleChange}
                className="w-full p-2 rounded-md border border-input bg-background"
                placeholder="en, hi, mr"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="ai_use_emoji"
              name="ai_use_emoji"
              checked={formData.ai_use_emoji}
              onChange={handleChange}
              className="h-4 w-4 rounded border-input"
            />
            <label htmlFor="ai_use_emoji" className="text-sm font-medium">Allow AI to use Emojis 😊</label>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Human Escalation Keywords (comma-separated)</label>
            <input
              type="text"
              name="escalation_keywords_json"
              value={formData.escalation_keywords_json.join(', ')}
              onChange={handleChange}
              className="w-full p-2 rounded-md border border-input bg-background"
              placeholder="human, agent, support, manager"
            />
            <p className="text-xs text-muted-foreground">If the user types any of these, the AI will pause and route to the human inbox.</p>
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t border-border">
          <button
            type="submit"
            disabled={saving}
            className="bg-whatsapp hover:bg-whatsapp/90 text-white px-6 py-2 rounded-md font-medium flex items-center gap-2 transition-colors disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    </div>
  )
}
