import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity, Ambulance, BarChart3, Bot, ChevronLeft, LayoutDashboard,
  LogOut, Package, Settings, Stethoscope, Leaf, Users,
} from 'lucide-react'

import { useAuth } from '@/context/AuthContext'
import { ROLES, ROLE_LABELS } from '@/lib/constants'
import { cn } from '@/lib/utils'

const ALL_ROLES = Object.values(ROLES)

// Nav items are filtered by role, so a user never sees a link they cannot open.
const NAV_ITEMS = [
  { to: '/dashboard/admin', label: 'Admin', icon: LayoutDashboard, roles: [ROLES.ADMIN] },
  { to: '/dashboard/doctor', label: 'Doctor', icon: Stethoscope, roles: [ROLES.DOCTOR, ROLES.ADMIN] },
  { to: '/dashboard/emergency', label: 'Emergency', icon: Ambulance, roles: [ROLES.NURSE, ROLES.DOCTOR, ROLES.ADMIN, ROLES.MANAGER] },
  { to: '/dashboard/inventory', label: 'Inventory', icon: Package, roles: [ROLES.PHARMACIST, ROLES.ADMIN, ROLES.MANAGER] },
  { to: '/dashboard/sustainability', label: 'Sustainability', icon: Leaf, roles: [ROLES.SUSTAINABILITY_OFFICER, ROLES.MANAGER, ROLES.ADMIN] },
  { to: '/dashboard/executive', label: 'Executive', icon: BarChart3, roles: [ROLES.MANAGER, ROLES.ADMIN] },
  { to: '/agents', label: 'AI Agents', icon: Bot, roles: [ROLES.ADMIN, ROLES.MANAGER, ROLES.DOCTOR, ROLES.NURSE] },
  { to: '/analytics', label: 'Analytics', icon: Users, roles: [ROLES.ADMIN, ROLES.MANAGER] },
]

// Settings is available to every role, so it lives outside the filtered list.
const SETTINGS_ITEM = { to: '/settings', label: 'Settings', icon: Settings, roles: ALL_ROLES }

export function Sidebar({ collapsed = false, onToggle, onNavigate }) {
  const { user, logout } = useAuth()
  const items = NAV_ITEMS.filter((item) => item.roles.includes(user?.role))

  return (
    <motion.aside
      animate={{ width: collapsed ? 76 : 248 }}
      transition={{ duration: 0.25, ease: 'easeInOut' }}
      className="relative flex h-full flex-col border-r border-border"
      style={{ background: 'hsl(var(--sidebar))' }}
    >
      {/* Brand */}
      <div className={cn('flex h-16 items-center gap-2.5 px-4', collapsed && 'justify-center px-0')}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-gradient shadow-glow">
          <Activity className="h-5 w-5 text-white" />
        </div>
        {!collapsed && (
          <div className="leading-tight">
            <p className="font-bold">HealMatrix</p>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">AI Platform</p>
          </div>
        )}
      </div>

      {/* Collapse toggle */}
      {onToggle && (
        <button
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="absolute -right-3 top-20 z-10 hidden h-6 w-6 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-elevated transition-colors hover:text-foreground lg:flex"
        >
          <ChevronLeft className={cn('h-3.5 w-3.5 transition-transform', collapsed && 'rotate-180')} />
        </button>
      )}

      <nav className="flex-1 space-y-1 overflow-y-auto scrollbar-slim px-3 py-2">
        {!collapsed && (
          <p className="px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Workspace
          </p>
        )}
        {[...items, SETTINGS_ITEM].map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
            className={({ isActive }) =>
              cn(
                'focus-ring group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all',
                collapsed && 'justify-center px-0',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-brand-gradient shadow-glow"
                  />
                )}
                <item.icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                {!collapsed && <span>{item.label}</span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="border-t border-border p-3">
        <div className={cn('mb-1 flex items-center gap-3 rounded-lg px-2 py-2', collapsed && 'justify-center px-0')}>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-sm font-semibold text-white">
            {user?.full_name?.charAt(0) || '?'}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{user?.full_name}</p>
              <p className="truncate text-xs text-muted-foreground">{ROLE_LABELS[user?.role]}</p>
            </div>
          )}
        </div>
        <button
          onClick={logout}
          title={collapsed ? 'Sign out' : undefined}
          className={cn(
            'focus-ring flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground',
            collapsed && 'justify-center px-0'
          )}
        >
          <LogOut className="h-[18px] w-[18px]" />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </motion.aside>
  )
}
