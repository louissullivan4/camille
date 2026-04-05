import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Theme } from '@carbon/react'

import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import AppShell from './components/AppShell'

import Login from './pages/auth/Login'
import ResetPasswordRequest from './pages/auth/ResetPasswordRequest'
import ResetPasswordConfirm from './pages/auth/ResetPasswordConfirm'
import Signup from './pages/auth/Signup'
import Dashboard from './pages/Dashboard'
import AdminDashboard from './pages/admin/AdminDashboard'
import OrganizationList from './pages/admin/OrganizationList'
import InviteOrgManager from './pages/admin/InviteOrgManager'

import './carbon.scss'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
})

function ShellRoute({ children, requiredRole }: { children: React.ReactNode; requiredRole?: import('./api/types').UserRole | import('./api/types').UserRole[] }) {
  return (
    <ProtectedRoute requiredRole={requiredRole}>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Theme theme="g10">
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              {/* Public routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/reset-password" element={<ResetPasswordRequest />} />
              <Route path="/reset-password/confirm" element={<ResetPasswordConfirm />} />
              <Route path="/signup" element={<Signup />} />

              {/* Shared protected routes */}
              <Route
                path="/dashboard"
                element={
                  <ShellRoute>
                    <Dashboard />
                  </ShellRoute>
                }
              />

              {/* Admin routes */}
              <Route
                path="/admin"
                element={
                  <ShellRoute requiredRole={['admin']}>
                    <AdminDashboard />
                  </ShellRoute>
                }
              />
              <Route
                path="/admin/organizations"
                element={
                  <ShellRoute requiredRole={['admin']}>
                    <OrganizationList />
                  </ShellRoute>
                }
              />
              <Route
                path="/admin/organizations/invite"
                element={
                  <ShellRoute requiredRole={['admin']}>
                    <InviteOrgManager />
                  </ShellRoute>
                }
              />

              {/* Default redirect */}
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </Theme>
    </QueryClientProvider>
  )
}
