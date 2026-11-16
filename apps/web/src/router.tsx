import { createBrowserRouter, Navigate } from 'react-router-dom'
import { lazy } from 'react'
import { AppLayout } from './components/layout/AppLayout'
import { useAuthStore } from './stores/authStore'

const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const PlaygroundPage = lazy(() => import('./pages/PlaygroundPage'))
const KnowledgePage = lazy(() => import('./pages/KnowledgePage'))
const ConversationsPage = lazy(() => import('./pages/ConversationsPage'))
const InboxPage = lazy(() => import('./pages/InboxPage'))
const LeadsPage = lazy(() => import('./pages/LeadsPage'))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'))
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
      { path: 'playground', element: <PlaygroundPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'conversations', element: <ConversationsPage /> },
      { path: 'inbox', element: <InboxPage /> },
      { path: 'knowledge', element: <KnowledgePage /> },
      { path: 'leads', element: <LeadsPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
    ],
  },
  {
    path: '*',
    element: <div className="flex h-screen items-center justify-center">404 Not Found</div>,
  },
])
