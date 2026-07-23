import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { authService } from '@/services/auth'
import { ROLE_HOME } from '@/lib/constants'

const AuthContext = createContext(null)

/**
 * Holds the authenticated user and exposes login/logout. On mount, if a token is
 * present it revalidates it against /auth/me so a stale session is cleared rather
 * than trusted.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function bootstrap() {
      if (!authService.hasToken()) {
        setLoading(false)
        return
      }
      try {
        const profile = await authService.me()
        if (active) setUser(profile)
      } catch {
        authService.logout()
      } finally {
        if (active) setLoading(false)
      }
    }
    bootstrap()
    return () => {
      active = false
    }
  }, [])

  const login = useCallback(async (email, password) => {
    const profile = await authService.login(email, password)
    setUser(profile)
    return profile
  }, [])

  const logout = useCallback(() => {
    authService.logout()
    setUser(null)
  }, [])

  // Lets Settings (or anything else) patch the in-memory profile after a
  // successful /auth/me PATCH, without a full re-fetch.
  const updateUser = useCallback((patch) => {
    setUser((current) => (current ? { ...current, ...patch } : current))
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      updateUser,
      isAuthenticated: Boolean(user),
      homeRoute: user ? ROLE_HOME[user.role] || '/dashboard/admin' : '/login',
    }),
    [user, loading, login, logout, updateUser]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
