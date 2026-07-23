import { useState } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Activity, Eye, EyeOff } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { useAuth } from '@/context/AuthContext'
import { ROLE_HOME, ROLE_LABELS } from '@/lib/constants'

// One-click demo accounts. Essential for a viva or hackathon where switching
// roles quickly matters more than typing credentials.
const DEMO_ACCOUNTS = [
  { role: 'admin', email: 'admin@hmblr01.healmatrix.ai' },
  { role: 'doctor', email: 'doctor@hmblr01.healmatrix.ai' },
  { role: 'nurse', email: 'nurse@hmblr01.healmatrix.ai' },
  { role: 'pharmacist', email: 'pharmacist@hmblr01.healmatrix.ai' },
  { role: 'manager', email: 'manager@hmblr01.healmatrix.ai' },
  { role: 'sustainability_officer', email: 'sustainability@hmblr01.healmatrix.ai' },
]

const DEMO_PASSWORD = 'HealMatrix@2026'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const redirectTo = location.state?.from?.pathname

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const user = await login(email, password)
      navigate(redirectTo || ROLE_HOME[user.role] || '/dashboard/admin', { replace: true })
    } catch (err) {
      setError(err.message || 'Sign in failed. Check your credentials and try again.')
    } finally {
      setLoading(false)
    }
  }

  function fillDemo(account) {
    setEmail(account.email)
    setPassword(DEMO_PASSWORD)
    setError(null)
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel */}
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-primary/90 via-primary to-accent lg:block">
        <div className="grid-backdrop absolute inset-0 opacity-20" />
        <div className="relative flex h-full flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-2 text-lg font-bold">
            <Activity className="h-6 w-6" />
            HealMatrix AI
          </div>
          <div>
            <h1 className="text-4xl font-extrabold leading-tight">
              Empowering Sustainable Hospitals Through Collaborative Agentic AI.
            </h1>
            <p className="mt-4 max-w-md text-white/80">
              Ten specialised AI agents observe, reason and act — cutting waiting times and
              carbon from a single control plane.
            </p>
          </div>
          <p className="text-sm text-white/60">
            Academic demonstration · all data is synthetic · agent outputs are advisory
          </p>
        </div>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center bg-background px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-sm"
        >
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2 text-lg font-bold text-primary">
              <Activity className="h-6 w-6" /> HealMatrix AI
            </div>
          </div>

          <h2 className="text-2xl font-bold">Welcome back</h2>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to your HealMatrix workspace</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="focus-ring w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
                placeholder="you@hospital.ai"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="focus-ring w-full rounded-md border border-input bg-card px-3 py-2 pr-10 text-sm"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <p className="mt-1.5 text-xs text-muted-foreground">
                Forgot your password? Ask your hospital administrator to reset it — HealMatrix
                accounts are provisioned per hospital, not self-registered.
              </p>
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" loading={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs text-muted-foreground">Demo accounts</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <div className="grid grid-cols-2 gap-2">
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.role}
                type="button"
                onClick={() => fillDemo(account)}
                className="focus-ring rounded-md border border-border bg-card px-3 py-2 text-left text-xs font-medium transition-colors hover:bg-secondary"
              >
                {ROLE_LABELS[account.role]}
              </button>
            ))}
          </div>
          <p className="mt-3 text-center text-xs text-muted-foreground">
            One click fills credentials · password{' '}
            <code className="font-mono">HealMatrix@2026</code>
          </p>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            <Link to="/" className="hover:text-foreground">
              ← Back to home
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  )
}
