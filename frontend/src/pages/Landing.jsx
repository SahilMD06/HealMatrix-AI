import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity, ArrowRight, Bot, Droplets, Leaf, Recycle, Zap, ShieldCheck,
} from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { useTheme } from '@/context/ThemeContext'
import { Moon, Sun } from 'lucide-react'
import { AGENTS, SDG_GOALS } from '@/lib/constants'

const METRICS = [
  { label: 'faster triage decisions', value: '38%', icon: Activity },
  { label: 'lower energy intensity', value: '22%', icon: Zap },
  { label: 'less waste to landfill', value: '31%', icon: Recycle },
  { label: 'UN SDGs addressed', value: '6', icon: Leaf },
]

const STEPS = [
  { title: 'Observe', description: 'Agents read live telemetry: admissions, beds, meters, fleet.' },
  { title: 'Reason', description: 'Each agent applies trained models and domain rules to its slice.' },
  { title: 'Reconcile', description: 'Conflicts resolve by priority: safety, compliance, cost, sustainability.' },
  { title: 'Recommend', description: 'An executive plan lands on the right desk, every action traceable.' },
]

export default function Landing() {
  const { resolvedTheme, toggleTheme } = useTheme()

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-2 font-bold">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent">
              <Activity className="h-5 w-5 text-white" />
            </div>
            HealMatrix AI
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="focus-ring rounded-md p-2 hover:bg-secondary"
            >
              {resolvedTheme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
            <Link to="/login">
              <Button size="sm">Sign in</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="grid-backdrop pointer-events-none absolute inset-0" />
        <div className="relative mx-auto max-w-4xl px-6 py-24 text-center">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <span className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-secondary px-3 py-1 text-xs font-medium text-muted-foreground">
              <Bot className="h-3.5 w-3.5" /> Ten collaborating AI agents
            </span>
            <h1 className="text-balance text-4xl font-extrabold tracking-tight sm:text-6xl">
              Empowering Sustainable Hospitals Through{' '}
              <span className="text-gradient">Collaborative Agentic AI</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-balance text-lg text-muted-foreground">
              HealMatrix is an agentic operations layer for a network of hospitals. Autonomous
              agents cut waiting times and carbon from the same control plane.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link to="/login">
                <Button size="lg">
                  Explore the platform <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <a href="#agents">
                <Button size="lg" variant="outline">See the agents</Button>
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Metrics */}
      <section className="border-y border-border bg-card/50">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-6 py-10 lg:grid-cols-4">
          {METRICS.map((m) => (
            <div key={m.label} className="text-center">
              <m.icon className="mx-auto mb-2 h-5 w-5 text-primary" />
              <p className="font-mono text-3xl font-bold">{m.value}</p>
              <p className="mt-1 text-sm text-muted-foreground">{m.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Agents */}
      <section id="agents" className="mx-auto max-w-6xl px-6 py-20">
        <div className="mb-10 text-center">
          <h2 className="text-3xl font-bold">The agent network</h2>
          <p className="mt-2 text-muted-foreground">
            Ten specialists that negotiate through a shared state graph — not a chatbot.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {AGENTS.map((agent, i) => (
            <motion.div
              key={agent.key}
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.04 }}
              className="glass-card flex items-center gap-3"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                <Bot className="h-4 w-4 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold">{agent.name}</p>
                <p className="text-xs capitalize text-muted-foreground">{agent.domain}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-border bg-card/50">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">How it works</h2>
          </div>
          <div className="grid gap-6 md:grid-cols-4">
            {STEPS.map((step, i) => (
              <div key={step.title} className="relative">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary font-bold text-primary-foreground">
                  {i + 1}
                </div>
                <h3 className="font-semibold">{step.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SDGs */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="mb-10 text-center">
          <h2 className="text-3xl font-bold">Aligned to the UN SDGs</h2>
          <p className="mt-2 text-muted-foreground">Clinical outcomes and climate action, measured together.</p>
        </div>
        <div className="flex flex-wrap justify-center gap-3">
          {SDG_GOALS.map((goal) => (
            <div
              key={goal.number}
              className={`rounded-lg border px-4 py-3 ${
                goal.primary ? 'border-primary bg-primary/10' : 'border-border bg-card'
              }`}
            >
              <p className="font-mono text-lg font-bold">SDG {goal.number}</p>
              <p className="text-xs text-muted-foreground">{goal.title}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Value props */}
      <section className="border-t border-border bg-card/50">
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-20 md:grid-cols-3">
          {[
            { icon: ShieldCheck, title: 'Explainable by design', body: 'Every decision records its inputs, rationale and confidence. Nothing is a black box.' },
            { icon: Droplets, title: 'Sustainability native', body: 'Energy, water, waste and carbon are first-class, scored on every operational decision.' },
            { icon: Zap, title: 'Graceful under failure', body: 'Each agent has a deterministic fallback, so an LLM outage never stops the hospital.' },
          ].map((v) => (
            <div key={v.title} className="glass-card">
              <v.icon className="mb-3 h-6 w-6 text-primary" />
              <h3 className="font-semibold">{v.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{v.body}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-8 text-sm text-muted-foreground sm:flex-row">
          <p>HealMatrix AI · Final-year engineering project</p>
          <p>Academic demonstration · synthetic data · advisory outputs</p>
        </div>
      </footer>
    </div>
  )
}
