import { useState } from 'react'
import { toast } from 'sonner'
import { CreditCard, KeyRound, Palette, User } from 'lucide-react'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs'
import { EmptyState } from '@/components/ui/States'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { authService } from '@/services/auth'
import { ROLE_LABELS } from '@/lib/constants'

const THEME_OPTIONS = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'Match system' },
]

function ProfileTab() {
  const { user, updateUser } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [phone, setPhone] = useState(user?.phone || '')
  const [saving, setSaving] = useState(false)

  const dirty = fullName !== (user?.full_name || '') || phone !== (user?.phone || '')

  async function handleSave(event) {
    event.preventDefault()
    setSaving(true)
    try {
      const updated = await authService.updateProfile({ full_name: fullName, phone: phone || null })
      updateUser(updated)
      toast.success('Profile updated')
    } catch (err) {
      toast.error(err.message || 'Could not update profile')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>How you appear across HealMatrix.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSave} className="max-w-md space-y-4">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-lg font-semibold text-white shadow-glow">
              {user?.full_name?.charAt(0) || '?'}
            </div>
            <div>
              <p className="font-medium">{user?.email}</p>
              <Badge variant="primary" className="mt-1">
                {ROLE_LABELS[user?.role] || user?.role}
              </Badge>
            </div>
          </div>

          <div>
            <label htmlFor="full_name" className="mb-1.5 block text-sm font-medium">
              Full name
            </label>
            <input
              id="full_name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              minLength={2}
              maxLength={120}
              required
              className="focus-ring w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label htmlFor="phone" className="mb-1.5 block text-sm font-medium">
              Phone <span className="text-muted-foreground">(optional)</span>
            </label>
            <input
              id="phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="focus-ring w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
              placeholder="+91 …"
            />
          </div>

          <div className="grid grid-cols-2 gap-4 border-t border-border pt-4 text-sm">
            <div>
              <p className="text-muted-foreground">Hospital ID</p>
              <p className="mt-0.5 font-mono text-xs">{user?.hospital_id || '—'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Last login</p>
              <p className="mt-0.5 text-xs">
                {user?.last_login_at ? new Date(user.last_login_at).toLocaleString() : '—'}
              </p>
            </div>
          </div>

          <Button type="submit" loading={saving} disabled={!dirty}>
            Save changes
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function SecurityTab() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)

    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match.')
      return
    }
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters.')
      return
    }

    setSaving(true)
    try {
      await authService.changePassword(currentPassword, newPassword)
      toast.success('Password changed')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(err.message || 'Could not change password')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
        <CardDescription>
          Choose a password that mixes letters and numbers. Changing it does not sign out your
          other sessions.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="max-w-md space-y-4">
          <div>
            <label htmlFor="current_password" className="mb-1.5 block text-sm font-medium">
              Current password
            </label>
            <input
              id="current_password"
              type="password"
              required
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="focus-ring w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="new_password" className="mb-1.5 block text-sm font-medium">
              New password
            </label>
            <input
              id="new_password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="focus-ring w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="confirm_password" className="mb-1.5 block text-sm font-medium">
              Confirm new password
            </label>
            <input
              id="confirm_password"
              type="password"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="focus-ring w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
            />
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </div>
          )}

          <Button type="submit" loading={saving}>
            Update password
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function AppearanceTab() {
  const { theme, setTheme } = useTheme()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Appearance</CardTitle>
        <CardDescription>Applies instantly, and is remembered on this device.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid max-w-md grid-cols-3 gap-3">
          {THEME_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => setTheme(option.value)}
              className={
                'focus-ring flex flex-col items-center gap-2 rounded-lg border p-4 text-sm font-medium transition-all ' +
                (theme === option.value
                  ? 'border-primary/50 bg-primary/10 text-primary shadow-glow'
                  : 'border-border bg-card text-muted-foreground hover:border-primary/30 hover:text-foreground')
              }
            >
              <Palette className="h-5 w-5" />
              {option.label}
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function BillingTab() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Billing</CardTitle>
        <CardDescription>Not applicable to this deployment.</CardDescription>
      </CardHeader>
      <CardContent>
        <EmptyState
          icon={CreditCard}
          title="No billing on this deployment"
          description="HealMatrix is running as an academic, multi-hospital-network demonstration with no metering or invoicing configured. In a commercial deployment this tab would show the workspace's plan, usage-based charges, and invoice history."
        />
      </CardContent>
    </Card>
  )
}

export default function SettingsPage() {
  return (
    <PageContainer title="Settings" subtitle="Your profile, security and preferences">
      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">
            <User className="mr-1.5 h-3.5 w-3.5" /> Profile
          </TabsTrigger>
          <TabsTrigger value="security">
            <KeyRound className="mr-1.5 h-3.5 w-3.5" /> Security
          </TabsTrigger>
          <TabsTrigger value="appearance">
            <Palette className="mr-1.5 h-3.5 w-3.5" /> Appearance
          </TabsTrigger>
          <TabsTrigger value="billing">
            <CreditCard className="mr-1.5 h-3.5 w-3.5" /> Billing
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <ProfileTab />
        </TabsContent>
        <TabsContent value="security">
          <SecurityTab />
        </TabsContent>
        <TabsContent value="appearance">
          <AppearanceTab />
        </TabsContent>
        <TabsContent value="billing">
          <BillingTab />
        </TabsContent>
      </Tabs>
    </PageContainer>
  )
}
