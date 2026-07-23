import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '@/context/AuthContext'

function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading HealMatrix…</p>
      </div>
    </div>
  )
}

/** Gate for authenticated routes. Preserves the intended destination for post-login redirect. */
export function ProtectedRoute({ children, roles }) {
  const { isAuthenticated, loading, user } = useAuth()
  const location = useLocation()

  if (loading) return <FullScreenLoader />
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/unauthorized" replace />

  return children
}

/** Keeps an already-authenticated user out of the login page. */
export function PublicOnlyRoute({ children }) {
  const { isAuthenticated, loading, homeRoute } = useAuth()
  if (loading) return <FullScreenLoader />
  if (isAuthenticated) return <Navigate to={homeRoute} replace />
  return children
}
