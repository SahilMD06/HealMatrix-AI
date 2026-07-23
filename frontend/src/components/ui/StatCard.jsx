import { motion } from 'framer-motion'

import { cn } from '@/lib/utils'
import { useAnimatedCounter } from '@/hooks/useAnimatedCounter'

const ACCENTS = {
  indigo: { icon: 'text-brand-indigo', glow: 'group-hover:shadow-glow', ring: 'bg-brand-indigo/10' },
  cyan: { icon: 'text-brand-cyan', glow: 'group-hover:shadow-glow-cyan', ring: 'bg-brand-cyan/10' },
  emerald: { icon: 'text-brand-emerald', glow: 'group-hover:shadow-glow-emerald', ring: 'bg-brand-emerald/10' },
  rose: { icon: 'text-triage-1', glow: '', ring: 'bg-triage-1/10' },
}

/**
 * Headline KPI tile with an animated counter and an accent-tinted icon well.
 * Numeric values ease to their target when they change, giving a live feel.
 */
export function StatCard({
  icon: Icon,
  label,
  value,
  unit,
  decimals = 0,
  accent = 'indigo',
  trend,
  trendLabel,
  animate = true,
  delay = 0,
}) {
  const numeric = typeof value === 'number'
  const counter = useAnimatedCounter(numeric ? value : 0, { decimals })
  const shown = numeric ? (animate ? counter : value.toLocaleString('en-IN')) : (value ?? '—')

  const a = ACCENTS[accent] || ACCENTS.indigo
  const trendPositive = trend > 0
  const trendNegative = trend < 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
      className={cn('premium-card group p-5', a.glow)}
    >
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        {Icon && (
          <span className={cn('flex h-8 w-8 items-center justify-center rounded-lg', a.ring)}>
            <Icon className={cn('h-4 w-4', a.icon)} aria-hidden="true" />
          </span>
        )}
      </div>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="tabular font-mono text-3xl font-bold tracking-tight">{shown}</span>
        {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
      </div>
      {trend !== undefined && trend !== null && (
        <p
          className={cn(
            'mt-1 text-xs font-medium',
            trendPositive && 'text-brand-emerald',
            trendNegative && 'text-triage-1',
            !trendPositive && !trendNegative && 'text-muted-foreground'
          )}
        >
          {trendPositive ? '▲' : trendNegative ? '▼' : '•'} {Math.abs(trend)}
          {trendLabel ? ` ${trendLabel}` : ''}
        </p>
      )}
    </motion.div>
  )
}
