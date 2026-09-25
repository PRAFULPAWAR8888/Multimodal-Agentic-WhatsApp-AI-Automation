import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { lazy } from 'react'
import { AppLayout } from './components/layout/AppLayout'
import { useAuthStore } from './stores/authStore'

const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const LoginPage = lazy(() => import('./pages/auth/LoginPage'))
const RegisterPage = lazy(() => import('./pages/auth/RegisterPage'))

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuthenticated = useAuthStore(state => state.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

const PublicRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuthenticated = useAuthStore(state => state.isAuthenticated)
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: (
      <PublicRoute>
        <LoginPage />
      </PublicRoute>
    ),
  },
  {
    path: '/register',
    element: (
      <PublicRoute>
        <RegisterPage />
      </PublicRoute>
    ),
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      // Mock routes for others
      { path: 'conversations', element: <div>Conversations (PLANNED)</div> },
      { path: 'inbox', element: <div>Inbox (PLANNED)</div> },
      { path: 'knowledge', element: <div>Knowledge Base (PLANNED)</div> },
      { path: 'leads', element: <div>Leads (PLANNED)</div> },
      { path: 'analytics', element: <div>Analytics (PLANNED)</div> },
      { path: 'playground', element: <div>Playground (PLANNED)</div> },
      { path: 'settings', element: <div>Settings (PLANNED)</div> },
    ],
  },
  {
    path: '*',
    element: <div className="flex h-screen items-center justify-center">404 Not Found</div>,
  },
])
