import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Activity } from 'lucide-react'

/**
 * Shared full-screen frame for 404/403/500 states: brand mark, animated glow
 * backdrop, a big status glyph, and a primary/secondary action pair. Every
 * error page below composes this instead of duplicating the layout.
 */
export function ErrorShell({ code, icon: Icon, title, description, primaryAction, secondaryAction }) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-6 text-center">
      <div className="grid-backdrop pointer-events-none absolute inset-0 opacity-40" />
      <div className="bg-brand-radial pointer-events-none absolute inset-x-0 top-0 h-[60vh]" />

      <Link to="/" className="relative mb-10 flex items-center gap-2 text-lg font-bold text-foreground">
        <Activity className="h-6 w-6 text-primary" />
        HealMatrix AI
      </Link>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative flex flex-col items-center"
      >
        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-brand-gradient shadow-glow">
          <Icon className="h-9 w-9 text-white" aria-hidden="true" />
        </div>

        <p className="font-mono text-sm font-semibold uppercase tracking-widest text-primary">
          Error {code}
        </p>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-3 max-w-md text-muted-foreground">{description}</p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          {primaryAction}
          {secondaryAction}
        </div>
      </motion.div>
    </div>
  )
}
