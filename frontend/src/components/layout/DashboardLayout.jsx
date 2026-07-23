import { useMemo, useState } from 'react'
import { Outlet } from 'react-router-dom'
import {
  Ambulance, BarChart3, Bot, LayoutDashboard, Package, Settings, Stethoscope, Leaf,
} from 'lucide-react'

import { Sidebar } from './Sidebar'
import { CommandPalette, useCommandPalette } from '@/components/ui/CommandPalette'
import { useAuth } from '@/context/AuthContext'
import { ROLES } from '@/lib/constants'

const ALL_ROLES = Object.values(ROLES)

// Actions available in the ⌘K palette. Kept here so the shell owns navigation.
// `roles` mirrors Sidebar's NAV_ITEMS exactly — the palette must not offer a
// destination the sidebar itself would hide, or a non-admin user can land on
// an admin-only dashboard and hit a wall of 403s from its own API calls.
const COMMAND_ACTIONS = [
  { label: 'Doctor Dashboard', to: '/dashboard/doctor', icon: Stethoscope, group: 'Go to', roles: [ROLES.DOCTOR, ROLES.ADMIN] },
  { label: 'Emergency & Operations', to: '/dashboard/emergency', icon: Ambulance, group: 'Go to', roles: [ROLES.NURSE, ROLES.DOCTOR, ROLES.ADMIN, ROLES.MANAGER] },
  { label: 'AI Agents', to: '/agents', icon: Bot, group: 'Go to', roles: [ROLES.ADMIN, ROLES.MANAGER, ROLES.DOCTOR, ROLES.NURSE] },
  { label: 'Admin Dashboard', to: '/dashboard/admin', icon: LayoutDashboard, group: 'Go to', roles: [ROLES.ADMIN] },
  { label: 'Inventory', to: '/dashboard/inventory', icon: Package, group: 'Go to', roles: [ROLES.PHARMACIST, ROLES.ADMIN, ROLES.MANAGER] },
  { label: 'Sustainability', to: '/dashboard/sustainability', icon: Leaf, group: 'Go to', roles: [ROLES.SUSTAINABILITY_OFFICER, ROLES.MANAGER, ROLES.ADMIN] },
  { label: 'Executive', to: '/dashboard/executive', icon: BarChart3, group: 'Go to', roles: [ROLES.MANAGER, ROLES.ADMIN, ROLES.SUSTAINABILITY_OFFICER] },
  { label: 'Settings', to: '/settings', icon: Settings, group: 'Go to', roles: ALL_ROLES },
]

/**
 * App shell: collapsible sidebar on desktop, slide-over on mobile, plus the
 * command palette. Pages render their own Header via PageContainer.
 */
export function DashboardLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const palette = useCommandPalette()
  const { user } = useAuth()
  const paletteActions = useMemo(
    () => COMMAND_ACTIONS.filter((action) => action.roles.includes(user?.role)),
    [user?.role]
  )

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <div className="hidden lg:block">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <div className="absolute left-0 top-0 h-full">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        <Outlet
          context={{
            openMenu: () => setMobileOpen(true),
            openSearch: () => palette.setOpen(true),
          }}
        />
      </div>

      <CommandPalette open={palette.open} onOpenChange={palette.setOpen} actions={paletteActions} />
    </div>
  )
}
