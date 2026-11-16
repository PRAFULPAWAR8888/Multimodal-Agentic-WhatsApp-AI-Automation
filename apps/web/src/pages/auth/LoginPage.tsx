import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MessageCircle, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { apiClient } from '@/services/api'

export default function LoginPage() {
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('Admin@123')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const setAuth = useAuthStore(state => state.setAuth)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    
    try {
      const response = await apiClient.post('/auth/login', { email, password })
      const data = response.data
      const user = data.user || { id: 'a36883dc-addf-4c3b-bdde-f57af9211453', email, full_name: 'Administrator', is_active: true }
      const workspace = data.workspace || { id: 'fb06fb3d-08f4-454c-9422-50f60c25239c', name: 'Default Workspace', slug: 'default', plan: 'pro' }
      
      setAuth(user, workspace, data.access_token)
      navigate('/dashboard')
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.detail || 'Invalid email or password'
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md bg-card border border-border rounded-2xl p-8 shadow-xl">
        <div className="flex justify-center mb-6">
          <div className="bg-primary/10 p-3 rounded-full text-whatsapp">
            <MessageCircle className="h-8 w-8" />
          </div>
        </div>
        <h2 className="text-2xl font-bold text-center mb-2">Welcome Back</h2>
        <p className="text-muted-foreground text-center mb-8 text-sm">Sign in to WhatsApp AI Platform</p>
        
        {error && <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md mb-4 text-center">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input 
              type="email" 
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full bg-background border border-border rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="you@company.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Password</label>
            <input 
              type="password" 
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="w-full bg-background border border-border rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="••••••••"
            />
          </div>
          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium rounded-md py-2 px-4 transition-colors flex justify-center items-center"
          >
            {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Sign In'}
          </button>
        </form>

        <p className="text-center mt-6 text-sm text-muted-foreground">
          Don't have an account? <Link to="/register" className="text-primary hover:underline">Register</Link>
        </p>
      </div>
    </div>
  )
}
