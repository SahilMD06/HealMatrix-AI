import { Bell, Menu, Moon, Search, Sun } from 'lucide-react'

import { useTheme } from '@/context/ThemeContext'
import { StatusDot } from '@/components/ui/StatusDot'
import { useApiHealth } from '@/hooks/useApiHealth'

/**
 * Top bar: page title, a command-palette trigger styled as search, live API
 * status, notifications, and the theme toggle.
 */
export function Header({ title, subtitle, onMenuClick, onSearchClick, actions }) {
  const { resolvedTheme, toggleTheme } = useTheme()
  const { data } = useApiHealth({ pollMs: 30000 })
  const online = data?.status === 'ready'

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b border-border bg-background/70 px-4 backdrop-blur-xl lg:px-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="focus-ring rounded-md p-2 hover:bg-secondary lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-lg font-semibold leading-tight">{title}</h1>
          {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Command palette trigger */}
        <button
          onClick={onSearchClick}
          className="focus-ring hidden items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground sm:flex"
        >
          <Search className="h-3.5 w-3.5" />
          <span>Search…</span>
          <kbd className="ml-4 rounded border border-border px-1.5 py-0.5 font-mono text-[10px]">⌘K</kbd>
        </button>

        {actions}

        {/* Live API status */}
        <div className="hidden items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs md:flex">
          <StatusDot tone={online ? 'online' : 'offline'} />
          <span className="text-muted-foreground">{online ? 'API live' : 'API offline'}</span>
        </div>

        <button
          aria-label="Notifications"
          className="focus-ring relative rounded-md p-2 hover:bg-secondary"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-triage-1" />
        </button>

        <button
          onClick={toggleTheme}
          aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`}
          className="focus-ring rounded-md p-2 hover:bg-secondary"
        >
          {resolvedTheme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
      </div>
    </header>
  )
}
