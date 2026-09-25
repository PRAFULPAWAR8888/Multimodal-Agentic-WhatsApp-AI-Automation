import { Link, Outlet, useLocation } from 'react-router-dom'
import { 
  LayoutDashboard, MessageCircle, Inbox, BookOpen, 
  Users, BarChart3, FlaskConical, Settings, LogOut 
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/lib/utils'

export function AppLayout() {
  const location = useLocation()
  const { user, workspace, clearAuth } = useAuthStore()

  const navItems = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Conversations', path: '/conversations', icon: MessageCircle },
    { name: 'Inbox', path: '/inbox', icon: Inbox },
    { name: 'Knowledge Base', path: '/knowledge', icon: BookOpen },
    { name: 'Leads', path: '/leads', icon: Users },
    { name: 'Analytics', path: '/analytics', icon: BarChart3 },
    { name: 'Playground', path: '/playground', icon: FlaskConical },
    { name: 'Settings', path: '/settings', icon: Settings },
  ]

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="w-60 border-r border-border bg-card flex flex-col">
        <div className="p-4 md:p-6 flex items-center gap-2 text-whatsapp font-bold text-lg">
          <MessageCircle className="h-6 w-6" />
          <span>WhatsApp AI</span>
        </div>
        
        <nav className="flex-1 px-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname.startsWith(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  isActive 
                    ? "bg-primary/10 text-primary" 
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.name}
              </Link>
            )
          })}
        </nav>

        <div className="p-4 border-t border-border mt-auto">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-8 w-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold">
              {user?.full_name?.[0] || 'U'}
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-sm font-medium truncate">{user?.full_name || 'User'}</p>
              <p className="text-xs text-muted-foreground truncate">{workspace?.name || 'Workspace'}</p>
            </div>
          </div>
          <button 
            onClick={clearAuth}
            className="flex items-center gap-2 text-sm text-destructive hover:text-destructive/80 transition-colors w-full px-2"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {import.meta.env.VITE_MOCK_MODE === 'true' && (
          <div className="bg-warning/20 text-warning px-4 py-1 text-xs text-center font-medium">
            MOCK MODE ENABLED
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-4 md:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
