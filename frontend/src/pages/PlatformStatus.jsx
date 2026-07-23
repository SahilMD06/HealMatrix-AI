import { motion } from 'framer-motion'
import { Activity, Database, Moon, RefreshCw, Sparkles, Sun } from 'lucide-react'

import { useApiHealth } from '@/hooks/useApiHealth'
import { useTheme } from '@/context/ThemeContext'
import { AGENTS, SDG_GOALS } from '@/lib/constants'
import { cn } from '@/lib/utils'

/**
 * Platform status screen.
 *
 * A real, working page rather than a placeholder: it exercises the theme system,
 * the Axios client, the glassmorphic design tokens and Framer Motion, and reports
 * live backend readiness. It doubles as the Phase 1 smoke test.
 */
export default function PlatformStatus() {
  const { resolvedTheme, toggleTheme } = useTheme()
  const { data, error, loading, refetch } = useApiHealth({ pollMs: 15000 })

  const apiOnline = Boolean(data && !error)
  const mongoOnline = data?.dependencies?.mongodb === 'up'
  const llmConfigured = data?.dependencies?.gemini === 'configured'

  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      <div className="grid-backdrop pointer-events-none absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto max-w-5xl px-6 py-16">
        <header className="mb-12 flex items-start justify-between gap-6">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-border bg-secondary px-3 py-1 text-xs font-medium text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              Phase 1 · Architecture &amp; Scaffold
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">
              <span className="text-gradient">HealMatrix AI</span>
            </h1>
            <p className="mt-3 max-w-xl text-balance text-muted-foreground">
              Multi-Agent Sustainable Healthcare Intelligence Platform. Empowering sustainable
              hospitals through collaborative agentic AI.
            </p>
          </div>

          <button
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} theme`}
            className="focus-ring rounded-lg border border-border bg-card p-2.5 text-foreground transition-colors hover:bg-secondary"
          >
            {resolvedTheme === 'dark' ? (
              <Sun className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Moon className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        </header>

        <section aria-labelledby="services-heading" className="mb-12">
          <div className="mb-4 flex items-center justify-between">
            <h2 id="services-heading" className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Service Health
            </h2>
            <button
              type="button"
              onClick={refetch}
              disabled={loading}
              className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} aria-hidden="true" />
              Refresh
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <StatusCard
              icon={Activity}
              label="FastAPI Backend"
              online={apiOnline}
              loading={loading}
              detail={apiOnline ? 'Responding to readiness probe' : 'Start the backend on :8000'}
            />
            <StatusCard
              icon={Database}
              label="MongoDB Atlas"
              online={mongoOnline}
              loading={loading}
              detail={mongoOnline ? 'Connected, indexes bootstrapped' : 'Awaiting connection'}
            />
            <StatusCard
              icon={Sparkles}
              label="Gemini API"
              online={llmConfigured}
              loading={loading}
              detail={llmConfigured ? 'Key configured' : 'Set GOOGLE_API_KEY to enable agents'}
            />
          </div>
        </section>

        <section aria-labelledby="agents-heading" className="mb-12">
          <h2 id="agents-heading" className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Agent Roster · {AGENTS.length} agents
          </h2>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {AGENTS.map((agent, index) => (
              <motion.div
                key={agent.key}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04, duration: 0.3 }}
                className="glass-card flex items-center justify-between !p-3.5"
              >
                <span className="text-sm font-medium">{agent.name}</span>
                <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                  {agent.domain}
                </span>
              </motion.div>
            ))}
          </div>
        </section>

        <section aria-labelledby="sdg-heading">
          <h2 id="sdg-heading" className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            UN Sustainable Development Goals
          </h2>
          <div className="flex flex-wrap gap-2">
            {SDG_GOALS.map((goal) => (
              <span
                key={goal.number}
                className={cn(
                  'rounded-full border px-3 py-1.5 text-xs font-medium',
                  goal.primary
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-card text-muted-foreground'
                )}
              >
                SDG {goal.number} · {goal.title}
              </span>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

function StatusCard({ icon: Icon, label, online, loading, detail }) {
  return (
    <div className="glass-card">
      <div className="mb-3 flex items-center justify-between">
        <Icon className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <span
          className={cn(
            'h-2.5 w-2.5 rounded-full',
            loading ? 'bg-muted-foreground' : online ? 'bg-sustain-excellent' : 'bg-destructive'
          )}
          role="status"
          aria-label={loading ? 'Checking' : online ? 'Online' : 'Offline'}
        />
      </div>
      <p className="text-sm font-semibold">{label}</p>
      <p className="mt-1 text-xs text-muted-foreground">{loading ? 'Checking…' : detail}</p>
    </div>
  )
}
