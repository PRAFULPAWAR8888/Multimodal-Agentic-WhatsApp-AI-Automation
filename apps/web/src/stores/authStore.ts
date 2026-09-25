import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
}

interface Workspace {
  id: string
  name: string
  slug: string
  plan: string
}

interface AuthState {
  user: User | null
  workspace: Workspace | null
  accessToken: string | null
  isAuthenticated: boolean
  setAuth: (user: User, workspace: Workspace, token: string) => void
  clearAuth: () => void
  setWorkspace: (workspace: Workspace) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      workspace: null,
      accessToken: null,
      isAuthenticated: false,
      setAuth: (user, workspace, token) => {
        localStorage.setItem('access_token', token)
        set({ user, workspace, accessToken: token, isAuthenticated: true })
      },
      clearAuth: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, workspace: null, accessToken: null, isAuthenticated: false })
      },
      setWorkspace: (workspace) => set({ workspace }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        workspace: state.workspace,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
