import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MessageCircle, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'

export default function RegisterPage() {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    workspaceName: ''
  })
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const setAuth = useAuthStore(state => state.setAuth)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    
    // Mock register
    setTimeout(() => {
      setAuth(
        { id: '1', email: formData.email, full_name: formData.fullName, is_active: true },
        { id: 'w1', name: formData.workspaceName, slug: formData.workspaceName.toLowerCase().replace(/\s+/g, '-'), plan: 'free' },
        'mock-jwt-token'
      )
      navigate('/dashboard')
    }, 1000)
  }

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md bg-card border border-border rounded-2xl p-8 shadow-xl">
        <div className="flex justify-center mb-6">
          <div className="bg-primary/10 p-3 rounded-full text-whatsapp">
            <MessageCircle className="h-8 w-8" />
          </div>
        </div>
        <h2 className="text-2xl font-bold text-center mb-2">Create Account</h2>
        <p className="text-muted-foreground text-center mb-8 text-sm">Start automating WhatsApp interactions</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Full Name</label>
            <input 
              type="text" required
              value={formData.fullName} onChange={e => setFormData({...formData, fullName: e.target.value})}
              className="w-full bg-background border border-border rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input 
              type="email" required
              value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})}
              className="w-full bg-background border border-border rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Workspace Name</label>
            <input 
              type="text" required
              value={formData.workspaceName} onChange={e => setFormData({...formData, workspaceName: e.target.value})}
              className="w-full bg-background border border-border rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Password</label>
            <input 
              type="password" required
              value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})}
              className="w-full bg-background border border-border rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <button 
            type="submit" disabled={loading}
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium rounded-md py-2 px-4 mt-2 transition-colors flex justify-center items-center"
          >
            {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Create Account'}
          </button>
        </form>

        <p className="text-center mt-6 text-sm text-muted-foreground">
          Already have an account? <Link to="/login" className="text-primary hover:underline">Sign In</Link>
        </p>
      </div>
    </div>
  )
}
