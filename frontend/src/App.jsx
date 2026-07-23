import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'

import { AuthProvider } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { ProtectedRoute, PublicOnlyRoute } from '@/components/RouteGuards'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { ErrorBoundary } from '@/components/ErrorBoundary'

// Route-level code splitting keeps the initial bundle small.
const Landing = lazy(() => import('@/pages/Landing'))
const Login = lazy(() => import('@/pages/auth/Login'))
const Settings = lazy(() => import('@/pages/Settings'))
const DoctorDashboard = lazy(() => import('@/pages/dashboards/DoctorDashboard'))
const EmergencyDashboard = lazy(() => import('@/pages/dashboards/EmergencyDashboard'))
const AgentsDashboard = lazy(() => import('@/pages/dashboards/AgentsDashboard'))
const AdminDashboard = lazy(() => import('@/pages/dashboards/AdminDashboard'))
const InventoryDashboard = lazy(() => import('@/pages/dashboards/InventoryDashboard'))
const SustainabilityDashboard = lazy(() => import('@/pages/dashboards/SustainabilityDashboard'))
const ExecutiveDashboard = lazy(() => import('@/pages/dashboards/ExecutiveDashboard'))
const PlaceholderDashboard = lazy(() => import('@/pages/dashboards/PlaceholderDashboard'))
const NotFound = lazy(() => import('@/pages/errors/NotFound'))
const Unauthorized = lazy(() => import('@/pages/errors/Unauthorized'))

function SuspenseFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  )
}

export default function App() {
  const { resolvedTheme } = useTheme()

  return (
    <AuthProvider>
      <Toaster
        position="top-right"
        theme={resolvedTheme}
        toastOptions={{ className: 'font-sans' }}
      />
      <ErrorBoundary>
        <Suspense fallback={<SuspenseFallback />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route
              path="/login"
              element={
                <PublicOnlyRoute>
                  <Login />
                </PublicOnlyRoute>
              }
            />
            <Route path="/unauthorized" element={<Unauthorized />} />

            <Route
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard/doctor" element={<DoctorDashboard />} />
              <Route path="/dashboard/emergency" element={<EmergencyDashboard />} />
              <Route path="/agents" element={<AgentsDashboard />} />
              <Route path="/settings" element={<Settings />} />

              <Route path="/dashboard/admin" element={<AdminDashboard />} />
              <Route path="/dashboard/inventory" element={<InventoryDashboard />} />
              <Route path="/dashboard/sustainability" element={<SustainabilityDashboard />} />
              <Route path="/dashboard/executive" element={<ExecutiveDashboard />} />

              {/* Later-phase: a dedicated cross-cutting analytics explorer beyond
                  the per-role dashboards above. */}
              <Route
                path="/analytics"
                element={<PlaceholderDashboard title="Analytics" phase="Phase 6" endpoints={['/analytics/patients', '/analytics/occupancy']} />}
              />
            </Route>

            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </AuthProvider>
  )
}
