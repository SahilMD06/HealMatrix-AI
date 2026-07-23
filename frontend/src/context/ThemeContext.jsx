import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { STORAGE_KEYS } from '@/lib/constants'

const ThemeContext = createContext(null)

/** Resolve the OS preference when the user has chosen "system". */
function systemTheme() {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function readStoredTheme() {
  if (typeof window === 'undefined') return 'system'
  return window.localStorage.getItem(STORAGE_KEYS.THEME) || 'system'
}

/**
 * Applies the `dark` class to <html>, which is what every Tailwind token keys off.
 * Supports light, dark and system, and follows the OS live while set to system.
 */
export function ThemeProvider({ children }) {
  const [preference, setPreference] = useState(readStoredTheme)
  const [resolved, setResolved] = useState(() =>
    readStoredTheme() === 'system' ? systemTheme() : readStoredTheme()
  )

  useEffect(() => {
    const next = preference === 'system' ? systemTheme() : preference
    setResolved(next)

    const root = window.document.documentElement
    root.classList.toggle('dark', next === 'dark')
    root.style.colorScheme = next

    window.localStorage.setItem(STORAGE_KEYS.THEME, preference)
  }, [preference])

  useEffect(() => {
    if (preference !== 'system') return undefined

    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event) => {
      const next = event.matches ? 'dark' : 'light'
      setResolved(next)
      window.document.documentElement.classList.toggle('dark', next === 'dark')
    }

    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [preference])

  const toggleTheme = useCallback(() => {
    setPreference((current) => (current === 'dark' ? 'light' : 'dark'))
  }, [])

  const value = useMemo(
    () => ({ theme: preference, resolvedTheme: resolved, setTheme: setPreference, toggleTheme }),
    [preference, resolved, toggleTheme]
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used inside a ThemeProvider')
  }
  return context
}
